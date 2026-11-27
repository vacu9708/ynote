"""Markdown for the clipboard: a copy goes out as Markdown, and Markdown pasted
in comes back with its formats.

A note is kept as plain text with format ranges (see models.py), not as
Markdown, so search, undo and the editor see the text as it is shown. These
functions convert between that and Markdown at the clipboard only. They take
and give a rich state as NoteWindow uses it for its own clipboard: 'text' and
the 'bold', 'heading', 'code' (code block lines) and 'backtick' (inline code)
ranges, as [start, end] offsets into the text. A table is in the text itself:
each row starts with TABLE_MARKER and has its cells separated by tabs. So is a
section that folds away, which is HTML's <details> in Markdown.
"""
import re

from .config import (
    BULLET_MARKER, CHECKBOX_MARKER, CHECKED_MARKER, CODE_ANCHOR, CODE_PAD_CHAR,
    EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN, QUOTE_MARKER,
    DIVIDER_TEXT, IMAGE_ANCHOR, TABLE_MARKER,
)

MARKDOWN_MARKERS = {
    BULLET_MARKER: '- ',
    CHECKBOX_MARKER: '- [ ] ',
    CHECKED_MARKER: '- [x] ',
    QUOTE_MARKER: '> ',
}
# A level of a nested list in Markdown, as GitHub writes it.
MARKDOWN_INDENT = '  '
FENCE = '```'

_INVISIBLE = {CODE_ANCHOR: '', CODE_PAD_CHAR: '', IMAGE_ANCHOR: '',
              TABLE_MARKER: '', EXPAND_END: ''}


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


def _table_row(text, start, end, bold, inline, columns):
    """One row of a table, the text from start to end, as a Markdown row of
    `columns` cells."""
    cells = []
    cell_start = start + len(TABLE_MARKER)
    for cell in text[cell_start:end].split('\t'):
        cell_end = cell_start + len(cell)
        body = _inline(cell, bold[cell_start:cell_end],
                       inline[cell_start:cell_end]).strip()
        cells.append(body.replace('|', '\\|'))
        cell_start = cell_end + 1
    cells += [''] * (columns - len(cells))
    return '| ' + ' | '.join(cells) + ' |'


def to_markdown(state):
    """The state's text as Markdown."""
    text = state.get('text', '')
    bold = _flags(len(text), state.get('bold', []))
    heading = _flags(len(text), state.get('heading', []))
    block = _flags(len(text), state.get('code', []))
    inline = _flags(len(text), state.get('backtick', []))

    lines = text.split('\n')
    starts = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line) + 1

    def is_row(n):
        start = starts[n]
        end = start + len(lines[n])
        return (lines[n].startswith(TABLE_MARKER)
                and not all(block[start:end]))

    out = []
    in_block = False
    table_columns = None   # inside a table, how many columns it has
    for number, line in enumerate(lines):
        start = starts[number]
        end = start + len(line)
        is_block = end > start and all(block[start:end])
        if is_block != in_block:
            out.append(FENCE)
            in_block = is_block
        if is_block:
            table_columns = None
            out.append(_clean(line))
            continue

        if is_row(number):
            header = table_columns is None
            if header:
                last = number
                while last + 1 < len(lines) and is_row(last + 1):
                    last += 1
                table_columns = max(lines[n].count('\t') + 1
                                    for n in range(number, last + 1))
            out.append(_table_row(text, start, end, bold, inline,
                                  table_columns))
            if header:
                out.append('| ' + ' | '.join(['---'] * table_columns) + ' |')
            continue
        if table_columns is not None:
            table_columns = None
            # Text right under a table would be read as one more row.
            if line.strip():
                out.append('')

        # A section: GitHub reads Markdown inside <details> only after a
        # blank line, and ends it at a blank line before </details>.
        for marker, tag in ((EXPAND_OPEN, '<details open>'),
                            (EXPAND_CLOSED, '<details>')):
            if line.startswith(marker):
                body = start + len(marker)
                title = _inline(text[body:end], bold[body:end],
                                inline[body:end]).strip()
                out.extend([tag, f'<summary>{title}</summary>', ''])
                break
        else:
            if line == EXPAND_END:
                out.extend(['', '</details>'])
                continue
        if line.startswith((EXPAND_OPEN, EXPAND_CLOSED)):
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
_DETAILS_RE = re.compile(
    r'^\s*<details(\s+open)?\s*>\s*(?:<summary>(.*?)</summary>)?\s*$', re.I)
_SUMMARY_RE = re.compile(r'^\s*<summary>(.*?)</summary>\s*$', re.I)
_DETAILS_END_RE = re.compile(r'^\s*</details>\s*$', re.I)
_QUOTE_RE = re.compile(r'^ {0,3}>[ \t]?(.*)$')
_ITEM_RE = re.compile(r'^([ \t]*)[-*+][ \t]+(?:\[([ xX])\][ \t]+)?(.*)$')
# Only **: __ would take apart names like __init__ in pasted text.
_BOLD_RE = re.compile(r'\*\*(?=\S)(.+?)(?<=\S)\*\*')
_LINK_RE = re.compile(r'!?\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
_AUTOLINK_RE = re.compile(r'<((?:https?|ftp|file)://[^>\s]+)>')
_ESCAPE_RE = re.compile(r'\\([!-/:-@\[-`{-~])')
_DELIMITER_CELL_RE = re.compile(r'^:?-+:?$')


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


def _table_cells(line):
    """The cells of a Markdown table row, or None for a line that is not
    one. An escaped pipe is a pipe in a cell, also in code."""
    if '|' not in line or line.startswith('    '):
        return None
    row = line.strip()
    if row.startswith('|'):
        row = row[1:]
    if row.endswith('|') and not row.endswith('\\|'):
        row = row[:-1]
    cells, cell, i = [], [], 0
    while i < len(row):
        if row[i] == '\\' and i + 1 < len(row):
            cell.append('|' if row[i + 1] == '|' else row[i:i + 2])
            i += 2
            continue
        if row[i] == '|':
            cells.append(''.join(cell))
            cell = []
        else:
            cell.append(row[i])
        i += 1
    cells.append(''.join(cell))
    # A cell is one line of a note's table, where a tab is between cells.
    return [c.strip().replace('\t', ' ') for c in cells]


def _table_columns(lines, at):
    """How many columns the table starting at lines[at] has: its header row
    and the delimiter row under it agree. None when no table starts there."""
    if at + 1 >= len(lines):
        return None
    header, delimiter = _table_cells(lines[at]), _table_cells(lines[at + 1])
    if (header is None or delimiter is None
            or len(header) != len(delimiter)
            or not all(_DELIMITER_CELL_RE.match(c) for c in delimiter)):
        return None
    return len(header)


def _add_table_row(builder, cells, columns):
    cells = (cells + [''] * columns)[:columns]
    builder.add(TABLE_MARKER)
    for index, cell in enumerate(cells):
        if index:
            builder.add('\t')
        _add_inline(builder, cell)


def _sections(lines):
    """The lines with each <details> block made a title line, its summary
    in it, and an end line, without the blank lines that only Markdown needs
    around a block's content. Code fences are left as they are."""
    out = []
    fence = None
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _FENCE_RE.match(line)
        if fence is not None or m:
            if fence is None:
                fence = m.group(1)
            elif (line.strip() and not line.strip().lstrip(fence[0])
                  and len(line.strip()) >= len(fence)):
                fence = None
            out.append(line)
            i += 1
            continue
        m = _DETAILS_RE.match(line)
        if m:
            title = m.group(2)
            if title is None and i + 1 < len(lines):
                summary = _SUMMARY_RE.match(lines[i + 1])
                if summary:
                    title = summary.group(1)
                    i += 1
            marker = EXPAND_OPEN if m.group(1) else EXPAND_CLOSED
            out.append(('section', marker, title or ''))
            i += 1
            if i < len(lines) and not lines[i].strip():
                i += 1
            continue
        if _DETAILS_END_RE.match(line):
            if out and out[-1] == '':
                out.pop()
            out.append(('end',))
            i += 1
            continue
        out.append(line)
        i += 1
    return out


def from_markdown(text):
    """A state for Markdown text, ready to paste into a note."""
    builder = _Builder()
    fence = None
    levels = []   # the indents of the list items open, one per level
    first = True
    lines = _sections(text.replace('\r\n', '\n').split('\n'))
    table_columns = None   # inside a table, how many columns it has
    skip_delimiter = False
    for number, line in enumerate(lines):
        if skip_delimiter:
            skip_delimiter = False
            continue
        if isinstance(line, tuple):
            table_columns = None
            levels = []
            if not first:
                builder.add('\n')
            first = False
            if line[0] == 'end':
                builder.add(EXPAND_END)
            else:
                builder.add(line[1])
                _add_inline(builder, line[2])
            continue
        if table_columns is not None:
            cells = _table_cells(line) if line.strip() else None
            if cells is None:
                table_columns = None
            else:
                builder.add('\n')
                _add_table_row(builder, cells, table_columns)
                continue
        if fence is None:
            columns = _table_columns(lines, number)
            if columns is not None:
                if not first:
                    builder.add('\n')
                first = False
                _add_table_row(builder, _table_cells(line), columns)
                table_columns = columns
                skip_delimiter = True
                levels = []
                continue
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
        m = _QUOTE_RE.match(line)
        if m:
            builder.add(QUOTE_MARKER)
            _add_inline(builder, m.group(1))
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
        return (line == DIVIDER_TEXT or line.startswith(TABLE_MARKER)
                or (end > start and (
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
