// Ynote's icons: 2px strokes on a 24px grid, as in 1.x, so they stand beside
// bold labels. Shared by the note page and the menu page; a menu item names
// its icon, since menus travel between them as JSON.
const SVG = 'http://www.w3.org/2000/svg';

export const ICONS = {
  down: 'M6 9l6 6 6-6',
  right: 'M9 6l6 6-6 6',
  up: 'M6 15l6-6 6 6',
  pin: ['M9 4h6l-1 6 3 3H7l3-3z', 'M12 13v7'],
  // Dots as discs, bold enough beside the other icons.
  more: ['M5 10.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3z', 'M12 10.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3z',
    'M19 10.5a1.5 1.5 0 1 0 0 3a1.5 1.5 0 1 0 0-3z'],
  cross: 'M6 6l12 12M18 6L6 18',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  hidden: ['M3 3l18 18', 'M10.6 6.1A9.8 9.8 0 0 1 12 6c5 0 8.5 4.5 9.5 6a17 17 0 0 1-2.6 3.1M6.2 7.6A16 16 0 0 0 2.5 12c1 1.5 4.5 6 9.5 6 1.6 0 3-.4 4.2-1', 'M9.9 10a3 3 0 0 0 4.1 4.1'],
  search: ['M11 5a6 6 0 1 0 0 12a6 6 0 1 0 0-12z', 'M20 20l-4.5-4.5'],
  bold: ['M7 5h6a3.5 3.5 0 0 1 0 7H7z', 'M7 12h7a3.5 3.5 0 0 1 0 7H7z'],
  heading: ['M6 5v14', 'M18 5v14', 'M6 12h12'],
  code: 'M9 7l-5 5 5 5M15 7l5 5-5 5',
  bullet: ['M9 7h11M9 12h11M9 17h11', 'M4.5 7h.01M4.5 12h.01M4.5 17h.01'],
  checklist: ['M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z', 'M8.5 12.5l2.5 2.5 4.5-5'],
  quote: ['M5 5v14', 'M10 8h9M10 12h9M10 16h6'],
  divider: ['M4 12h16', 'M8 7h8M8 17h8'],
  expand: ['M8 6l6 6-6 6', 'M17 6v12'],
  table: ['M4 4h16v16H4z', 'M4 12h16M12 4v16'],
  image: ['M4 5h16v14H4z', 'M4 16l5-5 4 4 2-2 5 5', 'M15.5 9h.01'],
  copy: ['M9 9h10v11H9z', 'M5 15V4h10'],
  cut: ['M6 7a2 2 0 1 0 0-.01', 'M6 19a2 2 0 1 0 0-.01', 'M8 8l11 9M8 16l11-9'],
  paste: ['M8 4h8v3H8z', 'M6 6H5v14h14V6h-1'],
  text: ['M5 6h14', 'M12 6v13', 'M9 19h6'],
  rename: 'M4 20h4L19 9l-4-4L4 16z',
  trash: ['M4 7h16', 'M10 11v6M14 11v6', 'M6 7l1 13h10l1-13', 'M9 7V4h6v3'],
  help: ['M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z', 'M9.6 9.3a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.4', 'M12 17h.01'],
  power: ['M12 3v9', 'M6.3 7.3a8 8 0 1 0 11.4 0'],
  quit: ['M15 4h4v16h-4', 'M10 8l-4 4 4 4', 'M6 12h10'],
  open: ['M14 4h6v6', 'M20 4l-9 9', 'M18 14v6H4V6h6'],
  link: ['M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1', 'M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1'],
  rowAbove: ['M4 13h16v7H4z', 'M12 4v6M9 7h6'],
  rowBelow: ['M4 4h16v7H4z', 'M12 14v6M9 17h6'],
  colLeft: ['M13 4h7v16h-7z', 'M4 12h6M7 9v6'],
  colRight: ['M4 4h7v16H4z', 'M14 12h6M17 9v6'],
  check: 'M5 12l5 5 9-10',
  codeblock: ['M4 5h16v14H4z', 'M9 10l-2 2 2 2M15 10l2 2-2 2'],
  emoji: ['M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z', 'M8.5 14a4.5 4.5 0 0 0 7 0', 'M9 9.5h.01M15 9.5h.01'],
  calendar: ['M4 6h16v14H4z', 'M4 10h16', 'M8 3v4M16 3v4'],
  clock: ['M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z', 'M12 7v5l3 2'],
  markdown: ['M3 6h18v12H3z', 'M6 15V9l2.5 3L11 9v6', 'M15 9v6M13 13l2 2 2-2'],
  regex: ['M17 4v7M14 5.5l6 4M20 5.5l-6 4', 'M6 17a2 2 0 1 0 0 .01'],
};

export function strokeIcon(name, size = 16) {
  const svg = document.createElementNS(SVG, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', size);
  svg.setAttribute('height', size);
  svg.setAttribute('class', 'icon');
  svg.setAttribute('aria-hidden', 'true');
  for (const d of [].concat(ICONS[name] || [])) {
    const path = document.createElementNS(SVG, 'path');
    path.setAttribute('d', d);
    svg.appendChild(path);
  }
  return svg;
}

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  node.append(...children.flat().filter(c => c !== null && c !== undefined && c !== false));
  return node;
}
