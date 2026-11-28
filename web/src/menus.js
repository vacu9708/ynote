// What the note's menus hold, as the popup window shows them (menu.js).
// Rows come from the actions (actions.js), so they show the same name,
// icon, Markdown, and keys as everywhere else.
import {isInTable, addRowBefore, addRowAfter, addColumnBefore, addColumnAfter,
  deleteRow, deleteColumn, deleteTable} from 'prosemirror-tables';
import {ACTION, menuRow, MORE} from './actions.js';
import {PALETTE} from './palette.js';

// ＋: the toolbar's actions that did not fit, then the rest.
export function moreMenu(ctx, overflow) {
  const rows = overflow.map(id => menuRow(ACTION[id], ctx));
  if (rows.length) rows.push({sep: true});
  return rows.concat(MORE.map(id => menuRow(ACTION[id], ctx)));
}

// The note's menu: how it looks, what to do with it, then Ynote's.
export function noteMenu(ctx, props) {
  const row = (id, extra) => menuRow(ACTION[id], ctx, extra);
  return [
    {swatches: Object.entries(PALETTE).map(([name, c]) => ({
      id: 'color', value: name, color: c.paper, label: name[0].toUpperCase() + name.slice(1),
      on: name === props.color}))},
    {slider: {id: 'opacity', label: 'Opacity', value: props.opacity, min: 0.2, max: 1, step: 0.05}},
    {toggle: {id: 'solid-in-use', label: 'Solid while in use', value: props.solidInUse}},
    {stepper: {id: 'font-size', label: 'Font size', value: props.fontSize, min: 8, max: 32}},
    {sep: true},
    row('new-note'),
    row('rename'),
    row('copy-markdown'),
    row('delete'),
    {sep: true},
    row('hidden-notes', {md: String(props.hiddenCount || 0)}),
    row('help'),
    ...(props.autostart && props.autostart.available
      ? [row('autostart', {check: !!props.autostart.enabled})] : []),
    row('quit'),
  ];
}

// Right-click in the text: editing first, then what is under the click.
export function contextMenu(state, {link, hasSelection}) {
  const items = [];
  if (link) {
    items.push({id: 'open-link', icon: 'open', label: 'Open link', keys: ['Ctrl', 'Click']},
      {id: 'copy-link', icon: 'link', label: 'Copy link address'}, {sep: true});
  }
  items.push(
    {id: 'cut', icon: 'cut', label: 'Cut', keys: ['Ctrl', 'X'], disabled: !hasSelection},
    {id: 'copy', icon: 'copy', label: 'Copy', keys: ['Ctrl', 'C'], disabled: !hasSelection},
    {id: 'paste', icon: 'paste', label: 'Paste', keys: ['Ctrl', 'V']},
    {id: 'paste-plain', icon: 'text', label: 'Paste as plain text', keys: ['Ctrl', '⇧', 'V']},
  );
  if (isInTable(state)) {
    items.push({section: 'Table'},
      {id: 'row-above', icon: 'rowAbove', label: 'Insert row above'},
      {id: 'row-below', icon: 'rowBelow', label: 'Insert row below'},
      {id: 'col-left', icon: 'colLeft', label: 'Insert column left'},
      {id: 'col-right', icon: 'colRight', label: 'Insert column right'},
      {id: 'delete-row', icon: 'minus', label: 'Delete row', danger: true},
      {id: 'delete-col', icon: 'minus', label: 'Delete column', danger: true},
      {id: 'delete-table', icon: 'trash', label: 'Delete table', danger: true});
  }
  return items;
}

export const TABLE_ACTIONS = {
  'row-above': addRowBefore, 'row-below': addRowAfter,
  'col-left': addColumnBefore, 'col-right': addColumnAfter,
  // Deleting the last row or column deletes the table, as in 1.x.
  'delete-row': (s, d) => deleteRow(s, d) || deleteTable(s, d),
  'delete-col': (s, d) => deleteColumn(s, d) || deleteTable(s, d),
  'delete-table': deleteTable,
};
