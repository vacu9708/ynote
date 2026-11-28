"""Markdown on the clipboard: a note's text and formats to Markdown and back."""
from ynote.config import CODE_ANCHOR, CODE_PAD_CHAR
from ynote.markdown import fit_between, from_markdown, is_all_code, to_markdown

PAD = CODE_PAD_CHAR


def state(text, **ranges):
    return {'text': text, 'bold': ranges.get('bold', []),
            'heading': ranges.get('heading', []),
            'code': ranges.get('code', []),
            'backtick': ranges.get('backtick', []), 'images': []}


def spans(st, key):
    return [st['text'][s:e] for s, e in st[key]]


def test_formats_become_markdown():
    text = f'Title\nsee {PAD}ls -l{PAD} and bold'
    st = state(text, heading=[[0, 5]], backtick=[[10, 17]], bold=[[22, 26]])

    assert to_markdown(st) == '# Title\nsee `ls -l` and **bold**'


def test_list_items_become_markdown_items_by_level():
    st = state('• one\n\t☐ todo\n\t\t☑ done')

    assert to_markdown(st) == '- one\n  - [ ] todo\n    - [x] done'


def test_code_block_lines_are_fenced_and_keep_empty_lines():
    st = state(f'run:\necho a\n{CODE_ANCHOR}\nls\nend',
               code=[[5, 11], [12, 13], [14, 16]])

    assert to_markdown(st) == 'run:\n```\necho a\n\nls\n```\nend'


def test_a_divider_under_text_gets_a_blank_line_so_it_is_not_a_heading():
    assert to_markdown(state('text\n---')) == 'text\n\n---'


def test_bold_keeps_its_spaces_outside_the_stars():
    assert to_markdown(state('a bold b', bold=[[1, 7]])) == 'a **bold** b'


def test_inline_code_with_a_backtick_gets_a_longer_fence():
    text = f'{PAD}a`b{PAD}'
    assert to_markdown(state(text, backtick=[[0, len(text)]])) == '``a`b``'


def test_code_alone_is_copied_as_it_is():
    assert is_all_code(state(f'echo a\n{CODE_ANCHOR}', code=[[0, 6], [7, 8]]))
    assert is_all_code(state(f'{PAD}ls{PAD}', backtick=[[0, 4]]))
    assert not is_all_code(state(f'run {PAD}ls{PAD}', backtick=[[4, 8]]))


def test_markdown_comes_back_with_its_formats():
    st = from_markdown('# Title\nsee `ls -l` and **bold**')

    assert st['text'] == f'Title\nsee {PAD}ls -l{PAD} and bold'
    assert spans(st, 'heading') == ['Title']
    assert spans(st, 'backtick') == [f'{PAD}ls -l{PAD}']
    assert spans(st, 'bold') == ['bold']


def test_bold_in_a_heading_goes_out_and_comes_back():
    st = state('Big Title', heading=[[0, 9]], bold=[[4, 9]])

    md = to_markdown(st)
    back = from_markdown(md)

    assert md == '# Big **Title**'
    assert spans(back, 'heading') == ['Big Title']
    assert spans(back, 'bold') == ['Title']


def test_markdown_lists_come_back_as_items_at_their_levels():
    # Nested by two spaces as GitHub writes them, or by four.
    for step in ('  ', '    '):
        md = f'- one\n{step}- [ ] todo\n{step * 2}* [x] done\n- two'
        assert from_markdown(md)['text'] == \
            '• one\n\t☐ todo\n\t\t☑ done\n• two'


def test_a_fenced_block_comes_back_as_code_lines_without_its_fences():
    st = from_markdown('run:\n```bash\n# a comment\n\nls\n```\nend')

    assert st['text'] == f'run:\n# a comment\n{CODE_ANCHOR}\nls\nend'
    assert spans(st, 'code') == ['# a comment', CODE_ANCHOR, 'ls']
    assert spans(st, 'heading') == []


def test_a_divider_links_and_escapes():
    st = from_markdown('***\n[docs](https://x.io) and <https://y.io>\n\\*not\\*')

    assert st['text'] == '---\ndocs (https://x.io) and https://y.io\n*not*'


def test_names_with_underscores_and_lone_stars_stay_text():
    for text in ('call __init__ now', '2 * 3 * 4', 'f(*args, **kwargs)'):
        st = from_markdown(text)
        assert st['text'] == text and st['bold'] == []


def test_a_round_trip_keeps_the_note():
    text = f'Title\n• a {PAD}x{PAD}\n\t☐ b\n---\necho\nend'
    st = state(text, heading=[[0, 5]], backtick=[[10, 13]],
               bold=[[8, 9]], code=[[23, 27]])

    back = from_markdown(to_markdown(st))

    # The blank line that keeps --- from making a heading is the only change.
    assert back['text'] == text.replace('\n---', '\n\n---')
    assert spans(back, 'bold') == ['a']
    assert spans(back, 'code') == ['echo']


def test_a_list_or_code_pasted_after_text_starts_a_line_of_its_own():
    st = from_markdown('- item')

    assert fit_between(st, 'text ', '')['text'] == '\n• item'
    assert fit_between(st, '  ', 'rest')['text'] == '• item'

    code = from_markdown('```\nls\n```')
    fitted = fit_between(code, 'x', 'y')
    assert fitted['text'] == '\nls\n'
    assert spans(fitted, 'code') == ['ls']


TABLE_MARKER = '⁣'


def test_a_table_becomes_a_markdown_table_with_its_header():
    st = state(f'{TABLE_MARKER}Name\tAge\n{TABLE_MARKER}a|b\t3',
               bold=[[1, 5]])

    assert to_markdown(st) == ('| **Name** | Age |\n| --- | --- |\n'
                               '| a\\|b | 3 |')


def test_text_right_under_a_table_gets_a_blank_line():
    st = state(f'{TABLE_MARKER}a\tb\nafter')

    assert to_markdown(st) == '| a | b |\n| --- | --- |\n\nafter'


def test_a_markdown_table_becomes_rows_of_tab_separated_cells():
    st = from_markdown('| a | b |\n|:--|--:|\n| `x\\|y` | **z** |\n| only |')

    assert st['text'] == (f'{TABLE_MARKER}a\tb\n'
                          f'{TABLE_MARKER}{PAD}x|y{PAD}\tz\n'
                          f'{TABLE_MARKER}only\t')
    assert spans(st, 'bold') == ['z']
    assert spans(st, 'backtick') == [f'{PAD}x|y{PAD}']


def test_pipes_without_a_delimiter_row_are_not_a_table():
    assert from_markdown('a | b\nc | d')['text'] == 'a | b\nc | d'


def test_a_table_ends_at_a_line_without_a_pipe():
    st = from_markdown('a | b\n--- | ---\n1 | 2\n\ntext')

    assert st['text'] == f'{TABLE_MARKER}a\tb\n{TABLE_MARKER}1\t2\n\ntext'


def test_a_pasted_table_starts_and_ends_a_line_of_its_own():
    st = fit_between(from_markdown('| a |\n| - |'), 'text ', ' more')

    assert st['text'] == f'\n{TABLE_MARKER}a\n'


QUOTE = '\u258d '


def test_a_quote_becomes_a_markdown_quote_and_back():
    st = state(f'{QUOTE}stay calm\nthen')

    assert to_markdown(st) == '> stay calm\nthen'
    assert from_markdown('> stay **calm**\n>\nthen')['text'] == (
        f'{QUOTE}stay calm\n{QUOTE}\nthen')


OPEN, END = '▾ ', '⁤'


def test_a_section_becomes_details_and_back_without_extra_lines():
    text = f'{OPEN}Test info\nrun it\n{END}\nafter'
    md = to_markdown(state(text))

    # A blank line after </details> too, as Markdown after HTML needs.
    assert md == ('<details open>\n<summary>Test info</summary>\n\nrun it\n\n'
                  '</details>\n\nafter')
    assert from_markdown(md)['text'] == text


def test_a_table_of_editors_becomes_a_markdown_table_with_br_line_breaks():
    def cell(text, **ranges):
        return state(text, **ranges)
    st = dict(state('Intro\n￼\nafter'), tables=[{'offset': 6, 'rows': [
        [cell('Name'), cell('Notes')],
        [cell('Kim'), cell('first\nsecond|x', bold=[[0, 5]])]]}])

    assert to_markdown(st) == ('Intro\n\n| Name | Notes |\n| --- | --- |\n'
                               '| Kim | **first**<br>second\\|x |\n\nafter')


def test_br_in_a_pasted_table_cell_is_a_line_break_to_come():
    st = from_markdown('| a |\n| - |\n| one<br>two |')

    assert st['text'] == f'{TABLE_MARKER}a\n{TABLE_MARKER}one two'
