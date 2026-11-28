"""Drive the installed Ynote as a person would, and read what it shows.

Input is real X input (XTEST): pointer moves, clicks, and keys. What the app
shows is read from outside it: its accessibility tree (AT-SPI) for windows,
text, the cursor, the selection and focus; the clipboard; the files it saves;
and the screen's pixels. Nothing here imports Ynote, so the tests hold for
any toolkit Ynote is built with.
"""
import json
import os
import signal
import subprocess
import time

import gi
gi.require_version('Atspi', '2.0')
gi.require_version('Gdk', '3.0')
gi.require_version('Gtk', '3.0')
from gi.repository import Atspi, Gdk, Gtk  # noqa: E402
from Xlib import X, XK, display as xdisplay  # noqa: E402
from Xlib.ext import xtest  # noqa: E402

TIMEOUT = 5.0


class TestError(AssertionError):
    pass


def pump():
    """Let this process answer the X server and the clipboard."""
    while Gtk.events_pending():
        Gtk.main_iteration_do(False)


def wait_until(check, timeout=TIMEOUT, what='condition'):
    """Poll check() until it returns something true, and return that."""
    deadline = time.monotonic() + timeout
    while True:
        quiet()
        value = check()
        if value:
            return value
        if time.monotonic() > deadline:
            raise TestError(f'timed out waiting for {what}')
        time.sleep(0.01)


def settle(seconds=0.3):
    """Wait a set time: for what the app does on a timer of its own, such
    as taking an undo step. Anything else waits with quiet()."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        pump()
        time.sleep(0.01)


class _Activity:
    """When the app last showed a change, through the accessibility events
    it sends as its text, cursor, focus, or windows change, or when it was
    last given input."""

    def __init__(self):
        self.last = time.monotonic()
        self._listener = Atspi.EventListener.new(self._seen)
        for kind in ('object:', 'window:'):
            self._listener.register(kind)

    def _seen(self, _event):
        self.last = time.monotonic()


_activity = None


def acted():
    """Note that input was just sent: the app reacts to it from now."""
    global _activity
    if _activity is None:
        _activity = _Activity()
    _activity.last = time.monotonic()


def quiet(still=0.06, timeout=TIMEOUT):
    """Wait until the app has done reacting: no change shown for `still`
    seconds since the last input or change. What is read after this is what
    the app shows for the input given so far."""
    acted() if _activity is None else None
    deadline = time.monotonic() + timeout
    while True:
        pump()
        now = time.monotonic()
        if now - _activity.last >= still or now > deadline:
            return
        time.sleep(0.005)


# ---------------------------------------------------------------- input

class Input:
    """Real pointer and keyboard input through XTEST."""

    MODIFIERS = {'ctrl': 'Control_L', 'shift': 'Shift_L', 'alt': 'Alt_L',
                 'super': 'Super_L'}
    NAMES = {'enter': 'Return', 'esc': 'Escape', 'backspace': 'BackSpace',
             'del': 'Delete', 'delete': 'Delete', 'tab': 'Tab',
             'up': 'Up', 'down': 'Down', 'left': 'Left', 'right': 'Right',
             'home': 'Home', 'end': 'End', 'space': 'space',
             'pageup': 'Prior', 'pagedown': 'Next'}

    # Two clicks this close in time and place are a double click.
    DOUBLE_CLICK = 0.45

    def __init__(self):
        self.d = xdisplay.Display()
        self._last_click = (0.0, -100, -100)
        # A spare key code, mapped to any character a key is wanted for.
        self._spare = self.d.display.info.max_keycode

    def _code(self, keysym):
        code = self.d.keysym_to_keycode(keysym)
        if code:
            return code, False
        self.d.change_keyboard_mapping(self._spare, [(keysym,) * 4])
        self.d.sync()
        return self._spare, True

    def move(self, x, y):
        xtest.fake_input(self.d, X.MotionNotify, x=int(x), y=int(y))
        self.d.sync()
        acted()

    def press(self, button=1):
        xtest.fake_input(self.d, X.ButtonPress, button)
        self.d.sync()
        acted()

    def release(self, button=1):
        xtest.fake_input(self.d, X.ButtonRelease, button)
        self.d.sync()
        acted()

    def click(self, x, y, button=1, count=1):
        """Click, or double- or triple-click with count, as a hand does:
        with a few dozen milliseconds between the presses. Back-to-back
        presses can reach the app out of order through a window manager,
        which takes each press and passes it on. A single click on the spot
        just clicked waits, as a person does, so the two stay separate."""
        then, lx, ly = self._last_click
        near = abs(x - lx) < 10 and abs(y - ly) < 10
        # A double or triple click starts a sequence of its own, wherever
        # the click before it was.
        if ((near or count > 1)
                and time.monotonic() - then < self.DOUBLE_CLICK):
            settle(self.DOUBLE_CLICK - (time.monotonic() - then))
        self.move(x, y)
        for i in range(count):
            if i:
                settle(0.06)
            self.press(button)
            settle(0.03)
            self.release(button)
        self._last_click = (time.monotonic(), x, y)

    def drag(self, start, end, steps=8):
        self.move(*start)
        self.press()
        settle(0.03)
        for i in range(1, steps + 1):
            self.move(start[0] + (end[0] - start[0]) * i / steps,
                      start[1] + (end[1] - start[1]) * i / steps)
            settle(0.01)
        self.release()
        self._last_click = (time.monotonic(), end[0], end[1])

    def scroll(self, x, y, down=True, notches=1, mods=()):
        self.move(x, y)
        self._mods(mods, True)
        for _ in range(notches):
            button = 5 if down else 4
            self.press(button)
            self.release(button)
            settle(0.05)
        self._mods(mods, False)

    def _mods(self, mods, down):
        for m in (mods if down else reversed(mods)):
            code = self.d.keysym_to_keycode(
                XK.string_to_keysym(self.MODIFIERS[m]))
            xtest.fake_input(self.d, X.KeyPress if down else X.KeyRelease,
                             code)
        self.d.sync()
        acted()

    def _keysym(self, name):
        keysym = XK.string_to_keysym(self.NAMES.get(name.lower(), name))
        if not keysym and len(name) == 1:
            keysym = ord(name)
        return keysym

    def chord(self, mods, keys):
        """Hold mods and keys down together, then let go, as for Alt and two
        arrows at once."""
        codes = [self._code(self._keysym(k))[0] for k in keys]
        self._mods(mods, True)
        for code in codes:
            xtest.fake_input(self.d, X.KeyPress, code)
            self.d.sync()
            settle(0.05)
        for code in reversed(codes):
            xtest.fake_input(self.d, X.KeyRelease, code)
        self._mods(mods, False)

    def key(self, combo):
        """A key with modifiers, as 'ctrl+shift+z', 'enter', or 'alt+F4'."""
        *mods, name = combo.split('+') if combo != '+' else ['+']
        mods = [m.lower() for m in mods]
        keysym = self._keysym(name)
        code, spare = self._code(keysym)
        self._mods(mods, True)
        xtest.fake_input(self.d, X.KeyPress, code)
        xtest.fake_input(self.d, X.KeyRelease, code)
        self._mods(mods, False)

    def hangul(self):
        """The Korean/English key, which turns Korean input on or off."""
        code, _spare = self._code(XK.string_to_keysym('Hangul') or 0xff31)
        xtest.fake_input(self.d, X.KeyPress, code)
        xtest.fake_input(self.d, X.KeyRelease, code)
        self.d.sync()
        quiet()

    def type(self, text):
        """Type text key by key; any character, through a spare key code
        when the keyboard has none for it. A line break is Enter."""
        for ch in text:
            if ch == '\n':
                self.key('enter')
                continue
            keysym = XK.string_to_keysym(ch) if ch.isascii() else 0
            if ch.isascii() and ch.isprintable():
                keysym = ord(ch) if ch != ' ' else XK.XK_space
            if not keysym:
                keysym = 0x01000000 + ord(ch)
            code, spare = self._code(keysym)
            shift = (not spare and ch.isascii()
                     and self.d.keycode_to_keysym(code, 0) != keysym)
            if shift:
                self._mods(['shift'], True)
            xtest.fake_input(self.d, X.KeyPress, code)
            xtest.fake_input(self.d, X.KeyRelease, code)
            if shift:
                self._mods(['shift'], False)
            self.d.sync()
            acted()
            if spare:
                # The spare key code is mapped to the next character only
                # once the app has read this one with its mapping.
                quiet()


# ---------------------------------------------------------------- reading

def _children(acc):
    try:
        return [acc.get_child_at_index(i) for i in range(acc.get_child_count())]
    except Exception:
        return []


def find_all(root, predicate, limit=20):
    """Accessibles under root that predicate accepts, depth first."""
    found = []

    def walk(acc, depth):
        if depth > limit:
            return
        try:
            if predicate(acc):
                found.append(acc)
        except Exception:
            pass
        for child in _children(acc):
            walk(child, depth + 1)
    walk(root, 0)
    return found


def role(acc):
    return acc.get_role_name()


def name(acc):
    return acc.get_name() or ''


def showing(acc):
    return acc.get_state_set().contains(Atspi.StateType.SHOWING)


def extents(acc):
    e = acc.get_component_iface().get_extents(Atspi.CoordType.SCREEN)
    return e.x, e.y, e.width, e.height


def center(acc):
    x, y, w, h = extents(acc)
    return x + w / 2, y + h / 2


class TextArea:
    """A text the user edits: a note's text or a table cell."""

    def __init__(self, acc, inp):
        self.acc = acc
        self.inp = inp

    def _text(self):
        quiet()
        return self.acc.get_text_iface()

    def _chars(self):
        """What each offset holds: a character, or '' for one a person does
        not read: one the text view hides, such as the mark that keeps an
        empty code line, or the place of a table or image. AT-SPI counts them
        in its offsets but leaves them out of the text."""
        t = self._text()
        return [Atspi.Text.get_text(t, i, i + 1)
                for i in range(Atspi.Text.get_character_count(t))]

    def _full(self, index, chars=None):
        """The AT-SPI offset of the character at index in text()."""
        chars = self._chars() if chars is None else chars
        seen = 0
        for offset, ch in enumerate(chars):
            if ch:
                if seen == index:
                    return offset
                seen += 1
        return len(chars)

    def _visible(self, offset, chars=None):
        """The index in text() of the AT-SPI offset."""
        chars = self._chars() if chars is None else chars
        return sum(1 for ch in chars[:offset] if ch)

    def text(self):
        """The text as a person reads it: the line of a table or an image
        is empty. Offsets everywhere here are offsets into this text."""
        return ''.join(self._chars())

    def caret(self):
        return self._visible(Atspi.Text.get_caret_offset(self._text()))

    def selection(self):
        t = self._text()
        if Atspi.Text.get_n_selections(t) == 0:
            return None
        r = Atspi.Text.get_selection(t, 0)
        if r.start_offset == r.end_offset:
            return None
        chars = self._chars()
        return (self._visible(r.start_offset, chars),
                self._visible(r.end_offset, chars))

    def focused(self):
        quiet()
        return self.acc.get_state_set().contains(Atspi.StateType.FOCUSED)

    def attrs(self, index):
        """The text attributes at index, as assistive tools see them."""
        attrs, _start, _end = Atspi.Text.get_attribute_run(
            self._text(), self._full(index), False)
        return attrs

    def formats(self, needle, occurrence=0):
        """The formats every character of needle has: 'bold', 'bolder'
        (heavier than bold), 'code', 'heading'."""
        text = self.text()
        start = -1
        for _ in range(occurrence + 1):
            start = text.index(needle, start + 1)
        common = None
        for offset in range(start, start + len(needle)):
            if text[offset].isspace():
                continue
            a = self.attrs(offset)
            weight = int(a.get('weight', '400'))
            found = set()
            if weight >= 700:
                found.add('bold')
            if weight >= 800:
                found.add('bolder')
            if 'monospace' in a.get('family-name', ''):
                found.add('code')
            if float(a.get('scale', '1')) > 1.1:
                found.add('heading')
            common = found if common is None else common & found
        return common or set()

    def char_box(self, index):
        r = Atspi.Text.get_character_extents(self._text(), self._full(index),
                                             Atspi.CoordType.SCREEN)
        return r.x, r.y, r.width, r.height

    def point_at(self, offset, side='left'):
        """Where to click to put the cursor before the character at offset
        ('left') or after it ('right')."""
        x, y, w, h = self.char_box(offset)
        return (x + 1 if side == 'left' else x + w - 1), y + h / 2

    def click_at(self, offset, side='left', count=1):
        self.inp.click(*self.point_at(offset, side), count=count)

    def click_text(self, needle, at='start', count=1):
        """Click just before needle (at='start'), just after it ('end'),
        or in its middle."""
        text = self.text()
        i = text.index(needle)
        if at == 'start':
            self.click_at(i, 'left', count)
        elif at == 'end':
            self.click_at(i + len(needle) - 1, 'right', count)
        else:
            self.click_at(i + len(needle) // 2, 'left', count)

    def click(self, count=1):
        self.inp.click(*center(self.acc), count=count)


# ---------------------------------------------------------------- the app

class Note:
    """A note window, found by its title."""

    def __init__(self, app, frame):
        self.app = app
        self.frame = frame
        self.inp = app.inp

    @property
    def title(self):
        return name(self.frame)

    def _texts(self):
        return find_all(self.frame, lambda a: role(a) == 'text'
                        and a.get_state_set().contains(Atspi.StateType.EDITABLE)
                        and showing(a))

    @property
    def body(self):
        """The note's own text: the editable text that holds the others."""
        texts = self._texts()
        cells = {id(c) for t in texts for c in find_all(
            t, lambda a: role(a) == 'text', limit=4)[1:]}
        for t in texts:
            if id(t) not in cells and name(t) != 'Search':
                return TextArea(t, self.inp)
        raise TestError('the note has no text')

    def tables(self):
        """Each table on screen, not one a folded expand hides, as rows of
        its cells' TextAreas in screen order."""
        quiet()
        out = []
        for panel in find_all(self.body.acc, lambda a: role(a) == 'panel'
                              and showing(a), limit=3):
            cells = [c for c in _children(panel) if role(c) == 'text']
            if not cells:
                continue
            boxes = sorted(cells, key=lambda c: (extents(c)[1], extents(c)[0]))
            rows, top = [], None
            for c in boxes:
                y = extents(c)[1]
                if top is None or y != top:
                    rows.append([])
                    top = y
                rows[-1].append(TextArea(c, self.inp))
            out.append(rows)
        return out

    def cell(self, row, column, table=0):
        return self.tables()[table][row][column]

    def button(self, label):
        """A button by its label, or by its tooltip, which is what a
        button that shows an icon is known by."""
        def find():
            return next((b for b in find_all(
                self.frame, lambda a: role(a) in (
                    'push button', 'toggle button', 'button') and showing(a))
                if label in (name(b),
                             (b.get_description() or '').split(' (')[0])),
                None)
        return wait_until(find, what=f'button {label!r} in {self.title!r}')

    def press(self, label):
        self.inp.click(*center(self.button(label)))

    def box(self):
        """Where the window is and its size: x, y, width, height."""
        return extents(self.frame)

    def open_menu(self):
        """Right-click the title bar for the note's popover."""
        x, y, w, _h = self.box()
        self.inp.click(x + w // 2, y + 12, button=3)
        # It slides open: wait until its buttons stop moving.
        button = self.button('Delete Note')
        last = None
        while extents(button) != last:
            last = extents(button)
            settle(0.05)

    def search(self, query):
        """Ctrl+F, type the query once the search entry has the cursor, and
        wait for the list of matches, as a person reads it before going on."""
        self.inp.key('ctrl+f')
        entry = wait_until(lambda: next((
            a for a in find_all(self.frame, lambda a: role(a) == 'text'
                                and name(a) == 'Search' and showing(a))
            if a.get_state_set().contains(Atspi.StateType.FOCUSED)), None),
            what='the search entry')
        self.inp.type(query)
        wait_until(lambda: TextArea(entry, self.inp).text() == query
                   and find_all(self.frame, lambda a: role(a) == 'list item'
                                and showing(a)), what='the matches')

    def active(self):
        """Whether the window manager has made this the active window."""
        return self.frame.get_state_set().contains(Atspi.StateType.ACTIVE)

    def focused_text(self):
        """The text area with the keyboard focus, or None."""
        quiet()
        for t in self._texts():
            if t.get_state_set().contains(Atspi.StateType.FOCUSED):
                return TextArea(t, self.inp)
        return None

    def menu_items(self):
        """Labels of the items of any open menu or popover."""
        quiet()
        return [name(i) for i in find_all(
            self.app.acc, lambda a: role(a) in ('menu item', 'check menu item',
                                                'radio menu item')
            and showing(a))]

    def choose(self, label):
        def find():
            return next((i for i in find_all(
                self.app.acc, lambda a: role(a) in (
                    'menu item', 'check menu item', 'radio menu item')
                and showing(a)) if name(i).replace('_', '') == label), None)
        self.inp.click(*center(wait_until(
            find, what=f'menu item {label!r}')))


class App:
    """The installed Ynote, started with a HOME of its own."""

    def __init__(self, home, inp, command=('ynote',), ime=False):
        self.home = home
        self.inp = inp
        self.command = list(command)
        # Typing through the input method, ibus with its Korean engine.
        self.ime = ime
        self.proc = None
        self.log = os.path.join(home, 'ynote.log')

    # files
    @property
    def conf(self):
        return os.path.join(self.home, '.config', 'ynote')

    @property
    def notes_file(self):
        return os.path.join(self.conf, 'notes.json')

    def write_notes(self, notes):
        """Notes for the app to open: as 1.x saved them, which it opens
        converted, or as it saves them, with their documents."""
        os.makedirs(self.conf, exist_ok=True)
        with open(self.notes_file, 'w', encoding='utf-8') as f:
            json.dump(notes, f, ensure_ascii=False)

    def saved(self):
        with open(self.notes_file, encoding='utf-8') as f:
            return json.load(f)

    def saved_note(self, title):
        for note in self.saved():
            if note.get('title') == title:
                return note
        raise TestError(f'no saved note {title!r}')

    # process
    def start(self, wait_for_window=True):
        env = dict(os.environ, HOME=self.home)
        if self.ime:
            env['GTK_IM_MODULE'] = 'ibus'
        self.proc = subprocess.Popen(
            self.command, env=env, stdout=open(self.log, 'w'),
            stderr=subprocess.STDOUT, start_new_session=True)
        if wait_for_window:
            wait_until(lambda: self.windows(), timeout=15,
                       what='a Ynote window')
            # Once all are shown, Ynote stacks the notes as they were saved,
            # which moves the focus to the top one a moment later; a person
            # starts after it.
            quiet(still=0.3)
        return self

    def quit(self):
        """Quit as the desktop asks it to at logout: it saves first. Input
        sent before is handled first, as a person quits after it."""
        if self.proc and self.proc.poll() is None:
            quiet(still=0.2)
            os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid, signal.SIGKILL)
                self.proc.wait()

    def output(self):
        with open(self.log) as f:
            return f.read()

    # accessibility
    @property
    def acc(self):
        desk = Atspi.get_desktop(0)
        for app in _children(desk):
            if self.proc and app.get_process_id() == self.proc.pid:
                return app
        return None

    def windows(self):
        quiet()
        app = self.acc
        if app is None:
            return []
        return [w for w in _children(app) if showing(w)]

    def note(self, title, timeout=TIMEOUT):
        frame = wait_until(
            lambda: next((w for w in self.windows()
                          if role(w) == 'frame' and name(w) == title), None),
            timeout, f'note {title!r}')
        return Note(self, frame)

    def notes(self):
        return [Note(self, w) for w in self.windows() if role(w) == 'frame']

    def window(self, title, timeout=TIMEOUT):
        """A window of the app by its title, such as Hidden Notes."""
        return wait_until(
            lambda: next((w for w in self.windows() if name(w) == title),
                         None), timeout, f'window {title!r}')

    def press_in(self, window, label):
        """Click a button of any window of the app, by label or tooltip."""
        def find():
            return next((b for b in find_all(
                window, lambda a: 'button' in role(a) or role(a) == 'check box')
                if showing(b) and label in (
                    name(b), (b.get_description() or '').split(' (')[0])),
                None)
        self.inp.click(*center(wait_until(find, what=f'button {label!r}')))

    def texts_in(self, window):
        """The labels of a window, such as a dialog's message."""
        return [name(a) for a in find_all(
            window, lambda a: role(a) == 'label' and showing(a))]

    def dialog(self, timeout=TIMEOUT):
        return wait_until(
            lambda: next((w for w in self.windows()
                          if role(w) in ('dialog', 'alert')), None),
            timeout, 'a dialog')


# ---------------------------------------------------------------- clipboard

def clipboard_text():
    cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    pump()
    return cb.wait_for_text()


def set_clipboard(text):
    """Hold text on the clipboard, as another app would; this process serves
    it while the tests pump events."""
    cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    cb.set_text(text, -1)
    cb.store()
    pump()


# ---------------------------------------------------------------- pixels

def screenshot(path, box=None):
    """Save the screen, or the box (x, y, w, h) of it, as a PNG."""
    root = Gdk.get_default_root_window()
    if box is None:
        box = (0, 0, root.get_width(), root.get_height())
    pb = Gdk.pixbuf_get_from_window(root, *[int(v) for v in box])
    pb.savev(path, 'png', [], [])
    return pb


def pixel(pb, x, y):
    n = pb.get_n_channels()
    data = pb.get_pixels()
    i = int(y) * pb.get_rowstride() + int(x) * n
    return tuple(data[i:i + 3])

