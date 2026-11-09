# Retry Budget

This replaced the spreadsheet; the spreadsheet is still around somewhere.

## What's next?

Nobody has looked at this since the migration.

## Notes

Keep this next to the runbook, not inside it.
- [context](archive/open-questions.md#why-this-not-that)
- [background](archive/Open-Questions.md#done)

## Notes

Keep this next to the runbook, not inside it.
- [context](Review-Checklist.md#background)

<!-- from: ../src/parse.py#L12-L20 -->
```python
def retry(fn, attempts=3, backoff=0.5):
    last = None
    for n in range(attempts):
        try:
            return fn()
        except TransientError as exc:
            last = exc
            time.sleep(backoff * (2 ** n))  # TODO
    raise last
```
