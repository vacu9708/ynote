from ynote.config import (
    BULLET_MARKER, CHECKBOX_MARKER, CHECKED_MARKER, CODE_ANCHOR, CODE_PAD_CHAR,
    EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN, IMAGE_ANCHOR, QUOTE_MARKER,
    TABLE_MARKER)
from ynote.convert import doc_text, note_doc


def blocks(text, **ranges):
    note = {'text': text}
    note.update(ranges)
    return note_doc(note)['content']


def t(text, *marks):
    node = {'type': 'text', 'text': text}
    if marks:
        node['marks'] = [{'type': m} for m in marks]
    return node


def p(*content):
    return {'type': 'paragraph', 'content': list(content)} if content else {'type': 'paragraph'}


def test_empty_note_is_one_empty_paragraph():
    assert blocks('') == [p()]


def test_lines_become_paragraphs():
    assert blocks('one\n\ntwo') == [p(t('one')), p(), p(t('two'))]


def test_bold_and_inline_code_become_marks():
    text = 'a bold x' + CODE_PAD_CHAR + 'cmd' + CODE_PAD_CHAR
    assert blocks(text, bold_ranges=[[2, 6]], backtick_ranges=[[8, 13]]) == [
        p(t('a '), t('bold', 'strong'), t(' x'), t('cmd', 'code'))]


def test_bold_inside_code_keeps_both_marks_in_schema_order():
    assert blocks('ab', bold_ranges=[[0, 2]], backtick_ranges=[[0, 2]]) == [
        p(t('ab', 'strong', 'code'))]


def test_heading_line():
    assert blocks('Title\nbody', heading_ranges=[[0, 5]]) == [
        {'type': 'heading', 'content': [t('Title')]}, p(t('body'))]


def test_code_lines_join_into_one_block_with_empty_lines_kept():
    text = 'ls\n' + CODE_ANCHOR + '\n\tpwd\nafter'
    assert blocks(text, code_ranges=[[0, 8]]) == [
        {'type': 'code_block', 'content': [t('ls\n\n\tpwd')]}, p(t('after'))]


def test_a_bullet_in_code_is_code():
    text = BULLET_MARKER + 'x'
    assert blocks(text, code_ranges=[[0, 3]]) == [
        {'type': 'code_block', 'content': [t(text)]}]


def item(checked, *content):
    return {'type': 'list_item', 'attrs': {'checked': checked},
            'content': [p(*content)] if not content or content[0].get('type') == 'text'
            else list(content)}


def test_markers_make_one_list_of_bullets_and_todos():
    text = '\n'.join([BULLET_MARKER + 'a', CHECKBOX_MARKER + 'b',
                      CHECKED_MARKER + 'c'])
    assert blocks(text) == [{'type': 'bullet_list', 'content': [
        item(None, t('a')), item(False, t('b')), item(True, t('c'))]}]


def test_tabs_nest_items_in_the_item_before():
    text = '\n'.join([BULLET_MARKER + 'a', '\t' + BULLET_MARKER + 'b',
                      '\t\t' + CHECKBOX_MARKER + 'c', BULLET_MARKER + 'd'])
    c = {'type': 'list_item', 'attrs': {'checked': False}, 'content': [p(t('c'))]}
    b = {'type': 'list_item', 'attrs': {'checked': None}, 'content': [
        p(t('b')), {'type': 'bullet_list', 'content': [c]}]}
    a = {'type': 'list_item', 'attrs': {'checked': None}, 'content': [
        p(t('a')), {'type': 'bullet_list', 'content': [b]}]}
    assert blocks(text) == [{'type': 'bullet_list', 'content': [
        a, item(None, t('d'))]}]


def test_a_line_between_lists_starts_a_new_list():
    text = '\n'.join([BULLET_MARKER + 'a', 'x', BULLET_MARKER + 'b'])
    result = blocks(text)
    assert [b['type'] for b in result] == ['bullet_list', 'paragraph', 'bullet_list']


def test_quote_lines_make_one_quote():
    text = QUOTE_MARKER + 'one\n' + QUOTE_MARKER + 'two'
    assert blocks(text) == [{'type': 'blockquote', 'content': [
        p(t('one')), p(t('two'))]}]


def test_divider():
    assert blocks('a\n---\nb') == [p(t('a')), {'type': 'horizontal_rule'}, p(t('b'))]


def test_expands_nest_and_keep_folded_state():
    text = '\n'.join([EXPAND_OPEN + 'Outer', 'in', EXPAND_CLOSED + 'Inner',
                      'deep', EXPAND_END, EXPAND_END, 'out'])
    inner = {'type': 'expand', 'attrs': {'open': False}, 'content': [
        {'type': 'expand_title', 'content': [t('Inner')]}, p(t('deep'))]}
    outer = {'type': 'expand', 'attrs': {'open': True}, 'content': [
        {'type': 'expand_title', 'content': [t('Outer')]}, p(t('in')), inner]}
    assert blocks(text) == [outer, p(t('out'))]


def test_an_expand_left_open_is_closed_and_never_empty():
    assert blocks(EXPAND_OPEN) == [{'type': 'expand', 'attrs': {'open': True},
                                    'content': [{'type': 'expand_title'}, p()]}]


def test_an_end_that_ends_nothing_is_dropped():
    assert blocks('a\n' + EXPAND_END) == [p(t('a'))]


def test_images_at_their_anchors():
    text = 'see ' + IMAGE_ANCHOR + '!'
    images = [{'file': 'f.png', 'original_name': 'shot.png', 'offset': 4}]
    assert blocks(text, images=images) == [p(t('see '), {
        'type': 'image', 'attrs': {'file': 'f.png', 'name': 'shot.png'}}, t('!'))]


def test_an_anchor_without_an_image_is_dropped():
    assert blocks('a' + IMAGE_ANCHOR + 'b') == [p(t('ab'))]


def cell(kind, *content):
    return {'type': kind, 'attrs': {'colspan': 1, 'rowspan': 1, 'colwidth': None},
            'content': list(content) or [p()]}


def test_table_with_rich_cells_and_a_header_row():
    tables = [{'offset': 2, 'rows': [
        [{'text': 'Name', 'bold': [[0, 4]]}, {'text': 'State'}],
        [{'text': 'a\nb'}, {'text': 'ok', 'backtick': [[0, 2]]}],
    ]}]
    result = blocks('x\n' + IMAGE_ANCHOR + '\ny', tables=tables)
    assert result == [p(t('x')), {'type': 'table', 'content': [
        {'type': 'table_row', 'content': [
            cell('table_header', p(t('Name', 'strong'))),
            cell('table_header', p(t('State')))]},
        {'type': 'table_row', 'content': [
            cell('table_cell', p(t('a')), p(t('b'))),
            cell('table_cell', p(t('ok', 'code')))]},
    ]}, p(t('y'))]


def test_ragged_table_rows_are_filled_out():
    tables = [{'offset': 0, 'rows': [[{'text': 'a'}, {'text': 'b'}], [{'text': 'c'}]]}]
    table = blocks(IMAGE_ANCHOR, tables=tables)[0]
    assert [len(r['content']) for r in table['content']] == [2, 2]


def test_old_tab_separated_table_rows():
    text = TABLE_MARKER + 'k\tv\n' + TABLE_MARKER + '1\t'
    table = blocks(text)[0]
    assert table['type'] == 'table'
    assert table['content'][0]['content'][0] == cell('table_header', p(t('k')))
    assert table['content'][1]['content'][1] == cell('table_cell', p())


def test_doc_text_for_search():
    text = '\n'.join(['Title', BULLET_MARKER + 'item', 'ls -l'])
    doc = note_doc({'text': text, 'heading_ranges': [[0, 5]],
                    'code_ranges': [[13, 18]]})
    assert doc_text(doc) == 'Title\nitem\nls -l'


def test_doc_text_puts_table_cells_on_one_line():
    tables = [{'offset': 0, 'rows': [[{'text': 'a'}, {'text': 'b\nc'}]]}]
    assert doc_text(note_doc({'text': IMAGE_ANCHOR, 'tables': tables})) == 'a\tb c'


# ---------------------------------------------------------------- state_of

from ynote.convert import state_blocks, state_of  # noqa: E402
from ynote.markdown import from_markdown, to_markdown  # noqa: E402


def roundtrip(text, **ranges):
    note = {'text': text}
    note.update(ranges)
    return state_of(note_doc(note)['content'])


def test_state_of_gives_back_text_and_ranges():
    state = roundtrip('Title\na bold x', heading_ranges=[[0, 5]], bold_ranges=[[8, 12]])
    assert state['text'] == 'Title\na bold x'
    assert state['heading'] == [[0, 5]] and state['bold'] == [[8, 12]]


def test_state_of_lists_quotes_code_and_expands():
    text = '\n'.join([BULLET_MARKER + 'a', '\t' + CHECKBOX_MARKER + 'b', QUOTE_MARKER + 'q',
                      EXPAND_OPEN + 'T', 'in', EXPAND_END])
    assert roundtrip(text)['text'] == text
    state = roundtrip('ls\n' + CODE_ANCHOR, code_ranges=[[0, 4]])
    assert state['text'] == 'ls\n' + CODE_ANCHOR and state['code'] == [[0, 2], [3, 4]]


def test_state_of_wraps_a_lone_list_item_and_row():
    item = {'type': 'list_item', 'attrs': {'checked': True},
            'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'x'}]}]}
    assert state_of([item])['text'] == CHECKED_MARKER + 'x'


def test_markdown_out_and_back_in():
    text = '\n'.join(['Title', BULLET_MARKER + 'item', CHECKED_MARKER + 'done'])
    doc = note_doc({'text': text, 'heading_ranges': [[0, 5]]})
    markdown = to_markdown(state_of(doc['content']))
    assert markdown == '# Title\n- item\n- [x] done'
    back = state_blocks(from_markdown(markdown))
    assert [b['type'] for b in back] == ['heading', 'bullet_list']
    assert [i['attrs']['checked'] for i in back[1]['content']] == [None, True]


def test_a_table_goes_out_as_a_markdown_table():
    tables = [{'offset': 0, 'rows': [[{'text': 'k', 'bold': [[0, 1]]}, {'text': 'v'}],
                                     [{'text': 'a|b'}, {'text': 'c'}]]}]
    doc = note_doc({'text': IMAGE_ANCHOR, 'tables': tables})
    assert to_markdown(state_of(doc['content'])) == '| k | v |\n| --- | --- |\n| a\\|b | c |'


def test_a_list_indented_by_spaces_nests_as_by_tabs():
    text = BULLET_MARKER + 'top\n    ' + BULLET_MARKER + 'nested'
    result = blocks(text, bold_ranges=[[12, 18]])
    nested = result[0]['content'][0]['content'][1]
    assert nested['content'][0]['content'] == [p(t('nested', 'strong'))]
