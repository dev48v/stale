# Store Layout

Half of this is still true.

## Step 1: install

Written up after the third time somebody asked in chat.

<!-- from: ../../src/legacy.py#L23-L29 -->
```python
def split_header(text):
    head, _, body = text.partition("\n\n")
    pairs = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        pairs[k.strip().lower()] = v.strip()
    return pairs, body
```

## Benchmarks & numbers

Written up after the third time somebody asked in chat.

## The decision

Nobody has looked at this since the migration.
- [see the notes](../archive/Open-Questions.md#why-this-not-that)

## Open questions

The short version is that the limit is a budget, not a ceiling.
- [the other note](../budgets.md#benchmarks-&-numbers)
- [background](../old-glossary.md#caveats)
