// How an expand and a to-do are drawn: each has a button that is not text,
// beside the text it belongs to.
import {setExpandOpen} from './commands.js';
import {strokeIcon} from './icons.js';

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
    this.toggle.appendChild(strokeIcon('down', 16));
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

// A code block, with a Copy button that shows while the mouse is over it.
// The button sits over the block by a grid, not by positioning: in a
// positioned box WebKit puts what Korean input composes on a line of its own.
export class CodeBlockView {
  constructor(node, view, getPos, onCopy) {
    this.node = node;
    this.dom = document.createElement('div');
    this.dom.className = 'code-block';
    const pre = document.createElement('pre');
    this.contentDOM = document.createElement('code');
    pre.appendChild(this.contentDOM);
    this.copy = inertButton('code-copy', () => {
      onCopy(this.node.textContent);
      this.copy.classList.add('done');
      this.copyLabel.textContent = 'Copied';
      clearTimeout(this.timer);
      this.timer = setTimeout(() => { this.copy.classList.remove('done'); this.copyLabel.textContent = 'Copy'; }, 1200);
    });
    this.copyLabel = document.createElement('span');
    this.copyLabel.textContent = 'Copy';
    this.copy.append(strokeIcon('copy', 13), this.copyLabel);
    this.copy.title = 'Copy the whole block';
    this.dom.append(pre, this.copy);
  }
  update(node) {
    if (node.type !== this.node.type) return false;
    this.node = node;
    return true;
  }
  ignoreMutation(mutation) {
    return !this.contentDOM.contains(mutation.target);
  }
  stopEvent(event) { return this.copy.contains(event.target); }
  destroy() { clearTimeout(this.timer); }
}
