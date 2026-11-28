#!/usr/bin/env python3
"""Render the README pictures from the real app in a virtual X server.

    tools/readme_screenshot.sh

which runs it in the end-to-end test image, under a compositing manager
(xcompmgr), so a see-through note shows what is behind it.

It opens sample notes with a throwaway HOME and captures them at 2x scale on
a plain background. The pictures show as much of what Ynote does as they
can, since the README is mostly them:

- assets/ynote-screenshot.png: three notes side by side, between them every
  element a note holds: headings, a code block with one command selected
  and its Copy button, an image, lists, a checklist, inline code, a table,
  expands open and folded, a quote, a link, emoji, and a divider, in three
  colors, one pinned.
- assets/ynote-features.png: in its first row, find in every note, which
  lists matches in hidden notes too, and a note beside the Markdown it
  copies as; in its second, the / menu open in a note, a note collapsed to
  its title bar, and a see-through note over a terminal.

No picture repeats what another shows.
Each sample note has a place of its own on the large screen, so no other
note shows in its picture. Rerun it after a visible UI change so the README
pictures stay current. dbus-run-session keeps it apart from a running Ynote.
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
from ynote.web_popup import popup  # noqa: E402
from ynote.web_view import run_js  # noqa: E402
from ynote.config import (  # noqa: E402
    EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN, IMAGE_ANCHOR, TABLE_MARKER)

OUTPUT = os.path.join(ROOT, 'assets', 'ynote-screenshot.png')
FEATURES_OUTPUT = os.path.join(ROOT, 'assets', 'ynote-features.png')
ASSETS = os.path.join(ROOT, 'assets')
SEARCH_NOTE = 'scratch'
SLASH_NOTE = 'standup'
CLEAR_NOTE = 'clear'
# Behind the see-through note: a terminal, where on the screen (x, y, w, h).
TERMINAL_RECT = (560, 615, 520, 240)
MARKDOWN_NOTE = 'release'
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
    debug.line('kubectl logs deploy/api --since=10m', 'code_ranges')
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

    # The notes of the feature pictures, each in a place of its own on the
    # large screen, so no other note shows in its picture.
    def place(note_id, title, builder, x, y, w, h, color, **fields):
        note = builder.note(note_id, title, x=x, w=w, h=h)
        note.update(y=y, color=color, **fields)
        out.append(note)

    md = NoteBuilder()
    md.line('Release 2.4', 'heading_ranges')
    md.add('• ').add('Faster', 'bold_ranges').line(' report page')
    md.add('• New ').add('--dry-run', 'backtick_ranges').line(' flag')
    md.line('☐ Announce it')
    md.line('make release VERSION=2.4', 'code_ranges')
    place(MARKDOWN_NOTE, 'Release', md, 1200, 0, 380, 280, 'orange')

    scratch = NoteBuilder()
    scratch.line('api pods stuck after the config change')
    scratch.line('restart them, then check the logs')
    place(SEARCH_NOTE, 'Scratch', scratch, 1200, 520, 520, 280, 'yellow')

    standup = NoteBuilder()
    standup.line('Standup', 'heading_ranges')
    standup.line('• shipped the report fix')
    place(SLASH_NOTE, 'Standup', standup, 60, 520, 360, 240, 'green')

    snippets = NoteBuilder()
    snippets.line('Collapsed to its title bar')
    place('snippets', 'Snippets', snippets, 640, 520, 360, 200, 'blue', collapsed=True)
    clear = NoteBuilder()
    clear.line('See-through: the log shows behind')
    place(CLEAR_NOTE, 'Scratchpad', clear, 640, 570, 360, 200, 'pink', opacity=0.5, solid_in_use=False)

    # Hidden runbooks that the search picture finds.
    k8s = NoteBuilder()
    k8s.line('kubectl rollout restart deploy/api', 'code_ranges')
    nginx = NoteBuilder()
    nginx.line('sudo systemctl restart nginx', 'code_ranges')
    deploy = NoteBuilder()
    deploy.line('• restart the workers last')
    other = NoteBuilder()
    other.line('Reference')
    hidden = [('k8s', 'k8s', k8s, 'blue'), ('nginx', 'nginx', nginx, 'green'),
              ('deploy', 'Deploy', deploy, 'yellow'), ('psql', 'psql', other, 'purple'),
              ('tmux', 'tmux', other, 'gray'), ('oncall', 'On-call handoff', other, 'orange')]
    for order, (note_id, title, builder, color) in enumerate(hidden):
        note = builder.note(note_id, title, x=0, w=340, h=200, hidden=True)
        note['sort_order'] = float(order)
        note['color'] = color
        out.append(note)
    return out


def setup_home():
    conf = os.path.join(HOME, '.config', 'ynote')
    os.makedirs(os.path.join(conf, 'images'))
    write_terminal_image(os.path.join(conf, 'images', TERMINAL_IMAGE))
    with open(os.path.join(conf, 'notes.json'), 'w') as f:
        json.dump(sample_notes(), f)
    # The emoji picker's recent ones, as after some use.
    with open(os.path.join(conf, 'settings.json'), 'w') as f:
        json.dump({'emoji_recent': ['🚀', '✅', '🔥', '👍', '🐛', '🎉'], 'autostart_done': True}, f)


def capture_rect(x, y, width, height):
    """Crop a rectangle out of the screen. Reading a window's own surface
    aborts inside cairo on some GTK/cairo builds (an assertion on a surface
    with MIME data), as it has since an update of libxrender1 on Ubuntu
    22.04, while reading the screen works. The windows are placed apart, so
    a crop shows one window alone."""
    return Gdk.pixbuf_get_from_window(Gdk.get_default_root_window(), x, y, width, height)


def window_rect(window):
    gdk_win = window.get_window()
    x, y = gdk_win.get_origin()[1:]
    return x, y, gdk_win.get_width(), gdk_win.get_height()


def capture(*windows):
    """The windows, such as a note and its menu, each cropped out of the
    screen and laid where they are on the background, which shows between
    them instead of what else is on the screen."""
    rects = [window_rect(w) for w in windows]
    x = min(r[0] for r in rects)
    y = min(r[1] for r in rects)
    width = max(r[0] + r[2] for r in rects) - x
    height = max(r[1] + r[3] for r in rects) - y
    # The screen is read at SCALE pixels a point.
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width * SCALE, height * SCALE)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*BACKGROUND)
    cr.paint()
    for rx, ry, rw, rh in rects:
        Gdk.cairo_set_source_pixbuf(cr, capture_rect(rx, ry, rw, rh), (rx - x) * SCALE, (ry - y) * SCALE)
        cr.paint()
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, width * SCALE, height * SCALE)


def compose(shots, output):
    compose_rows([shots], output)


def compose_rows(rows, output):
    """Pictures laid left to right in rows, the rows top to bottom, on the
    background."""
    m, gap = MARGIN * SCALE, GAP * SCALE
    width = max(sum(pb.get_width() for pb in row) + gap * (len(row) - 1) for row in rows)
    height = sum(max(pb.get_height() for pb in row) for row in rows) + gap * (len(rows) - 1)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width + 2 * m, height + 2 * m)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*BACKGROUND)
    cr.paint()
    top = m
    for row in rows:
        left = m
        for pb in row:
            Gdk.cairo_set_source_pixbuf(cr, pb, left, top)
            cr.paint()
            left += pb.get_width() + gap
        top += max(pb.get_height() for pb in row) + gap
    surface.write_to_png(output)
    print(output)


def desktop():
    """A plain desktop under the notes, in the background color, so their
    round corners and the menus' shadows are drawn on it; and a terminal,
    for the see-through note to show."""
    screen = Gdk.Screen.get_default()
    back = Gtk.Window()
    back.set_decorated(False)
    back.move(0, 0)
    back.set_default_size(screen.get_width(), screen.get_height())
    back.connect('draw', lambda _w, cr: (cr.set_source_rgb(*BACKGROUND), cr.paint()) and False)
    back.set_app_paintable(True)
    back.show_all()
    x, y, w, h = TERMINAL_RECT
    term = Gtk.Window()
    term.set_decorated(False)
    term.move(x, y)
    term.set_default_size(w, h)
    term.set_app_paintable(True)

    def draw(_w, cr):
        cr.set_source_rgb(0.12, 0.13, 0.15)
        cr.paint()
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription('DejaVu Sans Mono 9'))
        lines = TERMINAL_LINES + [('$ kubectl get pods', (0.62, 0.85, 0.55)),
                                  ('api-7c9f   1/1   Running', (0.88, 0.88, 0.88)),
                                  ('worker-x2  0/1   CrashLoopBackOff', (0.95, 0.45, 0.42))]
        for i, (text, rgb) in enumerate(lines):
            cr.move_to(16, 52 + i * 20)
            cr.set_source_rgb(*rgb)
            layout.set_text(text, -1)
            PangoCairo.show_layout(cr, layout)
        return False
    term.connect('draw', draw)
    term.show_all()
    return term


# JavaScript run in a note before its picture.
SET_CURSOR_AT_END = """{
const pm = document.querySelector('.ProseMirror');
pm.focus();
const range = document.createRange();
range.selectNodeContents(pm.lastElementChild);
range.collapse(false);
getSelection().removeAllRanges();
getSelection().addRange(range);
}"""
# One command of the code block selected, as a double click on it does, and
# its Copy button shown, as while the pointer is on the block.
SELECT_COMMAND = """{
const pre = document.querySelector('pre code') || document.querySelector('pre');
document.querySelector('.ProseMirror').focus();
const text = pre.firstChild;
const at = text.data.indexOf('kubectl logs');
const range = document.createRange();
range.setStart(text, at);
range.setEnd(text, text.data.length);
getSelection().removeAllRanges();
getSelection().addRange(range);
document.querySelector('.code-copy').style.opacity = 1;
}"""
FIND_ALL = ("{ document.querySelector('.find-btn').click();"
            "document.querySelector('.find-toggle.all').click();"
            "const input = document.querySelector('.find-input');"
            f"input.value = '{SEARCH_QUERY}';"
            "input.dispatchEvent(new Event('input')); }")


def markdown_panel(note, height):
    """The Markdown the note copies as, drawn as it shows in a plain text
    editor beside it: what markdown.to_markdown() gives its document."""
    from ynote.convert import state_of
    from ynote.markdown import to_markdown
    text = to_markdown(state_of(note._doc['content'])).rstrip('\n')
    font = Pango.FontDescription('Noto Sans Mono 9.5')
    pad, width = 16, 330
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width * SCALE, height * SCALE)
    cr = cairo.Context(surface)
    cr.scale(SCALE, SCALE)
    cr.set_source_rgb(0.12, 0.13, 0.15)
    cr.paint()
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription('Ubuntu Bold 9'))
    layout.set_text('Copied as Markdown', -1)
    cr.set_source_rgb(0.62, 0.66, 0.72)
    cr.move_to(pad, pad - 4)
    PangoCairo.show_layout(cr, layout)
    layout.set_font_description(font)
    layout.set_text(text, -1)
    cr.set_source_rgb(0.90, 0.91, 0.93)
    cr.move_to(pad, pad + 22)
    PangoCairo.show_layout(cr, layout)
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, width * SCALE, height * SCALE)


def main():
    if not os.environ.get('DISPLAY'):
        sys.exit('run this under xvfb-run; see the docstring')
    setup_home()
    terminal = desktop()
    app = PostItApp()

    def js(note, code):
        run_js(note.view, code)

    def tidy():
        # No cursor, and none of its formats lit: at the empty line each
        # note ends with, then out of the note.
        for w in app.notes.values():
            js(w, SET_CURSOR_AT_END)
        GLib.timeout_add(300, blur)
        return False

    def blur():
        for w in app.notes.values():
            js(w, 'document.activeElement && document.activeElement.blur()')
        GLib.timeout_add(500, capture_notes)
        return False

    def capture_notes():
        js(app.notes['orders'], SELECT_COMMAND)
        js(app.notes[SEARCH_NOTE], FIND_ALL)
        js(app.notes[SLASH_NOTE], SET_CURSOR_AT_END)
        GLib.timeout_add(400, lambda: js(app.notes[SLASH_NOTE], "ynote.pasteText('/')") and False)
        GLib.timeout_add(1800, shoot)
        return False

    def shoot():
        windows = sorted((w for w in app.notes.values() if w.note_id in ('orders', 'rollout', 'today')),
                         key=lambda w: w.get_window().get_origin()[1])
        compose([capture(w) for w in windows], OUTPUT)
        release = app.notes[MARKDOWN_NOTE]
        shot = capture(release)
        compose_rows([[capture(app.notes[SEARCH_NOTE]), shot,
                       markdown_panel(release, shot.get_height() // SCALE)],
                      [capture(app.notes[SLASH_NOTE], popup()),
                       capture(app.notes['snippets'], terminal, app.notes[CLEAR_NOTE])]],
                     FEATURES_OUTPUT)
        app.quit_app()
        return False

    GLib.timeout_add(3500, tidy)
    app.run([sys.argv[0]])


if __name__ == '__main__':
    main()
