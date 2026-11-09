"""ingest.py - part of the pipeline the notes keep pointing at."""

import json
import os
import time


class TransientError(Exception):
    pass


def read_batch(path, limit):
    rows = []
    with open(path) as fh:
        for i, line in enumerate(fh):
            if i >= limit:
                break
            rows.append(line.rstrip())
    return rows


def normalise(record):
    out = dict(record)
    out["id"] = str(out.get("id", "")).strip()
    out["kind"] = out.get("kind", "unknown").lower()
    return out
