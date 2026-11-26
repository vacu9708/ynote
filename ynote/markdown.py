"""Markdown for the clipboard: a copy goes out as Markdown, and Markdown pasted
in comes back with its formats.

A note is kept as plain text with format ranges (see models.py), not as
Markdown, so search, undo and the editor see the text as it is shown. These
functions convert between that and Markdown at the clipboard only. They take
and give a rich state as NoteWindow uses it for its own clipboard: 'text' and
the 'bold', 'heading', 'code' (code block lines) and 'backtick' (inline code)
ranges, as [start, end] offsets into the text.
"""
import re

from .config import (
    BULLET_MARKER, CHECKBOX_MARKER, CHECKED_MARKER, CODE_ANCHOR, CODE_PAD_CHAR,
    DIVIDER_TEXT, IMAGE_ANCHOR,
)

MARKDOWN_MARKERS = {
    BULLET_MARKER: '- ',
    CHECKBOX_MARKER: '- [ ] ',
    CHECKED_MARKER: '- [x] ',
}
# A level of a nested list in Markdown, as GitHub writes it.
MARKDOWN_INDENT = '  '
FENCE = '```'

_INVISIBLE = {CODE_ANCHOR: '', CODE_PAD_CHAR: '', IMAGE_ANCHOR: ''}


def _clean(text):
    return ''.join(_INVISIBLE.get(c, c) for c in text)


def _flags(length, ranges):
    flags = [False] * length
    for start, end in ranges:
        for i in range(max(0, start), min(length, end)):
            flags[i] = True
    return flags


def is_all_code(state):
    """Whether every character of the state but its line breaks is code, so
    it is copied as it is: a command goes into a terminal without fences."""
    text = state.get('text', '')
    code = _flags(len(text), state.get('code', []) + state.get('backtick', []))
    visible = [i for i, c in enumerate(text) if c != '\n']
    return bool(visible) and all(code[i] for i in visible)


# ------------------------------------------------------------------ to Markdown

def _code_span(body):
    """body as an inline code span, with a fence longer than any run of
    backticks in it."""
    longest = max((len(run) for run in re.findall('`+', body)), default=0)
    fence = '`' * (longest + 1)
    if body.startswith('`') or body.endswith('`'):
        body = f' {body} '
    return f'{fence}{body}{fence}'


def _inline(text, bold, code):
    """One line of text with its bold and inline code as Markdown."""
    out = []
    i = 0
    while i < len(text):
        if code[i]:
            j = i
            while j < len(text) and code[j]:
                j += 1
            body = _clean(text[i:j])
            if body.strip():
                out.append(_code_span(body))
            i = j
            continue
        j = i
        while j < len(text) and not code[j] and bold[j] == bold[i]:
            j += 1
        run = _clean(text[i:j])
        if bold[i] and run.strip():
            # Emphasis cannot start or end with a space in Markdown.
            lead = run[:len(run) - len(run.lstrip())]
            trail = run[len(run.rstrip()):]
            out.append(f'{lead}**{run.strip()}**{trail}')
        else:
            out.append(run)
        i = j
    return ''.join(out)


def _list_parts(line):
    stripped = line.lstrip(' \t')
    indent = line[:len(line) - len(stripped)]
    for marker in MARKDOWN_MARKERS:
        if stripped.startswith(marker):
            return indent, marker, stripped[len(marker):]
    return None


def to_markdown(state):
    """The state's text as Markdown."""
    text = state.get('text', '')
    bold = _flags(len(text), state.get('bold', []))
    heading = _flags(len(text), state.get('heading', []))
    block = _flags(len(text), state.get('code', []))
    inline = _flags(len(text), state.get('backtick', []))

    out = []
    in_block = False
    offset = 0
    for line in text.split('\n'):
        start, end = offset, offset + len(line)
        offset = end + 1
        is_block = end > start and all(block[start:end])
        if is_block != in_block:
            out.append(FENCE)
            in_block = is_block
        if is_block:
            out.append(_clean(line))
            continue

        if line == DIVIDER_TEXT:
            # Right under text, --- would make that text a heading.
            if out and out[-1].strip():
                out.append('')
            out.append(DIVIDER_TEXT)
            continue

        parts = _list_parts(line)
        if parts is not None:
            indent, marker, _body = parts
            level = indent.count('\t') + indent.count(' ') // 4
            body_start = start + len(indent) + len(marker)
            out.append(MARKDOWN_INDENT * level + MARKDOWN_MARKERS[marker]
                       + _inline(text[body_start:end], bold[body_start:end],
                                 inline[body_start:end]))
        elif end > start and all(heading[start:end]):
            # Bold does not show in a heading, so it is left out.
            out.append('# ' + _inline(text[start:end], [False] * len(line),
                                      inline[start:end]).strip())
        else:
            out.append(_inline(line, bold[start:end], inline[start:end]))
    if in_block:
        out.append(FENCE)
    return '\n'.join(out)


# ------------------------------------------------------------------ from Markdown

_FENCE_RE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
_HEADING_RE = re.compile(r'^ {0,3}#{1,6}(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$')
_BREAK_RE = re.compile(r'^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$')
_ITEM_RE = re.compile(r'^([ \t]*)[-*+][ \t]+(?:\[([ xX])\][ \t]+)?(.*)$')
# Only **: __ would take apart names like __init__ in pasted text.
_BOLD_RE = re.compile(r'\*\*(?=\S)(.+?)(?<=\S)\*\*')
_LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
_AUTOLINK_RE = re.compile(r'<((?:https?|ftp|file)://[^>\s]+)>')
_ESCAPE_RE = re.compile(r'\\([!-/:-@\[-`{-~])')


class _Builder:
    def __init__(self):
        self.text = []
        self.length = 0
        self.ranges = {'bold': [], 'heading': [], 'code': [], 'backtick': []}

    def add(self, text, kind=None):
        if kind is not None and text:
            self.ranges[kind].append([self.length, self.length + len(text)])
        self.text.append(text)
        self.length += len(text)

    def state(self):
        return dict(self.ranges, text=''.join(self.text), images=[])


def _plain(text):
    """Text outside code: links as their text and address, escapes undone."""
    def link(m):
        label, url = m.group(1), m.group(2)
        return url if not label or label == url else f'{label} ({url})'
    text = _LINK_RE.sub(link, text)
    text = _AUTOLINK_RE.sub(r'\1', text)
    return _ESCAPE_RE.sub(r'\1', text)


def _add_inline(builder, text, allow_bold=True):
    """Add one line of Markdown text: code spans first, then bold in what is
    left, as Markdown reads them."""
    i = 0
    plain_start = 0
    pieces = []
    while i < len(text):
        if text[i] == '\\' and i + 1 < len(text):
            i += 2
            continue
        if text[i] != '`':
            i += 1
            continue
        run = len(text[i:]) - len(text[i:].lstrip('`'))
        close = re.compile(r'(?<!`)' + '`' * run + r'(?!`)')
        m = close.search(text, i + run)
        if m is None:
            i += run
            continue
        body = text[i + run:m.start()]
        if (len(body) > 2 and body[0] == ' ' and body[-1] == ' '
                and body.strip()):
            body = body[1:-1]
        pieces.append(('text', text[plain_start:i]))
        pieces.append(('code', body))
        i = plain_start = m.end()
    pieces.append(('text', text[plain_start:]))

    for kind, piece in pieces:
        if kind == 'code':
            if piece.strip():
                builder.add(CODE_PAD_CHAR + piece + CODE_PAD_CHAR, 'backtick')
            continue
        pos = 0
        for m in _BOLD_RE.finditer(piece) if allow_bold else ():
            builder.add(_plain(piece[pos:m.start()]))
            builder.add(_plain(m.group(1)), 'bold')
            pos = m.end()
        builder.add(_plain(piece[pos:]))


def from_markdown(text):
    """A state for Markdown text, ready to paste into a note."""
    builder = _Builder()
    fence = None
    levels = []   # the indents of the list items open, one per level
    first = True
    for line in text.replace('\r\n', '\n').split('\n'):
        # A fence line leaves no line of its own.
        if fence is not None:
            if line.strip() and not line.strip().lstrip(fence[0]) \
                    and len(line.strip()) >= len(fence):
                fence = None
                continue
        else:
            m = _FENCE_RE.match(line)
            if m:
                fence = m.group(1)
                levels = []
                continue

        if not first:
            builder.add('\n')
        first = False

        if fence is not None:
            builder.add(line or CODE_ANCHOR, 'code')
            continue
        if _BREAK_RE.match(line):
            builder.add(DIVIDER_TEXT)
            levels = []
            continue
        m = _HEADING_RE.match(line)
        if m:
            start = builder.length
            _add_inline(builder, (m.group(1) or '').strip(), allow_bold=False)
            if builder.length > start:
                builder.ranges['heading'].append([start, builder.length])
            levels = []
            continue
        m = _ITEM_RE.match(line)
        if m:
            indent = len(m.group(1).expandtabs(4))
            while levels and indent < levels[-1]:
                levels.pop()
            if not levels or indent > levels[-1]:
                levels.append(indent)
            check = m.group(2)
            marker = (BULLET_MARKER if check is None
                      else CHECKBOX_MARKER if check == ' ' else CHECKED_MARKER)
            builder.add('\t' * (len(levels) - 1) + marker)
            _add_inline(builder, m.group(3))
            continue
        levels = []
        _add_inline(builder, line)
    return builder.state()


def _line_kinds(state):
    """For the first and the last line of the state, whether it must be a
    line of its own: a list item, a divider, a heading, or code."""
    text = state['text']
    heading = _flags(len(text), state.get('heading', []))
    block = _flags(len(text), state.get('code', []))

    def whole(start, end):
        line = text[start:end]
        return (line == DIVIDER_TEXT or (end > start and (
            all(heading[start:end]) or all(block[start:end]))))
    first_end = text.find('\n') if '\n' in text else len(text)
    last_start = text.rfind('\n') + 1
    first = whole(0, first_end) or _list_parts(text[:first_end]) is not None
    return first, whole(last_start, len(text))


def fit_between(state, before, after):
    """The state with a line break added in front when its first line must
    start a line and `before`, the text ahead of it on the line, is not blank,
    and one added behind when its last line must end a line and `after` is
    not empty. A list item takes the text after it on as its own."""
    first, last = _line_kinds(state)
    lead = 1 if first and before.strip() else 0
    trail = last and after != ''
    if not lead and not trail:
        return state
    shifted = {key: [[s + lead, e + lead] for s, e in ranges]
               for key, ranges in state.items()
               if key not in ('text', 'images')}
    text = '\n' * lead + state['text'] + ('\n' if trail else '')
    return dict(shifted, text=text, images=state.get('images', []))
