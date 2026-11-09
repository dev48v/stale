"""cli.py - part of the pipeline the notes keep pointing at."""

import json
import os
import time


class TransientError(Exception):
    pass


def parse_args(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--limit", type=int, default=100)
    return ap.parse_args(argv)


def chunked(seq, size):
    if size < 1:
        raise ValueError("size must be positive")
    for i in range(0, len(seq), size):
        yield seq[i:i + size]
