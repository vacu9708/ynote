"""Turn a note of Ynote 1.x into the content of a 2.0 note.

A 1.x note is plain text with formats as character ranges over it, and
structure as characters in the text (list markers, expand marks, anchors for
images and tables; see ARCHITECTURE.md). A 2.0 note is a ProseMirror
document, saved as its JSON, in the schema of web/src/schema.js. Pure Python,
so it is unit-tested.
"""
import re

from .config import (
    BULLET_MARKER, CHECKBOX_MARKER, CHECKED_MARKER, CODE_ANCHOR, CODE_PAD_CHAR,
    DIVIDER_TEXT, EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN, IMAGE_ANCHOR,
    OLD_CODE_PAD_CHAR, QUOTE_MARKER, TABLE_MARKER)

# How many spaces made a level of a list before a tab did (as editor.py).
INDENT_SPACES = 4

ITEM_MARKERS = {BULLET_MARKER: None, CHECKBOX_MARKER: False,
                CHECKED_MARKER: True}


def paragraph(content=None):
    node = {'type': 'paragraph'}
    if content:
        node['content'] = content
    return node


# An http or https address in text, as links.js finds one: it runs to a
# space or a character that rarely ends one, and leaves out punctuation that
# ends the sentence.
_URL_RE = re.compile(r'\bhttps?://[^\s<>"\'`]+', re.I)
_TRAILING = '.,;:!?\'"]}>'


def _trim_url(url):
    while url:
        if url[-1] in _TRAILING:
            url = url[:-1]
        elif url[-1] == ')' and url.count('(') < url.count(')'):
            url = url[:-1]
        else:
            break
    return url


def _linkify_inline(nodes):
    out = []
    for node in nodes:
        marks = node.get('marks') or []
        if node.get('type') != 'text' or any(m.get('type') in ('link', 'code') for m in marks):
            out.append(node)
            continue
        text, pos = node['text'], 0
        for m in _URL_RE.finditer(text):
            url = _trim_url(m.group(0))
            if '://' not in url or url.endswith('://'):
                continue
            start, end = m.start(), m.start() + len(url)
            if start > pos:
                out.append(dict(node, text=text[pos:start]))
            out.append(dict(node, text=url, marks=marks + [{'type': 'link', 'attrs': {'href': url}}]))
            pos = end
        if pos == 0:
            out.append(node)
        elif pos < len(text):
            out.append(dict(node, text=text[pos:]))
    return out


def linkify(doc):
    """The document with the addresses in its text made links, as typing
    them makes them, once: a note saved before links were marks, as by 1.x
    or 2.0.0, has attrs.links unset. Returned as it was otherwise."""
    if (doc.get('attrs') or {}).get('links'):
        return doc

    def walk(node):
        if node.get('type') == 'code_block':
            return node
        content = node.get('content')
        if not content:
            return node
        if node.get('type') in ('paragraph', 'heading', 'expand_title'):
            return dict(node, content=_linkify_inline(content))
        return dict(node, content=[walk(child) for child in content])
    return dict(walk(doc), attrs=dict(doc.get('attrs') or {}, links=1))


def note_doc(note):
    """The document of a 1.x note, given as its saved dict."""
    state = {
        'text': note.get('text') or '',
        'bold': note.get('bold_ranges'),
        'heading': note.get('heading_ranges'),
        'code': note.get('code_ranges'),
        'backtick': note.get('backtick_ranges'),
        'images': note.get('images'),
        'tables': note.get('tables'),
    }
    return {'type': 'doc', 'content': state_blocks(state) or [paragraph()]}


def _flags(length, ranges):
    flags = [False] * length
    for start, end in ranges or []:
        for i in range(max(0, int(start)), min(length, int(end))):
            flags[i] = True
    return flags


class _Converter:
    """The blocks of one rich state: a note's, or a table cell's, whose
    state has the same fields under the clipboard's names."""

    def __init__(self, state, allow_tables):
        self.text = text = state.get('text') or ''
        n = len(text)
        self.bold = _flags(n, state.get('bold'))
        self.heading = _flags(n, state.get('heading'))
        self.code = _flags(n, state.get('code'))
        self.tick = _flags(n, state.get('backtick'))
        # The address each character links to, or None.
        self.link = [None] * n
        for start, end, href in state.get('links') or []:
            for i in range(max(0, int(start)), min(n, int(end))):
                self.link[i] = href
        self.images = {int(im.get('offset', -1)): im
                       for im in state.get('images') or []}
        self.tables = ({int(t.get('offset', -1)): t
                        for t in state.get('tables') or []}
                       if allow_tables else {})
        # The open expands, innermost last, each the list of blocks it
        # holds; the first is the note itself.
        self.stack = [[]]
        self.expands = []
        # The kind of the line before, so runs of code, quote, or list
        # lines become one block.
        self.prev = None

    # --- inline content -------------------------------------------------

    def _is_pad(self, i):
        ch = self.text[i]
        if ch == CODE_PAD_CHAR:
            return True
        if ch != OLD_CODE_PAD_CHAR:
            return False
        near = [j for j in (i - 1, i, i + 1) if 0 <= j < len(self.text)]
        return any(self.tick[j] for j in near)

    def inline(self, start, end):
        nodes = []
        run, marks = '', None

        def flush():
            nonlocal run
            if run:
                node = {'type': 'text', 'text': run}
                if marks:
                    node['marks'] = marks
                nodes.append(node)
            run = ''

        for i in range(start, end):
            ch = self.text[i]
            if ch == CODE_ANCHOR or self._is_pad(i):
                continue
            if ch == IMAGE_ANCHOR:
                image = self.images.get(i)
                if image and image.get('file'):
                    flush()
                    nodes.append({'type': 'image', 'attrs': {
                        'file': image['file'],
                        'name': image.get('original_name') or ''}})
                continue
            want = []
            if self.bold[i]:
                want.append({'type': 'strong'})
            if self.tick[i]:
                want.append({'type': 'code'})
            if self.link[i]:
                want.append({'type': 'link', 'attrs': {'href': self.link[i]}})
            if want != marks:
                flush()
                marks = want
            run += ch
        flush()
        return nodes

    # --- blocks ---------------------------------------------------------

    @property
    def blocks(self):
        return self.stack[-1]

    def add(self, block, kind=None):
        self.blocks.append(block)
        self.prev = kind

    def add_item(self, level, checked, content):
        item = {'type': 'list_item', 'attrs': {'checked': checked},
                'content': [paragraph(content)]}
        if self.prev == 'item' and self.blocks[-1]['type'] == 'bullet_list':
            lst = self.blocks[-1]
            for _ in range(level):
                last = lst['content'][-1]
                if last['content'][-1]['type'] == 'bullet_list':
                    lst = last['content'][-1]
                else:
                    nested = {'type': 'bullet_list', 'content': []}
                    last['content'].append(nested)
                    lst = nested
                    break
            lst['content'].append(item)
        else:
            self.blocks.append({'type': 'bullet_list', 'content': [item]})
        self.prev = 'item'

    def add_code_line(self, line):
        line = line.replace(CODE_ANCHOR, '').replace(IMAGE_ANCHOR, '')
        if self.prev == 'code':
            block = self.blocks[-1]
            text = block['content'][0]['text'] if block.get('content') else ''
            text += '\n' + line
            block['content'] = [{'type': 'text', 'text': text}] if text else []
            if not text:
                del block['content']
        else:
            block = {'type': 'code_block'}
            if line:
                block['content'] = [{'type': 'text', 'text': line}]
            self.add(block)
        self.prev = 'code'

    def add_quote(self, content):
        if self.prev == 'quote':
            self.blocks[-1]['content'].append(paragraph(content))
        else:
            self.add({'type': 'blockquote', 'content': [paragraph(content)]})
        self.prev = 'quote'

    def open_expand(self, is_open, title):
        expand = {'type': 'expand', 'attrs': {'open': is_open},
                  'content': [{'type': 'expand_title', **(
                      {'content': title} if title else {})}]}
        self.add(expand)
        self.expands.append(expand)
        self.stack.append(expand['content'])
        self.prev = None

    def close_expand(self):
        if len(self.stack) == 1:
            return
        self.stack.pop()
        expand = self.expands.pop()
        if len(expand['content']) == 1:
            expand['content'].append(paragraph())
        self.prev = None

    def table(self, rows_of_cells):
        width = max((len(row) for row in rows_of_cells), default=0)
        if not width:
            return None
        rows = []
        for r, row in enumerate(rows_of_cells):
            cells = []
            for c in range(width):
                content = row[c] if c < len(row) else [paragraph()]
                cells.append({
                    'type': 'table_header' if r == 0 else 'table_cell',
                    'attrs': {'colspan': 1, 'rowspan': 1, 'colwidth': None},
                    'content': content or [paragraph()]})
            rows.append({'type': 'table_row', 'content': cells})
        return {'type': 'table', 'content': rows}

    def rich_table(self, table):
        rows = [[_Converter(cell or {}, False).convert() for cell in row]
                for row in table.get('rows') or []]
        return self.table(rows)

    def old_table_row(self, start, line):
        """A row of a table as 1.x wrote them before cells were editors:
        cells of text separated by tabs, as a pasted Markdown table also
        comes, with its formats."""
        at = start + len(line) - len(line.lstrip('\t')) + len(TABLE_MARKER)
        row = []
        for cell in line.lstrip('\t')[len(TABLE_MARKER):].split('\t'):
            # U+2028, a line break in a pasted cell, starts a line of it.
            lines = []
            for part in cell.split('\u2028'):
                lines.append(paragraph(self.inline(at, at + len(part)) or None))
                at += len(part) + 1
            row.append(lines)
        if self.prev == 'old-table':
            self._old_rows.append(row)
            self.blocks[-1] = self.table(self._old_rows)
        else:
            self._old_rows = [row]
            self.add(self.table(self._old_rows))
        self.prev = 'old-table'

    def line(self, start, line):
        text = self.text
        end = start + len(line)
        stripped = line.lstrip('\t')
        level = len(line) - len(stripped)
        body = start + level

        if stripped.startswith(TABLE_MARKER):
            self.old_table_row(start, line)
            return
        if line and self.code[start]:
            self.add_code_line(line)
            return
        if stripped == EXPAND_END:
            self.close_expand()
            return
        if stripped.startswith((EXPAND_OPEN, EXPAND_CLOSED)):
            self.open_expand(stripped.startswith(EXPAND_OPEN),
                             self.inline(body + len(EXPAND_OPEN), end))
            return
        if line == DIVIDER_TEXT:
            self.add({'type': 'horizontal_rule'})
            return
        tables = [i for i in range(start, end)
                  if text[i] == IMAGE_ANCHOR and i in self.tables]
        if tables:
            at = start
            for i in tables:
                before = self.inline(at, i)
                if before:
                    self.add(paragraph(before))
                block = self.rich_table(self.tables[i])
                if block:
                    self.add(block)
                at = i + 1
            after = self.inline(at, end)
            if after:
                self.add(paragraph(after))
            return
        for marker, checked in ITEM_MARKERS.items():
            if stripped.startswith(marker):
                self.add_item(level, checked,
                              self.inline(body + len(marker), end))
                return
        # An item indented by spaces, as before tabs were: each run of
        # INDENT_SPACES is a level, as 1.x opens it (tabbed_indent()).
        spaced = line.lstrip(' \t')
        indent = line[:len(line) - len(spaced)]
        for marker, checked in ITEM_MARKERS.items():
            if ' ' in indent and spaced.startswith(marker):
                self.add_item(indent.replace(' ' * INDENT_SPACES, '\t').count('\t'), checked,
                              self.inline(start + len(indent) + len(marker), end))
                return
        if stripped.startswith(QUOTE_MARKER):
            self.add_quote(self.inline(body + len(QUOTE_MARKER), end))
            return
        content = self.inline(start, end)
        if line and any(self.heading[start:end]):
            self.add({'type': 'heading', **(
                {'content': content} if content else {})})
            return
        self.add(paragraph(content))

    def convert(self):
        start = 0
        for line in self.text.split('\n'):
            self.line(start, line)
            start += len(line) + 1
        while len(self.stack) > 1:
            self.close_expand()
        return self.stack[0]


def state_blocks(state, allow_tables=True):
    """The blocks of a rich state: text, bold, heading, code, backtick,
    images, and tables, as 1.x's clipboard and table cells hold them."""
    return _Converter(state, allow_tables).convert()


def doc_text(doc):
    """The text of a document, a line per block and a tab between table
    cells, for search."""
    lines = []

    def walk(node, line):
        kind = node.get('type')
        if kind == 'text':
            line.append(node.get('text', ''))
            return
        if kind == 'image':
            return
        children = node.get('content') or []
        if kind in ('paragraph', 'heading', 'expand_title'):
            own = []
            for child in children:
                walk(child, own)
            lines.append(''.join(own))
        elif kind == 'code_block':
            lines.extend(''.join(c.get('text', '') for c in children)
                         .split('\n'))
        elif kind == 'table_row':
            cells = []
            for cell in children:
                start = len(lines)
                walk(cell, None)
                cells.append(' '.join(lines[start:]))
                del lines[start:]
            lines.append('\t'.join(cells))
        else:
            for child in children:
                walk(child, line)

    walk(doc, None)
    return '\n'.join(lines)


# --- From a 2.0 document back to a rich state, for markdown.py --------------

_WRAP = {'list_item': 'bullet_list', 'table_row': 'table', 'table_cell': 'table_row',
         'table_header': 'table_row'}


def _blocks_of(nodes):
    """Top-level nodes of a fragment as blocks: a list item, a row, or a cell
    copied alone is wrapped as in a note, and an expand's title is a line."""
    out = []
    for node in nodes:
        kind = node.get('type')
        while kind in _WRAP:
            node = {'type': _WRAP[kind], 'content': [node]}
            kind = node['type']
        if kind == 'expand_title':
            node = dict(node, type='paragraph')
        if kind == 'text' or kind == 'image':
            node = {'type': 'paragraph', 'content': [node]}
        out.append(node)
    return out


class _StateBuilder:
    """The text, ranges, images, and tables of a rich state, line by line."""

    def __init__(self, allow_tables=True):
        self.text = ''
        self.bold, self.heading, self.code, self.backtick = [], [], [], []
        self.links = []
        self.images, self.tables = [], []
        self.allow_tables = allow_tables
        self.lines = 0

    def _newline(self):
        if self.lines:
            self.text += '\n'
        self.lines += 1

    def inline(self, nodes):
        for node in nodes or []:
            if node.get('type') == 'image':
                attrs = node.get('attrs') or {}
                self.images.append({'file': attrs.get('file', ''),
                                    'original_name': attrs.get('name', ''),
                                    'offset': len(self.text)})
                self.text += IMAGE_ANCHOR
                continue
            text = node.get('text', '')
            start, end = len(self.text), len(self.text) + len(text)
            self.text += text
            marks = {m.get('type') for m in node.get('marks') or []}
            if 'strong' in marks:
                self.bold.append([start, end])
            if 'code' in marks:
                self.backtick.append([start, end])
            for mark in node.get('marks') or []:
                if mark.get('type') == 'link' and end > start:
                    href = (mark.get('attrs') or {}).get('href', '')
                    # Next to the same link it goes on, as one.
                    if self.links and self.links[-1][1] == start and self.links[-1][2] == href:
                        self.links[-1][1] = end
                    else:
                        self.links.append([start, end, href])

    def line(self, prefix='', nodes=(), heading=False):
        self._newline()
        start = len(self.text)
        self.text += prefix
        self.inline(nodes)
        if heading and len(self.text) > start:
            self.heading.append([start, len(self.text)])

    def block(self, node, level=0, quote=False):
        kind = node.get('type')
        content = node.get('content') or []
        if kind in ('paragraph', 'expand_title'):
            self.line(('\t' * level + QUOTE_MARKER) if quote else '', content)
        elif kind == 'heading':
            self.line('', content, heading=True)
        elif kind == 'code_block':
            text = ''.join(c.get('text', '') for c in content)
            for code_line in text.split('\n'):
                self._newline()
                start = len(self.text)
                self.text += code_line or CODE_ANCHOR
                self.code.append([start, len(self.text)])
        elif kind == 'horizontal_rule':
            self.line(DIVIDER_TEXT)
        elif kind == 'blockquote':
            for child in content:
                self.block(child, level, quote=True)
        elif kind == 'bullet_list':
            for item in content:
                checked = (item.get('attrs') or {}).get('checked')
                marker = BULLET_MARKER if checked is None else (
                    CHECKED_MARKER if checked else CHECKBOX_MARKER)
                for i, child in enumerate(item.get('content') or []):
                    if child.get('type') == 'paragraph':
                        self.line('\t' * level + (marker if i == 0 else BULLET_MARKER),
                                  child.get('content'))
                    elif child.get('type') == 'bullet_list':
                        self.block(child, level + 1)
                    else:
                        self.block(child, level)
        elif kind == 'expand':
            is_open = (node.get('attrs') or {}).get('open', True)
            title, *body = content or [{}]
            self.line(EXPAND_OPEN if is_open else EXPAND_CLOSED, title.get('content'))
            for child in body:
                self.block(child)
            self.line(EXPAND_END)
        elif kind == 'table':
            rows = []
            for row in content:
                rows.append([state_of(cell.get('content') or [], allow_tables=False)
                             for cell in row.get('content') or []])
            self._newline()
            if self.allow_tables:
                self.tables.append({'offset': len(self.text), 'rows': rows})
                self.text += IMAGE_ANCHOR
        else:
            for child in content:
                self.block(child, level, quote)

    def state(self):
        return {'text': self.text, 'bold': self.bold, 'heading': self.heading,
                'code': self.code, 'backtick': self.backtick,
                'images': self.images, 'tables': self.tables, 'links': self.links}


def state_of(nodes, allow_tables=True):
    """The rich state of a list of blocks, or of a fragment's top nodes, as
    1.x's clipboard and markdown.py take it."""
    builder = _StateBuilder(allow_tables)
    for node in _blocks_of(nodes):
        builder.block(node)
    return builder.state()
