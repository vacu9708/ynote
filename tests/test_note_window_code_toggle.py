"""Making lines a code block turns them into the Markdown they would be copied
as, with no format left on them, since nothing in code is formatted."""
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from tests.test_note_window_heading import make_window as plain_window
from ynote.config import CODE_ANCHOR, IMAGE_ANCHOR


def make_window(text):
    win, buf = plain_window(text)
    win.tv.scroll_mark_onscreen = lambda mark: None
    win._normalizing = False
    win._flush_snapshot = lambda: None
    win._refresh_line_styles = lambda: None
    win._queue_code_margins = lambda: None
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())
    return win, buf


def text_of(buf):
    return buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)


def tag(buf, tag, start, end):
    buf.apply_tag(tag, buf.get_iter_at_offset(start),
                  buf.get_iter_at_offset(end))


def test_formats_become_markdown_with_no_format_left_in_the_code():
    win, buf = make_window('Title\n• one\n\t☐ two\nsome bold\nplain')
    tag(buf, win._heading_tag, 0, 5)
    tag(buf, win._bold_tag, 24, 28)

    win._toggle_code_block()

    assert text_of(buf) == ('# Title\n- one\n  - [ ] two\nsome **bold**\n'
                            'plain')
    assert all(win._is_code_line(buf, n) for n in range(5))
    for format_tag in (win._heading_tag, win._bold_tag, win._backtick_tag):
        assert win._get_tag_ranges(format_tag) == []


def test_lines_already_code_stay_as_they_are_with_no_fences():
    win, buf = make_window('ls -l\n• item')
    tag(buf, win._code_tag, 0, 5)

    win._toggle_code_block()

    assert text_of(buf) == 'ls -l\n- item'
    assert win._is_code_line(buf, 0) and win._is_code_line(buf, 1)


def test_an_empty_line_in_a_new_code_block_keeps_its_anchor():
    win, buf = make_window('a\n\nb')

    win._toggle_code_block()

    assert text_of(buf) == f'a\n{CODE_ANCHOR}\nb'
    assert all(win._is_code_line(buf, n) for n in range(3))


def test_a_line_with_an_image_is_left_out():
    win, buf = make_window(f'see {IMAGE_ANCHOR}\nTitle')
    tag(buf, win._heading_tag, 6, 11)

    win._toggle_code_block()

    assert text_of(buf) == f'see {IMAGE_ANCHOR}\n# Title'
    assert not win._is_code_line(buf, 0) and win._is_code_line(buf, 1)


def test_code_made_plain_again_keeps_the_markdown_as_text():
    win, buf = make_window('Title')
    tag(buf, win._heading_tag, 0, 5)
    win._toggle_code_block()
    buf.select_range(buf.get_start_iter(), buf.get_end_iter())

    win._toggle_code_block()

    assert text_of(buf) == '# Title'
    assert not win._is_code_line(buf, 0)
