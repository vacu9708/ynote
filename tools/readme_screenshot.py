#!/usr/bin/env python3
"""Render the README screenshot from the real app in a virtual X server.

    dbus-run-session -- xvfb-run -a -s "-screen 0 2600x2000x24" \\
        python3 tools/readme_screenshot.py

It opens sample notes with a throwaway HOME and captures note windows at 2x
scale on a plain background. The pictures show as much of what Ynote does as
they can, since the README is mostly them:

- assets/ynote-screenshot.png: three notes side by side, between them every
  element a note holds: headings, a code block, an image, lists, a
  checklist, inline code, a table, expands open and folded, a quote, a link,
  emoji, and a divider, in three colors, one pinned.
- assets/ynote-hidden.png: a note with its right-click menu open, a note
  searching All notes, which lists matches in the hidden sample notes, and
  the Hidden Notes window.

Rerun it after a visible UI change so the README images stay current.
dbus-run-session keeps it apart from a running Ynote.
"""
import json
import os
import sys
import tempfile

# These must be set before GTK is imported.
os.environ['GDK_BACKEND'] = 'x11'
os.environ['GDK_SCALE'] = '2'
os.environ.pop('WAYLAND_DISPLAY', None)
HOME = tempfile.mkdtemp(prefix='ynote-screenshot-')
os.environ['HOME'] = HOME

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import cairo  # noqa: E402
import gi  # noqa: E402
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from ynote.app import PostItApp  # noqa: E402
from ynote.config import (  # noqa: E402
    EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN, IMAGE_ANCHOR, TABLE_MARKER)

OUTPUT = os.path.join(ROOT, 'assets', 'ynote-screenshot.png')
HIDDEN_OUTPUT = os.path.join(ROOT, 'assets', 'ynote-hidden.png')
SEARCH_NOTE = 'scratch'
MENU_NOTE = 'ideas'
SEARCH_QUERY = 'restart'
SCALE = 2
MARGIN = 28
GAP = 22
BACKGROUND = (0.89, 0.91, 0.93)

# Sample log output shown as a pasted screenshot in the first note.
TERMINAL_IMAGE = 'error-log.png'
TERMINAL_LINES = [
    ('$ tail -n 2 /var/log/nginx/error.log', (0.62, 0.85, 0.55)),
    ('[error] upstream timed out (110:', (0.95, 0.45, 0.42)),
    ('Connection timed out) while reading', (0.88, 0.88, 0.88)),
    ('response header from upstream', (0.88, 0.88, 0.88)),
]


class NoteBuilder:
    """Collects note text and the formatting ranges Ynote saves with it."""

    def __init__(self):
        self.text = ''
        self.ranges = {'bold_ranges': [], 'heading_ranges': [],
                       'code_ranges': [], 'backtick_ranges': []}
        self.images = []

    def add(self, text, kind=None):
        start = len(self.text)
        self.text += text
        if kind:
            self.ranges[kind].append([start, len(self.text)])
        return self

    def line(self, text='', kind=None):
        return self.add(text, kind).add('\n')

    def image(self, file_name):
        self.images.append({'file': file_name, 'offset': len(self.text)})
        return self.add(IMAGE_ANCHOR).add('\n')

    def note(self, note_id, title, x, w, h, on_top=False, hidden=False):
        return dict(id=note_id, title=title, text=self.text.rstrip('\n'),
                    x=x, y=0, w=w, h=h, on_top=on_top, hidden=hidden,
                    images=self.images, **self.ranges)


def write_terminal_image(path):
    # Drawn at 2x so it stays sharp at the note's 2x scale.
    font = Pango.FontDescription('DejaVu Sans Mono 8')
    pad, line_h, width = 10, 14, 300
    height = pad * 2 + line_h * len(TERMINAL_LINES)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width * SCALE,
                                 height * SCALE)
    cr = cairo.Context(surface)
    cr.scale(SCALE, SCALE)
    cr.set_source_rgb(0.12, 0.13, 0.15)
    cr.paint()
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(font)
    for i, (text, rgb) in enumerate(TERMINAL_LINES):
        cr.move_to(pad, pad + i * line_h)
        cr.set_source_rgb(*rgb)
        layout.set_text(text, -1)
        PangoCairo.show_layout(cr, layout)
    surface.write_to_png(path)


def sample_notes():
    debug = NoteBuilder()
    debug.line('Repro', 'heading_ranges')
    debug.line('curl -i $STAGING/api/orders', 'code_ranges')
    debug.image(TERMINAL_IMAGE)
    debug.line('Cause', 'heading_ranges')
    debug.line('• 🔥 The monthly report query takes ~75 s')
    debug.add('\t• ').add('proxy_read_timeout', 'backtick_ranges')
    debug.line(' is 60 s')
    debug.line('---')
    debug.add('Fix: paginate the report query. Raising the timeout in ')
    debug.add('nginx.conf', 'backtick_ranges').line(' would only hide it.')

    rollout = NoteBuilder()
    rollout.line('Services', 'heading_ranges')
    rollout.line(TABLE_MARKER + 'Service\tStatus\tOwner')
    rollout.add(TABLE_MARKER).add('orders-api', 'backtick_ranges')
    rollout.line('\t✅ live\tKim')
    rollout.add(TABLE_MARKER).add('report-worker', 'backtick_ranges')
    rollout.add('\t').add('blocked', 'bold_ranges').line('\tLee')
    rollout.line(EXPAND_OPEN + 'Checks after deploy')
    rollout.line('☑ Error rate under 0.1%')
    rollout.line('☐ p99 latency on the dashboard')
    rollout.line(EXPAND_END)
    rollout.line(EXPAND_CLOSED + 'Rollback steps')
    rollout.line('kubectl rollout undo deploy/orders-api', 'code_ranges')
    rollout.line(EXPAND_END)
    rollout.line('▍ Ship before the freeze on Friday')

    today = NoteBuilder()
    today.line('☑ Rotate staging DB password')
    today.line('☐ Review the orders timeout PR')
    today.line('\thttps://github.com/acme/shop/pull/482')
    today.line('☐ Update the on-call runbook')
    today.line('\t☐ add the 502 checklist')
    today.line('☐ Ship the fix 🚀')
    today.line('---')
    today.line('1:1 at 3 pm', 'bold_ranges')

    # A note that grows past its width would overlap the next one in the
    # capture, so they are wide enough for the bottom bar.
    notes = [('orders', '502 on /api/orders', debug, 340, 400, True, None),
             ('rollout', 'Rollout', rollout, 360, 400, False, 'green'),
             ('today', 'Today', today, 320, 400, False, 'blue')]
    out, x = [], 0
    for note_id, title, builder, width, height, on_top, color in notes:
        note = builder.note(note_id, title, x=x, w=width, h=height,
                            on_top=on_top)
        if color:
            note['color'] = color
        out.append(note)
        x += width + GAP

    # The notes of the second picture, below the first row so they stay out
    # of the first picture.
    ideas = NoteBuilder()
    for idea in ('Dark mode', 'Export', 'Sync', 'Themes'):
        ideas.line('• ' + idea)
    note = ideas.note(MENU_NOTE, 'Ideas', x=0, w=420, h=440)
    note['y'] = 460
    note['color'] = 'pink'
    out.append(note)

    # The note searched in the second picture, placed below the first row so
    # it stays out of the first picture.
    scratch = NoteBuilder()
    scratch.line('api pods stuck after the config change')
    scratch.line('restart them, then check the logs')
    note = scratch.note('scratch', 'Scratch', x=460, w=430, h=300)
    note['y'] = 460
    out.append(note)

    # Hidden runbooks that the search picture finds.
    k8s = NoteBuilder()
    k8s.line('kubectl rollout restart deploy/api', 'code_ranges')
    nginx = NoteBuilder()
    nginx.line('sudo systemctl restart nginx', 'code_ranges')
    deploy = NoteBuilder()
    deploy.line('• restart the workers last')
    other = NoteBuilder()
    other.line('Reference')
    hidden = [('k8s', 'k8s', k8s), ('nginx', 'nginx', nginx),
              ('deploy', 'Deploy', deploy), ('psql', 'psql', other),
              ('tmux', 'tmux', other), ('oncall', 'On-call handoff', other)]
    for order, (note_id, title, builder) in enumerate(hidden):
        note = builder.note(note_id, title, x=0, w=340, h=200, hidden=True)
        note['sort_order'] = float(order)
        out.append(note)
    return out


def setup_home():
    conf = os.path.join(HOME, '.config', 'ynote')
    os.makedirs(os.path.join(conf, 'images'))
    write_terminal_image(os.path.join(conf, 'images', TERMINAL_IMAGE))
    with open(os.path.join(conf, 'notes.json'), 'w') as f:
        json.dump(sample_notes(), f)


def capture(window):
    """Crop a window out of the screen instead of reading its own surface.

    Reading a window's own surface aborts inside cairo on some GTK/cairo
    builds (an assertion on a surface with MIME data), as it has since an
    update of libxrender1 on Ubuntu 22.04, while reading the screen works.
    The windows are placed apart, so a crop shows one window alone.
    """
    gdk_win = window.get_window()
    origin_x, origin_y = gdk_win.get_origin()[1:]
    return Gdk.pixbuf_get_from_window(
        Gdk.get_default_root_window(), origin_x, origin_y,
        gdk_win.get_width(), gdk_win.get_height())


def compose(shots, output):
    m, gap = MARGIN * SCALE, GAP * SCALE
    width = sum(pb.get_width() for pb in shots) + gap * (len(shots) - 1)
    height = max(pb.get_height() for pb in shots)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width + 2 * m,
                                 height + 2 * m)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*BACKGROUND)
    cr.paint()
    left = m
    for pb in shots:
        # A soft drop shadow made of a few widening translucent rectangles.
        for spread in range(1, 7):
            cr.set_source_rgba(0, 0, 0, 0.035)
            cr.rectangle(left - spread, m - spread + 4,
                         pb.get_width() + 2 * spread,
                         pb.get_height() + 2 * spread)
            cr.fill()
        Gdk.cairo_set_source_pixbuf(cr, pb, left, m)
        cr.paint()
        left += pb.get_width() + gap
    surface.write_to_png(output)
    print(output)


def main():
    if not os.environ.get('DISPLAY'):
        sys.exit('run this under xvfb-run; see the docstring')
    setup_home()
    app = PostItApp()

    def hide_cursors():
        # A blinking text cursor would land in the picture at random.
        for w in app.notes.values():
            w.tv.set_cursor_visible(False)
            # At the start of the first line where no format is on, so the
            # Format button is not lit.
            buf = w.tv.get_buffer()
            for line in range(buf.get_line_count()):
                buf.place_cursor(buf.get_iter_at_line(line))
                w._sync_format_state()
                if not (w._bold_active or w._heading_active
                        or w._code_active):
                    break
        GLib.timeout_add(300, capture_notes)
        return False

    def capture_notes():
        # Capture left to right, then lay the captures out by their real
        # widths, since a note can end up wider than requested.
        windows = sorted((w for w in app.notes.values()
                          if w.get_visible()
                          and w.note_id not in (SEARCH_NOTE, MENU_NOTE)),
                         key=lambda w: w.get_window().get_origin()[1])
        compose([capture(w) for w in windows], OUTPUT)

        menu_note = app.notes[MENU_NOTE]
        event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
        # Toward the right, so the notes' text stays in view beside it.
        event.button.x, event.button.y = 300.0, 10.0
        menu_note._show_ctx_menu(menu_note._title_box, event.button)
        GLib.timeout_add(800, capture_menu)
        return False

    def capture_menu():
        shots.append(capture(app.notes[MENU_NOTE]))
        note = app.notes[SEARCH_NOTE]
        note._toggle_search()
        note._search_entry.set_text(SEARCH_QUERY)
        note._all_notes_check.set_active(True)
        GLib.timeout_add(800, capture_search)
        return False

    def capture_search():
        note = app.notes[SEARCH_NOTE]
        # Show the query as typed, without the selection set_text() leaves.
        end = len(SEARCH_QUERY)
        note._search_entry.select_region(end, end)
        GLib.timeout_add(300, lambda: capture_search_now(note))
        return False

    def capture_search_now(note):
        shots.append(capture(note))
        app.show_hidden_notes_manager(parent_note=note)
        manager = app._hidden_notes_window
        manager._tree.get_selection().select_path(Gtk.TreePath(0))
        GLib.timeout_add(500, lambda: capture_hidden(shots, manager))
        return False

    def capture_hidden(shots, manager):
        compose(shots + [capture(manager)], HIDDEN_OUTPUT)
        app.quit_app()
        return False

    shots = []
    GLib.timeout_add(2500, hide_cursors)
    app.run([sys.argv[0]])


if __name__ == '__main__':
    main()
