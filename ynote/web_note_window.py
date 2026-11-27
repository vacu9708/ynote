"""A note of Ynote 2.0: a frameless GTK window holding a web view, in which
web/src draws the whole note, its bars and its ProseMirror editor.

The window does what only the window can: where it is, its size, staying on
top, hiding, snapping with Alt and the arrows. The page asks for those by
messages (see _on_message()), and the window tells the page how the note
looks through window.ynote (see web/src/main.js). For now this window is
used only when YNOTE_WEB is set (see config.WEB).
"""
import json
import os
import shutil
import sys
import uuid

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gdk, GLib, Gtk, WebKit2

from .config import IMAGES_DIR, PACKAGE_DIR, UNTITLED_LABEL
from .convert import doc_text, note_doc
from .models import normalize_note_data
from .snap import snap_rect
from .styles import PALETTE

PAGE_URI = GLib.filename_to_uri(os.path.join(PACKAGE_DIR, 'web', 'note.html'), None)
IMAGES_URI = GLib.filename_to_uri(IMAGES_DIR, None) + '/'

# As tall as the page's title bar (--title-h in note.css): a collapsed note.
TITLE_BAR_HEIGHT = 38

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

# Every note's page runs in one web process: a process each would take about
# 250 MB per note. A new view is related to a view that is still open.
_views = []


def _new_web_view():
    live = [v for v in _views if v.get_parent() is not None]
    view = (WebKit2.WebView.new_with_related_view(live[0]) if live
            else WebKit2.WebView())
    settings = view.get_settings()
    settings.set_allow_file_access_from_file_urls(True)
    # GL compositing costs hundreds of MB per note on some systems and gives
    # a note nothing it needs.
    settings.set_hardware_acceleration_policy(
        WebKit2.HardwareAccelerationPolicy.NEVER)
    settings.set_enable_back_forward_navigation_gestures(False)
    settings.set_enable_developer_extras(bool(os.environ.get('YNOTE_DEBUG')))
    settings.set_enable_write_console_messages_to_stdout(True)
    view.set_background_color(Gdk.RGBA(0, 0, 0, 0))
    _views.append(view)
    return view


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
        self._doc = data.get('doc') or note_doc(data)

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

        self.view = _new_web_view()
        manager = self.view.get_user_content_manager()
        manager.register_script_message_handler('ynote')
        manager.connect('script-message-received::ynote', self._on_message)
        self.view.connect('decide-policy', self._on_decide_policy)
        self.view.connect('context-menu', lambda *_: True)
        self.view.connect('button-press-event', self._on_press)
        self.view.connect('scroll-event', self._on_scroll)
        self.view.connect('web-process-terminated', self._on_crash)
        self.add(self.view)
        self.view.load_uri(PAGE_URI)

        self.connect('key-press-event', self._on_key_press)
        self.connect('key-release-event', self._on_key_release)
        self.connect('configure-event', self._on_configure)
        self.connect('window-state-event', self._on_window_state)
        self.connect('delete-event', self._on_delete)
        self.connect('focus-in-event', lambda *_: self.app._on_note_focus_in(self))
        self.connect('focus-out-event', lambda *_: self.app._on_note_focus_out())

        w, h = data['w'], data['h']
        self.set_default_size(w, TITLE_BAR_HEIGHT if self._collapsed else h)
        self.move(data['x'], data['y'])
        if self._collapsed:
            self._lock_size(True, w)
        self.view.show()
        if not data.get('hidden'):
            self.show()
        self.set_keep_above(self._on_top)

    # --- talking to the page ----------------------------------------------

    def _js(self, script):
        self.view.evaluate_javascript(script, -1, None, None, None, None, None)

    def _send(self, **props):
        """Tell the page how the note looks now, such as its title."""
        if self._ready:
            self._js(f'ynote.set({json.dumps(props)})')

    def _look(self):
        paper, bar = PALETTE[self._color]
        return {'title': self.title, 'pinned': self._on_top,
                'collapsed': self._collapsed, 'fontSize': self._font_size,
                'opacity': self._opacity, 'composited': self._composited,
                'colors': {'paper': paper, 'bar': bar},
                'maximized': self.is_maximized(),
                'hiddenCount': self._hidden_count}

    def _on_message(self, _manager, result):
        try:
            message = json.loads(result.get_js_value().to_string())
        except (ValueError, AttributeError):
            return
        handler = getattr(self, '_do_' + message.get('type', '').replace('-', '_'), None)
        if handler is None:
            print(f"ynote: the page sent {message.get('type')!r}, which is not handled",
                  file=sys.stderr)
            return
        handler(message)

    def _do_ready(self, _message):
        self._ready = True
        note = dict(self._look(), doc=self._doc, imagesUrl=IMAGES_URI)
        self._js(f'ynote.load({json.dumps(note)})')
        if self._focus_on_load:
            self._js('ynote.focus()')

    def _do_changed(self, message):
        self._doc = message['doc']
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

    def _do_new_note(self, _message):
        self.app.new_note(near=self)

    def _do_hide(self, _message):
        self.hide()
        self.app.put_first_in_hidden([self])
        self.app._rebuild_indicator_menu()
        self._queue_save()

    def _do_hidden_notes(self, _message):
        self.app.show_hidden_notes_manager(self)

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

    def _do_menu(self, _message):
        # The right-click menu comes with the next step; until then the
        # title can be edited from here.
        self._js('ynote.editTitle()')

    def insert_image_file(self, path):
        """Copy an image into the images folder and put it at the cursor."""
        ext = os.path.splitext(path)[1].lower() or '.png'
        name = str(uuid.uuid4()) + ext
        os.makedirs(IMAGES_DIR, exist_ok=True)
        shutil.copyfile(path, os.path.join(IMAGES_DIR, name))
        self._js(f'ynote.insertImage({json.dumps(name)}, '
                 f'{json.dumps(os.path.basename(path))})')

    def _on_decide_policy(self, _view, decision, kind):
        # The page is the note: nothing navigates away from it, such as a
        # file dropped on it. A link opens in the browser.
        if kind != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        uri = decision.get_navigation_action().get_request().get_uri()
        if uri == PAGE_URI:
            return False
        decision.ignore()
        return True

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
        # Alt + scroll steps through the notes (PostItApp.scroll_notes()).
        if not _alt_only(event):
            return False
        dy = 0
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = event.get_scroll_deltas()
        elif event.direction == Gdk.ScrollDirection.DOWN:
            dy = 1
        elif event.direction == Gdk.ScrollDirection.UP:
            dy = -1
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

    def _on_key_release(self, _window, event):
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
        pending = self._snap_pending_move
        if pending is not None and (event.width, event.height) == pending[2:]:
            self._apply_snap_move()
        self._queue_save()
        return False

    def _on_window_state(self, _window, event):
        self._send(maximized=bool(event.new_window_state & Gdk.WindowState.MAXIMIZED))
        return False

    def _on_delete(self, *_):
        self._do_hide(None)
        return True

    def _lock_size(self, locked, width=-1):
        # A collapsed note cannot be resized, so the window manager never
        # tiles or maximizes an empty note.
        self.set_size_request(width if locked else -1, -1)
        self.set_resizable(not locked)

    def _collapse(self):
        width, height = self.get_size()
        self._expanded_height = height
        self._collapsed = True
        self._send(collapsed=True)
        self._lock_size(True, width)
        self.resize(width, TITLE_BAR_HEIGHT)

    def _expand(self):
        self._collapsed = False
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
            self._js('ynote.focus()')
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
        return set()

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
                    opacity=self._opacity, collapsed=self._collapsed)

