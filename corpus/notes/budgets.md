# Budgets

The short version is that the limit is a budget, not a ceiling.

## Gotchas (read first)

The short version is that the limit is a budget, not a ceiling.
- [the other note](2026/Handoff-2025.md)

## Notes

Half of this is still true.
- [see the notes](2026/flaky-tests.md)
- [context](2026/postmortem-april.md)

## The decision

Written up after the third time somebody asked in chat.
- [see the notes](archive/backoff.md#whats-next)
- [the other note](SETUP.md#the-decision)

## Benchmarks & numbers

The short version is that the limit is a budget, not a ceiling.
- [the other note](archive/backoff.md#todo)

<!-- from: ../src/ingest.py#L12-L19 -->
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
