# Flaky Tests

Keep this next to the runbook, not inside it.

## Rollout / rollback

This replaced the spreadsheet; the spreadsheet is still around somewhere.
- [background](handoff-2025.md#todo)
- [context](../timeouts.md#caveats)

## Open questions

This replaced the spreadsheet; the spreadsheet is still around somewhere.

<!-- from: ../../src/legacy.py#L12-L17 -->
```python
def to_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return "%.2f" % value
    return str(value)
```
