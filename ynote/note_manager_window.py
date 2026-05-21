import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class HiddenNotesWindow(Gtk.Window):
    NOTE_ID = 0
    LABEL = 1

    def __init__(self, app):
        super().__init__(application=app, title='Hidden Notes')
        self.app = app
        self._parent_note = None
        self._tray_icon = None
        self._position_mode = None
        self._did_initial_position = False
        self.set_default_size(360, 300)
        self.set_border_width(10)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        root.pack_start(header, False, False, 0)

        self._summary = Gtk.Label()
        self._summary.set_xalign(0)
        header.pack_start(self._summary, True, True, 0)

        self._up_btn = Gtk.Button(label='↑')
        self._up_btn.set_tooltip_text('Move up')
        self._up_btn.connect('clicked', lambda *_: self._move_selected(-1))
        header.pack_start(self._up_btn, False, False, 0)

        self._down_btn = Gtk.Button(label='↓')
        self._down_btn.set_tooltip_text('Move down')
        self._down_btn.connect('clicked', lambda *_: self._move_selected(1))
        header.pack_start(self._down_btn, False, False, 0)

        self._store = Gtk.ListStore(str, str)
        self._tree = Gtk.TreeView(model=self._store)
        self._tree.set_headers_visible(False)
        self._tree.connect('row-activated', self._on_row_activated)

        selection = self._tree.get_selection()
        selection.connect('changed', lambda *_: self._refresh_actions())

        title_cell = Gtk.CellRendererText()
        title_column = Gtk.TreeViewColumn('Title', title_cell, text=self.LABEL)
        title_column.set_expand(True)
        self._tree.append_column(title_column)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self._tree)
        root.pack_start(scroller, True, True, 0)

        actions = Gtk.ButtonBox(orientation=Gtk.Orientation.HORIZONTAL)
        actions.set_layout(Gtk.ButtonBoxStyle.END)
        actions.set_spacing(6)
        root.pack_start(actions, False, False, 0)

        self._restore_all_btn = Gtk.Button(label='Restore All')
        self._restore_all_btn.connect('clicked', lambda *_: self._restore_all())
        actions.add(self._restore_all_btn)

        close_btn = Gtk.Button(label='Close')
        close_btn.connect('clicked', lambda *_: self.destroy())
        actions.add(close_btn)

        self.refresh()

    def set_parent_note(self, parent_note):
        self._parent_note = parent_note
        self._tray_icon = None
        self._position_mode = 'note'
        self._did_initial_position = False
        if parent_note is not None:
            self.set_transient_for(parent_note)
        else:
            self.set_transient_for(None)

    def set_tray_icon(self, tray_icon):
        self._parent_note = None
        self._tray_icon = tray_icon
        self._position_mode = 'tray'
        self._did_initial_position = False
        self.set_transient_for(None)

    def refresh(self):
        selected_id = self._selected_note_id()
        self._store.clear()

        hidden = self.app.hidden_notes()
        for note_id, window in hidden:
            title = window.title or '(untitled)'
            self._store.append([note_id, title])

        count = len(hidden)
        if count == 1:
            self._summary.set_text('1 hidden note')
        else:
            self._summary.set_text(f'{count} hidden notes')

        if selected_id:
            self._select_note(selected_id)

        self._restore_all_btn.set_sensitive(bool(hidden))
        self._refresh_actions()
        self.show_all()
        self._position_once()

    def _position_once(self):
        if self._did_initial_position:
            return

        if self._position_mode == 'tray' and self._move_below_tray_icon():
            self._did_initial_position = True
            return

        if self._position_mode == 'note' and self._center_on_parent_note():
            self._did_initial_position = True

    def _center_on_parent_note(self):
        parent = self._parent_note
        if parent is None or not parent.get_visible():
            return False

        px, py = parent.get_position()
        pw, ph = parent.get_size()
        self.resize(360, 300)
        self.move(px + (pw - 360) // 2, py + (ph - 300) // 2)
        return True

    def _move_below_tray_icon(self):
        tray_icon = self._tray_icon
        if tray_icon is None:
            return False

        ok, screen, area, _orientation = tray_icon.get_geometry()
        if not ok:
            return False

        width, height = 360, 300
        self.resize(width, height)

        x = area.x + (area.width - width) // 2
        y = area.y + area.height

        monitor = screen.get_monitor_at_point(area.x, area.y)
        monitor_geo = screen.get_monitor_geometry(monitor)
        x = max(monitor_geo.x, min(x, monitor_geo.x + monitor_geo.width - width))
        y = max(monitor_geo.y, min(y, monitor_geo.y + monitor_geo.height - height))

        self.move(x, y)
        return True

    def _selected_note_id(self):
        selection = self._tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return None
        return model[tree_iter][self.NOTE_ID]

    def _select_note(self, note_id):
        for row in self._store:
            if row[self.NOTE_ID] == note_id:
                self._tree.get_selection().select_iter(row.iter)
                self._tree.scroll_to_cell(row.path, None, False, 0, 0)
                return

    def _refresh_actions(self):
        has_note = self._selected_note_id() is not None
        self._up_btn.set_sensitive(has_note)
        self._down_btn.set_sensitive(has_note)

    def _move_selected(self, direction):
        note_id = self._selected_note_id()
        if note_id:
            self.app.move_hidden_note(note_id, direction)
            self.refresh()
            self._select_note(note_id)

    def _on_row_activated(self, _tree, path, _column):
        tree_iter = self._store.get_iter(path)
        self.app.show_note(self._store[tree_iter][self.NOTE_ID])
        self.destroy()

    def _restore_all(self):
        self.app.show_all()
        self.destroy()
