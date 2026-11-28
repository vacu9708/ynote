// What the Format and Insert menus and the shortcuts do. Each is a
// ProseMirror command: (state, dispatch) => whether it applies.
import {setBlockType, toggleMark, wrapIn, lift} from 'prosemirror-commands';
import {wrapInList, liftListItem, sinkListItem, splitListItem} from 'prosemirror-schema-list';
import {goToNextCell, addRowAfter, isInTable} from 'prosemirror-tables';
import {Selection, TextSelection} from 'prosemirror-state';
import {schema} from './schema.js';

const {paragraph, heading, code_block, blockquote, horizontal_rule, bullet_list,
  list_item, expand, expand_title, table, table_row, table_cell, table_header} = schema.nodes;

// On a selection only partly bold (or code), the format comes off, as in
// Confluence (1.x put it on all of it).
export const toggleBold = toggleMark(schema.marks.strong);
export const toggleInlineCode = toggleMark(schema.marks.code);

// The nearest ancestor of the selection's start of a type, as {node, pos, depth}.
export function ancestor(state, type) {
  const $from = state.selection.$from;
  for (let d = $from.depth; d > 0; d--) {
    if ($from.node(d).type === type) return {node: $from.node(d), pos: $from.before(d), depth: d};
  }
  return null;
}

export function headingActive(state) {
  return state.selection.$from.parent.type === heading;
}

export function toggleHeading(state, dispatch) {
  if (headingActive(state)) return setBlockType(paragraph)(state, dispatch);
  // A list item or a line of code is never made a heading, as in 1.x.
  if (ancestor(state, list_item) || state.selection.$from.parent.type === code_block) return false;
  return setBlockType(heading)(state, dispatch);
}

// A line as Markdown, with the marks of its text, as 1.x showed lines made
// code: **bold**, `code`.
function inlineMarkdown(block) {
  let out = '';
  block.forEach(child => {
    if (!child.isText) return;
    let text = child.text;
    if (child.marks.some(m => m.type === schema.marks.code)) text = '`' + text + '`';
    if (child.marks.some(m => m.type === schema.marks.strong)) text = '**' + text + '**';
    out += text;
  });
  return out;
}

// The lines of the blocks between from and to as Markdown: headings,
// list items at their levels, to-dos, quotes; code as it is.
function markdownLines(doc, from, to) {
  const lines = [];
  doc.nodesBetween(from, to, (node, pos) => {
    if (!node.isTextblock) return true;
    const $pos = doc.resolve(pos);
    if (node.type === code_block) { lines.push(...node.textContent.split('\n')); return false; }
    let prefix = '';
    let levels = 0;
    for (let d = $pos.depth; d > 0; d--) {
      const anc = $pos.node(d);
      if (anc.type === bullet_list) levels++;
      if (anc.type === blockquote) prefix = '> ' + prefix;
    }
    const item = $pos.depth > 0 && $pos.parent.type === list_item && $pos.index() === 0 ? $pos.parent : null;
    if (item) {
      const box = item.attrs.checked === null ? '' : item.attrs.checked ? '[x] ' : '[ ] ';
      prefix += '  '.repeat(Math.max(0, levels - 1)) + '- ' + box;
    } else if (levels) {
      prefix += '  '.repeat(levels);
    }
    if (node.type === heading) prefix += '# ';
    lines.push(prefix + inlineMarkdown(node));
    return false;
  });
  return lines;
}

export function toggleCodeBlock(state, dispatch) {
  const {$from, $to, from, to} = state.selection;
  // A block of code made plain again: a line for each of its lines, the
  // Markdown in them kept as text.
  if ($from.parent.type === code_block && $from.sameParent($to)) {
    if (!dispatch) return true;
    const block = $from.parent;
    const lines = block.textContent.split('\n').map(line =>
      paragraph.create(null, line ? schema.text(line) : null));
    const start = $from.before();
    const tr = state.tr.replaceWith(start, start + block.nodeSize, lines);
    tr.setSelection(TextSelection.near(tr.doc.resolve(start + 1)));
    dispatch(tr.scrollIntoView());
    return true;
  }
  // Within one line: that line becomes code.
  if ($from.parent.isTextblock && $from.sameParent($to)) return setBlockType(code_block)(state, dispatch);
  // Lines selected over several blocks become one block of code, a line
  // each, their formats as Markdown, as in 1.x. Not over an image, which
  // code cannot hold: it would be lost.
  const range = $from.blockRange($to);
  if (!range) return false;
  let image = false;
  state.doc.nodesBetween(from, to, node => { if (node.type.name === 'image') image = true; return !image; });
  if (image) return false;
  if (!dispatch) return true;
  const text = markdownLines(state.doc, from, to).join('\n');
  const tr = state.tr.replaceWith(range.start, range.end, code_block.create(null, text ? schema.text(text) : null));
  tr.setSelection(TextSelection.create(tr.doc, range.start + 1 + text.length));
  dispatch(tr.scrollIntoView());
  return true;
}

// The list items the selection is in, as {node, pos}: those at the depth of
// the innermost list holding the selection's start.
function selectedItems(state) {
  const item = ancestor(state, list_item);
  if (!item) return [];
  const {from, to} = state.selection;
  const list = state.doc.resolve(item.pos).parent;
  const listStart = state.doc.resolve(item.pos).start();
  const items = [];
  list.forEach((node, offset) => {
    const pos = listStart + offset;
    if (pos + node.nodeSize > from && pos <= Math.max(to, from)) items.push({node, pos});
  });
  return items;
}

function setChecked(state, dispatch, checked) {
  const items = selectedItems(state);
  if (!items.length) return false;
  if (dispatch) {
    const tr = state.tr;
    for (const {node, pos} of items) tr.setNodeMarkup(pos, null, {...node.attrs, checked});
    dispatch(tr);
  }
  return true;
}

// A bullet list, a checklist: turns the selected lines into items of that
// kind, items of the other kind into this one, or items of this kind back
// into lines.
function toggleList(checked) {
  return (state, dispatch) => {
    const items = selectedItems(state);
    if (items.length) {
      const allThis = items.every(({node}) => (node.attrs.checked === null) === (checked === null));
      if (allThis) return liftListItem(list_item)(state, dispatch);
      return setChecked(state, dispatch, checked);
    }
    if (!wrapInList(bullet_list)(state)) return false;
    if (!dispatch) return true;
    wrapInList(bullet_list)(state, tr => {
      if (checked !== null) {
        const {from, to} = tr.selection;
        tr.doc.nodesBetween(from, to, (node, pos) => {
          if (node.type === list_item) tr.setNodeMarkup(pos, null, {checked});
        });
      }
      dispatch(tr);
    });
    return true;
  };
}
export const toggleBullet = toggleList(null);
export const toggleChecklist = toggleList(false);

export function toggleQuote(state, dispatch) {
  if (ancestor(state, blockquote)) return lift(state, dispatch);
  return wrapIn(blockquote)(state, dispatch);
}

// Check or uncheck the to-dos on the selected lines: all checked when any is
// open, else all unchecked.
export function toggleTodos(state, dispatch) {
  const todos = selectedItems(state).filter(({node}) => node.attrs.checked !== null);
  if (!todos.length) return false;
  const anyOpen = todos.some(({node}) => !node.attrs.checked);
  if (dispatch) {
    const tr = state.tr;
    for (const {node, pos} of todos) tr.setNodeMarkup(pos, null, {...node.attrs, checked: anyOpen});
    dispatch(tr);
  }
  return true;
}

export function setExpandOpen(tr, pos, open) {
  const node = tr.doc.nodeAt(pos);
  tr.setNodeMarkup(pos, null, {...node.attrs, open});
  // Folding is not an edit to undo: the content stays as it was.
  tr.setMeta('addToHistory', false);
  return tr;
}

// Ctrl+Enter on an expand's title folds or opens it.
export function toggleExpandAtTitle(state, dispatch) {
  if (state.selection.$from.parent.type !== expand_title) return false;
  const found = ancestor(state, expand);
  if (dispatch) dispatch(setExpandOpen(state.tr, found.pos, !found.node.attrs.open));
  return true;
}

// A divider at the cursor: above the line when the cursor starts it or the
// line is empty, below it when the cursor ends it, else splitting the line
// there. The cursor goes on below it, on a line made when there is none.
export function insertDivider(state, dispatch) {
  if (state.selection.$from.parent.type === code_block) return false;
  if (dispatch) {
    const tr = state.tr.deleteSelection();
    const $pos = tr.selection.$from;
    let at;
    if (!$pos.parent.isTextblock) {
      at = $pos.pos;
    } else if ($pos.parentOffset === 0) {
      at = $pos.before();
    } else if ($pos.parentOffset === $pos.parent.content.size) {
      at = $pos.after();
    } else {
      tr.split($pos.pos);
      at = $pos.pos + 1;
    }
    tr.insert(at, horizontal_rule.create());
    const after = at + 1;
    const next = tr.doc.resolve(after).nodeAfter;
    if (!next || !next.isTextblock) tr.insert(after, paragraph.create());
    tr.setSelection(TextSelection.create(tr.doc, after + 1));
    dispatch(tr.scrollIntoView());
  }
  return true;
}

// An expand, holding the selected lines when there are some, as in 1.x.
export function insertExpand(state, dispatch) {
  const {$from, $to, empty} = state.selection;
  const range = $from.blockRange($to);
  if (!range) return false;
  if (dispatch) {
    let content;
    if (empty && $from.parent.content.size === 0) {
      content = [paragraph.create()];
    } else if (empty) {
      content = null;
    } else {
      content = [];
      for (let i = range.startIndex; i < range.endIndex; i++) content.push(range.parent.child(i));
    }
    const tr = state.tr;
    if (content) {
      const node = expand.create(null, [expand_title.create(), ...content]);
      tr.replaceWith(range.start, range.end, node);
      tr.setSelection(TextSelection.create(tr.doc, range.start + 2));
    } else {
      const after = $from.after(range.depth + 1);
      const node = expand.create(null, [expand_title.create(), paragraph.create()]);
      tr.insert(after, node);
      tr.setSelection(TextSelection.create(tr.doc, after + 2));
    }
    dispatch(tr.scrollIntoView());
  }
  return true;
}

// A 3 × 3 table, its first row the header.
const TABLE_ROWS = 3, TABLE_COLS = 3;
export function insertTable(state, dispatch) {
  const rows = TABLE_ROWS, cols = TABLE_COLS;
  if (isInTable(state)) return false;
  if (dispatch) {
    const row = type => table_row.create(null,
      Array.from({length: cols}, () => type.createAndFill()));
    const node = table.create(null, [row(table_header),
      ...Array.from({length: rows - 1}, () => row(table_cell))]);
    const {$from} = state.selection;
    const tr = state.tr;
    let pos;
    if ($from.parent.content.size === 0 && $from.depth > 0) {
      pos = $from.before();
      tr.replaceWith(pos, $from.after(), node);
    } else {
      pos = $from.after(1);
      tr.insert(pos, node);
    }
    tr.setSelection(TextSelection.near(tr.doc.resolve(pos + 3)));
    dispatch(tr.scrollIntoView());
  }
  return true;
}

// Tab in a table goes to the next cell, adding a row after the last one.
export function nextCellOrRow(state, dispatch, view) {
  if (!isInTable(state)) return false;
  if (goToNextCell(1)(state, dispatch)) return true;
  if (!dispatch) return true;
  addRowAfter(state, dispatch);
  goToNextCell(1)(view.state, view.dispatch);
  return true;
}

// Esc in a table goes on to the line after it, making one at the end.
export function leaveTable(state, dispatch) {
  const found = ancestor(state, table);
  if (!found) return false;
  if (dispatch) {
    const after = found.pos + found.node.nodeSize;
    const tr = state.tr;
    const $after = tr.doc.resolve(after);
    if (!$after.nodeAfter || !$after.nodeAfter.isTextblock) tr.insert(after, paragraph.create());
    tr.setSelection(TextSelection.create(tr.doc, after + 1));
    dispatch(tr.scrollIntoView());
  }
  return true;
}

export function indentItem(state, dispatch) { return sinkListItem(list_item)(state, dispatch); }
export function outdentItem(state, dispatch) { return liftListItem(list_item)(state, dispatch); }

// In a table, Tab and Shift+Tab indent and outdent a list item in a cell, as
// in 1.x; on a first item, which cannot go in, or a top one, which cannot go
// out, they go on to the next or the cell before.
function itemInCell(state) {
  const {$from} = state.selection;
  let item = -1;
  for (let d = $from.depth; d > 0; d--) {
    const type = $from.node(d).type;
    if (type === list_item && item < 0) item = d;
    if (type === table_cell || type === table_header) return item > 0 ? {depth: item, cell: d} : null;
  }
  return null;
}

export function indentItemInCell(state, dispatch) {
  return itemInCell(state) ? sinkListItem(list_item)(state, dispatch) : false;
}

export function outdentItemInCell(state, dispatch) {
  const found = itemInCell(state);
  // Only a nested item: a top one's list is the cell's own.
  if (!found || found.depth - 2 <= found.cell) return false;
  return liftListItem(list_item)(state, dispatch);
}

// Backspace at the start of the line after a list joins the line to its
// last item's text, as in Confluence. ProseMirror's own made the line an
// item again, which the next Backspace took back out, and so on: an empty
// last item came and went while Backspace was held.
export function backspaceAfterList(state, dispatch) {
  const {$cursor} = state.selection;
  if (!$cursor || $cursor.parentOffset || $cursor.depth < 1 || $cursor.parent.type !== paragraph) return false;
  const start = $cursor.before();
  const before = state.doc.resolve(start).nodeBefore;
  if (!before || before.type !== bullet_list) return false;
  const target = Selection.findFrom(state.doc.resolve(start), -1, true);
  if (!target) return false;
  if (dispatch) {
    const at = target.from;
    const tr = state.tr.delete(start, $cursor.after());
    tr.insert(at, $cursor.parent.content);
    tr.setSelection(TextSelection.create(tr.doc, at));
    dispatch(tr.scrollIntoView());
  }
  return true;
}

// Backspace at the start of the line after a table goes into its last cell,
// as in 1.x, taking the line away when it is empty; the default selected
// the whole table, and typing then emptied every cell.
export function backspaceAfterTable(state, dispatch) {
  const {$cursor} = state.selection;
  if (!$cursor || $cursor.parentOffset || $cursor.depth < 1) return false;
  const before = state.doc.resolve($cursor.before()).nodeBefore;
  if (!before || before.type !== table) return false;
  if (dispatch) {
    const tr = state.tr;
    const line = $cursor.before();
    if (!$cursor.parent.content.size) tr.delete(line, $cursor.after());
    tr.setSelection(Selection.findFrom(tr.doc.resolve(line - 1), -1, true) || tr.selection);
    dispatch(tr.scrollIntoView());
  }
  return true;
}


// Enter in a list: a new item of the same kind, an open to-do after a done
// one. An empty item ends the list (splitListItem lifts it).
export function splitItem(state, dispatch) {
  const item = ancestor(state, list_item);
  if (!item) return false;
  return splitListItem(list_item, item.node.attrs.checked === null ? null : {checked: false})(state, dispatch);
}

// Backspace at the start of an item outdents it, or ends the list at its top.
// Delete at the end of an item's line joins the next item's line to it, as
// in 1.x and Confluence, and what that item held after its line (a nested
// list) comes along; the default made it a second paragraph of the item.
export function deleteInItem(state, dispatch) {
  const {$cursor} = state.selection;
  if (!$cursor || $cursor.parentOffset !== $cursor.parent.content.size) return false;
  const d = $cursor.depth - 1;
  if (d < 1 || $cursor.node(d).type !== list_item || $cursor.index(d) !== $cursor.node(d).childCount - 1) return false;
  const itemEnd = $cursor.after(d);
  const next = state.doc.nodeAt(itemEnd);
  if (!next || next.type !== list_item || next.firstChild.type !== paragraph) return false;
  if (dispatch) {
    const rest = next.content.cut(next.firstChild.nodeSize);
    const tr = state.tr.delete(itemEnd, itemEnd + next.nodeSize);
    tr.insert($cursor.pos, next.firstChild.content);
    if (rest.size) tr.insert(tr.mapping.map(itemEnd - 1, -1), rest);
    tr.setSelection(TextSelection.create(tr.doc, $cursor.pos));
    dispatch(tr.scrollIntoView());
  }
  return true;
}

export function backspaceInItem(state, dispatch) {
  const {$cursor} = state.selection;
  if (!$cursor || $cursor.parentOffset > 0) return false;
  const item = ancestor(state, list_item);
  if (!item || $cursor.index(item.depth) !== 0) return false;
  return liftListItem(list_item)(state, dispatch);
}

