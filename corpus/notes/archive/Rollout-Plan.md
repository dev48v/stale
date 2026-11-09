# Rollout Plan

Two people disagreed about this and neither wrote it down, so here it is.

## Done

The failure mode is silence, which is why this note exists at all.

## Background

This replaced the spreadsheet; the spreadsheet is still around somewhere.
- [where this came from](render-widths.md)

<!-- from: ../../src/render.py#L12-L17 -->
```python
def to_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return "%.2f" % value
    return str(value)
```
