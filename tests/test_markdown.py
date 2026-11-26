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
