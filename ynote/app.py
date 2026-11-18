import os
import shutil
import signal
import sys
import uuid

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio

from . import autostart
from .config import (
    APP_ID, AUTOSTART_FILE, CODE_ANCHOR, CONF_DIR, ICON_PATH, IMAGES_DIR,
    NEW_NOTE_LABEL, NOTES_FILE, SETTINGS_FILE, UNTITLED_LABEL, display_path,
)
from .images import (
    cleanup_orphaned_images,
    image_files_from_metadata,
    referenced_image_files,
)
from .note_manager_window import HiddenNotesWindow
from .note_window import NoteWindow
from .search import Note
from .storage import UnreadableNotesError, load_notes, save_notes, set_aside
from .styles import BASE_CSS

class PostItApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.notes: dict[str, NoteWindow] = {}
        self._status_icon  = None
        self._tray_menu    = None
        self._notes_raised = False
        self._hidden_notes_window = None
        self._current_note = None
        self._rich_clipboard = None
        self._rich_clipboard_owned = False
        self._ignore_next_clipboard_owner_change = False
        # Set when notes.json could not be read. Its images must survive until
        # the user restores the file, so cleanup is skipped for this run.
        self._keep_all_images = False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        os.makedirs(CONF_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)

        # Autostart runs the `ynote` command, so it only makes sense when the
        # package is installed, not for a bare source checkout.
        self.autostart_available = shutil.which('ynote') is not None
        autostart.enable_on_first_run(
            AUTOSTART_FILE, SETTINGS_FILE, self.autostart_available)

        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.set_property('gtk-tooltip-timeout', 0)

        if os.path.exists(ICON_PATH):
            Gtk.Window.set_default_icon_from_file(ICON_PATH)

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.connect('owner-change', self._on_clipboard_owner_change)

        prov = Gtk.CssProvider()
        prov.load_from_data(BASE_CSS)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self._setup_status_icon()

        self._load()
        self.hold()

        signal.signal(signal.SIGTERM, lambda *_: self.quit_app())
        signal.signal(signal.SIGINT,  lambda *_: self.quit_app())
        signal.signal(signal.SIGHUP,  signal.SIG_IGN)  # survive terminal close

        quit_action = Gio.SimpleAction.new('quit', None)
        quit_action.connect('activate', lambda *_: self.quit_app())
        self.add_action(quit_action)

    def autostart_enabled(self):
        return autostart.is_enabled(AUTOSTART_FILE)

    def set_autostart(self, enabled):
        autostart.set_enabled(AUTOSTART_FILE, enabled)

    def do_activate(self):
        visible = [w for w in self.notes.values() if w.get_visible()]
        if visible:
            for w in visible:
                w.present()
        else:
            self.new_note()

    # ------------------------------------------------------------------ tray icon

    def _setup_status_icon(self):
        self._status_icon = Gtk.StatusIcon()
        if os.path.exists(ICON_PATH):
            self._status_icon.set_from_file(ICON_PATH)
        else:
            self._status_icon.set_from_icon_name('accessories-text-editor')
        self._status_icon.set_tooltip_text('Ynote')
        self._status_icon.set_visible(True)
        self._status_icon.connect('activate', self._on_tray_click)
        self._status_icon.connect('popup-menu', self._on_tray_menu)
        self._rebuild_indicator_menu()

    def _on_tray_click(self, _):
        if not any(w.get_visible() for w in self.notes.values()):
            self.new_note()
            self._notes_raised = True
            return

        if self._notes_raised:
            lowerable = [w for w in self.notes.values()
                         if w.get_visible() and not w._on_top]
            if lowerable:
                self._lower_all()
                self._notes_raised = False
        else:
            self.raise_all()
            self._notes_raised = True

    def _focus_note(self, note):
        try:
            from gi.repository import GdkX11
        except ImportError:
            note.present()
            return
        gdk_win = note.get_window()
        if gdk_win:
            gdk_win.focus(GdkX11.x11_get_server_time(gdk_win))

    def _on_note_focus_in(self, note=None):
        if note is not None:
            self._current_note = note
        self._notes_raised = True

    def _on_note_focus_out(self):
        # After a short delay (so the tray click handler runs first), reset the
        # flag if no note has focus — meaning notes went to background naturally.
        GLib.timeout_add(200, self._check_notes_lost_focus)

    def _check_notes_lost_focus(self):
        if not any(w.is_active() for w in self.notes.values()):
            self._notes_raised = False
        return False

    def _on_tray_menu(self, icon, button, time):
        if self._tray_menu:
            self._tray_menu.popup(None, None,
                                  Gtk.StatusIcon.position_menu,
                                  icon, button, time)

    def _lower_all(self):
        for w in self.notes.values():
            if w.get_visible() and not w._on_top:
                gdk_win = w.get_window()
                if gdk_win:
                    gdk_win.lower()

    def _rebuild_indicator_menu(self):
        menu = Gtk.Menu()

        open_notes = sorted(
            [(nid, w) for nid, w in self.notes.items() if w.get_visible()],
            key=lambda item: (item[1].title.lower(), item[0]),
        )
        for nid, w in open_notes:
            label = w.title or UNTITLED_LABEL
            item = Gtk.MenuItem(label=label)
            item.connect('activate', lambda _evt, note=w: (note.present(), note.grab_focus()))
            menu.append(item)

        if open_notes:
            menu.append(Gtk.SeparatorMenuItem())

        restore_item = Gtk.MenuItem(label='Hidden Notes')
        restore_item.connect(
            'activate',
            lambda *_: self.show_hidden_notes_manager(from_tray=True))
        menu.append(restore_item)
        menu.append(Gtk.SeparatorMenuItem())

        new_note = Gtk.MenuItem(label=NEW_NOTE_LABEL)
        new_note.connect('activate', lambda _: self.new_note())
        menu.append(new_note)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label='Quit')
        quit_item.connect('activate', lambda _: self.quit_app())
        menu.append(quit_item)

        menu.show_all()
        self._tray_menu = menu
        self._refresh_hidden_notes_manager()

    # ------------------------------------------------------------------ notes

    def _load(self):
        try:
            saved = load_notes(NOTES_FILE)
        except UnreadableNotesError as e:
            # Never let the empty note below overwrite a file we could not
            # read: keep it aside and tell the user where it went.
            kept = set_aside(NOTES_FILE)
            print(f'ynote: could not read {NOTES_FILE} ({e}); kept it as {kept}',
                  file=sys.stderr)
            self._keep_all_images = True
            saved = None
            GLib.idle_add(self._warn_unreadable_notes, kept)
        if not saved:
            self.new_note()
            return
        for d in saved:
            w = NoteWindow(self, d)
            self.notes[w.note_id] = w
        self._rebuild_indicator_menu()
        # Startup has no undo/redo history from the previous process, so only
        # images referenced by notes.json should survive.
        self._cleanup_orphaned_images([w.to_dict() for w in self.notes.values()],
                                      include_history=False)

    def new_note(self, near=None):
        if near is not None:
            px, py = near.get_position()
            pw, _h = near.get_size()
            x, y = px + pw + 10, py
        else:
            n = len(self.notes)
            display = Gdk.Display.get_default()
            # X servers without a primary monitor set return None here.
            monitor = display.get_primary_monitor() or display.get_monitor(0)
            geo = monitor.get_geometry()
            x = geo.x + (geo.width  - 238) // 2 + (n * 30) % 90
            y = geo.y + (geo.height - 300) // 2 + (n * 25) % 75
        d = {'id': str(uuid.uuid4()), 'x': x, 'y': y}
        w = NoteWindow(self, d)
        self.notes[w.note_id] = w
        w.tv.grab_focus()
        self.save_all()
        self._rebuild_indicator_menu()

    def delete_note(self, note_id: str):
        if note_id in self.notes:
            self.notes.pop(note_id).destroy()
        self.save_all()
        self._rebuild_indicator_menu()

    def show_note(self, note_id: str):
        if note_id in self.notes:
            w = self.notes[note_id]
            w.show()
            w.present()
        self._rebuild_indicator_menu()
        self.save_all()

    def searchable_notes(self, first=None):
        # The searching note first, then visible notes, then hidden ones.
        windows = sorted(self.notes.values(),
                         key=lambda w: (w is not first, not w.get_visible()))
        return [Note(w.note_id, w.title or UNTITLED_LABEL, not w.get_visible(),
                     w.buffer_text()) for w in windows]

    def reveal_match(self, note_id, start, end):
        w = self.notes.get(note_id)
        if w is None:
            return
        if not w.get_visible():
            self.show_note(note_id)
        w.present()
        w.show_match(start, end)

    def raise_all(self):
        try:
            from gi.repository import GdkX11
            use_x11 = True
        except ImportError:
            use_x11 = False

        for w in self.notes.values():
            if not w.get_visible():
                continue
            w.set_urgency_hint(False)
            gdk_win = w.get_window()
            if gdk_win and use_x11:
                ts = GdkX11.x11_get_server_time(gdk_win)
                gdk_win.focus(ts)
            else:
                w.present()

    def show_all(self):
        for w in self.notes.values():
            w.show()
            w.present()
        self._rebuild_indicator_menu()
        self.save_all()

    def hide_all(self):
        for w in self.notes.values():
            w.hide()
        self._rebuild_indicator_menu()
        self.save_all()

    def hidden_notes(self):
        return sorted(
            [(nid, w) for nid, w in self.notes.items() if not w.get_visible()],
            key=lambda item: (
                item[1].sort_order,
                item[1].title.lower(),
                item[0],
            ),
        )

    def move_hidden_note(self, note_id, direction):
        note = self.notes.get(note_id)
        if note is None or note.get_visible():
            return

        siblings = self.hidden_notes()
        index = next((i for i, (nid, _) in enumerate(siblings)
                      if nid == note_id), None)
        if index is None:
            return

        target = index + direction
        if target < 0 or target >= len(siblings):
            return

        siblings[index], siblings[target] = siblings[target], siblings[index]
        self._assign_sort_order(siblings)
        self.save_all()
        self._rebuild_indicator_menu()

    def _assign_sort_order(self, notes):
        for index, (_, note) in enumerate(notes):
            note.sort_order = float(index)

    def show_hidden_notes_manager(self, parent_note=None, from_tray=False):
        if parent_note is None and not from_tray:
            parent_note = self._current_note
        if self._hidden_notes_window is None:
            self._hidden_notes_window = HiddenNotesWindow(self)
            self._hidden_notes_window.connect(
                'destroy', lambda *_: self._clear_hidden_notes_manager())
        if from_tray:
            self._hidden_notes_window.set_tray_icon(self._status_icon)
        else:
            self._hidden_notes_window.set_parent_note(parent_note)
        self._hidden_notes_window.refresh()
        self._hidden_notes_window.present()

    def _clear_hidden_notes_manager(self):
        self._hidden_notes_window = None

    def _refresh_hidden_notes_manager(self):
        if self._hidden_notes_window is not None:
            self._hidden_notes_window.refresh()

    def set_rich_clipboard(self, state):
        self._rich_clipboard = state
        self._rich_clipboard_owned = True
        self._ignore_next_clipboard_owner_change = True 

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(state.get('text', '').replace(CODE_ANCHOR, ''), -1)
        GLib.idle_add(self._finish_rich_clipboard_claim)

    def _finish_rich_clipboard_claim(self):
        self._ignore_next_clipboard_owner_change = False
        return False

    def _on_clipboard_owner_change(self, *_):
        if self._ignore_next_clipboard_owner_change:
            self._ignore_next_clipboard_owner_change = False
            return
        self._rich_clipboard = None
        self._rich_clipboard_owned = False

    def rich_clipboard_state(self):
        if not self._rich_clipboard_owned:
            return None
        return self._rich_clipboard

    def _warn_unreadable_notes(self, kept):
        open_folder = 1
        dialog = Gtk.MessageDialog(
            transient_for=next(iter(self.notes.values()), None), modal=True,
            message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.NONE,
            text='Ynote could not read your notes')
        dialog.format_secondary_text(
            f'Your notes file was kept as {display_path(kept)}, and Ynote '
            'started with an empty note. To get your notes back, quit Ynote, '
            'fix that file and rename it to notes.json, then start Ynote again.')
        dialog.add_button('Open Folder', open_folder)
        dialog.add_button('OK', Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        response = dialog.run()
        dialog.destroy()
        if response == open_folder:
            self.open_uri(GLib.filename_to_uri(CONF_DIR, None))
        return False

    def open_uri(self, uri):
        """Open a link or folder in the user's default app."""
        context = Gdk.Display.get_default().get_app_launch_context()
        # GDK_BACKEND=x11 is meant for Ynote alone. In a Wayland session the
        # browser should pick its own backend. Over SSH there is no Wayland
        # display to inherit, and x11 keeps the app on the forwarded display.
        if os.environ.get('WAYLAND_DISPLAY'):
            context.unsetenv('GDK_BACKEND')
        try:
            Gio.AppInfo.launch_default_for_uri(uri, context)
        except GLib.Error as e:
            print(f'ynote: could not open {uri}: {e.message}', file=sys.stderr)

    def _referenced_image_files(self, data=None, include_history=True):
        if data is None:
            data = [w.to_dict() for w in self.notes.values()]

        # Runtime undo/redo history. This prevents Ctrl+Y from losing an image
        # after the image was removed from the visible note and autosave ran.
        history_files = set()
        if include_history:
            for w in self.notes.values():
                history_files.update(w.history_image_files())
            rich_clipboard = getattr(self, '_rich_clipboard', None)
            if rich_clipboard:
                history_files.update(
                    image_files_from_metadata(rich_clipboard.get('images', [])))

        return referenced_image_files(data, history_files)

    def _cleanup_orphaned_images(self, data=None, include_history=True):
        # Delete copied image files that are no longer referenced by any live
        # note or, during runtime, undo/redo history.
        if self._keep_all_images:
            return
        referenced = self._referenced_image_files(data, include_history=include_history)
        cleanup_orphaned_images(IMAGES_DIR, referenced)

    def save_all(self, include_history=True):
        data = [w.to_dict() for w in self.notes.values()]
        try:
            save_notes(data, NOTES_FILE)
            self._cleanup_orphaned_images(data, include_history=include_history)
        except OSError as e:
            print(f'ynote: save failed: {e}', file=sys.stderr)

    def quit_app(self):
        # Undo/redo history is not durable, so on quit only saved notes should
        # keep image files alive.
        self.save_all(include_history=False)
        self.release()
        Gtk.Application.quit(self)
