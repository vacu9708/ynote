import datetime
import json
import os
import shutil

from .config import NOTES_FILE


class UnreadableNotesError(Exception):
    """notes.json exists but does not hold a list of notes."""


def load_json(path):
    path = os.fspath(path)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def save_json(data, path):
    path = os.fspath(path)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load_notes(path=NOTES_FILE):
    """Return the saved notes, or None when there is no notes file yet.

    A file that exists but cannot be used raises UnreadableNotesError, so the
    caller never mistakes a damaged file for a fresh start and overwrites it.
    """
    path = os.fspath(path)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise UnreadableNotesError(str(e)) from e
    if not isinstance(data, list) or not all(isinstance(n, dict) for n in data):
        raise UnreadableNotesError('expected a list of notes')
    return data


def back_up(path):
    """Copy path to <path>.bak, replacing an older copy, and return it.

    The copy is written to a temporary file first, so a failed copy never
    leaves a damaged .bak behind.
    """
    path = os.fspath(path)
    kept = path + '.bak'
    shutil.copyfile(path, kept + '.tmp')
    os.replace(kept + '.tmp', kept)
    return kept


def set_aside(path, now=None):
    """Rename a damaged file to <name>.broken-<time> and return the new path."""
    path = os.fspath(path)
    now = now or datetime.datetime.now()
    kept = f'{path}.broken-{now:%Y%m%d-%H%M%S}'
    os.replace(path, kept)
    return kept


def save_notes(data, path=NOTES_FILE):
    save_json(data, path)
