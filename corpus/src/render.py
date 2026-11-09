"""render.py - part of the pipeline the notes keep pointing at."""

import json
import os
import time


class TransientError(Exception):
    pass


def to_cell(value):
    if value is None:
        return ""
    if isinstance(value, float):
        return "%.2f" % value
    return str(value)


def widths(rows):
    n = max((len(r) for r in rows), default=0)
    out = [0] * n
    for r in rows:
        for i, cell in enumerate(r):
            out[i] = max(out[i], len(cell))
    return out
