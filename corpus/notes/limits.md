# Limits

The numbers below were taken on the small box, so treat them as a floor.

## The decision

This replaced the spreadsheet; the spreadsheet is still around somewhere.
- [details](migration.md#what's-next?)
- [background](migration.md)

## Rollout / rollback

Half of this is still true.
- [context](archive/Rollout-Plan.md)
- [context](2025-handoff.md)

<!-- from: ../src/util.py#L18-L27 -->
```python
def dedupe(rows, key):
    seen = set()
    out = []
    for r in rows:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out
```

## Notes

Nobody has looked at this since the migration.
- [details](2026/store-layout.md)
- [see the notes](runbook.md)

## Done

If the retry count is wrong the symptom is a flat line, not an error.
- [background](2026/schema-drift.md)
- [details](header-split.md#why-this-not-that)
