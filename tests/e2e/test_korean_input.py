"""S. Korean typed through an input method, in Ynote 2.0: see BEHAVIORS.md.

The keys go through ibus with its Korean engine (2-beolsik), as on a Korean
desktop: g k s r m f is 한글. What the note holds is read from what it saves.
"""
import time

import pytest

from tests.e2e.driver import TestError, extents, quiet

pytestmark = [pytest.mark.ime]

EXPAND_OPEN = '▾ '
EXPAND_END = '⁤'


def start(app, text='', **fields):
    """Ynote 2.0 with one note, as 1.x saved it; the note's top left."""
    app.write_notes([dict({'id': 'test', 'title': 'test', 'text': text,
                           'x': 100, 'y': 80, 'w': 700, 'h': 500}, **fields)])
    app.start()
    x, y, _w, _h = extents(app.note('test').frame)
    return x, y


# Where the first line of text is, from the note's top left: below the title
# bar, inside the editor's padding.
FIRST_LINE = (150, 58)
FIRST_CELL = (25, 65)
EXPAND_TITLE = (60, 66)


def brief(node):
    """A block as kind(content), text as 'text'[marks]."""
    kind = node['type']
    if kind == 'text':
        marks = ','.join(m['type'] for m in node.get('marks', []))
        return repr(node['text']) + (f'[{marks}]' if marks else '')
    inner = ' '.join(brief(c) for c in node.get('content', []))
    return f'{kind}({inner})'


def assert_saved(app, expected, timeout=5):
    """The note's blocks, once saved, are as expected."""
    got = None
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        quiet()
        try:
            doc = app.saved_note('test')['doc']
            got = ' '.join(brief(b) for b in doc['content'])
        except (OSError, ValueError, KeyError, TestError):
            pass
        if got == expected:
            return
        time.sleep(0.2)
    assert got == expected


def test_S1_korean_is_saved_as_composed(app, inp):
    x, y = start(app)
    inp.click(x + FIRST_LINE[0], y + FIRST_LINE[1])
    inp.hangul()
    inp.type('gksrmf ')       # 한글, then a space
    inp.type('dkssud')        # 안녕, ended by Enter
    inp.key('enter')
    inp.type('rkqt')          # 값, as ㅂ and ㅅ join under 가
    inp.key('backspace')      # takes the last jamo: 갑
    inp.hangul()
    inp.type(' ok')
    assert_saved(app, "paragraph('한글 안녕') paragraph('갑 ok')")


def test_S2_enter_while_composing_in_a_list_starts_the_next_item(app, inp):
    x, y = start(app)
    inp.click(x + FIRST_LINE[0], y + FIRST_LINE[1])
    inp.type('- ')
    inp.hangul()
    inp.type('dkssud')        # 안녕
    inp.key('enter')
    inp.type('gksrmf')        # 한글
    inp.hangul()
    assert_saved(app, "bullet_list(list_item(paragraph('안녕')) "
                      "list_item(paragraph('한글'))) paragraph()")


def test_S3_typed_markdown_around_korean_makes_its_format(app, inp):
    x, y = start(app)
    inp.click(x + FIRST_LINE[0], y + FIRST_LINE[1])
    inp.hangul()
    inp.type('**rnfrrp** ')   # **굵게**
    inp.type('`zhem`')        # `코드`
    inp.hangul()
    assert_saved(app, "paragraph('굵게'[strong] ' ' '코드'[code])")


def test_S4_ctrl_b_while_composing_bolds_what_follows(app, inp):
    x, y = start(app)
    inp.click(x + FIRST_LINE[0], y + FIRST_LINE[1])
    inp.hangul()
    inp.type('rk')            # 가, still composing
    inp.key('ctrl+b')
    inp.type('sk')            # 나
    inp.hangul()
    assert_saved(app, "paragraph('가' '나'[strong])")


def test_S5_korean_in_a_table_cell_stays_on_its_line(app, inp):
    rows = [[{'text': 'k'}, {'text': 'v'}], [{'text': ''}, {'text': ''}]]
    x, y = start(app, '￼', tables=[{'offset': 0, 'rows': rows}])
    inp.click(x + FIRST_CELL[0], y + FIRST_CELL[1])
    inp.key('end')
    inp.key('backspace')      # an empty cell
    inp.hangul()
    inp.type('gksrmf')        # 한글
    inp.key('tab')            # the next cell, its text selected
    inp.type('dkssud')        # 안녕, in place of it
    inp.hangul()
    # A header cell's typing starts bold (U5).
    assert_saved(app, "table(table_row(table_header(paragraph('한글'[strong])) "
                      "table_header(paragraph('안녕'[strong]))) "
                      "table_row(table_cell(paragraph()) table_cell(paragraph()))) paragraph()")


def test_S6_korean_in_an_expand_stays_where_it_is_typed(app, inp):
    x, y = start(app, f'{EXPAND_OPEN}T\nx\n{EXPAND_END}')
    inp.click(x + EXPAND_TITLE[0], y + EXPAND_TITLE[1])
    inp.key('end')
    inp.hangul()
    inp.type('wpahr')         # 제목
    inp.key('down')
    inp.key('end')
    inp.type('sodyd')         # 내용
    inp.hangul()
    assert_saved(app, "expand(expand_title('T제목') paragraph('x내용')) paragraph()")
