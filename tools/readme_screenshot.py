#!/usr/bin/env python3
"""Render the README screenshot from the real app in a virtual X server.

    dbus-run-session -- xvfb-run -a -s "-screen 0 1600x1200x24" \\
        python3 tools/readme_screenshot.py

It opens sample notes with a throwaway HOME, captures each note window at
2x scale, and places them side by side on a plain background in
assets/ynote-screenshot.png. Rerun it after a visible UI change so the README
image stays current. dbus-run-session keeps it apart from a running Ynote.
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
from gi.repository import Gdk, GLib, Pango, PangoCairo  # noqa: E402

from ynote.app import PostItApp  # noqa: E402
from ynote.config import IMAGE_ANCHOR  # noqa: E402

OUTPUT = os.path.join(ROOT, 'assets', 'ynote-screenshot.png')
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
        self.ranges = {'bold_ranges': [], 'code_ranges': [],
                       'backtick_ranges': []}
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

    def note(self, note_id, title, x, w, h, on_top=False):
        return dict(id=note_id, title=title, text=self.text.rstrip('\n'),
                    x=x, y=0, w=w, h=h, on_top=on_top, images=self.images,
                    **self.ranges)


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
    debug.line('Repro', 'bold_ranges')
    debug.line('curl -i $STAGING/api/orders', 'code_ranges')
    debug.image(TERMINAL_IMAGE)
    debug.line('Cause', 'bold_ranges')
    debug.line('• The monthly report query takes ~75 s')
    debug.add('    • ').add('proxy_read_timeout', 'backtick_ranges')
    debug.line(' is 60 s')
    debug.line('---')
    debug.add('Fix: paginate the report query. Raising the timeout in ')
    debug.add('nginx.conf', 'backtick_ranges').line(' would only hide it.')

    git = NoteBuilder()
    git.line('Undo', 'bold_ranges')
    git.line('git reset --soft HEAD~1', 'code_ranges')
    git.line('git restore --staged <file>', 'code_ranges')
    git.line('Branches', 'bold_ranges')
    git.line('git switch -c fix/orders-timeout', 'code_ranges')
    git.line('git push -u origin HEAD', 'code_ranges')
    git.line('---')
    git.add('List branches that are safe to delete with ')
    git.add('git branch --merged', 'backtick_ranges').line('.')

    today = NoteBuilder()
    today.line('• Review the orders timeout PR')
    today.line('• Update the on-call runbook')
    today.line('    • add the 502 checklist')
    today.line('• Rotate staging DB password')
    today.line('---')
    today.line('1:1 at 3 pm', 'bold_ranges')

    # The bottom bar keeps a note at least about 300 px wide.
    notes = [('orders', '502 on /api/orders', debug, 340, True),
             ('git', 'git', git, 310, False),
             ('today', 'Today', today, 300, False)]
    out, x = [], 0
    for note_id, title, builder, width, on_top in notes:
        out.append(builder.note(note_id, title, x=x, w=width, h=320,
                                on_top=on_top))
        x += width + GAP
    return out


def setup_home():
    conf = os.path.join(HOME, '.config', 'ynote')
    os.makedirs(os.path.join(conf, 'images'))
    write_terminal_image(os.path.join(conf, 'images', TERMINAL_IMAGE))
    with open(os.path.join(conf, 'notes.json'), 'w') as f:
        json.dump(sample_notes(), f)


def compose(app):
    # Capture left to right, then lay the captures out by their real widths,
    # since a note can end up wider than requested.
    windows = sorted(app.notes.values(),
                     key=lambda w: w.get_window().get_origin()[1])
    shots = []
    for w in windows:
        gdk_win = w.get_window()
        shots.append(Gdk.pixbuf_get_from_window(
            gdk_win, 0, 0, gdk_win.get_width(), gdk_win.get_height()))

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
    surface.write_to_png(OUTPUT)
    print(OUTPUT)


def main():
    if not os.environ.get('DISPLAY'):
        sys.exit('run this under xvfb-run; see the docstring')
    setup_home()
    app = PostItApp()

    def hide_cursors():
        # A blinking text cursor would land in the picture at random.
        for w in app.notes.values():
            w.tv.set_cursor_visible(False)
        GLib.timeout_add(300, capture)
        return False

    def capture():
        compose(app)
        app.quit_app()
        return False

    GLib.timeout_add(2500, hide_cursors)
    app.run([sys.argv[0]])


if __name__ == '__main__':
    main()
