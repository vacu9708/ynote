// The note around the editor. The title bar is the note's: collapse, title,
// to-do progress, pin, the note's menu, hide. The bottom bar is the text's:
// the toolbar, ＋ for the rest, and find. The find bar opens below the title
// bar. Menus show in the app's popup window (ynote/web_popup.py); what only
// the window can do is asked of the app with post().
import {el, strokeIcon} from './icons.js';
import {PALETTE, DEFAULT_COLOR} from './palette.js';
import {ACTION, ACTIONS, TOOLBAR, SLASH, perform, enabled, menuRow} from './actions.js';
import * as menus from './menus.js';
import {findKey, setFind, step, endFind} from './find.js';
import {slashKey, slashMatches} from './slash.js';

// A button of a bar: pressing it never takes the focus from the text, so the
// cursor and the selection stay.
function barButton(content, label, onClick, extraClass = '') {
  const button = el('button', {class: 'bar-btn ' + extraClass, 'aria-label': label, tabindex: '-1'},
    [].concat(content));
  button.addEventListener('mousedown', event => event.preventDefault());
  button.addEventListener('click', onClick);
  return button;
}

export function setupChrome(editor, post) {
  const root = document.documentElement;
  const note = document.getElementById('note');
  const titleText = document.getElementById('title');
  const titleBar = document.getElementById('titlebar');
  const bottomBar = document.getElementById('bottombar');
  const scrollBox = document.getElementById('scroll');
  let props = {title: '', pinned: false, collapsed: false, hiddenCount: 0, color: DEFAULT_COLOR,
    opacity: 1, solidInUse: true, fontSize: 14, maximized: false, autostart: null};
  const ctx = () => ({state: editor.view.state, dispatch: editor.view.dispatch, view: editor.view, post, chrome});
  const run = id => {
    const action = ACTION[id];
    if (!action) return;
    perform(action, ctx());
    if (action.edits) editor.view.focus();
  };

  // --- Tooltips: an action's name, Markdown, and keys, after a moment.
  const tip = el('div', {class: 'tip', role: 'tooltip', hidden: true});
  document.body.append(tip);
  let tipTimer = null;
  function tipFor(button, action) {
    button.addEventListener('mouseenter', () => {
      clearTimeout(tipTimer);
      tipTimer = setTimeout(() => showTip(button, action), 450);
    });
    button.addEventListener('mouseleave', hideTip);
    button.addEventListener('mousedown', hideTip);
  }
  function showTip(button, action) {
    // replaceChildren() would write a null out as "null".
    tip.replaceChildren(...[el('span', {}, action.label),
      action.md && el('span', {class: 'md'}, action.md),
      action.keys && el('span', {class: 'keys'}, action.keys.map(k => el('kbd', {}, k)))].filter(Boolean));
    // Its text as its name, as WebKit gives a tooltip's plain text to no one.
    tip.setAttribute('aria-label', tip.textContent);
    tip.hidden = false;
    const b = button.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    const above = b.top - t.height - 6;
    tip.style.top = (above >= 0 ? above : b.bottom + 6) + 'px';
    tip.style.left = Math.max(4, Math.min(b.left + b.width / 2 - t.width / 2, innerWidth - t.width - 4)) + 'px';
  }
  function hideTip() { clearTimeout(tipTimer); tip.hidden = true; }

  // --- Title bar. Dragging it anywhere but a button moves the window, from
  // the press GTK saw, once the pointer moves: a double click still arrives
  // and maximizes.
  const collapseBtn = barButton(strokeIcon('down', 17), 'Collapse', () => run('collapse'));
  const progress = el('span', {class: 'progress', hidden: true, title: 'To-dos done'},
    el('span', {class: 'ring'}), el('span', {class: 'count'}));
  const pinBtn = barButton(strokeIcon('pin', 17), 'Always on top', () => run('pin'), 'pin');
  const moreBtn = barButton(strokeIcon('more', 17), 'Note menu', () => openNoteMenu(moreBtn));
  const hideBtn = barButton(strokeIcon('cross', 17), 'Hide note', () => run('hide'));
  titleBar.prepend(collapseBtn);
  titleBar.append(progress, pinBtn, moreBtn, hideBtn);
  tipFor(collapseBtn, {label: 'Collapse'});
  tipFor(pinBtn, ACTION.pin);
  tipFor(moreBtn, {label: 'Note menu'});
  tipFor(hideBtn, ACTION.hide);
  let press = null;
  titleBar.addEventListener('mousedown', event => {
    if (event.button !== 0 || event.target.closest('button') || titleText.isContentEditable) return;
    event.preventDefault();
    press = event.detail > 1 ? null : {x: event.screenX, y: event.screenY};
  });
  document.addEventListener('mousemove', event => {
    if (!press || !(event.buttons & 1)) { press = null; return; }
    if (Math.abs(event.screenX - press.x) + Math.abs(event.screenY - press.y) < 4) return;
    press = null;
    post({type: 'move'});
  });
  document.addEventListener('mouseup', () => { press = null; });
  titleBar.addEventListener('dblclick', event => {
    if (event.target.closest('button') || titleText.isContentEditable) return;
    post({type: 'maximize'});
  });
  titleBar.addEventListener('contextmenu', event => {
    event.preventDefault();
    openNoteMenu(null, {x: event.clientX, y: event.clientY});
  });

  // --- Toolbar: the text's actions; those that do not fit go into ＋.
  const tools = TOOLBAR.map(id => {
    if (id === '|') return {id, node: el('span', {class: 'bar-sep'})};
    const action = ACTION[id];
    const content = id === 'bold' ? el('b', {class: 'glyph'}, 'B') : strokeIcon(action.icon, 17);
    const node = barButton(content, action.label, () => run(id), 'tool');
    tipFor(node, action);
    return {id, node};
  });
  const plusBtn = barButton(strokeIcon('plus', 17), 'More to insert', () => openMoreMenu());
  tipFor(plusBtn, {label: 'More to insert'});
  const findBtn = barButton(strokeIcon('search', 17), ACTION.find.label, () => openFind(), 'find-btn');
  tipFor(findBtn, ACTION.find);
  bottomBar.append(...tools.map(t => t.node), plusBtn, el('span', {class: 'bar-space'}), findBtn);
  let overflow = [];
  function layoutToolbar() {
    tools.forEach(t => { t.node.hidden = false; });
    overflow = [];
    const room = () => bottomBar.scrollWidth <= bottomBar.clientWidth;
    for (let i = tools.length - 1; i >= 0 && !room(); i--) {
      tools[i].node.hidden = true;
      if (tools[i].id !== '|') overflow.unshift(tools[i].id);
    }
    // No divider at the end.
    const shown = tools.filter(t => !t.node.hidden);
    if (shown.length && shown[shown.length - 1].id === '|') shown[shown.length - 1].node.hidden = true;
  }
  new ResizeObserver(layoutToolbar).observe(bottomBar);

  // The toolbar shows what is on at the cursor and what cannot be done.
  function refreshTools() {
    const c = ctx();
    for (const t of tools) {
      if (t.id === '|') continue;
      const action = ACTION[t.id];
      t.node.classList.toggle('on', !!(action.active && action.active(c)));
      t.node.classList.toggle('off', !enabled(action, c));
    }
    refreshProgress();
    refreshFindCount();
  }

  // --- To-do progress, beside the title.
  function refreshProgress() {
    let all = 0, done = 0;
    editor.view.state.doc.descendants(node => {
      if (node.type.name === 'list_item' && node.attrs.checked !== null) {
        all++;
        if (node.attrs.checked) done++;
      }
      return true;
    });
    progress.hidden = !all;
    progress.querySelector('.count').textContent = `${done}/${all}`;
    progress.style.setProperty('--done', all ? `${(done / all) * 100}%` : '0%');
    progress.classList.toggle('all-done', all > 0 && done === all);
  }

  // --- Edges and corners resize the window.
  for (const edge of ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw']) {
    note.append(el('div', {class: 'grip grip-' + edge, onmousedown: event => {
      if (event.button !== 0) return;
      event.preventDefault();
      post({type: 'resize', edge});
    }}));
  }

  // --- Find bar.
  const findInput = el('input', {class: 'find-input', type: 'text', spellcheck: 'false', 'aria-label': 'Find',
    placeholder: 'Find'});
  const findCount = el('span', {class: 'find-count'});
  const caseBtn = el('button', {class: 'find-toggle', title: 'Match case (Alt+C)', tabindex: '-1'}, 'Aa');
  const regexBtn = el('button', {class: 'find-toggle', title: 'Regular expression (Alt+R)', tabindex: '-1'}, '.*');
  const allBtn = el('button', {class: 'find-toggle all', title: 'Find in every note, hidden ones too (Alt+A)',
    tabindex: '-1', 'aria-pressed': 'false'}, 'All notes');
  const prevBtn = barButton(strokeIcon('up', 16), 'Previous match (Shift+Enter)', () => step(editor.view, -1));
  const nextBtn = barButton(strokeIcon('down', 16), 'Next match (Enter)', () => step(editor.view, 1));
  const findBar = el('div', {class: 'find-bar', hidden: true},
    el('div', {class: 'find-box'}, strokeIcon('search', 14), findInput, findCount, caseBtn, regexBtn),
    allBtn, prevBtn, nextBtn,
    barButton(strokeIcon('cross', 16), 'Close (Esc)', () => closeFind()));
  titleBar.after(findBar);

  // All notes: the matches in every note, listed in place of the text; a
  // match chosen shows its note and finds the query there.
  const results = el('div', {class: 'all-results', role: 'listbox', hidden: true});
  scrollBox.before(results);
  let allMode = false, resultRows = [], resultIndex = -1, searchTimer = null;
  function setAllMode(on) {
    allMode = on;
    allBtn.classList.toggle('on', on);
    allBtn.setAttribute('aria-pressed', String(on));
    results.hidden = !on;
    scrollBox.hidden = on;
    caseBtn.hidden = regexBtn.hidden = prevBtn.hidden = nextBtn.hidden = on;
    if (on) {
      setFind(editor.view, {query: ''});
      searchAll();
    } else {
      setFind(editor.view, {query: findInput.value, current: 0});
    }
    refreshFindCount();
    findInput.focus();
  }
  allBtn.addEventListener('mousedown', event => event.preventDefault());
  allBtn.addEventListener('click', () => setAllMode(!allMode));
  function searchAll() {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => post({type: 'search-all', query: findInput.value}), 80);
  }
  function lightResult(i) {
    if (resultRows[resultIndex]) resultRows[resultIndex].classList.remove('sel');
    resultIndex = i;
    if (resultRows[i]) {
      resultRows[i].classList.add('sel');
      resultRows[i].scrollIntoView({block: 'nearest'});
    }
  }
  function showResults(query, list) {
    if (!allMode || query !== findInput.value) return;
    resultRows = list.map(m => {
      const row = el('div', {class: 'result', role: 'option'},
        el('span', {class: 'dot', style: `background:${(PALETTE[m.color] || PALETTE[DEFAULT_COLOR]).paper}`}),
        el('b', {}, m.title || 'Untitled'), el('span', {class: 'snippet'}, mark(m.snippet, query)),
        m.hidden ? el('span', {class: 'tag'}, 'hidden') : null);
      row.addEventListener('mousedown', event => event.preventDefault());
      row.addEventListener('click', () => openMatch(m));
      return row;
    });
    results.replaceChildren(...(resultRows.length ? resultRows
      : [el('div', {class: 'no-results'}, query ? 'No note has this' : '')]));
    resultIndex = -1;
    lightResult(0);
    findCount.textContent = query ? String(list.length) : '';
  }
  function mark(text, query) {
    const i = text.toLowerCase().indexOf(query.toLowerCase());
    if (!query || i < 0) return [text];
    return [text.slice(0, i), el('mark', {}, text.slice(i, i + query.length)), text.slice(i + query.length)];
  }
  function openMatch(m) {
    const query = findInput.value;
    setAllMode(false);
    post({type: 'open-match', id: m.id, query});
  }
  const findState = () => findKey.getState(editor.view.state);
  findInput.addEventListener('input', () => {
    if (allMode) searchAll();
    else setFind(editor.view, {query: findInput.value, current: 0});
  });
  const toggle = (button, key) => {
    button.addEventListener('mousedown', event => event.preventDefault());
    button.addEventListener('click', () => {
      setFind(editor.view, {[key]: !findState()[key]});
      button.classList.toggle('on', findState()[key]);
    });
  };
  toggle(caseBtn, 'caseSensitive');
  toggle(regexBtn, 'regex');
  findInput.addEventListener('keydown', event => {
    if (allMode && event.key === 'ArrowDown') { event.preventDefault(); lightResult(Math.min(resultIndex + 1, resultRows.length - 1)); }
    else if (allMode && event.key === 'ArrowUp') { event.preventDefault(); lightResult(Math.max(resultIndex - 1, 0)); }
    else if (allMode && event.key === 'Enter') { event.preventDefault(); if (resultRows[resultIndex]) resultRows[resultIndex].click(); }
    else if (event.altKey && (event.key === 'a' || event.key === 'A')) { event.preventDefault(); allBtn.click(); }
    else if (event.key === 'Enter') { event.preventDefault(); step(editor.view, event.shiftKey ? -1 : 1); }
    else if (event.key === 'Escape') { event.preventDefault(); closeFind(); }
    else if (event.altKey && (event.key === 'c' || event.key === 'C')) { event.preventDefault(); caseBtn.click(); }
    else if (event.altKey && (event.key === 'r' || event.key === 'R')) { event.preventDefault(); regexBtn.click(); }
    event.stopPropagation();
  });
  function openFind(query) {
    if (props.collapsed) post({type: 'collapse'});
    if (allMode && typeof query === 'string') setAllMode(false);
    findBar.hidden = false;
    findBtn.classList.add('open');
    const {from, to} = editor.view.state.selection;
    const selected = editor.view.state.doc.textBetween(from, to);
    if (typeof query === 'string') findInput.value = query;
    else if (selected && !selected.includes('\n')) findInput.value = selected;
    findInput.focus();
    findInput.select();
    setFind(editor.view, {query: findInput.value, current: 0});
  }
  function closeFind() {
    if (findBar.hidden) return;
    if (allMode) setAllMode(false);
    findBar.hidden = true;
    findBtn.classList.remove('open');
    endFind(editor.view);
    editor.view.focus();
  }
  function refreshFindCount() {
    if (findBar.hidden || allMode) return;
    const {matches, current, error, query} = findState();
    findCount.textContent = error ? 'error' : query ? (matches.length ? `${current + 1}/${matches.length}` : '0/0') : '';
    findCount.title = error || '';
    findInput.classList.toggle('none', !!query && !matches.length);
  }

  // --- Menus. One is open at a time; the app shows it and sends back the
  // id of the item chosen, to the handler kept here.
  let openMenu = null;
  function popup(name, items, anchor, {side = 'below', button = null, byKeys = false, input = true} = {}) {
    closeMenu();
    hideTip();
    openMenu = {name, button};
    if (button) button.classList.add('open');
    post({type: 'popup', spec: {items, byKeys}, anchor: rectOf(anchor), side, input});
    return openMenu;
  }

  // --- The / menu follows the text: shown again as the query changes,
  // closed when it ends. It takes no keys; the editor passes it these.
  let slashQuery = null;
  function refreshSlash() {
    const s = slashKey.getState(editor.view.state);
    const items = s.active
      ? slashMatches(SLASH.map(id => ACTION[id]), s.query).filter(a => enabled(a, ctx())) : [];
    if (!items.length) {
      slashQuery = null;
      if (openMenu && openMenu.name === 'slash') { closeMenu(); post({type: 'popup-close'}); }
      return;
    }
    if (openMenu && openMenu.name === 'slash' && slashQuery === s.query) return;
    slashQuery = s.query;
    const at = editor.view.coordsAtPos(s.from);
    const rows = items.map(a => menuRow(a, ctx()));
    popup('slash', rows, {x: at.left, y: at.top, height: at.bottom - at.top}, {byKeys: true, input: false});
  }
  function slashKeyPressed(key) {
    if (!openMenu || openMenu.name !== 'slash') return false;
    post({type: 'popup-key', key});
    return true;
  }
  function closeMenu() {
    if (!openMenu) return;
    if (openMenu.button) openMenu.button.classList.remove('open');
    openMenu = null;
  }
  function rectOf(anchor) {
    if (anchor instanceof Element) {
      const r = anchor.getBoundingClientRect();
      return {x: r.left, y: r.top, width: r.width, height: r.height};
    }
    return {x: anchor.x, y: anchor.y, width: anchor.width || 0, height: anchor.height || 0};
  }
  function toggleMenu(button, open) {
    if (button && openMenu && openMenu.button === button) { post({type: 'popup-close'}); return; }
    open();
  }

  function openHelp() {
    const r = note.getBoundingClientRect();
    post({type: 'popup', spec: {items: menus.helpPage(ACTIONS, props), columns: true},
      anchor: {x: r.left + 16, y: r.top + 40, width: 0, height: 0}, side: 'below', input: true});
    openMenu = {name: 'help', button: null};
  }

  function openMoreMenu() {
    toggleMenu(plusBtn, () => popup('more', menus.moreMenu(ctx(), overflow), plusBtn, {side: 'above', button: plusBtn}));
  }
  function openNoteMenu(button, point) {
    toggleMenu(button, () => popup('note', menus.noteMenu(ctx(), props), button || point, {button}));
  }
  function openContextMenu(point, byKeys = false) {
    const state = editor.view.state;
    const link = linkAt(point);
    popup('context', menus.contextMenu(state, {link, hasSelection: !state.selection.empty}), point, {byKeys}).link = link;
  }
  function linkAt(point) {
    const target = point && document.elementFromPoint(point.x, point.y);
    const link = target && target.closest && target.closest('.link');
    return link ? link.dataset.url : null;
  }
  editor.view.dom.addEventListener('contextmenu', event => {
    event.preventDefault();
    // A right click outside the selection moves the cursor there first.
    const pos = editor.view.posAtCoords({left: event.clientX, top: event.clientY});
    const {from, to} = editor.view.state.selection;
    if (pos && (pos.pos < from || pos.pos > to)) {
      editor.run((state, dispatch) => {
        dispatch(state.tr.setSelection(state.selection.constructor.near(state.doc.resolve(pos.pos))));
        return true;
      });
    }
    openContextMenu({x: event.clientX, y: event.clientY});
  });

  function pick(id) {
    const menu = openMenu;
    closeMenu();
    if (!menu) return;
    if (menu.name === 'slash') {
      // The / and what was typed after it go; the action takes their place.
      editor.run((state, dispatch) => {
        const s = slashKey.getState(state);
        if (s.active) dispatch(state.tr.delete(s.from, state.selection.from).setMeta(slashKey, 'end'));
        return true;
      });
      run(id);
      return;
    }
    if (menu.name === 'context') {
      if (id === 'open-link') post({type: 'open-link', url: menu.link});
      else if (id === 'copy-link') post({type: 'copy-text', text: menu.link});
      else if (['cut', 'copy', 'paste', 'paste-plain'].includes(id)) window.ynote.clipboard(id);
      else if (menus.TABLE_ACTIONS[id]) editor.run(menus.TABLE_ACTIONS[id]);
      return;
    }
    run(id);
  }
  function change(id, value) {
    if (id === 'color') post({type: 'set-color', color: value});
    else if (id === 'opacity') { props.opacity = value; post({type: 'set-opacity', opacity: value}); }
    else if (id === 'solid-in-use') { props.solidInUse = value; post({type: 'set-solid-in-use', value}); }
    else if (id === 'font-size') { set({fontSize: value}); post({type: 'set-font-size', size: value}); }
  }

  // --- Keys of the note, beside the editor's.
  document.addEventListener('keydown', event => {
    const ctrl = event.ctrlKey && !event.altKey && !event.metaKey;
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    let id = null;
    if (event.key === 'F2') id = 'rename';
    else if (event.key === 'F1') id = 'help';
    else if (ctrl && !event.shiftKey && key === 'n') id = 'new-note';
    else if (ctrl && !event.shiftKey && key === 'w') id = 'hide';
    else if (ctrl && !event.shiftKey && key === 'f') id = 'find';
    else if (ctrl && event.shiftKey && key === 'm') id = 'copy-markdown';
    else if (event.key === 'Escape' && !findBar.hidden) { event.preventDefault(); closeFind(); return; }
    else if (event.key === 'ContextMenu' || (event.key === 'F10' && event.shiftKey)) {
      event.preventDefault();
      const coords = editor.view.coordsAtPos(editor.view.state.selection.head);
      openContextMenu({x: coords.left, y: coords.bottom}, true);
      return;
    }
    if (id) { event.preventDefault(); run(id); }
  });

  editor.view.setProps({dispatchTransaction(tr) {
    editor.view.updateState(editor.view.state.apply(tr));
    refreshTools();
    refreshSlash();
  }});

  // --- Rename in place: Enter keeps it, Esc puts the old one back.
  function editTitle() {
    if (props.collapsed) post({type: 'collapse'});
    titleText.textContent = props.title;
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
    event.stopPropagation();
    if (event.key === 'Enter') { event.preventDefault(); endTitleEdit(true); }
    if (event.key === 'Escape') { event.preventDefault(); endTitleEdit(false); }
  });
  titleText.addEventListener('blur', () => endTitleEdit(true));
  function renderTitle() {
    titleText.textContent = props.title || 'Untitled';
    titleText.classList.toggle('untitled', !props.title);
  }

  // --- Delete: asked on the note itself, with Hide offered to keep it.
  function confirmDelete() {
    if (props.collapsed) post({type: 'collapse'});
    const name = props.title ? `“${props.title}”` : 'this note';
    const close = () => { veil.remove(); editor.view.focus(); };
    const veil = el('div', {class: 'veil'},
      el('div', {class: 'sheet', role: 'alertdialog', 'aria-label': `Delete ${name}?`},
        el('b', {}, `Delete ${name}?`),
        el('span', {}, 'Its text and images go away. Hide it instead to keep it.'),
        el('div', {class: 'sheet-buttons'},
          el('button', {class: 'btn', onclick: close}, 'Cancel'),
          el('button', {class: 'btn', onclick: () => { veil.remove(); run('hide'); }}, 'Hide'),
          el('button', {class: 'btn danger', onclick: () => post({type: 'delete'})}, 'Delete'))));
    veil.addEventListener('keydown', event => {
      event.stopPropagation();
      if (event.key === 'Escape') { event.preventDefault(); close(); }
    });
    note.append(veil);
    veil.querySelector('.danger').focus();
  }

  function set(next) {
    props = {...props, ...next};
    if ('title' in next && !titleText.isContentEditable) renderTitle();
    if ('color' in next) {
      const c = PALETTE[next.color] || PALETTE[DEFAULT_COLOR];
      root.style.setProperty('--paper', c.paper);
      root.style.setProperty('--bar', c.bar);
      root.style.setProperty('--soft', c.soft);
    }
    if ('fontSize' in next) root.style.setProperty('--font-size', next.fontSize + 'px');
    if ('composited' in next) root.classList.toggle('square', !next.composited);
    if ('pinned' in next) pinBtn.classList.toggle('on', next.pinned);
    if ('collapsed' in next) {
      note.classList.toggle('collapsed', next.collapsed);
      collapseBtn.replaceChildren(strokeIcon(next.collapsed ? 'right' : 'down', 17));
      collapseBtn.setAttribute('aria-label', next.collapsed ? 'Expand' : 'Collapse');
      if (next.collapsed) closeFind();
    }
    if ('maximized' in next) root.classList.toggle('maximized', next.maximized);
  }

  renderTitle();
  const chrome = {set, editTitle, confirmDelete, openFind, closeFind, pick, change, closed: closeMenu,
    refresh: refreshTools, slashKey: slashKeyPressed, allResults: showResults, openHelp};
  return chrome;
}
