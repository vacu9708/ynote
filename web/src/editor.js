// A note's editor: ProseMirror with Ynote's content, keys, and typed
// Markdown. The app talks to it through window.ynote (see bridge.js).
import {EditorState, Plugin, Selection, TextSelection} from 'prosemirror-state';
import {EditorView, Decoration, DecorationSet} from 'prosemirror-view';
import {Node} from 'prosemirror-model';
import {keymap} from 'prosemirror-keymap';
import {baseKeymap, chainCommands, splitBlock} from 'prosemirror-commands';
import {history, undo, redo} from 'prosemirror-history';
import {inputRules, InputRule, wrappingInputRule, textblockTypeInputRule} from 'prosemirror-inputrules';
import {findWrapping} from 'prosemirror-transform';
import {tableEditing, goToNextCell} from 'prosemirror-tables';
import {gapCursor, GapCursor} from 'prosemirror-gapcursor';
import {dropCursor} from 'prosemirror-dropcursor';
import {schema} from './schema.js';
import * as cmd from './commands.js';
import {CodeBlockView, ExpandView, ListItemView} from './views.js';
import {linksPlugin} from './links.js';
import {findPlugin} from './find.js';
import {structurePlugin, headerBoldPlugin, codeClicksPlugin, normalize} from './structure.js';
import {slashPlugin} from './slash.js';

const {paragraph, heading, code_block, blockquote, horizontal_rule, bullet_list,
  list_item, expand, expand_title} = schema.nodes;

// --- Typed Markdown, each its own undo step, as the menus show it ---------

function markRule(regexp, mark) {
  return new InputRule(regexp, (state, match, start, end) => {
    const tr = state.tr.replaceWith(start, end, schema.text(match[1], [mark.create()]));
    tr.removeStoredMark(mark);
    return tr;
  });
}

// "[ ] " or "[x] " makes a to-do, also at the start of a bullet item.
const todoRule = new InputRule(/^\s*\[([ xX]?)\]\s$/, (state, match, start, end) => {
  const checked = match[1].toLowerCase() === 'x';
  const tr = state.tr.delete(start, end);
  const $start = tr.doc.resolve(start);
  const item = $start.depth >= 2 && $start.node(-1).type === list_item && $start.index(-1) === 0;
  if (item) return tr.setNodeMarkup($start.before(-1), null, {checked});
  const range = $start.blockRange();
  const wrapping = range && findWrapping(range, bullet_list);
  if (!wrapping) return null;
  tr.wrap(range, wrapping);
  const $in = tr.doc.resolve(tr.mapping.map(start));
  for (let d = $in.depth; d > 0; d--) {
    if ($in.node(d).type === list_item) return tr.setNodeMarkup($in.before(d), null, {checked});
  }
  return tr;
});

const dividerRule = new InputRule(/^---$/, (state, match, start, end) => {
  const $start = state.doc.resolve(start);
  if ($start.parent.type !== paragraph || $start.parent.content.size !== 3) return null;
  const tr = state.tr.replaceWith($start.before(), $start.after(),
    [horizontal_rule.create(), paragraph.create()]);
  return tr.setSelection(TextSelection.create(tr.doc, $start.before() + 2));
});

const rules = inputRules({rules: [
  wrappingInputRule(/^\s*[-*]\s$/, bullet_list),
  todoRule,
  wrappingInputRule(/^>\s$/, blockquote),
  textblockTypeInputRule(/^#{1,6}\s$/, heading),
  textblockTypeInputRule(/^```$/, code_block),
  dividerRule,
  markRule(/(?<![*\\])\*\*([^*\s](?:[^*]*[^*\s])?)\*\*$/, schema.marks.strong),
  markRule(/(?<![`\\])`([^`]+)`$/, schema.marks.code),
]});

// --- Keys ------------------------------------------------------------------

// Enter on an empty line of an expand makes another line in it, as in
// Confluence; the default would take the line out of the expand.
function enterInExpand(state, dispatch) {
  const {$cursor} = state.selection;
  if (!$cursor || $cursor.parent.type !== paragraph || $cursor.parent.content.size) return false;
  if ($cursor.depth < 2 || $cursor.node(-1).type !== expand) return false;
  return splitBlock(state, dispatch);
}

// Up and Down out of a code block's first or last line go to the line
// above or below it, which WebKit does not do by itself.
function outOfCode(dir) {
  return (state, dispatch) => {
    const {$cursor} = state.selection;
    if (!$cursor || $cursor.parent.type !== code_block) return false;
    const text = $cursor.parent.textContent;
    const rest = dir === 'down' ? text.slice($cursor.parentOffset) : text.slice(0, $cursor.parentOffset);
    if (rest.includes('\n')) return false;
    const pos = dir === 'down' ? $cursor.after() : $cursor.before();
    const $pos = state.doc.resolve(pos);
    const sel = Selection.findFrom($pos, dir === 'down' ? 1 : -1, true);
    if (!sel) return false;
    if (dispatch) dispatch(state.tr.setSelection(sel).scrollIntoView());
    return true;
  };
}

// Right at the very end of a table, in its last cell, puts the cursor after
// the table, where typing starts a line, as in Confluence: the way to go on
// writing below a table at the end of an expand, as Down leaves the expand.
function rightOutOfTable(state, dispatch, view) {
  const {$cursor} = state.selection;
  if (!$cursor || !view || !view.endOfTextblock('right')) return false;
  for (let d = $cursor.depth; d > 0; d--) {
    if ($cursor.node(d).type.name !== 'table') continue;
    // Only at the end of the table's last cell's last line.
    const last = Selection.findFrom(state.doc.resolve($cursor.end(d)), -1, true);
    if (!last || last.head !== $cursor.pos) return false;
    const $after = state.doc.resolve($cursor.after(d));
    if (dispatch) {
      const sel = GapCursor.valid($after) ? new GapCursor($after) : null;
      if (sel) dispatch(state.tr.setSelection(sel).scrollIntoView());
      else return cmd.leaveTable(state, dispatch);
    }
    return true;
  }
  return false;
}

// Backspace at the start of an expand's title takes the expand away and
// keeps what it holds.
function unwrapExpand(state, dispatch) {
  const {$cursor} = state.selection;
  if (!$cursor || $cursor.parent.type !== expand_title || $cursor.parentOffset) return false;
  if (dispatch) {
    const found = cmd.ancestor(state, expand);
    const title = $cursor.parent;
    const blocks = [];
    if (title.content.size) blocks.push(paragraph.create(null, title.content));
    found.node.forEach((child, _, i) => { if (i > 0) blocks.push(child); });
    const tr = state.tr.replaceWith(found.pos, found.pos + found.node.nodeSize, blocks);
    tr.setSelection(TextSelection.near(tr.doc.resolve(found.pos + 1)));
    dispatch(tr.scrollIntoView());
  }
  return true;
}

function insertTab(state, dispatch) {
  if (dispatch) dispatch(state.tr.insertText('\t').scrollIntoView());
  return true;
}

const keys = keymap({
  'Mod-z': undo, 'Mod-y': redo, 'Shift-Mod-z': redo,
  'Mod-b': cmd.toggleBold,
  'Mod-h': cmd.toggleHeading,
  'Mod-e': cmd.toggleInlineCode,
  'Mod-8': cmd.toggleBullet,
  'Mod-9': cmd.toggleChecklist,
  'Shift-Mod-c': cmd.toggleCodeBlock,
  'Mod-Enter': chainCommands(cmd.toggleTodos, cmd.toggleExpandAtTitle),
  'Tab': chainCommands(cmd.nextCellOrRow, cmd.indentItem, insertTab),
  'Shift-Tab': chainCommands(goToNextCell(-1), cmd.outdentItem, () => true),
  'Escape': cmd.leaveTable,
  'Enter': chainCommands(cmd.splitItem, enterInExpand),
  'ArrowDown': outOfCode('down'),
  'ArrowRight': rightOutOfTable,
  'ArrowUp': outOfCode('up'),
  'Backspace': chainCommands(cmd.backspaceInItem, unwrapExpand),
});

// --- The view --------------------------------------------------------------

// A new note says what it takes: shown while the note is one empty line.
const PLACEHOLDER = 'Type, or / for commands';
const placeholder = new Plugin({props: {decorations(state) {
  const doc = state.doc;
  if (doc.childCount !== 1 || doc.firstChild.type !== paragraph || doc.firstChild.content.size) return null;
  return DecorationSet.create(doc, [Decoration.node(0, doc.firstChild.nodeSize, {class: 'empty', 'data-placeholder': PLACEHOLDER})]);
}}});

export function createEditor(place, {onChange, onOpenLink, onFocus, onCopy, onSlashKey, onClipboard}) {
  // Copy, cut, and paste go to the app, which puts Markdown on the
  // clipboard; handled here, in turn with the keys before them, so a copy
  // right after Ctrl+A copies what it selected.
  const clipboardKeys = keymap({
    'Mod-c': () => { onClipboard('copy'); return true; },
    'Mod-x': () => { onClipboard('cut'); return true; },
    'Mod-v': () => { onClipboard('paste'); return true; },
    'Shift-Mod-v': () => { onClipboard('paste-plain'); return true; },
  });
  const changes = new Plugin({
    view: () => ({
      update(view, prev) {
        if (!view.state.doc.eq(prev.doc)) onChange(view.state.doc);
      },
    }),
  });
  const plugins = [
    slashPlugin(key => onSlashKey(key)), clipboardKeys, rules, keys, keymap(baseKeymap),
    history(), tableEditing(), gapCursor(), dropCursor({color: '#2D6BE0', width: 2}),
    linksPlugin(onOpenLink), placeholder, findPlugin, structurePlugin, headerBoldPlugin, codeClicksPlugin,
    changes,
  ];
  const view = new EditorView(place, {
    state: EditorState.create({schema, plugins}),
    nodeViews: {
      expand: (node, v, getPos) => new ExpandView(node, v, getPos),
      list_item: (node, v, getPos) => new ListItemView(node, v, getPos),
      code_block: (node, v, getPos) => new CodeBlockView(node, v, getPos, onCopy),
    },
    handleDOMEvents: {focus: () => { onFocus && onFocus(); return false; }},
  });
  return {
    view,
    // Replaces the content, as a new start: no undo back to before it.
    setDoc(json) {
      let doc;
      try {
        doc = Node.fromJSON(schema, json);
        doc.check();
      } catch (e) {
        console.error('ynote: the note could not be read', e);
        doc = schema.node('doc', null, [paragraph.create()]);
      }
      view.updateState(EditorState.create({doc, plugins}));
      // A note saved before a rule, or by 1.x, keeps it from the start.
      const tr = normalize(view.state);
      if (tr) view.updateState(view.state.apply(tr));
    },
    doc: () => view.state.doc,
    run(command) {
      const done = command(view.state, view.dispatch, view);
      view.focus();
      return done;
    },
  };
}

