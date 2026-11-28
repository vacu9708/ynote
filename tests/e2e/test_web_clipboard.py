"""V. Copy and paste in a 2.0 note, as in 1.x (N): see BEHAVIORS.md."""
import pytest

from tests.e2e.driver import clipboard_text, set_clipboard, settle, wait_until
from tests.e2e.web import WebNote, assert_saved, brief, start
from ynote.convert import note_doc
from ynote.config import (BULLET_MARKER, CHECKBOX_MARKER, EXPAND_END, EXPAND_OPEN,
                          IMAGE_ANCHOR, QUOTE_MARKER)
from ynote.markdown import to_markdown

pytestmark = [pytest.mark.web]

# A note with every kind of content, as 1.x saved it.
TEXT = '\n'.join(['Title', 'a b c', BULLET_MARKER + 'item', '\t' + BULLET_MARKER + 'sub',
                  CHECKBOX_MARKER + 'todo', QUOTE_MARKER + 'q', '---', 'ls',
                  EXPAND_OPEN + 'More', 'inside', EXPAND_END, IMAGE_ANCHOR])
FIELDS = dict(heading_ranges=[[0, 5]], bold_ranges=[[8, 9]], backtick_ranges=[[10, 11]],
              code_ranges=[[TEXT.index('ls'), TEXT.index('ls') + 2]],
              tables=[{'offset': len(TEXT) - 1, 'rows': [[{'text': 'k'}, {'text': 'v'}],
                                                        [{'text': 'a|b'}, {'text': 'c'}]]}])


def blocks_of_note():
    """The blocks the test note opens with, a line after them."""
    doc = note_doc(dict(text=TEXT, **FIELDS))
    return ' '.join(brief(b) for b in doc['content']) + ' paragraph()'


def copied(app, inp, keys='ctrl+c'):
    set_clipboard('-')
    inp.key(keys)
    return wait_until(lambda: (clipboard_text() or '-') != '-' and clipboard_text(), what='a copy')


def test_V1_copied_text_goes_to_other_apps_as_the_markdown_of_1x(app, inp):
    start(app, TEXT, **FIELDS)
    inp.key('ctrl+a')
    expected = to_markdown(dict(text=TEXT, bold=FIELDS['bold_ranges'], heading=FIELDS['heading_ranges'],
                                code=FIELDS['code_ranges'], backtick=FIELDS['backtick_ranges'],
                                tables=FIELDS['tables']))
    assert copied(app, inp) == expected


def test_V2_code_alone_is_copied_as_it_is(app, inp):
    note = start(app, 'ls -l\npwd', code_ranges=[[0, 9]])
    x, y = note.text_point(26, 30)
    inp.click(x, y, count=3)
    assert copied(app, inp) == 'ls -l\npwd'


def two_notes(app, text='', **fields):
    app.write_notes([
        dict({'id': 'test', 'title': 'test', 'text': text, 'x': 100, 'y': 80, 'w': 420, 'h': 420}, **fields),
        {'id': 'other', 'title': 'other', 'text': '', 'x': 560, 'y': 80, 'w': 420, 'h': 420}])
    app.start()
    return WebNote(app, app.note('test').frame), WebNote(app, app.note('other').frame)


def test_V3_a_paste_into_another_note_keeps_everything(app, inp):
    first, other = two_notes(app, TEXT, **FIELDS)
    first.click_text(10, 8)
    inp.key('ctrl+a')
    copied(app, inp)
    other.click_text(10, 8)
    inp.key('ctrl+v')
    assert_saved(app, blocks_of_note(), note_id='other')


def test_V4_once_another_app_copies_its_text_is_pasted(app, inp):
    start(app, 'mine')
    inp.key('ctrl+a')
    copied(app, inp)
    set_clipboard('theirs')
    inp.key('end')
    inp.key('ctrl+v')
    assert_saved(app, "paragraph('minetheirs')")


def test_V5_markdown_from_another_app_pastes_in_with_its_formats(app, inp):
    start(app, '')
    set_clipboard('# Head\n\n**b** and `c`\n\n- [x] done\n\n| k |\n| --- |\n| v |')
    inp.key('ctrl+v')
    # The blank lines between blocks stay, as in 1.x.
    assert_saved(app, "heading('Head') paragraph() paragraph('b'[strong] ' and ' 'c'[code]) paragraph() "
                      "bullet_list(done(paragraph('done'))) paragraph() "
                      "table(table_row(table_header(paragraph('k'))) table_row(table_cell(paragraph('v')))) "
                      "paragraph()")


def test_V6_a_list_pasted_after_text_starts_a_line_of_its_own(app, inp):
    start(app, 'text ')
    set_clipboard('- one\n- two')
    inp.key('ctrl+v')
    assert_saved(app, "paragraph('text ') bullet_list(list_item(paragraph('one')) "
                      "list_item(paragraph('two'))) paragraph()")


def test_V7_ctrl_shift_v_pastes_the_text_alone(app, inp):
    start(app, '')
    set_clipboard('**not bold**\n- not a list')
    inp.key('ctrl+shift+v')
    assert_saved(app, "paragraph('**not bold**') paragraph('- not a list')")


def test_V8_cut_and_paste_brings_everything_back(app, inp):
    start(app, TEXT, **FIELDS)
    inp.key('ctrl+a')
    copied(app, inp, 'ctrl+x')
    assert_saved(app, 'paragraph()')
    inp.key('ctrl+v')
    assert_saved(app, blocks_of_note())


def test_V9_markdown_pasted_into_code_stays_as_it_is(app, inp):
    note = start(app, 'x', code_ranges=[[0, 1]])
    note.click_text(30, 8)
    inp.key('end')
    set_clipboard('**a** `b`')
    inp.key('ctrl+v')
    settle(0.3)
    assert_saved(app, "code_block('x**a** `b`') paragraph()")


def test_V10_copy_as_markdown_copies_the_whole_note(app, inp):
    start(app, 'Title\nbody', heading_ranges=[[0, 5]])
    assert copied(app, inp, 'ctrl+shift+m') == '# Title\nbody'
