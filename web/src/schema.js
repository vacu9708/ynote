// The kinds of content a note holds. A note is saved as this schema's JSON
// (ynote/convert.py turns a note of Ynote 1.x into it), so a node or an
// attribute is only ever added, never renamed.
import {Schema} from 'prosemirror-model';
import {tableNodes} from 'prosemirror-tables';

// Where the note's image files are, as a file:// URL ending in a slash. The
// app sets it before the note's content is loaded.
let imagesUrl = '';
export function setImagesUrl(url) { imagesUrl = url; }
export const imageSrc = file => imagesUrl + encodeURIComponent(file);

const nodes = {
  doc: {content: 'block+'},

  paragraph: {
    content: 'inline*', group: 'block cellblock',
    parseDOM: [{tag: 'p'}],
    toDOM: () => ['p', 0],
  },

  // One level, as Ynote has one heading. A pasted h2 or h3 becomes one too.
  heading: {
    content: 'inline*', group: 'block cellblock', defining: true,
    parseDOM: ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'].map(tag => ({tag})),
    toDOM: () => ['h1', 0],
  },

  code_block: {
    content: 'text*', marks: '', group: 'block cellblock', code: true, defining: true,
    parseDOM: [{tag: 'pre', preserveWhitespace: 'full'}],
    toDOM: () => ['pre', ['code', 0]],
  },

  blockquote: {
    content: 'block+', group: 'block cellblock', defining: true,
    parseDOM: [{tag: 'blockquote'}],
    toDOM: () => ['blockquote', 0],
  },

  horizontal_rule: {
    group: 'block cellblock',
    parseDOM: [{tag: 'hr'}],
    toDOM: () => ['hr'],
  },

  // A bullet and a to-do are items of the same list, as in Ynote 1.x, where
  // each line had its own marker: checked is null for a bullet.
  bullet_list: {
    content: 'list_item+', group: 'block cellblock',
    parseDOM: [{tag: 'ul'}, {tag: 'ol'}],
    toDOM: () => ['ul', 0],
  },
  list_item: {
    content: 'paragraph block*', defining: true,
    attrs: {checked: {default: null}},
    parseDOM: [{
      tag: 'li',
      getAttrs(dom) {
        const box = dom.getAttribute('data-checked')
          ?? (dom.querySelector(':scope > input[type=checkbox]') ? String(dom.querySelector(':scope > input').checked) : null);
        return {checked: box === null ? null : box === 'true'};
      },
    }],
    toDOM: node => node.attrs.checked === null
      ? ['li', 0]
      : ['li', {class: 'todo', 'data-checked': String(node.attrs.checked)}, 0],
  },

  // A section that folds away, with a title, as in Confluence. The node view
  // in editor.js draws its button and hides what it holds when folded.
  expand: {
    content: 'expand_title block+', group: 'block cellblock', defining: true,
    attrs: {open: {default: true}},
    parseDOM: [{tag: 'details', getAttrs: dom => ({open: dom.hasAttribute('open')})}],
    toDOM: node => ['details', node.attrs.open ? {open: ''} : {}, 0],
  },
  expand_title: {
    content: 'inline*', defining: true,
    parseDOM: [{tag: 'summary'}],
    toDOM: () => ['summary', 0],
  },

  // An image is a file in the images folder, named by a UUID; name is the
  // name the file had when it was inserted.
  image: {
    inline: true, group: 'inline', draggable: true,
    attrs: {file: {}, name: {default: ''}},
    parseDOM: [{
      tag: 'img[data-file]',
      getAttrs: dom => ({file: dom.getAttribute('data-file'), name: dom.getAttribute('alt') || ''}),
    }],
    toDOM: node => ['img', {src: imageSrc(node.attrs.file), 'data-file': node.attrs.file, alt: node.attrs.name}],
  },

  text: {group: 'inline'},

  // Cells hold anything a note does but a table: every block but a table is
  // also a cellblock.
  ...tableNodes({tableGroup: 'block', cellContent: 'cellblock+', cellAttributes: {}}),
};

const marks = {
  strong: {
    parseDOM: [
      {tag: 'strong'},
      {tag: 'b', getAttrs: dom => dom.style.fontWeight !== 'normal' && null},
      {style: 'font-weight', getAttrs: value => /^(bold(er)?|[6-9]\d\d)$/.test(value) && null},
    ],
    toDOM: () => ['strong', 0],
  },
  code: {
    parseDOM: [{tag: 'code'}],
    toDOM: () => ['code', 0],
  },
};

export const schema = new Schema({nodes, marks});
