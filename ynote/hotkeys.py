"""Global Ctrl + Super + arrow hotkeys on X11.

GTK only sees key presses while one of our windows has focus, so the snap
shortcut is grabbed on the X root window through a separate python-xlib
connection that runs in a background thread.
"""
import threading

from gi.repository import GLib

try:
    from Xlib import X, XK, display, error
except ImportError:  # python3-xlib is optional; the in-window shortcut still works
    X = None

ARROWS = {'Left': 'left', 'Right': 'right', 'Up': 'up', 'Down': 'down'}


class SnapHotkeys:
    def __init__(self, callback):
        # callback(keys) runs on the GTK main loop with the arrows currently
        # held, the one just pressed last.
        self._callback = callback

    def start(self):
        if X is None:
            return False
        try:
            self._dpy = display.Display()
        except Exception:
            return False
        root = self._dpy.screen().root
        self._keycodes = {}
        for name, key in ARROWS.items():
            self._keycodes[self._dpy.keysym_to_keycode(XK.string_to_keysym(name))] = key

        # Grab with every combination of CapsLock/NumLock so they don't block it.
        base = X.ControlMask | X.Mod4Mask
        catcher = error.CatchError(error.BadAccess)
        for keycode in self._keycodes:
            for extra in (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask):
                root.grab_key(keycode, base | extra, True,
                              X.GrabModeAsync, X.GrabModeAsync, onerror=catcher)
        self._dpy.sync()
        if catcher.get_error():
            return False

        threading.Thread(target=self._run, daemon=True).start()
        return True

    def _run(self):
        while True:
            ev = self._dpy.next_event()
            if ev.type != X.KeyPress or ev.detail not in self._keycodes:
                continue
            pressed = self._keycodes[ev.detail]
            # Ask the server which arrows are physically down, so pressing two
            # arrows together works even if a release was delivered elsewhere.
            keymap = self._dpy.query_keymap()
            held = [key for keycode, key in self._keycodes.items()
                    if key != pressed and keymap[keycode // 8] & (1 << keycode % 8)]
            GLib.idle_add(self._callback, held + [pressed])
