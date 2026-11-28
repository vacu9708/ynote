// Rules the note's content keeps after every change, and clicks in code.
import {Plugin, TextSelection} from 'prosemirror-state';
import {schema} from './schema.js';

const {paragraph, table, table_header, table_cell, code_block} = schema.nodes;

// The first row of a table is its header, also after a row is deleted or
// moved, so a table never loses its header and has no header in its body.
function fixHeaders(doc, tr) {
  doc.descendants((node, pos) => {
    if (node.type !== table) return true;
    node.forEach((row, rowOffset, rowIndex) => {
      row.forEach((cell, cellOffset) => {
        const want = rowIndex === 0 ? table_header : table_cell;
        if (cell.type !== want) {
          tr.setNodeMarkup(pos + 1 + rowOffset + 1 + cellOffset, want, cell.attrs, cell.marks);
        }
      });
    });
    return false;
  });
}

// The rules, as a transaction that applies them to state, or null.
export function normalize(state) {
  const tr = state.tr;
  fixHeaders(state.doc, tr);
  // A line after the last block, so the cursor can always go below a code
  // block, an expand, or a table at the end, as in Confluence.
  const last = tr.doc.lastChild;
  if (!last || last.type !== paragraph) tr.insert(tr.doc.content.size, paragraph.create());
  return tr.steps.length ? tr.setMeta('addToHistory', false) : null;
}

export const structurePlugin = new Plugin({
  appendTransaction(trs, _old, state) {
    return trs.some(tr => tr.docChanged) ? normalize(state) : null;
  },
});

// A header cell is bold until bold is turned off in it: typing in an empty
// line of one starts bold, as in 1.x and Confluence.
export const headerBoldPlugin = new Plugin({
  appendTransaction(trs, _old, state) {
    if (!trs.some(tr => tr.selectionSet || tr.docChanged)) return null;
    const {$cursor} = state.selection;
    if (!$cursor || $cursor.parent.content.size || state.storedMarks) return null;
    for (let d = $cursor.depth; d > 0; d--) {
      if ($cursor.node(d).type === table_header) {
        return state.tr.setStoredMarks([schema.marks.strong.create()]);
      }
      if ($cursor.node(d).type === table_cell) return null;
    }
    return null;
  },
});

// In a code block, a double click selects the line clicked, which is
// usually one command, and a triple click the whole block, as in 1.x.
export const codeClicksPlugin = new Plugin({
  props: {
    handleDoubleClick(view, pos) {
      const $pos = view.state.doc.resolve(pos);
      if ($pos.parent.type !== code_block) return false;
      const text = $pos.parent.textContent;
      const at = $pos.parentOffset;
      const start = text.lastIndexOf('\n', at - 1) + 1;
      let end = text.indexOf('\n', at);
      if (end < 0) end = text.length;
      const base = $pos.start();
      view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, base + start, base + end)));
      return true;
    },
    handleTripleClick(view, pos) {
      const $pos = view.state.doc.resolve(pos);
      if ($pos.parent.type !== code_block) return false;
      view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc, $pos.start(), $pos.end())));
      return true;
    },
  },
});
