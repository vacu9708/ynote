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
    win._bold_tag = win._heading_tag = win._code_tag = None
    win._backtick_tag = None
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


def test_font_size_steps_by_one_and_stays_between_8_and_32():
    win = make_window()
    win._apply_note_font = lambda: None
    win._queue_save = lambda: None

    for start, delta, expected in ((14, +1, 15), (14, -1, 13),
                                   (8, -1, 8), (32, +1, 32)):
        win._font_size = start
        win._change_font_size(delta)
        assert win._font_size == expected


def popup_labels(items):
    """Run the text view's right-click handler on a menu of these items."""
    win = make_window()
    win._history, win._hist_pos = [{}], 0
    menu = Gtk.Menu()
    for label in items:
        menu.append(Gtk.SeparatorMenuItem() if label == '-'
                    else Gtk.MenuItem(label=label))

    win._on_tv_popup(None, menu)

    return ['-' if isinstance(item, Gtk.SeparatorMenuItem) else item.get_label()
            for item in menu.get_children()]


def test_text_menu_puts_emoji_then_the_insert_items_first_and_drops_select_all():
    labels = popup_labels(['_Cut', '_Copy', '_Paste', '_Delete', '-',
                           'Select _All', '-', 'Insert _Emoji'])

    assert labels == [
        'Insert _Emoji', 'Insert Image', 'Insert Divider  (---)', '-',
        'Undo  (Ctrl+Z)', 'Redo  (Ctrl+Shift+Z)', '-',
        'Search  (Ctrl+F)', '-',
        '_Cut', '_Copy', '_Paste', '_Delete']


def test_text_menu_has_no_backtick_item_even_with_a_selection():
    win = make_window()
    win._history, win._hist_pos = [{}], 0
    win.tv.get_buffer().select_range(
        win.tv.get_buffer().get_start_iter(),
        win.tv.get_buffer().get_end_iter())
    menu = Gtk.Menu()

    win._on_tv_popup(None, menu)

    assert not any('Backtick' in (item.get_label() or '')
                   for item in menu.get_children()
                   if isinstance(item, Gtk.MenuItem))


class FakeMonitor:
    def get_workarea(self):
        return types.SimpleNamespace(x=0, y=0, width=1000, height=800)


class FakeDisplay:
    def __init__(self):
        self.monitor = FakeMonitor()

    def get_n_monitors(self):
        return 1

    def get_monitor(self, index):
        return self.monitor

    def get_monitor_at_window(self, window):
        return self.monitor


def test_snapping_a_collapsed_note_sets_its_new_width_in_the_size_request():
    win = make_collapsible(size=(300, 28))
    win._collapsed = True
    win._snap_pending_move = None
    win.moves = []
    win.move = lambda x, y: win.moves.append((x, y))
    win.get_window = lambda: types.SimpleNamespace(
        get_display=lambda: FakeDisplay())

    win._snap_to(['left'])

    assert win.locks == [(True, 500)]  # half of the 1000 px work area
    assert win.resizes == [(500, 28)]


def test_a_note_without_a_title_shows_a_dimmed_placeholder():
    win = NoteWindow.__new__(NoteWindow)
    win._title_label = Gtk.Label()
    context = win._title_label.get_style_context()

    win.title = ''
    win._show_title()
    assert win._title_label.get_text() == 'Untitled'
    assert context.has_class('untitled')

    win.title = 'Deploy'
    win._show_title()
    assert win._title_label.get_text() == 'Deploy'
    assert not context.has_class('untitled')


def test_changed_end_is_where_an_edit_ends_in_the_new_text():
    from ynote.note_window import changed_end

    # Undoing typed text: the cursor goes where the text was.
    assert changed_end('ab typed cd', 'ab cd') == 3
    # Redoing it: the cursor goes after the text that came back.
    assert changed_end('ab cd', 'ab typed cd') == 9
    # A line deleted from the middle, and text added to the end.
    assert changed_end('one\nzzz\nthree', 'one\nthree') == 4
    assert changed_end('one', 'one two') == 7
    # Repeated characters do not confuse the two ends.
    assert changed_end('aaa', 'aaaa') == 4
    assert changed_end('aaaa', 'aaa') == 3
    assert changed_end('', 'new') == 3
    assert changed_end('old', '') == 0


def test_even_slots_leave_a_note_of_one_font_as_it_is():
    from ynote.note_window import even_slots

    base = (14.2, 3.0)
    assert even_slots([base, base, base], base, (2, 2)) == [(2, 2)] * 3
    assert even_slots([], base, (2, 2)) == []


def test_even_slots_give_every_line_the_same_room_above_and_below_the_baseline():
    from ynote.note_window import even_slots

    base = (14.0, 3.0)
    tall = (17.0, 5.0)
    slots = even_slots([base, tall, base], base, (2, 2))

    # A tall line has all the room it needs, and the spacing on the other lines
    # makes up the difference, so every line takes 22 px.
    assert slots == [(3, 2), (0, 0), (3, 2)]
    for (a, d), (above, below) in zip([base, tall, base], slots):
        assert a + above == 17 and d + below == 5


def test_even_slots_never_take_less_than_a_line_of_the_notes_font():
    from ynote.note_window import even_slots

    # A font only a little taller than the note's own fits in its spacing.
    base = (14.0, 3.0)
    slots = even_slots([base, (15.0, 3.5)], base, (2, 2))

    assert slots == [(2, 2), (1, 2)]


def test_even_slots_never_go_negative_for_a_line_taller_than_the_rest_need():
    from ynote.note_window import even_slots

    base = (14.0, 3.0)
    assert all(a >= 0 and b >= 0 for a, b in
               even_slots([(30.0, 9.0), base], base, (2, 2)))


def test_slot_ascent_is_where_every_baseline_lies_below_the_top_of_its_line():
    from ynote.note_window import even_slots, slot_ascent

    base = (14, 3)
    # A note of one font: the spacing above, and the font's own ascent.
    assert slot_ascent([base, base], base, (3, 2)) == 17
    # A taller font takes the place of the spacing.
    metrics = [base, (17, 5)]
    assert slot_ascent(metrics, base, (3, 2)) == 17
    for (ascent, _), (above, _) in zip(metrics, even_slots(metrics, base, (3, 2))):
        assert ascent + above == 17
