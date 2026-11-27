import bisect
import heapq
from collections import namedtuple
import math
import os
import re
import shutil
import sys
import unicodedata
import urllib.parse
import uuid

import cairo
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gtk, Gdk, GLib, Pango, PangoCairo, GdkPixbuf

from . import __version__
from .config import (
    BULLET_MARKER, CHECKBOX_MARKER, CHECKED_MARKER, CODE_ANCHOR, EXPAND_CLOSED,
    EXPAND_END, EXPAND_OPEN, QUOTE_MARKER,
    CODE_PAD_CHAR, CONF_DIR,
    DIVIDER_TEXT, ICON_PATH, IMAGE_ANCHOR, IMAGES_DIR, NEW_NOTE_LABEL,
    PROJECT_DIR, TABLE_MARKER, UNTITLED_LABEL, display_path,
)
from .help import show_help
from .images import image_files_from_metadata, image_path, normalize_image_meta
from .links import find_links
from .markdown import fit_between, from_markdown, is_all_code, to_markdown
from .models import MAX_OPACITY, MIN_OPACITY, normalize_note_data
from .search import find_matches
from .sections import find_sections, hidden_lines, section_at
from .sections import is_title as is_section_title
from .snap import snap_rect
from .styles import (
    BODY_FONT, BULLET_SIZE, CHECKBOX_SIZE, CODE_BLOCK_MARGIN, CODE_FONT,
    CODE_OUTLINE, EXPAND_BUTTON_PAD, EXPAND_GAP, EXPAND_MARGIN, EXPAND_PAD,
    EXPAND_TITLE_SCALE,
    MARKER_GAP,
    QUOTE_BAR,
    CODE_GAP, CODE_PAD, CODE_PAD_Y, CODE_RADIUS, CODE_TEXT_COLOR, HEADING_FONT,
    HEADING_SCALE, INLINE_CODE_RISE,
    LINE_SPACING, PALETTE, TABLE_MARGIN, TABLE_MIN_COLUMN, TABLE_PAD,
    TABLE_PAD_Y, code_background, inline_code_background, note_css,
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


def outlined_box(cr, fill, x, y, width, height):
    """Fill a rounded box and draw a thin outline just inside its edge."""
    r = min(CODE_RADIUS, width / 2, height / 2)
    x, y, width, height = x + 0.5, y + 0.5, width - 1, height - 1
    cr.new_sub_path()
    cr.arc(x + width - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + width - r, y + height - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + height - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()
    cr.set_source_rgba(fill.red, fill.green, fill.blue, 1.0)
    cr.fill_preserve()
    cr.set_source_rgba(*CODE_OUTLINE)
    cr.set_line_width(1)
    cr.stroke()


# Space between the note's edge and its text, the same on all four sides.
TEXT_MARGIN = 8

# Characters below this are Latin, which the note's font has, so they never
# need another font. Everything from here on is looked up.
FIRST_NON_LATIN = 0x250


def even_slots(metrics, base, spacing):
    """The spacing above and below each line that makes every line the same.

    A line is as tall as the tallest font in it. The note's font may lack some
    of its characters, which another, taller font then draws, and that line is
    taller than the rest. `metrics` has the (ascent, descent) of the tallest
    font in each line. `base` is the same for the note's own font, and
    `spacing` the (above, below) a line of it has. Every line gets the spacing
    that puts its baseline the same distance from the top and from the bottom
    of the room it takes: the most any line needs, and no less than a line of
    the note's font has. That way a font with more room of its own takes the
    place of the spacing, and the lines are no further apart than that.
    """
    top = slot_ascent(metrics, base, spacing)
    bottom = max([base[1] + spacing[1]] + [d for _, d in metrics])
    return [(max(0, math.floor(top - a + 0.5)),
             max(0, math.floor(bottom - d + 0.5)))
            for a, d in metrics]


def slot_ascent(metrics, base, spacing):
    """How far the baseline is below the top of the room every line takes."""
    return max([base[0] + spacing[0]] + [a for a, _ in metrics])


def changed_end(old, new):
    """Offset in new where the text that differs from old ends.

    Undo puts the cursor where the edit was: at the start of text that came
    out, or after text that went back in.
    """
    limit = min(len(old), len(new))
    start = 0
    while start < limit and old[start] == new[start]:
        start += 1
    end = 0
    while end < limit - start and old[-1 - end] == new[-1 - end]:
        end += 1
    return len(new) - end

LIST_MARKERS = (BULLET_MARKER, CHECKBOX_MARKER, CHECKED_MARKER, QUOTE_MARKER)

# An item of the Format or Insert menu: its icon as Pango markup, its name,
# the Markdown typed for it, its shortcut, what it does, whether it is on, or
# None when it is not a format, and whether it can be chosen. A boxed icon is
# drawn inside a box, as the code block one is.
BarItem = namedtuple('BarItem', 'icon label hint keys action active sensitive '
                                'boxed', defaults=(False,))
CHECK_MARKERS = (CHECKBOX_MARKER, CHECKED_MARKER)

# Room a popover's arrow and border take around its content.
POPOVER_PAD = 24

# Pixels around a to-do box that still check it when clicked.
CHECKBOX_HIT_MARGIN = 6

# What a typed prefix at the start of a line becomes when Space follows it,
# like Markdown. "• [ ]" is "- [ ]" after "- " has already become a bullet.
TYPED_MARKERS = {
    '-': BULLET_MARKER,
    '>': QUOTE_MARKER,
    '[]': CHECKBOX_MARKER, '[ ]': CHECKBOX_MARKER,
    '[x]': CHECKED_MARKER, '[X]': CHECKED_MARKER,
    '• []': CHECKBOX_MARKER, '• [ ]': CHECKBOX_MARKER,
    '• [x]': CHECKED_MARKER, '• [X]': CHECKED_MARKER,
}

# How many spaces of the note's font a tab is as wide as: one level of a list.
# Items were indented by this many spaces before a tab took one level.
INDENT_SPACES = 4

# "**text**" just typed at the end of the text before the cursor: the text is
# not empty, does not start or end with a space, and has no asterisk, as in
# Markdown. An asterisk or a backslash right before it keeps it as it is.
TYPED_BOLD_RE = re.compile(r'(?<![*\\])\*\*([^*\s](?:[^*]*[^*\s])?)\*\*$')


def tabbed_indent(indent):
    """The indent of a list item with each run of INDENT_SPACES spaces made a
    tab, as items indented before tabs were are opened."""
    return indent.replace(' ' * INDENT_SPACES, '\t')


def cell_width(line):
    """How many monospace cells `line` takes: a tab runs to the next stop of 8
    and a full-width character or emoji takes two."""
    line = line.expandtabs(8)
    if line.isascii():
        return len(line)
    return sum(2 if unicodedata.east_asian_width(ch) in 'WF' else 1
               for ch in line)


class NoteWindow(Gtk.ApplicationWindow):
    # Set while Ctrl+Shift+V pastes text as it is.
    _paste_plain = False
    # The expands found when the note was last styled, and the lines they
    # hide; replaced, never changed in place. See _apply_sections().
    _sections = ()
    _hidden_lines = frozenset()
    # The title line of the expand whose button is under the pointer.
    _expand_hover = None

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
        self._restoring   = False
        self._snap_sid    = None
        self._history   = [{'text': data.get('text', ''),
                             'bold': data.get('bold_ranges', []),
                             'heading': data.get('heading_ranges', []),
                             'code': data.get('code_ranges', []),
                             'backtick': data.get('backtick_ranges', []),
                             'images': data.get('images', [])}]
        self._hist_pos  = 0
        self._bold_active = False
        self._code_active = False
        self._heading_active = False
        self._pending_format_inserts = []
        self._image_widgets = []
        self._title_drag = None
        self._snap_held = []
        self._snap_pending_move = None
        self._normal_geometry = None
        # [first line, last line, right] of each code block drawn so far, in
        # order. See _watch_code_blocks().
        self._code_blocks = []

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
        sw = self._sw

        self.tv = Gtk.TextView()
        # Soft-wrap prose to the note width so narrow notes stay readable.
        # Code lines opt out through the code tag's wrap mode.
        self.tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.tv.set_left_margin(TEXT_MARGIN)
        self.tv.set_right_margin(TEXT_MARGIN)
        # The same room between every two lines, also the rows of a wrapped
        # line. A code block's lines set their own, inside its box.
        # Divided above and below by _refresh_code_spacing().
        self.tv.set_top_margin(TEXT_MARGIN)
        self.tv.set_bottom_margin(TEXT_MARGIN)
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
        # Deleting text moves the cursor without a mark-set, as Backspace does
        # when it joins a line to the one above, so the formats are taken from
        # the cursor again afterwards.
        buf.connect_after('delete-range',
                          lambda *_: self._sync_format_state())
        self._hl_tag   = buf.create_tag('search-hl',
                                        background='#FFCC00', foreground='#000')
        self._bold_tag = buf.create_tag('bold', weight=Pango.Weight.BOLD)
        self._code_tag = buf.create_tag('code',
                                        family=CODE_FONT,
                                        foreground='#222',
                                        # Keep commands on one visual line
                                        # so a wrap is never mistaken for a
                                        # line break. Long ones scroll.
                                        wrap_mode=Gtk.WrapMode.NONE,
                                        # The box starts at the note's text
                                        # margin, so its text sits CODE_PAD in.
                                        left_margin=TEXT_MARGIN + CODE_PAD,
                                        right_margin=CODE_PAD)
        # The box behind inline code is drawn by _draw_inline_code(), since a
        # text tag cannot have an outline.
        self._backtick_tag = buf.create_tag(
            'backtick', family=CODE_FONT, foreground=CODE_TEXT_COLOR,
            rise=INLINE_CODE_RISE * Pango.SCALE)
        # Derived from the text like dividers, so none of these are saved.
        # The first and last line of a code block keep the room around the
        # block.
        # The anchor of an empty code line is no text, and is hidden so that
        # GTK leaves it out of what it copies and drags, as it does the
        # selection that middle click pastes. It has no width to lose.
        self._anchor_tag = buf.create_tag('code-anchor', invisible=True)
        self._code_top_tag = buf.create_tag('code-top')
        self._code_bottom_tag = buf.create_tag('code-bottom')
        # The padding of inline code is a space at each end of it, in the
        # body's font at its size. A smaller space would be as wide as wanted,
        # but the cursor beside it would be as small. See _pad_kind().
        self._pad_tag = buf.create_tag('inline-pad', family=BODY_FONT,
                                       scale=1.0)
        # Derived too: the rows of a table. A row stays on one line, its first
        # cell starts inside the table's line and padding, and the room above
        # and below it is set by _refresh_code_spacing(). The first and last
        # row also keep the room around the table, so they are made after the
        # row tag, to win over it. The tab stops that line up the columns
        # differ from table to table: see _apply_tables().
        self._table_row_tag = buf.create_tag(
            'table-row', wrap_mode=Gtk.WrapMode.NONE,
            left_margin=TEXT_MARGIN + 1 + TABLE_PAD)
        self._table_top_tag = buf.create_tag('table-top')
        self._table_bottom_tag = buf.create_tag('table-bottom')
        self._table_head_tag = buf.create_tag('table-head',
                                              weight=Pango.Weight.BOLD)
        self._table_tab_tags = []
        # (first line, last line, x of each column's left line and of the
        # right edge) of each table, in buffer coordinates.
        self._tables = []
        # Derived too: an expand. What a folded one hides, and the mark that
        # ends it, are invisible. Its triangle's characters are not seen, as
        # _draw_sections() draws a chevron over them, and its title is small
        # and gray. The end line of an open one is kept, set very small, as
        # the room at the bottom of its box. The margins that put its title
        # and content inside its box depend on how deep it is in other
        # expands, so there is a tag for each depth. See _apply_sections().
        self._fold_tag = buf.create_tag('fold', invisible=True)
        self._expand_marker_tag = buf.create_tag(
            'expand-marker', foreground_rgba=Gdk.RGBA(0, 0, 0, 0),
            scale=EXPAND_TITLE_SCALE)
        self._expand_title_tag = buf.create_tag(
            'expand-title', foreground_rgba=Gdk.RGBA(0, 0, 0, 0.6),
            scale=EXPAND_TITLE_SCALE)
        self._expand_end_tag = buf.create_tag('expand-end', scale=0.1)
        self._expand_depth_tags = {}
        self._sections = []
        self._hidden_lines = set()
        self._line_depth = {}
        self._expand_boxes = []
        self._skip_lines = set()
        # Derived too: the spacing of a line, in a note whose lines differ in
        # height. One tag for each pair of spacings. See _even_lines().
        self._slot_tags = {}
        # The characters of a list marker are there for the text, and are not
        # seen: bullets and boxes are drawn over them, by _draw_list_markers().
        # Derived from the text like dividers. Sized by _refresh_code_spacing()
        # to take the room the drawing needs and to fit in the line.
        transparent = Gdk.RGBA(0, 0, 0, 0)
        self._marker_tags = {
            marker[0]: buf.create_tag(f'marker-{ord(marker[0]):x}',
                                      foreground_rgba=transparent)
            for marker in LIST_MARKERS}
        self._refresh_code_spacing()
        self._heading_tag = buf.create_tag(
            'heading', family=HEADING_FONT, weight=Pango.Weight.BOLD,
            scale=HEADING_SCALE)
        self._emoji_tag = buf.create_tag('emoji', scale=self._emoji_scale())
        # A line that is exactly DIVIDER_TEXT is drawn as a horizontal rule:
        # the dashes are hidden and _draw_dividers() paints the line.
        self._divider_tag = buf.create_tag(
            'divider',
            foreground_rgba=Gdk.RGBA(0, 0, 0, 0),
            pixels_above_lines=4,
            pixels_below_lines=4)
        self._divider_lines = []
        # Derived from the text on every change, like dividers, so none is
        # saved: a checked item is grayed out, a quote is muted, and URLs are
        # links.
        self._done_tag = buf.create_tag(
            'done', foreground='#77775A')
        self._quote_tag = buf.create_tag(
            'quote', foreground_rgba=Gdk.RGBA(0, 0, 0, 0.62))
        # A quote's wrapped rows start where its text does, clear of the bar.
        # Its margins are set from the marker's width by
        # _refresh_code_spacing(). Only for a quote that is not indented:
        # tab stops count from the margin, so an indented one would move.
        self._quote_hang_tag = buf.create_tag('quote-hang')
        self._refresh_quote_hang()
        self._link_tag = buf.create_tag(
            # Below the tails of the letters: the code font's own underline
            # runs through them.
            'link', foreground='#1A55B0', underline=Pango.Underline.LOW)
        self._cursor_offset = 0
        self._leaving_marker = False
        buf.connect('mark-set', self._on_mark_set)
        self._watch_code_blocks(buf)
        self._hl_tag.set_priority(buf.get_tag_table().get_size() - 1)
        self._refresh_emoji_tags()
        for s, e in data.get('bold_ranges', []):
            buf.apply_tag(self._bold_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        for s, e in data.get('heading_ranges', []):
            buf.apply_tag(self._heading_tag,
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
        self._strip_marker_formats()
        # Notes from before inline code had spaces for padding, and from
        # before list items were indented by tabs.
        pads_changed = self._normalize_code_pads()
        pads_changed = self._normalize_tables() or pads_changed
        pads_changed = self._normalize_sections() or pads_changed
        if self._tab_list_indents() or pads_changed:
            self._history[0] = self._current_state()
        self._refresh_line_styles()
        # Before the default handler, so the code boxes sit under the text.
        self.tv.connect('draw', self._draw_code_blocks)
        self.tv.connect_after('draw', self._draw_dividers)
        self.tv.connect_after('draw', self._draw_list_markers)
        self.tv.connect_after('draw', self._draw_sections)
        self.tv.connect('populate-popup', self._on_tv_popup)
        self.tv.connect('key-press-event', self._on_tv_key_press)
        self.tv.connect('button-press-event', self._on_tv_button_press)
        self.tv.add_events(Gdk.EventMask.POINTER_MOTION_MASK)
        self.tv.connect('motion-notify-event', self._on_tv_motion)
        self.tv.add_events(Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.tv.connect('leave-notify-event', self._on_tv_leave)
        self.tv.set_has_tooltip(True)
        self.tv.connect('query-tooltip', self._on_tv_query_tooltip)
        self.tv.connect('copy-clipboard', self._on_copy_clipboard)
        self.tv.connect('cut-clipboard', self._on_cut_clipboard)
        self.tv.connect('paste-clipboard', self._on_paste_clipboard)

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
                      lambda *_: self._toggle_bold() or True)
        accel.connect(Gdk.KEY_h, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_heading() or True)
        accel.connect(Gdk.KEY_e, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_inline_code() or True)
        accel.connect(Gdk.KEY_8, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_bullet() or True)
        accel.connect(Gdk.KEY_KP_8, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_bullet() or True)
        accel.connect(Gdk.KEY_9, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_checklist() or True)
        accel.connect(Gdk.KEY_KP_9, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._toggle_checklist() or True)
        accel.connect(Gdk.KEY_c,
                      Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
                      0, lambda *_: self._toggle_code_block() or True)
        accel.connect(Gdk.KEY_z, Gdk.ModifierType.CONTROL_MASK, 0,
                      lambda *_: self._undo() or True)
        accel.connect(Gdk.KEY_z,
                      Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK,
                      0, lambda *_: self._redo() or True)

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
        # Child anchors read as IMAGE_ANCHOR in the buffer text, so find them
        # with a string search instead of stepping through every character.
        buf = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        images = []
        offset = text.find(IMAGE_ANCHOR)
        while offset != -1:
            anchor = buf.get_iter_at_offset(offset).get_child_anchor()
            if anchor is not None and hasattr(anchor, 'ynote_image'):
                meta = self._normalize_image_meta(anchor.ynote_image)
                meta['offset'] = offset
                images.append(meta)
            offset = text.find(IMAGE_ANCHOR, offset + 1)
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
        return self._rich_state(start.get_offset(), end.get_offset())

    def _rich_state(self, start_offset, end_offset):
        """The text between two offsets with its formats and images, as the
        clipboard holds it."""
        buf = self.tv.get_buffer()
        start = buf.get_iter_at_offset(start_offset)
        end = buf.get_iter_at_offset(end_offset)
        return {
            'text': buf.get_slice(start, end, True),
            'bold': self._get_tag_ranges_between(
                self._bold_tag, start_offset, end_offset),
            'heading': self._get_tag_ranges_between(
                self._heading_tag, start_offset, end_offset),
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

        # Other apps get Markdown, but code alone goes as it is, so a command
        # can be pasted into a terminal. Notes still get the formats exactly.
        text = None if is_all_code(state) else to_markdown(state)
        self.app.set_rich_clipboard(state, text)
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

            self._refresh_line_styles()
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

        for rel_start, rel_end in state.get('heading', []):
            buf.apply_tag(
                self._heading_tag,
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

        self._strip_marker_formats()
        self._normalize_code_pads()
        self._normalize_tables()
        self._normalize_sections()
        self._refresh_line_styles()
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
                or self._paste_plain_text_into_code_selection()
                or self._paste_markdown_if_any()):
            tv.stop_emission_by_name('paste-clipboard')

    def _paste_plain_text(self):
        """Paste the clipboard's text as it is: no Markdown is read, and no
        backticks become inline code."""
        state = self.app.rich_clipboard_state()
        if state:
            # Copied from a note: the clipboard holds it as Markdown, so the
            # note's own text is pasted instead.
            text = state.get('text', '')
            for char in (CODE_ANCHOR, CODE_PAD_CHAR, IMAGE_ANCHOR,
                         TABLE_MARKER, EXPAND_END):
                text = text.replace(char, '')
        else:
            text = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        if not text:
            return
        text = self._fit_text_to_cell(text)
        buf = self.tv.get_buffer()
        self._flush_snapshot()
        self._paste_plain = True
        try:
            buf.delete_selection(True, True)
            buf.insert_at_cursor(text)
        finally:
            self._paste_plain = False
        self._flush_snapshot()
        self._queue_save()

    def _fit_text_to_cell(self, text):
        """Text pasted into a table cell, which holds one line: its lines
        joined by spaces."""
        buf = self.tv.get_buffer()
        bounds = buf.get_selection_bounds()
        at = bounds[0] if bounds else buf.get_iter_at_mark(buf.get_insert())
        if '\n' not in text or not self._is_table_row(at.get_line()):
            return text
        return ' '.join(part.strip() for part in text.splitlines()
                        if part.strip())

    def _paste_markdown_if_any(self):
        """Paste text from another app with the formats its Markdown gives,
        unless it goes into code, which takes text as it is."""
        buf = self.tv.get_buffer()
        bounds = buf.get_selection_bounds()
        at = bounds[0] if bounds else buf.get_iter_at_mark(buf.get_insert())
        before_at = at.copy()
        if (self._is_code_line(buf, at.get_line())
                or (at.has_tag(self._backtick_tag) and before_at.backward_char()
                    and before_at.has_tag(self._backtick_tag))):
            return False
        text = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text()
        if not text:
            return False
        state = from_markdown(text)
        fitted = (text if TABLE_MARKER in state['text']
                  else self._fit_text_to_cell(text))
        if fitted != text:
            # Lines pasted into a cell become one line, which keeps its bold
            # and inline code but is no heading or code block.
            state = dict(from_markdown(fitted), heading=[], code=[])
        elif state['text'] == text and not any(
                state[key] for key in ('bold', 'heading', 'code', 'backtick')):
            return False

        end = bounds[1] if bounds else at
        line_start = at.copy()
        line_start.set_line_offset(0)
        line_end = end.copy()
        if not line_end.ends_line():
            line_end.forward_to_line_end()
        state = fit_between(state, buf.get_text(line_start, at, True),
                            buf.get_text(end, line_end, True))
        self._flush_snapshot()
        self._insert_rich_state_at_cursor(state)
        return True

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
        self._clear_highlights()
        # The expands a match showed open fold again.
        self._refresh_line_styles()
        self.tv.grab_focus()

    def _do_search(self):
        self._clear_highlights()
        query = self._search_entry.get_text()
        if not query:
            self._refresh_results(query)
            self._refresh_line_styles()
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
        self._refresh_results(query)
        # Matches in a folded expand show it open.
        self._refresh_line_styles()

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
        buf = self.tv.get_buffer()
        return buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)

    def show_match(self, start, end):
        # Select the match and scroll to it once the window has its size.
        self._expand()
        self._open_sections_around(start)
        buf = self.tv.get_buffer()
        buf.select_range(buf.get_iter_at_offset(start), buf.get_iter_at_offset(end))
        self.tv.grab_focus()
        GLib.idle_add(lambda: self.tv.scroll_to_mark(
            buf.get_insert(), 0.1, False, 0, 0) and False)

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
        if self._restoring or self._normalizing:
            return
        self._pending_format_inserts.append(
            (self._bold_active, self._code_active, self._heading_active,
             self._iter_has_tag_context(location, self._code_tag)))

    def _after_buf_insert_text(self, buf, location, text, length):
        if self._restoring or self._normalizing:
            return
        bold, inline_code, heading, apply_code = (
            self._pending_format_inserts.pop(0)
            if self._pending_format_inserts else (False, False, False, False))
        if not text:
            return

        end = location.copy()
        start = end.copy()
        start.backward_chars(len(text))
        # Enter starts the new line with every format off, as in Slack. Other
        # text takes the formats that are on. A paste of several lines is not
        # one heading.
        new_line = text.startswith('\n')
        # Text typed inside bold or inline code takes that format from the
        # text around it. With the format turned off, it does not.
        if not bold:
            buf.remove_tag(self._bold_tag, start, end)
        if not inline_code:
            buf.remove_tag(self._backtick_tag, start, end)
        self._clear_line_breaks(start, text)
        if not new_line:
            if bold and not heading:
                self._apply_tag_to_non_newline_chars(
                    buf, self._bold_tag, start, end)
            if inline_code:
                self._apply_tag_to_non_newline_chars(
                    buf, self._backtick_tag, start, end)
            if heading and '\n' not in text:
                self._tag_text(self._heading_tag, start, end)
        if apply_code and text != '\n':
            for line in range(start.get_line(), end.get_line() + 1):
                self._tag_code_line(line)
            self._remove_redundant_code_anchors(start.get_line(), end.get_line())
        if not self._paste_plain and (
                (text == '`' and self._typed_code_fence(buf))
                or (text == '*' and self._typed_bold(buf))):
            return
        if '`' in text and not self._paste_plain:
            self._format_backtick_wrapped_text()
        self._refresh_emoji_tags()
        if new_line:
            self._bold_active = self._code_active = False
            self._heading_active = False
            self._refresh_format_buttons()

    def _clear_line_breaks(self, start, text):
        """Take the formats off the line breaks of `text`, inserted at `start`.
        A line break takes them from the text around it, as any text does, but
        it is not text; see _text_segments()."""
        buf = self.tv.get_buffer()
        first = start.get_offset()
        for index, char in enumerate(text):
            if char != '\n':
                continue
            low = buf.get_iter_at_offset(first + index)
            high = low.copy()
            high.forward_char()
            for tag in (self._bold_tag, self._heading_tag, self._backtick_tag):
                buf.remove_tag(tag, low, high)

    def _apply_tag_to_non_newline_chars(self, buf, tag, start, end,
                                        skip_markers=True):
        """Tag the text from start to end except newlines and list markers."""
        if skip_markers:
            spans = [(buf.get_iter_at_offset(s), buf.get_iter_at_offset(e))
                     for s, e in self._text_segments(start.get_offset(),
                                                     end.get_offset())]
        else:
            spans = [(start, end)]
        for span_start, span_end in spans:
            it = span_start.copy()
            range_start = None
            while it.compare(span_end) < 0:
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
                buf.apply_tag(tag, range_start, span_end)

    # ------------------------------------------------------------------ list markers
    # A bullet or a to-do box is not text to the user, only the mark of a line.
    # It is characters in the note, so everything that would treat it as text
    # steps around it: the cursor and a selection never end inside one, a
    # format never covers one, and Backspace removes the whole mark.

    def _marker_end(self, line):
        """Offset where the list marker of `line` ends, or None.

        A line of a code block has none: a bullet in code is code. A row of a
        table has the invisible TABLE_MARKER, which is treated the same."""
        buf = self.tv.get_buffer()
        if line < 0 or line >= buf.get_line_count():
            return None
        if self._is_table_row(line):
            return buf.get_iter_at_line(line).get_offset() + len(TABLE_MARKER)
        if self._is_section_title(line):
            return buf.get_iter_at_line(line).get_offset() + len(EXPAND_OPEN)
        parts = self._line_list_parts(line)
        if parts is None or self._is_code_line(buf, line):
            return None
        return (buf.get_iter_at_line(line).get_offset()
                + len(parts[0]) + len(parts[1]))

    def _text_segments(self, start, end):
        """The (start, end) offsets of the text between two offsets, with the
        list marker of each line, the indent before it, and the line break
        after it left out. A line break is not text: a format on one reaches
        into the next line, such as to the indent of an item, and moves it."""
        buf = self.tv.get_buffer()
        first = buf.get_iter_at_offset(start).get_line()
        last = buf.get_iter_at_offset(end).get_line()
        count = buf.get_line_count()
        segments = []
        for line in range(first, last + 1):
            line_start = buf.get_iter_at_line(line).get_offset()
            line_end = (buf.get_iter_at_line(line + 1).get_offset() - 1
                        if line + 1 < count else buf.get_char_count())
            low = max(start, self._marker_end(line) or line_start)
            high = min(end, line_end)
            if low < high:
                segments.append((low, high))
        return segments

    def _tag_text(self, tag, start, end, remove=False):
        """Apply tag to the text from start to end, or take it off, leaving the
        list markers alone."""
        buf = self.tv.get_buffer()
        for low, high in self._text_segments(start.get_offset(),
                                             end.get_offset()):
            first, last = (buf.get_iter_at_offset(low),
                           buf.get_iter_at_offset(high))
            if remove:
                buf.remove_tag(tag, first, last)
            else:
                buf.apply_tag(tag, first, last)

    def _strip_marker_formats(self):
        """Take the formats off the parts of a note that are not text: the
        list markers, and the line breaks. A note can have them from before a
        marker could not be formatted, or from a format over several lines."""
        buf = self.tv.get_buffer()
        count = buf.get_line_count()
        for line in range(count):
            marker_end = self._marker_end(line)
            if marker_end is not None:
                first = buf.get_iter_at_line(line)
                last = buf.get_iter_at_offset(marker_end)
                for tag in (self._bold_tag, self._heading_tag,
                            self._backtick_tag, self._code_tag):
                    buf.remove_tag(tag, first, last)
            if line + 1 < count:
                # The line break, which a line of code does not have either:
                # its box is drawn from the lines, not from the break.
                last = buf.get_iter_at_line(line + 1)
                first = last.copy()
                first.backward_char()
                for tag in (self._bold_tag, self._heading_tag,
                            self._backtick_tag):
                    buf.remove_tag(tag, first, last)

    def _keep_out_of_marker(self, buf, it, mark, previous):
        if self._leaving_marker:
            # The start of the line, where _leave_marker() put a selection end.
            return
        marker_end = self._marker_end(it.get_line())
        if marker_end is not None and it.get_offset() < marker_end:
            event = Gtk.get_current_event()
            keyboard = (event is not None
                        and event.type == Gdk.EventType.KEY_PRESS)
            # Once GTK has finished moving it, as for a divider.
            GLib.idle_add(self._leave_marker, mark.get_name(), previous,
                          keyboard, priority=GLib.PRIORITY_HIGH_IDLE)

    def _leave_marker(self, name, previous, keyboard=False):
        """Move the cursor, or an end of a selection, out of a marker.

        The cursor goes to the end of the marker, or, when Left took it back
        from the start of the item, to the end of the line before. Home there
        leaves it where it was. An end of a
        selection takes the marker whole or leaves it out, never part of it:
        selecting left from the start of an item takes the marker, the next
        step left the line break, and the way back the same steps in reverse.
        A mouse selection takes the marker it reaches over."""
        buf = self.tv.get_buffer()
        mark = buf.get_mark(name)
        if mark is None:
            return False
        it = buf.get_iter_at_mark(mark)
        offset = it.get_offset()
        marker_end = self._marker_end(it.get_line())
        if marker_end is None or offset >= marker_end:
            return False
        line = it.get_line()
        line_start = buf.get_iter_at_line(line).get_offset()
        other = buf.get_selection_bound() if name == 'insert' else buf.get_insert()
        anchor = buf.get_iter_at_mark(other).get_offset()
        if anchor == offset:
            # No selection: both ends move, so one does not appear.
            if (keyboard and previous == marker_end
                    and offset == marker_end - 1 and line > 0):
                buf.place_cursor(self._line_bounds(line - 1)[1])
            else:
                buf.place_cursor(buf.get_iter_at_offset(marker_end))
            return False
        if keyboard:
            take = (previous == marker_end
                    or (previous is not None and previous < line_start
                        and offset == line_start))
        else:
            take = anchor >= marker_end
        target = line_start if take else marker_end
        if target != offset:
            self._leaving_marker = True
            try:
                buf.move_mark(mark, buf.get_iter_at_offset(target))
            finally:
                self._leaving_marker = False
        return False

    def _on_buf_changed(self, buf):
        if self._restoring:
            return
        if not self._normalizing:
            self._queue_pad_normalization()
        self._refresh_line_styles()
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
                and last.get('heading', []) == state['heading']
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
            'heading': self._get_tag_ranges(self._heading_tag),
            'code': self._get_tag_ranges(self._code_tag),
            'backtick': self._get_tag_ranges(self._backtick_tag),
            'images': self._get_images_state(),
        }

    def _restore_state(self, state):
        self._restoring = True
        self._remove_all_image_widgets()
        buf = self.tv.get_buffer()
        old_text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        old_cursor = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        scroll = self._sw.get_vadjustment().get_value()
        buf.set_text(state['text'])
        buf.remove_tag(self._bold_tag, buf.get_start_iter(), buf.get_end_iter())
        buf.remove_tag(
            self._heading_tag, buf.get_start_iter(), buf.get_end_iter())
        buf.remove_tag(self._code_tag, buf.get_start_iter(), buf.get_end_iter())
        buf.remove_tag(
            self._backtick_tag, buf.get_start_iter(), buf.get_end_iter())
        for s, e in state.get('bold', []):
            buf.apply_tag(self._bold_tag,
                          buf.get_iter_at_offset(s),
                          buf.get_iter_at_offset(e))
        for s, e in state.get('heading', []):
            buf.apply_tag(self._heading_tag,
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
        self._strip_marker_formats()
        self._normalize_code_pads()
        self._refresh_emoji_tags()
        self._refresh_line_styles()
        self._restoring = False
        # Setting the text moved the cursor to the end and the view with it.
        # Put the cursor where the edit was, and the view back where it was,
        # moving it only if the cursor is off screen.
        new_text = state['text']
        offset = (old_cursor if old_text == new_text
                  else changed_end(old_text, new_text))
        buf.place_cursor(buf.get_iter_at_offset(min(offset, len(new_text))))
        GLib.idle_add(self._restore_scroll, scroll,
                      priority=GLib.PRIORITY_LOW)
        self._sync_format_state()
        self._queue_save()

    def _restore_scroll(self, scroll):
        # After the view has laid out the new text, which changes its height.
        adj = self._sw.get_vadjustment()
        adj.set_value(min(scroll, max(0, adj.get_upper() - adj.get_page_size())))
        buf = self.tv.get_buffer()
        self.tv.scroll_to_mark(buf.get_insert(), 0.05, False, 0, 0)
        return False

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

    def _iter_at_pointer(self, x, y, window=Gtk.TextWindowType.TEXT):
        """The character under the pointer, or None past the end of a line."""
        bx, by = self.tv.window_to_buffer_coords(window, int(x), int(y))
        over, it = self.tv.get_iter_at_location(bx, by)
        if not over or it.ends_line():
            return None
        return it

    def _checkbox_bounds(self, line):
        """Iters around a to-do's box and the space after it, or None."""
        parts = self._line_list_parts(line)
        if parts is None or parts[1] not in CHECK_MARKERS:
            return None
        box = self.tv.get_buffer().get_iter_at_line(line)
        box.forward_chars(len(parts[0]))
        after = box.copy()
        after.forward_chars(len(parts[1]))
        return box, after

    def _checkbox_line_at(self, x, y, window=Gtk.TextWindowType.TEXT):
        """The line of the to-do box under the pointer, or None.

        The box is a single character, so the target also takes in the space
        after it and a margin around it, like a check button's label.
        """
        bx, by = self.tv.window_to_buffer_coords(window, int(x), int(y))
        line_start, _ = self.tv.get_line_at_y(by)
        bounds = self._checkbox_bounds(line_start.get_line())
        if bounds is None:
            return None
        box = self.tv.get_iter_location(bounds[0])
        body = self.tv.get_iter_location(bounds[1])
        pad = CHECKBOX_HIT_MARGIN
        if (box.x - pad <= bx < body.x
                and box.y - pad <= by < box.y + box.height + pad):
            return line_start.get_line()
        return None

    def _link_at(self, it):
        """The URL of the link under it, or None."""
        if it is None or not it.has_tag(self._link_tag):
            return None
        start, end = it.copy(), it.copy()
        if not start.starts_tag(self._link_tag):
            start.backward_to_tag_toggle(self._link_tag)
        end.forward_to_tag_toggle(self._link_tag)
        return start.get_text(end)

    def _on_tv_motion(self, tv, event):
        it = self._iter_at_pointer(event.x, event.y)
        ctrl = event.state & Gdk.ModifierType.CONTROL_MASK
        hover = self._expand_button_at(event.x, event.y)
        if hover != self._expand_hover:
            self._expand_hover = hover
            tv.queue_draw()
        clickable = (hover is not None
                     or self._checkbox_line_at(event.x, event.y) is not None
                     or (ctrl and self._link_at(it) is not None))
        window = tv.get_window(Gtk.TextWindowType.TEXT)
        if window is not None:
            window.set_cursor(Gdk.Cursor.new_from_name(
                tv.get_display(), 'pointer' if clickable else 'text'))
        return False

    def _on_tv_query_tooltip(self, tv, x, y, keyboard_mode, tooltip):
        if keyboard_mode:
            return False
        url = self._link_at(self._iter_at_pointer(x, y, Gtk.TextWindowType.WIDGET))
        if url is None:
            return False
        tooltip.set_text(f'Ctrl+click to open {url}')
        return True

    def _on_tv_button_press(self, tv, event):
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 1:
            return self._on_tv_single_click(event)
        if (event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3
                and not tv.get_buffer().get_has_selection()):
            # The table items of the menu act on the cell right-clicked.
            self._click_table_cell(event, move_only=True)
            return False
        # In a code block, a double click selects the clicked line, which is
        # usually one command, and a triple click selects the whole block.
        multi = (Gdk.EventType.DOUBLE_BUTTON_PRESS, Gdk.EventType.TRIPLE_BUTTON_PRESS)
        if event.type not in multi or event.button != 1:
            return False
        buf = tv.get_buffer()
        x, y = tv.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, int(event.x), int(event.y))
        _, it = tv.get_iter_at_location(x, y)
        if not self._iter_has_tag_context(it, self._code_tag):
            return False
        clicked_line = it.get_line()
        if event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            # Leave out the newline, so pasting into a terminal does not run
            # the command right away.
            buf.select_range(*self._line_bounds(clicked_line))
            return True
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

    def _on_tv_single_click(self, event):
        # A click on a checkbox checks it without moving the cursor. Ctrl+click
        # opens a link, since a plain click must still place the cursor in it.
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        it = self._iter_at_pointer(event.x, event.y)
        if state == 0:
            if self._click_section_marker(event):
                return True
            line = self._checkbox_line_at(event.x, event.y)
            if line is None:
                return self._click_table_cell(event)
            self._toggle_checked([line])
            return True
        if state == Gdk.ModifierType.CONTROL_MASK:
            url = self._link_at(it)
            if url is None:
                return False
            self.app.open_uri(url)
            return True
        return False

    def _on_tv_key_press(self, tv, event):
        handled = self._handle_tv_key(tv, event)
        if handled:
            # GTK keeps the cursor in view after the keys it handles, not
            # after the edits made here, such as Enter starting the next list
            # item. The view follows once the new text is laid out.
            tv.scroll_mark_onscreen(tv.get_buffer().get_insert())
        return handled

    def _handle_tv_key(self, tv, event):
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        if (state == Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
                and Gdk.keyval_to_lower(event.keyval) == Gdk.KEY_v):
            self._paste_plain_text()
            return True
        if (state == Gdk.ModifierType.CONTROL_MASK
                and Gdk.keyval_to_lower(event.keyval) == Gdk.KEY_v):
            if self._paste_rich_clipboard_if_available():
                return True
            if self._paste_image_if_available():
                return True
            return False

        buf = tv.get_buffer()
        if self._on_table_key(buf, event.keyval, state):
            return True
        if self._on_section_key(buf, event.keyval, state):
            return True
        if (state == Gdk.ModifierType.CONTROL_MASK
                and event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)):
            # Ctrl+Enter checks or unchecks the to-dos on the selected lines.
            first_line, last_line = self._selected_or_cursor_lines()
            lines = [ln for ln in range(first_line, last_line + 1)
                     if self._line_list_marker(ln) in CHECK_MARKERS]
            if lines:
                self._toggle_checked(lines)
            return True

        # Tab and Shift+Tab over a selection indent or outdent the list items
        # on the selected lines, and leave the other lines as they are.
        if (buf.get_has_selection()
                and event.keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab)
                and state in (0, Gdk.ModifierType.SHIFT_MASK)):
            first_line, last_line = self._selected_or_cursor_lines()
            lines = [ln for ln in range(first_line, last_line + 1)
                     if self._marker_end(ln) is not None
                     and not self._is_table_row(ln)]
            if lines:
                self._flush_snapshot()
                for line in lines:
                    if state == 0:
                        self._indent_bullet_line(line)
                    else:
                        self._outdent_bullet_line(line)
                self._flush_snapshot()
                self._queue_save()
                return True

        if buf.get_has_selection():
            return False
        cursor = buf.get_iter_at_mark(buf.get_insert())
        cursor_line = cursor.get_line()

        if state == 0 and event.keyval == Gdk.KEY_space:
            line_start = buf.get_iter_at_line(cursor_line)
            before = buf.get_text(line_start, cursor, True)
            indent_len = self._line_indent_len(before)
            marker = TYPED_MARKERS.get(before[indent_len:])
            if (marker is not None
                    and not self._iter_has_tag_context(cursor, self._code_tag)
                    and not self._iter_has_tag_context(
                        cursor, self._heading_tag)):
                self._start_list_from_typed(
                    cursor_line, indent_len, len(before) - indent_len, marker)
                return True
            if (before == '#'
                    and not self._iter_has_tag_context(cursor, self._code_tag)
                    and not self._iter_has_tag_context(
                        cursor, self._backtick_tag)):
                self._start_heading_from_typed(cursor_line)
                return True

        if (state == 0 and event.keyval == Gdk.KEY_Tab
                and self._line_has_list_marker(cursor_line)):
            self._indent_bullet_line(cursor_line)
            return True

        if (state == Gdk.ModifierType.SHIFT_MASK
                and event.keyval in (Gdk.KEY_Tab, Gdk.KEY_ISO_Left_Tab)
                and self._line_has_list_marker(cursor_line)):
            self._outdent_bullet_line(cursor_line)
            return True

        if state == 0 and event.keyval in (Gdk.KEY_BackSpace, Gdk.KEY_Delete):
            # A divider is removed as a whole, also by Backspace from the
            # start of the line below it.
            divider_line = cursor_line
            if (event.keyval == Gdk.KEY_BackSpace
                    and cursor.get_line_offset() == 0
                    and not self._line_is_divider(cursor_line)):
                divider_line = cursor_line - 1
            if divider_line >= 0 and self._line_is_divider(divider_line):
                self._remove_divider_line(divider_line)
                return True

        if (state == 0 and event.keyval in (Gdk.KEY_BackSpace, Gdk.KEY_Delete)
                and self._delete_around_pad(buf, event.keyval)):
            return True

        # Backspace at the start of a nested item, empty or not, outdents it
        # one level and keeps its marker.
        if (state == 0 and event.keyval == Gdk.KEY_BackSpace
                and cursor.get_offset() == self._marker_end(cursor_line)
                and self._line_list_parts(cursor_line)[0]):
            self._flush_snapshot()
            self._outdent_bullet_line(cursor_line)
            self._flush_snapshot()
            self._queue_save()
            return True

        if (state == 0 and event.keyval == Gdk.KEY_BackSpace
                and self._line_is_empty_list_item(cursor_line)):
            self._remove_empty_bullet_line(cursor_line)
            return True

        # Backspace at the start of an item takes off its marker, not a piece
        # of it, and Delete at the end of the line before an item joins it on
        # without leaving the marker in the middle of the line.
        if (state == 0 and event.keyval == Gdk.KEY_BackSpace
                and cursor.get_offset() == self._marker_end(cursor_line)):
            self._flush_snapshot()
            self._set_line_marker(cursor_line, None)
            self._flush_snapshot()
            self._queue_save()
            return True
        if (state == 0 and event.keyval == Gdk.KEY_Delete and cursor.ends_line()
                and self._marker_end(cursor_line + 1) is not None):
            self._set_line_marker(cursor_line + 1, None)

        if event.keyval not in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            return False

        if self._line_is_fully_tagged(self._code_tag, cursor.get_line()):
            line_start, line_end = self._line_bounds(cursor.get_line())
            line_text = buf.get_text(line_start, line_end, True)
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
        line_text = buf.get_text(line_start, line_end, True)
        parts = self._list_parts(line_text)
        if parts is None:
            return False
        indent, marker, body = parts
        if body.strip() == '':
            # Empty item: remove the current marker and stop the list.
            self._remove_empty_bullet_line(cursor_line)
            return True
        # The next item of a checklist starts unchecked.
        if marker == CHECKED_MARKER:
            marker = CHECKBOX_MARKER
        marker_len = len(indent) + len(marker)
        if cursor.get_line_offset() <= marker_len:
            insert_offset = line_start.get_offset()
            buf.insert(line_start, f'{indent}{marker}\n')
            buf.place_cursor(buf.get_iter_at_offset(insert_offset + marker_len))
            return True
        buf.insert_at_cursor(f'\n{indent}{marker}')
        return True

    # ------------------------------------------------------------------ dividers

    def _line_is_divider(self, line):
        buf = self.tv.get_buffer()
        if line >= buf.get_line_count():
            return False
        start, end = self._line_bounds(line)
        return (buf.get_text(start, end, True) == DIVIDER_TEXT
                and not start.has_tag(self._code_tag))

    def _refresh_line_styles(self):
        # Styles that follow from the text alone: dividers, checked to-dos,
        # quotes and links. They are worked out again after every change.
        buf = self.tv.get_buffer()
        start, end = buf.get_start_iter(), buf.get_end_iter()
        for tag in (self._divider_tag, self._done_tag, self._quote_tag,
                    self._quote_hang_tag, self._link_tag):
            buf.remove_tag(tag, start, end)
        self._divider_lines = [line for line in range(buf.get_line_count())
                               if self._line_is_divider(line)]
        for line in self._divider_lines:
            buf.apply_tag(self._divider_tag, *self._line_bounds(line))

        text = buf.get_slice(start, end, True)
        offset = 0
        for line in text.split('\n'):
            parts = self._list_parts(line)
            muted = {CHECKED_MARKER: self._done_tag,
                     QUOTE_MARKER: self._quote_tag}
            if parts is not None and parts[1] in muted:
                body = offset + len(parts[0]) + len(parts[1])
                buf.apply_tag(muted[parts[1]], buf.get_iter_at_offset(body),
                              buf.get_iter_at_offset(offset + len(line)))
            if parts is not None and parts[1] == QUOTE_MARKER and not parts[0]:
                buf.apply_tag(self._quote_hang_tag,
                              buf.get_iter_at_offset(offset),
                              buf.get_iter_at_offset(offset + len(line)))
            offset += len(line) + 1
        for link_start, link_end, _ in find_links(text):
            buf.apply_tag(self._link_tag, buf.get_iter_at_offset(link_start),
                          buf.get_iter_at_offset(link_end))
        self._apply_sections(buf)
        # The cursor rests on neither a divider nor the end of an expand.
        self._skip_lines = set(self._divider_lines) | {
            end for _title, end, _level in self._expand_boxes}
        self._queue_code_margins()
        self.tv.queue_draw()

    _margins_sid = None

    def _queue_code_margins(self):
        # A line typed into a code block, or text styled as code, gets its tag
        # after the buffer reports the change, so the room is worked out once
        # the edit is done, still before the next frame.
        if self._margins_sid is None:
            self._margins_sid = GLib.idle_add(
                self._apply_code_margins, priority=GLib.PRIORITY_HIGH_IDLE)

    def _apply_code_margins(self):
        self._margins_sid = None
        buf = self.tv.get_buffer()
        start, end = buf.get_start_iter(), buf.get_end_iter()
        for tag in (self._code_top_tag, self._code_bottom_tag,
                    self._pad_tag, *self._marker_tags.values(),
                    *self._slot_tags.values(), self._table_row_tag,
                    self._table_top_tag, self._table_bottom_tag,
                    self._table_head_tag, *self._table_tab_tags):
            buf.remove_tag(tag, start, end)
        self._tag_list_markers(buf)
        self._even_lines(buf)
        self._hide_code_anchors(buf)

        # The first and last line of each run of code lines.
        line, last_line = 0, buf.get_line_count()
        while line < last_line:
            if not self._is_code_line(buf, line):
                line += 1
                continue
            end = line
            while end + 1 < last_line and self._is_code_line(buf, end + 1):
                end += 1
            buf.apply_tag(self._code_top_tag, *self._line_bounds(line))
            buf.apply_tag(self._code_bottom_tag, *self._line_bounds(end))
            line = end + 1

        # The space at each end of an inline code range is its padding.
        for first, last in self._get_tag_ranges(self._backtick_tag):
            for offset in (first, last - 1):
                if self._pad_kind(buf, offset):
                    here = buf.get_iter_at_offset(offset)
                    after = here.copy()
                    after.forward_char()
                    buf.apply_tag(self._pad_tag, here, after)
        # After the padding of inline code, which a cell's width takes in.
        self._apply_tables(buf)
        return False

    def _hide_code_anchors(self, buf):
        buf.remove_tag(self._anchor_tag, buf.get_start_iter(),
                       buf.get_end_iter())
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        index = text.find(CODE_ANCHOR)
        while index >= 0:
            buf.apply_tag(self._anchor_tag, buf.get_iter_at_offset(index),
                          buf.get_iter_at_offset(index + 1))
            index = text.find(CODE_ANCHOR, index + 1)

    def _tag_list_markers(self, buf):
        for line in range(buf.get_line_count()):
            end = self._marker_end(line)
            parts = end is not None and self._line_list_parts(line)
            if parts:
                first = buf.get_iter_at_line(line)
                first.forward_chars(len(parts[0]))
                buf.apply_tag(self._marker_tags[parts[1][0]], first,
                              buf.get_iter_at_offset(end))

    def _draw_list_markers(self, tv, cr):
        """Draw the bullet, to-do box, or quote bar of each visible item.

        The characters are not seen, only taking the room. Over the text, so a
        selection does not hide them."""
        buf = tv.get_buffer()
        visible = tv.get_visible_rect()
        first = tv.get_line_at_y(visible.y)[0].get_line()
        last = tv.get_line_at_y(visible.y + visible.height)[0].get_line()
        size = self._font_size
        text = tv.get_style_context().get_color(Gtk.StateFlags.NORMAL)
        for line in range(first, last + 1):
            parts = (line not in self._hidden_lines
                     and self._marker_end(line) is not None
                     and self._line_list_parts(line))
            if not parts:
                continue
            start = buf.get_iter_at_line(line)
            start.forward_chars(len(parts[0]))
            top = tv.get_line_yrange(buf.get_iter_at_line(line))[0]
            x, y = tv.buffer_to_window_coords(
                Gtk.TextWindowType.WIDGET, tv.get_iter_location(start).x,
                top + self._baseline_offset)
            if parts[1] == QUOTE_MARKER:
                # A bar down the whole line, wrapped rows too, which meets
                # the bar of a quote line next to it.
                height = tv.get_line_yrange(buf.get_iter_at_line(line))[1]
                _, bar_top = tv.buffer_to_window_coords(
                    Gtk.TextWindowType.WIDGET, 0, top)
                cr.set_source_rgba(text.red, text.green, text.blue, 0.45)
                cr.rectangle(x + 1, bar_top, max(2, round(QUOTE_BAR * size)),
                             height)
                cr.fill()
                continue
            done = parts[1] == CHECKED_MARKER
            if done:
                cr.set_source_rgb(0x77 / 255, 0x77 / 255, 0x5A / 255)
            else:
                cr.set_source_rgba(text.red, text.green, text.blue, text.alpha)
            if parts[1] == BULLET_MARKER:
                diameter = BULLET_SIZE * size
                cr.arc(x + 1 + diameter / 2, y - self._x_height / 2,
                       diameter / 2, 0, 2 * math.pi)
                cr.fill()
            else:
                side = CHECKBOX_SIZE * size
                # The bottom edge is just under the baseline, so the box
                # stands on the line like a capital letter.
                box_x, box_y = x + 1.5, y + 1.5 - side
                cr.set_line_width(1.3)
                cr.new_sub_path()
                cr.arc(box_x + side - 2.5, box_y + 2, 2, -math.pi / 2, 0)
                cr.arc(box_x + side - 2.5, box_y + side - 2, 2, 0, math.pi / 2)
                cr.arc(box_x + 2, box_y + side - 2, 2, math.pi / 2, math.pi)
                cr.arc(box_x + 2, box_y + 2, 2, math.pi, 3 * math.pi / 2)
                cr.close_path()
                cr.stroke()
                if done:
                    cr.set_line_width(1.7)
                    cr.set_line_cap(cairo.LINE_CAP_ROUND)
                    cr.set_line_join(cairo.LINE_JOIN_ROUND)
                    cr.move_to(box_x + 0.24 * side, box_y + 0.54 * side)
                    cr.line_to(box_x + 0.43 * side, box_y + 0.74 * side)
                    cr.line_to(box_x + 0.78 * side, box_y + 0.26 * side)
                    cr.stroke()
        return False

    def _even_lines(self, buf):
        """Make every line of the note the same height. See even_slots().

        Only text beyond Latin can be drawn in another font, so a note without
        any is left alone. Every other line is measured, since a line without
        any of it can still be spaced to match."""
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        # Where the baseline is below the top of a line: the same in all.
        self._baseline_offset = self._body_metrics[0] + self._line_spacing[0]
        markers = ({marker[0] for marker in LIST_MARKERS}
                   | {TABLE_MARKER, EXPAND_OPEN[0], EXPAND_CLOSED[0], EXPAND_END})
        if text.isascii() or not any(
                ord(c) >= FIRST_NON_LATIN for c in set(text) - markers):
            return
        numbers, metrics, offsets = [], [], []
        offset = 0
        for number, line_text in enumerate(text.split('\n')):
            # Code, dividers, headings and tables are spaced on their own.
            if (line_text and number not in self._divider_lines
                    and not line_text.startswith(TABLE_MARKER)
                    and not is_section_title(line_text)
                    and line_text != EXPAND_END
                    and not self._is_code_line(buf, number)
                    and not buf.get_iter_at_offset(offset).has_tag(
                        self._heading_tag)):
                numbers.append(number)
                metrics.append(self._line_metrics(line_text))
                offsets.append((offset, offset + len(line_text)))
            offset += len(line_text) + 1
        slots = even_slots(metrics, self._body_metrics, self._line_spacing)
        self._baseline_offset = slot_ascent(
            metrics, self._body_metrics, self._line_spacing)
        for (first, last), slot in zip(offsets, slots):
            if slot != self._line_spacing:
                buf.apply_tag(self._slot_tag(slot),
                              buf.get_iter_at_offset(first),
                              buf.get_iter_at_offset(last))

    def _slot_tag(self, slot):
        tag = self._slot_tags.get(slot)
        if tag is None:
            above, below = slot
            # The rows of a wrapped line are as far apart as the lines are.
            tag = self.tv.get_buffer().create_tag(
                f'slot-{above}-{below}', pixels_above_lines=above,
                pixels_below_lines=below, pixels_inside_wrap=above + below)
            self._slot_tags[slot] = tag
        return tag

    def _line_metrics(self, line_text):
        """(ascent, descent) of the tallest font that draws line_text, in the
        whole pixels GTK makes a line of.

        Pango picks the font for each character, and for runs of them, so the
        line is laid out whole, in the note's font, as it is in the note: this
        is whichever fonts this computer falls back to, not ones chosen here,
        and a character measured alone could fall back to another one. Emoji
        are left out, since they are drawn large on purpose and keep their own
        line height, and so is a list marker, which is drawn over characters
        sized to fit in the line."""
        cached = self._line_cache.get(line_text)
        if cached is not None:
            return cached
        parts = self._list_parts(line_text)
        plain = ''.join(c for c in (parts[0] + parts[2] if parts else line_text)
                        if not self._is_emoji_char(c))
        # A line is as tall as the fonts that draw it and no more: one with
        # only Hangul in it has no Latin text, so the note's font does not
        # count. Nothing at all to measure is a line of the note's font.
        if plain:
            ascent, descent = self._line_extent(self._body_font, plain)
        else:
            ascent, descent = self._body_metrics
        if parts:
            # The marker is in the line too, in a font made to fit, and so is
            # the indent before it, which is in the note's font.
            marker = self._marker_metrics[parts[1][0]]
            ascent, descent = max(ascent, marker[0]), max(descent, marker[1])
        if len(self._line_cache) > 2000:
            self._line_cache.clear()
        self._line_cache[line_text] = (ascent, descent)
        return ascent, descent

    def _line_extent(self, font, text):
        """Ascent and descent of text in font, rounded as GTK rounds the
        height of a line: the baseline and the whole height to pixels."""
        layout = self.tv.create_pango_layout(text)
        layout.set_font_description(font)
        logical = layout.get_extents()[1]
        ascent = round(layout.get_baseline() / Pango.SCALE)
        return ascent, round(logical.height / Pango.SCALE) - ascent

    def _font_metrics(self, font, text='x'):
        """Ascent and descent of the font in pixels, not rounded, so that the
        boxes and the line spacing round the same value. Text the font lacks is
        drawn in whichever font Pango falls back to."""
        layout = self.tv.create_pango_layout(text)
        layout.set_font_description(font)
        logical = layout.get_extents()[1]
        baseline = layout.get_baseline()
        return ((baseline - logical.y) / Pango.SCALE,
                (logical.y + logical.height - baseline) / Pango.SCALE)

    def _is_code_line(self, buf, line):
        # Cheaper than _line_is_fully_tagged(): code is always applied to a
        # whole line, so the first and last characters tell.
        start = buf.get_iter_at_line(line)
        end = start.copy()
        if not end.ends_line():
            end.forward_to_line_end()
        if start.compare(end) == 0 or not start.has_tag(self._code_tag):
            return False
        end.backward_char()
        return end.has_tag(self._code_tag)

    # A block's edges and the width of its box are worked out when it is first
    # drawn and kept in self._code_blocks, since drawing happens on every scroll
    # and keystroke. An edit forgets only the blocks it touches.
    EXACT_CODE_BLOCK_LINES = 200
    WIDEST_CODE_LINES = 16

    def _watch_code_blocks(self, buf):
        # All of these run before the buffer changes, so the iterators they get
        # are still valid and the line numbers are the old ones. Reading the
        # iterator after the change fails once another handler has edited the
        # text, as the bullet and backtick formatting do.
        buf.connect('insert-text', self._on_code_blocks_insert)
        buf.connect('insert-child-anchor', self._on_code_blocks_anchor)
        buf.connect('delete-range', self._on_code_blocks_delete)
        buf.connect('apply-tag', self._on_code_blocks_tag)
        buf.connect('remove-tag', self._on_code_blocks_tag)

    def _on_code_blocks_insert(self, buf, where, text, _length):
        line = where.get_line()
        self._forget_code_blocks(line, line, text.count('\n'))

    def _on_code_blocks_anchor(self, buf, where, _anchor):
        self._forget_code_blocks(where.get_line(), where.get_line(), 0)

    def _on_code_blocks_delete(self, buf, start, end):
        first, last = start.get_line(), end.get_line()
        self._forget_code_blocks(first, last, first - last)

    def _on_code_blocks_tag(self, buf, tag, start, end):
        # Only tags that decide which lines are code or how wide a line is.
        # Dividers, links, and checked to-dos are re-applied over the whole
        # note after every change, and search highlighting comes and goes, yet
        # none of them moves anything.
        if tag in (self._code_tag, self._bold_tag, self._backtick_tag):
            self._forget_code_blocks(start.get_line(), end.get_line(), 0)
        if tag in (self._code_tag, self._backtick_tag):
            self._queue_code_margins()

    def _forget_code_blocks(self, first, last, delta):
        """An edit replaced lines `first` to `last` and moved the lines below by
        `delta`. Blocks it touches are measured again when next drawn, blocks
        below it move with their lines, and the rest are unchanged."""
        kept = []
        for block in self._code_blocks:
            if block[1] < first - 1:
                kept.append(block)
            elif block[0] > last + 1:
                block[0] += delta
                block[1] += delta
                kept.append(block)
        self._code_blocks[:] = kept

    def _code_block(self, tv, buf, line):
        """[first, last, right] of the code block holding the code line `line`.

        `right` is where the block's box ends, in buffer coordinates.
        """
        blocks = self._code_blocks
        at = bisect.bisect_right(blocks, line, key=lambda block: block[0])
        if at and blocks[at - 1][1] >= line:
            return blocks[at - 1]
        last_line = buf.get_line_count() - 1
        first = line
        while first > 0 and self._is_code_line(buf, first - 1):
            first -= 1
        last = line
        while last < last_line and self._is_code_line(buf, last + 1):
            last += 1
        block = [first, last, self._code_block_right(tv, buf, first, last)]
        blocks.insert(bisect.bisect_right(blocks, first,
                                          key=lambda b: b[0]), block)
        return block

    def _code_block_right(self, tv, buf, first, last):
        if last - first < self.EXACT_CODE_BLOCK_LINES:
            measured = range(first, last + 1)
        else:
            # A long block is mostly off screen, and measuring every line makes
            # GTK lay all of it out. Code is monospace, so the widest lines are
            # the longest ones: measure only those.
            start = buf.get_iter_at_line(first)
            lines = buf.get_slice(start, self._line_bounds(last)[1],
                                  True).split('\n')
            widest = heapq.nlargest(self.WIDEST_CODE_LINES, range(len(lines)),
                                    key=lambda n: cell_width(lines[n]))
            measured = [first + n for n in widest]
        right = tv.get_left_margin()
        for line in measured:
            it = buf.get_iter_at_line(line)
            if not it.ends_line():
                it.forward_to_line_end()
            right = max(right, tv.get_iter_location(it).x)
        return right

    def _draw_code_blocks(self, tv, cr):
        # Each run of code lines gets one box as wide as its longest line,
        # instead of the full width of the note.
        buf = tv.get_buffer()
        visible = tv.get_visible_rect()
        first = tv.get_line_at_y(visible.y)[0].get_line()
        last = tv.get_line_at_y(visible.y + visible.height)[0].get_line()
        left = tv.get_left_margin()
        pad = CODE_PAD
        if self._opacity < 1.0:
            self._draw_text_backing(tv, cr, buf, visible)
        self._draw_tables(tv, cr, buf, first, last)
        line = first
        while line <= last:
            # A folded section's code takes no room and has no box.
            if (line in self._hidden_lines
                    or not self._is_code_line(buf, line)):
                line += 1
                continue
            block_start, block_end, right = self._code_block(tv, buf, line)
            # Further in inside an expand.
            left = self._line_left(block_start)
            top, _ = tv.get_line_yrange(buf.get_iter_at_line(block_start))
            y, height = tv.get_line_yrange(buf.get_iter_at_line(block_end))
            wx, wy = tv.buffer_to_window_coords(
                Gtk.TextWindowType.WIDGET, left, top)
            outlined_box(cr, self._code_rgba, wx, wy + CODE_BLOCK_MARGIN,
                         right + pad - left,
                         y + height - top - 2 * CODE_BLOCK_MARGIN)
            line = block_end + 1
        self._draw_inline_code(tv, cr, buf, first, last)
        return False

    def _draw_inline_code(self, tv, cr, buf, first, last):
        # One box per display line of each inline code range, so a range that
        # wraps gets a box on every row it covers. The padding is the space at
        # each end of the range, so the box is where its characters are.
        tag = self._backtick_tag
        pad_y = CODE_PAD_Y + 1
        it = buf.get_iter_at_line(first)
        end = buf.get_iter_at_line(last)
        if not end.ends_line():
            end.forward_to_line_end()
        if not it.has_tag(tag) and not it.forward_to_tag_toggle(tag):
            return
        while it.compare(end) < 0:
            range_end = it.copy()
            if not range_end.forward_to_tag_toggle(tag):
                break
            self._draw_inline_part(tv, cr, buf, it, range_end, pad_y)
            it = range_end
            if not it.forward_to_tag_toggle(tag):
                break

    def _draw_inline_part(self, tv, cr, buf, start, stop, pad_y):
        if start.get_line() in self._hidden_lines:
            return
        row = start.copy()
        while row.compare(stop) < 0:
            # The start of the next display line. Its "line end" is the
            # last cursor position of a wrapped line, which is before its
            # last character, so it cannot bound the box.
            row_end = row.copy()
            if (not tv.forward_display_line(row_end)
                    or row_end.compare(row) <= 0
                    or row_end.compare(stop) > 0):
                row_end = stop.copy()
            tail = row_end.copy()
            tail.backward_char()
            if tail.get_char() == '\n':
                tail.backward_char()
            if tail.compare(row) >= 0:
                a, b = tv.get_iter_location(row), tv.get_iter_location(tail)
                # A character's rectangle is the line area of its own font,
                # raised with it. The spaces at the ends are smaller than the
                # rest, so the height is that of the other characters. One from
                # another font in the row, such as an emoji, widens the box.
                inner_first, inner_last = row.copy(), tail.copy()
                while (inner_first.compare(inner_last) < 0
                       and self._pad_kind(buf, inner_first.get_offset())):
                    inner_first.forward_char()
                while (inner_last.compare(inner_first) > 0
                       and self._pad_kind(buf, inner_last.get_offset())):
                    inner_last.backward_char()
                c, d = (tv.get_iter_location(inner_first),
                        tv.get_iter_location(inner_last))
                top = min(c.y, d.y)
                bottom = max(c.y + c.height, d.y + d.height)
                wx, wy = tv.buffer_to_window_coords(
                    Gtk.TextWindowType.WIDGET, a.x, top - pad_y)
                width = b.x + b.width - a.x
                # The box stops short of the spaces at its ends, which leaves
                # a gap from the text beside it.
                if self._pad_kind(buf, row.get_offset()) == 'lead':
                    wx, width = wx + CODE_GAP, width - CODE_GAP
                if self._pad_kind(buf, tail.get_offset()) == 'trail':
                    width -= CODE_GAP
                outlined_box(cr, self._inline_rgba, wx, wy, width,
                             bottom - top + 2 * pad_y)
            row = row_end

    def _draw_text_backing(self, tv, cr, buf, visible):
        # A see-through note would leave text unreadable over a dark desktop,
        # so each row that holds text gets an opaque strip in the note color
        # behind it. Only the visible rows are visited.
        body = self._body_rgba
        cr.set_source_rgba(body.red, body.green, body.blue, 1.0)
        left = tv.get_left_margin()
        pad = 4
        it = tv.get_line_at_y(visible.y)[0]
        bottom = visible.y + visible.height
        while True:
            start = tv.get_iter_location(it)
            if start.y > bottom:
                break
            end = it.copy()
            tv.forward_display_line_end(end)
            # A divider's text is hidden and its line is drawn across the
            # whole width, so it gets no strip.
            if end.compare(it) > 0 and it.get_line() not in self._divider_lines:
                right = tv.get_iter_location(end).x
                wx, wy = tv.buffer_to_window_coords(
                    Gtk.TextWindowType.WIDGET, left, start.y)
                cr.rectangle(wx, wy, right + pad - left, start.height)
                cr.fill()
            offset = it.get_offset()
            if not tv.forward_display_line(it) or it.get_offset() <= offset:
                break

    def _draw_dividers(self, tv, cr):
        if not self._divider_lines:
            return False
        buf = tv.get_buffer()
        left = tv.get_left_margin()
        right = tv.get_allocated_width() - tv.get_right_margin()
        cr.set_source_rgba(0, 0, 0, 0.3)
        cr.set_line_width(2)
        for line in self._divider_lines:
            if line in self._hidden_lines:
                continue
            y, height = tv.get_line_yrange(buf.get_iter_at_line(line))
            _, wy = tv.buffer_to_window_coords(
                Gtk.TextWindowType.WIDGET, 0, y + height // 2)
            # Inside an expand, inside its box.
            level = self._line_depth.get(line, 0)
            cr.move_to(left + level * self._expand_unit, wy)
            cr.line_to(right - level * EXPAND_PAD, wy)
        cr.stroke()
        return False

    def _on_mark_set(self, buf, it, mark):
        # The cursor never rests on a divider: it skips to the line after it
        # when moving forward and to the end of the line before it when moving
        # back. A divider at either end of the note keeps the cursor at its
        # outer edge instead. The jump runs once GTK has finished the current
        # cursor movement, since moving the cursor in the middle of it confuses
        # the text view.
        if mark is buf.get_selection_bound():
            self._keep_out_of_marker(buf, it, mark, None)
            self._sync_format_state()
        if mark is not buf.get_insert():
            return
        self._keep_out_of_marker(buf, it, mark, self._cursor_offset)
        self._sync_format_state()
        offset = it.get_offset()
        previous, self._cursor_offset = self._cursor_offset, offset
        # get_has_selection() has not caught up while the mark is being set.
        if not it.equal(buf.get_iter_at_mark(buf.get_selection_bound())):
            event = Gtk.get_current_event()
            keyboard = (event is not None
                        and event.type == Gdk.EventType.KEY_PRESS)
            GLib.idle_add(self._keep_pads_out_of_selection, previous, keyboard,
                          priority=GLib.PRIORITY_HIGH_IDLE)
        if not buf.get_has_selection() and it.get_line() in self._skip_lines:
            GLib.idle_add(self._skip_divider, offset, offset >= previous,
                          priority=GLib.PRIORITY_HIGH_IDLE)

    def _skip_divider(self, offset, forward):
        buf = self.tv.get_buffer()
        it = buf.get_iter_at_mark(buf.get_insert())
        if (it.get_offset() != offset or buf.get_has_selection()
                or it.get_line() not in self._skip_lines):
            return False
        line = it.get_line()
        start, end = self._line_bounds(line)
        if forward:
            if line + 1 < buf.get_line_count():
                target = buf.get_iter_at_line(line + 1)
            else:
                target = end
        elif line > 0:
            target = self._line_bounds(line - 1)[1]
        else:
            target = start
        if not target.equal(it):
            buf.place_cursor(target)
        return False

    def _remove_divider_line(self, line):
        buf = self.tv.get_buffer()
        start, end = self._line_bounds(line, include_newline=True)
        if end.is_end() and line > 0:
            # The last line has no newline of its own; take the one before it.
            start.backward_char()
        buf.delete(start, end)

    def _insert_divider(self):
        buf = self.tv.get_buffer()
        line = buf.get_iter_at_mark(buf.get_insert()).get_line()
        start, end = self._line_bounds(line)
        if buf.get_text(start, end, True).strip():
            buf.insert(end, '\n' + DIVIDER_TEXT)
            line += 1
        else:
            buf.delete(start, end)
            buf.insert(start, DIVIDER_TEXT)
        _, end = self._line_bounds(line)
        if end.is_end():
            buf.insert(end, '\n')
        buf.place_cursor(buf.get_iter_at_line(line + 1))

    # ------------------------------------------------------------------ tables
    # A row of a table is a line that starts with TABLE_MARKER, with its cells
    # separated by tabs, and the rows next to each other are one table whose
    # first row is its header. Like a list marker, the marker is text, so a
    # table is saved, undone, searched, and copied between notes as text.
    # Tab stops line up the columns and _draw_tables() draws the lines.

    def _is_table_row(self, line):
        buf = self.tv.get_buffer()
        if line < 0 or line >= buf.get_line_count():
            return False
        return (buf.get_iter_at_line(line).get_char() == TABLE_MARKER
                and not self._is_code_line(buf, line))

    def _table_runs(self, buf, lines):
        """[first, last] line of each table, given the note's lines."""
        runs = []
        for number, line in enumerate(lines):
            if (line.startswith(TABLE_MARKER)
                    and not self._is_code_line(buf, number)):
                if runs and runs[-1][1] == number - 1:
                    runs[-1][1] = number
                else:
                    runs.append([number, number])
        return runs

    def _table_bounds(self, line):
        """The first and last line of the table that holds the row `line`."""
        first = last = line
        while self._is_table_row(first - 1):
            first -= 1
        while self._is_table_row(last + 1):
            last += 1
        return first, last

    def _row_cells(self, line):
        """(start, end) offsets of the text of each cell of the row `line`."""
        buf = self.tv.get_buffer()
        start, end = self._line_bounds(line)
        text = buf.get_slice(start, end, True)
        offset = start.get_offset() + len(TABLE_MARKER)
        cells = []
        for cell in text[len(TABLE_MARKER):].split('\t'):
            cells.append((offset, offset + len(cell)))
            offset += len(cell) + 1
        return cells

    @staticmethod
    def _cell_index(cells, offset):
        """Which of the cells the offset is in. A cell ends where the tab
        after it is, which is still in it."""
        index = 0
        for number, (start, _end) in enumerate(cells):
            if start <= offset:
                index = number
        return index

    def _apply_tables(self, buf):
        """Tag the rows of every table and line up its columns: each column is
        as wide as its widest cell, and a tab stop starts each one."""
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        self._tables = []
        if TABLE_MARKER not in text:
            return
        lines = text.split('\n')
        min_width = TABLE_MIN_COLUMN * self._font_size
        for index, (first, last) in enumerate(self._table_runs(buf, lines)):
            left = self._line_left(first)
            columns = max(lines[n].count('\t') for n in range(first, last + 1))
            widths = [min_width] * (columns + 1)
            for line in range(first, last + 1):
                start, end = self._line_bounds(line)
                buf.apply_tag(self._table_row_tag, start, end)
                head = line == first
                if head:
                    after = start.copy()
                    after.forward_chars(len(TABLE_MARKER))
                    buf.apply_tag(self._table_head_tag, after, end)
                for column, (low, high) in enumerate(self._row_cells(line)):
                    widths[column] = max(widths[column],
                                         self._cell_text_width(buf, low, high,
                                                               head))
            buf.apply_tag(self._table_top_tag, *self._line_bounds(first))
            buf.apply_tag(self._table_bottom_tag, *self._line_bounds(last))
            # Where each column's line is, from the table's left edge. Its
            # text starts a pixel and the padding further in.
            edges = [0]
            for width in widths:
                edges.append(edges[-1] + width + 2 * TABLE_PAD + 1)
            tabs = self._table_tabs_tag(index, tuple(edges[1:-1]))
            # In from the table's left line, which is further in inside an
            # expand. The tag is made after the row tag, so it wins over it.
            tabs.set_property('left-margin', left + 1 + TABLE_PAD)
            buf.apply_tag(tabs, buf.get_iter_at_line(first),
                          self._line_bounds(last)[1])
            self._tables.append((first, last, [left + x for x in edges]))

    def _table_tabs_tag(self, index, stops):
        """The tag with the tab stops of the index-th table. Tab stops are
        relative to where a row's text starts."""
        buf = self.tv.get_buffer()
        while len(self._table_tab_tags) <= index:
            tag = buf.create_tag(f'table-tabs-{len(self._table_tab_tags)}')
            tag.ynote_stops = None
            self._table_tab_tags.append(tag)
        tag = self._table_tab_tags[index]
        if stops and tag.ynote_stops != stops:
            tabs = Pango.TabArray.new(len(stops), True)
            for number, stop in enumerate(stops):
                tabs.set_tab(number, Pango.TabAlign.LEFT, stop)
            tag.set_property('tabs', tabs)
            tag.ynote_stops = stops
        return tag

    def _cell_text_width(self, buf, start, end, head):
        """Width in pixels of the text from start to end, in the fonts its
        formats give it, and of the images in it, as they are shown."""
        if start >= end:
            return 0
        text = buf.get_slice(buf.get_iter_at_offset(start),
                             buf.get_iter_at_offset(end), True)
        attributes = Pango.AttrList()
        code_scale = self._code_tag.get_property('scale')
        emoji_scale = self._emoji_tag.get_property('scale')
        it = buf.get_iter_at_offset(start)
        index = 0
        measured = []
        images = 0
        for char in text:
            anchor = it.get_child_anchor()
            if anchor is not None:
                # An image is a widget in the text, as wide as it is drawn.
                images += max((widget.get_preferred_width()[1]
                               for widget in anchor.get_widgets()), default=0)
                it.forward_char()
                continue
            measured.append(char)
            size = len(char.encode())
            found = []
            if head or it.has_tag(self._bold_tag):
                found.append(Pango.attr_weight_new(Pango.Weight.BOLD))
            if it.has_tag(self._backtick_tag) and not it.has_tag(self._pad_tag):
                found += [Pango.attr_family_new(CODE_FONT),
                          Pango.attr_scale_new(code_scale)]
            elif self._is_emoji_char(char):
                found.append(Pango.attr_scale_new(emoji_scale))
            for attribute in found:
                attribute.start_index = index
                attribute.end_index = index + size
                attributes.insert(attribute)
            index += size
            it.forward_char()
        width = images
        if measured:
            layout = self.tv.create_pango_layout(''.join(measured))
            layout.set_font_description(self._body_font)
            layout.set_attributes(attributes)
            width += layout.get_extents()[1].width / Pango.SCALE
        return math.ceil(width)

    def _draw_tables(self, tv, cr, buf, first, last):
        """Draw the lines of each visible table, with its header shaded."""
        count = buf.get_line_count()
        dx, dy = tv.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, 0, 0)
        for table_first, table_last, edges in self._tables:
            if (table_last < first or table_first > last or table_last >= count
                    or table_first in self._hidden_lines):
                continue
            rows = [tv.get_line_yrange(buf.get_iter_at_line(line))
                    for line in range(table_first, table_last + 1)]
            ys = [y for y, _ in rows]
            ys[0] += TABLE_MARGIN
            ys.append(rows[-1][0] + rows[-1][1] - TABLE_MARGIN)
            ys = [y + dy for y in ys]
            xs = [x + dx for x in edges]
            width = xs[-1] - xs[0] + 1
            if self._opacity < 1.0:
                body = self._body_rgba
                cr.set_source_rgba(body.red, body.green, body.blue, 1.0)
                cr.rectangle(xs[0], ys[0], width, ys[-1] - ys[0])
                cr.fill()
            head = self._code_rgba
            cr.set_source_rgba(head.red, head.green, head.blue, 1.0)
            cr.rectangle(xs[0], ys[0], width, ys[1] - ys[0])
            cr.fill()
            cr.set_source_rgba(*CODE_OUTLINE)
            cr.set_line_width(1)
            for y in ys[:-1]:
                cr.move_to(xs[0], y + 0.5)
                cr.line_to(xs[-1] + 1, y + 0.5)
            cr.move_to(xs[0], ys[-1] - 0.5)
            cr.line_to(xs[-1] + 1, ys[-1] - 0.5)
            for x in xs:
                cr.move_to(x + 0.5, ys[0])
                cr.line_to(x + 0.5, ys[-1])
            cr.stroke()

    def _normalize_tables(self):
        """Give every row of a table as many cells as its widest row has, and
        take out a TABLE_MARKER that is not at the start of a line, as one
        left by joining a row to the line before it. Returns whether the text
        changed. The cursor stays at the characters it was at."""
        if self._normalizing:
            return False
        buf = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        if TABLE_MARKER not in text:
            return False
        lines = text.split('\n')
        starts, offset = [], 0
        for line in lines:
            starts.append(offset)
            offset += len(line) + 1
        edits = []   # (offset, text to insert, or None to delete one char)
        for number, line in enumerate(lines):
            index = line.find(TABLE_MARKER, 1)
            if index >= 0 and not self._is_code_line(buf, number):
                while index >= 0:
                    edits.append((starts[number] + index, None))
                    index = line.find(TABLE_MARKER, index + 1)
        for first, last in self._table_runs(buf, lines):
            columns = max(lines[n].count('\t') for n in range(first, last + 1))
            for number in range(first, last + 1):
                missing = columns - lines[number].count('\t')
                if missing:
                    edits.append((starts[number] + len(lines[number]),
                                  '\t' * missing))
        if not edits:
            return False

        marks = [buf.get_iter_at_mark(buf.get_insert()).get_offset(),
                 buf.get_iter_at_mark(buf.get_selection_bound()).get_offset()]
        self._normalizing = True
        try:
            for offset, insert in sorted(edits, key=lambda e: -e[0]):
                if insert is None:
                    buf.delete(buf.get_iter_at_offset(offset),
                               buf.get_iter_at_offset(offset + 1))
                    marks = [m - 1 if m > offset else m for m in marks]
                else:
                    self._insert_plain(offset, insert)
                    marks = [m + len(insert) if m > offset else m
                             for m in marks]
            insert, bound = (buf.get_iter_at_offset(m) for m in marks)
            buf.select_range(insert, bound)
        finally:
            self._normalizing = False
        self._queue_code_margins()
        return True

    def _insert_plain(self, offset, text):
        """Insert text at offset without the formats of the text before it."""
        buf = self.tv.get_buffer()
        buf.insert(buf.get_iter_at_offset(offset), text)
        start = buf.get_iter_at_offset(offset)
        end = buf.get_iter_at_offset(offset + len(text))
        for tag in (self._bold_tag, self._backtick_tag, self._heading_tag,
                    self._code_tag):
            buf.remove_tag(tag, start, end)

    def _edit_lines(self, edit):
        """Run edit, a change to the lines of a table or a section, as one
        undo step, without the formats typing would give the text it
        inserts."""
        self._flush_snapshot()
        self._restoring = True
        try:
            edit(self.tv.get_buffer())
        finally:
            self._restoring = False
        self._normalize_tables()
        self._normalize_sections()
        self._refresh_line_styles()
        self._sync_format_state()
        self.tv.scroll_mark_onscreen(self.tv.get_buffer().get_insert())
        self._flush_snapshot()
        self._queue_save()

    def _insert_table(self, columns=3, rows=3):
        """Insert an empty table with a header row, on the cursor's line when
        it is empty, else on a line after it."""
        def edit(buf):
            line = buf.get_iter_at_mark(buf.get_insert()).get_line()
            start, end = self._line_bounds(line)
            table = '\n'.join([TABLE_MARKER + '\t' * (columns - 1)] * rows)
            if buf.get_slice(start, end, True).strip(CODE_ANCHOR + ' \t'):
                self._insert_plain(end.get_offset(), '\n' + table)
                line += 1
            else:
                buf.delete(start, end)
                self._insert_plain(start.get_offset(), table)
            # A line to go on writing after the table.
            _, end = self._line_bounds(line + rows - 1)
            if end.is_end():
                buf.insert(end, '\n')
            buf.place_cursor(buf.get_iter_at_offset(
                buf.get_iter_at_line(line).get_offset() + len(TABLE_MARKER)))
        self._edit_lines(edit)

    def _add_table_row(self, line):
        """Add an empty row after the row `line` and put the cursor in it."""
        def edit(buf):
            columns = len(self._row_cells(line))
            offset = self._line_bounds(line)[1].get_offset()
            self._insert_plain(offset, '\n' + TABLE_MARKER + '\t' * (columns - 1))
            buf.place_cursor(buf.get_iter_at_offset(
                offset + 1 + len(TABLE_MARKER)))
        self._edit_lines(edit)

    def _delete_table_rows(self, first, last):
        """Delete the lines from first to last, with the line break before
        them, or after them at the start of the note, and put the cursor at
        the end of the line before, or at the start of the text after."""
        def edit(buf):
            start = buf.get_iter_at_line(first)
            _, end = self._line_bounds(last, include_newline=first == 0)
            if first > 0:
                start.backward_char()
            offset = start.get_offset()
            buf.delete(start, end)
            target = buf.get_iter_at_offset(offset)
            if first == 0 and self._is_table_row(0):
                target.forward_chars(len(TABLE_MARKER))
            buf.place_cursor(target)
        self._edit_lines(edit)

    def _cursor_table_cell(self):
        """(line, column) of the cell the cursor is in, or None."""
        buf = self.tv.get_buffer()
        cursor = buf.get_iter_at_mark(buf.get_insert())
        line = cursor.get_line()
        if not self._is_table_row(line):
            return None
        return line, self._cell_index(self._row_cells(line),
                                      cursor.get_offset())

    def _add_table_column(self):
        """Add an empty column after the cursor's."""
        here = self._cursor_table_cell()
        if here is None:
            return
        line, column = here
        first, last = self._table_bounds(line)

        def edit(buf):
            for row in range(last, first - 1, -1):
                cells = self._row_cells(row)
                self._insert_plain(cells[min(column, len(cells) - 1)][1], '\t')
            buf.place_cursor(buf.get_iter_at_offset(
                self._row_cells(line)[column + 1][0]))
        self._edit_lines(edit)

    def _delete_table_column(self):
        """Delete the cursor's column, or the whole table when it has no
        other."""
        here = self._cursor_table_cell()
        if here is None:
            return
        line, column = here
        first, last = self._table_bounds(line)
        if len(self._row_cells(line)) == 1:
            self._delete_table_rows(first, last)
            return

        def edit(buf):
            for row in range(last, first - 1, -1):
                cells = self._row_cells(row)
                if column >= len(cells):
                    continue
                start, end = cells[column]
                # The cell and the tab after it, or before the last one.
                if column + 1 < len(cells):
                    end += 1
                else:
                    start -= 1
                buf.delete(buf.get_iter_at_offset(start),
                           buf.get_iter_at_offset(end))
            cells = self._row_cells(line)
            buf.place_cursor(buf.get_iter_at_offset(
                cells[min(column, len(cells) - 1)][1]))
        self._edit_lines(edit)

    def _step_cell(self, forward):
        """Tab: the cursor goes to the end of the next cell, or of the one
        before. Past the last cell a new row is added."""
        buf = self.tv.get_buffer()
        line, column = self._cursor_table_cell()
        cells = self._row_cells(line)
        first, last = self._table_bounds(line)
        if forward:
            if column + 1 < len(cells):
                target = cells[column + 1][1]
            elif line < last:
                target = self._row_cells(line + 1)[0][1]
            else:
                self._add_table_row(line)
                return
        elif column > 0:
            target = cells[column - 1][1]
        elif line > first:
            target = self._row_cells(line - 1)[-1][1]
        else:
            target = cells[0][1]
        buf.place_cursor(buf.get_iter_at_offset(target))
        self.tv.scroll_mark_onscreen(buf.get_insert())

    def _on_table_key(self, buf, keyval, state):
        """Keys that act on a table. A cell holds one line of text, so Enter
        adds a row, and a tab is what separates cells, so Tab moves between
        them, and Backspace or Delete never take one."""
        cursor = buf.get_iter_at_mark(buf.get_insert())
        line = cursor.get_line()
        if not self._is_table_row(line):
            # Delete at the end of a line would join the table's first row to
            # it, and take that row out of the table.
            return (state == 0 and keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete)
                    and not buf.get_has_selection() and cursor.ends_line()
                    and not cursor.starts_line()
                    and self._is_table_row(line + 1))
        if (keyval in (Gdk.KEY_Tab, Gdk.KEY_KP_Tab, Gdk.KEY_ISO_Left_Tab)
                and state in (0, Gdk.ModifierType.SHIFT_MASK)):
            self._step_cell(state == 0 and keyval != Gdk.KEY_ISO_Left_Tab)
            return True
        if buf.get_has_selection() or state != 0:
            return False
        offset = cursor.get_offset()
        cells = self._row_cells(line)
        empty = all(start == end for start, end in cells)
        first, last = self._table_bounds(line)
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if empty and line == last:
                # Enter on an empty last row ends the table, as on an empty
                # list item: the row becomes an empty line.
                def edit(buf):
                    buf.delete(*self._line_bounds(line))
                self._edit_lines(edit)
            elif line == first and offset == cells[0][0]:
                # At the very start of the table, a line before it.
                def edit(buf):
                    buf.insert(buf.get_iter_at_line(line), '\n')
                    buf.place_cursor(buf.get_iter_at_line(line))
                self._edit_lines(edit)
            else:
                self._add_table_row(line)
            return True
        if keyval == Gdk.KEY_BackSpace:
            if offset == cells[0][0]:
                if empty:
                    self._delete_table_rows(line, line)
                return True
            return any(offset == start for start, _ in cells[1:])
        if keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete):
            return any(offset == end for _, end in cells)
        return False

    def _table_cell_at_pointer(self, x, y):
        """(iter under the pointer, (start, end) of the cell whose column the
        pointer is in), or None outside a table. The space a cell's text does
        not fill is the tab after it, which GTK counts as the next cell's."""
        bx, by = self.tv.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, int(x), int(y))
        _, it = self.tv.get_iter_at_location(bx, by)
        line = it.get_line()
        for first, last, edges in self._tables:
            if first <= line <= last and self._is_table_row(line):
                cells = self._row_cells(line)
                column = bisect.bisect_right(edges, bx) - 1
                return it, cells[max(0, min(len(cells) - 1, column))]
        return None

    def _click_table_cell(self, event, move_only=False):
        """Put the cursor in the cell clicked. Returns whether the click is
        handled; GTK places the cursor itself when it is in that cell."""
        hit = self._table_cell_at_pointer(event.x, event.y)
        if hit is None:
            return False
        it, (start, end) = hit
        offset = it.get_offset()
        if start <= offset <= end and not move_only:
            return False
        buf = self.tv.get_buffer()
        buf.place_cursor(buf.get_iter_at_offset(min(end, max(start, offset))))
        self.tv.grab_focus()
        return True

    # ------------------------------------------------------------------ sections
    # A section folds away what a note does not need now. Its title line
    # starts with ▾ or ▸, open or folded, and an invisible end line closes
    # it, so it is text like a list or a table: saved, undone, searched, and
    # copied as text. Folded content is hidden by a derived invisible tag.
    # See sections.py.

    def _is_section_title(self, line):
        buf = self.tv.get_buffer()
        if line < 0 or line >= buf.get_line_count():
            return False
        start = buf.get_iter_at_line(line)
        end = start.copy()
        end.forward_chars(len(EXPAND_OPEN))
        return (is_section_title(buf.get_slice(start, end, True))
                and not self._is_code_line(buf, line))

    def _find_sections(self):
        buf = self.tv.get_buffer()
        lines = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(),
                              True).split('\n')
        code = {n for n, line in enumerate(lines)
                if (is_section_title(line) or line == EXPAND_END)
                and self._is_code_line(buf, n)}
        return find_sections(lines, code)

    def _apply_sections(self, buf):
        """Hide what folded expands hold, and put what open ones hold in
        their boxes: margins for each line by how deep it is, the small gray
        title, and the end line that is the room at the bottom of a box."""
        start, end = buf.get_start_iter(), buf.get_end_iter()
        for tag in (self._fold_tag, self._expand_marker_tag,
                    self._expand_title_tag, self._expand_end_tag,
                    *self._expand_depth_tags.values()):
            buf.remove_tag(tag, start, end)
        sections, _orphans = self._find_sections()
        # A folded expand that holds a search match is shown open while it is
        # highlighted, as a browser opens <details> to show what it finds,
        # without changing the note. It folds again when the search closes.
        found = {buf.get_iter_at_offset(low).get_line()
                 for low, _high in self._get_tag_ranges(self._hl_tag)}
        self._sections = [
            s._replace(open=True) if not s.open and any(
                s.title < line and (s.end is None or line <= s.end)
                for line in found) else s
            for s in sections]
        count = buf.get_line_count()
        hidden = self._hidden_lines = hidden_lines(self._sections, count)

        def whole_line(line):
            # With its line break, which holds the margins of an empty line,
            # and which a hidden line hides so that it takes no room.
            low = buf.get_iter_at_line(line)
            high = (buf.get_iter_at_line(line + 1) if line + 1 < count
                    else buf.get_end_iter())
            return low, high

        for line in sorted(hidden):
            buf.apply_tag(self._fold_tag, *whole_line(line))

        # How many open expands each line is inside of.
        depth = {}
        for section in self._sections:
            if not section.open or section.title in hidden:
                continue
            last = count - 1 if section.end is None else section.end - 1
            for line in range(section.title + 1, last + 1):
                depth[line] = depth.get(line, 0) + 1
        self._line_depth = depth

        self._expand_boxes = []
        titles, ends = set(), set()
        for section in self._sections:
            if section.title in hidden:
                continue
            level = depth.get(section.title, 0)
            titles.add(section.title)
            line_start, line_end = self._line_bounds(section.title)
            marker_end = line_start.copy()
            marker_end.forward_chars(len(EXPAND_OPEN))
            buf.apply_tag(self._expand_marker_tag, line_start, marker_end)
            buf.apply_tag(self._expand_title_tag, marker_end, line_end)
            buf.apply_tag(self._expand_tag('title', level),
                          *whole_line(section.title))
            if section.open and section.end is not None:
                ends.add(section.end)
                low, high = whole_line(section.end)
                mark_end = low.copy()
                mark_end.forward_char()
                buf.apply_tag(self._fold_tag, low, mark_end)
                buf.apply_tag(self._expand_end_tag, low, high)
                self._expand_boxes.append((section.title, section.end, level))

        for line, level in depth.items():
            if line in hidden or line in titles or line in ends:
                continue
            if self._is_code_line(buf, line):
                kind = 'code'
            elif self._is_table_row(line):
                # Its tab stops tag sets its margin: see _apply_tables().
                continue
            else:
                kind = 'body'
            buf.apply_tag(self._expand_tag(kind, level), *whole_line(line))

    def _line_left(self, line):
        """Where the text of a line starts, in buffer coordinates, before a
        format of its own moves it: further in for each expand it is in."""
        return TEXT_MARGIN + self._line_depth.get(line, 0) * self._expand_unit

    def _expand_tag(self, kind, level):
        """The tag with the margins of a title, a line of content, or a line
        of code, `level` expands deep."""
        tag = self._expand_depth_tags.get((kind, level))
        if tag is None:
            tag = self.tv.get_buffer().create_tag(f'expand-{kind}-{level}')
            self._expand_depth_tags[(kind, level)] = tag
            self._set_expand_tag(kind, level, tag)
        return tag

    def _set_expand_tag(self, kind, level, tag):
        unit = self._expand_unit
        if kind == 'title':
            above, below = self._line_spacing
            tag.set_property('left-margin',
                             TEXT_MARGIN + level * unit + EXPAND_PAD)
            tag.set_property('right-margin',
                             TEXT_MARGIN + (level + 1) * EXPAND_PAD)
            tag.set_property('pixels-above-lines',
                             above + EXPAND_MARGIN + EXPAND_PAD)
            tag.set_property('pixels-below-lines', below + 2)
        elif kind == 'body':
            tag.set_property('left-margin', TEXT_MARGIN + level * unit)
            tag.set_property('right-margin', TEXT_MARGIN + level * EXPAND_PAD)
        else:
            tag.set_property('left-margin',
                             TEXT_MARGIN + level * unit + CODE_PAD)

    def _refresh_expand_tags(self):
        # The title's mark is as wide as the button drawn over it and a gap
        # after it, which takes the letter spacing Pango is asked for, made
        # up until it is as wide as that, as for list markers. The content is
        # as far in as the title's text.
        font, mark = self._body_font, EXPAND_OPEN
        wanted = self._expand_button_side() + EXPAND_GAP * self._font_size
        spread = 0
        for _ in range(4):
            spread = max(0, spread + (wanted - self._text_width(
                font, mark, EXPAND_TITLE_SCALE, spread)) / len(mark))
        self._expand_marker_tag.set_property(
            'letter-spacing', round(spread * Pango.SCALE))
        self._expand_unit = EXPAND_PAD + round(self._text_width(
            font, mark, EXPAND_TITLE_SCALE, spread))
        for (kind, level), tag in self._expand_depth_tags.items():
            self._set_expand_tag(kind, level, tag)
        # The end line's own text is a few pixels tall, which is part of
        # the room at the bottom of the box.
        self._expand_end_tag.set_property('pixels-above-lines',
                                          max(0, EXPAND_PAD - 3))
        self._expand_end_tag.set_property('pixels-below-lines',
                                          EXPAND_MARGIN)

    def _expand_chevron(self):
        """How wide the chevron of an expand's title is, in pixels."""
        return self._font_size * EXPAND_TITLE_SCALE * 0.5

    def _expand_button_side(self):
        """The chevron's button, square, with padding around the chevron so
        it is easy to hit."""
        return round(self._expand_chevron() + 2 * EXPAND_BUTTON_PAD)

    def _expand_button_rect(self, line):
        """(x, y, side) of the button of the expand titled on line, in
        buffer coordinates: over the title's mark, centered on the line."""
        buf = self.tv.get_buffer()
        loc = self.tv.get_iter_location(buf.get_iter_at_line(line))
        side = self._expand_button_side()
        return loc.x, loc.y + (loc.height - side) / 2, side

    def _expand_button_at(self, x, y):
        """The title line of the expand whose button is at x, y in the text
        window, or None."""
        bx, by = self.tv.window_to_buffer_coords(
            Gtk.TextWindowType.TEXT, int(x), int(y))
        count = self.tv.get_buffer().get_line_count()
        for section in self._sections:
            if section.title in self._hidden_lines or section.title >= count:
                continue
            left, top, side = self._expand_button_rect(section.title)
            if left <= bx < left + side and top <= by < top + side:
                return section.title
        return None

    def _on_tv_leave(self, tv, _event):
        if self._expand_hover is not None:
            self._expand_hover = None
            tv.queue_draw()
        return False

    def _draw_sections(self, tv, cr):
        """The box around each open expand, the chevron of each title, and a
        gray Title for a title not yet written."""
        buf = tv.get_buffer()
        count = buf.get_line_count()
        width = tv.get_allocated_width()
        cr.set_line_width(1)
        for title, end, level in self._expand_boxes:
            if end >= count:
                continue
            top = tv.get_line_yrange(buf.get_iter_at_line(title))[0]
            y, height = tv.get_line_yrange(buf.get_iter_at_line(end))
            left, wy = tv.buffer_to_window_coords(
                Gtk.TextWindowType.WIDGET,
                TEXT_MARGIN + level * self._expand_unit, top + EXPAND_MARGIN)
            right = width - TEXT_MARGIN - level * EXPAND_PAD
            box_height = y + height - EXPAND_MARGIN - top - EXPAND_MARGIN
            x0, y0 = left + 0.5, wy + 0.5
            w, h = right - left - 1, box_height - 1
            r = min(4, w / 2, h / 2)
            cr.new_sub_path()
            cr.arc(x0 + w - r, y0 + r, r, -math.pi / 2, 0)
            cr.arc(x0 + w - r, y0 + h - r, r, 0, math.pi / 2)
            cr.arc(x0 + r, y0 + h - r, r, math.pi / 2, math.pi)
            cr.arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2)
            cr.close_path()
            cr.set_source_rgba(0, 0, 0, 0.2)
            cr.stroke()

        size = self._expand_chevron()
        for section in self._sections:
            if section.title in self._hidden_lines or section.title >= count:
                continue
            start = buf.get_iter_at_line(section.title)
            bx, by, side = self._expand_button_rect(section.title)
            x, y = tv.buffer_to_window_coords(
                Gtk.TextWindowType.WIDGET, bx, round(by))
            if section.title == self._expand_hover:
                # Under the pointer, as a button is.
                r = 4
                cr.new_sub_path()
                cr.arc(x + side - r, y + r, r, -math.pi / 2, 0)
                cr.arc(x + side - r, y + side - r, r, 0, math.pi / 2)
                cr.arc(x + r, y + side - r, r, math.pi / 2, math.pi)
                cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
                cr.close_path()
                cr.set_source_rgba(0, 0, 0, 0.1)
                cr.fill()
            cx, cy = x + side / 2, y + side / 2
            cr.set_source_rgba(0, 0, 0, 0.55)
            cr.set_line_width(1.6)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_line_join(cairo.LINE_JOIN_ROUND)
            half = size / 2
            if section.open:
                cr.move_to(cx - half, cy - half / 2)
                cr.line_to(cx, cy + half / 2)
                cr.line_to(cx + half, cy - half / 2)
            else:
                cr.move_to(cx - half / 2, cy - half)
                cr.line_to(cx + half / 2, cy)
                cr.line_to(cx - half / 2, cy + half)
            cr.stroke()
            # A title not yet written shows what goes there.
            line_end = self._line_bounds(section.title)[1]
            if line_end.get_offset() - start.get_offset() == len(EXPAND_OPEN):
                after = start.copy()
                after.forward_chars(len(EXPAND_OPEN))
                aloc = tv.get_iter_location(after)
                ax, ay = tv.buffer_to_window_coords(
                    Gtk.TextWindowType.WIDGET, aloc.x, aloc.y)
                layout = tv.create_pango_layout('Title')
                font = self._body_font.copy()
                font.set_size(round(font.get_size() * EXPAND_TITLE_SCALE))
                layout.set_font_description(font)
                cr.set_source_rgba(0, 0, 0, 0.35)
                cr.move_to(ax, ay + (aloc.height - layout.get_pixel_size()[1]) / 2)
                PangoCairo.show_layout(cr, layout)
        return False

    def _toggle_sections(self, lines):
        """Fold the open sections titled on these lines and open the folded
        ones. A cursor in what folds goes to the end of the title."""
        def edit(buf):
            insert = buf.get_iter_at_mark(buf.get_insert()).get_offset()
            for line in lines:
                start = buf.get_iter_at_line(line)
                after = start.copy()
                after.forward_chars(len(EXPAND_OPEN))
                folded = buf.get_slice(start, after, True) == EXPAND_CLOSED
                buf.delete(start, after)
                self._insert_plain(buf.get_iter_at_line(line).get_offset(),
                                   EXPAND_OPEN if folded else EXPAND_CLOSED)
                section = next((s for s in self._sections if s.title == line),
                               None)
                if not folded and section is not None:
                    first = buf.get_iter_at_line(line + 1).get_offset() if (
                        line + 1 < buf.get_line_count()) else None
                    end = (buf.get_char_count() if section.end is None
                           else self._line_bounds(section.end)[1].get_offset())
                    if first is not None and first <= insert <= end:
                        insert = self._line_bounds(line)[1].get_offset()
            buf.place_cursor(buf.get_iter_at_offset(insert))
        self._edit_lines(edit)

    def _open_sections_around(self, offset):
        """Open the folded sections that hide the text at offset, as a search
        match there."""
        buf = self.tv.get_buffer()
        line = buf.get_iter_at_offset(offset).get_line()
        # Folded in the note, even when a search shows it open for now.
        folded = [s.title for s in self._find_sections()[0]
                  if not s.open and s.title < line
                  and (s.end is None or line <= s.end)]
        if folded:
            self._toggle_sections(folded)

    def _insert_section(self):
        """Insert an open section with an empty title for the cursor. With a
        selection, its lines become the section's content."""
        def edit(buf):
            bounds = buf.get_selection_bounds()
            if bounds:
                first, last = self._selected_or_cursor_lines()
                _, end = self._line_bounds(last)
                self._insert_plain(end.get_offset(), '\n' + EXPAND_END)
                start = buf.get_iter_at_line(first).get_offset()
                self._insert_plain(start, EXPAND_OPEN + '\n')
                title = first
            else:
                line = buf.get_iter_at_mark(buf.get_insert()).get_line()
                start, end = self._line_bounds(line)
                block = EXPAND_OPEN + '\n\n' + EXPAND_END
                if buf.get_slice(start, end, True).strip():
                    self._insert_plain(end.get_offset(), '\n' + block)
                    title = line + 1
                else:
                    buf.delete(start, end)
                    self._insert_plain(start.get_offset(), block)
                    title = line
            # A line after the section to go on writing outside it.
            end_line = next(s.end for s in self._find_sections()[0]
                            if s.title == title)
            _, end = self._line_bounds(end_line)
            if end.is_end():
                buf.insert(end, '\n')
            buf.place_cursor(self._line_bounds(title)[1])
        self._edit_lines(edit)

    def _unwrap_section(self, title):
        """Take away a section's title marker and end, and keep its content
        where it is."""
        section = next((s for s in self._find_sections()[0]
                        if s.title == title), None)

        def edit(buf):
            if section is not None and section.end is not None:
                start, end = self._line_bounds(section.end,
                                               include_newline=True)
                if end.is_end():
                    start.backward_char()
                buf.delete(start, end)
            start = buf.get_iter_at_line(title)
            after = start.copy()
            after.forward_chars(len(EXPAND_OPEN))
            buf.delete(start, after)
            buf.place_cursor(buf.get_iter_at_line(title))
        self._edit_lines(edit)

    def _on_section_key(self, buf, keyval, state):
        """Keys that act on a section: Ctrl+Enter on its title folds or opens
        it, Backspace at the start of the title takes the section away and
        keeps its content, and Enter on an empty last line of an open section
        goes on below it."""
        enter = keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
        if state == Gdk.ModifierType.CONTROL_MASK and enter:
            first, last = self._selected_or_cursor_lines()
            titles = [n for n in range(first, last + 1)
                      if self._is_section_title(n)]
            if titles:
                self._toggle_sections(titles)
                return True
            return False
        if state != 0 or buf.get_has_selection():
            return False
        cursor = buf.get_iter_at_mark(buf.get_insert())
        line = cursor.get_line()
        if (keyval == Gdk.KEY_BackSpace and self._is_section_title(line)
                and cursor.get_offset() == self._marker_end(line)):
            self._unwrap_section(line)
            return True
        # Joining a line to an expand's end would take the end away. Backspace
        # just after an expand goes into it instead, taking an empty line
        # with it, and Delete before an end, or after a folded title, does
        # nothing.
        if keyval == Gdk.KEY_BackSpace and cursor.starts_line() and line > 0:
            before = next((s for s in self._sections if s.end == line - 1),
                          None)
            if before is not None:
                into = before.end - 1 if before.open else before.title
                empty = cursor.ends_line()

                def edit(buf):
                    if empty:
                        low = buf.get_iter_at_line(line)
                        high = low.copy()
                        low.backward_char()
                        buf.delete(low, high)
                    buf.place_cursor(self._line_bounds(into)[1])
                self._edit_lines(edit)
                return True
        if (keyval in (Gdk.KEY_Delete, Gdk.KEY_KP_Delete) and cursor.ends_line()
                and any(s.end == line + 1 or (s.title == line and not s.open)
                        for s in self._sections)):
            return True
        if enter and cursor.starts_line() and cursor.ends_line():
            section = section_at(self._sections, line)
            if (section is not None and section.open
                    and section.end == line + 1):
                def edit(buf):
                    start, end = self._line_bounds(line, include_newline=True)
                    buf.delete(start, end)
                    # The end line is now `line`: a new line after it.
                    _, after = self._line_bounds(line, include_newline=True)
                    offset = after.get_offset()
                    if not after.is_end() or after.starts_line():
                        buf.insert(after, '\n')
                    buf.place_cursor(buf.get_iter_at_offset(offset))
                self._edit_lines(edit)
                return True
        return False

    def _click_section_marker(self, event):
        """A click on an expand's button folds or opens it."""
        line = self._expand_button_at(event.x, event.y)
        if line is None:
            return False
        self._toggle_sections([line])
        return True

    def _normalize_sections(self):
        """Take away an end line that ends no section, and an end mark that
        is not a line of its own, end a section never ended at the end of the
        note, and keep a line after the last end so the cursor can go there.
        Returns whether the text changed."""
        if self._normalizing:
            return False
        buf = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        if EXPAND_END not in text and not any(
                is_section_title(line) for line in text.split('\n')):
            return False
        sections, orphans = self._find_sections()
        lines = text.split('\n')
        starts, offset = [], 0
        for line in lines:
            starts.append(offset)
            offset += len(line) + 1
        edits = []   # (offset, characters to delete, text to insert)
        for number in orphans:
            if number > 0:
                edits.append((starts[number] - 1, len(lines[number]) + 1, ''))
            else:
                edits.append((0, len(lines[0]) + (len(lines) > 1), ''))
        for number, line in enumerate(lines):
            if EXPAND_END in line and line != EXPAND_END:
                index = line.find(EXPAND_END)
                while index >= 0:
                    edits.append((starts[number] + index, 1, ''))
                    index = line.find(EXPAND_END, index + 1)
        unended = sum(1 for s in sections if s.end is None)
        tail = '\n' + '\n'.join([EXPAND_END] * unended) if unended else ''
        ends = [s.end for s in sections if s.end is not None]
        if unended or (ends and max(ends) == len(lines) - 1):
            tail += '\n'
        if tail:
            edits.append((len(text), 0, tail))
        if not edits:
            return False
        marks = [buf.get_iter_at_mark(buf.get_insert()).get_offset(),
                 buf.get_iter_at_mark(buf.get_selection_bound()).get_offset()]
        self._normalizing = True
        try:
            for offset, length, insert in sorted(edits, key=lambda e: -e[0]):
                if length:
                    buf.delete(buf.get_iter_at_offset(offset),
                               buf.get_iter_at_offset(offset + length))
                    marks = [offset if offset < m < offset + length
                             else m - length if m >= offset + length else m
                             for m in marks]
                if insert:
                    self._insert_plain(offset, insert)
            buf.select_range(*(buf.get_iter_at_offset(m) for m in marks))
        finally:
            self._normalizing = False
        self._refresh_line_styles()
        return True

    # ------------------------------------------------------------------ formatting

    def _line_indent_len(self, text):
        index = 0
        while index < len(text) and text[index] in (' ', '\t'):
            index += 1
        return index

    def _list_parts(self, text):
        """(indent, marker, body) for a bullet or to-do line, else None."""
        indent_len = self._line_indent_len(text)
        for marker in LIST_MARKERS:
            if text.startswith(marker, indent_len):
                return (text[:indent_len], marker,
                        text[indent_len + len(marker):])
        return None

    def _line_list_parts(self, line):
        buf = self.tv.get_buffer()
        line_start, line_end = self._line_bounds(line)
        text = buf.get_text(line_start, line_end, True)
        return self._list_parts(text)

    def _line_list_marker(self, line):
        parts = self._line_list_parts(line)
        return parts and parts[1]

    def _line_has_list_marker(self, line):
        return self._line_list_parts(line) is not None

    def _line_is_empty_list_item(self, line):
        parts = self._line_list_parts(line)
        return parts is not None and parts[2].strip() == ''

    def _line_marker_bounds(self, line):
        parts = self._line_list_parts(line)
        if parts is None:
            return None
        marker_start = self.tv.get_buffer().get_iter_at_line(line)
        marker_start.forward_chars(len(parts[0]))
        marker_end = marker_start.copy()
        marker_end.forward_chars(len(parts[1]))
        return marker_start, marker_end

    def _flush_snapshot(self):
        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
        self._take_snapshot()

    def _start_list_from_typed(self, line, col, typed_len, marker):
        # Typing "- " or "[ ] " at the start of a line starts a list item, like
        # Markdown. The typed text is kept as its own undo step, so Ctrl+Z
        # turns the item back into what was typed.
        buf = self.tv.get_buffer()
        buf.insert_at_cursor(' ')
        self._flush_snapshot()

        typed = buf.get_iter_at_line_offset(line, col)
        typed_end = typed.copy()
        typed_end.forward_chars(typed_len + 1)
        buf.delete(typed, typed_end)
        buf.insert(buf.get_iter_at_line_offset(line, col), marker)
        self._tab_list_indents([line])
        self._flush_snapshot()

    def _start_heading_from_typed(self, line):
        # Typing "# " at the start of a line makes it a heading, like
        # Markdown, and the typed text is its own undo step. On an empty
        # line, the text typed next is the heading.
        buf = self.tv.get_buffer()
        buf.insert_at_cursor(' ')
        self._flush_snapshot()
        start = buf.get_iter_at_line(line)
        end = start.copy()
        end.forward_chars(2)
        buf.delete(start, end)
        start, end = self._line_bounds(line)
        if start.equal(end):
            self._heading_active = True
            self._bold_active = False
            self._refresh_format_buttons()
        else:
            buf.remove_tag(self._bold_tag, start, end)
            buf.apply_tag(self._heading_tag, start, end)
            self._sync_format_state()
        self._flush_snapshot()
        self._queue_save()

    def _typed_code_fence(self, buf):
        """Typing ``` alone on a line makes it a line of a code block, like
        Markdown. Returns whether it did."""
        cursor = buf.get_iter_at_mark(buf.get_insert())
        line = cursor.get_line()
        start, end = self._line_bounds(line)
        if (not cursor.equal(end) or self._is_code_line(buf, line)
                or buf.get_slice(start, end, True) != '```'):
            return False
        self._flush_snapshot()
        buf.delete(start, end)
        self._tag_code_line(line, keep_cursor=True)
        self._code_active = False
        self._refresh_format_buttons()
        self._flush_snapshot()
        self._queue_save()
        return True

    def _typed_bold(self, buf):
        """Typing the closing ** of **text** makes the text bold, like
        Markdown, and the asterisks go. Returns whether it did."""
        cursor = buf.get_iter_at_mark(buf.get_insert())
        line = cursor.get_line()
        start = buf.get_iter_at_line(line)
        if (self._is_code_line(buf, line) or start.has_tag(self._heading_tag)
                or self._iter_has_tag_context(cursor, self._backtick_tag)):
            return False
        m = TYPED_BOLD_RE.search(buf.get_slice(start, cursor, True))
        if m is None:
            return False
        first = start.get_offset() + m.start()
        length = len(m.group(1))
        self._flush_snapshot()
        closing = first + 2 + length
        buf.delete(buf.get_iter_at_offset(closing),
                   buf.get_iter_at_offset(closing + 2))
        buf.delete(buf.get_iter_at_offset(first),
                   buf.get_iter_at_offset(first + 2))
        self._tag_text(self._bold_tag, buf.get_iter_at_offset(first),
                       buf.get_iter_at_offset(first + length))
        # As with the closing backtick, the text typed next is not bold.
        self._bold_active = False
        self._refresh_format_buttons()
        self._flush_snapshot()
        self._queue_save()
        return True

    def _set_line_marker(self, line, marker):
        """Replace the line's list marker, or add one after its indent."""
        buf = self.tv.get_buffer()
        bounds = self._line_marker_bounds(line)
        if bounds is None:
            line_start, line_end = self._line_bounds(line)
            text = buf.get_text(line_start, line_end, True)
            at = line_start.copy()
            at.forward_chars(self._line_indent_len(text))
        else:
            offset = bounds[0].get_offset()
            buf.delete(*bounds)
            at = buf.get_iter_at_offset(offset)
        if marker:
            buf.insert(at, marker)

    def _toggle_checked(self, lines):
        self._flush_snapshot()
        for line in lines:
            marker = self._line_list_marker(line)
            if marker in CHECK_MARKERS:
                self._set_line_marker(
                    line, CHECKBOX_MARKER if marker == CHECKED_MARKER
                    else CHECKED_MARKER)
        self._flush_snapshot()
        self._queue_save()

    def _indent_bullet_line(self, line):
        buf = self.tv.get_buffer()
        line_start = buf.get_iter_at_line(line)
        buf.insert(line_start, '\t')

    def _tab_list_indents(self, lines=None):
        """Make the spaces that indent list items tabs (see tabbed_indent()).
        Returns whether any changed."""
        buf = self.tv.get_buffer()
        changed = False
        for line in (range(buf.get_line_count()) if lines is None else lines):
            parts = (self._marker_end(line) is not None
                     and self._line_list_parts(line))
            if not parts:
                continue
            indent = parts[0]
            tabbed = tabbed_indent(indent)
            if tabbed == indent:
                continue
            start = buf.get_iter_at_line(line)
            end = start.copy()
            end.forward_chars(len(indent))
            buf.delete(start, end)
            buf.insert(buf.get_iter_at_line(line), tabbed)
            changed = True
        return changed

    def _outdent_bullet_line(self, line):
        buf = self.tv.get_buffer()
        line_start, line_end = self._line_bounds(line)
        text = buf.get_text(line_start, line_end, True)
        parts = self._list_parts(text)
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
        # get_selection_bounds() is empty while the cursor is moving, even
        # when get_has_selection() has not caught up on some PyGObject
        # versions, so it is the one that decides.
        bounds = buf.get_selection_bounds()
        if not bounds:
            line = buf.get_iter_at_mark(buf.get_insert()).get_line()
            return line, line

        start, end = bounds
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
        line_text = buf.get_text(start, end, True)

        if line_text.replace(CODE_ANCHOR, ''):
            self._apply_tag_to_non_newline_chars(
                buf, self._code_tag, start, end, skip_markers=False)
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
            line_text = buf.get_text(start, end, True)
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
        bounds = buf.get_selection_bounds()
        if not bounds:
            return False
        start, end = bounds
        all_tagged = self._range_has_tag(tag, start, end)
        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()
        self._tag_text(tag, start, end, remove=all_tagged)
        self._take_snapshot()
        self._queue_save()
        self._sync_format_state()
        return True

    def _range_has_tag(self, tag, start, end):
        """Whether every character but newlines and list markers from start
        to end has tag."""
        buf = self.tv.get_buffer()
        found = False
        for low, high in self._text_segments(start.get_offset(),
                                             end.get_offset()):
            it = buf.get_iter_at_offset(low)
            stop = buf.get_iter_at_offset(high)
            while it.compare(stop) < 0:
                if it.get_char() != '\n':
                    if not it.has_tag(tag):
                        return False
                    found = True
                it.forward_char()
        return found

    # ------------------------------------------------------------------ format state
    # Bold, inline code, and heading are each on or off at the cursor, and the
    # buttons show which. Moving the cursor takes them from the text it is
    # attached to, the buttons and shortcuts toggle them, typing uses them, and
    # Enter turns them off.

    _bold_active = _code_active = _heading_active = False

    def _sync_format_state(self):
        """Take bold, inline code, and heading from the text at the cursor.

        A character format is on when the character before the cursor has it,
        or at the start of a line the character after it, or with a selection
        when all of it has it. A heading is on when every line with text that
        the cursor or selection is on is a heading.
        """
        if self._pending_format_inserts:
            # Mid-insert: the new text has not been styled yet.
            return
        buf = self.tv.get_buffer()
        self._code_active = self._format_at_cursor(buf, self._backtick_tag)
        lines = self._heading_lines()
        self._heading_active = bool(lines) and all(
            self._line_is_fully_tagged(self._heading_tag, ln) for ln in lines)
        # A heading is already bold, so bold is neither on nor available there.
        self._bold_active = (not self._heading_active
                             and self._format_at_cursor(buf, self._bold_tag))
        self._refresh_format_buttons()

    def _format_at_cursor(self, buf, tag):
        # The bounds are empty when the selection has just collapsed, as it
        # does when undo replaces the text.
        bounds = buf.get_selection_bounds()
        if bounds:
            return self._range_has_tag(tag, *bounds)
        it = buf.get_iter_at_mark(buf.get_insert())
        offset = it.get_offset()
        # The space at the end of inline code is outside of it as far as the
        # cursor after it goes, and the one at the start of it is not inside
        # for the cursor before it.
        if it.starts_line():
            if tag is self._backtick_tag and self._pad_kind(buf, offset):
                return False
            return not it.ends_line() and it.has_tag(tag)
        before = it.copy()
        before.backward_char()
        if tag is self._backtick_tag and self._pad_kind(buf, offset - 1) == 'trail':
            return False
        return before.has_tag(tag)

    def _heading_lines(self):
        """The lines with text that the cursor or selection is on, leaving
        out code, dividers, and list items, which never become headings."""
        buf = self.tv.get_buffer()
        first_line, last_line = self._selected_or_cursor_lines()
        return [ln for ln in range(first_line, last_line + 1)
                if not self._is_code_line(buf, ln)
                and ln not in self._divider_lines
                and self._marker_end(ln) is None
                and not self._line_bounds(ln)[0].ends_line()]

    def _toggle_bold(self):
        if self._heading_active:
            return
        if not self._toggle_tag(self._bold_tag):
            self._bold_active = not self._bold_active
            self._refresh_format_buttons()

    # ------------------------------------------------------------------ code padding
    # Inline code has a space at each end of it, which is its padding: a box
    # needs room beside its characters, and a space is the one thing a text
    # view lets take room without opening gaps in the text around it. The
    # spaces are tagged as code, sized by `_pad_tag`, and made and removed by
    # _normalize_code_pads() whenever the text changes, so a range that comes
    # from anywhere, an old note, a paste, or typing, gets them. The cursor is
    # in the code or outside it on either side of a space, and Backspace and
    # Delete step over a space as they do over a list marker.

    _normalizing = False
    _pads_sid = None

    def _pad_kind(self, buf, offset):
        """'lead' for the space at the start of an inline code range, 'trail'
        for the one at its end, or None."""
        if offset < 0 or offset >= buf.get_char_count():
            return None
        tag = self._backtick_tag
        here = buf.get_iter_at_offset(offset)
        if here.get_char() != CODE_PAD_CHAR or not here.has_tag(tag):
            return None
        before = here.copy()
        has_before = before.backward_char() and before.has_tag(tag)
        after = here.copy()
        has_after = after.forward_char() and after.has_tag(tag)
        if has_after and not has_before:
            return 'lead'
        if has_before and not has_after:
            return 'trail'
        return None

    def _keep_pads_out_of_selection(self, previous=None, keyboard=True):
        """A selection never ends in the padding of inline code, which a
        browser would not select either. Moved by a key, the end that moves
        goes on past a space it reached, the way it was going, so the selection
        grows by the character beyond it or gives the space up with the one
        before it. Dragged by the mouse, it stops short of the space, at the
        text that is under the pointer. The end that stays gives up a space it
        starts with."""
        buf = self.tv.get_buffer()
        insert = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        anchor = buf.get_iter_at_mark(buf.get_selection_bound()).get_offset()
        if insert == anchor:
            return False
        new_insert, new_anchor = insert, anchor
        edge = insert - 1 if insert > anchor else insert
        if self._pad_kind(buf, edge):
            if keyboard:
                step = 1 if previous is None or insert >= previous else -1
                if not 0 <= insert + step <= buf.get_char_count():
                    step = -step
            else:
                step = -1 if insert > anchor else 1
            new_insert = insert + step
        if new_anchor < new_insert and self._pad_kind(buf, new_anchor):
            new_anchor += 1
        elif new_anchor > new_insert and self._pad_kind(buf, new_anchor - 1):
            new_anchor -= 1
        if (new_insert, new_anchor) != (insert, anchor):
            buf.select_range(buf.get_iter_at_offset(new_insert),
                             buf.get_iter_at_offset(new_anchor))
        return False

    def _queue_pad_normalization(self):
        if self._pads_sid is None:
            self._pads_sid = GLib.idle_add(
                self._run_pad_normalization, priority=GLib.PRIORITY_HIGH_IDLE)

    def _run_pad_normalization(self):
        self._pads_sid = None
        self._normalize_code_pads()
        self._normalize_tables()
        self._normalize_sections()
        return False

    def _normalize_code_pads(self):
        """Give every inline code range the space at each end that is its
        padding, and take away a range that is only spaces. Returns whether
        the text changed. The cursor stays where it is among the characters;
        the one at the end of a range stays inside it, and the one at the
        start of a range stays outside it unless that is a line's start."""
        if self._normalizing:
            return False
        buf = self.tv.get_buffer()
        ranges = self._get_tag_ranges(self._backtick_tag)
        if not ranges:
            return False
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        edits = []
        for first, last in ranges:
            if self._is_code_line(buf, buf.get_iter_at_offset(first).get_line()):
                continue
            body = text[first:last]
            if not body.strip(' ' + CODE_PAD_CHAR):
                edits.append((first, 'delete', last))
                continue
            # A plain space there is the padding of an older note.
            if body[0] == ' ':
                edits.append((first, 'swap', first + 1))
            elif body[0] != CODE_PAD_CHAR:
                edits.append((first, 'lead', first))
            if body[-1] == ' ':
                edits.append((last - 1, 'swap', last))
            elif body[-1] != CODE_PAD_CHAR:
                edits.append((last, 'trail', last))
        if not edits:
            return False

        marks = [buf.get_iter_at_mark(buf.get_insert()).get_offset(),
                 buf.get_iter_at_mark(buf.get_selection_bound()).get_offset()]
        flags = (self._bold_active, self._code_active, self._heading_active)
        self._normalizing = True
        try:
            for offset, kind, stop in sorted(edits, key=lambda e: -e[0]):
                if kind == 'delete':
                    buf.delete(buf.get_iter_at_offset(offset),
                               buf.get_iter_at_offset(stop))
                    marks = [offset if offset < m < stop
                             else m - (stop - offset) if m >= stop else m
                             for m in marks]
                    continue
                if kind == 'swap':
                    buf.delete(buf.get_iter_at_offset(offset),
                               buf.get_iter_at_offset(stop))
                buf.insert(buf.get_iter_at_offset(offset), CODE_PAD_CHAR)
                buf.apply_tag(self._backtick_tag,
                              buf.get_iter_at_offset(offset),
                              buf.get_iter_at_offset(offset + 1))
                if kind == 'swap':
                    continue
                # A lone cursor at the start of a range is before it when
                # plain text has just been typed in front of it, and inside
                # it at the start of a line, where Enter has carried it.
                at_start = kind == 'lead' and (
                    marks[0] != marks[1] or offset == 0
                    or text[offset - 1] == '\n')
                marks = [m + 1 if (m >= offset if at_start else m > offset)
                         else m for m in marks]
            insert, bound = (buf.get_iter_at_offset(m) for m in marks)
            if marks[0] == marks[1]:
                buf.place_cursor(insert)
            else:
                buf.select_range(insert, bound)
        finally:
            self._normalizing = False
        self._bold_active, self._code_active, self._heading_active = flags
        self._refresh_format_buttons()
        self._queue_code_margins()
        return True

    def _toggle_inline_code(self):
        buf = self.tv.get_buffer()
        if buf.get_selection_bounds():
            self._toggle_code_selection(buf)
        elif not self._step_across_code_edge(buf):
            self._code_active = not self._code_active
            self._refresh_format_buttons()

    def _toggle_code_selection(self, buf):
        start, end = buf.get_selection_bounds()
        all_tagged = self._range_has_tag(self._backtick_tag, start, end)
        if self._snap_sid:
            GLib.source_remove(self._snap_sid)
            self._snap_sid = None
            self._take_snapshot()
        first = buf.create_mark(None, start, True)
        last = buf.create_mark(None, end, False)
        if all_tagged:
            # Spaces of the padding in the selection go with the code.
            pads = [o for o in range(start.get_offset(), end.get_offset())
                    if self._pad_kind(buf, o)]
            self._tag_text(self._backtick_tag, start, end, remove=True)
            self._normalizing = True
            try:
                for offset in reversed(pads):
                    buf.delete(buf.get_iter_at_offset(offset),
                               buf.get_iter_at_offset(offset + 1))
            finally:
                self._normalizing = False
        else:
            self._tag_text(self._backtick_tag, start, end)
        buf.select_range(buf.get_iter_at_mark(first),
                         buf.get_iter_at_mark(last))
        self._normalize_code_pads()
        buf.delete_mark(first)
        buf.delete_mark(last)
        self._take_snapshot()
        self._queue_save()
        self._sync_format_state()

    def _step_across_code_edge(self, buf):
        """Turning inline code on or off at the edge of it: the cursor steps
        over the space at the end, so it is where the text will go. Returns
        whether it did."""
        it = buf.get_iter_at_mark(buf.get_insert())
        offset = it.get_offset()
        before, after = self._pad_kind(buf, offset - 1), self._pad_kind(buf, offset)
        if self._code_active:
            if before == 'lead':
                buf.place_cursor(buf.get_iter_at_offset(offset - 1))
                return True
            if after == 'trail':
                buf.place_cursor(buf.get_iter_at_offset(offset + 1))
                return True
            return False
        if after == 'lead':
            buf.place_cursor(buf.get_iter_at_offset(offset + 1))
            return True
        if before == 'trail':
            buf.place_cursor(buf.get_iter_at_offset(offset - 1))
            return True
        return False

    def _delete_around_pad(self, buf, keyval):
        """Backspace and Delete next to the space of inline code take the
        character beyond it, as the box has no characters of its own there.
        Returns whether it handled the key."""
        offset = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        before, after = (self._pad_kind(buf, offset - 1),
                         self._pad_kind(buf, offset))
        if keyval == Gdk.KEY_BackSpace and before:
            if offset < 2:
                return True
            low = offset - 2
            # Code with nothing in it goes with both of its spaces.
            if before == 'trail' and self._pad_kind(buf, low) == 'lead':
                span = (low, offset)
            else:
                span = (low, offset - 1)
        elif keyval == Gdk.KEY_Delete and after:
            if offset + 2 > buf.get_char_count():
                return True
            if self._pad_kind(buf, offset + 1) == 'trail':
                span = (offset, offset + 2)
            else:
                span = (offset + 1, offset + 2)
        else:
            return False
        buf.delete(buf.get_iter_at_offset(span[0]),
                   buf.get_iter_at_offset(span[1]))
        return True

    def _toggle_heading(self):
        # A heading is a whole line, so it applies to every line the selection
        # touches, or to the cursor's line, like a list item. On an empty line
        # it is the text typed there next.
        buf = self.tv.get_buffer()
        lines = self._heading_lines()
        if not lines:
            self._heading_active = not self._heading_active
            self._refresh_format_buttons()
            return
        remove = all(self._line_is_fully_tagged(self._heading_tag, ln)
                     for ln in lines)
        self._flush_snapshot()
        for ln in lines:
            start, end = self._line_bounds(ln)
            if remove:
                buf.remove_tag(self._heading_tag, start, end)
            else:
                # Bold would not show in a heading, and would come back
                # unexpectedly if the heading were removed.
                buf.remove_tag(self._bold_tag, start, end)
                buf.apply_tag(self._heading_tag, start, end)
        self._flush_snapshot()
        self._queue_save()
        self._sync_format_state()

    def _format_backtick_wrapped_text(self):
        """Make text between two backticks on a line inline code. Code is
        text as it is, so a backtick in a code block or in inline code is
        left alone."""
        buf = self.tv.get_buffer()
        text = buf.get_slice(buf.get_start_iter(), buf.get_end_iter(), True)
        in_code = [False] * len(text)
        for first, last in self._get_tag_ranges(self._backtick_tag):
            in_code[first:last] = [True] * (last - first)
        pairs = []
        open_offset = None
        line = 0
        code_line = self._is_code_line(buf, 0)
        for offset, char in enumerate(text):
            if char == '\n':
                line += 1
                code_line = self._is_code_line(buf, line)
                open_offset = None
                continue
            if char != '`' or code_line or in_code[offset]:
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
            self._tag_text(self._backtick_tag, styled_start, styled_end)

        # Typing the closing backtick leaves the code, as in Slack: the cursor
        # is past the space that ends it.
        self._normalize_code_pads()
        cursor = buf.get_iter_at_mark(buf.get_insert()).get_offset()
        if self._pad_kind(buf, cursor) == 'trail':
            buf.place_cursor(buf.get_iter_at_offset(cursor + 1))
        self._code_active = False
        self._refresh_format_buttons()
        self._take_snapshot()
        self._queue_save()

    def _toggle_bullet(self):
        self._toggle_list((BULLET_MARKER,))

    def _toggle_checklist(self):
        self._toggle_list(CHECK_MARKERS)

    def _toggle_list(self, kind):
        # When every line is already this kind of item, the markers go.
        # Otherwise every line becomes one, replacing any other list marker.
        buf = self.tv.get_buffer()
        first_line, last_line = self._selected_or_cursor_lines()
        # A line of code, a heading, or a row of a table is not a list item.
        lines = [ln for ln in range(first_line, last_line + 1)
                 if not self._is_code_line(buf, ln)
                 and not self._is_table_row(ln)
                 and not self._is_section_title(ln)
                 and not (not self._line_bounds(ln)[0].ends_line()
                          and buf.get_iter_at_line(ln).has_tag(
                              self._heading_tag))]
        if not lines:
            return
        all_kind = all(self._line_list_marker(ln) in kind for ln in lines)

        self._flush_snapshot()
        for ln in reversed(lines):
            if all_kind:
                self._set_line_marker(ln, None)
            elif self._line_list_marker(ln) not in kind:
                self._set_line_marker(ln, kind[0])
        self._flush_snapshot()
        self._queue_save()

    def _toggle_code_block(self):
        """Make the cursor's or the selected lines a code block, or, when they
        all are code already, plain lines again.

        Nothing in code is formatted, so the lines become what they would be
        copied out as: Markdown, such as "# Title", "**bold**", "- item", or a
        table's rows, with every format taken off. Lines already code stay as
        they are. A line with an image is left out, as an image is no text."""
        buf = self.tv.get_buffer()
        first_line, last_line = self._selected_or_cursor_lines()
        lines = range(first_line, last_line + 1)
        if all(self._is_code_line(buf, ln) for ln in lines):
            self._flush_snapshot()
            for ln in reversed(lines):
                self._remove_code_from_line(ln)
            self._flush_snapshot()
            self._queue_save()
            return

        # Runs of lines without an image, each made code on its own.
        runs = []
        for ln in lines:
            start, end = self._line_bounds(ln)
            if IMAGE_ANCHOR in buf.get_slice(start, end, True):
                continue
            if runs and runs[-1][1] == ln - 1:
                runs[-1][1] = ln
            else:
                runs.append([ln, ln])
        if not runs:
            return

        def edit(buf):
            cursor = None
            # From the last, so the lines of the runs before stay where they
            # are. The cursor goes after the last, kept by a mark as the runs
            # before it change.
            for first, last in reversed(runs):
                start = buf.get_iter_at_line(first).get_offset()
                end = self._line_bounds(last)[1].get_offset()
                state = self._rich_state(start, end)
                # Code lines in it are text as they are, with no fences.
                state['code'] = []
                text = to_markdown(state)
                buf.delete(buf.get_iter_at_offset(start),
                           buf.get_iter_at_offset(end))
                self._insert_plain(start, text)
                new_last = first + text.count('\n')
                for ln in range(new_last, first - 1, -1):
                    self._tag_code_line(ln)
                if cursor is None:
                    cursor = buf.create_mark(
                        None, self._line_bounds(new_last)[1], True)
            buf.place_cursor(buf.get_iter_at_mark(cursor))
            buf.delete_mark(cursor)
            self._refresh_emoji_tags()
        self._edit_lines(edit)

    def _refresh_format_buttons(self):
        # The Format button is lit while a format is on at the cursor, so
        # that what is typed next gets it. Its menu checks which ones are.
        ctx = self._format_btn.get_style_context()
        if self._bold_active or self._heading_active or self._code_active:
            ctx.add_class('pinned')
        else:
            ctx.remove_class('pinned')

    def _format_items(self):
        return [
            BarItem('<b>B</b>', 'Bold', '**text**', 'Ctrl+B', self._toggle_bold,
                    self._bold_active, not self._heading_active),
            BarItem('<b>H</b>', 'Heading', '# text', 'Ctrl+H',
                    self._toggle_heading, self._heading_active, True),
            BarItem('&lt;/&gt;', 'Inline code', '`text`', 'Ctrl+E',
                    self._toggle_inline_code, self._code_active, True),
        ]

    def _insert_items(self):
        return [
            # A bullet is small in any font, so it is drawn a size up.
            BarItem('<span size="x-large">•</span>', 'Bullet list', '- item', 'Ctrl+8',
                    self._toggle_bullet, None, True),
            BarItem(CHECKBOX_MARKER.strip(), 'Checklist', '[ ] item', 'Ctrl+9',
                    self._toggle_checklist, None, True),
            BarItem('❝', 'Quote', '> text', '',
                    lambda: self._toggle_list((QUOTE_MARKER,)), None, True),
            BarItem('&lt;/&gt;', 'Code block', '```', 'Ctrl+Shift+C',
                    self._toggle_code_block, None, True, boxed=True),
            BarItem('—', 'Divider', '---', '', self._insert_divider,
                    None, True),
            BarItem('▸', 'Expand', '', '', self._insert_section, None, True),
            # Not inside a table: it would join that table.
            BarItem('⊞', 'Table', '', '', self._insert_table, None,
                    self._cursor_table_cell() is None),
            BarItem('🖼', 'Image…', '', 'Ctrl+V',
                    self._choose_and_insert_image, None, True),
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

    @staticmethod
    def _drop_extra_separators(menu):
        # Removing an item can leave two separators in a row, or one at an end.
        previous_was_separator = True
        for item in menu.get_children():
            is_separator = isinstance(item, Gtk.SeparatorMenuItem)
            if is_separator and previous_was_separator:
                menu.remove(item)
            else:
                previous_was_separator = is_separator
        children = menu.get_children()
        if children and isinstance(children[-1], Gtk.SeparatorMenuItem):
            menu.remove(children[-1])

    # GTK's own entries, as written in its source and as translated.
    _SELECT_ALL_LABELS = {'Select _All', 'Select All',
                          GLib.dgettext('gtk30', 'Select _All')}
    _EMOJI_LABELS = {'Insert _Emoji', 'Insert Emoji',
                     GLib.dgettext('gtk30', 'Insert _Emoji')}

    def _on_tv_popup(self, _, menu):
        # Select All is not worth a place in the menu (Ctrl+A does it), and
        # Insert Emoji moves to the top, above Undo.
        emoji_item = None
        for item in menu.get_children():
            if not isinstance(item, Gtk.MenuItem):
                continue
            if item.get_label() in self._SELECT_ALL_LABELS:
                menu.remove(item)
            elif item.get_label() in self._EMOJI_LABELS:
                menu.remove(item)
                emoji_item = item
        self._drop_extra_separators(menu)

        redo_item = Gtk.MenuItem(label='Redo  (Ctrl+Shift+Z)')
        redo_item.set_sensitive(self._hist_pos < len(self._history) - 1)
        redo_item.connect('activate', lambda _: self._redo())

        undo_item = Gtk.MenuItem(label='Undo  (Ctrl+Z)')
        undo_item.set_sensitive(self._hist_pos > 0)
        undo_item.connect('activate', lambda _: self._undo())

        search_item = Gtk.MenuItem(label='Search  (Ctrl+F)')
        search_item.connect('activate', lambda _: self._toggle_search())

        # Elements are inserted from the Insert button. A table's own items
        # act on the cell clicked, so they are here.
        table_items = []
        if self._cursor_table_cell() is not None:
            line = self.tv.get_buffer().get_iter_at_mark(
                self.tv.get_buffer().get_insert()).get_line()
            for label, callback in (
                    ('Add Row  (Enter)', lambda: self._add_table_row(line)),
                    ('Add Column', self._add_table_column),
                    ('Delete Row', lambda: self._delete_table_rows(line, line)),
                    ('Delete Column', self._delete_table_column),
                    ('Delete Table',
                     lambda: self._delete_table_rows(*self._table_bounds(line)))):
                item = Gtk.MenuItem(label=label)
                item.connect('activate', lambda _, cb=callback: cb())
                table_items.append(item)

        # Each prepend goes above the last, so this reads bottom to top:
        # Insert Emoji first, then Undo and Redo, then Search. In a table,
        # its items go above them all.
        menu.prepend(Gtk.SeparatorMenuItem())
        menu.prepend(search_item)
        menu.prepend(Gtk.SeparatorMenuItem())
        menu.prepend(redo_item)
        menu.prepend(undo_item)
        if emoji_item is not None:
            menu.prepend(Gtk.SeparatorMenuItem())
            menu.prepend(emoji_item)
        if table_items:
            menu.prepend(Gtk.SeparatorMenuItem())
            for item in reversed(table_items):
                menu.prepend(item)

        menu.show_all()

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

    def _apply_note_font(self):
        css = f'textview {{ font-size: {self._font_size}px; }}'.encode()
        self._font_prov.load_from_data(css)
        self._code_blocks.clear()
        if hasattr(self, '_emoji_tag'):
            self._emoji_tag.set_property('scale', self._emoji_scale())
        if hasattr(self, '_code_tag'):
            self._refresh_code_spacing()
            # Columns are as wide as their text in the new size.
            self._queue_code_margins()

    def _refresh_code_spacing(self):
        """Size the boxes around code and the room around them from the font.

        See CODE_PAD and CODE_PAD_Y. Every font has its own room
        above its tallest letters and below its lowest, so that room is
        measured. One more pixel is the outline itself.
        """
        tv = self.tv
        # The note's font as its CSS sets it, where GTK turns CSS pixels into
        # points at 96 dpi. It is not read back from the style context: on
        # PyGObject 3.42 (Ubuntu 22.04) that returns freed memory, which broke
        # every note.
        body = Pango.FontDescription()
        body.set_family(BODY_FONT)
        body.set_size(round(self._font_size * 0.75 * Pango.SCALE))

        measure = self._font_metrics

        def x_height(family):
            # Measured large, so rounding to pixels does not skew the ratio.
            font = Pango.FontDescription()
            font.set_family(family)
            font.set_absolute_size(100 * Pango.SCALE)
            layout = tv.create_pango_layout('x')
            layout.set_font_description(font)
            return layout.get_extents()[0].height

        # Code text is scaled so its lowercase letters match the body's.
        scale = x_height(body.get_family()) / x_height(CODE_FONT)
        scale = min(1.2, max(0.8, scale))
        self._code_tag.set_property('scale', scale)
        self._backtick_tag.set_property('scale', scale)
        code = body.copy()
        code.set_family(CODE_FONT)
        size = body.get_size() * scale
        if body.get_size_is_absolute():
            code.set_absolute_size(size)
        else:
            code.set_size(round(size))

        # The outline takes a pixel of the padding, so the room is one more.
        pad = CODE_PAD_Y + 1

        # A code block: its first and last line have the padding, and the room
        # around the block. The lines between keep the spacing of any line.
        self._code_top_tag.set_property('pixels-above-lines',
                                        CODE_BLOCK_MARGIN + pad)
        self._code_bottom_tag.set_property('pixels-below-lines',
                                           CODE_BLOCK_MARGIN + pad)

        # Inline code: the box is the code font's line area, raised with the
        # text, plus the padding. It may reach into the spacing between lines.
        # A code character's own rectangle is that area.
        ascent, descent = measure(code)
        rise = INLINE_CODE_RISE
        box_up = ascent + rise + pad
        box_down = descent - rise + pad

        # Where the line spacing goes. A line is as tall as its taller font
        # above and below the baseline. The box is in the middle of the line
        # when the room above it equals the room below it:
        #   spacing above + line ascent - box_up
        #       == spacing below + line descent - box_down
        body_ascent, body_descent = measure(body)
        line_ascent = max(body_ascent, ascent + rise)
        line_descent = max(body_descent, descent - rise)
        lean = round((box_up - box_down) - (line_ascent - line_descent))
        # Whole pixels only: when the spacing cannot be divided to match, it
        # is a pixel more, since the box being off center shows more than a
        # line being a pixel taller.
        total = LINE_SPACING + (LINE_SPACING + lean) % 2
        above = min(total, max(0, (total + lean) // 2))
        tv.set_pixels_above_lines(above)
        tv.set_pixels_below_lines(total - above)
        tv.set_pixels_inside_wrap(total)
        below = total - above
        self._table_row_tag.set_property('pixels-above-lines',
                                         above + TABLE_PAD_Y)
        self._table_row_tag.set_property('pixels-below-lines',
                                         below + TABLE_PAD_Y)
        self._table_top_tag.set_property(
            'pixels-above-lines', above + TABLE_PAD_Y + TABLE_MARGIN)
        self._table_bottom_tag.set_property(
            'pixels-below-lines', below + TABLE_PAD_Y + TABLE_MARGIN)

        # What _even_lines() works from. The fonts are measured again when the
        # size changes, so what was measured is forgotten.
        self._body_font = body
        self._body_metrics = self._line_extent(body, 'x')
        self._line_spacing = (above, total - above)
        self._line_cache = {}
        self._baseline_offset = self._body_metrics[0] + above

        # The height of a lowercase letter, which a bullet is centered on.
        layout = tv.create_pango_layout('x')
        layout.set_font_description(body)
        self._x_height = layout.get_extents()[0].height / Pango.SCALE

        # A list marker is drawn, so its characters are made to fit in the
        # line, so that they do not make it taller, and to take as much room
        # as they did, or as much as the drawing needs, so that the text after
        # them is where it was.
        size = self._font_size
        self._marker_metrics = {}
        self._marker_widths = {}
        for marker in LIST_MARKERS:
            ascent, descent = self._line_extent(body, marker[0])
            scale = max(0.4, min(
                1.0, self._body_metrics[0] / max(ascent, 1),
                self._body_metrics[1] / max(descent, 1)))
            fitted = body.copy()
            fitted.set_size(round(body.get_size() * scale))
            # What it adds to a line, whatever else is in it.
            self._marker_metrics[marker[0]] = self._line_extent(
                fitted, marker[0])
            drawn = {BULLET_MARKER: BULLET_SIZE, QUOTE_MARKER: QUOTE_BAR}.get(
                marker, CHECKBOX_SIZE) * size
            width = max(self._text_width(body, marker),
                        drawn + 1 + MARKER_GAP * size)
            # Pango does not add all the spacing it is asked for, so it is
            # measured as it will be applied, and made up until the marker is
            # as wide as it should be.
            spread = 0
            for _ in range(4):
                spread = max(0, spread + (
                    width - self._text_width(body, marker, scale, spread))
                    / len(marker))
            tag = self._marker_tags[marker[0]]
            tag.set_property('scale', scale)
            tag.set_property('letter-spacing', round(spread * Pango.SCALE))
            self._marker_widths[marker[0]] = width
        if hasattr(self, '_quote_hang_tag'):
            self._refresh_quote_hang()
        self._refresh_expand_tags()

        # A tab indents a list item by INDENT_SPACES spaces of the note's
        # font, and in code runs to the next stop of 8 characters, as
        # cell_width() counts it for the box.
        tv.set_tabs(self._tab_stops(
            self._text_width(body, ' ' * INDENT_SPACES)))
        self._code_tag.set_property('tabs', self._tab_stops(
            self._text_width(code, ' ' * 8)))

    def _refresh_quote_hang(self):
        # The first row starts at the margin, where the bar is, and the rows
        # after it as far in as the marker is wide: Pango indents every row
        # but the first by a negative indent.
        width = round(self._marker_widths[QUOTE_MARKER[0]])
        self._quote_hang_tag.set_property('indent', -width)

    @staticmethod
    def _tab_stops(width):
        """Tab stops every width pixels: Pango repeats the one stop given."""
        tabs = Pango.TabArray.new(1, True)
        tabs.set_tab(0, Pango.TabAlign.LEFT, max(1, round(width)))
        return tabs

    def _text_width(self, font, text, scale=1.0, spacing=0):
        """Width of text in font, as a tag with that scale and letter spacing
        in pixels would make it, when more text follows it.

        Pango leaves the spacing off the end of a line, so the width is where
        a character after the text starts."""
        layout = self.tv.create_pango_layout(text + 'x')
        layout.set_font_description(font)
        attributes = Pango.AttrList()
        for attribute in (Pango.attr_scale_new(scale),
                          Pango.attr_letter_spacing_new(
                              round(spacing * Pango.SCALE))):
            attribute.start_index = 0
            attribute.end_index = len(text.encode())
            attributes.insert(attribute)
        layout.set_attributes(attributes)
        return layout.index_to_pos(len(text.encode())).x / Pango.SCALE

    def _emoji_scale(self):
        return (self._font_size + 3) / self._font_size

    def _is_emoji_char(self, char):
        codepoint = ord(char)
        # The ballot boxes are checklist markers, which stay at text size so
        # a checklist is spaced like the lines around it.
        return (
            char in ('\u200d', '\ufe0e', '\ufe0f')
            or 0x1F000 <= codepoint <= 0x1FAFF
            or (0x2600 <= codepoint <= 0x27BF
                and not 0x2610 <= codepoint <= 0x2612)
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

    def _change_font_size(self, delta: int):
        self._font_size = max(8, min(32, self._font_size + delta))
        self._apply_note_font()
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
                    font_size=self._font_size, color=self._color,
                    opacity=self._opacity, collapsed=self._collapsed)

    def _get_tag_ranges(self, tag):
        # Jump from one toggle of the tag to the next instead of visiting every
        # character: this runs on every save and undo snapshot.
        buf = self.tv.get_buffer()
        ranges, it = [], buf.get_start_iter()
        start = 0 if it.has_tag(tag) else None
        while it.forward_to_tag_toggle(tag):
            if it.starts_tag(tag):
                start = it.get_offset()
            elif start is not None:
                ranges.append([start, it.get_offset()])
                start = None
        # GTK reports a toggle at the buffer end too, so this only guards
        # against a range left open.
        if start is not None:
            ranges.append([start, buf.get_char_count()])
        return ranges
