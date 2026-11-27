"""E. Bold, heading, and inline code: see BEHAVIORS.md."""
from tests.e2e.driver import clipboard_text, settle, wait_until

PAD = ' '


def plain(text):
    """The text without the padding inline code has at its ends."""
    return text.replace(PAD, '')


def test_E1_ctrl_b_bolds_a_selection_and_without_one_types_bold(write, app):
    note = write('make this bold\n')
    body = note.body
    text = body.text()
    i = text.index('this')
    app.inp.drag(body.point_at(i), body.point_at(i + 3, 'right'))
    app.inp.key('ctrl+b')
    assert body.formats('this') == {'bold'}
    assert body.formats('make') == set()
    body.click_text('bold', at='end')
    app.inp.key('end')
    app.inp.type(' ')
    app.inp.key('ctrl+b')
    app.inp.type('strong')
    assert body.formats('strong') == {'bold'}


def test_E2_typing_right_after_bold_text_is_bold(write, app):
    note = write('a **bold** word\n')
    note.body.click_text('bold', at='end')
    app.inp.type('er')
    assert note.body.formats('bolder') == {'bold'}


def test_E3_at_the_start_of_a_line_the_text_after_the_cursor_counts(write, app):
    note = write('top\n**bold** start\n')
    note.body.click_text('bold', at='start')
    app.inp.key('home')
    app.inp.type('X')
    assert note.body.formats('Xbold') == {'bold'}


def test_E4_at_the_start_of_a_list_item_or_quote_the_text_after_it_counts(write, app):
    note = write('top\n- **item** x\n> **quote** z\n')
    for word in ('item', 'quote'):
        note.body.click_text(word, at='start')
        app.inp.type('Z')
        assert note.body.formats('Z' + word) == {'bold'}, word


def test_E5_at_the_left_edge_of_bold_within_a_line_typing_is_plain(write, app):
    note = write('mid **bold** text\n')
    note.body.click_text('bold', at='start')
    app.inp.type('Q')
    assert note.body.formats('Q') == set()
    assert note.body.formats('bold') == {'bold'}


def test_E7_bold_turned_off_in_its_middle_types_plain_text(write, app):
    note = write('**boldtext**\n')
    note.body.click_text('text', at='start')
    app.inp.key('ctrl+b')
    app.inp.type('plain')
    body = note.body
    assert body.formats('bold') == {'bold'}
    assert body.formats('plain') == set()
    assert body.formats('text') == {'bold'}


def test_E8_enter_turns_every_format_off(write, app):
    note = write('**bold** and `code`\n')
    note.body.click_text('bold', at='end')
    app.inp.key('enter')
    app.inp.type('next')
    assert note.body.formats('next') == set()


def test_E9_ctrl_h_makes_the_line_a_heading_and_again_takes_it_away(write, app):
    note = write('Title\nbody\n')
    note.body.click_text('Title', at='middle')
    app.inp.key('ctrl+h')
    assert 'heading' in note.body.formats('Title')
    assert note.body.formats('body') == set()
    app.inp.key('ctrl+h')
    assert 'heading' not in note.body.formats('Title')


def test_E10_heading_on_an_empty_line_waits_for_the_text_typed_next(note, app):
    app.inp.key('ctrl+h')
    app.inp.type('Plan')
    assert 'heading' in note.body.formats('Plan')
    app.inp.key('enter')
    app.inp.key('ctrl+h')
    app.inp.key('ctrl+h')
    app.inp.type('body')
    assert 'heading' not in note.body.formats('body')


def test_E11_a_list_item_does_not_become_a_heading(write, app):
    note = write('- item\n')
    note.body.click_text('item', at='middle')
    app.inp.key('ctrl+h')
    assert 'heading' not in note.body.formats('item')


def test_E12_enter_at_the_end_of_a_heading_starts_a_plain_line(write, app):
    note = write('# Title\n')
    note.body.click_text('Title', at='end')
    app.inp.key('enter')
    app.inp.type('plain')
    assert note.body.formats('plain') == set()


def test_E13_bold_in_a_heading_is_off_and_turning_it_on_is_bolder(write, app):
    note = write('# Heading words\n')
    body = note.body
    assert body.formats('Heading') == {'heading', 'bold'}
    text = body.text()
    i = text.index('words')
    app.inp.drag(body.point_at(i), body.point_at(i + 4, 'right'))
    app.inp.key('ctrl+b')
    wait_until(lambda: 'bolder' in note.body.formats('words'),
               what='bolder words')
    assert 'bolder' not in note.body.formats('Heading')


def test_E14_a_line_made_a_heading_keeps_its_bold(write, app):
    note = write('**bold** line\n')
    note.body.click_text('line', at='middle')
    app.inp.key('ctrl+h')
    assert 'bolder' in note.body.formats('bold')
    app.inp.key('ctrl+h')
    assert note.body.formats('bold') == {'bold'}


def test_E16_ctrl_e_makes_a_selection_inline_code_and_types_code(write, app):
    note = write('run ls now\n')
    body = note.body
    i = body.text().index('ls')
    app.inp.drag(body.point_at(i), body.point_at(i + 1, 'right'))
    app.inp.key('ctrl+e')
    assert note.body.formats('ls') == {'code'}
    note.body.click_text('now', at='end')
    app.inp.type(' ')
    app.inp.key('ctrl+e')
    app.inp.type('pwd')
    assert note.body.formats('pwd') == {'code'}


def test_E17_inline_code_has_padding_that_copying_leaves_out(write, app):
    note = write('see `ls -l` here\n')
    text = note.body.text()
    assert PAD + 'ls -l' + PAD in text
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+c')
    assert wait_until(clipboard_text).strip() == 'see `ls -l` here'


def test_E18_typing_after_inline_code_is_plain_and_inside_it_code(write, app):
    note = write('`code` end\n')
    note.body.click_text('code', at='end')
    app.inp.key('right')
    app.inp.type('X')
    assert note.body.formats('X') == set()
    note.body.click_text('od', at='start')
    app.inp.type('Y')
    assert note.body.formats('cYode') == {'code'}


def test_E20_backspace_after_inline_code_takes_its_last_character(write, app):
    note = write('`abc` end\n')
    body = note.body
    text = body.text()
    # Right after the code, past its padding.
    body.click_at(text.index(' end'), 'left')
    app.inp.key('backspace')
    assert plain(note.body.text()).startswith('ab end')


def test_E21_deleting_all_of_inline_code_takes_its_padding_too(write, app):
    note = write('x `a` y\n')
    note.body.click_text('a', at='end')
    app.inp.key('backspace')
    settle(0.3)
    assert PAD not in note.body.text()
    assert note.body.text().startswith('x  y')


def test_E24_enter_does_not_continue_inline_code(write, app):
    note = write('`code`\n')
    note.body.click_text('code', at='end')
    app.inp.key('enter')
    app.inp.type('next')
    assert note.body.formats('next') == set()


def test_E6_ctrl_b_on_a_partly_bold_selection_makes_all_of_it_bold(write, app):
    note = write('**bold** plain\n')
    body = note.body
    text = body.text()
    app.inp.drag(body.point_at(text.index('bold')),
                 body.point_at(text.index('plain') + 4, 'right'))
    app.inp.key('ctrl+b')
    assert note.body.formats('bold plain') == {'bold'}
    app.inp.key('ctrl+b')
    assert note.body.formats('bold') == set()


def test_E22_shift_right_into_code_skips_its_padding(write, app):
    note = write('ab `cd` ef\n')
    body = note.body
    text = body.text()
    body.click_at(text.index(' ' + PAD) + 1, 'left')
    app.inp.key('shift+right')
    start, end = note.body.selection()
    assert text[start:end].replace(PAD, '') == 'c'


def test_E23_code_turned_off_in_its_middle_splits_it(write, app):
    note = write('`abcdef`\n')
    note.body.click_text('cd', at='end')
    app.inp.key('ctrl+e')
    app.inp.type('X')
    body = note.body
    assert body.formats('abcd') == {'code'}
    assert body.formats('X') == set()
    assert body.formats('ef') == {'code'}
    assert plain(body.text()).startswith('abcdXef')


def test_E9b_heading_applies_to_every_line_a_selection_touches(write, app):
    note = write('# one\ntwo\nthree\n')
    body = note.body
    text = body.text()
    app.inp.drag(body.point_at(text.index('one') + 1),
                 body.point_at(text.index('two') + 1))
    app.inp.key('ctrl+h')
    assert 'heading' in note.body.formats('one')
    assert 'heading' in note.body.formats('two')
    assert 'heading' not in note.body.formats('three')
    app.inp.key('ctrl+h')
    assert 'heading' not in note.body.formats('one')


def test_E19_turning_code_on_or_off_at_its_edge_steps_over_the_padding(write, app):
    note = write('ab `cd` ef\n')
    note.body.click_text('cd', at='end')
    app.inp.key('ctrl+e')
    app.inp.type('X')
    assert note.body.formats('X') == set()
    assert plain(note.body.text()).startswith('ab cdX ef')


def test_E20b_backspace_and_delete_beside_the_padding_skip_it(write, app):
    note = write('ab `cd` ef\n')
    body = note.body
    text = body.text()
    # Right before the code's first character, after its padding.
    body.click_text('cd', at='start')
    app.inp.key('backspace')
    assert plain(note.body.text()).startswith('abcd ef')
    note.body.click_text('cd', at='end')
    app.inp.key('del')
    assert plain(note.body.text()).startswith('abcdef')
    del text
