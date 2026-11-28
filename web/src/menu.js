// The menu page: one popup window of the app shows every menu of every
// note, so a menu may be larger than its note or reach past it. The app
// (ynote/web_popup.py) hands it a menu as JSON with window.menu.show(); the
// page answers with its size, and with what was chosen.
//
// A menu is a list of items:
//   {id, icon, label, md, keys: ['Ctrl', 'B'], on, check, disabled, danger}
//   {sep: true}, {section: 'Table'}
//   {swatches: [{id, value, color, on}]}
//   {slider: {id, label, value, min, max, step, unit}}
//   {stepper: {id, label, value, min, max}}
//   {toggle: {id, label, value}}
// Choosing an item sends {type: 'pick', id}; a swatch, slider, or stepper
// sends {type: 'change', id, value} and leaves the menu open.
import {el, strokeIcon} from './icons.js';

function post(message) {
  const handler = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.ynote;
  if (handler) handler.postMessage(JSON.stringify(message));
  else console.log('menu:', JSON.stringify(message));
}

const root = document.getElementById('menu');
let rows = [];      // the choosable rows, in order
let current = -1;   // the row lit, by mouse or keys

function light(index) {
  if (rows[current]) rows[current].classList.remove('sel');
  current = index;
  if (rows[current]) {
    rows[current].classList.add('sel');
    rows[current].scrollIntoView({block: 'nearest'});
  }
}

function step(delta) {
  if (!rows.length) return;
  let i = current;
  for (let n = 0; n < rows.length; n++) {
    i = (i + delta + rows.length) % rows.length;
    if (!rows[i].classList.contains('off')) { light(i); return; }
  }
}

function keysOf(keys) {
  return el('span', {class: 'keys'}, (keys || []).map(k => el('kbd', {}, k)));
}

function row(item) {
  const node = el('div', {class: ['row', item.on && 'on', item.danger && 'danger', item.disabled && 'off'].filter(Boolean).join(' '),
    role: 'menuitem', 'aria-disabled': item.disabled ? 'true' : null},
  el('span', {class: 'ic'}, item.icon ? strokeIcon(item.icon, 16) : null),
  el('span', {class: 'label'}, item.label),
  item.md ? el('span', {class: 'md'}, item.md) : el('span'),
  item.check !== undefined
    ? el('span', {class: 'chk' + (item.check ? ' checked' : '')}, item.check ? strokeIcon('check', 12) : null)
    : keysOf(item.keys));
  const index = rows.length;
  rows.push(node);
  node.addEventListener('mousemove', () => { if (current !== index) light(index); });
  node.addEventListener('click', () => { if (!item.disabled) post({type: 'pick', id: item.id}); });
  return node;
}

function swatches(list) {
  return el('div', {class: 'swatches'}, list.map(s => {
    const b = el('button', {class: 'swatch' + (s.on ? ' on' : ''), title: s.label || s.value, style: `background:${s.color}`});
    b.addEventListener('click', () => {
      root.querySelectorAll('.swatch.on').forEach(x => x.classList.remove('on'));
      b.classList.add('on');
      post({type: 'change', id: s.id, value: s.value});
    });
    return b;
  }));
}

function slider(spec) {
  const out = el('span', {class: 'value'}, `${Math.round(spec.value * 100)}%`);
  const input = el('input', {type: 'range', min: spec.min ?? 0, max: spec.max ?? 1, step: spec.step ?? 0.05, value: spec.value});
  input.addEventListener('input', () => {
    out.textContent = `${Math.round(input.value * 100)}%`;
    post({type: 'change', id: spec.id, value: Number(input.value)});
  });
  return el('div', {class: 'ctl'}, el('span', {}, spec.label), el('span', {class: 'ctl-right'}, input, out));
}

function toggle(spec) {
  let value = !!spec.value;
  const box = el('span', {class: 'chk' + (value ? ' checked' : '')}, value ? strokeIcon('check', 12) : null);
  const node = el('div', {class: 'ctl toggle', role: 'menuitemcheckbox', 'aria-checked': String(value)},
    el('span', {}, spec.label), box);
  node.addEventListener('click', () => {
    value = !value;
    box.className = 'chk' + (value ? ' checked' : '');
    box.replaceChildren(...(value ? [strokeIcon('check', 12)] : []));
    node.setAttribute('aria-checked', String(value));
    post({type: 'change', id: spec.id, value});
  });
  return node;
}

function stepper(spec) {
  let value = spec.value;
  const shown = el('span', {class: 'num'}, String(value));
  const change = delta => {
    const next = Math.min(spec.max ?? 99, Math.max(spec.min ?? 1, value + delta));
    if (next === value) return;
    value = next;
    shown.textContent = String(value);
    post({type: 'change', id: spec.id, value});
  };
  return el('div', {class: 'ctl'}, el('span', {}, spec.label),
    el('span', {class: 'stepper'},
      el('button', {title: 'Smaller', onclick: () => change(-1)}, 'A−'), shown,
      el('button', {title: 'Larger', onclick: () => change(1)}, 'A+')));
}

function render(items) {
  rows = [];
  current = -1;
  root.replaceChildren(...items.map(item => {
    if (item.sep) return el('div', {class: 'sep'});
    if (item.section) return el('div', {class: 'section'}, item.section);
    if (item.swatches) return swatches(item.swatches);
    if (item.slider) return slider(item.slider);
    if (item.stepper) return stepper(item.stepper);
    if (item.toggle) return toggle(item.toggle);
    return row(item);
  }));
}

function sendSize() {
  // Measured whole: the window may still be hidden, with no height to
  // limit the menu by, and is then made to fit it, within the monitor.
  root.style.maxHeight = 'none';
  const box = root.getBoundingClientRect();
  root.style.maxHeight = '';
  post({type: 'size', width: Math.ceil(box.width), height: Math.ceil(box.height)});
}

window.menu = {
  // Shows a menu: lights its first row when opened by keys, and says how
  // large it is, as the window is made to fit it.
  show(spec) {
    document.documentElement.classList.toggle('flat', !!spec.flat);
    render(spec.items || []);
    if (spec.light !== undefined && spec.light >= 0) light(spec.light);
    else if (spec.byKeys) step(1);
    sendSize();
  },
  // Keys from the app, which has them while the menu is open, or from the
  // note while it types into a menu that follows the text, like /.
  key(name) {
    if (name === 'down') step(1);
    else if (name === 'up') step(-1);
    else if (name === 'home') { light(-1); step(1); }
    else if (name === 'end') { light(rows.length); step(-1); }
    else if (name === 'enter') {
      if (rows[current] && !rows[current].classList.contains('off')) rows[current].click();
    } else if (name.length === 1) {
      // A letter goes to the next item that starts with it.
      const lower = name.toLowerCase();
      for (let n = 1; n <= rows.length; n++) {
        const i = (current + n) % rows.length;
        const label = rows[i].querySelector('.label').textContent.toLowerCase();
        if (label.startsWith(lower) && !rows[i].classList.contains('off')) { light(i); break; }
      }
    }
  },
};

post({type: 'ready'});
