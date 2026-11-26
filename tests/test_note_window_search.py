"""The search bar's list of matches in every note, driven from the entry."""
from types import SimpleNamespace

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk

from ynote.note_window import NoteWindow


def make_window(note_ids):
    win = NoteWindow.__new__(NoteWindow)
    win._results = Gtk.ListBox()
    for note_id in note_ids:
        row = Gtk.ListBoxRow()
        row.match = SimpleNamespace(note_id=note_id, start=0, end=1)
        win._results.add(row)
    win._results_scroll = Gtk.ScrolledWindow()
    win._results_scroll.add(win._results)
    win._results_scroll.show()
    win.opened = []
    win._on_result_activated = lambda _list, row: win.opened.append(
        row.match.note_id)
    return win


def key(win, keyval):
    return win._on_search_key(None, SimpleNamespace(keyval=keyval, state=0))


def test_the_arrows_pick_a_match_and_enter_opens_it():
    win = make_window(['a', 'b', 'c'])

    assert key(win, Gdk.KEY_Down)
    assert key(win, Gdk.KEY_Down)
    assert key(win, Gdk.KEY_Down)
    assert key(win, Gdk.KEY_Down)   # stays on the last match
    assert key(win, Gdk.KEY_Up)
    assert key(win, Gdk.KEY_Return)

    assert win.opened == ['b']


def test_enter_opens_the_first_match_when_none_is_picked():
    win = make_window(['a', 'b'])

    assert key(win, Gdk.KEY_Return)

    assert win.opened == ['a']


def test_the_arrows_are_left_to_gtk_without_a_list():
    win = make_window(['a'])
    win._results_scroll.hide()

    assert not key(win, Gdk.KEY_Down)
    assert not key(win, Gdk.KEY_Return)
