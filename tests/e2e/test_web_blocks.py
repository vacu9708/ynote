"""I. Code blocks, J. dividers and links, L. tables, M. expands, in Ynote
2.0: the 1.x behaviors that still apply. Cases start from a note as 1.x
saved it, with the cursor at the end of its first line, give keys (^tab) and
text, and check what the note saves, leaving out the empty line a note
always ends with. See BEHAVIORS.md."""
import os

import pytest

from tests.e2e.driver import settle, wait_until
from tests.e2e.test_misc import fake_browser
from tests.e2e.web import WebNote, assert_saved, choose, saved_note, start

pytestmark = [pytest.mark.web]

B = '• '
ANCHOR = '￼'
OPEN, END = '▾ ', '⁤'

# A line, then a table of a header row k | v and a row a | b.
TABLE = {'tables': [{'offset': 2, 'rows': [[{'text': 'k'}, {'text': 'v'}],
                                          [{'text': 'a'}, {'text': 'b'}]]}]}


def cell(kind, *lines):
    return f"{kind}({' '.join(lines) or 'paragraph()'})"


def table(*rows):
    """A table from rows of cells, each a list of its lines as saved; the
    first row is the header."""
    out = []
    for i, row in enumerate(rows):
        kind = 'table_header' if i == 0 else 'table_cell'
        out.append('table_row(' + ' '.join(cell(kind, *c) for c in row) + ')')
    return 'table(' + ' '.join(out) + ')'


def p(text=None):
    return f"paragraph('{text}')" if text is not None else 'paragraph()'


KV = [[p('k')], [p('v')]]
AB = [[p('a')], [p('b')]]

CASES = {
    # I. code blocks
    'I7 lines with formats made a code block show their Markdown': (
        ('Title\n' + B + 'item\nx bold',), {'heading_ranges': [[0, 5]], 'bold_ranges': [[15, 19]]},
        ['^ctrl+a', '^ctrl+shift+c'], "code_block('# Title\\n- item\\nx **bold**')"),
    'I7 Ctrl+Z brings the lines back in one step': (
        ('Title\nx',), {'heading_ranges': [[0, 5]]},
        ['^ctrl+a', '^ctrl+shift+c', '^ctrl+z'], "heading('Title') paragraph('x')"),
    'I9 a code block made plain keeps its lines': (
        ('ls\npwd',), {'code_ranges': [[0, 6]]}, ['^ctrl+shift+c'], "paragraph('ls') paragraph('pwd')"),

    # J. dividers
    'J1 Down skips a divider': (
        ('a\n---\nb',), {}, ['^down', 'X'], "paragraph('a') horizontal_rule() paragraph('Xb')"),
    'J1 Up skips a divider': (
        ('a\n---\nb',), {}, ['^down', '^up', 'X'], "paragraph('aX') horizontal_rule() paragraph('b')"),

    # L. tables
    'L8 Down from the line above goes into the first cell': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^end', 'K'], "paragraph('x') " + table([[p('kK')], [p('v')]], AB)),
    'L8 Up from the line below goes into the last cell': (
        ('x\n' + ANCHOR + '\ny',), TABLE, ['^ctrl+end', '^up', '^end', 'U'],
        "paragraph('x') " + table(KV, [[p('a')], [p('bU')]]) + " paragraph('y')"),
    'L4 Tab goes to the next cell': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^tab', '^end', 'X'], "paragraph('x') " + table([[p('k')], [p('vX')]], AB)),
    'L4 Shift+Tab goes to the cell before': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^tab', '^tab', '^shift+tab', '^end', 'X'],
        "paragraph('x') " + table([[p('k')], [p('vX')]], AB)),
    'L4 Tab past the last cell adds a row and goes to its first cell': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^tab', '^tab', '^tab', '^tab', 'N'],
        "paragraph('x') " + table(KV, AB, [[p('N')], []])),
    'L5 Tab on a list item in a cell indents it': (
        ('x\n' + ANCHOR,), {'tables': [{'offset': 2, 'rows': [[{'text': 'k'}], [{'text': B + 'a\n' + B + 'b'}]]}]},
        ['^down', '^down', '^down', '^tab', '^end', 'X'],
        "paragraph('x') " + table([[p('k')]], [["bullet_list(list_item(paragraph('a') "
                                                "bullet_list(list_item(paragraph('bX')))))"]])),
    'L6 Enter makes a new line in a cell': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^down', '^end', '^enter', 'y'],
        "paragraph('x') " + table(KV, [[p('a'), p('y')], [p('b')]])),
    'L7 Down at a cell end goes to the cell below': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^down', '^end', 'Z'], "paragraph('x') " + table(KV, [[p('aZ')], [p('b')]])),
    'L7 Down from the last row goes out of the table': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^down', '^down', 'W'], "paragraph('x') " + table(KV, AB) + " paragraph('W')"),
    'L7 Esc leaves the table': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^esc', 'W'], "paragraph('x') " + table(KV, AB) + " paragraph('W')"),
    'L12 Ctrl+Z in a cell undoes the cell edit': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^end', 'QQ', '^ctrl+z'], "paragraph('x') " + table(KV, AB)),
    'L14 Ctrl+B acts on the cell': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^down', '^end', '^shift+home', '^ctrl+b'],
        "paragraph('x') " + table(KV, [["paragraph('a'[strong])"], [p('b')]])),
    'L14 Ctrl+8 makes a list in the cell': (
        ('x\n' + ANCHOR,), TABLE, ['^down', '^down', '^ctrl+8'],
        "paragraph('x') " + table(KV, [["bullet_list(list_item(paragraph('a')))"], [p('b')]])),
    'L19 typing over a selection across a table replaces it': (
        ('x\n' + ANCHOR + '\ny',), TABLE, ['^ctrl+a', 'Q'], "paragraph('Q')"),
    'L19 Ctrl+Z brings it back': (
        ('x\n' + ANCHOR + '\ny',), TABLE, ['^ctrl+a', '^backspace', '^ctrl+z'],
        "paragraph('x') " + table(KV, AB) + " paragraph('y')"),
    'L20 Backspace at the start of the line below goes into the last cell': (
        ('x\n' + ANCHOR + '\ny',), TABLE, ['^ctrl+end', '^home', '^backspace', 'Z'],
        "paragraph('x') " + table(KV, [[p('a')], [p('bZ')]]) + " paragraph('y')"),
    'L20 Backspace on the empty line below takes it away': (
        ('x\n' + ANCHOR + '\n\nz',), TABLE, ['^ctrl+end', '^up', '^backspace', 'Z'],
        "paragraph('x') " + table(KV, [[p('a')], [p('bZ')]]) + " paragraph('z')"),
    'L20 Delete at the end of the line above does nothing': (
        ('x\n' + ANCHOR,), TABLE, ['^delete', 'Y'], "paragraph('xY') " + table(KV, AB)),

    # M. expands
    'M2 Ctrl+Enter on the title folds it': (
        (OPEN + 'T\nbody\n' + END,), {}, ['^ctrl+enter'], "expand[closed](expand_title('T') paragraph('body'))"),
    'M2 folding moves a cursor inside to the title': (
        (OPEN + 'T\nbody\n' + END,), {}, ['^down', '^up', '^ctrl+enter', 'X'],
        "expand[closed](expand_title('TX') paragraph('body'))"),
    'M5 Backspace after an expand takes an empty line into it': (
        (OPEN + 'T\nbody\n' + END + '\n\nz',), {}, ['^ctrl+end', '^up', '^backspace', 'Z'],
        "expand(expand_title('T') paragraph('body') paragraph('Z')) paragraph('z')"),
    'M5 Delete never joins a line to its end': (
        (OPEN + 'T\nbody\n' + END + '\nz',), {}, ['^down', '^end', '^delete', 'Y'],
        "expand(expand_title('T') paragraph('bodyY')) paragraph('z')"),
    'M6 Backspace at the title start keeps what it holds': (
        (OPEN + 'T\nbody\n' + END,), {}, ['^home', '^backspace'], "paragraph('T') paragraph('body')"),
}


@pytest.mark.parametrize('case', list(CASES))
def test_web_blocks(app, inp, case):
    (text,), fields, steps, expected = CASES[case]
    start(app, text, at=(200, 10), **fields)
    for step in steps:
        if step.startswith('^'):
            inp.key(step[1:])
        else:
            inp.type(step)
    assert_saved(app, expected.removesuffix(' paragraph()'), last_line=False)


# ---------------------------------------------------------------- menus


def in_table(app):
    note = start(app, 'x\n' + ANCHOR, at=(200, 10), **TABLE)
    note.click_text(14, 70, button=3)       # the cell a, in the second row
    return note


def test_L10_web_insert_column_right_adds_a_column_that_takes_typing(app, inp):
    in_table(app)
    choose(app, 'Insert column right')
    settle(0.3)
    inp.key('tab')
    inp.type('C')
    assert_saved(app, "paragraph('x') " + table([[p('k')], [], [p('v')]], [[p('a')], [p('C')], [p('b')]]),
                 last_line=False)


def test_L10_web_deleting_the_last_row_deletes_the_table(app, inp):
    start(app, 'x\n' + ANCHOR, at=(200, 10), tables=[{'offset': 2, 'rows': [[{'text': 'k'}]]}])
    WebNote(app, app.note('test').frame).click_text(14, 40, button=3)
    choose(app, 'Delete row')
    assert_saved(app, "paragraph('x')", last_line=False)


def test_L11_web_a_deleted_table_comes_back_with_ctrl_z_and_takes_clicks(app, inp):
    note = in_table(app)
    choose(app, 'Delete table')
    assert_saved(app, "paragraph('x')", last_line=False)
    inp.key('ctrl+z')
    assert_saved(app, "paragraph('x') " + table(KV, AB), last_line=False)
    note.click_text(14, 70)
    inp.key('end')
    inp.type('Z')
    assert_saved(app, "paragraph('x') " + table(KV, [[p('aZ')], [p('b')]]), last_line=False)


def test_L21_web_a_click_right_of_a_table_and_typing_goes_on_the_line_after(app, inp):
    note = start(app, 'x\n' + ANCHOR, at=(200, 10), **TABLE)
    note.click_text(300, 40)
    inp.type('W')
    assert_saved(app, "paragraph('x') " + table(KV, AB) + " paragraph('W')", last_line=False)


# ---------------------------------------------------------------- links


def test_J2_web_ctrl_click_opens_a_link_and_a_click_only_places_the_cursor(app, inp):
    opened = fake_browser(app.home)
    note = start(app, 'see https://example.com/page now', at=(200, 10))
    note.click_text(80, 10)                  # on the link
    settle(0.5)
    assert not os.path.exists(opened)
    x, y = note.text_point(80, 10)
    inp.move(x, y)
    inp._mods(['ctrl'], True)
    inp.press()
    inp.release()
    inp._mods(['ctrl'], False)
    wait_until(lambda: os.path.exists(opened), timeout=10, what='the link')
    with open(opened) as f:
        assert f.read().strip() == 'https://example.com/page'


def test_J3_web_a_link_leaves_out_the_punctuation_after_it(app, inp):
    opened = fake_browser(app.home)
    note = start(app, 'at https://example.com:8080/a?b=(c), then', at=(200, 10))
    x, y = note.text_point(70, 10)
    inp.move(x, y)
    inp._mods(['ctrl'], True)
    inp.press()
    inp.release()
    inp._mods(['ctrl'], False)
    wait_until(lambda: os.path.exists(opened), timeout=10, what='the link')
    with open(opened) as f:
        assert f.read().strip() == 'https://example.com:8080/a?b=(c)'


# ---------------------------------------------------------------- images


def test_K2_web_an_image_no_note_uses_is_cleaned_up(app):
    images = os.path.join(app.conf, 'images')
    os.makedirs(images)
    for name in ('used.png', 'unused.png'):
        with open(os.path.join(images, name), 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')
    images_field = [{'file': 'used.png', 'original_name': 'used.png', 'offset': 2}]
    start(app, 'x ' + ANCHOR, at=(200, 10), images=images_field)
    wait_until(lambda: not os.path.exists(os.path.join(images, 'unused.png')), what='the unused image to go')
    assert os.path.exists(os.path.join(images, 'used.png'))
    assert saved_note(app)['id'] == 'test'
