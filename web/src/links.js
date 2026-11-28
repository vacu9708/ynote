// Links: one kind, a link mark with its address (schema.js). An http or
// https address typed, as a space or Enter after it ends it, or pasted
// becomes one, as in Confluence; Link… gives one text of its own. A click
// opens a link; its right-click menu changes it or takes it away, which
// leaves its text as text. Notes saved before links were marks have their
// addresses made links once as they open (convert.linkify()).
import {Plugin} from 'prosemirror-state';
import {schema} from './schema.js';

// The same rules as ynote/links.py: a URL runs to a space or a character
// that rarely ends one, and leaves out punctuation that ends the sentence.
const URL_RE = /\bhttps?:\/\/[^\s<>"'`]+/gi;
const TRAILING = '.,;:!?\'"]}>';

export function trimUrl(url) {
  for (;;) {
    const last = url[url.length - 1];
    if (last && TRAILING.includes(last)) url = url.slice(0, -1);
    else if (last === ')' && url.split('(').length < url.split(')').length) url = url.slice(0, -1);
    else return url;
  }
}

export function findLinks(text) {
  const links = [];
  for (const m of text.matchAll(URL_RE)) {
    const url = trimUrl(m[0]);
    if (url.includes('://') && !url.endsWith('://')) links.push({from: m.index, to: m.index + url.length, url});
  }
  return links;
}

// The addresses a change made links: those pasted, and a typed one once a
// space or Enter typed right after it ends it, not while it is typed, as
// "https://e." is an address too. Text already a link, or code, stays.
function linkify(trs, state) {
  const ranges = [];
  for (const tr of trs) {
    if (!tr.docChanged || tr.getMeta('addToHistory') === false) continue;
    const pasted = tr.getMeta('uiEvent') === 'paste';
    tr.steps.forEach((step, i) => {
      const after = tr.mapping.slice(i + 1);
      step.getMap().forEach((_a, _b, from, to) => {
        ranges.push({from: after.map(from, -1), to: after.map(to, 1), pasted});
      });
    });
  }
  if (!ranges.length) return null;
  const link = schema.marks.link;
  const tr = state.tr;
  for (const {from, to, pasted} of ranges) {
    const typed = state.doc.textBetween(Math.min(from, to), Math.max(from, to), '\n', '\n');
    if (!pasted && !/^\s/.test(typed)) continue;
    const lo = Math.max(0, Math.min(from, to) - 1), hi = Math.min(state.doc.content.size, Math.max(from, to) + 1);
    state.doc.nodesBetween(lo, hi, (node, pos) => {
      if (node.type.spec.code) return false;
      if (!node.isTextblock) return true;
      let text = '';
      node.forEach(child => {
        const skip = !child.isText || child.marks.some(m => m.type === link || m.type === schema.marks.code);
        text += skip ? '\ufffc'.repeat(child.nodeSize) : child.text;
      });
      for (const url of findLinks(text)) {
        const a = pos + 1 + url.from, b = pos + 1 + url.to;
        if (pasted ? !(a < to && b > from) : b !== from) continue;
        tr.addMark(a, b, link.create({href: url.url}));
      }
      return false;
    });
  }
  return tr.steps.length ? tr : null;
}

export function linksPlugin(open) {
  return new Plugin({
    appendTransaction(trs, _old, state) { return linkify(trs, state); },
    props: {
      handleClick(view, pos, event) {
        const target = event.target.closest && event.target.closest('.link');
        if (!target || event.button !== 0 || event.shiftKey) return false;
        open(target.dataset.url);
        return true;
      },
    },
  });
}
