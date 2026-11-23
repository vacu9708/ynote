"""Finding a code block, where its box ends, and keeping that up to date while
the text is edited, without a display."""
import random
import types

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.note_window import NoteWindow, cell_width


class FakeTextView:
    """Monospace: a column is 10 px wide, 12 px when bold. Counts the lines it
    measures."""
    def __init__(self, buf, bold_tag):
        self.measured = 0
        self.bold_tag = bold_tag
        self.get_buffer = lambda: buf

    def get_left_margin(self):
        return 6

    def get_iter_location(self, it):
        self.measured += 1
        x, here = 6, it.copy()
        here.set_line_offset(0)
        while here.compare(it) < 0:
            x += 12 if here.has_tag(self.bold_tag) else 10
            here.forward_char()
        return types.SimpleNamespace(x=x)


def make_window(lines, code_lines):
    """A buffer with one line per entry, code on the lines in `code_lines`."""
    buf = Gtk.TextBuffer()
    win = NoteWindow.__new__(NoteWindow)
    win._code_tag = buf.create_tag('code')
    win._bold_tag = buf.create_tag('bold')
    win._backtick_tag = buf.create_tag('backtick')
    win._hl_tag = buf.create_tag('hl')
    win._link_tag = buf.create_tag('link')
    win._code_blocks = []
    win._watch_code_blocks(buf)
    buf.set_text('\n'.join(lines))
    for n in code_lines:
        tag_line(win, buf, n, True)
    win.tv = FakeTextView(buf, win._bold_tag)
    return win, buf


def tag_line(win, buf, n, on):
    start = buf.get_iter_at_line(n)
    end = start.copy()
    if not end.ends_line():
        end.forward_to_line_end()
    (buf.apply_tag if on else buf.remove_tag)(win._code_tag, start, end)


def blocks(win):
    return [list(block) for block in win._code_blocks]


def test_block_covers_the_run_of_code_lines_around_a_line():
    win, buf = make_window(
        ['prose', 'a', 'bbbb', 'cc', 'prose', 'dd'], [1, 2, 3, 5])

    first, last, right = win._code_block(win.tv, buf, 2)

    assert (first, last) == (1, 3)
    assert right == 6 + 10 * 4
    assert win._code_block(win.tv, buf, 5)[:2] == [5, 5]
    assert blocks(win) == [[1, 3, 46], [5, 5, 26]]


def test_a_block_is_found_again_from_any_of_its_lines_without_measuring():
    win, buf = make_window(['aa', 'bbb', 'c', 'prose'], [0, 1, 2])
    win._code_block(win.tv, buf, 1)
    measured = win.tv.measured

    for line in (0, 1, 2):
        assert win._code_block(win.tv, buf, line)[:2] == [0, 2]

    assert win.tv.measured == measured


def test_a_small_block_is_measured_line_by_line():
    # The longest line sits in the middle of a block of 40 lines.
    lines = ['x' * (3 + n % 7) for n in range(40)]
    lines[23] = 'y' * 50
    win, buf = make_window(lines, range(40))

    _, _, right = win._code_block(win.tv, buf, 0)

    assert right == 6 + 10 * 50
    assert win.tv.measured == 40


def test_a_long_block_measures_only_its_widest_lines():
    lines = ['x' * (3 + n % 7) for n in range(300)]
    lines[211] = 'y' * 50
    win, buf = make_window(lines, range(300))

    _, _, right = win._code_block(win.tv, buf, 0)

    assert right == 6 + 10 * 50
    assert win.tv.measured <= NoteWindow.WIDEST_CODE_LINES


def test_typing_in_a_block_forgets_only_that_block():
    win, buf = make_window(['aa', 'bbb', 'prose', 'cc', 'dddd'], [0, 1, 3, 4])
    win._code_block(win.tv, buf, 0)
    win._code_block(win.tv, buf, 3)
    measured = win.tv.measured

    buf.insert(buf.get_iter_at_line_offset(1, 1), 'zzzzzz')

    assert blocks(win) == [[3, 4, 46]]
    assert win._code_block(win.tv, buf, 0)[2] == 6 + 10 * 9
    assert win.tv.measured == measured + 2


def test_blocks_below_move_when_lines_are_added_or_removed_above_them():
    win, buf = make_window(['prose', 'aa', 'prose', 'bbb', 'cc'], [1, 3, 4])
    win._code_block(win.tv, buf, 3)

    buf.insert(buf.get_iter_at_line(0), 'one\ntwo\n')
    assert blocks(win) == [[5, 6, 36]]
    assert win._code_block(win.tv, buf, 5)[:2] == [5, 6]

    buf.delete(buf.get_iter_at_line(0), buf.get_iter_at_line(3))
    assert blocks(win) == [[2, 3, 36]]
    assert win._code_block(win.tv, buf, 2)[:2] == [2, 3]


def test_re_applied_dividers_links_and_search_highlight_keep_the_cache():
    win, buf = make_window(['aa', 'bbb', 'c'], [0, 1, 2])
    win._code_block(win.tv, buf, 0)

    for tag in (win._hl_tag, win._link_tag):
        buf.apply_tag(tag, buf.get_start_iter(), buf.get_end_iter())
        buf.remove_tag(tag, buf.get_start_iter(), buf.get_end_iter())

    assert blocks(win) == [[0, 2, 36]]


def test_changing_which_lines_are_code_splits_the_block():
    win, buf = make_window(['aa', 'bbb', 'c', 'prose'], [0, 1, 2])
    win._code_block(win.tv, buf, 0)

    tag_line(win, buf, 1, False)

    assert win._code_block(win.tv, buf, 0)[:2] == [0, 0]
    assert win._code_block(win.tv, buf, 2)[:2] == [2, 2]


def test_edits_are_noted_before_the_text_changes():
    # Another handler may edit the text right after an insert, which leaves
    # the iterator GTK passes on invalid, so the line is read before the change.
    win, buf = make_window(['aa', 'bbb', 'c'], [0, 1, 2])
    seen = []
    forget = win._forget_code_blocks
    win._forget_code_blocks = lambda *args: (
        seen.append(buf.get_char_count()), forget(*args))

    buf.insert(buf.get_iter_at_line_offset(1, 1), 'xy')
    buf.delete(buf.get_iter_at_line(0), buf.get_iter_at_line_offset(0, 1))

    assert seen == [8, 10]


def test_cell_width_counts_tab_stops_and_full_width_characters():
    assert cell_width('abc') == 3
    assert cell_width('a\tb') == 9
    assert cell_width('\tab') == 10
    assert cell_width('한a') == 3
    assert cell_width('🔥') == 2


def fresh_block(win, buf, line):
    """The block as a scan of the current text finds it, ignoring the cache."""
    saved, win._code_blocks = win._code_blocks, []
    try:
        return list(win._code_block(win.tv, buf, line))
    finally:
        win._code_blocks = saved


def test_cached_blocks_always_match_a_fresh_scan_after_random_edits():
    rng = random.Random(11)
    lines = [''.join(rng.choice('abc\t') for _ in range(rng.randint(0, 40)))
             for _ in range(120)]
    win, buf = make_window(lines, [n for n in range(120) if rng.random() < .7])

    for _ in range(1500):
        op = rng.choice(['insert', 'newlines', 'delete', 'tag', 'untag',
                         'bold', 'anchor', 'replace'])
        n = rng.randrange(buf.get_line_count())
        start = buf.get_iter_at_line(n)
        if op == 'insert':
            start.forward_chars(rng.randint(0, 10))
            buf.insert(start, ''.join(rng.choice('abc\t')
                                      for _ in range(rng.randint(1, 30))))
        elif op == 'newlines':
            start.forward_chars(rng.randint(0, 5))
            buf.insert(start, '\n' * rng.randint(1, 3))
        elif op == 'delete' and buf.get_line_count() > 20:
            end = start.copy()
            end.forward_lines(rng.randint(1, 3))
            end.forward_chars(rng.randint(0, 4))
            buf.delete(start, end)
        elif op == 'tag':
            tag_line(win, buf, n, True)
        elif op == 'untag':
            tag_line(win, buf, n, False)
        elif op == 'bold':
            buf.apply_tag(win._bold_tag, start, buf.get_end_iter())
        elif op == 'anchor':
            buf.create_child_anchor(start)
        elif op == 'replace' and buf.get_line_count() < 150:
            buf.set_text('\n'.join('x' * rng.randint(0, 20)
                                   for _ in range(rng.randint(5, 60))))
            for k in range(buf.get_line_count()):
                if rng.random() < .6:
                    tag_line(win, buf, k, True)
        for _ in range(4):
            line = rng.randrange(buf.get_line_count())
            if win._is_code_line(buf, line):
                assert win._code_block(win.tv, buf, line) == \
                    fresh_block(win, buf, line)
