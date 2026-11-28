// The / menu: a / typed at the start of a line or after a space opens a menu
// of what can be inserted, which what is typed after it narrows, as in
// Confluence. Up, Down, Enter, and Tab work the menu, while the text keeps
// the keys; a space, Esc, or moving away ends it, leaving the text as typed,
// so a path such as /var/log is typed as usual.
import {Plugin, PluginKey} from 'prosemirror-state';

export const slashKey = new PluginKey('slash');

const OFF = {active: false, from: 0, query: ''};

export function slashPlugin(onKey) {
  return new Plugin({
    key: slashKey,
    state: {
      init: () => OFF,
      apply(tr, value, _old, state) {
        const meta = tr.getMeta(slashKey);
        if (meta === 'end') return OFF;
        const {$cursor} = state.selection;
        if (!$cursor) return OFF;
        let from = value.active ? tr.mapping.map(value.from) : -1;
        if (!value.active) {
          // A / just typed, where a word may start.
          const typed = tr.getMeta('uiEvent') === undefined && tr.docChanged
            && $cursor.parentOffset >= 1
            && $cursor.parent.textBetween($cursor.parentOffset - 1, $cursor.parentOffset) === '/';
          if (!typed || $cursor.parent.type.spec.code) return OFF;
          const before = $cursor.parent.textBetween(0, $cursor.parentOffset - 1);
          if (before && !/\s$/.test(before)) return OFF;
          from = $cursor.pos - 1;
        }
        if ($cursor.pos <= from || state.doc.resolve(from).parent !== $cursor.parent) return OFF;
        const text = state.doc.textBetween(from, $cursor.pos);
        if (!text.startsWith('/') || /\s/.test(text)) return OFF;
        return {active: true, from, query: text.slice(1)};
      },
    },
    props: {
      handleKeyDown(view, event) {
        const s = slashKey.getState(view.state);
        if (!s.active) return false;
        const key = {ArrowDown: 'down', ArrowUp: 'up', Enter: 'enter', Tab: 'enter'}[event.key];
        if (event.key === 'Escape') {
          view.dispatch(view.state.tr.setMeta(slashKey, 'end'));
          return true;
        }
        return key ? onKey(key) : false;
      },
    },
  });
}

// What the / menu holds for a query: the actions whose names start with it
// first, then those that have it.
export function slashMatches(actions, query) {
  const q = query.toLowerCase();
  const starts = [], has = [];
  for (const action of actions) {
    const names = [action.label.toLowerCase(), action.id, (action.md || '').replace(/^\//, '')];
    if (names.some(n => n.startsWith(q))) starts.push(action);
    else if (names.some(n => n.includes(q))) has.push(action);
  }
  return starts.concat(has);
}
