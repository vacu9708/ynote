"""Finding a code block and where its box ends, without a display."""
import types

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.note_window import NoteWindow, cell_width


class FakeTextView:
    """Monospace: a column is 10 px wide. Counts the lines it measures."""
    def __init__(self):
        self.measured = 0

    def get_left_margin(self):
        return 6

    def get_iter_location(self, it):
        self.measured += 1
        return types.SimpleNamespace(x=6 + 10 * it.get_line_offset())


def make_window(lines, code_lines):
    """A buffer with one line per entry, code on the lines in `code_lines`."""
    buf = Gtk.TextBuffer()
    code = buf.create_tag('code')
    buf.set_text('\n'.join(lines))
    for n in code_lines:
        start = buf.get_iter_at_line(n)
        end = start.copy()
        end.forward_to_line_end()
        buf.apply_tag(code, start, end)
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView()
    win._code_tag = code
    win._hl_tag = buf.create_tag('hl')
    win._code_block_cache = {}
    win._watch_code_blocks(buf)
    # _line_bounds() reads the buffer from the text view.
    win.tv.get_buffer = lambda: buf
    return win, buf


def test_block_covers_the_run_of_code_lines_around_a_line():
    win, buf = make_window(
        ['prose', 'a', 'bbbb', 'cc', 'prose', 'dd'], [1, 2, 3, 5])

    first, last, right = win._code_block(win.tv, buf, 2)

    assert (first, last) == (1, 3)
    assert right == 6 + 10 * 4
    assert win._code_block(win.tv, buf, 5)[:2] == [5, 5]


def test_box_width_matches_measuring_every_line_of_a_long_block():
    # The longest line sits in the middle of a block of 40 lines.
    lines = ['x' * (3 + n % 7) for n in range(40)]
    lines[23] = 'y' * 50
    win, buf = make_window(lines, range(40))

    _, _, right = win._code_block(win.tv, buf, 0)

    assert right == 6 + 10 * 50
    # Only a few lines are measured, not all 40.
    assert win.tv.measured <= NoteWindow.WIDEST_CODE_LINES


def test_a_block_is_measured_once_until_the_buffer_changes():
    win, buf = make_window(['aa', 'bbb', 'c'], [0, 1, 2])

    win._code_block(win.tv, buf, 0)
    measured = win.tv.measured
    win._code_block(win.tv, buf, 2)
    assert win.tv.measured == measured

    # Inside the tagged line, so the new text is code too.
    buf.insert(buf.get_iter_at_line_offset(1, 1), 'dddd')
    assert win._code_block(win.tv, buf, 0)[2] == 6 + 10 * 7
    assert win.tv.measured > measured


def test_tagging_a_line_starts_a_new_measurement_but_search_highlight_does_not():
    win, buf = make_window(['aa', 'bbb', 'c'], [0, 1, 2])
    win._code_block(win.tv, buf, 0)

    buf.apply_tag(win._hl_tag, buf.get_start_iter(), buf.get_end_iter())
    assert win._code_block_cache

    buf.remove_tag(win._code_tag, buf.get_iter_at_line(2),
                   buf.get_end_iter())
    assert not win._code_block_cache
    assert win._code_block(win.tv, buf, 0)[:2] == [0, 1]


def test_cell_width_counts_tab_stops_and_full_width_characters():
    assert cell_width('abc') == 3
    assert cell_width('a\tb') == 9
    assert cell_width('\tab') == 10
    assert cell_width('한a') == 3
    assert cell_width('🔥') == 2
