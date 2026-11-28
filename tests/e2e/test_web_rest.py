"""N. Clipboard, O. undo, P. search, Q. drawing, R. notes from older
versions, in Ynote 2.0: the 1.x behaviors the other 2.0 tests leave out. See
BEHAVIORS.md."""
import pytest

from tests.e2e.driver import Atspi, clipboard_text, set_clipboard, settle, wait_until
from tests.e2e.web import WebNote, assert_saved, saved_blocks, start, text_holding

pytestmark = [pytest.mark.web]


def paste(app, inp, markdown):
    set_clipboard(markdown)
    inp.key('ctrl+v')


def test_N5_web_a_pasted_markdown_link_is_its_text_and_address(app, inp):
    start(app, '')
    paste(app, inp, 'see [the docs](https://example.com/a) now')
    assert_saved(app, "paragraph('see the docs (https://example.com/a) now')", last_line=False)


def test_N6_web_a_heading_or_code_pasted_after_text_starts_a_line(app, inp):
    start(app, 'ab')
    paste(app, inp, '# Title\n```\nls\n```')
    assert_saved(app, "paragraph('ab') heading('Title') code_block('ls')", last_line=False)


def test_N10_web_names_with_underscores_and_lone_stars_stay_text(app, inp):
    start(app, '')
    paste(app, inp, 'my_long_name and 2 * 3 and *.txt')
    assert_saved(app, "paragraph('my_long_name and 2 * 3 and *.txt')", last_line=False)


def test_N10_web_inline_code_holding_a_backtick_gets_longer_backticks(app, inp):
    # With text around it: code alone is copied as it is (N2).
    start(app, 'x a`b', backtick_ranges=[[2, 5]])
    inp.key('ctrl+a')
    set_clipboard('-')
    inp.key('ctrl+c')
    wait_until(lambda: clipboard_text() not in (None, '-'), what='a copy')
    assert clipboard_text() == 'x ``a`b``'


def test_O1_web_undo_puts_the_cursor_where_the_edit_was(app, inp):
    start(app, 'abc')
    inp.key('home')
    inp.type('X')
    inp.key('end')
    settle(0.6)                     # the edit is a step of its own
    inp.key('ctrl+z')
    inp.type('Y')
    assert_saved(app, "paragraph('Yabc')", last_line=False)


def test_P3_web_find_ignores_case_and_takes_the_query_literally(app, inp):
    start(app, 'abc ABC a.c')
    inp.key('ctrl+f')
    inp.type('a.c')
    inp.key('esc')                  # the match is left selected
    inp.type('X')
    assert_saved(app, "paragraph('abc ABC X')", last_line=False)
    inp.key('ctrl+f')
    inp.key('ctrl+a')
    inp.type('abc')
    inp.key('enter')                # the second: case is ignored
    inp.key('esc')
    inp.type('Y')
    assert_saved(app, "paragraph('abc Y X')", last_line=False)


def test_Q10_web_after_enter_at_the_end_the_new_line_is_in_view(app, inp):
    note = start(app, '\n'.join(f'line {i}' for i in range(40)), h=220)
    inp.key('ctrl+end')
    for _ in range(3):
        inp.key('enter')
    inp.type('NEWLINE')
    settle(0.3)
    acc, at = text_holding(note, 'NEWLINE')
    box = Atspi.Text.get_range_extents(acc, at, at + 7, Atspi.CoordType.SCREEN)
    x, y, w, h = note.box
    assert y < box.y and box.y + box.height <= y + h, (box.y, y, h)


def old_note(app, **fields):
    app.write_notes([dict({'id': 'test', 'title': 'old', 'x': 100, 'y': 80, 'w': 500, 'h': 400}, **fields)])
    app.start()
    app.note('old')
    app.quit()
    return saved_blocks(app)


def test_R1_web_inline_code_padded_by_older_versions_opens_as_code(app):
    assert old_note(app, text='a  ls  b', backtick_ranges=[[2, 6]]) == \
        "paragraph('a ' 'ls'[code] ' b')"


def test_R2_web_a_list_indented_by_spaces_opens_nested(app):
    blocks = old_note(app, text='• top\n    • nested', bold_ranges=[[12, 18]])
    assert blocks == ("bullet_list(list_item(paragraph('top') "
                      "bullet_list(list_item(paragraph('nested'[strong])))))"), blocks


def test_R4_web_a_table_from_1_13_opens_as_a_table(app):
    tm = '⁣'
    blocks = old_note(app, text=f'top\n{tm}Name\tAge\n{tm}Kim\t31\nend')
    assert blocks == ("paragraph('top') table(table_row(table_header(paragraph('Name')) "
                      "table_header(paragraph('Age'))) table_row(table_cell(paragraph('Kim')) "
                      "table_cell(paragraph('31')))) paragraph('end')"), blocks


def test_R5_web_a_note_saved_with_only_its_text_opens(app):
    app.write_notes([{'id': 'test', 'title': 'bare', 'text': 'just text'}])
    app.start()
    WebNote(app, app.note('bare').frame)
    app.quit()
    assert saved_blocks(app) == "paragraph('just text')"
