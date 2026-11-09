"""Tests for stale.

The invariants worth guarding are not "does it find a broken link". They are:

  1. a verdict is never returned without the evidence that produced it
  2. the answer does not depend on the filesystem the checker happens to run
     on - the case mode decides, not NTFS
  3. the three option flags each change the answer in a stated direction and
     nowhere else
  4. markdown is parsed, not grepped: a heading inside a code fence is not a
     heading, and a link inside one is not a link

Run:  python -m pytest test_stale.py -q        (40+ cases)
"""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from stale import (Finding, REASONS, Report, Tree, anchor_table, cause_of,
                   check_anchor, check_link, check_quote, join_rel, parse_note,
                   rawify, read_tree, scan, slugify)

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = os.path.join(HERE, "corpus")


@pytest.fixture(scope="module")
def corpus():
    return read_tree(CORPUS)


def tree(**files):
    return dict(files)


# --------------------------------------------------------------------------- #
# slugs
# --------------------------------------------------------------------------- #

def test_slug_lowercases_and_hyphenates():
    assert slugify("Open Questions") == "open-questions"


def test_slug_drops_punctuation_rather_than_replacing_it():
    # the surprise: an apostrophe and a question mark VANISH
    assert slugify("What's next?") == "whats-next"


def test_slug_leaves_a_double_hyphen_where_a_word_was_removed():
    # "Rollout / rollback" -> the slash is dropped, both spaces survive
    assert slugify("Rollout / rollback") == "rollout--rollback"
    assert slugify("Benchmarks & numbers") == "benchmarks--numbers"


def test_slug_keeps_digits_and_underscores():
    assert slugify("Step 1: install_now") == "step-1-install_now"


def test_slug_trims_before_it_hyphenates():
    assert slugify("   Done   ") == "done"


def test_raw_keeps_the_punctuation_slug_drops():
    assert rawify("What's next?") == "what's-next?"
    assert rawify("Rollout / rollback") == "rollout-/-rollback"


def test_raw_collapses_whitespace_runs_to_one_hyphen():
    assert rawify("a   b\tc") == "a-b-c"


def test_slug_and_raw_agree_on_plain_ascii_headings():
    for h in ("Background", "The decision", "open questions"):
        assert slugify(h) == rawify(h)


def test_anchor_table_suffixes_duplicates_in_slug_mode():
    t = anchor_table(["Notes", "Notes", "Notes"], "slug")
    assert set(t) == {"notes", "notes-1", "notes-2"}


def test_anchor_table_lets_duplicates_collide_in_raw_mode():
    t = anchor_table(["Notes", "Notes", "Notes"], "raw")
    assert set(t) == {"notes"}


def test_anchor_table_is_empty_for_a_note_with_no_headings():
    assert anchor_table([], "slug") == {}


# --------------------------------------------------------------------------- #
# path joining
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("base,link,want", [
    ("notes", "other.md", "notes/other.md"),
    ("notes/archive", "../other.md", "notes/other.md"),
    ("notes/archive", "../../src/a.py", "src/a.py"),
    ("notes", "./x.md", "notes/x.md"),
    ("", "x.md", "x.md"),
    ("notes", "/abs.md", "abs.md"),
    ("notes/a/b", "../../c/d.md", "notes/c/d.md"),
])
def test_join_rel(base, link, want):
    assert join_rel(base, link) == want


def test_join_rel_cannot_climb_above_the_root():
    assert join_rel("notes", "../../../../escape.md") == "escape.md"


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #

def test_headings_are_found_with_line_numbers():
    n = parse_note("a.md", "# One\n\ntext\n\n## Two\n")
    assert n.headings == [(1, "One"), (5, "Two")]


def test_closing_hashes_are_stripped_from_a_heading():
    n = parse_note("a.md", "## Two ##\n")
    assert n.heading_texts == ["Two"]


def test_a_hash_inside_a_code_fence_is_not_a_heading():
    n = parse_note("a.md", "# Real\n\n```python\n# not a heading\n```\n")
    assert n.heading_texts == ["Real"]


def test_a_link_inside_a_code_fence_is_not_a_link():
    n = parse_note("a.md", "```\n[see](gone.md)\n```\n")
    assert n.links == []


def test_a_tilde_fence_is_a_fence_too():
    n = parse_note("a.md", "~~~\n# no\n~~~\n# yes\n")
    assert n.heading_texts == ["yes"]


def test_a_backtick_fence_does_not_close_a_tilde_fence():
    n = parse_note("a.md", "~~~\n```\n# still inside\n~~~\n# out\n")
    assert n.heading_texts == ["out"]


def test_links_are_found_with_label_and_target():
    n = parse_note("a.md", "see [the doc](b.md#x) and [other](c.md)\n")
    assert n.links == [(1, "the doc", "b.md#x"), (1, "other", "c.md")]


def test_a_quote_block_is_captured_with_its_range_and_body():
    text = "<!-- from: ../src/a.py#L3-L4 -->\n```python\nx = 1\ny = 2\n```\n"
    n = parse_note("notes/a.md", text)
    assert n.quotes == [(1, "../src/a.py", 3, 4, ["x = 1", "y = 2"])]


def test_a_fence_without_a_from_comment_is_not_a_quote():
    n = parse_note("a.md", "```python\nx = 1\n```\n")
    assert n.quotes == []


def test_an_unterminated_fence_swallows_the_rest_of_the_note():
    # deliberate: half a fence is a broken note, and guessing where it ends
    # would invent headings that are not there
    n = parse_note("a.md", "# Top\n```\n# inside\n## also inside\n")
    assert n.heading_texts == ["Top"]


# --------------------------------------------------------------------------- #
# links
# --------------------------------------------------------------------------- #

def test_a_link_to_a_file_that_exists_resolves():
    t = Tree(tree(**{"notes/a.md": "", "notes/b.md": ""}))
    n = parse_note("notes/a.md", "[x](b.md)")
    f, hit = check_link(n, 1, "b.md", t)
    assert not f.stale and f.reason == "resolved" and hit == "notes/b.md"


def test_a_link_to_a_file_that_does_not_exist_is_stale():
    t = Tree(tree(**{"notes/a.md": ""}))
    n = parse_note("notes/a.md", "[x](gone.md)")
    f, hit = check_link(n, 1, "gone.md", t)
    assert f.stale and f.reason == "target-missing" and hit is None


def test_every_finding_carries_non_empty_evidence():
    t = Tree(tree(**{"notes/a.md": "", "notes/B.md": ""}))
    n = parse_note("notes/a.md", "x")
    for target in ("B.md", "b.md", "gone.md"):
        f, _ = check_link(n, 1, target, t)
        assert f.evidence and len(f.evidence) > 5


def test_a_case_only_difference_is_STALE_under_strict():
    t = Tree(tree(**{"notes/a.md": "", "notes/Setup.md": ""}))
    n = parse_note("notes/a.md", "x")
    f, hit = check_link(n, 1, "setup.md", t, case="strict")
    assert f.stale and f.reason == "case-only-match"
    assert "Setup.md" in f.evidence
    assert hit == "notes/Setup.md"


def test_a_case_only_difference_is_FINE_under_insensitive():
    t = Tree(tree(**{"notes/a.md": "", "notes/Setup.md": ""}))
    n = parse_note("notes/a.md", "x")
    f, hit = check_link(n, 1, "setup.md", t, case="insensitive")
    assert not f.stale and f.reason == "resolved-case-insensitively"
    assert hit == "notes/Setup.md"


def test_INVERSION_the_case_verdict_does_not_consult_the_real_filesystem():
    # the whole point: on NTFS os.path.exists("setup.md") is True for
    # Setup.md, so a checker built on the filesystem reports PASS here and
    # the same tree 404s in CI. stale answers from the index.
    t = Tree(tree(**{"notes/a.md": "", "notes/Setup.md": ""}))
    n = parse_note("notes/a.md", "x")
    assert check_link(n, 1, "setup.md", t, case="strict")[0].stale is True


def test_a_missing_file_beats_a_case_match_in_specificity():
    t = Tree(tree(**{"notes/a.md": "", "notes/Setup.md": ""}))
    n = parse_note("notes/a.md", "x")
    assert check_link(n, 1, "nope.md", t)[0].reason == "target-missing"
    assert check_link(n, 1, "setup.md", t)[0].reason == "case-only-match"


def test_the_fragment_is_not_part_of_the_file_lookup():
    t = Tree(tree(**{"notes/a.md": "", "notes/b.md": "# H\n"}))
    n = parse_note("notes/a.md", "x")
    f, hit = check_link(n, 1, "b.md#anything", t)
    assert not f.stale and hit == "notes/b.md"


def test_external_links_are_not_checked(corpus):
    files = dict(corpus)
    files["notes/ext.md"] = "# E\n\n[x](https://example.com/gone.md)\n[y](mailto:a@b.c)\n"
    rep = scan(files)
    assert not [f for f in rep.findings if f.note == "notes/ext.md"]


# --------------------------------------------------------------------------- #
# anchors
# --------------------------------------------------------------------------- #

def test_an_anchor_that_matches_a_heading_resolves():
    files = {"notes/a.md": "[x](b.md#open-questions)", "notes/b.md": "## Open questions\n"}
    notes = {p: parse_note(p, t) for p, t in files.items()}
    f = check_anchor(notes["notes/a.md"], 1, "b.md#open-questions", "notes/b.md", notes, "slug")
    assert not f.stale and f.reason == "resolved"


def test_an_anchor_to_a_heading_that_was_renamed_is_stale():
    files = {"notes/a.md": "x", "notes/b.md": "## Open questions\n"}
    notes = {p: parse_note(p, t) for p, t in files.items()}
    f = check_anchor(notes["notes/a.md"], 1, "b.md#open-issues", "notes/b.md", notes, "slug")
    assert f.stale and f.reason == "anchor-missing"
    assert "notes/b.md" in f.evidence


def test_the_anchor_evidence_lists_what_the_target_actually_has():
    files = {"notes/a.md": "x", "notes/b.md": "## Alpha\n## Beta\n"}
    notes = {p: parse_note(p, t) for p, t in files.items()}
    f = check_anchor(notes["notes/a.md"], 1, "b.md#gamma", "notes/b.md", notes, "slug")
    assert "alpha" in f.evidence and "beta" in f.evidence


def test_INVERSION_slug_and_raw_disagree_on_a_punctuated_heading():
    files = {"notes/a.md": "x", "notes/b.md": "## What's next?\n"}
    notes = {p: parse_note(p, t) for p, t in files.items()}
    a = check_anchor(notes["notes/a.md"], 1, "b.md#whats-next", "notes/b.md", notes, "slug")
    b = check_anchor(notes["notes/a.md"], 1, "b.md#whats-next", "notes/b.md", notes, "raw")
    assert a.stale is False and b.stale is True


def test_INVERSION_and_they_disagree_the_other_way_round_too():
    files = {"notes/a.md": "x", "notes/b.md": "## What's next?\n"}
    notes = {p: parse_note(p, t) for p, t in files.items()}
    a = check_anchor(notes["notes/a.md"], 1, "b.md#what's-next?", "notes/b.md", notes, "slug")
    b = check_anchor(notes["notes/a.md"], 1, "b.md#what's-next?", "notes/b.md", notes, "raw")
    assert a.stale is True and b.stale is False


def test_a_duplicate_heading_anchor_works_in_slug_mode_only():
    files = {"notes/a.md": "x", "notes/b.md": "## Notes\n\n## Notes\n"}
    notes = {p: parse_note(p, t) for p, t in files.items()}
    assert check_anchor(notes["notes/a.md"], 1, "b.md#notes-1", "notes/b.md", notes, "slug").stale is False
    assert check_anchor(notes["notes/a.md"], 1, "b.md#notes-1", "notes/b.md", notes, "raw").stale is True


def test_an_anchor_into_the_same_note_is_checked(corpus):
    files = dict(corpus)
    files["notes/self.md"] = "# S\n\n## Real one\n\n[a](#real-one)\n\n[b](#imaginary)\n"
    rep = scan(files)
    mine = [f for f in rep.findings if f.note == "notes/self.md"]
    assert len(mine) == 2
    assert [f.stale for f in sorted(mine, key=lambda f: f.line)] == [False, True]


def test_an_anchor_is_not_checked_when_the_file_itself_is_missing():
    files = {"notes/a.md": "[x](gone.md#whatever)\n"}
    rep = scan(files)
    assert [f.kind for f in rep.findings] == ["link"]


def test_an_anchor_into_a_non_note_target_is_skipped():
    files = {"notes/a.md": "[x](../src/a.py#L1)\n", "src/a.py": "x = 1\n"}
    rep = scan(files)
    assert [f.kind for f in rep.findings] == ["link"]


# --------------------------------------------------------------------------- #
# quotes
# --------------------------------------------------------------------------- #

SRC = "line one\nline two\nline three\nline four\n"


def _quote_note(body, rng="../src/a.py#L2-L3"):
    return "<!-- from: %s -->\n```python\n%s\n```\n" % (rng, body)


def test_a_quote_that_matches_byte_for_byte_resolves():
    files = {"notes/a.md": _quote_note("line two\nline three"), "src/a.py": SRC}
    rep = scan(files)
    q = [f for f in rep.findings if f.kind == "quote"][0]
    assert not q.stale and q.reason == "resolved"


def test_a_quote_whose_source_changed_is_stale_with_the_differing_line():
    files = {"notes/a.md": _quote_note("line two\nline THREE"), "src/a.py": SRC}
    q = [f for f in scan(files).findings if f.kind == "quote"][0]
    assert q.stale and q.reason == "content-drifted"
    assert "line 3" in q.evidence


def test_the_drift_evidence_shows_both_sides_from_where_they_differ():
    long_a = "x" * 60 + "ALPHA"
    long_b = "x" * 60 + "BETA"
    files = {"notes/a.md": _quote_note(long_b, "../src/a.py#L1-L1"),
             "src/a.py": long_a + "\n"}
    q = [f for f in scan(files).findings if f.kind == "quote"][0]
    assert "ALPHA" in q.evidence and "BETA" in q.evidence


def test_a_quote_whose_source_file_is_gone_says_source_missing():
    files = {"notes/a.md": _quote_note("line two\nline three", "../src/gone.py#L2-L3")}
    q = [f for f in scan(files).findings if f.kind == "quote"][0]
    assert q.stale and q.reason == "source-missing"


def test_a_range_past_the_end_of_the_file_says_so():
    files = {"notes/a.md": _quote_note("line two", "../src/a.py#L2-L99"), "src/a.py": SRC}
    q = [f for f in scan(files).findings if f.kind == "quote"][0]
    assert q.stale and q.reason == "range-out-of-bounds"
    assert "5 lines" in q.evidence


def test_an_inverted_range_is_rejected_rather_than_silently_empty():
    files = {"notes/a.md": _quote_note("", "../src/a.py#L3-L2"), "src/a.py": SRC}
    q = [f for f in scan(files).findings if f.kind == "quote"][0]
    assert q.stale and q.reason == "range-out-of-bounds"


def test_INVERSION_a_whitespace_only_difference_is_STALE_under_exact():
    files = {"notes/a.md": _quote_note("  line two\n  line three"), "src/a.py": SRC}
    q = [f for f in scan(files, quote="exact").findings if f.kind == "quote"][0]
    assert q.stale and q.reason == "content-drifted"
    assert "normalisation" in q.evidence


def test_INVERSION_the_same_block_is_FINE_under_normalised():
    files = {"notes/a.md": _quote_note("  line two\n  line three"), "src/a.py": SRC}
    q = [f for f in scan(files, quote="normalised").findings if f.kind == "quote"][0]
    assert not q.stale and q.reason == "resolved-after-normalising"


def test_normalising_does_not_forgive_a_real_change():
    files = {"notes/a.md": _quote_note("  line two\n  line THREE"), "src/a.py": SRC}
    q = [f for f in scan(files, quote="normalised").findings if f.kind == "quote"][0]
    assert q.stale and q.reason == "content-drifted"


def test_a_trailing_space_is_a_whitespace_difference_not_a_change():
    files = {"notes/a.md": _quote_note("line two \nline three"), "src/a.py": SRC}
    assert scan(files, quote="exact").findings[0].stale is True
    assert scan(files, quote="normalised").findings[0].stale is False


def test_a_quote_whose_source_only_differs_in_case_follows_the_case_mode():
    files = {"notes/a.md": _quote_note("line two\nline three", "../src/A.py#L2-L3"),
             "src/a.py": SRC}
    assert scan(files, case="strict").findings[0].reason == "case-only-match"
    assert scan(files, case="insensitive").findings[0].reason == "resolved"


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #

def test_bad_option_values_raise():
    for kw in ({"case": "fuzzy"}, {"anchors": "github"}, {"quote": "loose"}):
        with pytest.raises(ValueError):
            scan({"a.md": "# x\n"}, **kw)


def test_an_empty_tree_is_a_valid_empty_report():
    rep = scan({})
    assert rep.notes_scanned == 0 and rep.findings == [] and rep.base_rate == 0.0


def test_a_tree_with_no_notes_scans_nothing():
    rep = scan({"src/a.py": SRC})
    assert rep.notes_scanned == 0 and rep.refs_checked == 0


def test_every_reason_used_is_a_declared_reason(corpus):
    for case in ("strict", "insensitive"):
        for anchors in ("slug", "raw"):
            for quote in ("exact", "normalised"):
                rep = scan(corpus, case=case, anchors=anchors, quote=quote)
                for f in rep.findings:
                    assert f.reason in REASONS


def test_stale_and_clean_partition_the_findings(corpus):
    rep = scan(corpus)
    assert len(rep.stale) + len([f for f in rep.findings if not f.stale]) == len(rep.findings)


def test_the_finding_count_equals_the_references_checked(corpus):
    rep = scan(corpus)
    assert len(rep.findings) == rep.refs_checked


def test_findings_are_sorted_and_reproducible(corpus):
    a = scan(corpus)
    b = scan(dict(reversed(list(corpus.items()))))
    assert [f.__dict__ for f in a.findings] == [f.__dict__ for f in b.findings]


def test_the_base_rate_is_notes_flagged_over_notes_scanned(corpus):
    rep = scan(corpus)
    assert rep.base_rate == pytest.approx(len(rep.stale_notes) / rep.notes_scanned)


def test_relaxing_the_case_mode_never_adds_a_link_finding(corpus):
    strict = scan(corpus, case="strict")
    loose = scan(corpus, case="insensitive")
    s = {(f.note, f.line, f.ref) for f in strict.stale if f.kind == "link"}
    l = {(f.note, f.line, f.ref) for f in loose.stale if f.kind == "link"}
    assert l <= s


def test_relaxing_the_quote_mode_never_adds_a_quote_finding(corpus):
    ex = {(f.note, f.line) for f in scan(corpus, quote="exact").stale if f.kind == "quote"}
    no = {(f.note, f.line) for f in scan(corpus, quote="normalised").stale if f.kind == "quote"}
    assert no <= ex


def test_INVERSION_relaxing_the_case_mode_can_EXPOSE_new_anchor_checks(corpus):
    # a link that failed on case never had its #fragment checked. Fixing the
    # case mode does not only remove findings - it uncovers the ones that
    # were hiding behind them.
    strict = scan(corpus, case="strict")
    loose = scan(corpus, case="insensitive")
    s = {(f.note, f.line, f.ref) for f in strict.findings if f.kind == "anchor"}
    l = {(f.note, f.line, f.ref) for f in loose.findings if f.kind == "anchor"}
    assert len(l - s) > 0


def test_causes_never_outnumber_findings(corpus):
    rep = scan(corpus)
    assert 0 < len(rep.causes()) <= len(rep.stale)


def test_causes_account_for_every_stale_finding(corpus):
    rep = scan(corpus)
    assert sum(len(fs) for _c, fs in rep.causes()) == len(rep.stale)


def test_causes_are_ordered_biggest_first(corpus):
    counts = [len(fs) for _c, fs in scan(corpus).causes()]
    assert counts == sorted(counts, reverse=True)


def test_one_renamed_file_collapses_to_one_cause():
    files = {"notes/a.md": "[x](gone.md)\n", "notes/b.md": "[y](gone.md)\n",
             "notes/c.md": "[z](gone.md)\n"}
    rep = scan(files)
    assert len(rep.stale) == 3 and len(rep.causes()) == 1
    assert rep.causes()[0][1][0].reason == "target-missing"


def test_cause_of_is_stable_for_the_same_underlying_fault():
    f1 = Finding("a.md", 1, "link", "gone.md", True, "target-missing", "no file at gone.md")
    f2 = Finding("z.md", 9, "link", "../gone.md", True, "target-missing", "no file at gone.md")
    assert cause_of(f1) == cause_of(f2)


# --------------------------------------------------------------------------- #
# the corpus, and the CLI
# --------------------------------------------------------------------------- #

def test_the_corpus_is_on_disk():
    assert os.path.isdir(CORPUS)


def test_the_corpus_has_notes_and_sources(corpus):
    assert len([p for p in corpus if p.endswith(".md")]) >= 25
    assert len([p for p in corpus if p.endswith(".py")]) >= 5


def test_the_corpus_contains_case_only_collisions(corpus):
    rep = scan(corpus, case="strict")
    assert [f for f in rep.stale if f.reason == "case-only-match"]


def test_the_corpus_contains_drifted_quotes(corpus):
    rep = scan(corpus)
    assert [f for f in rep.stale if f.reason == "content-drifted"]


def test_the_corpus_base_rate_is_high_enough_to_be_a_problem(corpus):
    # the finding the page is built on: a detector that flags most of the
    # pile is a detector nobody reads twice
    assert scan(corpus).base_rate > 0.5


def test_regenerating_the_corpus_is_deterministic(tmp_path):
    import make_corpus
    a = make_corpus.build()
    b = make_corpus.build()
    assert a == b


def test_the_corpus_on_disk_matches_the_generator(corpus):
    import make_corpus
    built = make_corpus.build()
    assert set(built) == set(corpus)
    for k in built:
        assert built[k] == corpus[k], k


def test_the_cli_runs_and_exits_2_when_something_is_stale():
    r = subprocess.run([sys.executable, "stale.py", "corpus"],
                       cwd=HERE, capture_output=True, text=True)
    assert r.returncode == 2
    assert "base rate" in r.stdout


def test_the_cli_json_is_parseable_and_self_consistent():
    r = subprocess.run([sys.executable, "stale.py", "corpus", "--json"],
                       cwd=HERE, capture_output=True, text=True)
    d = json.loads(r.stdout)
    assert d["stale"] == len(d["findings"])
    assert sum(c["count"] for c in d["causes"]) == d["stale"]
    assert 0 < d["base_rate"] <= 1


def test_the_cli_exits_0_on_a_clean_tree(tmp_path):
    (tmp_path / "a.md").write_text("# A\n\n## H\n\n[x](a.md#h)\n", encoding="utf-8")
    r = subprocess.run([sys.executable, os.path.join(HERE, "stale.py"), str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode == 0
