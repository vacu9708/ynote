"""GNOME's window manager, mutter, run headless with Xwayland, for what only
it does: openbox, which the other tests run, focuses and stacks windows
otherwise, and XTEST input does not reach an app the way GNOME's does.

Input goes in as GNOME's own remote desktop does (the RemoteDesktop D-Bus
service): to the compositor, which hands it to Xwayland as from a real
mouse and keyboard. What the window manager did is read from X: the
stacking and the active window, with xprop: python-xlib fails to open a
second display in one process.
"""
import os
import re
import signal
import subprocess
import tempfile
import time

from gi.repository import Gio, GLib

ALT, SHIFT = 0xffe9, 0xffe1
BTN_LEFT = 0x110
SIGNATURES = {'CreateSession': None, 'Start': None, 'Stop': None,
              'NotifyPointerMotionRelative': '(dd)', 'NotifyKeyboardKeysym': '(ub)',
              'NotifyPointerAxisDiscrete': '(ui)', 'NotifyPointerButton': '(ib)'}


def _wait(check, timeout, what):
    deadline = time.monotonic() + timeout
    while True:
        value = check()
        if value:
            return value
        if time.monotonic() > deadline:
            raise AssertionError(f'timed out waiting for {what}')
        time.sleep(0.05)


class Gnome:
    """A headless GNOME desktop of 1600×1000, with a mouse and keyboard."""

    def __init__(self, log):
        self.runtime = tempfile.mkdtemp(prefix='mutter-')
        os.chmod(self.runtime, 0o700)
        self.proc = subprocess.Popen(
            ['mutter', '--headless', '--wayland', '--virtual-monitor', '1600x1000',
             '--wayland-display', 'wayland-ynote'],
            env=dict(os.environ, XDG_RUNTIME_DIR=self.runtime),
            stdout=open(log, 'w'), stderr=subprocess.STDOUT, start_new_session=True)
        # The display apps connect to, as it says: it keeps another for itself.
        number = _wait(lambda: re.findall(r'public X11 display :(\d+)', open(log).read()),
                       15, 'Xwayland')[0]
        auth = _wait(lambda: [f for f in os.listdir(self.runtime) if f.startswith('.mutter-Xwaylandauth')],
                     15, 'the Xwayland authority')
        self.env = {'DISPLAY': f':{number}', 'XAUTHORITY': os.path.join(self.runtime, auth[0]),
                    'XDG_RUNTIME_DIR': self.runtime}
        _wait(lambda: self._xprop('-root', '_NET_SUPPORTING_WM_CHECK'), 15, 'the window manager')
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION)
        self.session = _wait(lambda: self._call('/org/gnome/Mutter/RemoteDesktop', 'CreateSession'),
                             15, 'a remote desktop session')
        self._call(self.session, 'Start')
        # Its first key is lost while the keyboard's keymap is set up.
        # (Pointer moves, too: see move().)
        self.key(SHIFT, True)
        self.key(SHIFT, False)
        time.sleep(0.3)

    def _xprop(self, *args):
        out = subprocess.run(['xprop', *args], env=dict(os.environ, **self.env),
                             capture_output=True, text=True)
        return out.stdout if out.returncode == 0 and 'not found' not in out.stdout else ''

    def _call(self, path, method, *args):
        iface = 'org.gnome.Mutter.RemoteDesktop' + ('.Session' if '/Session/' in path else '')
        try:
            result = self.bus.call_sync(
                'org.gnome.Mutter.RemoteDesktop', path, iface, method,
                GLib.Variant(SIGNATURES[method], args) if args else None, None, 0, -1, None)
        except GLib.Error:
            if method == 'CreateSession':
                return None
            raise
        return result.unpack()[0] if result and result.n_children() else True

    # input
    def pointer(self):
        """Where the pointer is, from a process of its own (see above)."""
        out = subprocess.run(
            ['python3', '-c', 'from Xlib import display; p = display.Display().screen().root'
             '.query_pointer(); print(p.root_x, p.root_y)'],
            env=dict(os.environ, **self.env), capture_output=True, text=True).stdout.split()
        return tuple(map(int, out)) if len(out) == 2 else None

    def move(self, x, y):
        """Put the pointer at x, y: to the corner, then from there. The
        first moves of the session can be lost, as its first key is, so it
        goes again until X has it there. X knows where it is only while it
        is over a window of X."""
        for _ in range(10):
            self._call(self.session, 'NotifyPointerMotionRelative', -10000.0, -10000.0)
            self._call(self.session, 'NotifyPointerMotionRelative', float(x), float(y))
            time.sleep(0.2)
            if self.pointer() == (x, y):
                time.sleep(0.2)
                return
        raise AssertionError(f'the pointer is at {self.pointer()}, not {x}, {y}')

    def click(self):
        self._call(self.session, 'NotifyPointerButton', BTN_LEFT, True)
        self._call(self.session, 'NotifyPointerButton', BTN_LEFT, False)
        time.sleep(0.5)

    def key(self, keysym, down):
        self._call(self.session, 'NotifyKeyboardKeysym', keysym, down)

    def scroll(self, notches=1):
        """Wheel notches, down for more than 0, a while apart as a hand
        turns them."""
        self._call(self.session, 'NotifyPointerAxisDiscrete', 0, notches)
        time.sleep(0.5)

    # what the window manager did
    def _ids(self, prop):
        return re.findall(r'0x[0-9a-f]+', self._xprop('-root', prop).partition('#')[2])

    def _name(self, xid):
        found = re.search(r'= "(.*)"', self._xprop('-id', xid, '_NET_WM_NAME'))
        return found.group(1) if found else None

    def stacking(self):
        """The windows' names, top first."""
        return [self._name(x) for x in reversed(self._ids('_NET_CLIENT_LIST_STACKING'))]

    def active(self):
        ids = [x for x in self._ids('_NET_ACTIVE_WINDOW') if int(x, 16)]
        return self._name(ids[0]) if ids else None

    def wait_for_windows(self, names, timeout=20):
        _wait(lambda: set(names) <= set(self.stacking()), timeout, f'windows {names}')

    def stop(self):
        try:
            self._call(self.session, 'Stop')
        except Exception:
            pass
        try:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(5)
        except Exception:
            os.killpg(self.proc.pid, signal.SIGKILL)


def started(app, gnome, notes):
    """Ynote on the GNOME desktop with these notes, once it has stacked them
    as saved, which moves the focus to the top one."""
    app.write_notes(notes)
    env = dict(os.environ, HOME=app.home, YNOTE_DEBUG='1', **gnome.env)
    if app.web:
        env['YNOTE_WEB'] = '1'
    app.proc = subprocess.Popen(app.command, env=env, stdout=open(app.log, 'w'),
                                stderr=subprocess.STDOUT, start_new_session=True)
    gnome.wait_for_windows([n['title'] for n in notes])
    time.sleep(2)
    return app

