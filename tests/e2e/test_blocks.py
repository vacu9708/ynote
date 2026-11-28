"""I. Code blocks, J. dividers and links, L. tables, M. expands, in Ynote
2.0: the 1.x behaviors that still apply. Cases start from a note as 1.x
saved it, with the cursor at the end of its first line, give keys (^tab) and
text, and check what the note saves, leaving out the empty line a note
always ends with. See BEHAVIORS.md."""
import os

import pytest

from tests.e2e.driver import settle, wait_until
from tests.e2e.web import WebNote, assert_saved, choose, fake_browser, start



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

    'U26 Right at the end of a code block, then typing, makes a line before a divider': (
        ('ls\n---',), {'code_ranges': [[0, 2]]}, ['^right', 'x'],
        "code_block('ls') paragraph('x') horizontal_rule()"),
    'U26 Right at the end of a code block, then typing, makes a line before a table': (
        ('ls\n' + ANCHOR,), {'code_ranges': [[0, 2]], 'tables': [{'offset': 3, 'rows': [[{'text': 'k'}]]}]},
        ['^right', 'x'], "code_block('ls') paragraph('x') table(table_row(table_header(paragraph('k'))))"),
    'U26 Right at the end of a code block goes onto the line after it, when there is one': (
        ('ls\npwd',), {'code_ranges': [[0, 2]]}, ['^right', 'x'], "code_block('ls') paragraph('xpwd')"),
    'J1 Down from a code block selects a divider after it, as from a table': (
        ('ls\n---\nb',), {'code_ranges': [[0, 2]]}, ['^down', 'X'], "code_block('ls') paragraph('X') paragraph('b')"),
    'J1 Down from a table selects a divider after it': (
        ('x\n' + ANCHOR + '\n---\nb',), TABLE, ['^down', '^down', '^down', 'X'],
        "paragraph('x') " + table(KV, AB) + " paragraph('X') paragraph('b')"),
    'U26 a line made so and left as it is goes again': (
        ('ls\n---',), {'code_ranges': [[0, 2]]}, ['^right', '^up', 'Y'], "code_block('Yls') horizontal_rule()"),
    'U26 Right at the end of an expand, then typing, makes a line before a divider': (
        (OPEN + 'T\nbody\n' + END + '\n---',), {}, ['^down', '^end', '^right', 'X'],
        "expand(expand_title('T') paragraph('body')) paragraph('X') horizontal_rule()"),
    'U27 Right at the end of a table, then typing, makes a line before a divider': (
        ('x\n' + ANCHOR + '\n---',), TABLE, ['^down', '^down', '^tab', '^end', '^right', 'y'],
        "paragraph('x') " + table(KV, AB) + " paragraph('y') horizontal_rule()"),

    # J. dividers
    'J1 Down selects a divider, and typing replaces it, as in Confluence': (
        ('a\n---\nb',), {}, ['^down', 'X'], "paragraph('a') paragraph('X') paragraph('b')"),

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
    'L20 Delete at the end of the line above selects the table, as in Confluence': (
        ('x\n' + ANCHOR,), TABLE, ['^delete', 'Y'], "paragraph('x') paragraph('Y')"),

    # M. expands
    'M2 Ctrl+Enter on the title folds it': (
        (OPEN + 'T\nbody\n' + END,), {}, ['^ctrl+enter'], "expand[closed](expand_title('T') paragraph('body'))"),
    'M2 folding moves a cursor inside to the title': (
        (OPEN + 'T\nbody\n' + END,), {}, ['^down', '^up', '^ctrl+enter', 'X'],
        "expand[closed](expand_title('TX') paragraph('body'))"),
    'M5 Backspace after an expand takes an empty line into it': (
        (OPEN + 'T\nbody\n' + END + '\n\nz',), {}, ['^ctrl+end', '^up', '^backspace', 'Z'],
        "expand(expand_title('T') paragraph('body') paragraph('Z')) paragraph('z')"),
    'M5 Delete at its last line end takes the line after into it, as in Confluence': (
        (OPEN + 'T\nbody\n' + END + '\nz',), {}, ['^down', '^end', '^delete', 'Y'],
        "expand(expand_title('T') paragraph('bodyY') paragraph('z'))"),
    'M6 Backspace at the title start keeps what it holds': (
        (OPEN + 'T\nbody\n' + END,), {}, ['^home', '^backspace'], "paragraph('T') paragraph('body')"),
}


@pytest.mark.parametrize('case', list(CASES))
def test_blocks(app, inp, case):
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


def test_L10_insert_column_right_adds_a_column_that_takes_typing(app, inp):
    in_table(app)
    choose(app, 'Insert column right')
    settle(0.3)
    inp.key('tab')
    inp.type('C')
    assert_saved(app, "paragraph('x') " + table([[p('k')], [], [p('v')]], [[p('a')], [p('C')], [p('b')]]),
                 last_line=False)


def test_L10_deleting_the_last_row_deletes_the_table(app, inp):
    start(app, 'x\n' + ANCHOR, at=(200, 10), tables=[{'offset': 2, 'rows': [[{'text': 'k'}]]}])
    WebNote(app, app.note('test').frame).click_text(14, 40, button=3)
    choose(app, 'Delete row')
    assert_saved(app, "paragraph('x')", last_line=False)


def test_L11_a_deleted_table_comes_back_with_ctrl_z_and_takes_clicks(app, inp):
    note = in_table(app)
    choose(app, 'Delete table')
    assert_saved(app, "paragraph('x')", last_line=False)
    inp.key('ctrl+z')
    assert_saved(app, "paragraph('x') " + table(KV, AB), last_line=False)
    note.click_text(14, 70)
    inp.key('end')
    inp.type('Z')
    assert_saved(app, "paragraph('x') " + table(KV, [[p('aZ')], [p('b')]]), last_line=False)


def test_L21_a_click_right_of_a_table_and_typing_goes_on_the_line_after(app, inp):
    note = start(app, 'x\n' + ANCHOR, at=(200, 10), **TABLE)
    note.click_text(300, 40)
    inp.type('W')
    assert_saved(app, "paragraph('x') " + table(KV, AB) + " paragraph('W')", last_line=False)


# ---------------------------------------------------------------- links


def test_K2_an_image_no_note_uses_is_cleaned_up(app):
    images = os.path.join(app.conf, 'images')
    os.makedirs(images)
    for name in ('used.png', 'unused.png'):
        with open(os.path.join(images, name), 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')
    images_field = [{'file': 'used.png', 'original_name': 'used.png', 'offset': 2}]
    start(app, 'x ' + ANCHOR, at=(200, 10), images=images_field)
    wait_until(lambda: not os.path.exists(os.path.join(images, 'unused.png')), what='the unused image to go')
    assert os.path.exists(os.path.join(images, 'used.png'))


# ---------------------------------------------------------------- emoji


def test_J4_ctrl_dot_finds_an_emoji_by_name_and_puts_it_at_the_cursor(app, inp):
    import json
    note = start(app, 'go', at=(200, 10))
    inp.key('ctrl+period')
    settle(0.8)
    # A picker of its size, a grid that scrolls, not every emoji at once.
    from tests.e2e.driver import extents, role
    picker = wait_until(lambda: next((w for w in app.windows() if role(w) != 'frame'
                                      and extents(w)[3] > 100), None), what='the picker')
    assert extents(picker)[3] < 500, extents(picker)
    inp.type('rocket')
    settle(0.3)
    inp.key('enter')
    assert_saved(app, "paragraph('go🚀')", last_line=False)
    with open(os.path.join(app.conf, 'settings.json'), encoding='utf-8') as f:
        assert json.load(f)['emoji_recent'][0] == '🚀'


def test_J4_emoji_comes_first_in_the_texts_right_click_menu(app, inp):
    from tests.e2e.web import menu_items
    note = start(app, 'go', at=(200, 10))
    note.click_text(100, 10, button=3)      # right of the text
    first = menu_items(app)[0].get_name()
    assert first.startswith('Emoji'), first
    choose(app, 'Emoji')
    settle(0.8)
    inp.type('red heart')
    settle(0.3)
    inp.key('enter')
    assert_saved(app, "paragraph('go❤️')", last_line=False)


# ---------------------------------------------------------------- links


def link_form(app):
    """The popup while it shows the link form."""
    from tests.e2e.driver import find_all, name, role
    from tests.e2e.driver import wait_until as wait
    return wait(lambda: next((w for w in app.windows() if role(w) != 'frame' and find_all(
        w, lambda a: name(a) in ('Insert', 'Save') and role(a) in ('button', 'push button'))), None),
        what='the link form')


def doc_note(app, content):
    """A note saved by 2.0, with this paragraph content, clicked into at its
    start."""
    import json
    os.makedirs(app.conf, exist_ok=True)
    doc = {'type': 'doc', 'content': [{'type': 'paragraph', 'content': content}, {'type': 'paragraph'}]}
    with open(app.notes_file, 'w') as f:
        json.dump([{'id': 'test', 'title': 'test', 'x': 100, 'y': 80, 'w': 420, 'h': 360, 'doc': doc}], f)
    app.start()
    note = WebNote(app, app.note('test').frame)
    note.click_text(2, 10)
    return note


def saved_link(app):
    from tests.e2e.web import saved_note
    for node in saved_note(app)['doc']['content'][0].get('content', []):
        for mark in node.get('marks', []):
            if mark['type'] == 'link':
                return node['text'], mark['attrs']['href']
    return None


def test_J6_ctrl_k_links_the_selected_text(app, inp):
    start(app, 'see docs here', at=(200, 10))
    inp.key('home')
    for _ in range(4):
        inp.key('right')
    for _ in range(4):
        inp.key('shift+right')
    inp.key('ctrl+k')
    link_form(app)
    settle(0.3)
    inp.type('https://e.com/a')
    inp.key('enter')
    wait_until(lambda: saved_link(app) == ('docs', 'https://e.com/a'), what='docs linked')
    assert_saved(app, "paragraph('see ' 'docs'[link] ' here')", last_line=False)


def test_J6_link_inserts_text_and_address_at_the_cursor(app, inp):
    note = start(app, 'see ', at=(200, 10))
    note.press('More to insert')
    choose(app, 'Link')
    link_form(app)
    settle(0.3)
    inp.type('the docs')
    inp.key('tab')
    inp.type('https://e.com/a')
    inp.key('enter')
    wait_until(lambda: saved_link(app) == ('the docs', 'https://e.com/a'), what='the link inserted')


def test_J6_editing_a_link_changes_its_text_and_keeps_its_address(app, inp):
    doc_note(app, [{'type': 'text', 'text': 'docs', 'marks': [{'type': 'link', 'attrs': {'href': 'https://e.com/a'}}]}])
    inp.key('right')
    inp.key('ctrl+k')
    link_form(app)
    settle(0.3)
    inp.key('ctrl+a')
    inp.type('manual')
    inp.key('enter')
    wait_until(lambda: saved_link(app) == ('manual', 'https://e.com/a'), what='the text changed')


def test_J6_remove_link_keeps_its_text(app, inp):
    from tests.e2e.driver import center, find_all, name
    doc_note(app, [{'type': 'text', 'text': 'docs', 'marks': [{'type': 'link', 'attrs': {'href': 'https://e.com/a'}}]}])
    inp.key('right')
    inp.key('ctrl+k')
    form = link_form(app)
    remove = wait_until(lambda: next(iter(find_all(form, lambda a: name(a) == 'Remove link')), None),
                        what='Remove link')
    app.inp.click(*center(remove))
    assert_saved(app, "paragraph('docs')", last_line=False)


def test_J6_a_link_copies_as_a_markdown_link(app, inp):
    from tests.e2e.driver import clipboard_text, set_clipboard
    doc_note(app, [{'type': 'text', 'text': 'see '},
                   {'type': 'text', 'text': 'docs', 'marks': [{'type': 'link', 'attrs': {'href': 'https://e.com/a'}}]}])
    inp.key('ctrl+a')
    set_clipboard('-')
    inp.key('ctrl+c')
    wait_until(lambda: clipboard_text() not in (None, '-'), what='a copy')
    assert clipboard_text() == 'see [docs](https://e.com/a)'


def cursor_image(inp):
    """The mouse cursor's picture, as X shows it (XFixes): through libXfixes,
    as 22.04's python-xlib cannot ask for it."""
    import ctypes
    import hashlib

    class Image(ctypes.Structure):
        _fields_ = [('x', ctypes.c_short), ('y', ctypes.c_short), ('width', ctypes.c_ushort),
                    ('height', ctypes.c_ushort), ('xhot', ctypes.c_ushort), ('yhot', ctypes.c_ushort),
                    ('serial', ctypes.c_ulong), ('pixels', ctypes.POINTER(ctypes.c_ulong)),
                    ('atom', ctypes.c_ulong), ('name', ctypes.c_char_p)]
    xlib = ctypes.CDLL('libX11.so.6')
    xfixes = ctypes.CDLL('libXfixes.so.3')
    xlib.XOpenDisplay.restype = ctypes.c_void_p
    xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
    xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
    xfixes.XFixesGetCursorImage.restype = ctypes.POINTER(Image)
    xfixes.XFixesGetCursorImage.argtypes = [ctypes.c_void_p]
    display = xlib.XOpenDisplay(None)
    try:
        image = xfixes.XFixesGetCursorImage(display).contents
        pixels = bytes(memoryview(ctypes.cast(image.pixels, ctypes.POINTER(
            ctypes.c_ulong * (image.width * image.height))).contents))
        return image.width, image.height, hashlib.sha1(pixels).hexdigest()
    finally:
        xlib.XCloseDisplay(display)


def opened_by_click(app, inp, note, dx):
    """Click the text dx from its left, and the address a browser was asked
    to open, if one was."""
    opened = fake_browser(app.home)
    x, y = note.text_point(dx, 10)
    app.inp.click(x, y)
    try:
        wait_until(lambda: os.path.exists(opened), timeout=5, what='the link')
    except AssertionError:
        return None
    with open(opened) as f:
        return f.read().strip()


def test_J2_a_click_opens_a_link(app, inp):
    note = start(app, 'see https://example.com/page now', at=(200, 10))
    assert opened_by_click(app, inp, note, 80) == 'https://example.com/page'


def test_J3_a_link_leaves_out_the_punctuation_after_it(app, inp):
    note = start(app, 'at https://example.com:8080/a?b=(c), then', at=(200, 10))
    assert opened_by_click(app, inp, note, 70) == 'https://example.com:8080/a?b=(c)'


def test_J2a_an_address_typed_becomes_a_link_as_a_space_ends_it(app, inp):
    start(app, '', at=(200, 10))
    inp.type('see https://e.com/a')
    settle(0.3)
    assert saved_link(app) is None, 'not while it is typed'
    inp.type(' now')
    wait_until(lambda: saved_link(app) == ('https://e.com/a', 'https://e.com/a'), what='the address linked')


def test_J2a_an_address_typed_becomes_a_link_as_enter_ends_it(app, inp):
    start(app, '', at=(200, 10))
    inp.type('https://e.com/a')
    inp.key('enter')
    inp.type('next')
    wait_until(lambda: saved_link(app) == ('https://e.com/a', 'https://e.com/a'), what='the address linked')


def test_J2a_an_address_pasted_becomes_a_link(app, inp):
    from tests.e2e.driver import set_clipboard
    start(app, 'see ', at=(200, 10))
    set_clipboard('https://e.com/a')
    inp.key('ctrl+v')
    wait_until(lambda: saved_link(app) == ('https://e.com/a', 'https://e.com/a'), what='the address linked')


def test_J2b_a_link_shows_the_hand(app, inp):
    note = start(app, 'plain https://e.com/a', at=(200, 10))
    x, y = note.text_point(10, 10)
    inp.move(x, y)
    settle(0.3)
    text = cursor_image(inp)
    x, y = note.text_point(90, 10)
    inp.move(x, y)
    settle(0.3)
    assert cursor_image(inp) != text


def test_J6_an_address_gets_text_of_its_own(app, inp):
    start(app, 'see https://e.com/a now', at=(200, 10))
    inp.key('home')
    for _ in range(6):
        inp.key('right')
    inp.key('ctrl+k')
    link_form(app)
    settle(0.3)
    inp.key('ctrl+a')
    inp.type('docs')
    inp.key('enter')
    wait_until(lambda: saved_link(app) == ('docs', 'https://e.com/a'), what='the address given text')


def test_J6_remove_link_leaves_text_that_a_click_does_not_open(app, inp):
    from tests.e2e.driver import center, find_all, name
    note = start(app, 'see https://e.com/a now', at=(200, 10))
    inp.key('home')
    for _ in range(6):
        inp.key('right')
    inp.key('ctrl+k')
    form = link_form(app)
    remove = wait_until(lambda: next(iter(find_all(form, lambda a: name(a) == 'Remove link')), None),
                        what='Remove link')
    app.inp.click(*center(remove))
    assert_saved(app, "paragraph('see https://e.com/a now')", last_line=False)
    # Typing after it does not make it a link again.
    inp.key('end')
    inp.type(' more')
    settle(0.5)
    assert saved_link(app) is None
    assert opened_by_click(app, inp, note, 80) is None


def test_J6_the_link_forms_fields_fit_in_it(app, inp):
    from tests.e2e.driver import extents, find_all, role, showing
    doc_note(app, [{'type': 'text', 'text': 'docs', 'marks': [{'type': 'link', 'attrs': {'href': 'https://e.com/a'}}]}])
    inp.key('right')
    inp.key('ctrl+k')
    form = link_form(app)
    settle(0.3)
    buttons = [b for b in find_all(form, lambda a: role(a) in ('button', 'push button')) if showing(b)]
    from tests.e2e.driver import Atspi
    # By being editable: 22.04's WebKit names a field's role otherwise.
    fields = [f for f in find_all(form, lambda a: a.get_state_set().contains(Atspi.StateType.EDITABLE)
                                  and role(a) not in ('document web', 'frame', 'window')) if showing(f)]
    assert len(fields) >= 2, [role(f) for f in fields]
    right = max(extents(b)[0] + extents(b)[2] for b in buttons)
    for f in fields:
        x, y, w, h = extents(f)
        assert x + w <= right + 1, (x + w, right)
