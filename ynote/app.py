import os
import shutil
import signal
import sys
import traceback
import uuid

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio

from . import autostart, focus, tray
from .config import (
    APP_ID, AUTOSTART_FILE, CODE_ANCHOR, CODE_PAD_CHAR, CONF_DIR, ICON_PATH, IMAGES_DIR,
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
from .snap import keep_reachable, place_beside
from .storage import (
    UnreadableNotesError, back_up, load_notes, save_notes, set_aside,
)
from .styles import BASE_CSS

class PostItApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.notes: dict[str, NoteWindow] = {}
        self._indicator    = None
        self._tray_menu    = None
        self._menu_rebuild_id = None
        self._hidden_notes_window = None
        self._current_note = None
        self._rich_clipboard = None
        self._rich_clipboard_owned = False
        self._ignore_next_clipboard_owner_change = False
        # Set when notes.json could not be read. Its images must survive until
        # the user restores the file, so cleanup is skipped for this run.
        self._keep_all_images = False
        # Notes read from notes.json that could not be opened. They are saved
        # back as they were read, so a bug in opening one never loses it.
        self._unopened_notes = []

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
        module = tray.load_app_indicator()
        if module is None:
            print('Ynote: the application indicator library is missing, so '
                  'there is no tray icon. Install gir1.2-ayatanaappindicator3-0.1.',
                  file=sys.stderr)
            return
        self._indicator = tray.make_indicator(module, ICON_PATH)
        self._rebuild_indicator_menu()

    def _show_notes(self):
        if any(w.get_visible() for w in self.notes.values()):
            self.raise_all()
        else:
            self.new_note()

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

    def _on_note_focus_out(self):
        # An untitled note shows its first line in the tray menu. Leaving a note
        # is when that line may have changed, and the tray is opened from
        # outside the notes, so the menu is brought up to date here.
        if self._menu_rebuild_id is None:
            self._menu_rebuild_id = GLib.timeout_add(
                300, self._rebuild_after_focus_out)

    def _rebuild_after_focus_out(self):
        self._menu_rebuild_id = None
        self._rebuild_indicator_menu()
        return False

    def _rebuild_indicator_menu(self):
        if self._indicator is None:
            return
        # The indicator keeps the one menu it was given and follows its items,
        # which is quieter than handing it a new menu each time.
        reuse = self._tray_menu is not None
        menu = self._tray_menu if reuse else Gtk.Menu()
        for child in menu.get_children():
            menu.remove(child)

        # Listed by the name the menu shows for each note.
        open_notes = sorted(
            ((tray.note_label(w.title, w.first_text()), nid, w)
             for nid, w in self.notes.items() if w.get_visible()),
            key=lambda item: (item[0].lower(), item[1]),
        )
        hidden_count = len(self.notes) - len(open_notes)

        # The notes come first under a header, so that a note is not mistaken
        # for an action. One separator only: the desktop gives each a lot of room.
        if open_notes:
            header = Gtk.MenuItem(label=tray.OPEN_NOTES_HEADER)
            header.set_sensitive(False)
            menu.append(header)
            for label, nid, w in open_notes:
                item = Gtk.MenuItem(label=label)
                item.connect('activate', lambda _evt, note=w: (focus.present_now(note), note.grab_focus()))
                menu.append(item)
            menu.append(Gtk.SeparatorMenuItem())

        new_note = Gtk.MenuItem(label=NEW_NOTE_LABEL)
        new_note.connect('activate', lambda _: self.new_note())
        menu.append(new_note)

        # The indicator library ignores a middle click when its target item is
        # hidden, so the item is there whenever there are notes to raise.
        show_item = Gtk.MenuItem(label=tray.RAISE_ALL_LABEL)
        show_item.connect('activate', lambda _: self._show_notes())
        menu.append(show_item)

        if hidden_count:
            restore_item = Gtk.MenuItem(
                label=tray.hidden_notes_label(hidden_count))
            restore_item.connect(
                'activate',
                lambda *_: self.show_hidden_notes_manager(from_tray=True))
            menu.append(restore_item)

        quit_item = Gtk.MenuItem(label='Quit')
        quit_item.connect('activate', lambda _: self.quit_app())
        menu.append(quit_item)

        menu.show_all()
        show_item.set_visible(bool(open_notes))
        self._tray_menu = menu
        if not reuse:
            self._indicator.set_menu(menu)
        # A middle click raises the notes without opening the menu.
        self._indicator.set_secondary_activate_target(show_item)
        self._refresh_hidden_notes_manager()

    # ------------------------------------------------------------------ notes

    def _load(self):
        try:
            saved = load_notes(NOTES_FILE)
            if saved:
                # The notes as they were before this run opened them, to fall
                # back on if opening or saving them goes wrong.
                back_up(NOTES_FILE)
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
        areas, primary = self._work_areas()
        for d in saved:
            if areas and all(k in d for k in ('x', 'y', 'w', 'h')):
                d['x'], d['y'] = keep_reachable(
                    (d['x'], d['y'], d['w'], d['h']), areas, primary)
            try:
                w = NoteWindow(self, d)
            except Exception:
                traceback.print_exc()
                self._unopened_notes.append(d)
                self._keep_all_images = True
                continue
            self.notes[w.note_id] = w
        if self._unopened_notes:
            GLib.idle_add(self._warn_unopened_notes,
                          len(self._unopened_notes))
        self._rebuild_indicator_menu()
        # Startup has no undo/redo history from the previous process, so only
        # images referenced by notes.json should survive.
        self._cleanup_orphaned_images([w.to_dict() for w in self.notes.values()],
                                      include_history=False)

    def _work_areas(self):
        """Every monitor's work area as (x, y, w, h), and the primary's."""
        display = Gdk.Display.get_default()
        if display is None or display.get_n_monitors() == 0:
            return [], None
        monitors = [display.get_monitor(i)
                    for i in range(display.get_n_monitors())]
        areas = []
        for m in monitors:
            a = m.get_workarea()
            areas.append((a.x, a.y, a.width, a.height))
        # X servers without a primary monitor set return None here.
        primary = display.get_primary_monitor()
        index = monitors.index(primary) if primary in monitors else 0
        return areas, areas[index]

    def new_note(self, near=None):
        d = {'id': str(uuid.uuid4())}
        if near is not None:
            d['x'], d['y'] = near.get_position()
        w = NoteWindow(self, d)
        # The window may be wider than its default size because of its
        # minimum width, so place it once that is known.
        size = w.get_size()
        natural = w.get_preferred_size()[1]
        size = (max(size[0], natural.width), max(size[1], natural.height))
        areas, primary = self._work_areas()
        if areas and near is not None:
            x, y = place_beside(near.get_position() + near.get_size(),
                                size, areas)
            w.move(x, y)
        elif primary is not None:
            n = len(self.notes)
            ax, ay, aw, ah = primary
            w.move(ax + (aw - size[0]) // 2 + (n * 30) % 90,
                   ay + (ah - size[1]) // 2 + (n * 25) % 75)
        self.notes[w.note_id] = w
        w.tv.grab_focus()
        focus.present_now(w)
        self.save_all()
        self._rebuild_indicator_menu()

    def delete_note(self, note_id: str):
        if note_id in self.notes:
            self.notes.pop(note_id).destroy()
        self.save_all()
        self._rebuild_indicator_menu()

    def show_note(self, note_id: str):
        if note_id in self.notes:
            focus.present_now(self.notes[note_id])
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
        newly_hidden = [w for w in self.notes.values() if w.get_visible()]
        for w in newly_hidden:
            w.hide()
        self.put_first_in_hidden(newly_hidden)
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

    def put_first_in_hidden(self, windows):
        """Move just-hidden windows to the top of the hidden list.

        The list runs from the most recently hidden note down, so a note
        hidden now goes first and the rest keep their order below it.
        """
        first = {id(w) for w in windows}
        rest = [(nid, w) for nid, w in self.hidden_notes() if id(w) not in first]
        ids = {id(w): nid for nid, w in self.notes.items()}
        self._assign_sort_order([(ids.get(id(w)), w) for w in windows] + rest)

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
            self._hidden_notes_window.set_from_tray()
        else:
            self._hidden_notes_window.set_parent_note(parent_note)
        self._hidden_notes_window.refresh()
        focus.present_now(self._hidden_notes_window)

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
        text = state.get('text', '').replace(CODE_ANCHOR, '')
        clipboard.set_text(text.replace(CODE_PAD_CHAR, ''), -1)
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

    def _warn_unopened_notes(self, count):
        dialog = Gtk.MessageDialog(
            transient_for=next(iter(self.notes.values()), None), modal=True,
            message_type=Gtk.MessageType.WARNING, buttons=Gtk.ButtonsType.OK,
            text=f'Ynote could not open {count} of your notes')
        dialog.format_secondary_text(
            'They are kept unchanged in notes.json and will open again once '
            'the problem is fixed. Run ynote in a terminal to see the error.')
        dialog.run()
        dialog.destroy()
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

        # Runtime undo/redo history. This prevents redo from losing an image
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
        data = ([w.to_dict() for w in self.notes.values()]
                + self._unopened_notes)
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
