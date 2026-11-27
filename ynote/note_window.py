"""A note's window: its title bar, bottom bar, search bar, right-click
popover, snapping, collapsing, color, and saving. The text in it is edited by
Editor, which NoteWindow is too; see editor.py."""
import math
from collections import namedtuple

import cairo
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf, Pango

from . import __version__
from .config import (
    CHECKBOX_MARKER, CONF_DIR, ICON_PATH, NEW_NOTE_LABEL, PROJECT_DIR,
    QUOTE_MARKER, UNTITLED_LABEL, display_path,
)
from .editor import Editor
from .help import show_help
from .models import MAX_OPACITY, MIN_OPACITY, normalize_note_data
from .search import find_matches
from .snap import snap_rect
from .styles import (
    PALETTE, code_background, inline_code_background, note_css,
)



# The size of the icons of the title bar and bottom bar buttons, in pixels:
# most of a button, so an icon is not lost in it.
BAR_ICON_SIZE = 16


class StrokeIcon(Gtk.DrawingArea):
    """A plus, a cross, an arrowhead pointing down or right, or an eye
    struck through, for what is hidden, drawn in lines as thick as bold
    text, in the color of the button's text. The theme's symbolic ones are
    drawn in a line one pixel wide, too thin to see beside the bold labels of
    the bars."""
    STROKE = 2

    def __init__(self, kind, size=BAR_ICON_SIZE):
        super().__init__()
        self._kind = kind
        self.set_size_request(size, size)
        self.set_valign(Gtk.Align.CENTER)
        self.connect('draw', self._draw)

    def _draw(self, widget, cr):
        size = min(widget.get_allocated_width(),
                   widget.get_allocated_height())
        color = widget.get_style_context().get_color(widget.get_state_flags())
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.set_line_width(self.STROKE)
        if self._kind == 'plus':
            # On whole pixels, so the lines are sharp.
            middle, reach = size / 2, round(size * 0.4)
            cr.move_to(middle - reach, middle)
            cr.line_to(middle + reach, middle)
            cr.move_to(middle, middle - reach)
            cr.line_to(middle, middle + reach)
        elif self._kind == 'hidden':
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            # An eye: two arcs meeting at its corners, around a pupil.
            middle = size / 2
            left, right = size * 0.08, size * 0.92
            lid = size * 0.36
            cr.move_to(left, middle)
            cr.curve_to(size * 0.3, middle - lid, size * 0.7, middle - lid,
                        right, middle)
            cr.curve_to(size * 0.7, middle + lid, size * 0.3, middle + lid,
                        left, middle)
            cr.close_path()
            cr.stroke()
            cr.arc(middle, middle, size * 0.13, 0, 2 * math.pi)
            cr.fill()
            # Struck through, corner to corner.
            cr.move_to(size * 0.15, size * 0.12)
            cr.line_to(size * 0.85, size * 0.88)
        elif self._kind == 'cross':
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            low, high = size * 0.2, size * 0.8
            cr.move_to(low, low)
            cr.line_to(high, high)
            cr.move_to(high, low)
            cr.line_to(low, high)
        else:
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            # A chevron half as deep as it is wide, centered.
            wide, deep = size * 0.6, size * 0.3
            if self._kind == 'down':
                left, top = (size - wide) / 2, (size - deep) / 2
                cr.move_to(left, top)
                cr.line_to(left + wide / 2, top + deep)
                cr.line_to(left + wide, top)
            else:
                left, top = (size - deep) / 2, (size - wide) / 2
                cr.move_to(left, top)
                cr.line_to(left + deep, top + wide / 2)
                cr.line_to(left, top + wide)
        cr.stroke()
        return False


def set_button_content(button, *children):
    """Show children side by side in a button, in place of what it had."""
    old = button.get_child()
    if old is not None:
        button.remove(old)
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
    box.set_halign(Gtk.Align.CENTER)
    for child in children:
        box.pack_start(child, False, False, 0)
    box.show_all()
    button.add(box)



# An item of the Format or Insert menu: its icon as Pango markup, its name,
# the Markdown typed for it, its shortcut, what it does, whether it is on, or
# None when it is not a format, and whether it can be chosen. A boxed icon is
# drawn inside a box, as the code block one is.
BarItem = namedtuple('BarItem', 'icon label hint keys action active sensitive '
                                'boxed', defaults=(False,))

# Room a popover's arrow and border take around its content.
POPOVER_PAD = 24


class NoteWindow(Gtk.ApplicationWindow, Editor):
    def __init__(self, app, data: dict):
        super().__init__(application=app)
        self.app      = app
        data = normalize_note_data(data)
        self.note_id  = data['id']
        self.title    = data['title']
        self._on_top  = data['on_top']
        self.sort_order = data['sort_order']
        self._font_size = data['font_size']
        self._color     = data['color']
        self._opacity   = data['opacity']
        self._collapsed = data['collapsed']
        self._expanded_height = data['h']
        self._sid       = None
        self._editing   = False
        self._title_drag = None
        self._snap_held = []
        self._snap_pending_move = None
        self._normal_geometry = None

        self._build(data)
        self._apply_color()
        self.set_title(self.title or UNTITLED_LABEL)
        # A note that starts collapsed opens one pixel tall, so it never
        # flashes at full height before the body is hidden.
        self.set_default_size(data.get('w', 200),
                              1 if self._collapsed else data.get('h', 300))
        self.move(data.get('x', 200), data.get('y', 200))
        self.show_all()
        if self._collapsed:
            self._set_body_visible(False)
            self._lock_size(True, data.get('w', 200))
            self.resize(data.get('w', 200), 1)
            GLib.timeout_add(150, self._shrink_to_header)
        self.set_keep_above(self._on_top)
        self._refresh_pin()
        if data.get('hidden', False):
            self.hide()

    # ------------------------------------------------------------------ build

    def _build(self, data):
        self.set_decorated(False)
        self._setup_rgba_visual()
        self.set_resizable(True)
        self.set_skip_pager_hint(True)
        self.set_wmclass('ynote', 'Ynote')
        self.get_style_context().add_class('note')

        # Overlay lets thin resize strips sit on top of the header and bottom
        # bar without taking any layout space.
        overlay = Gtk.Overlay()
        self.add(overlay)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        overlay.add(root)

        # ---- Bars ----
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        hdr.get_style_context().add_class('hdr')
        self._hdr = hdr
        root.pack_start(hdr, False, False, 0)

        self._collapse_btn = Gtk.Button()
        self._collapse_btn.set_can_focus(False)
        self._collapse_btn.get_style_context().add_class('collapse-btn')
        self._collapse_btn.connect('clicked', lambda _: self._toggle_collapse())
        hdr.pack_start(self._collapse_btn, False, False, 0)
        self._refresh_collapse_state()

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

        self._title_label = Gtk.Label()
        self._title_label.get_style_context().add_class('title')
        self._show_title()
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
        self._btmbar = btn_row
        self._bottom_bar_box.add(btn_row)

        # Left group: note/window-level actions.
        note_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        note_group.get_style_context().add_class('tool-group')
        btn_row.pack_start(note_group, False, False, 0)

        new_btn = Gtk.Button()
        set_button_content(new_btn, StrokeIcon('plus'))
        new_btn.set_tooltip_text(NEW_NOTE_LABEL)
        new_btn.connect('clicked', lambda _: self.app.new_note(near=self))
        note_group.pack_start(new_btn, False, False, 0)

        close_btn = Gtk.Button()
        set_button_content(close_btn, StrokeIcon('cross'))
        close_btn.set_tooltip_text('Hide Note')
        close_btn.connect('clicked', lambda _: self._hide_note())
        note_group.pack_start(close_btn, False, False, 0)

        # An eye struck through, for the notes that are hidden. How many
        # there are is in its tooltip, which shows at once.
        hidden_btn = Gtk.Button()
        self._hidden_btn = hidden_btn
        set_button_content(hidden_btn, StrokeIcon('hidden', BAR_ICON_SIZE + 2))
        self.set_hidden_count(0)
        hidden_btn.connect('clicked',
                           lambda _: self.app.show_hidden_notes_manager(self))
        note_group.pack_start(hidden_btn, False, False, 0)

        # Visual/semantic split between note actions and text-editing actions.
        split = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        split.get_style_context().add_class('tool-separator')
        btn_row.pack_start(split, False, False, 4)

        # Right group: text/content editing actions.
        text_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        text_group.get_style_context().add_class('tool-group')
        btn_row.pack_start(text_group, False, False, 0)

        # Formats of the text, and elements to insert, each in a menu that
        # lists what it holds with the Markdown typed for it and its shortcut,
        # so the bar stays short as elements are added.
        self._format_btn = Gtk.Button()
        set_button_content(self._format_btn, Gtk.Label(label='Format'),
                           StrokeIcon('down', 12))
        self._format_btn.set_tooltip_text('Format text')
        self._format_btn.set_can_focus(False)
        self._format_btn.connect(
            'clicked', lambda b: self._popup_bar_menu(b, self._format_items()))
        text_group.pack_start(self._format_btn, False, False, 0)

        insert_btn = Gtk.Button()
        set_button_content(insert_btn, Gtk.Label(label='Insert'),
                           StrokeIcon('down', 12))
        insert_btn.set_tooltip_text('Insert an element')
        insert_btn.set_can_focus(False)
        insert_btn.connect(
            'clicked', lambda b: self._popup_bar_menu(b, self._insert_items()))
        text_group.pack_start(insert_btn, False, False, 0)

        row_spacer = Gtk.Box()
        row_spacer.set_hexpand(True)
        btn_row.pack_start(row_spacer, True, True, 0)

        # Right-clicking any bottom-bar button opens the same popover as the
        # title bar. Left-click behavior is unchanged because _on_bottom_bar_click()
        # returns False for non-right-clicks.
        for btn in (self._pin_btn, new_btn, close_btn, hidden_btn,
                    self._format_btn, insert_btn):
            btn.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            btn.connect('button-press-event', self._on_bottom_bar_click)

        # ---- Text area ----
        self._sw = Gtk.ScrolledWindow()
        self._sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        root.pack_start(self._sw, True, True, 0)

        self._build_editor(data)
        self._sw.add(self.tv)
        # The menus and shortcuts act on the note's text while it has the
        # cursor, and on a table's cell while that has it.
        self.tv.connect('focus-in-event',
                        lambda *_: self._set_active_editor(self) or False)
        # A table's columns fit the note's width.
        self._tv_width = 0
        self.tv.connect('size-allocate', self._on_tv_size)

        # ---- Search bar (hidden until Ctrl+F) ----
        # Wrapped in a Revealer so the widget is always realized — avoids the
        # "WIDGET_REALIZED_FOR_EVENT" crash that occurs when showing a widget
        # that was excluded from show_all() and then immediately receiving events.
        search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search_box.get_style_context().add_class('search-bar')
        sbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        search_box.pack_start(sbar, False, False, 0)
        self._search_bar = sbar

        self._search_revealer = Gtk.Revealer()
        self._search_revealer.set_transition_type(Gtk.RevealerTransitionType.NONE)
        self._search_revealer.set_reveal_child(False)
        self._search_revealer.add(search_box)
        root.pack_start(self._search_revealer, False, False, 0)
        root.pack_start(self._bottom_bar_box, False, False, 0)

        self._search_entry = Gtk.SearchEntry()
        self._search_entry.set_hexpand(True)
        self._search_entry.set_placeholder_text('Search…')
        self._search_entry.connect('search-changed', lambda e: self._do_search())
        self._search_entry.connect('key-press-event', self._on_search_key)
        sbar.pack_start(self._search_entry, True, True, 0)

        self._all_notes_check = Gtk.CheckButton(label='All notes')
        self._all_notes_check.set_tooltip_text('Search every note, hidden ones too')
        # On by default: a note's own matches are listed first anyway.
        self._all_notes_check.set_active(True)
        self._all_notes_check.connect('toggled', lambda _: self._do_search())
        sbar.pack_start(self._all_notes_check, False, False, 0)

        close_btn = Gtk.Button(label='✕')
        close_btn.connect('clicked', lambda _: self._close_search())
        sbar.pack_start(close_btn, False, False, 0)

        # Matches in every note, shown only in All notes mode.
        self._results = Gtk.ListBox()
        self._results.set_activate_on_single_click(True)
        self._results.connect('row-activated', self._on_result_activated)
        self._results_scroll = Gtk.ScrolledWindow()
        self._results_scroll.set_policy(Gtk.PolicyType.NEVER,
                                        Gtk.PolicyType.AUTOMATIC)
        self._results_scroll.set_max_content_height(140)
        self._results_scroll.set_propagate_natural_height(True)
        self._results_scroll.add(self._results)
        self._results_scroll.set_no_show_all(True)
        search_box.pack_start(self._results_scroll, False, False, 0)

        # Keyboard shortcuts via AccelGroup (avoids unrealised-widget errors)
        accel = Gtk.AccelGroup()
        self.add_accel_group(accel)
        accel.connect(Gdk.KEY_f, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_search() or True)
        accel.connect(Gdk.KEY_b, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._toggle_bold() or True)
        accel.connect(Gdk.KEY_h, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._toggle_heading() or True)
        accel.connect(Gdk.KEY_e, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._toggle_inline_code() or True)
        accel.connect(Gdk.KEY_8, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._toggle_bullet() or True)
        accel.connect(Gdk.KEY_KP_8, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._toggle_bullet() or True)
        accel.connect(Gdk.KEY_9, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._toggle_checklist() or True)
        accel.connect(Gdk.KEY_KP_9, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._toggle_checklist() or True)
        accel.connect(Gdk.KEY_c,
                      Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
                      0, lambda *_: self._active_editor()._toggle_code_block() or True)
        accel.connect(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._active_editor()._undo() or True)
        accel.connect(Gdk.KEY_z,
                      Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
                      0, lambda *_: self._active_editor()._redo() or True)

        # Edge strips on all four sides. The outer 14px of each strip resizes
        # the matching corner, the rest resizes the edge.
        W = Gdk.WindowEdge
        for halign, valign, edges in [
            (Gtk.Align.FILL,  Gtk.Align.START, (W.NORTH_WEST, W.NORTH, W.NORTH_EAST)),
            (Gtk.Align.FILL,  Gtk.Align.END,   (W.SOUTH_WEST, W.SOUTH, W.SOUTH_EAST)),
            (Gtk.Align.START, Gtk.Align.FILL,  (W.NORTH_WEST, W.WEST,  W.SOUTH_WEST)),
            (Gtk.Align.END,   Gtk.Align.FILL,  (W.NORTH_EAST, W.EAST,  W.SOUTH_EAST)),
        ]:
            strip = Gtk.EventBox()
            strip.set_visible_window(False)
            strip.set_above_child(True)
            if halign == Gtk.Align.FILL:
                strip.set_size_request(-1, 5)
            else:
                strip.set_size_request(5, -1)
            strip.set_valign(valign)
            strip.set_halign(halign)
            strip.add_events(
                Gdk.EventMask.BUTTON_PRESS_MASK |
                Gdk.EventMask.ENTER_NOTIFY_MASK |
                Gdk.EventMask.POINTER_MOTION_MASK)
            strip.connect('button-press-event',
                          lambda w, ev, es=edges: self._on_resize(
                              w, ev, self._strip_edge(w, ev, es)))
            strip.connect('enter-notify-event',
                          lambda w, ev, es=edges: self._set_strip_cursor(w, ev, es))
            strip.connect('motion-notify-event',
                          lambda w, ev, es=edges: self._set_strip_cursor(w, ev, es))
            overlay.add_overlay(strip)

        self.connect('configure-event',    self._on_configure)
        self.connect('focus-in-event',     lambda *_: self.app._on_note_focus_in(self))
        self.connect('focus-out-event',    lambda *_: self.app._on_note_focus_out())
        self.connect('window-state-event', self._on_window_state)
        self.connect('key-press-event',    self._on_snap_key_press)
        self.connect('key-release-event',  self._on_snap_key_release)
        # Alt + scroll steps through the notes. The scrolled windows take
        # scrolls for themselves, so they are asked first as well.
        self.add_events(Gdk.EventMask.SCROLL_MASK |
                        Gdk.EventMask.SMOOTH_SCROLL_MASK)
        for widget in (self, self._sw, self._results_scroll):
            widget.connect('scroll-event', self._on_switch_scroll)
        # The window manager's close button hides the note instead of quitting.
        self.connect('delete-event', lambda *_: self._hide_note() or True)

    def _setup_rgba_visual(self):
        # Must run before the window is realized. Without a compositor the
        # alpha would draw as black, so the opacity slider is disabled then.
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        self._rgba = visual is not None and screen.is_composited()
        if self._rgba:
            self.set_visual(visual)

    # ------------------------------------------------------------------ snapping

    _SNAP_KEYS = {
        Gdk.KEY_Left: 'left', Gdk.KEY_Right: 'right',
        Gdk.KEY_Up: 'up', Gdk.KEY_Down: 'down',
    }

    _EDGE_CURSORS = {
        Gdk.WindowEdge.NORTH_WEST: 'nw-resize',
        Gdk.WindowEdge.NORTH:      'n-resize',
        Gdk.WindowEdge.NORTH_EAST: 'ne-resize',
        Gdk.WindowEdge.WEST:       'w-resize',
        Gdk.WindowEdge.EAST:       'e-resize',
        Gdk.WindowEdge.SOUTH_WEST: 'sw-resize',
        Gdk.WindowEdge.SOUTH:      's-resize',
        Gdk.WindowEdge.SOUTH_EAST: 'se-resize',
    }

    @staticmethod
    def _alt_only(ev):
        mods = ev.state & Gtk.accelerator_get_default_mod_mask()
        return mods == Gdk.ModifierType.MOD1_MASK

    def _on_snap_key_press(self, _, ev):
        # Alt + arrow snaps the note into a column (see snap.py). GNOME's own
        # shortcuts with arrows all add Super, Ctrl, or Shift to Alt.
        key = self._SNAP_KEYS.get(ev.keyval)
        if key is None or not self._alt_only(ev):
            return False
        if key in self._snap_held:
            self._snap_held.remove(key)
        self._snap_held.append(key)
        self._snap_to(self._snap_held)
        return True

    def _on_snap_key_release(self, _, ev):
        key = self._SNAP_KEYS.get(ev.keyval)
        if key in self._snap_held:
            self._snap_held.remove(key)
        elif ev.keyval in (Gdk.KEY_Alt_L, Gdk.KEY_Alt_R):
            self._snap_held.clear()
            self.app.end_note_switch()
        return False

    def _on_switch_scroll(self, _, ev):
        # Alt + scroll brings the next or previous note forward (see
        # PostItApp.scroll_notes()).
        if not self._alt_only(ev):
            return False
        dy = 0
        if ev.direction == Gdk.ScrollDirection.SMOOTH:
            _ok, _dx, dy = ev.get_scroll_deltas()
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            dy = 1
        elif ev.direction == Gdk.ScrollDirection.UP:
            dy = -1
        if dy:
            self.app.scroll_notes(self, dy, ev.time)
        return True

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
        x, y, w, h = snap_rect(keys, self.get_position() + self.get_size(),
                               areas, index)
        if tuple(self.get_size()) == (w, h):
            self.move(x, y)
            return
        # Moving in the same request as a resize lets the window manager keep
        # the note on screen using its old, larger size, which can leave it a
        # few pixels off the slot. Move once the new size has been applied.
        self._snap_pending_move = (x, y, w, h)
        if self._collapsed:
            # A collapsed note keeps the width in its size request, so the
            # new width has to go there or the resize is ignored.
            self._lock_size(True, w)
        self.resize(w, h)
        GLib.timeout_add(300, self._apply_snap_move)

    def _apply_snap_move(self):
        if self._snap_pending_move is not None:
            x, y, _, _ = self._snap_pending_move
            self._snap_pending_move = None
            self.move(x, y)
        return False

    def _on_window_state(self, _, event):
        self._refresh_collapse_button(event.new_window_state)

    # ------------------------------------------------------------------ title editing

    def _on_title_click(self, widget, ev):
        if ev.type == Gdk.EventType.DOUBLE_BUTTON_PRESS and ev.button == 1:
            self._title_drag = None
            self._toggle_maximize()
            return True
        if ev.button == 3:
            self._title_drag = None
            self._show_ctx_menu(widget, ev)
            return True
        if ev.button == 1 and not self._editing:
            # Do not start a window move immediately on button-press.
            # On X11, begin_move_drag() grabs the pointer early enough that the
            # second click may never be delivered as DOUBLE_BUTTON_PRESS.  Wait
            # until the pointer actually moves past GTK's drag threshold.
            self._title_drag = (ev.button, ev.x_root, ev.y_root, ev.time)
            self._release_text_focus()
            return True
        return False

    def _toggle_maximize(self):
        if self._collapsed:
            return
        if self.is_maximized():
            self.unmaximize()
            return
        # Remember the normal rectangle: to_dict() saves it while maximized,
        # so the next start does not open at full-screen size.
        self._normal_geometry = self.get_position() + self.get_size()
        self.maximize()

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
            self._show_ctx_menu(widget, ev, above=True)
            return True
        if ev.button == 1 and widget is self._bottom_bar_box:
            self._release_text_focus()
        return False

    def _release_text_focus(self):
        # Clicking the bars means the user is not typing, so stop the text
        # cursor from blinking until the text area is clicked again.
        self.set_focus(None)

    def _show_title(self):
        """The title on the bar, or a dimmed Untitled when there is none."""
        self._title_label.set_text(self.title or UNTITLED_LABEL)
        context = self._title_label.get_style_context()
        if self.title:
            context.remove_class('untitled')
        else:
            context.add_class('untitled')

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
        self._show_title()
        self._title_box.add(self._title_label)
        self._title_label.show()
        self.set_title(self.title or UNTITLED_LABEL)
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

    def _strip_edge(self, widget, ev, edges):
        start, middle, end = edges
        if widget.get_halign() == Gtk.Align.FILL:
            pos, length = ev.x, widget.get_allocated_width()
        else:
            pos, length = ev.y, widget.get_allocated_height()
        if pos < 14:
            return start
        if pos > length - 14:
            return end
        return middle

    def _set_strip_cursor(self, widget, ev, edges):
        edge = self._strip_edge(widget, ev, edges)
        self._set_resize_cursor(widget, ev, self._EDGE_CURSORS[edge])


    # ------------------------------------------------------------------ search

    def _on_search_key(self, entry, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self._close_search()
            return True
        if not self._results_scroll.get_visible():
            return False
        # The arrows pick a match while the cursor stays in the entry, so
        # Enter opens it, not a line break in the note the focus moved to.
        if ev.keyval in (Gdk.KEY_Down, Gdk.KEY_Up):
            self._step_result(1 if ev.keyval == Gdk.KEY_Down else -1)
            return True
        if ev.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            # Enter opens the picked match, or the first one.
            row = (self._results.get_selected_row()
                   or self._results.get_row_at_index(0))
            if row is not None and getattr(row, 'match', None):
                self._on_result_activated(self._results, row)
                return True
        return False

    def _step_result(self, step):
        """Select the match `step` rows from the selected one, or the first,
        and scroll it into view."""
        rows = [r for r in self._results.get_children()
                if getattr(r, 'match', None)]
        if not rows:
            return
        selected = self._results.get_selected_row()
        index = (rows.index(selected) + step if selected in rows else 0)
        row = rows[max(0, min(index, len(rows) - 1))]
        self._results.select_row(row)
        alloc = row.get_allocation()
        self._results_scroll.get_vadjustment().clamp_page(
            alloc.y, alloc.y + alloc.height)

    # ------------------------------------------------------------------ collapse

    def _set_body_visible(self, visible):
        for widget in (self._sw, self._search_revealer, self._bottom_bar_box):
            widget.set_visible(visible)

    def _refresh_collapse_state(self):
        set_button_content(self._collapse_btn,
                           StrokeIcon('right' if self._collapsed else 'down'))
        self._refresh_collapse_button()

    def set_hidden_count(self, count):
        """Say how many notes are hidden in the Hidden Notes button's
        tooltip."""
        self._hidden_btn.set_tooltip_text(
            f'Hidden Notes ({count})' if count else 'Hidden Notes')

    # The window manager owns the size of a maximized or tiled window and
    # ignores resizes, so such a note cannot be collapsed until it is restored.
    _WM_FIXED = (Gdk.WindowState.MAXIMIZED | Gdk.WindowState.TILED
                 | Gdk.WindowState.TOP_TILED | Gdk.WindowState.BOTTOM_TILED
                 | Gdk.WindowState.LEFT_TILED | Gdk.WindowState.RIGHT_TILED)

    def _refresh_collapse_button(self, state=None):
        if state is None:
            gdk_window = self.get_window()
            state = gdk_window.get_state() if gdk_window else 0
        blocked = bool(state & self._WM_FIXED) and not self._collapsed
        self._collapse_btn.set_sensitive(not blocked)
        if blocked:
            tip = 'Restore the note to collapse it'
        else:
            tip = 'Expand' if self._collapsed else 'Collapse'
        self._collapse_btn.set_tooltip_text(tip)

    def _toggle_collapse(self):
        if self._collapsed:
            self._expand()
        else:
            self._collapse()
        self._queue_save()

    def _lock_size(self, locked, width=-1):
        # A collapsed note cannot be resized. That keeps the window manager
        # from tiling or maximizing it, which would stretch an empty note over
        # the screen. The width is kept through the size request.
        self.set_size_request(width if locked else -1, -1)
        self.set_resizable(not locked)

    def _collapse(self):
        if self._collapsed:
            return
        width, height = self.get_size()
        self._expanded_height = height
        self._collapsed = True
        self.set_focus(None)
        self._set_body_visible(False)
        self._refresh_collapse_state()
        self._lock_size(True, width)
        self.resize(width, 1)
        # The first resize can be clamped to the size the hidden body still
        # asked for, which leaves an invisible window that eats clicks. Ask
        # again once GTK has relaid out the header alone.
        GLib.timeout_add(150, self._shrink_to_header)

    def _shrink_to_header(self):
        if self._collapsed:
            self.resize(self.get_size()[0], 1)
        return False

    def _expand(self):
        if not self._collapsed:
            return
        self._collapsed = False
        self._lock_size(False)
        self._set_body_visible(True)
        self._refresh_collapse_state()
        self.resize(self.get_size()[0], self._expanded_height)

    def _toggle_search(self):
        self._expand()
        if self._search_revealer.get_reveal_child():
            self._close_search()
        else:
            self._search_revealer.set_reveal_child(True)
            GLib.idle_add(self._search_entry.grab_focus)

    def _close_search(self):
        self._search_revealer.set_reveal_child(False)
        self._search_entry.set_text('')
        # The expands a match showed open fold again.
        for editor in [self] + self._all_cells():
            editor._clear_highlights()
            editor._refresh_line_styles()
        self.tv.grab_focus()

    def _do_search(self):
        for editor in [self] + self._all_cells():
            editor._clear_highlights()
        query = self._search_entry.get_text()
        if not query:
            self._refresh_results(query)
            self._refresh_line_styles()
            return
        # In the note's text and in every table cell. Matches in a folded
        # expand show it open.
        for editor in [self] + self._all_cells():
            editor._highlight(query)
        self._refresh_results(query)

    def _refresh_results(self, query):
        for row in self._results.get_children():
            self._results.remove(row)
        if not (query and self._all_notes_check.get_active()):
            self._results_scroll.hide()
            return
        matches = find_matches(self.app.searchable_notes(first=self), query)
        for m in matches:
            # Only the matching line shrinks to fit, so the title and the
            # hidden mark stay readable however long the line is.
            line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            title = Gtk.Label(xalign=0)
            title.set_markup(f'<b>{GLib.markup_escape_text(m.title)}</b>')
            title.set_max_width_chars(16)
            title.set_ellipsize(Pango.EllipsizeMode.END)
            line.pack_start(title, False, False, 0)
            snippet = Gtk.Label(label=m.snippet, xalign=0)
            snippet.set_ellipsize(Pango.EllipsizeMode.END)
            line.pack_start(snippet, True, True, 0)
            if m.hidden:
                hidden = Gtk.Label()
                hidden.set_markup('<i>(hidden)</i>')
                line.pack_start(hidden, False, False, 0)
            row = Gtk.ListBoxRow()
            row.match = m
            row.add(line)
            self._results.add(row)
        if not matches:
            row = Gtk.ListBoxRow(activatable=False, selectable=False)
            row.add(Gtk.Label(label='No matches', xalign=0))
            self._results.add(row)
        self._results.show_all()
        self._results_scroll.show()

    def _on_result_activated(self, _listbox, row):
        m = getattr(row, 'match', None)
        if m is not None:
            self.app.reveal_match(m.note_id, m.start, m.end)

    def first_text(self, chars=200):
        """The start of the note's text, for naming an untitled note."""
        buf = self.tv.get_buffer()
        return buf.get_slice(buf.get_start_iter(),
                             buf.get_iter_at_offset(chars), True)

    def buffer_text(self):
        """The note's text for searching all notes, with the text of each
        table cell after it, one per line. See show_match()."""
        buf = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        for cell in self._all_cells():
            cbuf = cell.tv.get_buffer()
            text += '\n' + cbuf.get_slice(cbuf.get_start_iter(),
                                          cbuf.get_end_iter(), True)
        return text

    def _match_in_cell(self, start, end):
        """(cell, start, end) for a match past the note's own text in
        buffer_text(), or None for one in the note's text."""
        buf = self.tv.get_buffer()
        offset = buf.get_char_count()
        if start < offset:
            return None
        for cell in self._all_cells():
            length = cell.tv.get_buffer().get_char_count()
            offset += 1
            if start <= offset + length:
                return cell, start - offset, end - offset
            offset += length
        return None

    def show_match(self, start, end):
        # Select the match and scroll to it once the window has its size.
        self._expand()
        found = self._match_in_cell(start, end)
        if found is not None:
            cell, low, high = found
            cbuf = cell.tv.get_buffer()
            cbuf.select_range(cbuf.get_iter_at_offset(low),
                              cbuf.get_iter_at_offset(high))
            self._open_sections_around(
                self.tv.get_buffer().get_iter_at_child_anchor(
                    cell.table.anchor).get_offset())
            cell.tv.grab_focus()
            return
        self._open_sections_around(start)
        buf = self.tv.get_buffer()
        buf.select_range(buf.get_iter_at_offset(start), buf.get_iter_at_offset(end))
        self.tv.grab_focus()
        GLib.idle_add(lambda: self.tv.scroll_to_mark(
            buf.get_insert(), 0.1, False, 0, 0) and False)

    def _active_editor(self):
        """The editor the Format and Insert menus and the shortcuts act on:
        the note's text, or the table cell the cursor was last in."""
        return getattr(self, '_active', None) or self

    def _set_active_editor(self, editor):
        self._active = editor
        # A note has one selection, as a page does: the note's text and each
        # cell are text views of their own, so the ones the cursor is not in
        # drop theirs. The selection's end comes to the cursor, which stays
        # where it is, so nothing follows a cursor that moved.
        for other in [self] + self._all_cells():
            if other is not editor:
                buf = other.tv.get_buffer()
                if buf.get_has_selection():
                    buf.move_mark(buf.get_selection_bound(),
                                  buf.get_iter_at_mark(buf.get_insert()))
        self._refresh_format_buttons()

    def _refresh_format_buttons(self):
        # The Format button is lit while a format is on at the cursor, so
        # that what is typed next gets it. Its menu checks which ones are.
        ctx = self._format_btn.get_style_context()
        ed = self._active_editor()
        if ed._bold_active or ed._heading_active or ed._code_active:
            ctx.add_class('pinned')
        else:
            ctx.remove_class('pinned')

    def _format_items(self):
        ed = self._active_editor()
        return [
            BarItem('<b>B</b>', 'Bold', '**text**', 'Ctrl+B', ed._toggle_bold,
                    ed._bold_active, not ed._heading_active),
            BarItem('<b>H</b>', 'Heading', '# text', 'Ctrl+H',
                    ed._toggle_heading, ed._heading_active, True),
            BarItem('&lt;/&gt;', 'Inline code', '`text`', 'Ctrl+E',
                    ed._toggle_inline_code, ed._code_active, True),
        ]

    def _insert_items(self):
        ed = self._active_editor()
        return [
            # A bullet is small in any font, so it is drawn a size up.
            BarItem('<span size="x-large">•</span>', 'Bullet list', '- item', 'Ctrl+8',
                    ed._toggle_bullet, None, True),
            BarItem(CHECKBOX_MARKER.strip(), 'Checklist', '[ ] item', 'Ctrl+9',
                    ed._toggle_checklist, None, True),
            BarItem('❝', 'Quote', '> text', '',
                    lambda: ed._toggle_list((QUOTE_MARKER,)), None, True),
            BarItem('&lt;/&gt;', 'Code block', '```', 'Ctrl+Shift+C',
                    ed._toggle_code_block, None, True, boxed=True),
            BarItem('—', 'Divider', '---', '', ed._insert_divider,
                    None, True),
            BarItem('▸', 'Expand', '', '', ed._insert_section, None, True),
            # A table is not put in a table's cell.
            BarItem('⊞', 'Table', '', '', self._insert_table, None,
                    ed is self),
            BarItem('🖼', 'Image…', '', 'Ctrl+V',
                    ed._choose_and_insert_image, None, True),
        ]

    def _popup_bar_menu(self, button, items):
        """Open a menu of items above a button of the bottom bar. Each row
        shows the item's icon and name, the Markdown that typing makes it
        from, and its shortcut, in columns. A menu is a window of its own, so
        it may be larger than the note."""
        menu = Gtk.Menu()
        # A format that is on has its icon lit, as the bar buttons are, not a
        # check mark, whose column would push every row of the menu right.
        menu.set_reserve_toggle_size(False)
        icons = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        names = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        hints = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        for entry in items:
            label, hint, keys = entry.label, entry.hint, entry.keys
            item = Gtk.MenuItem()
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
            icon = Gtk.Label()
            icon.set_markup(entry.icon)
            icon.get_style_context().add_class('menu-icon')
            # The icon hugs its text, so a box drawn around it fits it, and
            # its column is as wide as the widest icon.
            icon.set_halign(Gtk.Align.CENTER)
            icon_cell = Gtk.Box()
            icon_cell.set_center_widget(icon)
            icons.add_widget(icon_cell)
            if entry.boxed:
                icon.get_style_context().add_class('boxed')
            if entry.active:
                icon.get_style_context().add_class('on')
            row.pack_start(icon_cell, False, False, 0)
            name = Gtk.Label(label=label, xalign=0)
            names.add_widget(name)
            row.pack_start(name, False, False, 0)
            typed = Gtk.Label(xalign=0)
            # What is typed as it is, in <tt>: the note's font joins dashes.
            typed.set_markup(f'<tt>{GLib.markup_escape_text(hint)}</tt>')
            hints.add_widget(typed)
            row.pack_start(typed, False, False, 0)
            shortcut = Gtk.Label(label=keys, xalign=1)
            row.pack_end(shortcut, False, False, 0)
            for dim in (typed, shortcut):
                dim.get_style_context().add_class('dim-label')
            item.add(row)
            item.set_sensitive(entry.sensitive)
            item.connect('activate', lambda _, act=entry.action: act())
            menu.append(item)
        menu.show_all()
        # Kept until the next one opens, so it is not freed while shown.
        self._bar_menu = menu
        menu.popup_at_widget(button, Gdk.Gravity.NORTH_WEST,
                             Gdk.Gravity.SOUTH_WEST, None)

    # ------------------------------------------------------------------ context menu

    def _show_ctx_menu(self, widget, ev, above=False):
        """Open the note's popover at the click position.

        Built on every open and destroyed when it closes, so it always shows
        the note's current state. A popover is drawn inside the window it is
        attached to and cannot extend past it. When the note is too small for
        it, which a collapsed note always is, it is attached to a transparent
        window of its own instead.
        """
        pop = Gtk.Popover()
        pop.set_constrain_to(Gtk.PopoverConstraint.NONE)
        pop.connect('closed', lambda p: GLib.idle_add(p.destroy))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_border_width(4)
        pop.add(box)
        self._build_ctx_menu(pop, box)
        box.show_all()

        x, y = int(ev.x), int(ev.y)
        win_x, win_y = widget.translate_coordinates(self, x, y)
        height = self._popover_size(pop)[1]
        win_h = self.get_allocated_height()
        position = Gtk.PositionType.BOTTOM
        fits = False
        if not self._collapsed:
            if above and win_y >= height:
                position, fits = Gtk.PositionType.TOP, True
            elif above and height <= win_h:
                # Not enough room above: open from the title bar instead.
                widget, fits = self._title_box, True
                x, y = self.translate_coordinates(widget, win_x, 0)
            elif not above and win_y + height <= win_h:
                fits = True
        if fits:
            pop.set_relative_to(widget)
            pop.set_position(position)
            self._point_popover(pop, x, y)
            pop.popup()
            return
        self._show_ctx_menu_in_own_window(pop, win_x, win_y)

    @staticmethod
    def _popover_size(pop):
        # The popover's own size request is 0 until it is attached, so size it
        # from its content, plus the room its arrow and border take.
        child = pop.get_child()
        return (child.get_preferred_width()[1] + POPOVER_PAD,
                child.get_preferred_height()[1] + POPOVER_PAD)

    @staticmethod
    def _point_popover(pop, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = x, y, 1, 1
        pop.set_pointing_to(rect)

    def _show_ctx_menu_in_own_window(self, pop, win_x, win_y):
        origin_x, origin_y = self.get_window().get_origin()[1:]
        margin = 24
        pop_w, pop_h = self._popover_size(pop)
        width, height = pop_w + 2 * margin, pop_h + 2 * margin
        host = Gtk.Window(type=Gtk.WindowType.POPUP)
        screen = host.get_screen()
        visual = screen.get_rgba_visual()
        if visual is not None and screen.is_composited():
            host.set_visual(visual)
            host.set_app_paintable(True)

            def clear(_widget, cr):
                cr.set_operator(cairo.Operator.CLEAR)
                cr.paint()
                cr.set_operator(cairo.Operator.OVER)
                return False
            host.connect('draw', clear)
        host.set_default_size(width, height)
        anchor = Gtk.Box()
        anchor.set_size_request(1, 1)
        fixed = Gtk.Fixed()
        fixed.put(anchor, width // 2, margin)
        host.add(fixed)
        # Keep the whole popover on its monitor.
        display = host.get_display()
        monitor = display.get_monitor_at_point(origin_x + win_x,
                                               origin_y + win_y)
        area = monitor.get_workarea()
        left = min(max(origin_x + win_x - width // 2, area.x),
                   area.x + area.width - width)
        top = min(max(origin_y + win_y - margin, area.y),
                  area.y + area.height - height)
        host.move(left, top)
        host.show_all()
        pop.set_relative_to(anchor)
        pop.set_position(Gtk.PositionType.BOTTOM)
        self._point_popover(pop, 0, 0)
        pop.connect('closed', lambda _: GLib.idle_add(host.destroy))
        pop.popup()

    def _ctx_item(self, pop, box, label, callback, danger=False):
        item = Gtk.ModelButton(text=label)
        item.set_halign(Gtk.Align.FILL)
        if danger:
            item.get_style_context().add_class('danger')

        def clicked(_):
            # Close first, so a dialog or the title entry does not open under
            # a popover that still holds the pointer and focus.
            pop.popdown()
            GLib.idle_add(lambda: callback() and False)
        item.connect('clicked', clicked)
        box.pack_start(item, False, False, 0)
        return item

    def _build_ctx_menu(self, pop, box):
        def separator():
            box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL),
                           False, False, 2)

        self._ctx_item(pop, box, 'Edit Title', self._start_title_edit)
        separator()
        self._build_color_row(box)
        self._build_opacity_row(box)
        self._build_font_row(box)
        separator()
        self._ctx_item(pop, box, 'Minimize', self.iconify)
        if self.app.autostart_available:
            login = Gtk.ModelButton(text='Start at Login')
            login.set_property('role', Gtk.ButtonRole.CHECK)
            login.set_property('active', self.app.autostart_enabled())
            login.connect('clicked', lambda b: (
                self.app.set_autostart(not b.get_property('active')),
                pop.popdown()))
            box.pack_start(login, False, False, 0)
        self._ctx_item(pop, box, 'Help', lambda: show_help(self))
        self._ctx_item(pop, box, 'About', self._show_about_dialog)
        separator()
        self._ctx_item(pop, box, 'Delete Note', self._confirm_delete,
                       danger=True)
        self._ctx_item(pop, box, 'Quit', self.app.quit_app)

    def _build_color_row(self, box):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        row.set_halign(Gtk.Align.CENTER)
        row.set_margin_top(3)
        row.set_margin_bottom(3)
        swatches = {}

        def choose(name):
            self._set_color(name)
            for other, swatch in swatches.items():
                ctx = swatch.get_style_context()
                if other == name:
                    ctx.add_class('selected')
                else:
                    ctx.remove_class('selected')

        for name in PALETTE:
            swatch = Gtk.Button()
            swatch.set_can_focus(False)
            swatch.set_tooltip_text(name.capitalize())
            ctx = swatch.get_style_context()
            ctx.add_class('swatch')
            ctx.add_class(f'swatch-{name}')
            if name == self._color:
                ctx.add_class('selected')
            swatch.connect('clicked', lambda _, n=name: choose(n))
            swatches[name] = swatch
            row.pack_start(swatch, False, False, 0)
        box.pack_start(row, False, False, 0)

    def _build_font_row(self, box):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        row.set_margin_top(4)
        row.pack_start(Gtk.Label(label='Font size', xalign=0), True, True, 0)
        size = Gtk.Label(label=f'{self._font_size}px')
        size.set_width_chars(5)

        def change(delta):
            self._change_font_size(delta)
            size.set_text(f'{self._font_size}px')

        for label, tip, delta in (('A−', 'Decrease font size', -1),
                                  ('A+', 'Increase font size', +1)):
            button = Gtk.Button(label=label)
            button.set_tooltip_text(tip)
            button.set_can_focus(False)
            button.get_style_context().add_class('step')
            button.connect('clicked', lambda _, d=delta: change(d))
            if delta < 0:
                row.pack_start(button, False, False, 0)
                row.pack_start(size, False, False, 0)
            else:
                row.pack_start(button, False, False, 0)
        box.pack_start(row, False, False, 0)

    def _build_opacity_row(self, box):
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        head.pack_start(Gtk.Label(label='Opacity', xalign=0), True, True, 0)
        percent = Gtk.Label(label=f'{round(self._opacity * 100)}%')
        head.pack_end(percent, False, False, 0)
        scale = Gtk.Scale.new_with_range(
            Gtk.Orientation.HORIZONTAL,
            round(MIN_OPACITY * 100), round(MAX_OPACITY * 100), 5)
        scale.set_draw_value(False)
        scale.set_size_request(180, -1)
        scale.set_value(round(self._opacity * 100))
        scale.set_sensitive(self._rgba)
        if not self._rgba:
            scale.set_tooltip_text('Needs a compositing window manager')

        def changed(sc):
            value = round(sc.get_value() / 5) * 5
            percent.set_text(f'{value}%')
            self._set_opacity(value / 100)
        scale.connect('value-changed', changed)
        box.pack_start(head, False, False, 0)
        box.pack_start(scale, False, False, 0)

    def _set_opacity(self, opacity):
        opacity = min(MAX_OPACITY, max(MIN_OPACITY, opacity))
        if opacity == self._opacity:
            return
        self._opacity = opacity
        self._apply_color()
        self._queue_save()

    def _set_color(self, name):
        if name not in PALETTE or name == self._color:
            return
        self._color = name
        self._apply_color()
        self._queue_save()

    def _apply_color(self):
        # One provider per window, at USER priority so it wins over BASE_CSS.
        # A provider only styles the widget it is added to, so it goes on the
        # window and on both bars.
        if getattr(self, '_color_prov', None) is None:
            self._color_prov = Gtk.CssProvider()
            for widget in (self, self._hdr, self._btmbar):
                widget.get_style_context().add_provider(
                    self._color_prov, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        self._color_prov.load_from_data(note_css(self._color, self._opacity).encode())
        # Code blocks follow the note color, so they stay readable on it.
        self._code_rgba = Gdk.RGBA()
        self._code_rgba.parse(code_background(self._color))
        self._inline_rgba = Gdk.RGBA()
        self._inline_rgba.parse(inline_code_background(self._color))
        self._body_rgba = Gdk.RGBA()
        self._body_rgba.parse(PALETTE[self._color][0])
        self.tv.queue_draw()
        for table in getattr(self, '_table_widgets', []):
            table.queue_draw()

    def _show_about_dialog(self):
        dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        dialog.set_program_name('Ynote')
        dialog.set_version(__version__)
        # Where this copy runs from tells the installed package apart from a
        # source checkout, which is the first thing to check when an update
        # seems to have no effect.
        dialog.set_comments(
            'Engineer-friendly sticky notes\n\n'
            f'Notes: {display_path(CONF_DIR)}\n'
            f'Running from: {display_path(PROJECT_DIR)}')
        # The MIT license asks for this notice to travel with the program.
        dialog.set_copyright('Copyright (c) 2026 Youngsik Yang')
        dialog.set_license_type(Gtk.License.MIT_X11)
        try:
            dialog.set_logo(
                GdkPixbuf.Pixbuf.new_from_file_at_scale(ICON_PATH, 96, 96, True))
        except GLib.Error:
            pass
        dialog.run()
        dialog.destroy()

    def _confirm_delete(self):
        # Delete sits next to Hide and cannot be undone, so ask first. An empty
        # note has nothing to lose and goes without asking.
        buf = self.tv.get_buffer()
        if buf.get_char_count() == 0:
            self.app.delete_note(self.note_id)
            return
        dialog = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.NONE,
            text=f'Delete "{self.title or UNTITLED_LABEL}"?')
        dialog.format_secondary_text(
            'The note and its images are deleted permanently. To keep the note '
            'but take it off the screen, hide it instead.')
        dialog.add_button('Cancel', Gtk.ResponseType.CANCEL)
        delete_btn = dialog.add_button('Delete', Gtk.ResponseType.ACCEPT)
        delete_btn.get_style_context().add_class('destructive-action')
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        response = dialog.run()
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            self.app.delete_note(self.note_id)

    def _hide_note(self):
        self.hide()
        self.app.put_first_in_hidden([self])
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

    def _all_cells(self):
        return [cell for table in self._table_widgets
                for cell in table.all_cells()]

    def _on_tv_size(self, tv, allocation):
        if allocation.width != self._tv_width:
            self._tv_width = allocation.width
            for table in self._table_widgets:
                table.queue_widths()

    def _change_font_size(self, delta: int):
        self._font_size = max(8, min(32, self._font_size + delta))
        self._apply_note_font()
        for cell in self._all_cells():
            cell._apply_note_font()
        for table in self._table_widgets:
            table.queue_widths()
        self._queue_save()

    def _on_configure(self, _, event):
        pending = self._snap_pending_move
        if pending is not None and (event.width, event.height) == pending[2:]:
            self._apply_snap_move()
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
        if self.is_maximized() and self._normal_geometry:
            x, y, w, h = self._normal_geometry
        if self._collapsed:
            h = self._expanded_height
        buf  = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        return dict(id=self.note_id, x=x, y=y, w=w, h=h,
                    text=text, title=self.title, on_top=self._on_top,
                    hidden=not self.get_visible(),
                    sort_order=self.sort_order,
                    bold_ranges=self._get_tag_ranges(self._bold_tag),
                    heading_ranges=self._get_tag_ranges(self._heading_tag),
                    code_ranges=self._get_tag_ranges(self._code_tag),
                    backtick_ranges=self._get_tag_ranges(self._backtick_tag),
                    images=self._get_images_state(),
                    tables=self._get_tables_state(),
                    font_size=self._font_size, color=self._color,
                    opacity=self._opacity, collapsed=self._collapsed)
