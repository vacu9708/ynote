// http and https addresses in the text show as links, found from the text
// whenever it changes, as in 1.x, so nothing about them is saved. Ctrl+click
// opens one; a plain click only places the cursor.
import {Plugin} from 'prosemirror-state';
import {Decoration, DecorationSet} from 'prosemirror-view';

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

function decorate(doc) {
  const decos = [];
  doc.descendants((node, pos) => {
    if (node.type.spec.code) return false;
    if (!node.isTextblock) return true;
    // Text and images of the block, an image counted as one character.
    let text = '';
    node.forEach(child => { text += child.isText ? child.text : '￼'; });
    for (const {from, to, url} of findLinks(text)) {
      decos.push(Decoration.inline(pos + 1 + from, pos + 1 + to,
        {class: 'link', 'data-url': url, title: 'Ctrl+click to open'}));
    }
    return false;
  });
  return DecorationSet.create(doc, decos);
}

export function linksPlugin(open) {
  return new Plugin({
    state: {
      init: (_, state) => decorate(state.doc),
      apply: (tr, old) => tr.docChanged ? decorate(tr.doc) : old,
    },
    props: {
      decorations(state) { return this.getState(state); },
      handleClick(view, pos, event) {
        if (!event.ctrlKey) return false;
        const link = event.target.closest && event.target.closest('.link');
        if (!link) return false;
        open(link.dataset.url);
        return true;
      },
    },
  });
}
