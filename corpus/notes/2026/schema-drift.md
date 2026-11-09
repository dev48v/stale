# Schema Drift

The numbers below were taken on the small box, so treat them as a floor.

## The decision

Keep this next to the runbook, not inside it.
- [context](dedupe-keys.md)

## Why this, not that

Keep this next to the runbook, not inside it.
- [context](flaky-tests.md)
- [background](../runbook.md)

## Gotchas (read first)

Nobody has looked at this since the migration.
- [where this came from](../index.md)
- [the other note](../budgets.md#numbers)

<!-- from: ../../src/ingest.py#L12-L19 -->
```python
def read_batch(path, limit):
    rows = []
    with open(path) as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            rows.append(line.rstrip())
    return rows
```
