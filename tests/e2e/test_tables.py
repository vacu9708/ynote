"""L. Tables: see BEHAVIORS.md."""
from tests.e2e.driver import extents, settle, wait_until

TABLE = '| Name | Description | State |\n| --- | --- | --- |\n' \
        '| Kim | first line<br>second line | done |\n' \
        '| Lee | a long cell with enough words to wrap | x |\nbelow\n'


def cell_texts(note):
    return [[c.text() for c in row] for row in note.tables()[0]]


def test_L1_insert_table_adds_a_table_with_the_cursor_in_its_first_cell(note, app):
    note.press('Insert')
    note.choose('Table')
    wait_until(lambda: note.tables(), what='a table')
    first = note.cell(0, 0)
    wait_until(first.focused, what='the first cell to have the cursor')
    app.inp.type('Head')
    assert note.cell(0, 0).text() == 'Head'


def test_L2_a_click_in_a_cell_puts_the_cursor_where_it_was_clicked(write, app):
    note = write(TABLE)
    cell = note.cell(1, 1)
    cell.click_text('second', at='start')
    assert cell.focused()
    app.inp.type('X')
    assert note.cell(1, 1).text() == 'first line\nXsecond line'
    # and in another cell, then a header cell
    note.cell(2, 0).click_text('ee', at='start')
    app.inp.type('Y')
    assert note.cell(2, 0).text() == 'LYee'
    note.cell(0, 2).click_text('State', at='end')
    app.inp.type('Z')
    assert note.cell(0, 2).text() == 'StateZ'


def test_L4_tab_past_the_last_cell_adds_a_row_you_can_type_in(write, app):
    note = write(TABLE)
    note.cell(2, 2).click_text('x', at='end')
    app.inp.key('tab')
    wait_until(lambda: len(note.tables()[0]) == 4, what='a new row')
    new = note.cell(3, 0)
    assert new.focused()
    app.inp.type('new')
    assert note.cell(3, 0).text() == 'new'


def test_L10_rows_and_columns_from_a_cells_menu_can_be_typed_in(write, app):
    note = write(TABLE)
    note.cell(1, 1).click_text('first', at='start')
    x, y = note.cell(1, 1).point_at(0)
    app.inp.click(x, y, button=3)
    note.choose('Add Row Below')
    wait_until(lambda: len(note.tables()[0]) == 4, what='a new row')
    app.inp.type('r')
    assert note.cell(2, 0).text() == 'r'
    x, y = note.cell(1, 0).point_at(0)
    app.inp.click(x, y, button=3)
    note.choose('Add Column Right')
    wait_until(lambda: len(note.tables()[0][0]) == 4, what='a new column')
    app.inp.type('c')
    assert note.cell(0, 1).text() == 'c'


def test_L18_a_note_has_one_selection_across_its_text_and_cells(write, app):
    note = write(TABLE)
    header = note.cell(0, 1)
    header.click_text('Description', at='middle', count=2)
    assert header.selection() == (0, 11)
    note.cell(1, 0).click_text('Kim', at='end')
    assert note.cell(0, 1).selection() is None
    note.body.click_text('below', at='end')
    assert note.cell(1, 0).selection() is None


def test_L19_typing_over_a_selection_across_a_table_removes_it(write, app):
    note = write('above\n\n' + TABLE)
    body = note.body
    text = body.text()
    start, end = text.index('above') + 2, text.index('below') + 2
    app.inp.drag(body.point_at(start), body.point_at(end))
    app.inp.type('W')
    wait_until(lambda: not note.tables(), what='the table to go')
    assert 'abW' in note.body.text()
    app.inp.key('ctrl+z')
    settle(1.0)
    assert note.tables(), 'undo brings the table back'
    note.cell(1, 1).click_text('first', at='start')
    assert note.cell(1, 1).focused()


def test_L29_cells_are_saved_with_their_text(write, app):
    note = write(TABLE)
    note.cell(1, 0).click_text('Kim', at='end')
    app.inp.type(' saved')
    app.quit()
    table = app.saved_note('test')['tables'][0]
    assert table['rows'][1][0]['text'] == 'Kim saved'


def test_L3_drag_and_double_click_select_inside_a_cell(write, app):
    note = write(TABLE)
    cell = note.cell(2, 1)
    app.inp.drag(cell.point_at(2), cell.point_at(5, 'right'))
    assert cell.selection() == (2, 6)
    assert note.body.selection() is None
    settle(0.5)  # a person pauses between a drag and a double click
    cell.click_text('cell', at='middle', count=2)
    assert cell.selection() == (7, 11)


def test_L5_tab_in_a_list_item_in_a_cell_indents_it(write, app):
    note = write(TABLE)
    cell = note.cell(1, 0)
    cell.click_text('Kim', at='end')
    app.inp.key('enter')
    app.inp.type('- item')
    app.inp.key('tab')
    assert note.cell(1, 0).text().endswith('\t• item')
    assert note.cell(1, 0).focused()


def test_L6_enter_in_a_cell_is_a_new_line_and_the_table_grows(write, app):
    note = write(TABLE)
    before = note.tables()[0][2][0]
    top = before.char_box(0)[1]
    note.cell(1, 0).click_text('Kim', at='end')
    app.inp.key('enter')
    app.inp.type('two')
    app.inp.key('enter')
    app.inp.type('three')
    assert note.cell(1, 0).text() == 'Kim\ntwo\nthree'
    wait_until(lambda: note.cell(2, 0).char_box(0)[1] > top,
               what='the row below to move down')


def test_L7_up_and_down_at_a_cells_edge_and_esc_move_between_cells(write, app):
    note = write(TABLE)
    note.cell(1, 1).click_text('second', at='middle')
    app.inp.key('down')
    assert note.cell(2, 1).focused()
    app.inp.key('up')
    assert note.cell(1, 1).focused()
    note.cell(2, 0).click_text('Lee', at='end')
    app.inp.key('down')
    assert note.body.focused()
    app.inp.type('X')
    assert note.body.text().startswith('\nXbelow')
    note.cell(1, 0).click_text('Kim', at='end')
    app.inp.key('esc')
    assert note.body.focused()


def test_L8_arrow_keys_go_into_a_table_from_the_lines_around_it(write, app):
    note = write('above\n\n' + TABLE)
    note.body.click_text('above', at='end')
    app.inp.key('down')
    app.inp.key('down')
    assert note.cell(0, 0).focused()
    note.body.click_text('below', at='start')
    app.inp.key('up')
    last = note.tables()[0][-1][-1]
    assert last.focused()


def test_L9_leaving_a_table_at_the_end_of_an_expand_goes_past_it(write, app):
    note = write('top\n\n<details open>\n<summary>Fold</summary>\n\n'
                 '| K | V |\n| --- | --- |\n| a | b |\n\n</details>\n\nbottom\n')
    note.cell(1, 0).click_text('a', at='end')
    app.inp.key('esc')
    assert note.body.focused()
    app.inp.type('X')
    # Past the end of the expand: folding it leaves X in view.
    note.body.click_at(note.body.text().index('▾'))
    wait_until(lambda: not note.tables(), what='folding')
    assert 'X' in note.body.text()


def test_L22b_a_search_match_in_a_cell_of_a_folded_expand_is_selected(write, app):
    note = write('top\n\n<details>\n<summary>Fold</summary>\n\n'
                 '| K | V |\n| --- | --- |\n| banana | yellow |\n\n</details>\n')
    note.search('banana')
    app.inp.key('enter')
    cell = wait_until(lambda: note.tables() and note.cell(1, 0), what='the table')
    wait_until(lambda: cell.selection() == (0, 6), what='the match selected')


def test_L10a_deleting_the_header_row_makes_the_next_row_a_bold_header(write, app):
    note = write(TABLE)
    x, y = note.cell(0, 0).point_at(0)
    app.inp.click(x, y, button=3)
    note.choose('Delete Row')
    wait_until(lambda: len(note.tables()[0]) == 2, what='the row to go')
    assert note.cell(0, 0).text() == 'Kim'
    assert note.cell(0, 0).formats('Kim') == {'bold'}


def test_L10b_deleting_the_last_row_or_column_deletes_the_table(write, app):
    note = write('| A |\n| --- |\n\nafter\n')
    x, y = note.cell(0, 0).point_at(0)
    app.inp.click(x, y, button=3)
    note.choose('Delete Row')
    wait_until(lambda: not note.tables(), what='the table to go')


def test_L11_a_deleted_table_comes_back_with_undo_and_takes_clicks(write, app):
    note = write(TABLE)
    x, y = note.cell(1, 1).point_at(0)
    app.inp.click(x, y, button=3)
    note.choose('Delete Table')
    wait_until(lambda: not note.tables(), what='the table to go')
    app.inp.key('ctrl+z')
    wait_until(lambda: note.tables(), what='the table to come back')
    note.cell(1, 1).click_text('second', at='start')
    assert note.cell(1, 1).focused()


def test_L12_undo_in_a_cell_undoes_the_cells_edit(write, app):
    note = write(TABLE)
    note.cell(1, 0).click_text('Kim', at='end')
    app.inp.type('XYZ')
    settle(1.0)
    app.inp.key('ctrl+z')
    wait_until(lambda: note.cell(1, 0).text() == 'Kim', what='undo in the cell')


def test_L13_a_cell_holds_lists_quotes_code_and_formats(write, app):
    note = write(TABLE)
    note.cell(1, 0).click_text('Kim', at='end')
    for line in ('', '- item', '', '> quote', '', '```', 'ls -l'):
        if line:
            app.inp.type(line)
        app.inp.key('enter')
    cell = note.cell(1, 0)
    assert '• item' in cell.text()
    assert 'quote' in cell.text()
    assert cell.formats('ls -l') == {'code'}


def test_L14_format_shortcuts_act_on_the_cell_with_the_cursor(write, app):
    note = write(TABLE)
    cell = note.cell(1, 0)
    cell.click_text('Kim', at='middle', count=2)
    app.inp.key('ctrl+b')
    assert note.cell(1, 0).formats('Kim') == {'bold'}
    assert note.body.formats('below') == set()
    note.press('Insert')
    labels = note.menu_items()
    assert 'Table' in labels
    app.inp.key('esc')


def test_L16_short_inline_code_in_a_narrow_column_stays_on_one_line(write, app):
    note = write('| Name | Description of a fairly long column | State |\n'
                 '| --- | --- | --- |\n| a | b | `x \\| y` |\n')
    cell = note.cell(1, 2)
    text = cell.text()
    assert cell.char_box(text.index('x'))[1] == cell.char_box(text.index('y'))[1]


def test_L17_a_header_cell_is_bold_and_its_bold_turns_off(write, app):
    note = write(TABLE)
    head = note.cell(0, 1)
    assert head.formats('Description') == {'bold'}
    head.click_text('Description', at='middle', count=2)
    app.inp.key('ctrl+b')
    assert note.cell(0, 1).formats('Description') == set()
    x, y = note.cell(0, 0).point_at(0)
    app.inp.click(x, y, button=3)
    note.choose('Add Column Right')
    wait_until(lambda: len(note.tables()[0][0]) == 4, what='a new column')
    app.inp.type('New')
    assert note.cell(0, 1).formats('New') == {'bold'}


def test_L20_backspace_below_a_table_goes_into_it_and_delete_above_does_nothing(write, app):
    note = write('above\n\n' + TABLE)
    note.body.click_text('below', at='start')
    app.inp.key('backspace')
    assert note.tables()[0][-1][-1].focused()
    note.body.click_text('above', at='end')
    before = note.body.text()
    app.inp.key('del')
    app.inp.key('del')
    assert note.tables(), 'the table stays'
    assert note.body.text().startswith('above')
    del before


def test_L21_a_click_right_of_a_table_puts_the_cursor_after_it(write, app):
    note = write('above\n\n' + TABLE)
    table_box = note.tables()[0][0][-1]
    x, y, w, h = extents(table_box.acc)
    app.inp.click(x + w + 40, y + h // 2)
    assert note.body.focused()
    app.inp.type('next')
    lines = note.body.text().split('\n')
    i = lines.index('next')
    # The table's line, which holds no text a person reads.
    assert lines[i - 1] == '', 'typed text goes on the line after the table'


def test_L22_search_finds_text_in_a_cell_and_selects_it(write, app):
    note = write(TABLE)
    note.search('wrap')
    app.inp.key('enter')
    cell = wait_until(lambda: note.focused_text() if note.focused_text()
                      and note.focused_text().acc != note.body.acc else None,
                      what='a cell with the match')
    text = cell.text()
    assert cell.selection() == (text.index('wrap'), text.index('wrap') + 4)


def test_L24_a_table_copies_as_a_markdown_table(write, app):
    from tests.e2e.driver import clipboard_text
    note = write('| A | B |\n| --- | --- |\n| x<br>y | a \\| b |\n')
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+c')
    md = wait_until(clipboard_text)
    assert '| A | B |\n| --- | --- |\n| x<br>y | a \\| b |' in md


def test_L25_a_pasted_markdown_table_becomes_a_table(write, app):
    note = write('| **A** | B |\n| --- | --- |\n| one<br>two | `c` |\n')
    assert [[c.text().replace(' ', '') for c in row]
            for row in note.tables()[0]] == [['A', 'B'], ['one\ntwo', 'c']]
    assert note.cell(1, 1).formats('c') == {'code'}


def test_L27_a_table_from_ynote_1_13_opens_as_a_table(app):
    tm = '⁣'
    app.write_notes([{'id': 'n', 'title': 'old', 'x': 100, 'y': 80,
                      'w': 600, 'h': 500,
                      'text': f'top\n{tm}Name\tAge\n{tm}Kim\t31\nend'}])
    app.start()
    note = app.note('old')
    assert [[c.text() for c in row] for row in note.tables()[0]] == [
        ['Name', 'Age'], ['Kim', '31']]


def test_L28_a_cells_right_click_opens_one_menu(write, app):
    note = write(TABLE)
    x, y = note.cell(1, 1).point_at(2)
    app.inp.click(x, y, button=3)
    labels = note.menu_items()
    assert labels.count('Delete Table') == 1
    assert labels.count('Paste') <= 1
    app.inp.key('esc')


def test_L21b_beside_a_table_enter_opens_a_line_and_backspace_enters_it(write, app):
    note = write('above\n\n' + TABLE)
    x, y, w, h = extents(note.tables()[0][0][-1].acc)
    app.inp.click(x + w + 40, y + h // 2)
    app.inp.key('backspace')
    assert note.tables()[0][-1][-1].focused()
    app.inp.click(x + w + 40, y + h // 2)
    app.inp.key('enter')
    app.inp.type('new')
    assert note.body.text().split('\n')[3:5] == ['new', 'below']
    app.inp.click(x + w + 40, y + h // 2)
    app.inp.key('del')
    assert note.tables(), 'Delete beside a table leaves it'


def test_L23_a_folded_expand_hides_its_table(write, app):
    note = write('<details open>\n<summary>Fold</summary>\n\n'
                 '| K | V |\n| --- | --- |\n| a | b |\n\n</details>\n')
    assert note.tables()
    note.body.click_at(note.body.text().index('▾'))
    wait_until(lambda: not note.tables(), what='the table to be hidden')
    note.body.click_at(note.body.text().index('▸'))
    wait_until(lambda: note.tables(), what='the table to show')
