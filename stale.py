"""stale - find the notes that have gone out of date with what they point at.

A folder of notes rots from the edges. The note is still there, still
readable, still confidently telling you to "see the setup doc" - and the
setup doc was renamed eight months ago. Nothing in markdown notices. The
link renders, the anchor renders, the code block you pasted from a source
file renders exactly as it did the day you pasted it, including the two
lines that source file no longer contains.

stale reads a tree of notes and reports three kinds of rot:

  link    an internal link whose target file is not in the tree
  anchor  a link to a heading that the target file no longer has
  quote   a fenced block that claims to be copied from a source file
          (<!-- from: src/parse.py#L10-L18 -->) whose lines have changed

Every verdict carries the evidence that produced it - the line it was found
on, the reference as written, and what was actually there instead. A report
you cannot audit is a report you will start ignoring.

Three things it deliberately makes you choose, because each one changes the
answer and no default is right for everybody:

  --case     strict | insensitive   how a path is matched
  --anchors  slug   | raw           how a heading anchor is matched
  --quote    exact  | normalised    how a quoted block is compared

Usage:
    python stale.py <dir> [--case strict] [--anchors slug] [--quote exact]
                          [--json] [--all]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- #
# slugs
# --------------------------------------------------------------------------- #

# The characters GitHub keeps when it turns a heading into an anchor. Anything
# else is DROPPED - not replaced with a hyphen, dropped - which is why
# "Rollout / rollback" becomes "rollout--rollback" with two hyphens and not
# one. That surprise is the whole reason this is a mode and not a constant.
_SLUG_KEEP = re.compile(r"[a-z0-9 _-]")


def slugify(text: str) -> str:
    """GitHub-style anchor slug for one heading, before de-duplication."""
    s = text.strip().lower()
    kept = [ch for ch in s if _SLUG_KEEP.match(ch)]
    return "".join(kept).replace(" ", "-")


def rawify(text: str) -> str:
    """The naive slug: lowercase, trim, whitespace runs to a single hyphen,
    and nothing removed.

    This is what most hand-rolled link checkers do, and it is wrong in two
    specific ways that this tool measures rather than argues about: it keeps
    punctuation that GitHub strips, and it has no notion of a duplicate
    heading, so two headings with the same text collide instead of getting
    the -1 suffix GitHub gives the second one.
    """
    return re.sub(r"\s+", "-", text.strip().lower())


def anchor_table(headings, mode: str) -> dict:
    """Map anchor -> heading text, for one matching mode.

    In slug mode a repeated anchor gets the GitHub suffix (-1, -2, ...). In
    raw mode it does not, and the later heading simply wins - which is the
    behaviour, not an oversight, and the tests pin it.
    """
    table = {}
    counts = {}
    for text in headings:
        if mode == "slug":
            base = slugify(text)
            n = counts.get(base, 0)
            counts[base] = n + 1
            key = base if n == 0 else "%s-%d" % (base, n)
        else:
            key = rawify(text)
        table[key] = text
    return table


# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #

def join_rel(base_dir: str, link: str) -> str:
    """Resolve a relative link against the directory of the note.

    Done on strings, never on the filesystem. A checker that calls
    os.path.exists answers a question about the machine it is running on,
    and the machine it is running on is not the machine that will serve the
    notes. See CASE, below.
    """
    parts = []
    start = [] if link.startswith("/") else [p for p in base_dir.split("/") if p]
    for p in start + link.lstrip("/").split("/"):
        if p in ("", "."):
            continue
        if p == "..":
            if parts:
                parts.pop()
            continue
        parts.append(p)
    return "/".join(parts)


class Tree:
    """The set of files that exist, and the two ways of looking one up.

    CASE. NTFS and APFS match filenames case-insensitively; ext4 does not.
    A link written as `setup.md` against a file called `Setup.md` therefore
    works on the laptop it was written on and 404s the moment the notes are
    published from Linux. stale resolves against an INDEX rather than
    against the filesystem so that the answer is the same on every machine,
    and so that the two answers can be compared.
    """

    def __init__(self, files: dict):
        self.files = dict(files)
        self.lower = {}
        for name in sorted(self.files):
            self.lower.setdefault(name.lower(), name)

    def exact(self, path: str):
        return path if path in self.files else None

    def insensitive(self, path: str):
        return self.lower.get(path.lower())

    def __contains__(self, path):
        return path in self.files

    def __len__(self):
        return len(self.files)


# --------------------------------------------------------------------------- #
# reading one note
# --------------------------------------------------------------------------- #

_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE = re.compile(r"^\s*(`{3,}|~{3,})\s*$")
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_TRAILING_HASH = re.compile(r"\s+#+\s*$")
_LINK = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")
_FROM = re.compile(r"^\s*<!--\s*from:\s*(\S+?)#L(\d+)-L(\d+)\s*-->\s*$")
_EXTERNAL = re.compile(r"^(https?:|mailto:|ftp:|#!|//)")


@dataclass
class Note:
    path: str
    headings: list = field(default_factory=list)   # (line, text)
    links: list = field(default_factory=list)      # (line, label, target)
    quotes: list = field(default_factory=list)     # (line, src, start, end, body)

    @property
    def heading_texts(self):
        return [t for _, t in self.headings]


def parse_note(path: str, text: str) -> Note:
    """Pull headings, links and quoted blocks out of one markdown note.

    Fences are tracked, because the first thing a naive checker gets wrong is
    reading `# TODO: fix this` inside a python block as a level-1 heading and
    then reporting a perfectly good anchor as broken.
    """
    note = Note(path=path)
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        m = _FROM.match(line)
        if m and i + 1 < len(lines) and _FENCE_OPEN.match(lines[i + 1]):
            marker = _FENCE_OPEN.match(lines[i + 1]).group(1)[0]
            body = []
            j = i + 2
            while j < len(lines):
                cm = _FENCE_CLOSE.match(lines[j])
                if cm and cm.group(1)[0] == marker:
                    break
                body.append(lines[j])
                j += 1
            note.quotes.append((i + 1, m.group(1), int(m.group(2)), int(m.group(3)), body))
            i = j + 1
            continue

        fm = _FENCE_OPEN.match(line)
        if fm:
            marker = fm.group(1)[0]
            j = i + 1
            while j < len(lines):
                cm = _FENCE_CLOSE.match(lines[j])
                if cm and cm.group(1)[0] == marker:
                    break
                j += 1
            i = j + 1
            continue

        hm = _HEADING.match(line)
        if hm:
            note.headings.append((i + 1, _TRAILING_HASH.sub("", hm.group(2)).strip()))
        else:
            for lm in _LINK.finditer(line):
                note.links.append((i + 1, lm.group(1), lm.group(2)))
        i += 1
    return note


# --------------------------------------------------------------------------- #
# findings
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Finding:
    note: str
    line: int
    kind: str        # link | anchor | quote
    ref: str         # the reference exactly as it was written
    stale: bool
    reason: str      # one of the REASONS below
    evidence: str    # what was actually there instead

    def __str__(self):
        return "%s:%d  %-6s %-26s %s  %s" % (
            self.note, self.line, self.kind,
            self.ref[:26], self.reason, self.evidence)


REASONS = (
    "resolved",                      # ok
    "resolved-case-insensitively",   # ok, but only because you asked
    "resolved-after-normalising",    # ok, but only because you asked
    "case-only-match",               # STALE: right file, wrong case
    "target-missing",                # STALE
    "anchor-missing",                # STALE
    "source-missing",                # STALE
    "range-out-of-bounds",           # STALE
    "content-drifted",               # STALE
)


def _clip_at(s: str, start: int, n: int = 40) -> str:
    s = s.replace("\t", " ")
    piece = s[start:start + n]
    return ("..." if start > 0 else "") + piece + ("..." if start + n < len(s) else "")


def _window(a: str, b: str, n: int = 40):
    """Two excerpts that start just BEFORE the first character that differs.

    Clipping both lines from column 0 is how a diff ends up printing two
    identical-looking strings and calling them different, which reads as a
    bug in the tool rather than as evidence about the note.
    """
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    start = max(0, i - 12)
    return _clip_at(a, start, n), _clip_at(b, start, n)


# --------------------------------------------------------------------------- #
# the three checks
# --------------------------------------------------------------------------- #

def check_link(note: Note, line: int, target: str, tree: Tree,
               case: str = "strict"):
    """Resolve one link's FILE part. Returns (Finding, resolved_path_or_None)."""
    path_part = target.split("#", 1)[0]
    base = note.path.rsplit("/", 1)[0] if "/" in note.path else ""
    want = join_rel(base, path_part)

    hit = tree.exact(want)
    if hit is not None:
        return Finding(note.path, line, "link", target, False,
                       "resolved", "resolves to " + hit), hit

    near = tree.insensitive(want)
    if near is not None:
        if case == "insensitive":
            return Finding(note.path, line, "link", target, False,
                           "resolved-case-insensitively",
                           "no " + want + "; matched " + near + " ignoring case"), near
        return Finding(note.path, line, "link", target, True,
                       "case-only-match",
                       "no " + want + "; " + near + " differs only in case"), near

    return Finding(note.path, line, "link", target, True,
                   "target-missing", "no file at " + want), None


def check_anchor(note: Note, line: int, target: str, resolved: str,
                 notes: dict, anchors: str = "slug"):
    """Check the #fragment of a link whose file part already resolved."""
    frag = target.split("#", 1)[1]
    dest = notes.get(resolved)
    if dest is None:
        return None
    table = anchor_table(dest.heading_texts, anchors)
    if frag in table:
        return Finding(note.path, line, "anchor", "#" + frag, False,
                       "resolved", "matches heading " + repr(table[frag]))
    shown = ", ".join(sorted(table)[:3]) or "(none)"
    return Finding(note.path, line, "anchor", "#" + frag, True,
                   "anchor-missing",
                   "%s has %d headings in %s mode; %s" % (
                       resolved, len(table), anchors, shown))


def _norm_lines(lines):
    """Whitespace-insensitive view of a block: blank lines dropped, each line
    stripped, internal runs of whitespace collapsed."""
    out = []
    for ln in lines:
        t = re.sub(r"\s+", " ", ln.strip())
        if t:
            out.append(t)
    return out


def check_quote(note: Note, line: int, src: str, start: int, end: int,
                body, tree: Tree, quote: str = "exact", case: str = "strict"):
    """Check one <!-- from: ... --> block against the source it names."""
    base = note.path.rsplit("/", 1)[0] if "/" in note.path else ""
    want = join_rel(base, src)
    ref = "%s#L%d-L%d" % (src, start, end)

    hit = tree.exact(want)
    if hit is None:
        near = tree.insensitive(want)
        if near is not None and case == "insensitive":
            hit = near
        elif near is not None:
            return Finding(note.path, line, "quote", ref, True, "case-only-match",
                           "no " + want + "; " + near + " differs only in case")
        else:
            return Finding(note.path, line, "quote", ref, True, "source-missing",
                           "no file at " + want)

    src_lines = tree.files[hit].split("\n")
    if start < 1 or end < start or end > len(src_lines):
        return Finding(note.path, line, "quote", ref, True, "range-out-of-bounds",
                       "%s has %d lines; asked for L%d-L%d" % (hit, len(src_lines), start, end))

    want_lines = src_lines[start - 1:end]
    if want_lines == list(body):
        return Finding(note.path, line, "quote", ref, False, "resolved",
                       "%d lines match %s byte for byte" % (len(body), hit))

    if _norm_lines(want_lines) == _norm_lines(body):
        if quote == "normalised":
            return Finding(note.path, line, "quote", ref, False,
                           "resolved-after-normalising",
                           "matches %s only after whitespace normalisation" % hit)
        return Finding(note.path, line, "quote", ref, True, "content-drifted",
                       "whitespace differs from %s (identical after normalisation)" % hit)

    k = 0
    while k < min(len(want_lines), len(body)) and want_lines[k] == body[k]:
        k += 1
    if k < min(len(want_lines), len(body)):
        sa, sb = _window(want_lines[k], body[k])
        detail = "line %d: source %r, note %r" % (start + k, sa, sb)
    else:
        detail = "source has %d lines, note has %d" % (len(want_lines), len(body))
    return Finding(note.path, line, "quote", ref, True, "content-drifted",
                   "%s %s" % (hit, detail))


# --------------------------------------------------------------------------- #
# scanning a whole tree
# --------------------------------------------------------------------------- #

NOTE_EXT = (".md", ".markdown")


@dataclass
class Report:
    case: str
    anchors: str
    quote: str
    findings: list = field(default_factory=list)
    notes_scanned: int = 0
    refs_checked: int = 0

    @property
    def stale(self):
        return [f for f in self.findings if f.stale]

    @property
    def stale_notes(self):
        return sorted({f.note for f in self.stale})

    @property
    def base_rate(self) -> float:
        """Fraction of scanned notes carrying at least one stale finding.

        Printed on every run on purpose. A detector that flags most of the
        pile has told you nothing you can act on, and the number that tells
        you that is this one - not the finding count, which only ever grows.
        """
        if not self.notes_scanned:
            return 0.0
        return len(self.stale_notes) / self.notes_scanned

    def by_reason(self) -> dict:
        out = {}
        for f in self.findings:
            out[f.reason] = out.get(f.reason, 0) + 1
        return out

    def causes(self):
        """Stale findings collapsed onto the thing you would actually fix.

        This is the only answer stale has to its own base rate. A tree where
        three quarters of the notes are flagged produces a report nobody
        opens twice - but the findings are not independent. One file that
        got renamed shows up once per note that linked to it, and renaming
        it back, or fixing it once, clears all of them. Counting FIXES
        instead of LINES is not a presentation trick; it is the difference
        between a list of symptoms and a list of jobs.

        Returns [(cause_key, count, [findings])], biggest first, ties by key.
        """
        groups = {}
        for f in self.stale:
            groups.setdefault(cause_of(f), []).append(f)
        return sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))


def cause_of(f: Finding) -> str:
    """The single thing whose repair clears this finding."""
    if f.reason in ("target-missing", "source-missing"):
        return f.reason + ": " + f.evidence.replace("no file at ", "")
    if f.reason == "case-only-match":
        return f.reason + ": " + f.evidence.split("; ")[1].split(" differs")[0]
    if f.reason == "anchor-missing":
        return f.reason + ": " + f.evidence.split(" has ")[0] + f.ref
    return f.reason + ": " + f.ref


def scan(files: dict, case: str = "strict", anchors: str = "slug",
         quote: str = "exact") -> Report:
    """Check every note in a tree. `files` is {relative path: text}."""
    if case not in ("strict", "insensitive"):
        raise ValueError("case must be strict or insensitive")
    if anchors not in ("slug", "raw"):
        raise ValueError("anchors must be slug or raw")
    if quote not in ("exact", "normalised"):
        raise ValueError("quote must be exact or normalised")

    tree = Tree(files)
    notes = {}
    for path in sorted(files):
        if path.lower().endswith(NOTE_EXT):
            notes[path] = parse_note(path, files[path])

    rep = Report(case=case, anchors=anchors, quote=quote, notes_scanned=len(notes))

    for path in sorted(notes):
        note = notes[path]
        for line, _label, target in note.links:
            if _EXTERNAL.match(target):
                continue
            if target.startswith("#"):
                # a link into this same note
                f = check_anchor(note, line, path + target, path, notes, anchors)
                if f is not None:
                    rep.refs_checked += 1
                    rep.findings.append(f)
                continue
            rep.refs_checked += 1
            f, resolved = check_link(note, line, target, tree, case)
            rep.findings.append(f)
            if "#" in target and resolved is not None and not f.stale:
                af = check_anchor(note, line, target, resolved, notes, anchors)
                if af is not None:
                    rep.refs_checked += 1
                    rep.findings.append(af)
        for line, src, start, end, body in note.quotes:
            rep.refs_checked += 1
            rep.findings.append(
                check_quote(note, line, src, start, end, body, tree, quote, case))

    rep.findings.sort(key=lambda f: (f.note, f.line, f.kind, f.ref))
    return rep


# --------------------------------------------------------------------------- #
# reading a directory
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}


def read_tree(root: str, max_bytes: int = 400_000) -> dict:
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            try:
                if os.path.getsize(full) > max_bytes:
                    continue
                with open(full, "r", encoding="utf-8") as fh:
                    text = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            files[rel] = text
    return files


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path")
    ap.add_argument("--case", choices=("strict", "insensitive"), default="strict")
    ap.add_argument("--anchors", choices=("slug", "raw"), default="slug")
    ap.add_argument("--quote", choices=("exact", "normalised"), default="exact")
    ap.add_argument("--all", action="store_true", help="show the healthy references too")
    ap.add_argument("--causes", action="store_true",
                    help="group the findings onto the fixes that would clear them")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    files = read_tree(args.path)
    if not files:
        print("nothing readable under %s" % args.path, file=sys.stderr)
        return 1

    rep = scan(files, case=args.case, anchors=args.anchors, quote=args.quote)

    if args.json:
        print(json.dumps({
            "case": rep.case, "anchors": rep.anchors, "quote": rep.quote,
            "notes_scanned": rep.notes_scanned, "refs_checked": rep.refs_checked,
            "stale": len(rep.stale), "stale_notes": len(rep.stale_notes),
            "base_rate": round(rep.base_rate, 6),
            "by_reason": rep.by_reason(),
            "causes": [{"cause": c, "count": len(fs)} for c, fs in rep.causes()],
            "findings": [f.__dict__ for f in (rep.findings if args.all else rep.stale)],
        }, indent=2, sort_keys=True))
        return 0

    print("case %s  anchors %s  quote %s" % (rep.case, rep.anchors, rep.quote))
    print("-" * 78)
    if args.causes:
        for c, fs in rep.causes():
            print("%3d  %s" % (len(fs), c))
            for f in fs:
                print("       %s:%d  %s" % (f.note, f.line, f.ref))
    else:
        for f in (rep.findings if args.all else rep.stale):
            print(f)
    print("-" * 78)
    print("%d notes, %d references, %d stale in %d notes (base rate %.0f%%)" % (
        rep.notes_scanned, rep.refs_checked, len(rep.stale),
        len(rep.stale_notes), rep.base_rate * 100))
    print("%d distinct fixes would clear all %d" % (len(rep.causes()), len(rep.stale)))
    for reason, n in sorted(rep.by_reason().items()):
        print("  %-28s %d" % (reason, n))
    return 2 if rep.stale else 0


if __name__ == "__main__":
    sys.exit(main())
