// The note page: the editor and its bars, and window.ynote, through which
// the app (ynote/web_note_window.py) loads the note and changes how it
// looks. Messages go the other way through post(), as JSON. Bundled into
// ynote/web/note.js.
import {createEditor} from './editor.js';
import {setupChrome} from './chrome.js';
import {Selection} from 'prosemirror-state';
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
  popupPick(id) { chrome.pick(id); },
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
};

// A click below the text puts the cursor at its end.
document.getElementById('scroll').addEventListener('mousedown', event => {
  if (event.target.id !== 'scroll' && event.target.id !== 'editor') return;
  event.preventDefault();
  editor.run((state, dispatch) => {
    dispatch(state.tr.setSelection(Selection.atEnd(state.doc)).scrollIntoView());
    return true;
  });
});

post({type: 'ready'});
