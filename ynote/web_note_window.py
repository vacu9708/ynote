"""A note of Ynote 2.0: a frameless GTK window holding a web view, in which
web/src draws the whole note, its bars and its ProseMirror editor.

The window does what only the window can: where it is, its size, staying on
top, hiding, snapping with Alt and the arrows. The page asks for those by
messages (see _on_message()), and the window tells the page how the note
looks through window.ynote (see web/src/note.js). Its menus are shown by
the popup window (web_popup.py). For now this window is used only when
YNOTE_WEB is set (see config.WEB).
"""
import os
import shutil
import sys
import uuid

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gdk, GLib, Gtk, WebKit2

from . import __version__
from .config import CONF_DIR, IMAGES_DIR, SETTINGS_FILE, UNTITLED_LABEL, display_path
from .images import doc_image_files
from .storage import load_json, save_json
from .convert import doc_text, linkify, note_doc
from .search import find_matches
from .models import normalize_note_data
from .snap import snap_rect
from .styles import PALETTE
from .web_popup import popup
from .web_view import call_js, new_web_view, page_uri, run_js, unhandled
from .convert import state_blocks, state_of
from .markdown import from_markdown, is_all_code, to_markdown

PAGE_URI = page_uri('note.html')
IMAGES_URI = GLib.filename_to_uri(IMAGES_DIR, None) + '/'

# As tall as the page's title bar (--bar-h in note.css): a collapsed note.
TITLE_BAR_HEIGHT = 34
# The smallest a note is resized to: room for the title bar's buttons and a
# title, and for a few lines between the bars.
MIN_WIDTH = 180
MIN_HEIGHT = 120


# The page's resize edges, by the names it sends.
EDGES = {
    'n': Gdk.WindowEdge.NORTH, 's': Gdk.WindowEdge.SOUTH,
    'e': Gdk.WindowEdge.EAST, 'w': Gdk.WindowEdge.WEST,
    'ne': Gdk.WindowEdge.NORTH_EAST, 'nw': Gdk.WindowEdge.NORTH_WEST,
    'se': Gdk.WindowEdge.SOUTH_EAST, 'sw': Gdk.WindowEdge.SOUTH_WEST,
}

SNAP_KEYS = {
    Gdk.KEY_Left: 'left', Gdk.KEY_Right: 'right',
    Gdk.KEY_Up: 'up', Gdk.KEY_Down: 'down',
}

# Find's toggles: match case, regular expression, and All notes.
FIND_OPTIONS = ('caseSensitive', 'regex', 'all')


def find_options():
    settings = load_json(SETTINGS_FILE)
    found = settings.get('find') if isinstance(settings, dict) else None
    return {k: bool(found.get(k)) for k in FIND_OPTIONS} if isinstance(found, dict) else {}


def save_find_options(options):
    settings = load_json(SETTINGS_FILE)
    if not isinstance(settings, dict):
        settings = {}
    settings['find'] = options
    try:
        save_json(settings, SETTINGS_FILE)
    except OSError as e:
        print(f'ynote: could not save settings: {e}', file=sys.stderr)


EMOJI_RECENT = 24


def emoji_recent():
    settings = load_json(SETTINGS_FILE)
    found = settings.get('emoji_recent') if isinstance(settings, dict) else None
    return [e for e in found if isinstance(e, str)][:EMOJI_RECENT] if isinstance(found, list) else []


def add_recent_emoji(emoji):
    """Put emoji first among the recent ones, kept in settings.json."""
    recent = emoji_recent()
    if emoji:
        recent = ([emoji] + [e for e in recent if e != emoji])[:EMOJI_RECENT]
        settings = load_json(SETTINGS_FILE)
        if not isinstance(settings, dict):
            settings = {}
        settings['emoji_recent'] = recent
        try:
            save_json(settings, SETTINGS_FILE)
        except OSError as e:
            print(f'ynote: could not save settings: {e}', file=sys.stderr)
    return recent


def _alt_only(event):
    mods = event.state & Gtk.accelerator_get_default_mod_mask()
    return mods == Gdk.ModifierType.MOD1_MASK


class WebNoteWindow(Gtk.ApplicationWindow):
    def __init__(self, app, data: dict):
        super().__init__(application=app)
        self.app = app
        data = normalize_note_data(data)
        self.note_id = data['id']
        self.title = data['title']
        self.sort_order = data['sort_order']
        self._on_top = data['on_top']
        self._font_size = data['font_size']
        self._color = data['color']
        self._opacity = data['opacity']
        self._solid_in_use = data['solid_in_use']
        self._body_opacity = 1.0
        self._hovered = False
        self._collapsed = data['collapsed']
        self._expanded_height = data['h']
        self._normal_geometry = None
        self._save_id = None
        self._snap_held = []
        self._snap_pending_move = None
        self._press = None
        self._ready = False
        self._hidden_count = 0
        self._focus_on_load = False
        # The content, as the page last sent it. A note of 1.x is converted
        # once, here, and saved in the new form from then on.
        # Addresses made links once in a note saved before they were.
        self._doc = linkify(data.get('doc') or note_doc(data))
        self._seen_images = doc_image_files(self._doc)

        self.set_decorated(False)
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        self._composited = visual is not None and screen.is_composited()
        if self._composited:
            self.set_visual(visual)
        self.set_skip_pager_hint(True)
        self.set_wmclass('ynote', 'Ynote')
        self.set_title(self.title or UNTITLED_LABEL)

        self.view = new_web_view(self._on_message, 'note.html')
        self.view.connect('button-press-event', self._on_press)
        self.view.connect('scroll-event', self._on_scroll)
        self.view.connect('web-process-terminated', self._on_crash)
        self.add(self.view)

        self.connect('key-press-event', self._on_key_press)
        self.connect('key-release-event', self._on_key_release)
        self.connect('configure-event', self._on_configure)
        self.connect('window-state-event', self._on_window_state)
        self.connect('delete-event', self._on_delete)
        self.connect('focus-in-event', lambda *_: self.app._on_note_focus_in(self))
        self.connect('focus-out-event', self._on_focus_out)
        # Whether the note is in use, for Solid while in use.
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect('enter-notify-event', self._on_crossing, True)
        self.connect('leave-notify-event', self._on_crossing, False)
        self.connect('notify::is-active', lambda *_: self._apply_opacity())

        # A note saved smaller than it can be used opens at the least size.
        w, h = max(data['w'], MIN_WIDTH), max(data['h'], MIN_HEIGHT)
        self._expanded_height = h
        self.set_default_size(w, TITLE_BAR_HEIGHT if self._collapsed else h)
        self.move(data['x'], data['y'])
        # Where the note shows again after it is hidden: the window manager
        # would place a window shown again anew.
        self._shown_at = (data['x'], data['y'])
        self.connect('show', lambda *_: self.move(*self._shown_at))
        if self._collapsed:
            self._lock_size(True, w)
        self.view.show()
        if not data.get('hidden'):
            self.show()
        self.set_keep_above(self._on_top)
        self._apply_min_size()
        self._apply_opacity()

    # --- talking to the page ----------------------------------------------

    def _send(self, **props):
        """Tell the page how the note looks now, such as its title."""
        if self._ready:
            call_js(self.view, 'ynote.set', props)

    def _look(self):
        app = self.app
        return {'title': self.title, 'pinned': self._on_top,
                'collapsed': self._collapsed, 'fontSize': self._font_size,
                'opacity': self._opacity, 'solidInUse': self._solid_in_use,
                'bodyOpacity': self._body_opacity,
                'composited': self._composited,
                'color': self._color, 'maximized': self.is_maximized(),
                'hiddenCount': self._hidden_count,
                'version': __version__, 'notesPath': display_path(CONF_DIR),
                'findOptions': find_options(),
                'emojiRecent': emoji_recent(),
                'autostart': {'available': bool(getattr(app, 'autostart_available', False)),
                              'enabled': bool(getattr(app, 'autostart_available', False)
                                              and app.autostart_enabled())}}

    def _on_message(self, message):
        kind = message.get('type', '')
        handler = getattr(self, '_do_' + kind.replace('-', '_'), None)
        if handler is None:
            unhandled(kind, 'note.html')
            return
        handler(message)

    def _do_ready(self, _message):
        self._ready = True
        call_js(self.view, 'ynote.load', dict(self._look(), doc=self._doc, imagesUrl=IMAGES_URI))
        if self._focus_on_load:
            run_js(self.view, 'ynote.focus()')

    def _do_changed(self, message):
        self._doc = message['doc']
        self._seen_images |= doc_image_files(self._doc)
        self._queue_save()

    def _do_title(self, message):
        self.title = message.get('title', '').strip()
        self.set_title(self.title or UNTITLED_LABEL)
        self._queue_save()
        self.app._rebuild_indicator_menu()

    def _do_move(self, _message):
        if self._press and not self.is_maximized():
            button, x, y, time = self._press
            self.begin_move_drag(button, x, y, time)

    def _do_resize(self, message):
        edge = EDGES.get(message.get('edge'))
        if edge is None or not self._press or self._collapsed:
            return
        button, x, y, time = self._press
        self.begin_resize_drag(edge, button, x, y, time)

    def _do_maximize(self, _message):
        if self._collapsed:
            return
        if self.is_maximized():
            self.unmaximize()
            return
        # to_dict() saves this while maximized, so the next start does not
        # open at the size of the screen.
        self._normal_geometry = self.get_position() + self.get_size()
        self.maximize()

    def _do_collapse(self, _message):
        if self._collapsed:
            self._expand()
        elif not self.is_maximized():
            self._collapse()
        self._queue_save()

    def _do_pin(self, _message):
        self._on_top = not self._on_top
        self.set_keep_above(self._on_top)
        self._send(pinned=self._on_top)
        self._queue_save()

    def _do_set_color(self, message):
        if message.get('color') in PALETTE:
            self._color = message['color']
            self._send(color=self._color)
            self._queue_save()

    def _do_set_opacity(self, message):
        self._opacity = min(1.0, max(0.0, float(message.get('opacity', 1))))
        self._apply_opacity(preview=True)
        self._queue_save()

    def _do_set_solid_in_use(self, message):
        self._solid_in_use = bool(message.get('value'))
        self._apply_opacity()
        self._queue_save()

    def _on_crossing(self, _window, event, inside):
        # Moving onto the web view inside the window is not leaving it.
        if event.detail == Gdk.NotifyType.INFERIOR:
            return False
        self._hovered = inside
        self._apply_opacity()
        return False

    def _apply_opacity(self, preview=False):
        """Everything below the title bar fades alike, text too; the title
        bar stays solid, so a note is found and moved at any opacity, 0%
        too. While the note is in use, and Solid while in use is on, the rest
        is solid as well; while the opacity is being set, it shows it. At 0%
        it is solid while in use whatever the setting, or its text could not
        be seen at all. Seeing through needs a compositor."""
        if not self._composited:
            return
        in_use = (self._hovered or self.is_active()
                  or popup().owner is self)
        solid_in_use = self._solid_in_use or self._opacity <= 0.001
        solid = solid_in_use and in_use and not preview
        value = 1.0 if solid else self._opacity
        if value != self._body_opacity:
            self._body_opacity = value
            self._send(bodyOpacity=value)

    def _do_set_font_size(self, message):
        self._font_size = min(32, max(8, int(message.get('size', 14))))
        self._queue_save()

    def _do_new_note(self, _message):
        self.app.new_note(near=self)

    def _do_hide(self, _message):
        self._close_my_popup()
        self.hide()
        self.app.put_first_in_hidden([self])
        self.app._rebuild_indicator_menu()
        self._queue_save()

    def _do_delete(self, _message):
        self._close_my_popup()
        self.app.delete_note(self.note_id)

    def _do_hidden_notes(self, _message):
        self.show_hidden_list()

    def show_hidden_list(self):
        """The hidden notes, in a menu below the note's title bar."""
        x, y = self.get_position()
        width, _height = self.get_size()
        show_hidden_list(self.app, (x + max(0, width - 300), y + TITLE_BAR_HEIGHT, 0, 0))

    def _do_autostart(self, _message):
        if getattr(self.app, 'autostart_available', False):
            self.app.set_autostart(not self.app.autostart_enabled())
            self._send(autostart=self._look()['autostart'])

    def _do_quit(self, _message):
        self.app.quit_app()

    def _do_clipboard(self, message):
        command = message.get('command')
        if command in ('copy', 'cut'):
            self.copy(message.get('slice') or {})
        elif command in ('paste', 'paste-plain'):
            self.paste(plain=command == 'paste-plain')

    # --- the clipboard, as in 1.x: other apps get Markdown, or code as it
    # is; a note gets what was copied exactly, while Ynote still owns the
    # clipboard. Markdown from another app pastes in with its formats.

    def copy(self, fragment):
        """Keep what the page copied for a paste into a note, and put it on
        the clipboard as Markdown, or as it is when it is all code."""
        state = state_of(fragment.get('content') or [])
        markdown = None if is_all_code(state) else to_markdown(state).rstrip('\n')
        self.app.set_rich_clipboard(dict(state, slice=fragment), markdown)

    def paste(self, plain=False):
        rich = None if plain else self.app.rich_clipboard_state()
        if rich and rich.get('slice'):
            # Code takes the text other apps get: a table as a Markdown
            # table, not each cell's text on a line of its own.
            call_js(self.view, 'ynote.pasteSlice', rich['slice'], self.app.rich_clipboard_text())
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        if not plain and self._paste_clipboard_image(clipboard):
            return
        text = clipboard.wait_for_text()
        if not text:
            return
        if plain:
            call_js(self.view, 'ynote.pasteText', text)
            return
        blocks = state_blocks(from_markdown(text)) or [{'type': 'paragraph'}]
        # A paragraph at either end joins the line it is pasted into; a list,
        # heading, or code block there starts a line of its own.
        open_start = 1 if blocks[0]['type'] == 'paragraph' else 0
        open_end = 1 if blocks[-1]['type'] == 'paragraph' else 0
        call_js(self.view, 'ynote.pasteSlice',
                {'content': blocks, 'openStart': open_start, 'openEnd': open_end}, text)

    def _do_copy_text(self, message):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(message.get('text') or '', -1)

    def _do_open_link(self, message):
        url = message.get('url', '')
        if url.startswith(('http://', 'https://')):
            self.app.open_uri(url)

    def _do_choose_image(self, _message):
        dialog = Gtk.FileChooserNative.new('Insert Image', self,
                                           Gtk.FileChooserAction.OPEN, None, None)
        image_filter = Gtk.FileFilter()
        image_filter.set_name('Images')
        image_filter.add_pixbuf_formats()
        dialog.add_filter(image_filter)
        if dialog.run() == Gtk.ResponseType.ACCEPT:
            self.insert_image_file(dialog.get_filename())
        dialog.destroy()

    def insert_image_file(self, path):
        """Copy an image into the images folder and put it at the cursor."""
        ext = os.path.splitext(path)[1].lower() or '.png'
        name = str(uuid.uuid4()) + ext
        os.makedirs(IMAGES_DIR, exist_ok=True)
        shutil.copyfile(path, os.path.join(IMAGES_DIR, name))
        call_js(self.view, 'ynote.insertImage', name, os.path.basename(path))

    # --- menus, which the popup window shows --------------------------------

    def _do_popup(self, message):
        """Show a menu the page made, hung from a rectangle of the page."""
        window = self.view.get_window()
        if window is None:
            return
        _ok, ox, oy = window.get_origin()
        a = message.get('anchor') or {}
        anchor = (ox + int(a.get('x', 0)), oy + int(a.get('y', 0)),
                  int(a.get('width', 0)), int(a.get('height', 0)))
        popup().open(self, message.get('spec') or {}, anchor,
                     side=message.get('side', 'below'),
                     takes_input=message.get('input', True))

    def _do_popup_close(self, _message):
        self._close_my_popup()

    def _do_popup_key(self, message):
        if popup().owner is self:
            popup().key(message.get('key', ''))

    # --- finding in every note (the find bar's All notes) ----------------

    def _do_search_all(self, message):
        """The matches of a query in every note, this one first, then the
        others shown, then the hidden ones, for the find bar's list."""
        query = message.get('query', '')
        notes = self.app.searchable_notes(first=self)
        matches = find_matches(notes, query, case_sensitive=bool(message.get('caseSensitive')),
                               regex=bool(message.get('regex')))
        call_js(self.view, 'ynote.allResults', query, [
            {'id': m.note_id, 'title': m.title, 'hidden': m.hidden, 'snippet': m.snippet,
             'start': m.mark[0], 'end': m.mark[1]}
            for m in matches])

    def _do_find_options(self, message):
        """Find's toggles, kept for every note and the next start."""
        options = {k: bool(v) for k, v in (message.get('options') or {}).items()
                   if k in FIND_OPTIONS}
        save_find_options(options)
        for note in self.app.notes.values():
            if note is not self:
                note._send(findOptions=options)

    def _do_emoji_used(self, message):
        """An emoji chosen goes first among the recent, for every note."""
        recent = add_recent_emoji(message.get('emoji', ''))
        for note in self.app.notes.values():
            note._send(emojiRecent=recent)

    def _do_open_match(self, message):
        """Show the note of a match chosen in the list, finding the query in
        it."""
        note = self.app.notes.get(message.get('id'))
        if note is None:
            return
        if note is not self:
            self.app.show_note(note.note_id)
        note.find(message.get('query', ''))

    def find(self, query):
        """Open the find bar on this note with a query."""
        if self._ready:
            call_js(self.view, 'ynote.find', query)

    def _close_my_popup(self):
        if popup().owner is self:
            popup().close()

    def popup_pick(self, item_id, value=None):
        call_js(self.view, 'ynote.popupPick', item_id, value)

    def popup_change(self, item_id, value):
        call_js(self.view, 'ynote.popupChange', item_id, value)

    def popup_closed(self):
        self._apply_opacity()
        if self._ready:
            run_js(self.view, 'ynote.popupClosed()')

    def _on_crash(self, _view, reason):
        print(f'ynote: the page of {self.title!r} stopped ({reason}); reloading',
              file=sys.stderr)
        self._ready = False
        self.view.load_uri(PAGE_URI)

    # --- window -------------------------------------------------------------

    def _on_press(self, _view, event):
        # A move or a resize starts from where the button went down, which
        # only GTK knows; the page asks for it once the pointer moves.
        self._press = (event.button, int(event.x_root), int(event.y_root), event.time)
        return False

    def _on_scroll(self, _view, event):
        if os.environ.get('YNOTE_DEBUG'):
            _ok, dx, dy = event.get_scroll_deltas()
            print(f'ynote: scroll {event.direction} delta {dx},{dy} state {int(event.state)} '
                  f'stop {getattr(event, "is_stop", None)} time {event.time} in {self.title!r} '
                  f'active {self.is_active()}', file=sys.stderr, flush=True)
        # Alt + scroll steps through the notes (PostItApp.scroll_notes()).
        if not _alt_only(event):
            return False
        dy = self.app.scroll_amount(event)
        if dy:
            self.app.scroll_notes(self, dy, event.time)
        return True

    def _on_key_press(self, _window, event):
        # Alt + arrow snaps the note into a column (see snap.py).
        key = SNAP_KEYS.get(event.keyval)
        if key is None or not _alt_only(event):
            return False
        if key in self._snap_held:
            self._snap_held.remove(key)
        self._snap_held.append(key)
        self._snap_to(self._snap_held)
        return True

    def _paste_clipboard_image(self, clipboard):
        """An image on the clipboard, such as a screenshot: a copy of it goes
        in the images folder and the image at the cursor."""
        if not clipboard.wait_is_image_available():
            return False
        pixbuf = clipboard.wait_for_image()
        if pixbuf is None:
            return False
        name = str(uuid.uuid4()) + '.png'
        os.makedirs(IMAGES_DIR, exist_ok=True)
        pixbuf.savev(os.path.join(IMAGES_DIR, name), 'png', [], [])
        call_js(self.view, 'ynote.insertImage', name, 'Pasted image')
        return True

    def _on_key_release(self, _window, event):
        if os.environ.get('YNOTE_DEBUG') and event.keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
            print(f'ynote: alt released in {self.title!r}', file=sys.stderr, flush=True)
        key = SNAP_KEYS.get(event.keyval)
        if key in self._snap_held:
            self._snap_held.remove(key)
        elif event.keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
            self._snap_held.clear()
            self.app.end_note_switch()
        return False

    def _snap_to(self, keys):
        win = self.get_window()
        if win is None or self.is_maximized():
            return
        display = win.get_display()
        monitors = [display.get_monitor(i) for i in range(display.get_n_monitors())]
        areas = []
        for monitor in monitors:
            area = monitor.get_workarea()
            areas.append((area.x, area.y, area.width, area.height))
        index = monitors.index(display.get_monitor_at_window(win))
        x, y, w, h = snap_rect(keys, self.get_position() + self.get_size(), areas, index)
        if tuple(self.get_size()) == (w, h):
            self.move(x, y)
            return
        # Moved once the new size is applied, or the window manager keeps the
        # note on screen by its old size.
        self._snap_pending_move = (x, y, w, h)
        if self._collapsed:
            self._lock_size(True, w)
        self.resize(w, h)
        GLib.timeout_add(300, self._apply_snap_move)

    def _apply_snap_move(self):
        if self._snap_pending_move is not None:
            x, y, _, _ = self._snap_pending_move
            self._snap_pending_move = None
            self.move(x, y)
        return False

    def _on_configure(self, _window, event):
        if self.get_visible() and not self.is_maximized():
            self._shown_at = self.get_position()
        pending = self._snap_pending_move
        if pending is not None and (event.width, event.height) == pending[2:]:
            self._apply_snap_move()
        self._queue_save()
        return False

    def _on_window_state(self, _window, event):
        self._send(maximized=bool(event.new_window_state & Gdk.WindowState.MAXIMIZED))
        return False

    def _on_focus_out(self, *_):
        self.app._on_note_focus_out()
        # Another window taking the focus ends the note's menu, as a click
        # outside it does, when the desktop did not let the menu grab.
        if popup().owner is self and not popup().grabbed:
            popup().close()
        return False

    def _on_delete(self, *_):
        self._do_hide(None)
        return True

    def _lock_size(self, locked, width=-1):
        # A collapsed note cannot be resized, so the window manager never
        # tiles or maximizes an empty note. Its height is asked for too: a
        # window that cannot be resized takes the size its child asks for,
        # and a web view asks for next to none, which left a 1px note.
        if locked:
            self.set_size_request(width, TITLE_BAR_HEIGHT)
        else:
            self.set_size_request(-1, -1)
        self.set_resizable(not locked)

    def _apply_min_size(self):
        """A note is never resized smaller than it can be used; collapsed,
        it is its title bar."""
        hints = Gdk.Geometry()
        hints.min_width = MIN_WIDTH
        hints.min_height = TITLE_BAR_HEIGHT if self._collapsed else MIN_HEIGHT
        self.set_geometry_hints(None, hints, Gdk.WindowHints.MIN_SIZE)

    def _collapse(self):
        width, height = self.get_size()
        self._expanded_height = height
        self._collapsed = True
        self._apply_min_size()
        self._send(collapsed=True)
        self._lock_size(True, width)
        self.resize(width, TITLE_BAR_HEIGHT)

    def _expand(self):
        self._collapsed = False
        self._apply_min_size()
        self._lock_size(False)
        self._send(collapsed=False)
        self.resize(self.get_size()[0], self._expanded_height)

    # --- what the app asks of a note ------------------------------------------

    def set_hidden_count(self, count):
        self._hidden_count = count
        self._send(hiddenCount=count)

    def grab_text_focus(self):
        self.view.grab_focus()
        if self._ready:
            run_js(self.view, 'ynote.focus()')
        else:
            self._focus_on_load = True

    def first_text(self, chars=200):
        return doc_text(self._doc).strip()[:chars]

    def buffer_text(self):
        return doc_text(self._doc)

    def show_match(self, start, end):
        # Search comes with a later step.
        pass

    def history_image_files(self):
        # Every image the note has shown in this run: a superset of those its
        # undo history holds, which the page keeps to itself. Cleaned up on
        # the next start, when there is no history.
        return set(self._seen_images)

    def _queue_save(self):
        if self._save_id:
            GLib.source_remove(self._save_id)
        self._save_id = GLib.timeout_add(600, self._save)

    def _save(self):
        self._save_id = None
        self.app.save_all()
        return False

    def to_dict(self) -> dict:
        x, y = self.get_position()
        w, h = self.get_size()
        if self.is_maximized() and self._normal_geometry:
            x, y, w, h = self._normal_geometry
        if self._collapsed:
            h = self._expanded_height
        return dict(id=self.note_id, x=x, y=y, w=w, h=h, title=self.title,
                    doc=self._doc, on_top=self._on_top,
                    hidden=not self.get_visible(), sort_order=self.sort_order,
                    font_size=self._font_size, color=self._color,
                    opacity=self._opacity, solid_in_use=self._solid_in_use,
                    collapsed=self._collapsed)


def show_hidden_list(app, anchor):
    """A menu of the hidden notes, the latest hidden first, at anchor, a
    rectangle on the screen: choosing one shows it, or Show all shows them
    all."""
    hidden = app.hidden_notes()
    items = [{'header': 'Hidden notes', 'icon': 'hidden', 'count': len(hidden)}]
    for note_id, window in hidden:
        # The title alone; an untitled note goes by its first line.
        items.append({'id': 'note:' + note_id,
                      'label': window.title or window.first_text(40) or UNTITLED_LABEL,
                      'colorName': window._color})
    if not hidden:
        items.append({'id': 'none', 'label': 'No hidden notes', 'disabled': True})
    items += [{'sep': True},
              {'id': 'show-all', 'icon': 'open', 'label': 'Show all', 'disabled': not hidden}]
    popup().open(_HiddenChoice(app), {'items': items}, anchor)


class _HiddenChoice:
    """What the hidden notes menu chose."""

    def __init__(self, app):
        self.app = app

    def popup_pick(self, item_id, _value=None):
        if item_id and item_id.startswith('note:'):
            self.app.show_note(item_id[len('note:'):])
        elif item_id == 'show-all':
            self.app.show_all()

    def popup_change(self, _item_id, _value):
        pass

    def popup_closed(self):
        pass
