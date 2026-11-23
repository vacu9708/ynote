#!/usr/bin/env python3
"""Render the README customize picture on the real desktop.

    dbus-run-session -- python3 tools/readme_customize_screenshot.py [monitor]

The picture shows a see-through note with its right-click popover open and a
collapsed note. Opacity shows the desktop through a note, which a virtual X
server without a compositor cannot draw, so this runs on a real compositing X11
desktop. To keep the picture free of whatever is on that desktop, it covers one
monitor (the last one by default, or the 0-based index given) with a dark
backdrop of sample log lines for a few seconds, puts the notes on it, and
captures that area from the screen. Do not touch the mouse or keyboard while it
runs.
dbus-run-session keeps it apart from a running Ynote.

Windows that are always on top, such as pinned notes, stay above the backdrop
and would end up in the picture. Pick a monitor without any, and look at the
result before committing it.

It writes assets/ynote-customize.png. Rerun it after a visible UI change.
"""
import json
import os
import sys
import tempfile

# These must be set before GTK is imported.
os.environ['GDK_BACKEND'] = 'x11'
os.environ['GDK_SCALE'] = '2'
HOME = tempfile.mkdtemp(prefix='ynote-customize-')
os.environ['HOME'] = HOME

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import gi  # noqa: E402
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from ynote.app import PostItApp  # noqa: E402

OUTPUT = os.path.join(ROOT, 'assets', 'ynote-customize.png')
LOG_LINES = [
    ('$ journalctl -u nginx -f', (0.62, 0.85, 0.55)),
    ('Nov 23 09:14:02 web-1 nginx[812]: upstream timed out (110)', None),
    ('Nov 23 09:14:02 web-1 nginx[812]: client 10.0.4.17 GET /api/orders', None),
    ('Nov 23 09:14:09 web-1 nginx[812]: upstream timed out (110)', None),
    ('Nov 23 09:14:11 web-1 systemd[1]: nginx.service: reload requested', None),
    ('$ kubectl get pods -n shop', (0.62, 0.85, 0.55)),
    ('NAME            READY   STATUS    RESTARTS   AGE', (0.95, 0.75, 0.4)),
    ('api-6d9c7f-x2k  1/1     Running   0          3h', None),
    ('api-6d9c7f-q8m  1/1     Running   2          3h', None),
    ('worker-5b8d-p7  0/1     Pending   0          12m', None),
    ('$ tail -n 3 /var/log/app/orders.log', (0.62, 0.85, 0.55)),
    ('09:14:20 INFO  orders.report  query took 74.8 s', None),
    ('09:14:20 WARN  orders.report  slower than proxy_read_timeout', None),
    ('09:14:21 ERROR orders.api     502 Bad Gateway', (0.95, 0.45, 0.42)),
]
MARGIN = 40
NOTE_SIZE = (560, 380)
COLLAPSED_HEIGHT = 28


def sample_notes(left, top):
    text = ('Release steps\n☑ Bump the version\n☐ Build the package\n'
            '☐ Tag and upload\n\nWatch the 502s on the dashboard after the '
            'rollout.')
    width, height = NOTE_SIZE
    return [
        dict(id='release', title='Release', text=text, x=left, y=top,
             w=width, h=height, opacity=0.35, color='green',
             bold_ranges=[[0, len('Release steps')]]),
        dict(id='runbook', title='On-call runbook', text='', x=left,
             y=top + height + 30, w=width, h=300, color='purple',
             collapsed=True),
    ]


def backdrop(monitor_index):
    window = Gtk.Window()
    window.set_decorated(False)
    area = Gtk.DrawingArea()
    window.add(area)

    def draw(widget, cr):
        cr.set_source_rgb(0.09, 0.1, 0.12)
        cr.paint()
        cr.select_font_face('DejaVu Sans Mono')
        cr.set_font_size(14)
        y = 28
        for text, color in LOG_LINES * 4:
            cr.set_source_rgb(*(color or (0.8, 0.82, 0.85)))
            cr.move_to(24, y)
            cr.show_text(text)
            y += 22
        return False

    area.connect('draw', draw)
    window.fullscreen_on_monitor(Gdk.Screen.get_default(), monitor_index)
    window.show_all()
    return window


def main():
    if not os.environ.get('DISPLAY'):
        sys.exit('run this on a real X11 desktop with a compositor')
    display = Gdk.Display.get_default()
    index = (int(sys.argv[1]) if len(sys.argv) > 1
             else display.get_n_monitors() - 1)
    area = display.get_monitor(index).get_geometry()
    if not display.get_default_screen().is_composited():
        sys.exit('this desktop has no compositor, so opacity cannot show')
    left, top = area.x + 120, area.y + 100

    conf = os.path.join(HOME, '.config', 'ynote')
    os.makedirs(conf)
    with open(os.path.join(conf, 'notes.json'), 'w') as f:
        json.dump(sample_notes(left, top), f)

    app = PostItApp()
    state = {}

    def cover():
        state['backdrop'] = backdrop(index)
        GLib.timeout_add(800, raise_notes)
        return False

    def raise_notes():
        for note in app.notes.values():
            note.tv.set_cursor_visible(False)
            note.set_keep_above(True)
            note.present()
        GLib.timeout_add(600, open_menu)
        return False

    def open_menu():
        # Near the note's right edge, so the popover leaves the text visible.
        note = app.notes['release']
        event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
        event.x, event.y = NOTE_SIZE[0] - 120, 12
        note._show_ctx_menu(note._title_box, event)
        GLib.timeout_add(1200, capture)
        return False

    def capture():
        x0, y0 = app.notes['release'].get_position()
        x0, y0 = x0 - MARGIN, y0 - MARGIN
        # Wide enough for the popover, which hangs past the note's right edge.
        width = NOTE_SIZE[0] + 2 * MARGIN + 100
        height = NOTE_SIZE[1] + 30 + COLLAPSED_HEIGHT + 2 * MARGIN
        root = Gdk.get_default_root_window()
        pixbuf = Gdk.pixbuf_get_from_window(root, x0, y0, width, height)
        pixbuf.savev(OUTPUT, 'png', [], [])
        print(OUTPUT)
        state['backdrop'].destroy()
        app.quit_app()
        return False

    GLib.timeout_add(2500, cover)
    app.run([sys.argv[0]])


if __name__ == '__main__':
    main()
