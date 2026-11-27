"""I. Code blocks, and F. Markdown typed into a note: see BEHAVIORS.md."""
from tests.e2e.driver import clipboard_text, set_clipboard, settle, wait_until


def lines(note):
    return note.body.text().rstrip('\n').split('\n')


def test_I1_three_backticks_on_an_empty_line_start_a_code_block(note, app):
    app.inp.type('```')
    app.inp.key('enter')
    app.inp.type('ls -l')
    assert note.body.formats('ls -l') == {'code'}


def test_I1b_three_backticks_after_text_stay_text(note, app):
    app.inp.type('see ```')
    assert note.body.text().startswith('see ```')
    assert note.body.formats('see') == set()


def test_I1c_insert_code_block_from_the_menu(note, app):
    app.inp.type('pwd')
    note.press('Insert')
    note.choose('Code block')
    assert note.body.formats('pwd') == {'code'}


def test_I3_a_double_click_in_a_code_block_selects_its_line(write, app):
    note = write('```\ncd /tmp\nls -l\n```\nafter\n')
    text = note.body.text()
    note.body.click_text('tmp', at='middle', count=2)
    start = text.index('cd /tmp')
    assert note.body.selection() == (start, start + len('cd /tmp'))


def test_I3b_a_triple_click_in_a_code_block_selects_the_block(write, app):
    note = write('```\ncd /tmp\nls -l\n```\nafter\n')
    text = note.body.text()
    note.body.click_text('tmp', at='middle', count=3)
    assert note.body.selection() == (text.index('cd /tmp'),
                                     text.index('ls -l') + 5)


def test_I4_empty_lines_in_a_code_block_stay_in_it(write, app):
    note = write('```\none\n\nthree\n```\n')
    assert note.body.formats('one') == {'code'}
    assert note.body.formats('three') == {'code'}
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+c')
    # The selection takes the line break after the block too.
    assert wait_until(clipboard_text).rstrip('\n') == 'one\n\nthree'


def test_I6_text_pasted_into_code_is_taken_as_it_is(write, app):
    note = write('```\nx\n```\n')
    note.body.click_text('x', at='end')
    set_clipboard('**not bold** # no\n- no list')
    app.inp.key('ctrl+v')
    settle(0.5)
    assert '**not bold** # no\n- no list' in note.body.text()
    assert note.body.formats('not bold') == {'code'}


def test_I7_lines_made_a_code_block_show_their_markdown(write, app):
    note = write('# Title\n**bold** and `code`\n- item\n')
    note.body.click()
    app.inp.key('ctrl+a')
    note.press('Insert')
    note.choose('Code block')
    settle(0.5)
    assert lines(note)[:3] == ['# Title', '**bold** and `code`', '- item']
    assert note.body.formats('Title') == {'code'}
    app.inp.key('ctrl+z')
    settle(0.8)
    assert lines(note)[:3] == ['Title', 'bold and  code ', '• item']


def test_I9_code_made_plain_again_keeps_the_markdown_as_text(write, app):
    note = write('```\n# Title\n```\n')
    note.body.click_text('Title', at='end')
    note.press('Insert')
    note.choose('Code block')
    settle(0.4)
    assert lines(note)[0] == '# Title'
    assert note.body.formats('Title') == set()


def test_F1_typed_double_asterisks_make_bold_but_not_around_spaces(note, app):
    app.inp.type('a **word** and ** not ** and *.txt')
    text = note.body.text()
    assert 'a word and' in text
    assert note.body.formats('word') == {'bold'}
    assert '** not **' in text and '*.txt' in text


def test_F2_typed_backticks_make_inline_code_with_the_cursor_after(note, app):
    app.inp.type('run `ls` then')
    assert note.body.formats('ls') == {'code'}
    assert note.body.formats('then') == set()


def test_F3_backticks_on_two_lines_do_not_make_code(note, app):
    app.inp.type('a `b\nc` d')
    assert lines(note) == ['a `b', 'c` d']


def test_F4_hash_space_makes_a_heading(note, app):
    app.inp.type('# Head\nx # not')
    assert 'heading' in note.body.formats('Head')
    assert lines(note)[1] == 'x # not'


def test_F4b_hash_space_before_text_makes_its_line_a_heading(write, app):
    note = write('Title\n')
    note.body.click_text('Title', at='start')
    app.inp.type('# ')
    assert 'heading' in note.body.formats('Title')
    assert lines(note)[0] == 'Title'


def test_F6_dash_and_brackets_start_lists_but_not_in_code(note, app):
    app.inp.type('- [ ] task\n')
    assert lines(note)[0] == '☐ task'
    app.inp.key('enter')
    app.inp.type('```')
    app.inp.key('enter')
    app.inp.type('- [ ] x')
    assert '- [ ] x' in note.body.text()


def test_F8_three_dashes_make_a_divider_the_cursor_skips(note, app):
    app.inp.type('above\n---\nbelow')
    app.inp.key('ctrl+home')
    app.inp.key('end')
    app.inp.key('down')
    app.inp.type('X')
    assert lines(note) == ['above', '---', 'Xbelow']


def test_F9_menus_show_each_items_shortcut_and_markdown(note, app):
    note.press('Insert')
    labels = note.menu_items()
    for label in ('Bullet list', 'Checklist', 'Quote', 'Code block',
                  'Divider', 'Expand', 'Table', 'Image…'):
        assert label in labels, labels
    app.inp.key('esc')
    note.press('Format')
    labels = note.menu_items()
    for label in ('Bold', 'Heading', 'Inline code'):
        assert label in labels, labels
    app.inp.key('esc')


def test_I5_text_typed_over_a_selection_in_a_code_block_stays_code(write, app):
    note = write('```\nold text\n```\n')
    note.body.click_text('old', at='middle', count=2)
    app.inp.type('new')
    assert note.body.formats('new') == {'code'}


def test_I8_a_line_with_an_image_is_left_out_of_a_new_code_block(note, app):
    from tests.e2e.test_misc import put_image_on_clipboard
    app.inp.type('one\n')
    put_image_on_clipboard()
    app.inp.key('ctrl+v')
    wait_until(lambda: note.body.text().count('\n') >= 1, what='the image')
    app.inp.key('ctrl+a')
    note.press('Insert')
    note.choose('Code block')
    assert note.body.formats('one') == {'code'}


def test_I5b_a_middle_line_of_code_typed_over_stays_in_the_block(write, app):
    note = write('```\ncd /tmp\nls -l\npwd\n```\n')
    note.body.click_text('ls', at='middle', count=2)
    app.inp.type('echo hi')
    assert note.body.formats('echo hi') == {'code'}
    assert note.body.formats('pwd') == {'code'}
