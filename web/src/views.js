// How an expand and a to-do are drawn: each has a button that is not text,
// beside the text it belongs to.
import {setExpandOpen} from './commands.js';

const SVG = 'http://www.w3.org/2000/svg';

// A 2px stroke icon, as the bars draw theirs.
export function strokeIcon(paths, size = 16) {
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  for (const d of [].concat(paths)) {
    const path = document.createElementNS(SVG, 'path');
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  return svg;
}

export const CHEVRON_DOWN = 'M6 9l6 6 6-6';

// A button inside the editor that acts on click without moving the cursor
// or taking focus from the text.
function inertButton(className, onClick) {
  const button = document.createElement('span');
  button.className = className;
  button.contentEditable = 'false';
  button.setAttribute('role', 'button');
  button.addEventListener('mousedown', event => {
    if (event.button !== 0) return;
    event.preventDefault();
    onClick();
  });
  return button;
}

export class ExpandView {
  constructor(node, view, getPos) {
    this.node = node;
    this.dom = document.createElement('div');
    this.dom.className = 'expand';
    this.toggle = inertButton('expand-toggle', () => {
      view.dispatch(setExpandOpen(view.state.tr, getPos(), !this.node.attrs.open));
    });
    this.toggle.appendChild(strokeIcon(CHEVRON_DOWN, 16));
    this.contentDOM = document.createElement('div');
    this.contentDOM.className = 'expand-content';
    this.dom.append(this.toggle, this.contentDOM);
    this.render();
  }
  render() {
    this.dom.classList.toggle('open', this.node.attrs.open);
    this.toggle.title = this.node.attrs.open ? 'Fold' : 'Open';
  }
  update(node) {
    if (node.type !== this.node.type) return false;
    this.node = node;
    this.render();
    return true;
  }
  ignoreMutation(mutation) {
    return !this.contentDOM.contains(mutation.target) || mutation.type === 'attributes' && mutation.target === this.dom;
  }
  stopEvent(event) { return this.toggle.contains(event.target); }
}

export class ListItemView {
  constructor(node, view, getPos) {
    this.node = node;
    this.dom = document.createElement('li');
    this.box = inertButton('todo-box', () => {
      const pos = getPos();
      view.dispatch(view.state.tr.setNodeMarkup(pos, null,
        {...this.node.attrs, checked: !this.node.attrs.checked}));
    });
    this.contentDOM = document.createElement('div');
    this.contentDOM.className = 'item-content';
    this.dom.append(this.box, this.contentDOM);
    this.render();
  }
  render() {
    const {checked} = this.node.attrs;
    this.dom.className = checked === null ? '' : checked ? 'todo done' : 'todo';
    this.box.hidden = checked === null;
  }
  update(node) {
    if (node.type !== this.node.type) return false;
    this.node = node;
    this.render();
    return true;
  }
  ignoreMutation(mutation) {
    return !this.contentDOM.contains(mutation.target) || mutation.type === 'attributes' && mutation.target === this.dom;
  }
  stopEvent(event) { return this.box.contains(event.target); }
}
