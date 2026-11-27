"""G. Bullets and to-dos: see BEHAVIORS.md."""
from tests.e2e.driver import settle


def lines(note):
    return note.body.text().rstrip('\n').split('\n')


def test_G1_ctrl_8_and_ctrl_9_make_bullets_and_to_dos(note, app):
    app.inp.type('one')
    app.inp.key('ctrl+8')
    assert lines(note) == ['• one']
    app.inp.key('ctrl+9')
    assert lines(note) == ['☐ one']
    app.inp.key('ctrl+8')
    assert lines(note) == ['• one']
    app.inp.key('ctrl+8')
    assert lines(note) == ['one']


def test_G2_enter_continues_a_list_and_on_an_empty_item_ends_it(note, app):
    app.inp.type('- a\nb\n\nplain')
    assert lines(note) == ['• a', '• b', 'plain']
    app.inp.key('enter')
    app.inp.type('[ ] t\nu')
    assert lines(note)[-2:] == ['☐ t', '☐ u']


def test_G2b_a_checked_to_do_continues_unchecked(write, app):
    note = write('- [x] done\n')
    note.body.click_text('done', at='end')
    app.inp.key('enter')
    app.inp.type('next')
    assert lines(note) == ['☑ done', '☐ next']


def test_G3_enter_at_the_start_of_an_item_adds_one_above(write, app):
    note = write('- first\n- second\n')
    note.body.click_text('second', at='start')
    app.inp.key('enter')
    assert lines(note) == ['• first', '• ', '• second']
    note.body.click_text('cond', at='start')
    app.inp.key('enter')
    assert lines(note)[-2:] == ['• se', '• cond']


def test_G4_tab_and_shift_tab_indent_an_item_one_level(write, app):
    note = write('- a\n- b\n')
    note.body.click_text('b', at='end')
    app.inp.key('tab')
    assert lines(note) == ['• a', '\t• b']
    app.inp.key('tab')
    assert lines(note) == ['• a', '\t\t• b']
    app.inp.key('shift+tab')
    assert lines(note) == ['• a', '\t• b']


def test_G5_tab_over_a_selection_indents_each_item_in_it(write, app):
    note = write('- a\n- b\n- c\nplain\n')
    body = note.body
    text = body.text()
    app.inp.drag(body.point_at(text.index('a')),
                 body.point_at(text.index('b'), 'right'))
    app.inp.key('tab')
    assert lines(note) == ['\t• a', '\t• b', '• c', 'plain']
    assert note.body.selection() is not None
    app.inp.key('shift+tab')
    assert lines(note)[:2] == ['• a', '• b']


def test_G5b_tab_over_a_selection_without_list_items_types_a_tab(write, app):
    note = write('one two\n')
    body = note.body
    app.inp.drag(body.point_at(0), body.point_at(2, 'right'))
    app.inp.key('tab')
    assert lines(note) == ['\t two']


def test_G6_backspace_at_the_start_of_an_item_takes_its_marker_or_outdents(write, app):
    note = write('- top\n  - nested\n')
    note.body.click_text('nested', at='start')
    app.inp.key('backspace')
    assert lines(note) == ['• top', '• nested']
    app.inp.key('backspace')
    assert lines(note) == ['• top', 'nested']


def test_G7_delete_at_the_end_of_a_line_takes_the_next_items_marker(write, app):
    note = write('text\n- item\n')
    note.body.click_text('text', at='end')
    app.inp.key('del')
    assert lines(note) == ['textitem']


def test_G8_a_click_on_a_box_checks_it_and_leaves_the_cursor(write, app):
    note = write('- [ ] task\nother\n')
    note.body.click_text('other', at='end')
    caret = note.body.caret()
    note.body.click_at(0)
    assert lines(note)[0] == '☑ task'
    assert note.body.caret() == caret
    note.body.click_at(0)
    assert lines(note)[0] == '☐ task'


def test_G9_ctrl_enter_checks_the_to_dos_on_the_selected_lines(write, app):
    note = write('- [ ] a\n- [ ] b\n- [ ] c\n')
    body = note.body
    text = body.text()
    app.inp.drag(body.point_at(text.index('a')),
                 body.point_at(text.index('b'), 'right'))
    app.inp.key('ctrl+enter')
    assert lines(note) == ['☑ a', '☑ b', '☐ c']


def test_G10_a_click_on_a_bullet_puts_the_cursor_at_the_items_start(write, app):
    note = write('top\n- item\n')
    text = note.body.text()
    note.body.click_at(text.index('•'))
    assert note.body.caret() == text.index('item')


def test_G11_home_stays_at_the_items_start_and_shift_home_twice_takes_the_marker(write, app):
    note = write('top\n- item\n')
    text = note.body.text()
    note.body.click_text('item', at='end')
    app.inp.key('home')
    assert note.body.caret() == text.index('item')
    app.inp.key('end')
    app.inp.key('shift+home')
    assert note.body.selection() == (text.index('item'), text.index('item') + 4)
    app.inp.key('shift+home')
    assert note.body.selection() == (text.index('•'), text.index('item') + 4)


def test_G12_shift_left_from_an_item_takes_the_marker_then_the_line_break(write, app):
    note = write('top\n- item\n')
    text = note.body.text()
    note.body.click_text('item', at='start')
    app.inp.key('shift+left')
    assert note.body.selection() == (text.index('•'), text.index('item'))
    app.inp.key('shift+left')
    assert note.body.selection() == (text.index('\n'), text.index('item'))
    app.inp.key('shift+right')
    assert note.body.selection() == (text.index('•'), text.index('item'))


def test_G13_left_from_an_items_start_goes_to_the_line_before(write, app):
    note = write('top\n- item\n')
    note.body.click_text('item', at='start')
    app.inp.key('left')
    assert note.body.caret() == note.body.text().index('\n')


def test_G14_bold_over_list_lines_leaves_the_markers_alone(write, app):
    note = write('- a\n- b\n')
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+b')
    assert note.body.formats('a') == {'bold'}
    assert note.body.formats('•') == set()


def test_G15_bullets_do_not_apply_to_a_code_block(write, app):
    note = write('```\nls\n```\n')
    note.body.click_text('ls', at='end')
    app.inp.key('ctrl+8')
    settle(0.3)
    assert '•' not in note.body.text()
    assert note.body.formats('ls') == {'code'}


def test_G17_a_list_indented_by_spaces_in_an_older_note_gets_tabs(app):
    app.write_notes([{'id': 'n', 'title': 'old', 'x': 100, 'y': 80,
                      'w': 500, 'h': 400,
                      'text': '• top\n    • nested\n        • deeper',
                      'bold_ranges': [[12, 18]]}])
    app.start()
    note = app.note('old')
    assert lines(note) == ['• top', '\t• nested', '\t\t• deeper']
    assert note.body.formats('nested') == {'bold'}


def test_G18_formats_on_markers_in_an_older_note_are_taken_off(app):
    app.write_notes([{'id': 'n', 'title': 'old', 'x': 100, 'y': 80,
                      'w': 500, 'h': 400, 'text': '• item',
                      'bold_ranges': [[0, 6]]}])
    app.start()
    note = app.note('old')
    assert note.body.formats('•') == set()
    assert note.body.formats('item') == {'bold'}


def test_H1_H2_a_quote_continues_on_enter_and_ends_on_an_empty_line(note, app):
    app.inp.type('> one\ntwo\n\nplain')
    assert lines(note) == ['▍ one', '▍ two', 'plain']


def test_G12b_a_mouse_selection_takes_a_marker_it_reaches_over(write, app):
    note = write('top\n- item\n')
    body = note.body
    text = body.text()
    app.inp.drag(body.point_at(text.index('item') + 3, 'right'),
                 body.point_at(text.index('•')))
    assert note.body.selection() == (text.index('•'), text.index('item') + 4)


def test_G12c_selecting_right_toward_an_item_takes_the_break_then_the_marker(write, app):
    note = write('top\n- item\n')
    text = note.body.text()
    note.body.click_text('top', at='end')
    app.inp.key('shift+right')
    assert note.body.selection() == (3, 4)
    app.inp.key('shift+right')
    assert note.body.selection() == (3, text.index('item'))
