// The note around the editor: the title bar, the bottom bar with the Format
// and Insert menus, and the edges that resize the window. What the window
// itself does (move, resize, hide) is asked of the app with post().
import * as cmd from './commands.js';
import {strokeIcon, CHEVRON_DOWN} from './views.js';
import {schema} from './schema.js';

const ICONS = {
  down: CHEVRON_DOWN,
  right: 'M9 6l6 6-6 6',
  pin: ['M9 4h6l-1 6 3 3H7l3-3z', 'M12 13v7'],
  plus: 'M12 5v14M5 12h14',
  cross: 'M6 6l12 12M18 6L6 18',
  hidden: ['M3 3l18 18', 'M10.6 6.1A9.8 9.8 0 0 1 12 6c5 0 8.5 4.5 9.5 6a17 17 0 0 1-2.6 3.1M6.2 7.6A16 16 0 0 0 2.5 12c1 1.5 4.5 6 9.5 6 1.6 0 3-.4 4.2-1', 'M9.9 10a3 3 0 0 0 4.1 4.1'],
  bullet: ['M9 7h11M9 12h11M9 17h11', 'M4.5 7h.01M4.5 12h.01M4.5 17h.01'],
  check: ['M4 5h5v5H4z', 'M4 14l2 2 3-4', 'M12 7h8M12 15h8'],
  quote: ['M5 5v14', 'M10 8h9M10 12h9M10 16h6'],
  code: 'M9 7l-5 5 5 5M15 7l5 5-5 5',
  divider: ['M4 12h16', 'M8 7h8M8 17h8'],
  expand: ['M8 6l6 6-6 6', 'M17 6v12'],
  table: ['M4 5h16v14H4z', 'M4 10h16M10 10v9'],
  image: ['M4 5h16v14H4z', 'M4 16l5-5 4 4 2-2 5 5', 'M15.5 9h.01'],
};
const icon = (name, size) => strokeIcon(ICONS[name], size);

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  node.append(...children.filter(c => c !== null && c !== undefined));
  return node;
}

// A button of a bar: a click does it, and pressing it never takes the focus
// from the text, so the cursor and the selection stay.
function barButton(content, label, onClick, extraClass = '') {
  const button = el('button', {class: 'bar-btn ' + extraClass, title: label, 'aria-label': label, tabindex: '-1'},
    ...[].concat(content));
  button.addEventListener('mousedown', event => event.preventDefault());
  button.addEventListener('click', onClick);
  return button;
}

function mix(a, b, t) {
  const parse = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  const x = parse(a), y = parse(b);
  return '#' + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, '0')).join('');
}

export function setupChrome(editor, post) {
  const root = document.documentElement;
  const note = document.getElementById('note');
  const titleText = document.getElementById('title');
  const titleBar = document.getElementById('titlebar');
  const bottomBar = document.getElementById('bottombar');
  let props = {title: '', pinned: false, collapsed: false, hiddenCount: 0};

  // Title bar: the chevron folds the note to its title bar, the pin keeps it
  // on top; dragging anywhere else moves the window.
  const collapseBtn = barButton(icon('down', 18), 'Collapse', () => post({type: 'collapse'}));
  const pinBtn = barButton(icon('pin', 18), 'Always on Top (toggle)', () => post({type: 'pin'}), 'pin');
  titleBar.prepend(collapseBtn);
  titleBar.append(pinBtn);
  titleBar.addEventListener('mousedown', event => {
    if (event.button !== 0 || event.detail > 1 || event.target.closest('button') || titleText.isContentEditable) return;
    event.preventDefault();
    post({type: 'move'});
  });
  titleBar.addEventListener('dblclick', event => {
    if (event.target.closest('button') || titleText.isContentEditable) return;
    post({type: 'maximize'});
  });
  titleBar.addEventListener('contextmenu', event => {
    event.preventDefault();
    post({type: 'menu'});
  });

  // Bottom bar: the note's actions, then the text's.
  const hiddenBtn = barButton(icon('hidden', 20), 'Hidden Notes', () => post({type: 'hidden-notes'}));
  const formatBtn = barButton([el('span', {}, 'Format'), icon('down', 14)], 'Format text',
    () => toggleMenu(formatBtn, formatItems), 'text');
  const insertBtn = barButton([el('span', {}, 'Insert'), icon('down', 14)], 'Insert an element',
    () => toggleMenu(insertBtn, insertItems), 'text');
  bottomBar.append(
    barButton(icon('plus', 18), 'New Note', () => post({type: 'new-note'})),
    barButton(icon('cross', 18), 'Hide Note', () => post({type: 'hide'})),
    hiddenBtn,
    el('span', {class: 'bar-sep'}),
    formatBtn, insertBtn,
  );

  // Edges and corners resize the window.
  for (const edge of ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']) {
    note.append(el('div', {class: 'grip grip-' + edge, onmousedown: event => {
      if (event.button !== 0) return;
      event.preventDefault();
      post({type: 'resize', edge});
    }}));
  }

  // --- Format and Insert menus: each row shows the Markdown that typing
  // makes it from and its shortcut.
  const formatItems = () => [
    {icon: el('b', {}, 'B'), name: 'Bold', md: '**text**', keys: 'Ctrl+B', run: cmd.toggleBold,
      active: s => markActive(s, schema.marks.strong)},
    {icon: el('b', {}, 'H'), name: 'Heading', md: '# text', keys: 'Ctrl+H', run: cmd.toggleHeading,
      active: cmd.headingActive},
    {icon: icon('code', 16), name: 'Inline code', md: '`text`', keys: 'Ctrl+E', run: cmd.toggleInlineCode,
      active: s => markActive(s, schema.marks.code)},
  ];
  const insertItems = () => [
    {icon: icon('bullet', 16), name: 'Bullet list', md: '- item', keys: 'Ctrl+8', run: cmd.toggleBullet},
    {icon: icon('check', 16), name: 'Checklist', md: '[ ] item', keys: 'Ctrl+9', run: cmd.toggleChecklist},
    {icon: icon('quote', 16), name: 'Quote', md: '> text', keys: '', run: cmd.toggleQuote},
    {icon: icon('code', 16), name: 'Code block', md: '```', keys: 'Ctrl+Shift+C', run: cmd.toggleCodeBlock},
    {icon: icon('divider', 16), name: 'Divider', md: '---', keys: '', run: cmd.insertDivider},
    {icon: icon('expand', 16), name: 'Expand', md: '', keys: '', run: cmd.insertExpand},
    {icon: icon('table', 16), name: 'Table', md: '', keys: '', run: cmd.insertTable},
    {icon: icon('image', 16), name: 'Image…', md: '', keys: 'Ctrl+V', run: () => { post({type: 'choose-image'}); return true; },
      always: true},
  ];

  let openMenu = null;
  function closeMenu() {
    if (!openMenu) return;
    openMenu.menu.remove();
    openMenu.button.classList.remove('open');
    openMenu = null;
  }
  function toggleMenu(button, items) {
    const same = openMenu && openMenu.button === button;
    closeMenu();
    if (same) return;
    const state = editor.view.state;
    const menu = el('div', {class: 'menu bar-menu', role: 'menu'});
    for (const item of items()) {
      const enabled = item.always || item.run(state);
      const row = el('button', {class: 'menu-row' + (item.active && item.active(state) ? ' active' : ''),
        role: 'menuitem', tabindex: '-1'},
      el('span', {class: 'menu-icon'}, item.icon),
      el('span', {class: 'menu-name'}, item.name),
      el('span', {class: 'menu-md'}, item.md),
      el('span', {class: 'menu-keys'}, item.keys));
      if (!enabled) row.disabled = true;
      row.addEventListener('mousedown', event => event.preventDefault());
      row.addEventListener('click', () => { closeMenu(); editor.run(item.run); });
      menu.append(row);
    }
    note.append(menu);
    // Above the button, inside the note; it scrolls when the note is short.
    const bar = bottomBar.getBoundingClientRect();
    const b = button.getBoundingClientRect();
    menu.style.bottom = (window.innerHeight - bar.top + 4) + 'px';
    menu.style.maxHeight = (bar.top - 8) + 'px';
    menu.style.left = Math.max(4, Math.min(b.left, window.innerWidth - menu.offsetWidth - 4)) + 'px';
    button.classList.add('open');
    openMenu = {menu, button};
  }
  document.addEventListener('mousedown', event => {
    if (openMenu && !openMenu.menu.contains(event.target) && !openMenu.button.contains(event.target)) closeMenu();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && openMenu) { closeMenu(); event.preventDefault(); event.stopPropagation(); }
  }, true);
  window.addEventListener('blur', closeMenu);

  // The Format button is lit while a format is on at the cursor.
  function refreshFormat() {
    const state = editor.view.state;
    formatBtn.classList.toggle('lit', formatItems().some(item => item.active(state)));
  }
  editor.view.setProps({dispatchTransaction(tr) {
    editor.view.updateState(editor.view.state.apply(tr));
    refreshFormat();
  }});

  // --- Title editing: Enter keeps it, Esc puts the old one back.
  function editTitle() {
    titleText.contentEditable = 'plaintext-only';
    titleText.focus();
    const range = document.createRange();
    range.selectNodeContents(titleText);
    getSelection().removeAllRanges();
    getSelection().addRange(range);
  }
  function endTitleEdit(keep) {
    if (!titleText.isContentEditable) return;
    titleText.contentEditable = 'false';
    const title = titleText.textContent.trim();
    if (keep && title !== props.title) {
      props.title = title;
      post({type: 'title', title});
    }
    renderTitle();
    editor.view.focus();
  }
  titleText.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); endTitleEdit(true); }
    if (event.key === 'Escape') { event.preventDefault(); endTitleEdit(false); }
  });
  titleText.addEventListener('blur', () => endTitleEdit(true));
  function renderTitle() {
    titleText.textContent = props.title || 'Untitled';
    titleText.classList.toggle('untitled', !props.title);
  }

  function set(next) {
    props = {...props, ...next};
    if ('title' in next) renderTitle();
    if (next.colors) {
      const {paper, bar} = next.colors;
      root.style.setProperty('--paper', paper);
      root.style.setProperty('--bar', bar);
      root.style.setProperty('--bar-soft', mix(paper, bar, 0.35));
      root.style.setProperty('--tint', mix(paper, '#ffffff', 0.45));
      root.style.setProperty('--line', mix(bar, '#000000', 0.25));
    }
    if ('opacity' in next) root.style.setProperty('--opacity', next.opacity);
    if ('fontSize' in next) root.style.setProperty('--font-size', next.fontSize + 'px');
    if ('composited' in next) root.classList.toggle('square', !next.composited);
    if ('pinned' in next) pinBtn.classList.toggle('on', next.pinned);
    if ('collapsed' in next) {
      note.classList.toggle('collapsed', next.collapsed);
      collapseBtn.replaceChildren(icon(next.collapsed ? 'right' : 'down', 18));
      collapseBtn.title = next.collapsed ? 'Expand' : 'Collapse';
    }
    if ('maximized' in next) root.classList.toggle('maximized', next.maximized);
    if ('hiddenCount' in next) {
      hiddenBtn.title = next.hiddenCount ? `Hidden Notes (${next.hiddenCount})` : 'Hidden Notes';
    }
  }

  renderTitle();
  return {set, editTitle, closeMenu};
}

function markActive(state, mark) {
  const {from, $from, to, empty} = state.selection;
  if (empty) return !!mark.isInSet(state.storedMarks || $from.marks());
  return state.doc.rangeHasMark(from, to, mark);
}
