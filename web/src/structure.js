// Rules the note's content keeps after every change, and clicks in code.
import {Plugin, PluginKey, TextSelection} from 'prosemirror-state';
import {Decoration, DecorationSet} from 'prosemirror-view';
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

// A drag that starts outside a table and passes over one lost where it
// started in WebKit, which moved the start to the table's edge, and showed
// so while dragging. The start is kept as the button goes down; while the
// drag crosses a table, the browser's selection is hidden and the range from
// the start to the pointer is drawn instead, and on release it becomes the
// selection.
const dragKey = new PluginKey('dragAcrossTables');

function crossesTable(doc, a, b) {
  let found = false;
  doc.nodesBetween(Math.min(a, b), Math.max(a, b), node => {
    if (node.type.name === 'table') found = true;
    return !found;
  });
  return found;
}

export const dragAcrossTablesPlugin = new Plugin({
  key: dragKey,
  state: {
    init: () => null,
    apply(tr, range) {
      const meta = tr.getMeta(dragKey);
      if (meta !== undefined) return meta;
      return range && {from: tr.mapping.map(range.from), to: tr.mapping.map(range.to)};
    },
  },
  props: {
    decorations(state) {
      const range = dragKey.getState(state);
      if (!range || range.from === range.to) return null;
      const from = Math.min(range.from, range.to), to = Math.max(range.from, range.to);
      const decos = [Decoration.inline(from, to, {class: 'drag-selected'})];
      // Cells wholly inside, as an empty cell has no text to mark.
      state.doc.nodesBetween(from, to, (node, pos) => {
        if ((node.type.name === 'table_cell' || node.type.name === 'table_header')
            && pos >= from && pos + node.nodeSize <= to) {
          decos.push(Decoration.node(pos, pos + node.nodeSize, {class: 'drag-selected-cell'}));
        }
        return true;
      });
      return DecorationSet.create(state.doc, decos);
    },
    handleDOMEvents: {
      mousedown(view, event) {
        if (event.button !== 0 || event.shiftKey || event.detail > 1) return false;
        if (event.target.closest && event.target.closest('td, th')) return false;
        const at = view.posAtCoords({left: event.clientX, top: event.clientY});
        if (!at) return false;
        const start = {pos: at.pos, x: event.clientX, y: event.clientY};
        let shown = false;
        const move = e => {
          if (!(e.buttons & 1)) return;
          if (Math.abs(e.clientX - start.x) + Math.abs(e.clientY - start.y) < 4) return;
          const here = view.posAtCoords({left: e.clientX, top: e.clientY});
          if (!here) return;
          const crossing = crossesTable(view.state.doc, start.pos, here.pos);
          if (crossing || shown) {
            shown = crossing;
            view.dom.classList.toggle('drag-crossing', crossing);
            view.dispatch(view.state.tr.setMeta(dragKey, crossing ? {from: start.pos, to: here.pos} : null));
          }
        };
        const up = e => {
          document.removeEventListener('mousemove', move, true);
          document.removeEventListener('mouseup', up, true);
          view.dom.classList.remove('drag-crossing');
          if (shown) view.dispatch(view.state.tr.setMeta(dragKey, null));
          if (Math.abs(e.clientX - start.x) + Math.abs(e.clientY - start.y) < 4) return;
          // After ProseMirror has read the browser's selection.
          setTimeout(() => {
            const {state} = view;
            const head = state.selection.head;
            if (start.pos > state.doc.content.size || !crossesTable(state.doc, start.pos, head)) return;
            view.dispatch(state.tr.setSelection(
              TextSelection.between(state.doc.resolve(start.pos), state.doc.resolve(head))));
          }, 0);
        };
        document.addEventListener('mousemove', move, true);
        document.addEventListener('mouseup', up, true);
        return false;
      },
    },
  },
});
