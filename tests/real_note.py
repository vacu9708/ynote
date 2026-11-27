"""A real NoteWindow for tests, in an application that stands in for Ynote's:
whatever the note asks the application for is a stand-in."""
from unittest.mock import MagicMock

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gio, Gtk

from ynote.note_window import NoteWindow


class FakeApp(Gtk.Application):
    """An application a note can be made in: whatever it is asked for is a
    stand-in."""

    def __getattr__(self, name):
        value = MagicMock(name=name)
        setattr(self, name, value)
        return value


_app = None


def make_note(lines):
    global _app
    if _app is None:
        _app = FakeApp(application_id='io.github.ynote.tests',
                       flags=Gio.ApplicationFlags.NON_UNIQUE)
        _app.register(None)
    note = NoteWindow(_app, {'id': 'n', 'text': '\n'.join(lines),
                             'w': 400, 'h': 400})
    settle()
    return note


def settle():
    while Gtk.events_pending():
        Gtk.main_iteration()
