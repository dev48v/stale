# Backoff

This replaced the spreadsheet; the spreadsheet is still around somewhere.

## The decision

The numbers below were taken on the small box, so treat them as a floor.
- [context](../2026/dedupe-keys.md)

<!-- from: ../../src/parse.py#L12-L20 -->
```python
def retry(fn, attempts=3, backoff=0.5):
    last = None
    for n in range(attempts):
        try:
            return fn()
        except TransientError as exc:
            last = exc
            time.sleep(backoff * (2 ** n))
    raise last
```

## What's next?

Two people disagreed about this and neither wrote it down, so here it is.
- [background](../2026/store-layout.md)

## TODO

Written up after the third time somebody asked in chat.

<!-- from: ../../src/cli.py#L19-L23 -->
```python
def chunked(seq, size):
    if size < 1:
        raise ValueError("size must be positive")
    for i in range(0, len(seq), size):
        yield seq[i:i + size]
```

## Background

Nobody has looked at this since the migration.
- [the other note](../old-glossary.md#the-decision)
