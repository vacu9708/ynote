"""Bringing a window forward after a choice in the tray menu."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote import focus


def test_a_realized_x11_window_is_presented_with_the_servers_current_time():
    win = Gtk.Window()
    seen = []
    win.present_with_time = seen.append

    focus.present_now(win)

    assert win.get_visible()
    assert len(seen) == 1 and seen[0] > 0
    win.destroy()


def test_the_window_is_asked_forward_again_unless_it_has_gone():
    win = Gtk.Window()
    seen = []
    win.present_with_time = seen.append
    later = []
    real = focus.GLib.timeout_add
    focus.GLib.timeout_add = lambda ms, fn, *args: later.append((ms, fn, args))
    try:
        focus.present_now(win)
    finally:
        focus.GLib.timeout_add = real

    (ms, fn, args), = later
    assert ms == focus.AGAIN_MS
    assert fn(*args) is False
    assert len(seen) == 2

    win.hide()
    fn(*args)
    assert len(seen) == 2
    win.destroy()


class StubWindow:
    def __init__(self):
        self.calls = []

    def show(self):
        self.calls.append('show')

    def get_window(self):
        return None

    def present(self):
        self.calls.append('present')

    def present_with_time(self, stamp):
        self.calls.append('present_with_time')


def test_a_window_that_is_not_on_x11_is_presented_the_ordinary_way():
    win = StubWindow()

    focus.present_now(win)

    assert win.calls == ['show', 'present']
