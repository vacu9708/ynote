"""N. Clipboard, O. undo and redo, P. search: see BEHAVIORS.md."""
from tests.e2e.driver import (
    TextArea, clipboard_text, find_all, name, role, set_clipboard, settle,
    wait_until)


def lines(note):
    return note.body.text().rstrip('\n').split('\n')


def copy_all(note, app):
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+c')
    return wait_until(clipboard_text)


def test_N1_copied_text_goes_out_as_markdown(write, app):
    md = ('# Title\n\nsee `ls` and **bold**\n\n- item\n  - [ ] task\n\n'
          '> quote\n\n---\n\n```\nls -l\n```')
    note = write(md + '\n')
    out = copy_all(note, app)
    for part in ('# Title', '`ls`', '**bold**', '- item', '  - [ ] task',
                 '> quote', '---', '```\nls -l\n```'):
        assert part in out, (part, out)


def test_N2_code_alone_is_copied_without_fences(write, app):
    note = write('```\nsudo apt update\n```\n')
    note.body.click_text('update', at='middle', count=2)
    app.inp.key('ctrl+c')
    assert wait_until(clipboard_text) == 'sudo apt update'


def test_N3_a_paste_between_notes_keeps_formats_tables_exactly(write, app):
    note = write('**b** `c`\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n')
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+c')
    settle(0.3)
    app.inp.key('ctrl+end')
    app.inp.key('enter')
    app.inp.key('ctrl+v')
    settle(0.8)
    assert len(note.tables()) == 2
    assert note.body.formats('b', occurrence=1) == {'bold'}


def test_N4_once_another_app_takes_the_clipboard_its_text_is_pasted(write, app):
    note = write('**bold**\n')
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+c')
    settle(0.3)
    set_clipboard('plain words')
    app.inp.key('ctrl+end')
    app.inp.key('ctrl+v')
    settle(0.5)
    assert 'plain words' in note.body.text()


def test_N5_pasted_markdown_keeps_its_formats_and_links(write, app):
    note = write('**b** and [site](https://example.com)\n')
    assert note.body.formats('b') == {'bold'}
    assert note.body.text().startswith('b and site (https://example.com)')


def test_N6_a_list_pasted_after_text_starts_its_own_line(write, app):
    note = write('text\n')
    note.body.click_text('text', at='end')
    set_clipboard('- item')
    app.inp.key('ctrl+v')
    settle(0.5)
    assert lines(note)[:2] == ['text', '• item']


def test_N7_ctrl_shift_v_pastes_the_text_alone(write, app):
    note = write('x\n')
    note.body.click_text('x', at='end')
    set_clipboard(' **raw** `t`')
    app.inp.key('ctrl+shift+v')
    settle(0.5)
    assert '**raw** `t`' in note.body.text()


def test_N8_cut_and_paste_brings_a_table_back(write, app):
    note = write('a\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\nz\n')
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+x')
    wait_until(lambda: not note.tables(), what='the cut')
    app.inp.key('ctrl+v')
    wait_until(lambda: note.tables(), what='the table back')


def test_N10_names_with_underscores_and_lone_stars_stay_text(write, app):
    note = write('my_var_name and 2 * 3\n')
    assert note.body.text().startswith('my_var_name and 2 * 3')
    assert note.body.formats('var') == set()


def test_O1_undo_and_redo(note, app):
    app.inp.type('one')
    settle(1.0)
    app.inp.type(' two')
    settle(1.0)
    app.inp.key('ctrl+z')
    wait_until(lambda: note.body.text().rstrip() == 'one', what='undo')
    app.inp.key('ctrl+shift+z')
    wait_until(lambda: note.body.text().rstrip() == 'one two', what='redo')


def test_P1_search_lists_matches_in_every_note_and_opens_one(app):
    app.write_notes([
        {'id': 'a', 'title': 'first', 'x': 100, 'y': 80, 'w': 500, 'h': 400,
         'text': 'nothing here'},
        {'id': 'b', 'title': 'second', 'x': 650, 'y': 80, 'w': 500, 'h': 400,
         'text': 'the needle is here', 'hidden': True}])
    app.start()
    first = app.note('first')
    first.body.click()
    first.search('NEEDLE')
    app.inp.key('enter')
    second = app.note('second')
    text = second.body.text()
    wait_until(lambda: second.body.selection() == (
        text.index('needle'), text.index('needle') + 6), what='the match')


def test_P5_the_arrows_pick_a_match_and_keep_the_cursor_in_the_entry(app):
    app.write_notes([
        {'id': 'a', 'title': 'one', 'x': 100, 'y': 80, 'w': 500, 'h': 400,
         'text': 'apple\napple pie'},
        {'id': 'b', 'title': 'two', 'x': 650, 'y': 80, 'w': 500, 'h': 400,
         'text': 'apple tree'}])
    app.start()
    one = app.note('one')
    one.body.click()
    one.search('apple')
    app.inp.key('down')
    app.inp.key('down')
    app.inp.type('s')
    settle(0.3)
    entry = TextArea(find_all(one.frame, lambda a: role(a) == 'text'
                              and name(a) == 'Search')[0], app.inp)
    assert entry.focused() and entry.text() == 'apples'
