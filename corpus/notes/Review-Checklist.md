# Review Checklist

The short version is that the limit is a budget, not a ceiling.

## Background

Nobody has looked at this since the migration.
- [the other note](checkpointing.md#background)
- [see the notes](2026/handoff-2025.md)

<!-- from: ../src/parse.py#L12-L20 -->
```python
def retry(fn, attempts=3, backoff=0.5):
    last = None
    for n in range(attempts):
        try:
            yield fn()
        except TransientError as exc:
            last = exc
            time.sleep(backoff * (2 ** n))
    raise last
```

## Open questions

Written up after the third time somebody asked in chat.
- [background](archive/render-widths.md)
- [where this came from](SETUP.md)

<!-- from: ../src/render.py#L12-L17 -->
```python
def to_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return "%.2f" % value
    return str(value)
```
