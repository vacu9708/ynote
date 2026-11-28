"""E. Formats, F. Markdown typed, G. lists, H. quotes, in Ynote 2.0: the
1.x behaviors that still apply to a note that is a web page. Each case starts
from a note as 1.x saved it, with the cursor at the end of its first line,
gives keys (^ctrl+b) and text, and checks what the note saves, leaving out
the empty line a note always ends with when its last block is no line. See
BEHAVIORS.md."""
import pytest

from tests.e2e.web import assert_saved, start

pytestmark = [pytest.mark.web]

B, TODO, DONE, Q = '• ', '☐ ', '☑ ', '▍ '
CODE_ANCHOR = '⁠'

P = "paragraph({})".format


def item(text, kind='list_item'):
    return f"{kind}(paragraph({text}))"


CASES = {
    # E. formats
    'E1 Ctrl+B bolds a selection': (
        ('ab',), {}, ['^shift+home', '^ctrl+b'], P("'ab'[strong]")),
    'E1 Ctrl+B with no selection bolds what is typed': (
        ('ab',), {}, ['^ctrl+b', 'c'], P("'ab' 'c'[strong]")),
    'E1 Ctrl+B again turns it off': (
        ('ab',), {}, ['^ctrl+b', '^ctrl+b', 'c'], P("'abc'")),
    'E2 after bold text, typing goes on bold': (
        ('ab',), {'bold_ranges': [[0, 2]]}, ['c'], P("'abc'[strong]")),
    'E3 at a line start, the text after counts': (
        ('ab',), {'bold_ranges': [[0, 2]]}, ['^home', 'x'], P("'xab'[strong]")),
    'E4 at a list item text start, the text after counts': (
        (B + 'ab',), {'bold_ranges': [[2, 4]]}, ['^home', 'x'],
        "bullet_list(" + item("'xab'[strong]") + ")"),
    'E5 at the left edge of bold within a line, bold is off': (
        ('abc',), {'bold_ranges': [[1, 3]]}, ['^home', '^right', 'x'], P("'ax' 'bc'[strong]")),
    'E6 Ctrl+B on a selection partly bold makes all of it bold': (
        ('abcd',), {'bold_ranges': [[0, 2]]}, ['^shift+home', '^ctrl+b'], P("'abcd'[strong]")),
    'E7 bold turned off in bold text types plain there': (
        ('abcd',), {'bold_ranges': [[0, 4]]}, ['^home', '^right', '^right', '^ctrl+b', 'x'],
        P("'ab'[strong] 'x' 'cd'[strong]")),
    'E8 Enter turns every format off': (
        ('ab',), {'bold_ranges': [[0, 2]]}, ['^enter', 'c'], P("'ab'[strong]") + ' ' + P("'c'")),
    'E9 Ctrl+H makes the line a heading, and again takes it away': (
        ('ab',), {}, ['^ctrl+h'], "heading('ab')"),
    'E9 Ctrl+H again takes the heading away': (
        ('ab',), {'heading_ranges': [[0, 2]]}, ['^ctrl+h'], P("'ab'")),
    'E9 Ctrl+H makes every line of a selection a heading': (
        ('a\nb',), {}, ['^ctrl+a', '^ctrl+h'], "heading('a') heading('b') paragraph()"),
    'E10 Ctrl+H on an empty line makes what is typed a heading': (
        ('',), {}, ['^ctrl+h', 'x'], "heading('x') paragraph()"),
    'E11 a list item does not become a heading': (
        (B + 'a',), {}, ['^ctrl+h'], "bullet_list(" + item("'a'") + ") paragraph()"),
    'E11 a code line does not become a heading': (
        ('ls',), {'code_ranges': [[0, 2]]}, ['^ctrl+h'], "code_block('ls') paragraph()"),
    'E12 Enter at the end of a heading starts a plain line': (
        ('T',), {'heading_ranges': [[0, 1]]}, ['^enter', 'b'], "heading('T') paragraph('b')"),
    'E14 making a line a heading keeps its bold': (
        ('ab',), {'bold_ranges': [[0, 1]]}, ['^ctrl+h'], "heading('a'[strong] 'b')"),
    'E16 Ctrl+E makes a selection code': (
        ('ab',), {}, ['^shift+home', '^ctrl+e'], P("'ab'[code]")),
    'E16 Ctrl+E with no selection makes what is typed code': (
        ('a',), {}, ['^ctrl+e', 'b'], P("'a' 'b'[code]")),
    'E18 text typed right after inline code is plain': (
        ('ab',), {'backtick_ranges': [[0, 2]]}, ['c'], P("'ab'[code] 'c'")),
    'E18 text typed inside inline code is code': (
        ('ab',), {'backtick_ranges': [[0, 2]]}, ['^left', 'x'], P("'axb'[code]")),
    'E24 Enter does not carry inline code to the next line': (
        ('ab',), {'backtick_ranges': [[0, 2]]}, ['^enter', 'c'], P("'ab'[code]") + ' ' + P("'c'")),

    # F. Markdown typed
    'F1 **text** makes bold': (
        ('',), {}, ['a **bold**'], P("'a ' 'bold'[strong]") + ' paragraph()'),
    'F1 stars around spaces stay': (
        ('',), {}, ['** a **'], P("'** a **'") + ' paragraph()'),
    'F1 a glob stays': (
        ('',), {}, ['ls *.txt **x'], P("'ls *.txt **x'") + ' paragraph()'),
    'F2 `text` makes inline code, and what follows is plain': (
        ('',), {}, ['`ls` x'], P("'ls'[code] ' x'") + ' paragraph()'),
    'F3 backticks in a code block stay': (
        ('ls',), {'code_ranges': [[0, 2]]}, [' `a`'], "code_block('ls `a`') paragraph()"),
    'F3 backticks on two lines do not make code': (
        ('',), {}, ['`a', '^enter', 'b`'], P("'`a'") + ' ' + P("'b`'") + ' paragraph()'),
    'F4 # on an empty line makes a heading': (
        ('',), {}, ['# T'], "heading('T') paragraph()"),
    'F4 # before text makes its line a heading': (
        ('abc',), {}, ['^home', '# '], "heading('abc')"),
    'F4 # after text stays': (
        ('',), {}, ['a # b'], P("'a # b'") + ' paragraph()'),
    'F5 ``` on an empty line starts a code block': (
        ('',), {}, ['```', 'ls'], "code_block('ls') paragraph()"),
    'F5 ``` after text stays text': (
        ('',), {}, ['a ```'], P("'a ```'") + ' paragraph()'),
    'F6 - makes a bullet': (
        ('',), {}, ['- a'], "bullet_list(" + item("'a'") + ") paragraph()"),
    'F6 [ ] makes a to-do': (
        ('',), {}, ['[ ] a'], "bullet_list(" + item("'a'", 'todo') + ") paragraph()"),
    'F6 [ ] after a bullet makes it a to-do': (
        ('',), {}, ['- [ ] a'], "bullet_list(" + item("'a'", 'todo') + ") paragraph()"),
    'F6 - in a code block stays': (
        ('ls',), {'code_ranges': [[0, 2]]}, ['^enter', '- a'], "code_block('ls\\n- a') paragraph()"),
    'F7 > starts a quote': (
        ('',), {}, ['> a'], "blockquote(paragraph('a')) paragraph()"),
    'F8 a line of --- is a divider': (
        ('',), {}, ['---'], "horizontal_rule() paragraph()"),

    # G. lists
    'G1 Ctrl+8 makes a bullet': (
        ('a',), {}, ['^ctrl+8'], "bullet_list(" + item("'a'") + ") paragraph()"),
    'G1 Ctrl+9 makes a to-do': (
        ('a',), {}, ['^ctrl+9'], "bullet_list(" + item("'a'", 'todo') + ") paragraph()"),
    'G1 Ctrl+8 on a to-do makes it a bullet': (
        (TODO + 'a',), {}, ['^ctrl+8'], "bullet_list(" + item("'a'") + ") paragraph()"),
    'G1 Ctrl+8 on a bullet takes it away': (
        (B + 'a',), {}, ['^ctrl+8'], P("'a'")),
    'G2 Enter starts the next item of the kind, a to-do unchecked': (
        (DONE + 'a',), {}, ['^enter', 'b'],
        "bullet_list(" + item("'a'", 'done') + " " + item("'b'", 'todo') + ") paragraph()"),
    'G2 Enter on an empty item ends the list': (
        (B + 'a',), {}, ['^enter', '^enter', 'b'], "bullet_list(" + item("'a'") + ") paragraph('b')"),
    'G3 Enter at an item start adds an empty item above': (
        (B + 'a',), {}, ['^home', '^enter'],
        "bullet_list(" + "list_item(paragraph()) " + item("'a'") + ") paragraph()"),
    'G3 Enter in an item text splits it': (
        (B + 'ab',), {}, ['^left', '^enter'],
        "bullet_list(" + item("'a'") + " " + item("'b'") + ") paragraph()"),
    'G4 Tab indents an item, Shift+Tab outdents it': (
        (B + 'a\n' + B + 'b',), {}, ['^down', '^tab'],
        "bullet_list(list_item(paragraph('a') bullet_list(" + item("'b'") + "))) paragraph()"),
    'G4 Shift+Tab outdents an item': (
        (B + 'a\n\t' + B + 'b',), {}, ['^down', '^shift+tab'],
        "bullet_list(" + item("'a'") + " " + item("'b'") + ") paragraph()"),
    'G5 Tab over a selection indents each item in it': (
        (B + 'a\n' + B + 'b\n' + B + 'c',), {}, ['^down', '^home', '^shift+down', '^shift+end', '^tab', 'X'],
        "bullet_list(list_item(paragraph('a') bullet_list(" + item("'X'") + "))) paragraph()"),
    'G6 Backspace at a top item start takes its marker': (
        (B + 'a',), {}, ['^home', '^backspace'], P("'a'")),
    'G6 Backspace at a nested item start outdents it': (
        (B + 'a\n\t' + B + 'b',), {}, ['^down', '^home', '^backspace'],
        "bullet_list(" + item("'a'") + " " + item("'b'") + ") paragraph()"),
    'G7 Delete at an item end joins the next item text': (
        (B + 'a\n' + B + 'b',), {}, ['^delete'], "bullet_list(" + item("'ab'") + ") paragraph()"),
    'G9 Ctrl+Enter checks the to-dos on the selected lines only': (
        (TODO + 'a\n' + TODO + 'b\n' + TODO + 'c',), {}, ['^shift+down', '^ctrl+enter'],
        "bullet_list(" + item("'a'", 'done') + " " + item("'b'", 'done') + " "
        + item("'c'", 'todo') + ") paragraph()"),
    'G9 Ctrl+Enter again unchecks them': (
        (DONE + 'a',), {}, ['^ctrl+enter'], "bullet_list(" + item("'a'", 'todo') + ") paragraph()"),
    'G13 Left from an item start goes to the end of the line before': (
        ('x\n' + B + 'a',), {}, ['^down', '^home', '^left', 'y'],
        P("'xy'") + " bullet_list(" + item("'a'") + ") paragraph()"),
    'G15 Ctrl+8 in a code block does nothing': (
        ('ls',), {'code_ranges': [[0, 2]]}, ['^ctrl+8'], "code_block('ls') paragraph()"),

    # H. quotes
    'H2 Enter continues a quote': (
        (Q + 'a',), {}, ['^enter', 'b'], "blockquote(paragraph('a') paragraph('b')) paragraph()"),
    'H2 Enter on an empty quote line ends it': (
        (Q + 'a',), {}, ['^enter', '^enter', 'b'], "blockquote(paragraph('a')) paragraph('b')"),
}


@pytest.mark.parametrize('case', list(CASES))
def test_web_text(app, inp, case):
    (text,), ranges, steps, expected = CASES[case]
    # Right of the first line's text, away from a to-do's box.
    start(app, text, at=(200, 10), **ranges)
    for step in steps:
        if step.startswith('^'):
            inp.key(step[1:])
        else:
            inp.type(step)
    assert_saved(app, expected.removesuffix(' paragraph()'), last_line=False)


def test_G8_web_a_click_on_a_box_checks_it_without_moving_the_cursor(app, inp):
    note = start(app, TODO + 'a\n' + TODO + 'b', at=(200, 10))
    inp.key('down')
    note.click_text(0, 10)              # the first item's box
    inp.type('X')
    assert_saved(app, "bullet_list(done(paragraph('a')) todo(paragraph('bX')))", last_line=False)
