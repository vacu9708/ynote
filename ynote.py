#!/usr/bin/env python3
"""ynote.py — Sticky notes for Ubuntu/GNOME (GTK3)"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Gio, Pango, GdkPixbuf
import json, os, uuid, sys, signal, shutil, urllib.parse


APP_ID     = 'io.github.youngsikyang.ynote'
THIS_DIR  = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(THIS_DIR, 'icon.png')
CONF_DIR  = os.path.expanduser('~/.config/ynote')
NOTES_FILE = os.path.join(CONF_DIR, 'notes.json')
IMAGES_DIR = os.path.join(CONF_DIR, 'images')
IMAGE_ANCHOR = '\uFFFC'
# Images are displayed at their natural pixel size by default.
# The scrolled note body handles images that are larger than the current note.
# Invisible sentinel used so an otherwise empty line can carry the code tag.
# Older versions used NBSP (\u00a0), which renders as a visible space.
CODE_ANCHOR = '\u2060'

BASE_CSS = b"""
window.note { background: #FFFF99; }
box.hdr {
    padding: 2px 4px 2px 2px;
    background: #E8D800;
}
box.hdr > eventbox { min-height: 26px; }
box.btmbar {
    padding: 3px 5px 3px 3px;
    background: #E8D800;
    min-height: 30px;
}
box.btmbar .tool-group {
    padding: 0 2px;
}
separator.tool-separator {
    background: rgba(0,0,0,0.25);
    min-width: 1px;
    margin: 3px 3px;
}

box.hdr button, box.btmbar button {
    padding: 1px 4px;
    min-width: 20px;
    min-height: 20px;
    border-radius: 10px;
    border: none;
    box-shadow: none;
    background: rgba(0,0,0,0.18);
    font-size: 12px;
    font-weight: bold;
    color: #333;
}
box.hdr button.pin-top {
    min-width: 18px;
    min-height: 18px;
    padding: 1px 6px;
    border-radius: 14px;
    font-size: 18px;
}
box.hdr button:hover, box.btmbar button:hover { background: rgba(0,0,0,0.35); }
box.hdr button.pinned, box.btmbar button.pinned { background: rgba(0,0,0,0.55); color: #000; }
box.btmbar button.delete { background: rgba(180,0,0,0.55); color: #fff; }
box.btmbar button.delete:hover { background: rgba(180,0,0,0.85); }
label.title {
    color: #444;
    font-weight: bold;
    font-size: 16px;
    padding: 0 4px;
}
entry.title-edit {
    background: transparent;
    border: 1px solid rgba(0,0,0,0.25);
    border-radius: 3px;
    box-shadow: none;
    color: #333;
    font-weight: bold;
    font-size: 15px;
    min-height: 20px;
    padding: 0 4px;
}
textview, textview text {
    background: transparent;
    font-family: Ubuntu, Cantarell, DejaVu Sans, sans-serif;
    font-size: 14px;
}
box.search-bar {
    background: rgba(0,0,0,0.08);
    padding: 2px 4px;
    border-top: 1px solid rgba(0,0,0,0.15);
}
box.search-bar entry {
    min-height: 22px;
    font-size: 12px;
}
"""


class NoteWindow(Gtk.ApplicationWindow):
    def __init__(self, app, data: dict):
        super().__init__(application=app)
        self.app      = app
        data = dict(data)
        self.note_id  = data.get('id') or str(uuid.uuid4())
        self.title    = data.get('title', '')
        self._on_top  = bool(data.get('on_top', False))
        self._font_size = data.get('font_size', 14)
        self._sid       = None
        self._editing   = False
        self._restoring   = False
        self._snap_sid    = None
        self._history   = [{'text': data.get('text', ''),
                             'bold': data.get('bold_ranges', []),
                             'code': data.get('code_ranges', []),
                             'images': data.get('images', [])}]
        self._hist_pos  = 0
        self._pending_code_inserts = []
        self._image_widgets = []
        self._title_drag = None

        self._build(data)
        self.set_title(self.title or 'New Note')
        self.set_default_size(data.get('w', 200), data.get('h', 300))
        self.move(data.get('x', 200), data.get('y', 200))
        self.show_all()
        self.set_keep_above(self._on_top)
        self._refresh_pin()
        if data.get('hidden', False):
            self.hide()

    # ------------------------------------------------------------------ build

    def _build(self, data):
        self.set_decorated(False)
        self.set_resizable(True)
        self.set_skip_pager_hint(True)
        self.set_wmclass('ynote', 'Ynote')
        self.get_style_context().add_class('note')

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)

        # ---- Bars ----
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hdr.get_style_context().add_class('hdr')
        root.pack_start(hdr, False, False, 0)

        # Top bar(header) — single-click drags, double-click edits title, right-click shows context menu.
        # The pin button is packed at the far right; the title area expands to fill the remaining space.
        self._title_box = Gtk.EventBox()
        self._title_box.set_hexpand(True)
        self._title_box.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK)
        self._title_box.connect('button-press-event', self._on_title_click)
        self._title_box.connect('motion-notify-event', self._on_title_motion)
        self._title_box.connect('button-release-event', self._on_title_release)
        hdr.pack_start(self._title_box, True, True, 0)

        self._title_label = Gtk.Label(label=self.title or 'New Note')
        self._title_label.get_style_context().add_class('title')
        self._title_label.set_xalign(0)
        self._title_label.set_ellipsize(3)  # Pango.EllipsizeMode.END == 3
        self._title_box.add(self._title_label)

        self._pin_btn = Gtk.Button(label='📌')
        self._pin_btn.get_style_context().add_class('pin-top')
        self._pin_btn.set_tooltip_text('Always on Top (toggle)')
        self._pin_btn.set_can_focus(False)
        self._pin_btn.connect('clicked', lambda _: self._toggle_on_top())
        hdr.pack_end(self._pin_btn, False, False, 0)

        # Bottom bar — built here, packed into root after the search bar.
        # Wrapped in an EventBox so right-clicking empty bar area opens the same
        # menu as the title bar.
        self._bottom_bar_box = Gtk.EventBox()
        self._bottom_bar_box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self._bottom_bar_box.connect('button-press-event', self._on_bottom_bar_click)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_row.get_style_context().add_class('btmbar')
        self._bottom_bar_box.add(btn_row)

        # Left group: note/window-level actions.
        note_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        note_group.get_style_context().add_class('tool-group')
        btn_row.pack_start(note_group, False, False, 0)

        new_btn = Gtk.Button(label='+')
        new_btn.set_tooltip_text('New Note')
        new_btn.connect('clicked', lambda _: self.app.new_note(near=self))
        note_group.pack_start(new_btn, False, False, 0)

        min_btn = Gtk.Button(label='−')
        min_btn.set_tooltip_text('Minimize')
        min_btn.connect('clicked', lambda _: self.iconify())
        note_group.pack_start(min_btn, False, False, 0)

        close_btn = Gtk.Button(label='✕')
        close_btn.set_tooltip_text('Hide Note')
        close_btn.connect('clicked', lambda _: self._hide_note())
        note_group.pack_start(close_btn, False, False, 0)

        del_btn = Gtk.Button(label='🗑')
        del_btn.set_tooltip_text('Delete Note')
        del_btn.get_style_context().add_class('delete')
        del_btn.connect('clicked', lambda _: self.app.delete_note(self.note_id))
        note_group.pack_start(del_btn, False, False, 0)

        # Visual/semantic split between note actions and text-editing actions.
        split = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        split.get_style_context().add_class('tool-separator')
        btn_row.pack_start(split, False, False, 4)

        # Right group: text/content editing actions.
        text_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        text_group.get_style_context().add_class('tool-group')
        btn_row.pack_start(text_group, False, False, 0)

        bold_btn = Gtk.Button(label='B')
        bold_btn.set_tooltip_text('Bold  (Ctrl+B)')
        bold_btn.set_can_focus(False)
        bold_btn.connect('clicked', lambda _: self._toggle_bold())
        text_group.pack_start(bold_btn, False, False, 0)

        bullet_btn = Gtk.Button(label='•')
        bullet_btn.set_tooltip_text('Bullet list')
        bullet_btn.set_can_focus(False)
        bullet_btn.connect('clicked', lambda _: self._toggle_bullet())
        text_group.pack_start(bullet_btn, False, False, 0)

        code_btn = Gtk.Button(label='</>')
        code_btn.set_tooltip_text('Code block  (Ctrl+Shift+C)')
        code_btn.set_can_focus(False)
        code_btn.connect('clicked', lambda _: self._toggle_code_block())
        text_group.pack_start(code_btn, False, False, 0)

        image_btn = Gtk.Button(label='🖼')
        image_btn.set_tooltip_text('Insert image')
        image_btn.set_can_focus(False)
        image_btn.connect('clicked', lambda _: self._choose_and_insert_image())
        text_group.pack_start(image_btn, False, False, 0)

        font_sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        font_sep.get_style_context().add_class('tool-separator')
        text_group.pack_start(font_sep, False, False, 4)

        self._fontsize_btn = Gtk.Button(label=f'{self._font_size}px')
        self._fontsize_btn.set_tooltip_text('Font size')
        self._fontsize_btn.set_can_focus(False)
        self._fontsize_btn.connect('clicked', self._show_font_popover)
        text_group.pack_start(self._fontsize_btn, False, False, 0)
        self._build_font_popover()

        row_spacer = Gtk.Box()
        row_spacer.set_hexpand(True)
        btn_row.pack_start(row_spacer, True, True, 0)

        # Right-clicking any bottom-bar button opens the same menu as the title
        # bar. Left-click behavior is unchanged because _on_bottom_bar_click()
        # returns False for non-right-clicks.
        for btn in (self._pin_btn, new_btn, min_btn, close_btn, del_btn,
                    bold_btn, bullet_btn, code_btn, image_btn,
                    self._fontsize_btn):
            btn.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            btn.connect('button-press-event', self._on_bottom_bar_click)

        # ---- Text area ----
        self._sw = Gtk.ScrolledWindow()
        self._sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        root.pack_start(self._sw, True, True, 0)
        sw = self._sw

        self.tv = Gtk.TextView()
        self.tv.set_wrap_mode(Gtk.WrapMode.NONE)
        self.tv.set_left_margin(6)
        self.tv.set_right_margin(6)
        self.tv.set_top_margin(4)
        self.tv.set_bottom_margin(4)
        sw.add(self.tv)
        self._font_prov = Gtk.CssProvider()
        self.tv.get_style_context().add_provider(
            self._font_prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self._apply_note_font()

        buf = self.tv.get_buffer()
        buf.set_text(data.get('text', ''))
        buf.connect('insert-text', self._on_buf_insert_text)
        buf.connect_after('insert-text', self._after_buf_insert_text)
        buf.connect('changed', self._on_buf_changed)
        self._hl_tag   = buf.create_tag('search-hl',
                                        background='#FFCC00', foreground='#000')
        self._bold_tag = buf.create_tag('bold', weight=Pango.Weight.BOLD)
        self._code_tag = buf.create_tag('code',
                                        family='Ubuntu Mono, DejaVu Sans Mono, monospace',
                                        background='#EFEFD6',
                                        paragraph_background='#EFEFD6',
                                        foreground='#222',
                                        left_margin=8,
                                        right_margin=8,
                                        pixels_above_lines=2,
                                        pixels_below_lines=2)
        self._emoji_tag = buf.create_tag('emoji', scale=self._emoji_scale())
        self._hl_tag.set_priority(buf.get_tag_table().get_size() - 1)
        self._refresh_emoji_tags()
        for s, e in data.get('bold_ranges', []):
            buf.apply_tag(self._bold_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        for s, e in data.get('code_ranges', []):
            buf.apply_tag(self._code_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        self._restore_images(data.get('images', []))
        self.tv.connect('populate-popup', self._on_tv_popup)
        self.tv.connect('key-press-event', self._on_tv_key_press)
        self.tv.connect('button-press-event', self._on_tv_button_press)

        # ---- Search bar (hidden until Ctrl+F) ----
        # Wrapped in a Revealer so the widget is always realized — avoids the
        # "WIDGET_REALIZED_FOR_EVENT" crash that occurs when showing a widget
        # that was excluded from show_all() and then immediately receiving events.
        sbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        sbar.get_style_context().add_class('search-bar')
        self._search_bar = sbar

        self._search_revealer = Gtk.Revealer()
        self._search_revealer.set_transition_type(Gtk.RevealerTransitionType.NONE)
        self._search_revealer.set_reveal_child(False)
        self._search_revealer.add(sbar)
        root.pack_start(self._search_revealer, False, False, 0)
        root.pack_start(self._bottom_bar_box, False, False, 0)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(True)
        self._search_entry.set_placeholder_text('Search…')
        self._search_entry.connect('search-changed', lambda e: self._do_search())
        self._search_entry.connect('key-press-event', self._on_search_key)
        sbar.pack_start(self._search_entry, True, True, 0)

        close_btn = Gtk.Button(label='✕')
        close_btn.connect('clicked', lambda _: self._close_search())
        sbar.pack_start(close_btn, False, False, 0)

        # Keyboard shortcuts via AccelGroup (avoids unrealised-widget errors)
        accel = Gtk.AccelGroup()
        self.add_accel_group(accel)
        accel.connect(Gdk.KEY_f, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_search() or True)
        accel.connect(Gdk.KEY_b, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_bold() or True)
        accel.connect(Gdk.KEY_c,
                      Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
                      0, lambda *_: self._toggle_code_block() or True)
        accel.connect(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._undo() or True)
        accel.connect(Gdk.KEY_y, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._redo() or True)

        # Resize grips integrated into the bottom bar
        for edge, cursor in [
            (Gdk.WindowEdge.SOUTH_WEST, 'sw-resize'),
            (Gdk.WindowEdge.SOUTH_EAST, 'se-resize'),
        ]:
            grip = Gtk.EventBox()
            grip.set_size_request(14, -1)
            grip.add_events(
                Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.ENTER_NOTIFY_MASK)
            grip.connect('button-press-event',
                         lambda w, ev, e=edge: self._on_resize(w, ev, e))
            grip.connect('enter-notify-event',
                         lambda w, ev, c=cursor: self._set_resize_cursor(w, ev, c))
            if edge == Gdk.WindowEdge.SOUTH_EAST:
                btn_row.pack_end(grip, False, False, 0)
            else:
                btn_row.pack_start(grip, False, False, 0)
                btn_row.reorder_child(grip, 0)

        self.connect('configure-event',    self._on_configure)
        self.connect('focus-in-event',     lambda *_: self.app._on_note_focus_in())
        self.connect('focus-out-event',    lambda *_: self.app._on_note_focus_out())
        self.connect('window-state-event', self._on_window_state)
        self.connect('delete-event', lambda *_: self.app.quit_app() or True)

    def _on_window_state(self, _, event):
        if event.new_window_state & Gdk.WindowState.ICONIFIED:
            self.app._notes_raised = False

    # ------------------------------------------------------------------ title editing

    def _on_title_click(self, widget, ev):
        if ev.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and ev.button == 1:
            self._title_drag = None
            self._start_title_edit()
            return True
        if ev.button == 3:
            self._title_drag = None
            self._show_ctx_menu(ev)
            return True
        if ev.button == 1 and not self._editing:
            # Do not start a window move immediately on button-press.
            # On X11, begin_move_drag() grabs the pointer early enough that the
            # second click may never be delivered as DOUBLE_BUTTON_PRESS.  Wait
            # until the pointer actually moves past GTK's drag threshold.
            self._title_drag = (ev.button, ev.x_root, ev.y_root, ev.time)
            return True
        return False

    def _on_title_motion(self, widget, ev):
        drag = getattr(self, '_title_drag', None)
        if not drag or self._editing:
            return False

        button, x_root, y_root, event_time = drag
        threshold = Gtk.Settings.get_default().get_property('gtk-dnd-drag-threshold')
        if (abs(ev.x_root - x_root) < threshold
                and abs(ev.y_root - y_root) < threshold):
            return True

        self._title_drag = None
        self.begin_move_drag(button, int(x_root), int(y_root), event_time)
        return True

    def _on_title_release(self, widget, ev):
        if ev.button == 1:
            self._title_drag = None
        return False

    def _on_bottom_bar_click(self, widget, ev):
        if ev.button == 3:
            self._show_ctx_menu(ev)
            return True
        return False

    def _start_title_edit(self):
        self._editing = True
        self._title_box.remove(self._title_label)

        entry = Gtk.Entry()
        entry.set_text(self.title)
        entry.set_has_frame(False)
        entry.get_style_context().add_class('title-edit')
        entry.connect('activate', self._finish_title_edit)
        entry.connect('focus-out-event', lambda w, _: self._finish_title_edit(w))
        self._title_box.add(entry)
        entry.show()
        entry.grab_focus()
        self._entry_widget = entry

    def _finish_title_edit(self, entry):
        if not self._editing:
            return
        self._editing = False
        self.title = entry.get_text().strip()
        self._title_box.remove(entry)
        self._title_label.set_text(self.title or 'New Note')
        self._title_box.add(self._title_label)
        self._title_label.show()
        self.set_title(self.title or 'New Note')
        self.app._rebuild_indicator_menu()
        self._queue_save()

    # ------------------------------------------------------------------ events

    def _on_resize(self, widget, ev, edge=Gdk.WindowEdge.SOUTH_EAST):
        if ev.button == 1:
            self.begin_resize_drag(
                edge, ev.button, int(ev.x_root), int(ev.y_root), ev.time)

    def _set_resize_cursor(self, widget, ev, cursor='se-resize'):
        win = widget.get_window()
        if win:
            cur = Gdk.Cursor.new_from_name(Gdk.Display.get_default(), cursor)
            win.set_cursor(cur)


    # ------------------------------------------------------------------ images

    def _normalize_image_meta(self, meta, include_offset=False):
        # Image metadata schema:
        # {"file": "<uuid>.<ext>", "original_name": "...", "offset": N}
        meta = dict(meta or {})
        name = meta.get('file', '')

        normalized = {}
        if name:
            normalized['file'] = name if os.path.isabs(name) else os.path.basename(name)
        if meta.get('original_name'):
            normalized['original_name'] = meta.get('original_name')
        if include_offset:
            normalized['offset'] = int(meta.get('offset', 0))
        return normalized

    def _image_path(self, meta):
        meta = self._normalize_image_meta(meta)
        name = meta.get('file', '')
        if not name:
            return ''
        if os.path.isabs(name):
            return name
        return os.path.join(IMAGES_DIR, os.path.basename(name))

    def _is_supported_image_file(self, path):
        try:
            GdkPixbuf.Pixbuf.get_file_info(path)
            return True
        except Exception:
            return False

    def _image_display_scale(self):
        # Gtk.Image sizes are in logical GTK units.  On HiDPI displays a pixbuf
        # that is W x H image pixels would otherwise request W x H logical units,
        # which makes it appear scale_factor times larger than its original
        # physical pixel size.
        scale = 1
        try:
            scale = int(self.get_scale_factor())
        except Exception:
            scale = 1

        if scale <= 1:
            try:
                display = Gdk.Display.get_default()
                monitor = display.get_primary_monitor() if display else None
                if monitor is not None:
                    scale = int(monitor.get_scale_factor())
            except Exception:
                scale = 1
        return max(1, scale)

    def _pixbuf_for_display_at_original_size(self, pixbuf):
        scale = self._image_display_scale()
        if scale <= 1:
            return pixbuf

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        display_width = max(1, int(round(width / scale)))
        display_height = max(1, int(round(height / scale)))

        if display_width == width and display_height == height:
            return pixbuf
        return pixbuf.scale_simple(
            display_width, display_height, GdkPixbuf.InterpType.BILINEAR)

    def _load_image_pixbuf(self, path):
        # Load the source image, then convert its pixel dimensions to GTK
        # logical units so it appears at the original physical size on HiDPI.
        # Large images remain scrollable inside the note rather than being
        # silently constrained to the note width.
        return self._pixbuf_for_display_at_original_size(
            GdkPixbuf.Pixbuf.new_from_file(path))

    def _attach_image_widget(self, anchor, meta):
        path = self._image_path(meta)
        if not path or not os.path.exists(path):
            return
        try:
            pixbuf = self._load_image_pixbuf(path)
        except Exception as e:
            print(f'ynote: failed to load image {path}: {e}', file=sys.stderr)
            return

        image = Gtk.Image.new_from_pixbuf(pixbuf)
        box = Gtk.EventBox()
        box.add(image)
        box.set_tooltip_text(meta.get('original_name') or os.path.basename(path))
        box.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        box.connect('button-press-event', self._on_image_button_press, anchor)
        self.tv.add_child_at_anchor(box, anchor)
        box.show_all()
        anchor.ynote_image = self._normalize_image_meta(meta)
        self._image_widgets.append(box)

    def _restore_images(self, images):
        if not images:
            return
        buf = self.tv.get_buffer()
        normalized_images = [self._normalize_image_meta(m, include_offset=True) for m in images]
        for meta in sorted(normalized_images, key=lambda m: m.get('offset', 0), reverse=True):
            offset = int(meta.get('offset', 0))
            it = buf.get_iter_at_offset(offset)
            next_it = it.copy()
            if (not it.is_end()) and it.get_char() == IMAGE_ANCHOR:
                next_it.forward_char()
                buf.delete(it, next_it)
                it = buf.get_iter_at_offset(offset)
            anchor = buf.create_child_anchor(it)
            self._attach_image_widget(anchor, meta)

    def _remove_all_image_widgets(self):
        for widget in list(self._image_widgets):
            parent = widget.get_parent()
            if parent:
                parent.remove(widget)
        self._image_widgets.clear()

    def _get_images_state(self):
        buf = self.tv.get_buffer()
        images = []
        it = buf.get_start_iter()
        while not it.is_end():
            anchor = it.get_child_anchor()
            if anchor is not None and hasattr(anchor, 'ynote_image'):
                meta = self._normalize_image_meta(anchor.ynote_image)
                meta['offset'] = it.get_offset()
                images.append(meta)
            it.forward_char()
        return images

    def image_file_paths(self):
        paths = []
        for meta in self._get_images_state():
            path = self._image_path(meta)
            if path:
                paths.append(path)
        return paths

    def history_image_files(self):
        files = set()
        for state in self._history:
            for meta in state.get('images', []):
                name = meta.get('file', '')
                if name and not os.path.isabs(name):
                    files.add(os.path.basename(name))
        return files

    def _save_pixbuf_to_images_dir(self, pixbuf, original_name='pasted-image.png'):
        os.makedirs(IMAGES_DIR, exist_ok=True)
        image_id = str(uuid.uuid4())
        filename = image_id + '.png'
        dest = os.path.join(IMAGES_DIR, filename)
        pixbuf.savev(dest, 'png', [], [])
        return {
            'file': filename,
            'original_name': original_name,
        }

    def _copy_image_to_images_dir(self, src_path):
        os.makedirs(IMAGES_DIR, exist_ok=True)
        image_id = str(uuid.uuid4())
        base = os.path.basename(src_path)
        _, ext = os.path.splitext(base)
        ext = ext.lower() if ext else '.png'
        filename = image_id + ext
        dest = os.path.join(IMAGES_DIR, filename)
        shutil.copy2(src_path, dest)
        return {
            'file': filename,
            'original_name': base,
        }

    def _insert_image_meta_at_cursor(self, meta):
        buf = self.tv.get_buffer()
        if buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            buf.delete(start, end)
        it = buf.get_iter_at_mark(buf.get_insert())
        anchor = buf.create_child_anchor(it)
        self._attach_image_widget(anchor, meta)
        after = buf.get_iter_at_mark(buf.get_insert())
        buf.place_cursor(after)
        self._take_snapshot()
        self._queue_save()
        self.tv.grab_focus()

    def _insert_image_from_path(self, path):
        if not path or not os.path.exists(path) or not self._is_supported_image_file(path):
            return False
        try:
            meta = self._copy_image_to_images_dir(path)
            self._insert_image_meta_at_cursor(meta)
            return True
        except Exception as e:
            print(f'ynote: failed to insert image {path}: {e}', file=sys.stderr)
            return False

    def _insert_image_from_pixbuf(self, pixbuf, original_name='pasted-image.png'):
        if pixbuf is None:
            return False
        try:
            meta = self._save_pixbuf_to_images_dir(pixbuf, original_name)
            self._insert_image_meta_at_cursor(meta)
            return True
        except Exception as e:
            print(f'ynote: failed to insert pasted image: {e}', file=sys.stderr)
            return False

    def _choose_and_insert_image(self):
        dialog = Gtk.FileChooserDialog(
            title='Insert Image', transient_for=self,
            action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OPEN, Gtk.ResponseType.OK)
        flt = Gtk.FileFilter()
        flt.set_name('Images')
        for mime in ('image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'):
            flt.add_mime_type(mime)
        for pattern in ('*.png', '*.jpg', '*.jpeg', '*.gif', '*.webp', '*.bmp'):
            flt.add_pattern(pattern)
        dialog.add_filter(flt)
        response = dialog.run()
        filename = dialog.get_filename() if response == Gtk.ResponseType.OK else None
        dialog.destroy()
        if filename:
            self._insert_image_from_path(filename)

    def _clipboard_first_local_image_path(self, clipboard):
        try:
            uris = clipboard.wait_for_uris()
        except Exception:
            uris = None
        if not uris:
            return None
        for uri in uris:
            parsed = urllib.parse.urlparse(uri)
            if parsed.scheme != 'file':
                continue
            path = urllib.parse.unquote(parsed.path)
            if path and os.path.exists(path) and self._is_supported_image_file(path):
                return path
        return None

    def _paste_image_if_available(self):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        try:
            if clipboard.wait_is_image_available():
                pixbuf = clipboard.wait_for_image()
                if pixbuf is not None:
                    return self._insert_image_from_pixbuf(pixbuf)
        except Exception as e:
            print(f'ynote: image paste failed: {e}', file=sys.stderr)

        path = self._clipboard_first_local_image_path(clipboard)
        if path:
            return self._insert_image_from_path(path)
        return False

    def _on_image_button_press(self, widget, ev, anchor):
        if ev.button != 3:
            return False
        menu = Gtk.Menu()
        remove_item = Gtk.MenuItem(label='Remove Image')
        remove_item.connect('activate', lambda _: self._remove_image_anchor(anchor))
        menu.append(remove_item)
        menu.show_all()
        menu.popup_at_pointer(ev)
        return True

    def _remove_image_anchor(self, anchor):
        buf = self.tv.get_buffer()
        it = buf.get_start_iter()
        while not it.is_end():
            if it.get_child_anchor() is anchor:
                end = it.copy()
                end.forward_char()
                buf.delete(it, end)
                self._take_snapshot()
                self.app.save_all()
                return
            it.forward_char()

    # ------------------------------------------------------------------ search

    def _on_search_key(self, entry, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self._close_search()
            return True
        return False

    def _toggle_search(self):
        if self._search_revealer.get_reveal_child():
            self._close_search()
        else:
            self._search_revealer.set_reveal_child(True)
            GLib.idle_add(self._search_entry.grab_focus)

    def _close_search(self):
        self._search_revealer.set_reveal_child(False)
        self._search_entry.set_text('')
        self._clear_highlights()
        self.tv.grab_focus()

    def _do_search(self):
        self._clear_highlights()
        query = self._search_entry.get_text()
        if not query:
            return
        buf   = self.tv.get_buffer()
        start = buf.get_start_iter()
        flags = Gtk.TextSearchFlags.CASE_INSENSITIVE | \
                Gtk.TextSearchFlags.TEXT_ONLY
        while True:
            result = start.forward_search(query, flags, None)
            if not result:
                break
            m_start, m_end = result
            buf.apply_tag(self._hl_tag, m_start, m_end)
            start = m_end

    def _clear_highlights(self):
        buf = self.tv.get_buffer()
        buf.remove_tag(self._hl_tag,
                       buf.get_start_iter(), buf.get_end_iter())

    # ------------------------------------------------------------------ undo/redo

    def _iter_has_tag_context(self, it, tag):
        if it.has_tag(tag):
            return True
        prev = it.copy()
        return prev.backward_char() and prev.has_tag(tag)

    def _on_buf_insert_text(self, buf, location, text, length):
        if self._restoring:
            return
        self._pending_code_inserts.append(
            self._iter_has_tag_context(location, self._code_tag))

    def _after_buf_insert_text(self, buf, location, text, length):
        if self._restoring:
            return
        apply_code = (
            self._pending_code_inserts.pop(0)
            if self._pending_code_inserts else False)
        if not apply_code or not text:
            if text:
                self._refresh_emoji_tags()
            return

        self._refresh_emoji_tags()
        if text == '\n':
            return

        end = location.copy()
        start = end.copy()
        start.backward_chars(len(text))
        self._apply_tag_to_non_newline_chars(buf, self._code_tag, start, end)
        self._remove_redundant_code_anchors(start.get_line(), end.get_line())

    def _apply_tag_to_non_newline_chars(self, buf, tag, start, end):
        it = start.copy()
        range_start = None
        while it.compare(end) < 0:
            char = it.get_char()
            next_it = it.copy()
            next_it.forward_char()
            if char == '\n':
                if range_start is not None:
                    buf.apply_tag(tag, range_start, it)
                    range_start = None
            elif range_start is None:
                range_start = it.copy()
            it = next_it
        if range_start is not None:
            buf.apply_tag(tag, range_start, end)

    def _on_buf_changed(self, buf):
        if self._restoring:
            return
        self._queue_save()
        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
        self._snap_sid = GLib.timeout_add(600, self._take_snapshot)

    def _take_snapshot(self):
        self._snap_sid = None
        state = self._current_state()
        last = self._history[self._hist_pos]
        if (last['text'] == state['text']
                and last['bold'] == state['bold']
                and last.get('code', []) == state['code']
                and last.get('images', []) == state['images']):
            return False
        # Truncate any redo history
        del self._history[self._hist_pos + 1:]
        self._history.append(state)
        if len(self._history) > 100:
            self._history.pop(0)
        else:
            self._hist_pos += 1
        return False

    def _current_state(self):
        buf = self.tv.get_buffer()
        return {
            'text': buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True),
            'bold': self._get_tag_ranges(self._bold_tag),
            'code': self._get_tag_ranges(self._code_tag),
            'images': self._get_images_state(),
        }

    def _restore_state(self, state):
        self._restoring = True
        self._remove_all_image_widgets()
        buf = self.tv.get_buffer()
        buf.set_text(state['text'])
        buf.remove_tag(self._bold_tag, buf.get_start_iter(), buf.get_end_iter())
        buf.remove_tag(self._code_tag, buf.get_start_iter(), buf.get_end_iter())
        for s, e in state.get('bold', []):
            buf.apply_tag(self._bold_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        for s, e in state.get('code', []):
            buf.apply_tag(self._code_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        self._restore_images(state.get('images', []))
        self._refresh_emoji_tags()
        self._restoring = False
        self._queue_save()

    def _undo(self):
        # Flush any pending snapshot first
        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()
        if self._hist_pos <= 0:
            return
        self._hist_pos -= 1
        self._restore_state(self._history[self._hist_pos])

    def _redo(self):
        if self._hist_pos >= len(self._history) - 1:
            return
        self._hist_pos += 1
        self._restore_state(self._history[self._hist_pos])

    # ------------------------------------------------------------------ key handling

    def _on_tv_button_press(self, tv, event):
        if event.type != Gdk.EventType.DOUBLE_BUTTON_PRESS or event.button != 1:
            return False
        buf = tv.get_buffer()
        x, y = tv.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, int(event.x), int(event.y))
        _, it = tv.get_iter_at_location(x, y)
        if not self._iter_has_tag_context(it, self._code_tag):
            return False
        clicked_line = it.get_line()
        first_line = clicked_line
        while first_line > 0 and self._line_is_fully_tagged(self._code_tag, first_line - 1):
            first_line -= 1
        last_line = clicked_line
        line_count = buf.get_line_count()
        while last_line < line_count - 1 and self._line_is_fully_tagged(self._code_tag, last_line + 1):
            last_line += 1
        start = buf.get_iter_at_line(first_line)
        _, end = self._line_bounds(last_line)
        buf.select_range(start, end)
        return True

    def _on_tv_key_press(self, tv, event):
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        if (state == Gdk.ModifierType.CONTROL_MASK
                and Gdk.keyval_to_lower(event.keyval) == Gdk.KEY_v):
            if self._paste_image_if_available():
                return True
            return False

        if event.keyval not in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return False
        buf = tv.get_buffer()
        if buf.get_has_selection():
            return False
        cursor = buf.get_iter_at_mark(buf.get_insert())
        if self._line_is_fully_tagged(self._code_tag, cursor.get_line()):
            line_start, line_end = self._line_bounds(cursor.get_line())
            line_text = buf.get_text(line_start, line_end, False)
            if line_text == CODE_ANCHOR:
                buf.place_cursor(line_end)
                buf.insert_at_cursor('\n')
                cursor = buf.get_iter_at_mark(buf.get_insert())
                self._tag_code_line(cursor.get_line(), keep_cursor=True)
                return True

            if cursor.equal(line_start):
                # At column 0 of a non-empty code line, Enter should create a
                # new empty code line above the text.  A non-empty line has no
                # CODE_ANCHOR, so create/tag one for the new blank line.
                offset = cursor.get_offset()
                buf.insert(cursor, CODE_ANCHOR + '\n')
                tag_start = buf.get_iter_at_offset(offset)
                tag_end = buf.get_iter_at_offset(offset + 1)
                buf.apply_tag(self._code_tag, tag_start, tag_end)
                buf.place_cursor(tag_end)
                return True

            buf.insert_at_cursor('\n')
            cursor = buf.get_iter_at_mark(buf.get_insert())
            self._tag_code_line(cursor.get_line(), keep_cursor=True)
            return True

        line_start = buf.get_iter_at_line(cursor.get_line())
        line_end = line_start.copy()
        line_end.forward_to_line_end()
        line_text = buf.get_text(line_start, line_end, False)
        if not line_text.startswith('• '):
            return False
        if line_text == '• ':
            # Empty bullet — remove marker and stop the list
            prefix_end = line_start.copy()
            prefix_end.forward_chars(2)
            buf.delete(line_start, prefix_end)
            return True
        buf.insert_at_cursor('\n• ')
        return True

    # ------------------------------------------------------------------ formatting

    def _selected_or_cursor_lines(self):
        buf = self.tv.get_buffer()
        if not buf.get_has_selection():
            line = buf.get_iter_at_mark(buf.get_insert()).get_line()
            return line, line

        start, end = buf.get_selection_bounds()
        first_line = start.get_line()
        last_line = end.get_line()
        if end.starts_line() and end.compare(start) > 0:
            last_line = max(first_line, last_line - 1)
        return first_line, last_line

    def _line_bounds(self, line, include_newline=False):
        buf = self.tv.get_buffer()
        start = buf.get_iter_at_line(line)
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        if include_newline and not end.is_end():
            end.forward_char()
        return start, end

    def _line_is_fully_tagged(self, tag, line):
        start, end = self._line_bounds(line)
        if start.compare(end) == 0:
            return False
        it = start.copy()
        while it.compare(end) < 0:
            if not it.has_tag(tag):
                return False
            it.forward_char()
        return True

    def _tag_code_line(self, line, keep_cursor=False):
        buf = self.tv.get_buffer()
        start, end = self._line_bounds(line)
        line_text = buf.get_text(start, end, False)

        if line_text.replace(CODE_ANCHOR, ''):
            self._apply_tag_to_non_newline_chars(buf, self._code_tag, start, end)
            return

        if line_text == CODE_ANCHOR:
            buf.apply_tag(self._code_tag, start, end)
            if keep_cursor:
                buf.place_cursor(end)
            return

        # GTK tags need at least one character. Use a zero-width anchor instead
        # of tagging the newline, because paragraph tags on line breaks can
        # paint adjacent empty paragraphs as code blocks.
        offset = start.get_offset()
        buf.insert(start, CODE_ANCHOR)
        tag_start = buf.get_iter_at_offset(offset)
        tag_end = buf.get_iter_at_offset(offset + 1)
        buf.apply_tag(self._code_tag, tag_start, tag_end)
        if keep_cursor:
            buf.place_cursor(tag_end)

    def _remove_code_from_line(self, line):
        buf = self.tv.get_buffer()
        start, end = self._line_bounds(line)
        if start.compare(end) >= 0:
            return
        start_off = start.get_offset()
        end_off = end.get_offset()
        buf.remove_tag(self._code_tag, start, end)

        for off in range(end_off - 1, start_off - 1, -1):
            it = buf.get_iter_at_offset(off)
            if it.get_char() == CODE_ANCHOR:
                next_it = buf.get_iter_at_offset(off + 1)
                buf.delete(it, next_it)

    def _remove_redundant_code_anchors(self, first_line, last_line):
        buf = self.tv.get_buffer()
        for line in range(last_line, first_line - 1, -1):
            start, end = self._line_bounds(line)
            line_text = buf.get_text(start, end, False)
            if CODE_ANCHOR not in line_text:
                continue
            if not line_text.replace(CODE_ANCHOR, ''):
                continue

            start_off = start.get_offset()
            end_off = end.get_offset()
            for off in range(end_off - 1, start_off - 1, -1):
                it = buf.get_iter_at_offset(off)
                if it.get_char() == CODE_ANCHOR:
                    next_it = buf.get_iter_at_offset(off + 1)
                    buf.delete(it, next_it)

    def _toggle_tag(self, tag):
        buf = self.tv.get_buffer()
        if not buf.get_has_selection():
            return
        start, end = buf.get_selection_bounds()
        it, all_tagged = start.copy(), True
        while it.compare(end) < 0:
            if not it.has_tag(tag):
                all_tagged = False
                break
            it.forward_char()
        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()
        if all_tagged:
            buf.remove_tag(tag, start, end)
        else:
            buf.apply_tag(tag, start, end)
        self._take_snapshot()
        self._queue_save()

    def _toggle_bold(self):
        self._toggle_tag(self._bold_tag)

    def _toggle_bullet(self):
        buf = self.tv.get_buffer()
        first_line, last_line = self._selected_or_cursor_lines()

        all_bulleted = True
        for ln in range(first_line, last_line + 1):
            it = buf.get_iter_at_line(ln)
            end = it.copy()
            end.forward_to_line_end()
            if not buf.get_text(it, end, False).startswith('• '):
                all_bulleted = False
                break

        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()

        for ln in range(last_line, first_line - 1, -1):
            line_start = buf.get_iter_at_line(ln)
            if all_bulleted:
                line_end_prefix = line_start.copy()
                line_end_prefix.forward_chars(2)
                buf.delete(line_start, line_end_prefix)
            else:
                line_end = line_start.copy()
                line_end.forward_to_line_end()
                if not buf.get_text(line_start, line_end, False).startswith('• '):
                    buf.insert(line_start, '• ')

        self._take_snapshot()
        self._queue_save()

    def _toggle_code_block(self):
        buf = self.tv.get_buffer()
        first_line, last_line = self._selected_or_cursor_lines()
        all_code = all(
            self._line_is_fully_tagged(self._code_tag, ln)
            for ln in range(first_line, last_line + 1))

        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()

        if all_code:
            for ln in range(last_line, first_line - 1, -1):
                self._remove_code_from_line(ln)
        else:
            keep_cursor = not buf.get_has_selection()
            for ln in range(last_line, first_line - 1, -1):
                self._tag_code_line(ln, keep_cursor=keep_cursor)

        self._take_snapshot()
        self._queue_save()

    def _on_tv_popup(self, _, menu):
        redo_item = Gtk.MenuItem(label='Redo  (Ctrl+Y)')
        redo_item.set_sensitive(self._hist_pos < len(self._history) - 1)
        redo_item.connect('activate', lambda _: self._redo())

        undo_item = Gtk.MenuItem(label='Undo  (Ctrl+Z)')
        undo_item.set_sensitive(self._hist_pos > 0)
        undo_item.connect('activate', lambda _: self._undo())

        search_item = Gtk.MenuItem(label='Search  (Ctrl+F)')
        search_item.connect('activate', lambda _: self._toggle_search())

        menu.prepend(Gtk.SeparatorMenuItem())
        menu.prepend(search_item)
        menu.prepend(Gtk.SeparatorMenuItem())
        menu.prepend(redo_item)
        menu.prepend(undo_item)

        menu.show_all()

    # ------------------------------------------------------------------ context menu

    def _show_ctx_menu(self, ev):
        menu = Gtk.Menu()

        # Hidden notes submenu
        hidden = [(nid, w) for nid, w in self.app.notes.items()
                  if not w.get_visible()]
        sub = Gtk.Menu()
        if hidden:
            for nid, w in hidden:
                label = w.title or '(untitled)'
                it = Gtk.MenuItem(label=f'↩  {label}')
                it.connect('activate', lambda _, n=nid: self.app.show_note(n))
                sub.append(it)
            sub.append(Gtk.SeparatorMenuItem())
            show_all = Gtk.MenuItem(label='Restore All Notes')
            show_all.connect('activate', lambda _: self.app.show_all())
            sub.append(show_all)
        else:
            no_item = Gtk.MenuItem(label='No hidden notes')
            no_item.set_sensitive(False)
            sub.append(no_item)
        restore_item = Gtk.MenuItem(label='Hidden Notes')
        restore_item.set_submenu(sub)
        menu.append(restore_item)

        menu.append(Gtk.SeparatorMenuItem())

        edit_title = Gtk.MenuItem(label='Edit Title')
        edit_title.connect('activate', lambda _: self._start_title_edit())
        menu.append(edit_title)

        menu.append(Gtk.SeparatorMenuItem())

        it = Gtk.MenuItem(label='Quit')
        it.connect('activate', lambda _: self.app.quit_app())
        menu.append(it)

        menu.show_all()
        menu.popup_at_pointer(ev)

    def _hide_note(self):
        self.hide()
        self.app._rebuild_indicator_menu()
        self._queue_save()

    def _toggle_on_top(self):
        self._on_top = not self._on_top
        self.set_keep_above(self._on_top)
        self._refresh_pin()
        self._queue_save()

    def _refresh_pin(self):
        ctx = self._pin_btn.get_style_context()
        if self._on_top:
            ctx.add_class('pinned')
        else:
            ctx.remove_class('pinned')

    def _apply_note_font(self):
        css = f'textview {{ font-size: {self._font_size}px; }}'.encode()
        self._font_prov.load_from_data(css)
        if hasattr(self, '_emoji_tag'):
            self._emoji_tag.set_property('scale', self._emoji_scale())

    def _emoji_scale(self):
        return (self._font_size + 3) / self._font_size

    def _is_emoji_char(self, char):
        codepoint = ord(char)
        return (
            char in ('\u200d', '\ufe0e', '\ufe0f')
            or 0x1F000 <= codepoint <= 0x1FAFF
            or 0x2600 <= codepoint <= 0x27BF
        )

    def _refresh_emoji_tags(self):
        buf = self.tv.get_buffer()
        start = buf.get_start_iter()
        end = buf.get_end_iter()
        buf.remove_tag(self._emoji_tag, start, end)

        it = start.copy()
        range_start = None
        while it.compare(end) < 0:
            char = it.get_char()
            next_it = it.copy()
            next_it.forward_char()
            if self._is_emoji_char(char):
                if range_start is None:
                    range_start = it.copy()
            elif range_start is not None:
                buf.apply_tag(self._emoji_tag, range_start, it)
                range_start = None
            it = next_it

        if range_start is not None:
            buf.apply_tag(self._emoji_tag, range_start, end)

    def _build_font_popover(self):
        self._font_popover = Gtk.Popover(relative_to=self._fontsize_btn)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        box.set_border_width(6)
        self._font_popover.add(box)

        font_down = Gtk.Button(label='A−')
        font_down.set_tooltip_text('Decrease font size')
        font_down.set_can_focus(False)
        font_down.connect('clicked', lambda _: self._change_font_size(-1))
        box.pack_start(font_down, False, False, 0)

        font_up = Gtk.Button(label='A+')
        font_up.set_tooltip_text('Increase font size')
        font_up.set_can_focus(False)
        font_up.connect('clicked', lambda _: self._change_font_size(+1))
        box.pack_start(font_up, False, False, 0)

        box.show_all()

    def _show_font_popover(self, *_):
        self._font_popover.set_relative_to(self._fontsize_btn)
        self._font_popover.popup()

    def _change_font_size(self, delta: int):
        self._font_size = max(8, min(32, self._font_size + delta))
        self._apply_note_font()
        self._fontsize_btn.set_label(f'{self._font_size}px')
        self._queue_save()

    def _on_configure(self, *_):
        self._queue_save()

    def _queue_save(self):
        if self._sid:
            GLib.source_remove(self._sid)
        self._sid = GLib.timeout_add(600, self._do_save)

    def _do_save(self):
        self._sid = None
        self.app.save_all()
        return False

    # ------------------------------------------------------------------ data

    def to_dict(self) -> dict:
        x, y = self.get_position()
        w, h = self.get_size()
        buf  = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        return dict(id=self.note_id, x=x, y=y, w=w, h=h,
                    text=text, title=self.title, on_top=self._on_top,
                    hidden=not self.get_visible(),
                    bold_ranges=self._get_tag_ranges(self._bold_tag),
                    code_ranges=self._get_tag_ranges(self._code_tag),
                    images=self._get_images_state(),
                    font_size=self._font_size)

    def _get_tag_ranges(self, tag):
        buf = self.tv.get_buffer()
        ranges, it = [], buf.get_start_iter()
        active, start_off = it.has_tag(tag), 0
        while True:
            it.forward_char()
            now = it.has_tag(tag)
            if it.is_end():
                if active:
                    ranges.append([start_off, it.get_offset()])
                break
            if now and not active:
                start_off = it.get_offset()
            elif not now and active:
                ranges.append([start_off, it.get_offset()])
            active = now
        return ranges


class PostItApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.notes: dict[str, NoteWindow] = {}
        self._status_icon  = None
        self._tray_menu    = None
        self._notes_raised = False

    def do_startup(self):
        Gtk.Application.do_startup(self)
        os.makedirs(CONF_DIR, exist_ok=True)
        os.makedirs(IMAGES_DIR, exist_ok=True)

        if os.path.exists(ICON_PATH):
            Gtk.Window.set_default_icon_from_file(ICON_PATH)

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
        if self._notes_raised:
            lowerable = [w for w in self.notes.values()
                         if w.get_visible() and not w._on_top]
            if lowerable:
                self._lower_all()
                self._notes_raised = False
        else:
            self.raise_all()
            self._notes_raised = True

    def _on_note_focus_in(self):
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

        hidden = [(nid, w) for nid, w in self.notes.items() if not w.get_visible()]

        restore_item = Gtk.MenuItem(label='Hidden Notes')
        sub = Gtk.Menu()
        if hidden:
            for nid, w in hidden:
                label = w.title or '(untitled)'
                it = Gtk.MenuItem(label=f'↩  {label}')
                it.connect('activate', lambda _, n=nid: self.show_note(n))
                sub.append(it)
            sub.append(Gtk.SeparatorMenuItem())
            show_all = Gtk.MenuItem(label='Restore All Notes')
            show_all.connect('activate', lambda _: self.show_all())
            sub.append(show_all)
        else:
            no_item = Gtk.MenuItem(label='No hidden notes')
            no_item.set_sensitive(False)
            sub.append(no_item)
        restore_item.set_submenu(sub)
        menu.append(restore_item)
        menu.append(Gtk.SeparatorMenuItem())

        new_note = Gtk.MenuItem(label='New Note')
        new_note.connect('activate', lambda _: self.new_note())
        menu.append(new_note)

        menu.append(Gtk.SeparatorMenuItem())

        quit_item = Gtk.MenuItem(label='Quit')
        quit_item.connect('activate', lambda _: self.quit_app())
        menu.append(quit_item)

        menu.show_all()
        self._tray_menu = menu

    # ------------------------------------------------------------------ notes

    def _load(self):
        if not os.path.exists(NOTES_FILE):
            self.new_note()
            return
        try:
            with open(NOTES_FILE) as f:
                saved = json.load(f)
        except Exception:
            self.new_note()
            return
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
            monitor = Gdk.Display.get_default().get_primary_monitor()
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

    def _referenced_image_files(self, data=None, include_history=True):
        referenced = set()
        if data is None:
            data = [w.to_dict() for w in self.notes.values()]

        # Durable/current note state. Hidden notes are included because they are
        # still live notes and must keep their images.
        for note in data:
            for meta in note.get('images', []):
                name = meta.get('file', '')
                if not name or os.path.isabs(name):
                    continue
                referenced.add(os.path.basename(name))

        # Runtime undo/redo history. This prevents Ctrl+Y from losing an image
        # after the image was removed from the visible note and autosave ran.
        if include_history:
            for w in self.notes.values():
                referenced.update(w.history_image_files())

        return referenced

    def _cleanup_orphaned_images(self, data=None, include_history=True):
        # Delete copied image files that are no longer referenced by any live
        # note or, during runtime, undo/redo history.
        if not os.path.isdir(IMAGES_DIR):
            return
        referenced = self._referenced_image_files(data, include_history=include_history)
        for name in os.listdir(IMAGES_DIR):
            path = os.path.join(IMAGES_DIR, name)
            if not os.path.isfile(path):
                continue
            if name in referenced:
                continue
            try:
                os.remove(path)
            except OSError as e:
                print(f'ynote: failed to remove unused image {path}: {e}',
                      file=sys.stderr)

    def save_all(self, include_history=True):
        data = [w.to_dict() for w in self.notes.values()]
        tmp  = NOTES_FILE + '.tmp'
        try:
            with open(tmp, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, NOTES_FILE)
            self._cleanup_orphaned_images(data, include_history=include_history)
        except OSError as e:
            print(f'ynote: save failed: {e}', file=sys.stderr)

    def quit_app(self):
        # Undo/redo history is not durable, so on quit only saved notes should
        # keep image files alive.
        self.save_all(include_history=False)
        self.release()
        Gtk.Application.quit(self)


if __name__ == '__main__':
    if (os.environ.get('WAYLAND_DISPLAY')
            and os.environ.get('GDK_BACKEND') != 'x11'):
        os.environ['GDK_BACKEND'] = 'x11'
        os.execv(sys.executable, [sys.executable] + sys.argv)

    app = PostItApp()
    sys.exit(app.run(sys.argv))
