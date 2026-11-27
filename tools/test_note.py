#!/usr/bin/env python3
"""Put the test note, written in tools/test-note.md, into the saved notes.

    python3 tools/test_note.py

The note titled "test note" in ~/.config/ynote/notes.json gets the text and
formats the Markdown gives when it is pasted into a note; where the note is,
its size, and its color stay. The note is added when there is none.

Ynote must not be running, since it saves over the file as it quits. The file
is copied to notes.json.bak first.
"""
import os
import subprocess
import sys
from unittest.mock import MagicMock

# These must be set before GTK is imported.
os.environ['GDK_BACKEND'] = 'x11'
os.environ.pop('WAYLAND_DISPLAY', None)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import gi  # noqa: E402
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk  # noqa: E402

from ynote.config import NOTES_FILE  # noqa: E402
from ynote.markdown import from_markdown  # noqa: E402
from ynote.note_window import NoteWindow  # noqa: E402
from ynote.storage import back_up, load_notes, save_notes  # noqa: E402

SOURCE = os.path.join(ROOT, 'tools', 'test-note.md')
TITLE = 'test note'
# What pasting the Markdown makes. The rest of the saved note stays.
CONTENT = ('text', 'bold_ranges', 'heading_ranges', 'code_ranges',
           'backtick_ranges', 'images', 'tables')


class _App(Gtk.Application):
    """An application a note can be made in, standing in for all else."""

    def __getattr__(self, name):
        value = MagicMock(name=name)
        setattr(self, name, value)
        return value


def ynote_running():
    # Only python3 processes: `pgrep -f` would also match a shell whose
    # command line names ynote.py.
    found = subprocess.run(['pgrep', '-a', 'python3'],
                           capture_output=True, text=True)
    return any(arg.endswith('ynote.py') for line in found.stdout.splitlines()
               for arg in line.split()[2:3])


def build(markdown):
    """The saved form of a note holding markdown pasted into it."""
    app = _App(application_id='io.github.ynote.test-note',
               flags=Gio.ApplicationFlags.NON_UNIQUE)
    app.register(None)
    note = NoteWindow(app, {'id': 'test-note', 'title': TITLE, 'text': ''})
    note._insert_rich_state_at_cursor(from_markdown(markdown))
    while Gtk.events_pending():
        Gtk.main_iteration()
    data = note.to_dict()
    note.destroy()
    return data


def main():
    if ynote_running():
        sys.exit('Quit Ynote first: it saves over notes.json as it quits.')
    with open(SOURCE, encoding='utf-8') as f:
        built = build(f.read())
    notes = load_notes(NOTES_FILE) or []
    if os.path.exists(NOTES_FILE):
        back_up(NOTES_FILE)
    for note in notes:
        if note.get('title') == TITLE:
            note.update({key: built[key] for key in CONTENT})
            print(f'Updated "{TITLE}" in {NOTES_FILE}')
            break
    else:
        notes.append(dict(built, hidden=False))
        print(f'Added "{TITLE}" to {NOTES_FILE}')
    save_notes(notes, NOTES_FILE)


if __name__ == '__main__':
    main()
