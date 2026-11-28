// The note page: the editor and its bars, and window.ynote, through which
// the app (ynote/web_note_window.py) loads the note and changes how it
// looks. Messages go the other way through post(), as JSON. Bundled into
// ynote/web/note.js.
import {createEditor} from './editor.js';
import {setupChrome} from './chrome.js';
import {Slice, Fragment} from 'prosemirror-model';
import {setImagesUrl, schema} from './schema.js';

function post(message) {
  const handler = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.ynote;
  if (handler) handler.postMessage(JSON.stringify(message));
  else console.log('ynote:', JSON.stringify(message).slice(0, 200));
}

let loading = false;
const editor = createEditor(document.getElementById('editor'), {
  onChange: doc => { if (!loading) post({type: 'changed', doc: doc.toJSON()}); },
  onOpenLink: url => post({type: 'open-link', url}),
  onCopy: text => post({type: 'copy-text', text}),
  onSlashKey: key => chrome.slashKey(key),
  onClipboard: command => clipboard(command),
});
const chrome = setupChrome(editor, post);

window.ynote = {
  load(note) {
    loading = true;
    setImagesUrl(note.imagesUrl || '');
    chrome.set(note);
    editor.setDoc(note.doc);
    loading = false;
    chrome.refresh();
  },
  set(props) { chrome.set(props); },
  // The popup window's answers about the menu this note opened.
  popupPick(id, value) { chrome.pick(id, value); },
  popupChange(id, value) { chrome.change(id, value); },
  popupClosed() { chrome.closed(); },
  focus() { editor.view.focus(); },
  find(query) { chrome.openFind(query); },
  allResults(query, list) { chrome.allResults(query, list); },
  editTitle() { chrome.editTitle(); },
  insertImage(file, name) {
    editor.run((state, dispatch) => {
      dispatch(state.tr.replaceSelectionWith(schema.nodes.image.create({file, name})).scrollIntoView());
      return true;
    });
  },
  text() { return editor.doc().textBetween(0, editor.doc().content.size, '\n', '￼'); },

  // The clipboard, which the app keeps (web_note_window.py).
  cut() {
    editor.run((state, dispatch) => { dispatch(state.tr.deleteSelection().scrollIntoView()); return true; });
  },
  // A fragment of a note, or Markdown read into blocks. Into code it goes as
  // its text alone, as code takes no formats.
  // raw, when given, is the text the fragment was read from, which code
  // takes as it is.
  pasteSlice(json, raw) {
    editor.run((state, dispatch) => {
      const slice = Slice.fromJSON(schema, json);
      if (state.selection.$from.parent.type.spec.code) {
        const text = raw ?? slice.content.textBetween(0, slice.content.size, '\n', '');
        dispatch(state.tr.insertText(text).scrollIntoView());
        return true;
      }
      const {$from, empty} = state.selection;
      // A table pasted in a table's cell goes after that table: a cell holds
      // no table, and the table it is in would be split.
      let hasTable = false;
      slice.content.descendants(node => { if (node.type === schema.nodes.table) hasTable = true; return !hasTable; });
      if (hasTable) {
        for (let d = $from.depth; d > 0; d--) {
          if ($from.node(d).type !== schema.nodes.table) continue;
          const after = $from.after(d);
          dispatch(state.tr.replaceRange(after, after, slice).scrollIntoView().setMeta('uiEvent', 'paste'));
          return true;
        }
      }
      // Blocks pasted on an empty line take its place, as in Confluence.
      const first = slice.content.firstChild;
      if (empty && slice.openStart === 0 && first && first.type !== schema.nodes.paragraph
          && $from.parent.type === schema.nodes.paragraph && !$from.parent.content.size) {
        dispatch(state.tr.replaceRange($from.before(), $from.after(), slice).scrollIntoView().setMeta('uiEvent', 'paste'));
        return true;
      }
      dispatch(state.tr.replaceSelection(slice).scrollIntoView().setMeta('uiEvent', 'paste'));
      return true;
    });
  },
  // Text as it is, without reading Markdown: a line for each line.
  pasteText(text) {
    editor.run((state, dispatch) => {
      if (state.selection.$from.parent.type.spec.code || !text.includes('\n')) {
        dispatch(state.tr.insertText(text).scrollIntoView());
        return true;
      }
      const lines = text.split('\n').map(line =>
        schema.nodes.paragraph.create(null, line ? schema.text(line) : null));
      dispatch(state.tr.replaceSelection(new Slice(Fragment.from(lines), 1, 1)).scrollIntoView());
      return true;
    });
  },
};

// The editor fills the note (note.css), so a click or a drag below the text
// is the editor's own, as on any line: the cursor goes to the end, and a
// drag selects up from there.

// What is selected goes with a copy or a cut; a cut then deletes it.
function clipboard(command) {
  const {selection} = editor.view.state;
  if (command === 'copy' || command === 'cut') {
    if (selection.empty) return;
    post({type: 'clipboard', command, slice: selection.content().toJSON()});
    if (command === 'cut') window.ynote.cut();
  } else {
    post({type: 'clipboard', command});
  }
}
window.ynote.clipboard = clipboard;

post({type: 'ready'});
