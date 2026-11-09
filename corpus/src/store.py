"""store.py - part of the pipeline the notes keep pointing at."""

import json
import os
import time


class TransientError(Exception):
    pass


def open_store(path, mode="r"):
    if mode not in ("r", "w"):
        raise ValueError("mode must be r or w")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return Store(path, mode)


def checkpoint(store, state):
    payload = json.dumps(state, sort_keys=True)
    store.write(payload)
    store.flush()
    return len(payload)
