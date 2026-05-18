import json
import os

from .config import NOTES_FILE


def load_notes(path=NOTES_FILE):
    path = os.fspath(path)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def save_notes(data, path=NOTES_FILE):
    path = os.fspath(path)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)
