// Find in a note (Ctrl+F): every match lit, the current one brighter, as
// a browser or VS Code finds. Matches are found in each block's text, so a
// match may cross bold or code, but not a line. A match in a folded expand
// opens it while it is the current match, and it folds again after.
import {Plugin, PluginKey, TextSelection} from 'prosemirror-state';
import {Decoration, DecorationSet} from 'prosemirror-view';
import {setExpandOpen} from './commands.js';

export const findKey = new PluginKey('find');

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// The pattern for a query, or null when it finds nothing or, as a regular
// expression, does not compile; error says why.
export function pattern(query, {caseSensitive, regex}) {
  if (!query) return {re: null};
  try {
    return {re: new RegExp(regex ? query : escapeRegExp(query), caseSensitive ? 'gu' : 'giu')};
  } catch (e) {
    return {re: null, error: e.message};
  }
}

export function findMatches(doc, re) {
  const matches = [];
  if (!re) return matches;
  doc.descendants((node, pos) => {
    if (!node.isTextblock) return true;
    let text = '';
    node.forEach(child => { text += child.isText ? child.text : '￼'; });
    re.lastIndex = 0;
    for (let m = re.exec(text); m; m = re.exec(text)) {
      if (m[0] === '') { re.lastIndex++; continue; }
      matches.push({from: pos + 1 + m.index, to: pos + 1 + m.index + m[0].length});
    }
    return false;
  });
  return matches;
}

const EMPTY = {query: '', caseSensitive: false, regex: false, matches: [], current: -1, error: null};

export const findPlugin = new Plugin({
  key: findKey,
  state: {
    init: () => EMPTY,
    apply(tr, value) {
      const meta = tr.getMeta(findKey);
      let next = meta ? {...value, ...meta} : value;
      if (!next.query) return {...EMPTY, caseSensitive: next.caseSensitive, regex: next.regex};
      if (meta || tr.docChanged) {
        const {re, error} = pattern(next.query, next);
        const matches = findMatches(tr.doc, re);
        let current = 'current' in (meta || {}) ? meta.current : next.current;
        if (!matches.length) current = -1;
        else if (current < 0 || current >= matches.length) current = 0;
        next = {...next, matches, current, error: error || null};
      }
      return next;
    },
  },
  props: {
    decorations(state) {
      const {matches, current} = findKey.getState(state);
      if (!matches.length) return null;
      return DecorationSet.create(state.doc, matches.map((m, i) =>
        Decoration.inline(m.from, m.to, {class: i === current ? 'find-hit current' : 'find-hit'})));
    },
  },
});

// The expands opened to show a match, folded again when it moves on.
let opened = [];

function foldBack(view, keep = []) {
  if (!opened.length) return;
  const tr = view.state.tr;
  for (const pos of opened) {
    if (keep.includes(pos)) continue;
    const node = tr.doc.nodeAt(pos);
    if (node && node.type.name === 'expand' && node.attrs.open) setExpandOpen(tr, pos, false);
  }
  opened = opened.filter(pos => keep.includes(pos));
  if (tr.docChanged || tr.steps.length) view.dispatch(tr);
}

function expandsAround(doc, pos) {
  const $pos = doc.resolve(pos);
  const around = [];
  for (let d = $pos.depth; d > 0; d--) {
    if ($pos.node(d).type.name === 'expand') around.push($pos.before(d));
  }
  return around;
}

// Show the current match: open the folded expands around it, scroll to it.
export function reveal(view) {
  const {matches, current} = findKey.getState(view.state);
  const match = matches[current];
  if (!match) { foldBack(view); return; }
  const around = expandsAround(view.state.doc, match.from);
  foldBack(view, around);
  const tr = view.state.tr;
  for (const pos of around) {
    if (!tr.doc.nodeAt(pos).attrs.open) {
      setExpandOpen(tr, pos, true);
      opened.push(pos);
    }
  }
  if (tr.steps.length) view.dispatch(tr);
  const node = view.domAtPos(match.from).node;
  const el = node.nodeType === 1 ? node : node.parentElement;
  if (el) el.scrollIntoView({block: 'nearest'});
}

export function setFind(view, props) {
  view.dispatch(view.state.tr.setMeta(findKey, props));
  reveal(view);
}

export function step(view, delta) {
  const {matches, current} = findKey.getState(view.state);
  if (!matches.length) return;
  setFind(view, {current: (current + delta + matches.length) % matches.length});
}

// Ends finding: the matches unlit and the current match selected, as a
// browser leaves it. The expands opened for other matches fold again; the
// current match's stay open, as it is where the cursor is.
export function endFind(view) {
  const {matches, current} = findKey.getState(view.state);
  const match = matches[current];
  foldBack(view, match ? expandsAround(view.state.doc, match.from) : []);
  opened = [];
  const tr = view.state.tr.setMeta(findKey, {query: ''});
  if (match) tr.setSelection(TextSelection.create(tr.doc, match.from, match.to));
  view.dispatch(tr);
}
