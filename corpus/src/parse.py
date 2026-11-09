"""parse.py - part of the pipeline the notes keep pointing at."""

import json
import os
import time


class TransientError(Exception):
    pass


def retry(fn, attempts=3, backoff=0.5):
    last = None
    for n in range(attempts):
        try:
            return fn()
        except TransientError as exc:
            last = exc
            time.sleep(backoff * (2 ** n))
    raise last


def split_header(text):
    head, _, body = text.partition("\n\n")
    pairs = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        pairs[k.strip().lower()] = v.strip()
    return pairs, body
