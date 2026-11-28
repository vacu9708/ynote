#!/usr/bin/env python3
"""Put the test note, written in tools/test-note.md, into the saved notes.

    python3 tools/test_note.py

The note titled "test note" in ~/.config/ynote/notes.json gets what the
Markdown makes when it is pasted into a note; where the note is, its size,
and its color stay. The note is added when there is none.

Ynote must not be running, since it saves over the file as it quits. The file
is copied to notes.json.bak first.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from ynote.config import NOTES_FILE  # noqa: E402
from ynote.convert import state_blocks  # noqa: E402
from ynote.markdown import from_markdown  # noqa: E402
from ynote.storage import back_up, load_notes, save_notes  # noqa: E402

SOURCE = os.path.join(ROOT, 'tools', 'test-note.md')
TITLE = 'test note'


def ynote_running():
    # Only python3 processes: `pgrep -f` would also match a shell whose
    # command line names ynote.py.
    found = subprocess.run(['pgrep', '-a', 'python3'],
                           capture_output=True, text=True)
    return any(arg.endswith('ynote.py') for line in found.stdout.splitlines()
               for arg in line.split()[2:3])


def build(markdown):
    """The document of a note holding markdown pasted into it, with the
    line a note always ends with."""
    blocks = state_blocks(from_markdown(markdown))
    if not blocks or blocks[-1]['type'] != 'paragraph':
        blocks.append({'type': 'paragraph'})
    return {'type': 'doc', 'content': blocks}


def main():
    if ynote_running():
        sys.exit('Quit Ynote first: it saves over notes.json as it quits.')
    with open(SOURCE, encoding='utf-8') as f:
        doc = build(f.read())
    notes = load_notes(NOTES_FILE) or []
    if os.path.exists(NOTES_FILE):
        back_up(NOTES_FILE)
    for note in notes:
        if note.get('title') == TITLE:
            note['doc'] = doc
            print(f'Updated "{TITLE}" in {NOTES_FILE}')
            break
    else:
        notes.append({'id': 'test-note', 'title': TITLE, 'doc': doc,
                      'x': 100, 'y': 80, 'w': 520, 'h': 640, 'hidden': False})
        print(f'Added "{TITLE}" to {NOTES_FILE}')
    save_notes(notes, NOTES_FILE)


if __name__ == '__main__':
    main()
