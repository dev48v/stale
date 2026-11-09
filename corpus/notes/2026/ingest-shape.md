# Ingest Shape

The failure mode is silence, which is why this note exists at all.

## Open questions

Nobody has looked at this since the migration.
- [see the notes](../archive/Rollout-Plan.md)

## Background

Half of this is still true.

<!-- from: ../../src/parse.py#L23-L29 -->
```python
def split_header(text):
    head, _, body = text.partition("\n\n")
    pairs = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        pairs[k.strip().lower()] = v.strip()
    return pairs, body
```
