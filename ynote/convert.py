"""Turn a note of Ynote 1.x into the content of a 2.0 note.

A 1.x note is plain text with formats as character ranges over it, and
structure as characters in the text (list markers, expand marks, anchors for
images and tables; see ARCHITECTURE.md). A 2.0 note is a ProseMirror
document, saved as its JSON, in the schema of web/src/schema.js. Pure Python,
so it is unit-tested.
"""
from .config import (
    BULLET_MARKER, CHECKBOX_MARKER, CHECKED_MARKER, CODE_ANCHOR, CODE_PAD_CHAR,
    DIVIDER_TEXT, EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN, IMAGE_ANCHOR,
    OLD_CODE_PAD_CHAR, QUOTE_MARKER, TABLE_MARKER)

ITEM_MARKERS = {BULLET_MARKER: None, CHECKBOX_MARKER: False,
                CHECKED_MARKER: True}


def paragraph(content=None):
    node = {'type': 'paragraph'}
    if content:
        node['content'] = content
    return node


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

    def old_table_row(self, line):
        """A row of a table as 1.x wrote them before cells were editors:
        cells of plain text separated by tabs."""
        cells = line.lstrip('\t')[len(TABLE_MARKER):].split('\t')
        row = [[paragraph([{'type': 'text', 'text': c}] if c else None)]
               for c in cells]
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
            self.old_table_row(line)
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
