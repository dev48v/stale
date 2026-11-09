"""util.py - part of the pipeline the notes keep pointing at."""

import json
import os
import time


class TransientError(Exception):
    pass


def backoff_seconds(attempt, base=0.5, cap=30.0):
    if attempt < 0:
        raise ValueError("attempt must not be negative")
    return min(cap, base * (2 ** attempt))


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
