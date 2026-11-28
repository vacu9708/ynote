// Every action of a note, in one list: the toolbar, the menus, the / menu,
// and the keyboard shortcuts page are all made from it, so a
// new action shows everywhere with the same name, icon, Markdown, and keys.
//
// An action: {id, label, icon, md, keys, run(ctx), enabled(ctx), active(ctx)}
//   md     the Markdown typed for it, shown beside its name
//   keys   its shortcut as shown, ['Ctrl', 'B']; the editor's keymap
//          (editor.js) and chrome.js bind them
//   run    does it; ctx is {state, dispatch, view, post, chrome}
//   active whether it is on at the cursor, as bold is
// Actions that only the window can do post a message to the app.
import * as cmd from './commands.js';
import {schema} from './schema.js';
import {isInTable} from 'prosemirror-tables';
import {TextSelection} from 'prosemirror-state';

export function markActive(state, mark) {
  const {from, $from, to, empty} = state.selection;
  if (empty) return !!mark.isInSet(state.storedMarks || $from.marks());
  return state.doc.rangeHasMark(from, to, mark);
}

// An editor command as an action's run and enabled. An action that edits
// leaves the keys with the text; others, such as Find, take them.
const edit = command => ({
  run: ({state, dispatch, view}) => command(state, dispatch, view),
  enabled: ({state}) => !!command(state),
  edits: true,
});

const pad = n => String(n).padStart(2, '0');
export function today(now = new Date()) {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}
const insertText = text => ({
  run: ({state, dispatch}) => {
    dispatch(state.tr.insertText(text()).scrollIntoView());
    return true;
  },
  enabled: () => true,
  edits: true,
});

export const ACTIONS = [
  // Text
  {id: 'heading', group: 'Text', label: 'Heading', icon: 'heading', md: '# text', keys: ['Ctrl', 'H'],
    ...edit(cmd.toggleHeading), active: ({state}) => cmd.headingActive(state)},
  {id: 'bold', group: 'Text', label: 'Bold', icon: 'bold', md: '**text**', keys: ['Ctrl', 'B'],
    ...edit(cmd.toggleBold), active: ({state}) => markActive(state, schema.marks.strong)},
  {id: 'code', group: 'Text', label: 'Inline code', icon: 'code', md: '`text`', keys: ['Ctrl', 'E'],
    ...edit(cmd.toggleInlineCode), active: ({state}) => markActive(state, schema.marks.code)},

  // Blocks
  {id: 'bullet', group: 'Insert', label: 'Bullet list', icon: 'bullet', md: '- item', keys: ['Ctrl', '8'],
    ...edit(cmd.toggleBullet)},
  {id: 'checklist', group: 'Insert', label: 'Checklist', icon: 'checklist', md: '[ ] item', keys: ['Ctrl', '9'],
    ...edit(cmd.toggleChecklist)},
  {id: 'codeblock', group: 'Insert', label: 'Code block', icon: 'codeblock', md: '```', keys: ['Ctrl', '⇧', 'C'],
    ...edit(cmd.toggleCodeBlock)},
  {id: 'table', group: 'Insert', label: 'Table', icon: 'table', md: '/table', ...edit(cmd.insertTable)},
  {id: 'quote', group: 'Insert', label: 'Quote', icon: 'quote', md: '> text', ...edit(cmd.toggleQuote)},
  {id: 'divider', group: 'Insert', label: 'Divider', icon: 'divider', md: '---', ...edit(cmd.insertDivider)},
  {id: 'expand', group: 'Insert', label: 'Expand', icon: 'expand', md: '/expand', ...edit(cmd.insertExpand)},
  {id: 'image', group: 'Insert', label: 'Image…', icon: 'image', keys: ['Ctrl', 'V'],
    run: ({post}) => { post({type: 'choose-image'}); return true; }, enabled: () => true},
  {id: 'emoji', group: 'Insert', label: 'Emoji…', icon: 'emoji', md: '/emoji', keys: ['Ctrl', '.'],
    run: ({chrome}) => { chrome.openEmoji(); return true; }, enabled: () => true},
  // Typed as // where a word starts, as in Confluence (editor.js).
  {id: 'date', group: 'Insert', label: 'Date', icon: 'calendar', md: '//', ...insertText(today)},

  // Keys of the editor, for the shortcuts page
  {id: 'todos', group: 'Lists and expands', label: 'Check or uncheck the to-dos', keys: ['Ctrl', 'Enter'], page: true},
  {id: 'indent', group: 'Lists and expands', label: 'Indent or outdent list items', keys: ['Tab', '⇧ Tab'], page: true},
  {id: 'fold', group: 'Lists and expands', label: 'Fold or open an expand, on its title', keys: ['Ctrl', 'Enter'], page: true},
  {id: 'next-cell', group: 'Tables', label: 'Next cell, a new row after the last', keys: ['Tab'], page: true},
  {id: 'leave-table', group: 'Tables', label: 'Out of the table', keys: ['Esc'], page: true},
  {id: 'paste-plain', group: 'Copy and paste', label: 'Paste as plain text', keys: ['Ctrl', '⇧', 'V'],
    run: ({post}) => { post({type: 'edit', command: 'paste-plain'}); return true; }, enabled: () => true},

  // The note
  {id: 'new-note', group: 'Notes', label: 'New note', icon: 'plus', keys: ['Ctrl', 'N'], window: true},
  {id: 'rename', group: 'Notes', label: 'Rename', icon: 'rename', keys: ['F2'],
    run: ({chrome}) => { chrome.editTitle(); return true; }, enabled: () => true},
  // The whole note, for a pull request, a ticket, or a chat.
  {id: 'copy-markdown', group: 'Notes', label: 'Copy as Markdown', icon: 'markdown', keys: ['Ctrl', '⇧', 'M'],
    run: ({state, post}) => {
      post({type: 'clipboard', command: 'copy', slice: state.doc.slice(0, state.doc.content.size).toJSON()});
      return true;
    },
    enabled: () => true},
  {id: 'find', group: 'Notes', label: 'Find', icon: 'search', keys: ['Ctrl', 'F'],
    run: ({chrome}) => { chrome.openFind(); return true; }, enabled: () => true},
  {id: 'collapse', group: 'Notes', label: 'Collapse', icon: 'down', window: true},
  {id: 'pin', group: 'Notes', label: 'Always on top', icon: 'pin', window: true},
  {id: 'hide', group: 'Notes', label: 'Hide note', icon: 'cross', keys: ['Ctrl', 'W'], window: true},
  {id: 'delete', group: 'Notes', label: 'Delete note…', icon: 'trash', danger: true,
    run: ({chrome}) => { chrome.confirmDelete(); return true; }, enabled: () => true},
  {id: 'hidden-notes', group: 'Notes', label: 'Hidden notes', icon: 'hidden', window: true},
  {id: 'help', group: 'Notes', label: 'Keyboard shortcuts', icon: 'help', keys: ['F1'],
    run: ({chrome}) => { chrome.openHelp(); return true; }, enabled: () => true},
  {id: 'autostart', group: 'Notes', label: 'Start at login', icon: 'power', window: true},
  {id: 'quit', group: 'Notes', label: 'Quit Ynote', icon: 'quit', window: true},
  {id: 'snap', group: 'Arranging notes', label: 'Snap to a half of the screen', keys: ['Alt', '← →'], page: true},
  {id: 'step', group: 'Arranging notes', label: 'Step through notes', keys: ['Alt', 'Scroll'], page: true},
  {id: 'maximize', group: 'Arranging notes', label: 'Maximize, on the title bar', keys: ['Double-click'], page: true},
];

export const ACTION = Object.fromEntries(ACTIONS.map(a => [a.id, a]));

export function enabled(action, ctx) {
  if (action.window) return true;
  return action.enabled ? action.enabled(ctx) : false;
}

export function perform(action, ctx) {
  if (action.window) { ctx.post({type: action.id}); return true; }
  return action.run ? action.run(ctx) : false;
}

// An action as a row of a menu (menu.js).
export function menuRow(action, ctx, extra = {}) {
  return {
    id: action.id, icon: action.icon, label: action.label,
    md: action.md, keys: action.keys, danger: action.danger,
    on: action.active ? action.active(ctx) : false,
    disabled: !enabled(action, ctx),
    ...extra,
  };
}

// The toolbar, in order; when the note is too narrow for all of them, those
// last before ＋ go into ＋'s menu first.
export const TOOLBAR = ['heading', 'bold', 'code', '|', 'bullet', 'checklist', 'codeblock', 'table'];
// ＋'s menu, after any of the toolbar's that did not fit.
export const MORE = ['quote', 'divider', 'expand', 'image', 'emoji', 'date'];

// The / menu: every insertable thing and the text formats that make a block.
export const SLASH = ['heading', 'bullet', 'checklist', 'codeblock', 'table', 'quote', 'divider', 'expand',
  'image', 'emoji', 'date'];

export function inTable(state) { return isInTable(state); }
export {TextSelection};
