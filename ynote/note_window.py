import os
import shutil
import sys
import urllib.parse
import uuid

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, Pango, GdkPixbuf

from .config import CODE_ANCHOR, IMAGE_ANCHOR, IMAGES_DIR
from .images import image_files_from_metadata, image_path, normalize_image_meta
from .models import normalize_note_data

class NoteWindow(Gtk.ApplicationWindow):
    def __init__(self, app, data: dict):
        super().__init__(application=app)
        self.app      = app
        data = normalize_note_data(data)
        self.note_id  = data['id']
        self.title    = data['title']
        self._on_top  = data['on_top']
        self.sort_order = data['sort_order']
        self._font_size = data['font_size']
        self._sid       = None
        self._editing   = False
        self._restoring   = False
        self._snap_sid    = None
        self._history   = [{'text': data.get('text', ''),
                             'bold': data.get('bold_ranges', []),
                             'code': data.get('code_ranges', []),
                             'backtick': data.get('backtick_ranges', []),
                             'images': data.get('images', [])}]
        self._hist_pos  = 0
        self._bold_active = False
        self._pending_format_inserts = []
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

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
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

        hidden_btn = Gtk.Button(label='▤')
        hidden_btn.set_tooltip_text('Hidden Notes')
        hidden_btn.connect('clicked',
                           lambda _: self.app.show_hidden_notes_manager(self))
        note_group.pack_start(hidden_btn, False, False, 0)
        note_group.pack_start(del_btn, False, False, 0)

        # Visual/semantic split between note actions and text-editing actions.
        split = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        split.get_style_context().add_class('tool-separator')
        btn_row.pack_start(split, False, False, 4)

        # Right group: text/content editing actions.
        text_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        text_group.get_style_context().add_class('tool-group')
        btn_row.pack_start(text_group, False, False, 0)

        self._bold_btn = Gtk.Button(label='B')
        self._bold_btn.set_tooltip_text('Bold  (Ctrl+B)')
        self._bold_btn.set_can_focus(False)
        self._bold_btn.connect('clicked', lambda _: self._toggle_bold())
        text_group.pack_start(self._bold_btn, False, False, 0)

        bullet_btn = Gtk.Button(label='•')
        bullet_btn.set_tooltip_text('Bullet list  (Ctrl+8)')
        bullet_btn.set_can_focus(False)
        bullet_btn.connect('clicked', lambda _: self._toggle_bullet())
        text_group.pack_start(bullet_btn, False, False, 0)

        code_btn = Gtk.Button(label='</>')
        code_btn.set_tooltip_text('Code block  (Ctrl+Shift+C)')
        code_btn.set_can_focus(False)
        code_btn.connect('clicked', lambda _: self._toggle_code_block())
        text_group.pack_start(code_btn, False, False, 0)

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
        for btn in (self._pin_btn, new_btn, min_btn, close_btn, hidden_btn,
                    del_btn, self._bold_btn, bullet_btn, code_btn,
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
        self._backtick_tag = buf.create_tag(
            'backtick',
            style=Pango.Style.ITALIC,
            underline=Pango.Underline.SINGLE,
            foreground='#C53030')
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
        for s, e in data.get('backtick_ranges', []):
            buf.apply_tag(self._backtick_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        self._restore_images(data.get('images', []))
        self.tv.connect('populate-popup', self._on_tv_popup)
        self.tv.connect('key-press-event', self._on_tv_key_press)
        self.tv.connect('button-press-event', self._on_tv_button_press)
        self.tv.connect('copy-clipboard', self._on_copy_clipboard)
        self.tv.connect('cut-clipboard', self._on_cut_clipboard)
        self.tv.connect('paste-clipboard', self._on_paste_clipboard)

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
        accel.connect(Gdk.KEY_8, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_bullet() or True)
        accel.connect(Gdk.KEY_KP_8, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_bullet() or True)
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
        self.connect('focus-in-event',     lambda *_: self.app._on_note_focus_in(self))
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
        return normalize_image_meta(meta, include_offset=include_offset)

    def _image_path(self, meta):
        return image_path(meta, IMAGES_DIR)

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
            files.update(image_files_from_metadata(state.get('images', [])))
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

    # ------------------------------------------------------------------ rich clipboard

    def _get_tag_ranges_between(self, tag, start_offset, end_offset):
        ranges = []
        for tag_start, tag_end in self._get_tag_ranges(tag):
            clipped_start = max(tag_start, start_offset)
            clipped_end = min(tag_end, end_offset)
            if clipped_start < clipped_end:
                ranges.append([
                    clipped_start - start_offset,
                    clipped_end - start_offset,
                ])
        return ranges

    def _get_images_between(self, start, end):
        images = []
        start_offset = start.get_offset()
        it = start.copy()
        while it.compare(end) < 0:
            anchor = it.get_child_anchor()
            if anchor is not None and hasattr(anchor, 'ynote_image'):
                meta = self._normalize_image_meta(anchor.ynote_image)
                meta['offset'] = it.get_offset() - start_offset
                images.append(meta)
            it.forward_char()
        return images

    def _selected_rich_state(self):
        buf = self.tv.get_buffer()
        if not buf.get_has_selection():
            return None

        start, end = buf.get_selection_bounds()
        start_offset = start.get_offset()
        end_offset = end.get_offset()
        return {
            'text': buf.get_slice(start, end, True),
            'bold': self._get_tag_ranges_between(
                self._bold_tag, start_offset, end_offset),
            'code': self._get_tag_ranges_between(
                self._code_tag, start_offset, end_offset),
            'backtick': self._get_tag_ranges_between(
                self._backtick_tag, start_offset, end_offset),
            'images': self._get_images_between(start, end),
        }

    def _copy_rich_selection_to_clipboard(self):
        state = self._selected_rich_state()
        if state is None:
            return False

        self.app.set_rich_clipboard(state)
        return True

    def _paste_rich_clipboard_if_available(self):
        state = self.app.rich_clipboard_state()
        if not state:
            return False

        self._insert_rich_state_at_cursor(state)
        return True

    def _selection_spans_code_lines(self):
        buf = self.tv.get_buffer()
        if not buf.get_has_selection():
            return False

        first_line, last_line = self._selected_or_cursor_lines()
        return all(
            self._line_is_fully_tagged(self._code_tag, line)
            for line in range(first_line, last_line + 1))

    def _paste_plain_text_into_code_selection(self):
        if not self._selection_spans_code_lines():
            return False

        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        text = clipboard.wait_for_text()
        if text is None:
            return False

        self._replace_selection_with_code_text(text)
        return True

    def _replace_selection_with_code_text(self, text):
        buf = self.tv.get_buffer()
        start, end = buf.get_selection_bounds()
        insert_offset = start.get_offset()

        self._restoring = True
        try:
            buf.delete(start, end)
            insert_iter = buf.get_iter_at_offset(insert_offset)
            buf.insert(insert_iter, text)

            start_line = buf.get_iter_at_offset(insert_offset).get_line()
            end_iter = buf.get_iter_at_offset(insert_offset + len(text))
            cursor_mark = buf.create_mark(None, end_iter, False)
            end_line = end_iter.get_line()
            for line in range(end_line, start_line - 1, -1):
                self._tag_code_line(line)
            self._remove_redundant_code_anchors(start_line, end_line)

            buf.place_cursor(buf.get_iter_at_mark(cursor_mark))
            buf.delete_mark(cursor_mark)
            self._refresh_emoji_tags()
        finally:
            self._restoring = False
        self._take_snapshot()
        self._queue_save()
        self.tv.grab_focus()

    def _insert_rich_state_at_cursor(self, state):
        buf = self.tv.get_buffer()
        text = state.get('text', '')

        self._restoring = True
        if buf.get_has_selection():
            start, end = buf.get_selection_bounds()
            insert_offset = start.get_offset()
            buf.delete(start, end)
        else:
            insert_offset = buf.get_iter_at_mark(buf.get_insert()).get_offset()

        insert_iter = buf.get_iter_at_offset(insert_offset)
        buf.insert(insert_iter, text)

        for rel_start, rel_end in state.get('bold', []):
            buf.apply_tag(
                self._bold_tag,
                buf.get_iter_at_offset(insert_offset + rel_start),
                buf.get_iter_at_offset(insert_offset + rel_end))

        for rel_start, rel_end in state.get('code', []):
            buf.apply_tag(
                self._code_tag,
                buf.get_iter_at_offset(insert_offset + rel_start),
                buf.get_iter_at_offset(insert_offset + rel_end))

        for rel_start, rel_end in state.get('backtick', []):
            buf.apply_tag(
                self._backtick_tag,
                buf.get_iter_at_offset(insert_offset + rel_start),
                buf.get_iter_at_offset(insert_offset + rel_end))

        images = []
        for meta in state.get('images', []):
            image_meta = self._normalize_image_meta(meta, include_offset=True)
            image_meta['offset'] = insert_offset + image_meta.get('offset', 0)
            images.append(image_meta)
        self._restore_images(images)

        end_offset = insert_offset + len(text)
        buf.place_cursor(buf.get_iter_at_offset(end_offset))
        self._refresh_emoji_tags()
        self._restoring = False
        self._take_snapshot()
        self._queue_save()
        self.tv.grab_focus()

    def _on_copy_clipboard(self, tv):
        if self._copy_rich_selection_to_clipboard():
            tv.stop_emission_by_name('copy-clipboard')

    def _on_cut_clipboard(self, tv):
        if not self._copy_rich_selection_to_clipboard():
            return

        buf = self.tv.get_buffer()
        start, end = buf.get_selection_bounds()
        buf.delete(start, end)
        self._take_snapshot()
        self._queue_save()
        tv.stop_emission_by_name('cut-clipboard')

    def _on_paste_clipboard(self, tv):
        if (self._paste_rich_clipboard_if_available()
                or self._paste_image_if_available()
                or self._paste_plain_text_into_code_selection()):
            tv.stop_emission_by_name('paste-clipboard')

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
        self._pending_format_inserts.append(
            (self._bold_active,
             self._iter_has_tag_context(location, self._code_tag)))

    def _after_buf_insert_text(self, buf, location, text, length):
        if self._restoring:
            return
        apply_bold, apply_code = (
            self._pending_format_inserts.pop(0)
            if self._pending_format_inserts else (False, False))
        if not text:
            return

        end = location.copy()
        start = end.copy()
        start.backward_chars(len(text))
        if apply_bold:
            self._apply_tag_to_non_newline_chars(buf, self._bold_tag, start, end)
        if apply_code and text != '\n':
            for line in range(start.get_line(), end.get_line() + 1):
                self._tag_code_line(line)
            self._remove_redundant_code_anchors(start.get_line(), end.get_line())
        if '`' in text:
            self._format_backtick_wrapped_text()
        self._refresh_emoji_tags()

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
                and last.get('backtick', []) == state['backtick']
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
            'backtick': self._get_tag_ranges(self._backtick_tag),
            'images': self._get_images_state(),
        }

    def _restore_state(self, state):
        self._restoring = True
        self._remove_all_image_widgets()
        buf = self.tv.get_buffer()
        buf.set_text(state['text'])
        buf.remove_tag(self._bold_tag, buf.get_start_iter(), buf.get_end_iter())
        buf.remove_tag(self._code_tag, buf.get_start_iter(), buf.get_end_iter())
        buf.remove_tag(
            self._backtick_tag, buf.get_start_iter(), buf.get_end_iter())
        for s, e in state.get('bold', []):
            buf.apply_tag(self._bold_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        for s, e in state.get('code', []):
            buf.apply_tag(self._code_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        for s, e in state.get('backtick', []):
            buf.apply_tag(self._backtick_tag,
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
            if self._paste_rich_clipboard_if_available():
                return True
            if self._paste_image_if_available():
                return True
            return False

        buf = tv.get_buffer()
        if buf.get_has_selection():
            return False
        cursor = buf.get_iter_at_mark(buf.get_insert())
        cursor_line = cursor.get_line()

        if (state == 0 and event.keyval == Gdk.KEY_Tab
                and self._line_has_bullet(cursor_line)):
            self._indent_bullet_line(cursor_line)
            return True

        if (state == Gdk.ModifierType.SHIFT_MASK
                and event.keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab)
                and self._line_has_bullet(cursor_line)):
            self._outdent_bullet_line(cursor_line)
            return True

        if (state == 0 and event.keyval == Gdk.KEY_BackSpace
                and self._line_is_empty_bullet(cursor_line)):
            self._remove_empty_bullet_line(cursor_line)
            return True

        if event.keyval not in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return False

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
        parts = self._bullet_parts(line_text)
        if parts is None:
            return False
        indent, body = parts
        if body.strip() == '':
            # Empty bullet: remove the current marker and stop the list.
            self._remove_empty_bullet_line(cursor_line)
            return True
        marker_len = len(indent) + 2
        if cursor.get_line_offset() <= marker_len:
            insert_offset = line_start.get_offset()
            buf.insert(line_start, f'{indent}• \n')
            buf.place_cursor(buf.get_iter_at_offset(insert_offset + marker_len))
            return True
        buf.insert_at_cursor(f'\n{indent}• ')
        return True

    # ------------------------------------------------------------------ formatting

    def _line_indent_len(self, text):
        index = 0
        while index < len(text) and text[index] in (' ', '\t'):
            index += 1
        return index

    def _bullet_parts(self, text):
        indent_len = self._line_indent_len(text)
        if not text[indent_len:].startswith('• '):
            return None
        return text[:indent_len], text[indent_len + 2:]

    def _line_bullet_parts(self, line):
        buf = self.tv.get_buffer()
        line_start, line_end = self._line_bounds(line)
        text = buf.get_text(line_start, line_end, False)
        return self._bullet_parts(text)

    def _line_has_bullet(self, line):
        return self._line_bullet_parts(line) is not None

    def _line_is_empty_bullet(self, line):
        parts = self._line_bullet_parts(line)
        return parts is not None and parts[1].strip() == ''

    def _line_bullet_marker_bounds(self, line):
        buf = self.tv.get_buffer()
        line_start, line_end = self._line_bounds(line)
        text = buf.get_text(line_start, line_end, False)
        parts = self._bullet_parts(text)
        if parts is None:
            return None
        marker_start = line_start.copy()
        marker_start.forward_chars(len(parts[0]))
        marker_end = marker_start.copy()
        marker_end.forward_chars(2)
        return marker_start, marker_end

    def _indent_bullet_line(self, line):
        buf = self.tv.get_buffer()
        line_start = buf.get_iter_at_line(line)
        buf.insert(line_start, '    ')

    def _outdent_bullet_line(self, line):
        buf = self.tv.get_buffer()
        line_start, line_end = self._line_bounds(line)
        text = buf.get_text(line_start, line_end, False)
        parts = self._bullet_parts(text)
        if parts is None or not parts[0]:
            return

        remove_count = 1 if parts[0].startswith('\t') else min(4, len(parts[0]))
        remove_end = line_start.copy()
        remove_end.forward_chars(remove_count)
        buf.delete(line_start, remove_end)

    def _remove_empty_bullet_line(self, line):
        buf = self.tv.get_buffer()
        line_start, line_end = self._line_bounds(line)
        buf.delete(line_start, line_end)

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
            return False
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
        return True

    def _toggle_bold(self):
        if not self._toggle_tag(self._bold_tag):
            self._bold_active = not self._bold_active
            self._refresh_format_buttons()

    def _toggle_backtick_format(self):
        self._toggle_tag(self._backtick_tag)

    def _format_backtick_wrapped_text(self):
        buf = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        pairs = []
        open_offset = None
        for offset, char in enumerate(text):
            if char != '`':
                continue
            if open_offset is None:
                open_offset = offset
            elif offset > open_offset + 1:
                pairs.append((open_offset, offset))
                open_offset = None
            else:
                open_offset = None

        if not pairs:
            return

        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()

        for open_offset, close_offset in reversed(pairs):
            close_start = buf.get_iter_at_offset(close_offset)
            close_end = buf.get_iter_at_offset(close_offset + 1)
            buf.delete(close_start, close_end)

            open_start = buf.get_iter_at_offset(open_offset)
            open_end = buf.get_iter_at_offset(open_offset + 1)
            buf.delete(open_start, open_end)

            styled_start = buf.get_iter_at_offset(open_offset)
            styled_end = buf.get_iter_at_offset(close_offset - 1)
            buf.apply_tag(self._backtick_tag, styled_start, styled_end)

        self._take_snapshot()
        self._queue_save()

    def _toggle_bullet(self):
        buf = self.tv.get_buffer()
        first_line, last_line = self._selected_or_cursor_lines()

        all_bulleted = True
        for ln in range(first_line, last_line + 1):
            if not self._line_has_bullet(ln):
                all_bulleted = False
                break

        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()

        for ln in range(last_line, first_line - 1, -1):
            line_start = buf.get_iter_at_line(ln)
            if all_bulleted:
                marker_bounds = self._line_bullet_marker_bounds(ln)
                if marker_bounds is not None:
                    marker_start, marker_end = marker_bounds
                    buf.delete(marker_start, marker_end)
            else:
                line_end = line_start.copy()
                line_end.forward_to_line_end()
                text = buf.get_text(line_start, line_end, False)
                if self._bullet_parts(text) is None:
                    insert_at = line_start.copy()
                    insert_at.forward_chars(self._line_indent_len(text))
                    buf.insert(insert_at, '• ')

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

    def _refresh_format_buttons(self):
        ctx = self._bold_btn.get_style_context()
        if self._bold_active:
            ctx.add_class('pinned')
        else:
            ctx.remove_class('pinned')

    def _on_tv_popup(self, _, menu):
        redo_item = Gtk.MenuItem(label='Redo  (Ctrl+Y)')
        redo_item.set_sensitive(self._hist_pos < len(self._history) - 1)
        redo_item.connect('activate', lambda _: self._redo())

        undo_item = Gtk.MenuItem(label='Undo  (Ctrl+Z)')
        undo_item.set_sensitive(self._hist_pos > 0)
        undo_item.connect('activate', lambda _: self._undo())

        search_item = Gtk.MenuItem(label='Search  (Ctrl+F)')
        search_item.connect('activate', lambda _: self._toggle_search())

        image_item = Gtk.MenuItem(label='Insert Image')
        image_item.connect('activate', lambda _: self._choose_and_insert_image())

        menu.prepend(Gtk.SeparatorMenuItem())
        menu.prepend(image_item)
        if self.tv.get_buffer().get_has_selection():
            backtick_item = Gtk.MenuItem(label='Backtick Format')
            backtick_item.connect('activate',
                                  lambda _: self._toggle_backtick_format())
            menu.prepend(backtick_item)
        menu.prepend(Gtk.SeparatorMenuItem())
        menu.prepend(search_item)
        menu.prepend(Gtk.SeparatorMenuItem())
        menu.prepend(redo_item)
        menu.prepend(undo_item)

        menu.show_all()

    # ------------------------------------------------------------------ context menu

    def _show_ctx_menu(self, ev):
        menu = Gtk.Menu()

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
                    sort_order=self.sort_order,
                    bold_ranges=self._get_tag_ranges(self._bold_tag),
                    code_ranges=self._get_tag_ranges(self._code_tag),
                    backtick_ranges=self._get_tag_ranges(self._backtick_tag),
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
