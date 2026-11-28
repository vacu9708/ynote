"""The rest of 1.x's behaviors in Ynote 2.0: formats out as Markdown, code
blocks, images, tables, expands, the clipboard, undo, find, and drawing.
See BEHAVIORS.md."""
import json
import os
import time

import pytest

from tests.e2e.driver import (
    Atspi, clipboard_text, find_all, name, role, screenshot, set_clipboard, settle, showing, wait_until)
from tests.e2e.web import (
    WebNote, assert_saved, choose, ink, put_image_on_clipboard, saved_blocks, saved_note, start,
    text_holding)



ANCHOR = '￼'
B, Q = '• ', '▍ '
OPEN, CLOSED, END = '▾ ', '▸ ', '⁤'
TABLE = {'tables': [{'offset': 2, 'rows': [[{'text': 'k'}, {'text': 'v'}],
                                          [{'text': 'a'}, {'text': 'b'}]]}]}


def box(note, needle):
    """The screen box of needle's text, as (x, y, w, h)."""
    acc, at = text_holding(note, needle)
    r = Atspi.Text.get_range_extents(acc, at, at + len(needle), Atspi.CoordType.SCREEN)
    return r.x, r.y, r.width, r.height


def char_boxes(note, needle):
    acc, at = text_holding(note, needle)
    return [Atspi.Text.get_character_extents(acc, i, Atspi.CoordType.SCREEN) for i in range(at, at + len(needle))]


def copied(inp, keys='ctrl+c'):
    set_clipboard('-')
    inp.key(keys)
    return wait_until(lambda: (clipboard_text() or '-') != '-' and clipboard_text(), what='a copy')


def pixels(area):
    # Inside the text's box, clear of a blinking cursor at either end.
    x, y, w, h = area
    pb = screenshot('/tmp/e2e-area.png', (x + 3, y + 2, w - 6, h - 4))
    return bytes(pb.get_pixels())


# ---------------------------------------------------------------- E, H


def test_E15_bold_in_a_heading_goes_out_and_comes_back_as_markdown(app, inp):
    start(app, 'Title bold', heading_ranges=[[0, 10]], bold_ranges=[[6, 10]], at=(200, 10))
    inp.key('ctrl+a')
    assert copied(inp) == '# Title **bold**'
    inp.key('ctrl+end')              # the empty line a note ends with
    set_clipboard('# Again **b**')
    inp.key('ctrl+v')
    assert_saved(app, "heading('Title ' 'bold'[strong]) heading('Again ' 'b'[strong])", last_line=False)


def test_H3_a_wrapped_quotes_later_rows_start_as_far_in_as_its_text(app, inp):
    words = ' '.join(['word'] * 30)
    note = start(app, Q + words, w=260, at=(5, 10))
    boxes = char_boxes(note, words)
    first = boxes[0]
    later = next(b for b in boxes if b.y > first.y + first.height // 2 and b.width > 0)
    assert abs(later.x - first.x) <= 2, (first.x, later.x)


# ---------------------------------------------------------------- I


def test_I2_a_code_lines_do_not_wrap_and_the_block_scrolls_sideways(app, inp):
    line = 'echo ' + 'x' * 150
    note = start(app, line + '\nb', code_ranges=[[0, len(line)]], w=300)
    boxes = char_boxes(note, 'echo')
    x, y, w, h = note.box
    assert all(abs(b.y - boxes[0].y) <= 1 for b in boxes)
    # The line's end is on its row, past the note's right edge, to scroll to.
    acc, at = text_holding(note, 'x' * 150)
    end = Atspi.Text.get_character_extents(acc, at + 149, Atspi.CoordType.SCREEN)
    assert end.y == boxes[0].y, (end.y, boxes[0].y)


def test_I8_lines_already_code_stay_as_they_are(app, inp):
    start(app, 'ls -l\nb', code_ranges=[[0, 5]], at=(200, 10))
    inp.key('ctrl+a')
    inp.key('ctrl+shift+c')
    assert_saved(app, "code_block('ls -l\\nb')", last_line=False)


def test_I8_lines_with_an_image_are_not_made_code(app, inp):
    os.makedirs(os.path.join(app.conf, 'images'))
    with open(os.path.join(app.conf, 'images', 'i.png'), 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
    start(app, 'a\n' + ANCHOR, at=(200, 10),
          images=[{'file': 'i.png', 'original_name': 'i.png', 'offset': 2}])
    inp.key('ctrl+a')
    inp.key('ctrl+shift+c')
    inp.key('ctrl+end')
    inp.type('z')

    def saved():
        try:
            return 'z' in saved_blocks(app) and saved_blocks(app)
        except (OSError, ValueError):
            return None
    blocks = wait_until(saved, what='the note saved')
    assert 'code_block' not in blocks and 'image' in blocks, blocks


def test_I10_a_find_match_in_a_code_block_is_lit(app, inp):
    note = start(app, 'top\nkubectl get pods', code_ranges=[[4, 20]], at=(200, 10))
    area = box(note, 'pods')
    before = pixels(area)
    inp.key('ctrl+f')
    inp.type('pods')
    settle(0.4)
    assert pixels(area) != before


def test_I11_a_long_code_block_opens_fast_and_types_fast(app, inp):
    lines = '\n'.join(f'line {i} echo something long enough to count' for i in range(3000))
    app.write_notes([{'id': 'test', 'title': 'test', 'text': lines, 'code_ranges': [[0, len(lines)]],
                      'x': 100, 'y': 80, 'w': 500, 'h': 500}])
    began = time.monotonic()
    app.start()
    note = WebNote(app, app.note('test').frame)
    note.click_text(200, 10)
    opened = time.monotonic() - began
    assert opened < 10, opened
    inp.key('end')
    began = time.monotonic()
    inp.type('typed fast')

    def saved():
        try:
            return 'typed fast' in saved_note(app)['doc']['content'][0]['content'][0]['text'][:200]
        except (OSError, ValueError, KeyError, IndexError):
            return False
    wait_until(saved, timeout=10, what='the typing saved')
    assert time.monotonic() - began < 5


# ---------------------------------------------------------------- K


def test_K3_an_image_removed_stays_while_undo_can_bring_it_back(app, inp):
    start(app, 'x', at=(200, 10))
    put_image_on_clipboard()
    inp.key('ctrl+v')
    images = os.path.join(app.conf, 'images')
    wait_until(lambda: 'image' in saved_blocks(app), what='the image in the note')
    files = os.listdir(images)
    inp.key('backspace')
    wait_until(lambda: 'image' not in saved_blocks(app), what='the image taken out')
    settle(1)
    assert os.listdir(images) == files
    inp.key('ctrl+z')
    wait_until(lambda: 'image' in saved_blocks(app), what='the image back')
    assert os.listdir(images) == files


def test_K4_an_image_in_a_table_cell_counts_as_in_use(app):
    images = os.path.join(app.conf, 'images')
    os.makedirs(images)
    for n in ('cell.png', 'unused.png'):
        with open(os.path.join(images, n), 'wb') as f:
            f.write(b'\x89PNG\r\n\x1a\n')
    image = {'type': 'image', 'attrs': {'file': 'cell.png', 'name': 'cell.png'}}
    cell = lambda kind, content: {'type': kind, 'content': [{'type': 'paragraph', 'content': content}]}
    doc = {'type': 'doc', 'content': [{'type': 'table', 'content': [
        {'type': 'table_row', 'content': [cell('table_header', [{'type': 'text', 'text': 'k'}])]},
        {'type': 'table_row', 'content': [cell('table_cell', [image])]}]}, {'type': 'paragraph'}]}
    with open(app.notes_file, 'w') as f:
        json.dump([{'id': 'test', 'title': 'test', 'x': 100, 'y': 80, 'w': 400, 'h': 300, 'doc': doc}], f)
    app.start()
    app.note('test')
    wait_until(lambda: not os.path.exists(os.path.join(images, 'unused.png')), what='the unused image to go')
    assert os.path.exists(os.path.join(images, 'cell.png'))


# ---------------------------------------------------------------- L


def in_table(app, **fields):
    return start(app, 'x\n' + ANCHOR, at=(200, 10), **(fields or TABLE))


def test_L2_a_click_right_of_a_cells_text_puts_the_cursor_at_its_end(app, inp):
    note = in_table(app)
    x, y, w, h = box(note, 'a')
    app.inp.click(x + w + 4, y + h // 2)
    inp.type('Z')
    assert_saved(app, "paragraph('x') table(table_row(table_header(paragraph('k')) table_header(paragraph('v'))) "
                      "table_row(table_cell(paragraph('aZ')) table_cell(paragraph('b'))))", last_line=False)


def test_L3_a_double_click_in_a_cell_selects_a_word(app, inp):
    note = in_table(app, tables=[{'offset': 2, 'rows': [[{'text': 'k'}], [{'text': 'hello world'}]]}])
    x, y, w, h = box(note, 'world')
    app.inp.click(x + w // 2, y + h // 2, count=2)
    inp.type('X')
    assert_saved(app, "paragraph('x') table(table_row(table_header(paragraph('k'))) "
                      "table_row(table_cell(paragraph('hello X'))))", last_line=False)


def test_L13_a_cell_holds_quotes_and_code_blocks(app, inp):
    note = in_table(app)
    x, y, w, h = box(note, 'a')
    app.inp.click(x + w + 4, y + h // 2)
    inp.key('enter')
    inp.type('> q')
    inp.key('enter')
    inp.key('enter')
    inp.type('```')
    inp.type('ls')
    assert_saved(app, "paragraph('x') table(table_row(table_header(paragraph('k')) table_header(paragraph('v'))) "
                      "table_row(table_cell(paragraph('a') blockquote(paragraph('q')) code_block('ls')) "
                      "table_cell(paragraph('b'))))", last_line=False)


def cell_widths(note):
    cells = [c for c in find_all(note.frame, lambda a: role(a) in ('table cell', 'column header'), limit=80)
             if showing(c)]
    return [c.get_extents(Atspi.CoordType.SCREEN).width for c in cells]


def test_L15_a_column_is_as_wide_as_its_text(app, inp):
    note = in_table(app, tables=[{'offset': 2, 'rows': [[{'text': 'id'}, {'text': 'description of it'}],
                                                       [{'text': '1'}, {'text': 'a much longer line of text'}]]}])
    narrow = box(note, 'id')[2]
    wide = box(note, 'a much longer line of text')[2]
    x1 = box(note, 'id')[0]
    x2 = box(note, 'description')[0]
    # The first column ends soon after its text.
    assert x2 - x1 < narrow + 60, (x1, x2, narrow, wide)


def test_L16_short_inline_code_does_not_wrap_in_a_narrow_column(app, inp):
    rows = [[{'text': 'flag'}, {'text': 'what it does, said at some length so the column is wide'}],
            [{'text': 'x | y', 'backtick': [[0, 5]]}, {'text': 'pipe x into y, said at length too, wide'}]]
    note = in_table(app, tables=[{'offset': 2, 'rows': rows}], w=320)
    boxes = char_boxes(note, 'x | y')
    assert all(abs(b.y - boxes[0].y) <= 1 for b in boxes), [b.y for b in boxes]


def test_L18_a_note_has_one_selection(app, inp):
    note = in_table(app, tables=[{'offset': 2, 'rows': [[{'text': 'k'}], [{'text': 'hello world'}]]}])
    x, y, w, h = box(note, 'world')
    app.inp.click(x + w // 2, y + h // 2, count=2)
    settle(0.5)
    note.click_text(200, 10)        # right of x, above the table
    inp.type('Y')
    assert_saved(app, "paragraph('xY') table(table_row(table_header(paragraph('k'))) "
                      "table_row(table_cell(paragraph('hello world'))))", last_line=False)


def beside_table(app):
    note = start(app, 'x\n' + ANCHOR, at=(200, 10), **TABLE)
    x, y, w, h = box(note, 'b')
    app.inp.click(x + 300, y + h // 2)
    return note


TABLE_AB = ("table(table_row(table_header(paragraph('k')) table_header(paragraph('v'))) "
            "table_row(table_cell(paragraph('a')) table_cell(paragraph('b'))))")


def test_L21b_enter_beside_a_table_opens_a_line_after_it(app, inp):
    beside_table(app)
    inp.key('enter')
    inp.type('W')
    blocks = saved_blocks(app)
    wait_until(lambda: "paragraph('W')" in saved_blocks(app), what='W after the table')
    assert saved_blocks(app).startswith("paragraph('x') " + TABLE_AB + " "), blocks


def test_L21b_backspace_beside_a_table_goes_into_its_last_cell(app, inp):
    beside_table(app)
    inp.key('backspace')
    inp.type('Z')
    assert_saved(app, "paragraph('x') " + TABLE_AB.replace("paragraph('b')", "paragraph('bZ')"), last_line=False)


def test_L21b_left_beside_a_table_goes_into_it(app, inp):
    beside_table(app)
    inp.key('left')
    inp.type('Z')
    assert_saved(app, "paragraph('x') " + TABLE_AB.replace("paragraph('b')", "paragraph('bZ')"), last_line=False)


def test_L22_find_finds_text_in_a_cell_and_selects_it_there(app, inp):
    in_table(app, tables=[{'offset': 2, 'rows': [[{'text': 'k'}], [{'text': 'needle here'}]]}])
    inp.key('ctrl+f')
    inp.type('needle')
    inp.key('esc')
    inp.type('X')
    assert_saved(app, "paragraph('x') table(table_row(table_header(paragraph('k'))) "
                      "table_row(table_cell(paragraph('X here'))))", last_line=False)


def test_L23_a_folded_expand_hides_a_table_in_it(app, inp):
    text = '\n'.join(['top', CLOSED + 'T', ANCHOR, END])
    note = start(app, text, at=(200, 10), tables=[{'offset': text.index(ANCHOR),
                                                   'rows': [[{'text': 'hiddencell'}]]}])
    try:
        x, y, w, h = box(note, 'hiddencell')
    except AssertionError:
        return
    assert w == 0 or h == 0, (x, y, w, h)


def test_L24_a_table_copies_as_a_github_markdown_table(app, inp):
    rows = [[{'text': 'Name', 'bold': [[0, 4]]}, {'text': 'Cmd'}],
            [{'text': 'two\nlines'}, {'text': 'a|b', 'backtick': [[0, 3]]}]]
    start(app, ANCHOR, tables=[{'offset': 0, 'rows': rows}], at=(5, 10))
    inp.key('ctrl+a')
    assert copied(inp) == '| Name | Cmd |\n| --- | --- |\n| two<br>lines | `a\\|b` |'


def test_L25_a_pasted_markdown_table_becomes_a_table(app, inp):
    start(app, '', at=(5, 10))
    set_clipboard('| k | v |\n| --- | --- |\n| one<br>two | **b** |')
    inp.key('ctrl+v')
    assert_saved(app, "table(table_row(table_header(paragraph('k')) table_header(paragraph('v'))) "
                      "table_row(table_cell(paragraph('one') paragraph('two')) "
                      "table_cell(paragraph('b'[strong]))))", last_line=False)


def test_L26_markdown_pasted_into_a_cell_keeps_its_formats(app, inp):
    note = in_table(app)
    x, y, w, h = box(note, 'a')
    app.inp.click(x + w + 4, y + h // 2)
    set_clipboard(' **bold** and `code`')
    inp.key('ctrl+v')
    assert_saved(app, "paragraph('x') table(table_row(table_header(paragraph('k')) table_header(paragraph('v'))) "
                      "table_row(table_cell(paragraph('a ' 'bold'[strong] ' and ' 'code'[code])) "
                      "table_cell(paragraph('b'))))", last_line=False)


def test_L26_a_table_is_not_put_in_a_cell(app, inp):
    note = in_table(app)
    x, y, w, h = box(note, 'a')
    app.inp.click(x + w + 4, y + h // 2)
    set_clipboard('| p | q |\n| --- | --- |\n| 1 | 2 |')
    inp.key('ctrl+v')
    settle(1)
    # It goes after the table, which stays whole.
    assert_saved(app, "paragraph('x') table(table_row(table_header(paragraph('k')) table_header(paragraph('v'))) "
                      "table_row(table_cell(paragraph('a')) table_cell(paragraph('b')))) "
                      "table(table_row(table_header(paragraph('p')) table_header(paragraph('q'))) "
                      "table_row(table_cell(paragraph('1')) table_cell(paragraph('2'))))", last_line=False)


# ---------------------------------------------------------------- M


def test_M1_insert_expand_puts_the_selected_lines_in_it(app, inp):
    note = start(app, 'a\nb\nc', at=(200, 10))
    inp.key('shift+down')
    inp.key('shift+end')
    note.press('More to insert')
    choose(app, 'Expand')
    inp.type('T')
    assert_saved(app, "expand(expand_title('T') paragraph('a') paragraph('b')) paragraph('c')", last_line=False)


def test_M1_an_expand_on_the_last_line_leaves_a_line_after_it(app, inp):
    note = start(app, 'a\n', at=(200, 10))
    inp.key('ctrl+end')
    note.press('More to insert')
    choose(app, 'Expand')
    assert_saved(app, "paragraph('a') expand(expand_title() paragraph()) paragraph()")


def test_M3_an_expand_holds_code_lists_tables_and_expands(app):
    text = '\n'.join([OPEN + 'Outer', 'ls', B + 'item', ANCHOR, OPEN + 'Inner', 'deep', END, END])
    app.write_notes([{'id': 'test', 'title': 'test', 'text': text, 'code_ranges': [[text.index('ls'), text.index('ls') + 2]],
                      'tables': [{'offset': text.index(ANCHOR), 'rows': [[{'text': 'k'}]]}],
                      'x': 100, 'y': 80, 'w': 400, 'h': 400}])
    app.start()
    app.note('test')
    app.quit()
    assert saved_blocks(app) == (
        "expand(expand_title('Outer') code_block('ls') bullet_list(list_item(paragraph('item'))) "
        "table(table_row(table_header(paragraph('k')))) expand(expand_title('Inner') paragraph('deep')))")


# ---------------------------------------------------------------- N, O, P, Q


def test_N9_copying_out_and_pasting_back_as_markdown_gives_the_same_note(app, inp):
    from tests.e2e.test_clipboard import FIELDS, TEXT, two_notes
    first, other = two_notes(app, TEXT, **FIELDS)
    first.click_text(200, 10)
    inp.key('ctrl+a')
    markdown = copied(inp)
    before = saved_blocks(app)
    other.click_text(10, 8)
    set_clipboard(markdown)          # as from another app
    inp.key('ctrl+v')
    # Not the image, which Markdown does not carry.
    wait_until(lambda: 'expand' in saved_blocks(app, 'other'), what='the paste saved')
    settle(0.8)
    # But for the blank line Markdown needs before a divider.
    after = saved_blocks(app, 'other').replace(' paragraph() horizontal_rule()', ' horizontal_rule()')
    assert after.removesuffix(' paragraph()') == before.removesuffix(' paragraph()')


def test_O3_after_undo_the_bold_button_follows_the_cursor(app, inp):
    note = start(app, 'ab', at=(200, 10))
    inp.key('ctrl+b')
    inp.type('cd')
    settle(0.6)

    def bold_on():
        # Found anew each time: WebKit 2.50 leaves a state kept from before.
        bold = note.button('Bold')
        bold.clear_cache()
        states = bold.get_state_set()
        return states.contains(Atspi.StateType.PRESSED) or states.contains(Atspi.StateType.CHECKED)
    wait_until(bold_on, what='Bold on')
    inp.key('ctrl+z')
    wait_until(lambda: not bold_on(), what='Bold off')


def test_P4_all_notes_shows_each_match_with_its_note_and_line(app, inp):
    long = 'start of a long line that goes on and on until the match ' + 'needle' + ' and after'
    app.write_notes([
        {'id': 'test', 'title': 'test', 'text': 'here', 'x': 100, 'y': 80, 'w': 500, 'h': 400},
        {'id': 'o', 'title': 'other', 'text': long, 'hidden': True, 'x': 700, 'y': 80, 'w': 300, 'h': 300}])
    app.start()
    note = WebNote(app, app.note('test').frame)
    note.click_text(10, 8)
    inp.key('ctrl+f')
    inp.key('alt+a')
    inp.type('needle')
    settle(0.6)
    texts = [name(a) for a in find_all(note.frame, lambda a: True, limit=200) if showing(a)]
    texts += [Atspi.Text.get_text(a, 0, -1) for a in find_all(
        note.frame, lambda a: a.get_text_iface() is not None, limit=200)]
    joined = ' | '.join(t for t in texts if t)
    assert 'other' in joined and 'needle' in joined and 'hidden' in joined, joined[:600]
    assert 'start of a long' not in joined, 'the line is cut around the match'


def test_P7_highlights_go_when_find_closes(app, inp):
    note = start(app, 'top needle', at=(200, 10))
    area = box(note, 'needle')
    before = pixels(area)
    inp.key('ctrl+f')
    inp.type('needle')
    settle(0.4)
    assert pixels(area) != before
    inp.key('esc')
    note.click_text(5, 10)
    settle(0.4)
    assert pixels(area) == before


def test_Q1_a_long_line_wraps_at_the_notes_width(app, inp):
    words = ' '.join(['word'] * 40)
    note = start(app, words, w=260, at=(5, 10))
    boxes = char_boxes(note, words)
    x, y, w, h = note.box
    assert boxes[-1].y > boxes[0].y
    assert all(b.x + b.width <= x + w for b in boxes)


def test_Q2_in_a_note_with_korean_every_line_is_as_far_from_the_next(app, inp):
    note = start(app, 'abc\n한글 줄\ndef\nghi', at=(200, 10))
    ys = [box(note, t)[1] for t in ('abc', '한글', 'def', 'ghi')]
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    assert max(gaps) - min(gaps) <= 1, gaps


def test_Q11_bold_in_a_heading_is_drawn_bolder_in_korean_too(app, inp):
    note = start(app, '한글제목 한글제목', heading_ranges=[[0, 9]], bold_ranges=[[5, 9]], at=(200, 10))
    plain = ink(note, '한글제목 ')
    bold = ink(note, ' 한글제목')
    assert bold > plain * 1.05, (plain, bold)
