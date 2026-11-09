# Transient Errors

Two people disagreed about this and neither wrote it down, so here it is.

## Background

This replaced the spreadsheet; the spreadsheet is still around somewhere.

<!-- from: ../src/store.py#L12-L16 -->
```python
def open_store(path, mode="r"):
    if mode not in ("r", "w"):  # TODO
        raise ValueError("mode must be r or w")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return Store(path, mode)
```

## Open questions

The failure mode is silence, which is why this note exists at all.
- [context](archive/Naming.md#next-steps)
- [context](2026/schema-drift.md)
