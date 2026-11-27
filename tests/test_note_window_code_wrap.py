"""Inline code that wraps: a line that starts with it has its later rows
start where its text does, and its rows keep the note's spacing, so their
boxes do not run into each other."""
from tests.real_note import make_note, settle
from ynote.config import CODE_PAD_CHAR


def lines_tagged(note, tag):
    buf = note.tv.get_buffer()
    return sorted({buf.get_iter_at_offset(start).get_line()
                   for start, _ in note._get_tag_ranges(tag)})


def code_note(lines, code_lines):
    note = make_note(lines)
    buf = note.tv.get_buffer()
    for line in code_lines:
        start, end = note._line_bounds(line)
        text = buf.get_slice(start, end, True)
        first = start.get_offset() + text.index('`')
        last = start.get_offset() + text.rindex('`')
        it = buf.get_iter_at_offset
        buf.delete(it(last), it(last + 1))
        buf.delete(it(first), it(first + 1))
        buf.apply_tag(note._backtick_tag, it(first), it(last - 1))
    note._normalize_code_pads()
    note._apply_code_margins()
    settle()
    return note


def test_a_line_that_starts_with_code_hangs_its_later_rows():
    note = code_note(['`ls -l` first', 'text `ls` mid'], [0, 1])

    assert lines_tagged(note, note._code_hang_tag) == [0]
    width = round(note._text_width(note._body_font, CODE_PAD_CHAR))
    assert note._code_hang_tag.get_property('indent') == -width


def test_rows_of_a_line_with_code_keep_the_spacing_beside_tall_fonts():
    # Korean is drawn in a taller font, which leaves such a line no spacing
    # of its own; its wrapped rows still keep the note's.
    note = code_note(['한글 문장', '`한글 code`'], [1])
    buf = note.tv.get_buffer()
    code_line = buf.get_iter_at_line(1)
    wraps = [tag.get_property('pixels-inside-wrap')
             for tag in code_line.get_tags()
             if tag.get_property('name').startswith('slot-')]

    wrap = wraps[-1] if wraps else note.tv.get_pixels_inside_wrap()
    assert wrap >= sum(note._line_spacing)
