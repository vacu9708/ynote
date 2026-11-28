"""M. Expands: see BEHAVIORS.md."""
from tests.e2e.driver import clipboard_text, settle, wait_until

# An empty line after the expand: the blank line right after </details> is
# only Markdown's, which pasting leaves out.
FOLDED = ('top\n\n<details>\n<summary>Fold</summary>\n\ninside text\n\n'
          '</details>\n\n\nbottom\n')
OPEN = FOLDED.replace('<details>', '<details open>')


def lines(note):
    return note.body.text().rstrip('\n').split('\n')


def test_M1_insert_expand_puts_the_selected_lines_in_it(write, app):
    note = write('one\ntwo\nthree\n')
    body = note.body
    text = body.text()
    app.inp.drag(body.point_at(text.index('one')),
                 body.point_at(text.index('two') + 2, 'right'))
    note.press('Insert')
    note.choose('Expand')
    settle(0.5)
    text = note.body.text()
    assert text.index('one') > text.index('▾')
    assert 'three' in text


def test_M2_ctrl_enter_on_the_title_folds_and_opens(write, app):
    note = write(OPEN)
    assert 'inside text' in note.body.text()
    note.body.click_text('Fold', at='end')
    app.inp.key('ctrl+enter')
    wait_until(lambda: 'inside text' not in note.body.text(), what='folding')
    app.inp.key('ctrl+enter')
    wait_until(lambda: 'inside text' in note.body.text(), what='opening')


def test_M2b_a_click_on_the_arrow_folds_and_opens(write, app):
    note = write(OPEN)
    note.body.click_at(note.body.text().index('▾'))
    wait_until(lambda: 'inside text' not in note.body.text(), what='folding')
    note.body.click_at(note.body.text().index('▸'))
    wait_until(lambda: 'inside text' in note.body.text(), what='opening')


def test_M2c_folding_moves_a_cursor_inside_to_the_title(write, app):
    note = write(OPEN)
    note.body.click_text('inside', at='end')
    note.body.click_at(note.body.text().index('▾'))
    settle(0.3)
    app.inp.type('X')
    assert 'FoldX' in note.body.text().replace('​', '')


def test_M3_an_expand_holds_code_lists_and_tables(write, app):
    note = write('<details open>\n<summary>All</summary>\n\n- item\n\n```\nls\n```\n\n'
                 '| A | B |\n| --- | --- |\n| 1 | 2 |\n\n</details>\n')
    text = note.body.text()
    assert '• item' in text
    assert note.body.formats('ls') == {'code'}
    assert note.tables()


def test_M4_enter_on_the_empty_last_line_goes_on_below_the_expand(write, app):
    note = write(OPEN)
    note.body.click_text('inside text', at='end')
    app.inp.key('enter')
    app.inp.key('enter')
    app.inp.type('out')
    note.body.click_at(note.body.text().index('▾'))
    wait_until(lambda: 'inside text' not in note.body.text(), what='folding')
    assert 'out' in note.body.text()


def test_M8_a_search_match_in_a_folded_expand_shows_it_until_search_closes(write, app):
    note = write(FOLDED)
    assert 'inside text' not in note.body.text()
    note.search('inside')
    wait_until(lambda: 'inside text' in note.body.text(), what='showing it open')
    app.inp.key('esc')
    wait_until(lambda: 'inside text' not in note.body.text(), what='folding again')


def test_M9_an_expand_copies_as_details(write, app):
    note = write(OPEN)
    note.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('ctrl+c')
    md = wait_until(clipboard_text)
    assert '<details open>' in md and '<summary>Fold</summary>' in md
    assert '</details>' in md


def test_M10_the_cursor_does_not_rest_on_an_expands_end(write, app):
    note = write(OPEN)
    note.body.click_text('inside text', at='end')
    app.inp.key('down')
    app.inp.type('Y')
    # Past the end line, onto the blank line the Markdown left after it.
    assert 'inside text\n\nY\nbottom' in note.body.text()


def test_M1b_an_expand_inserted_on_the_last_line_leaves_a_line_after_it(note, app):
    note.press('Insert')
    note.choose('Expand')
    app.inp.type('title')
    app.inp.key('ctrl+end')
    app.inp.type('after')
    lines = note.body.text().rstrip('\n').split('\n')
    assert lines[0].endswith('title') and lines[-1] == 'after'
    note.body.click_at(note.body.text().index('▾'))
    wait_until(lambda: 'after' in note.body.text(), what='after stays shown')


def test_M5_backspace_after_an_expand_takes_an_empty_line_into_it(write, app):
    note = write(OPEN)
    note.body.click_text('bottom', at='start')
    app.inp.key('up')
    app.inp.key('backspace')
    assert 'inside text' in note.body.text()
    assert note.body.text().count('\n\n') <= OPEN.count('\n\n')


def test_M5b_delete_never_joins_a_line_to_an_expands_end(write, app):
    note = write(OPEN)
    note.body.click_text('inside text', at='end')
    app.inp.key('del')
    app.inp.key('del')
    note.body.click_at(note.body.text().index('▾'))
    wait_until(lambda: 'inside text' not in note.body.text(), what='folding')
    assert 'bottom' in note.body.text()


def test_M6_backspace_at_the_titles_start_keeps_the_content(write, app):
    note = write(OPEN)
    note.body.click_text('Fold', at='start')
    app.inp.key('backspace')
    assert 'inside text' in note.body.text()


def test_M7_an_expand_never_ended_gets_an_end(app):
    app.write_notes([{'id': 'n', 'title': 'old', 'x': 100, 'y': 80,
                      'w': 500, 'h': 400, 'text': '▾ Fold\ninside\nmore'}])
    app.start()
    n = app.note('old')
    n.body.click_at(n.body.text().index('▾'))
    wait_until(lambda: 'inside' not in n.body.text(), what='folding')
