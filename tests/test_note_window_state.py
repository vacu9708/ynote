"""Maximize and collapse on a NoteWindow built without a display or a GTK
window: the methods under test only touch the attributes set here."""
import types

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.note_window import NoteWindow


class FakeTextView:
    def __init__(self, buf):
        self._buf = buf

    def get_buffer(self):
        return self._buf


def make_window(position=(100, 50), size=(300, 320)):
    win = NoteWindow.__new__(NoteWindow)
    buf = Gtk.TextBuffer()
    buf.set_text('hello')
    win.tv = FakeTextView(buf)
    win.note_id, win.title, win.sort_order = 'n1', 't', 0.0
    win._on_top, win._font_size = False, 14
    win._color, win._opacity = 'yellow', 1.0
    win._collapsed, win._expanded_height = False, size[1]
    win._normal_geometry = None
    win._bold_tag = win._code_tag = win._backtick_tag = None
    win._get_tag_ranges = lambda tag: []
    win._get_images_state = lambda: []
    win.get_visible = lambda: True
    win._state = {'position': position, 'size': size, 'maximized': False}
    win.get_position = lambda: win._state['position']
    win.get_size = lambda: win._state['size']
    win.is_maximized = lambda: win._state['maximized']
    win.calls = []

    def maximize():
        win._state.update(maximized=True, position=(0, 0), size=(1920, 1080))
        win.calls.append('maximize')

    def unmaximize():
        win._state.update(maximized=False, position=position, size=size)
        win.calls.append('unmaximize')

    win.maximize, win.unmaximize = maximize, unmaximize
    return win


def test_maximize_remembers_geometry_and_to_dict_saves_it():
    win = make_window()

    win._toggle_maximize()

    assert win.calls == ['maximize']
    assert win._normal_geometry == (100, 50, 300, 320)
    saved = win.to_dict()
    assert (saved['x'], saved['y'], saved['w'], saved['h']) == (100, 50, 300, 320)


def test_toggling_again_restores_and_saves_the_live_geometry():
    win = make_window()
    win._toggle_maximize()

    win._toggle_maximize()

    assert win.calls == ['maximize', 'unmaximize']
    win._state['position'], win._state['size'] = (10, 20), (250, 260)
    saved = win.to_dict()
    assert (saved['x'], saved['y'], saved['w'], saved['h']) == (10, 20, 250, 260)


def test_maximize_does_nothing_while_collapsed():
    win = make_window()
    win._collapsed = True

    win._toggle_maximize()

    assert win.calls == []
    assert win._normal_geometry is None


class Untouchable:
    def get_display(self):
        raise AssertionError('snapping went past the guard')


def test_snap_does_nothing_while_maximized():
    win = make_window()
    win.get_window = lambda: Untouchable()
    win._state['maximized'] = True

    win._snap_to(['left'])


def make_collapsible(size=(300, 320)):
    win = make_window(size=size)
    win.resizes, win.body_visible = [], True
    win.set_focus = lambda widget: None
    win.locks = []
    win._lock_size = lambda locked, width=-1: win.locks.append((locked, width))
    win._set_body_visible = lambda visible: setattr(win, 'body_visible', visible)
    win._refresh_collapse_state = lambda: None
    win.resize = lambda w, h: (win.resizes.append((w, h)),
                               win._state.update(size=(w, h)))
    return win


def test_collapse_shrinks_to_the_header_and_saves_the_expanded_height():
    win = make_collapsible()

    win._collapse()

    assert win._collapsed and not win.body_visible
    assert win.resizes == [(300, 1)]
    saved = win.to_dict()
    assert saved['collapsed'] is True
    assert saved['h'] == 320
    assert saved['w'] == 300


def test_expand_restores_the_previous_height_and_keeps_the_width():
    win = make_collapsible()
    win._collapse()
    win._state['size'] = (340, 28)  # the user widened it while collapsed

    win._expand()

    assert not win._collapsed and win.body_visible
    assert win.resizes[-1] == (340, 320)
    assert win.to_dict()['collapsed'] is False


def test_expand_is_a_no_op_on_an_expanded_note():
    win = make_collapsible()

    win._expand()

    assert win.resizes == []


def test_collapse_locks_the_size_at_its_width_and_expand_unlocks_it():
    win = make_collapsible()

    win._collapse()
    win._expand()

    assert win.locks == [(True, 300), (False, -1)]


class FakeButton:
    def __init__(self):
        self.sensitive, self.tip = True, None

    def set_sensitive(self, value):
        self.sensitive = value

    def set_tooltip_text(self, text):
        self.tip = text


def test_collapse_button_is_disabled_while_maximized_or_tiled():
    from gi.repository import Gdk
    win = make_window()
    win._collapse_btn = FakeButton()

    for state in (Gdk.WindowState.MAXIMIZED, Gdk.WindowState.LEFT_TILED,
                  Gdk.WindowState.TILED | Gdk.WindowState.BOTTOM_TILED):
        win._refresh_collapse_button(state)
        assert not win._collapse_btn.sensitive
        assert 'Restore' in win._collapse_btn.tip

    win._refresh_collapse_button(Gdk.WindowState.FOCUSED)
    assert win._collapse_btn.sensitive
    assert win._collapse_btn.tip == 'Collapse'


def test_collapsed_note_keeps_its_button_enabled_to_expand():
    from gi.repository import Gdk
    win = make_window()
    win._collapse_btn = FakeButton()
    win._collapsed = True

    win._refresh_collapse_button(Gdk.WindowState.FOCUSED)

    assert win._collapse_btn.sensitive
    assert win._collapse_btn.tip == 'Expand'
