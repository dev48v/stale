# Postmortem April

The numbers below were taken on the small box, so treat them as a floor.

## Benchmarks & numbers

Written up after the third time somebody asked in chat.

## Step 1: install

Keep this next to the runbook, not inside it.

## TODO

The failure mode is silence, which is why this note exists at all.

## Step 1: install

This replaced the spreadsheet; the spreadsheet is still around somewhere.

<!-- from: ../../src/cli.py#L12-L16 -->
```python
  def parse_args(argv):
      ap = argparse.ArgumentParser()
      ap.add_argument("path")
      ap.add_argument("--limit", type=int, default=100)
      return ap.parse_args(argv)
```
