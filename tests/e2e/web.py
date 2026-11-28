"""Driving a note of Ynote 2.0, whose window is a web page: its buttons and
editor as the page shows them through AT-SPI, the popup window that shows
its menus, and the content it saves (notes-2.json)."""
import time

from tests.e2e.driver import (
    TestError, _children, center, extents, find_all, name, quiet, role,
    showing, wait_until)

NOTE = {'id': 'test', 'title': 'test', 'text': '', 'x': 100, 'y': 80,
        'w': 420, 'h': 360}


def start(app, text='', at=(0, 10), **fields):
    """Ynote 2.0 with one note titled test, as 1.x saved it, clicked into at
    the end of its first line: clicked at, from the text's top left."""
    app.write_notes([dict(NOTE, text=text, **fields)])
    app.start()
    note = WebNote(app, app.note('test').frame)
    note.click_text(*at)
    note.app.inp.key('end')
    quiet()
    return note


class WebNote:
    def __init__(self, app, frame):
        self.app = app
        self.frame = frame

    @property
    def box(self):
        return extents(self.frame)

    def button(self, label):
        return wait_until(lambda: next(
            (b for b in find_all(self.frame, lambda a: role(a) in ('button', 'push button'))
             if showing(b) and name(b) == label), None), what=f'button {label!r}')

    def press(self, label):
        self.app.inp.click(*center(self.button(label)))
        quiet()

    def text_point(self, dx, dy):
        """The screen point dx and dy from the top left of the text: below the
        title bar (--bar-h), inside the editor's padding (note.css). Taken
        from the window, as WebKit names the editor otherwise on 22.04."""
        x, y, _w, _h = self.box
        return x + 12 + dx, y + 34 + 8 + dy

    def click_text(self, dx, dy, button=1):
        """Click the text, dx and dy from the editor's top left."""
        self.app.inp.click(*self.text_point(dx, dy), button=button)
        quiet()

    def buttons(self):
        """The names of the buttons shown."""
        return [name(b) for b in find_all(self.frame, lambda a: role(a) in ('button', 'push button'))
                if showing(b)]

    def find_button(self, text):
        """A button whose name holds text, such as a code block's Copy."""
        return wait_until(lambda: next(
            (b for b in find_all(self.frame, lambda a: role(a) in ('button', 'push button'))
             if text in name(b)), None), what=f'a button with {text!r}')


def _shows_menu(window):
    # WebKit 2.50 (22.04) leaves out the menu around the items.
    return role(window) == 'window' and find_all(
        window, lambda a: role(a) == 'menu item' and showing(a), limit=30)


def menu(app, timeout=5):
    """The popup window while it shows a menu."""
    return wait_until(lambda: next((w for w in app.windows() if _shows_menu(w)), None),
                      timeout, 'a menu')


def menu_open(app):
    return any(_shows_menu(w) for w in app.windows())


def menu_items(app):
    return [a for a in find_all(menu(app), lambda a: role(a) == 'menu item') if showing(a)]


def choose(app, label):
    """Click the menu item whose name starts with label."""
    item = wait_until(lambda: next((a for a in menu_items(app) if name(a).startswith(label)), None),
                      what=f'menu item {label!r}')
    app.inp.click(*center(item))
    quiet()


def menu_button(app, label):
    """A button inside the menu, such as a color swatch or A+."""
    return wait_until(lambda: next(
        (b for b in find_all(menu(app), lambda a: role(a) in ('button', 'push button'))
         if showing(b) and (name(b) == label or (b.get_description() or '') == label)), None),
        what=f'menu button {label!r}')


def brief(node):
    """A block as kind(content), text as 'text'[marks], a to-do item as todo
    or done."""
    kind = node['type']
    if kind == 'text':
        marks = ','.join(m['type'] for m in node.get('marks', []))
        return repr(node['text']) + (f'[{marks}]' if marks else '')
    if kind == 'list_item' and (node.get('attrs') or {}).get('checked') is not None:
        kind = 'done' if node['attrs']['checked'] else 'todo'
    if kind == 'expand' and (node.get('attrs') or {}).get('open') is False:
        kind = 'expand[closed]'
    inner = ' '.join(brief(c) for c in node.get('content', []))
    return f'{kind}({inner})'


def saved_note(app, note_id='test'):
    """The saved note by its id, which stays when it is renamed."""
    for note in app.saved():
        if note.get('id') == note_id:
            return note
    raise TestError(f'no saved note {note_id!r}')


def saved_blocks(app, note_id='test'):
    doc = saved_note(app, note_id)['doc']
    return ' '.join(brief(b) for b in doc['content'])


def assert_saved(app, expected, note_id='test', timeout=5, last_line=True):
    """The note's blocks, once saved, are as expected; without last_line,
    an empty line ending the note is left out."""
    got = None
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        quiet()
        try:
            got = saved_blocks(app, note_id)
            if not last_line:
                got = got.removesuffix(' paragraph()')
        except (OSError, ValueError, KeyError, TestError):
            pass
        if got == expected:
            return
        time.sleep(0.2)
    assert got == expected, f'saved {got!r}, expected {expected!r}'


def saved_field(app, field, expected, note_id='test', timeout=5):
    """A field of the saved note, once saved, is as expected."""
    got = None
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        quiet()
        try:
            got = saved_note(app, note_id).get(field)
        except (OSError, ValueError, TestError):
            pass
        if got == expected:
            return
        time.sleep(0.2)
    assert got == expected, f'saved {got!r}, expected {expected!r}'


__all__ = ['start', 'WebNote', 'menu', 'menu_open', 'menu_items', 'choose',
           'menu_button', 'brief', 'assert_saved', 'saved_field', '_children']


def text_holding(note, needle):
    """The innermost accessible whose own text holds needle, and where."""
    from tests.e2e.driver import Atspi
    best = None
    for acc in find_all(note.frame, lambda a: a.get_text_iface() is not None, limit=40):
        try:
            text = Atspi.Text.get_text(acc, 0, Atspi.Text.get_character_count(acc))
        except Exception:
            continue
        if needle in text:
            best = (acc, text.index(needle))
    if best is None:
        raise TestError(f'no text {needle!r}')
    return best


def attrs_at(note, needle):
    """The text attributes of needle's first character, as shown."""
    from tests.e2e.driver import Atspi
    acc, start = text_holding(note, needle)
    attrs, _s, _e = Atspi.Text.get_attribute_run(acc, start, False)
    return attrs


def ink(note, needle):
    """How dark the drawn needle is: the share of its box's pixels that are
    dark, from the screen."""
    from tests.e2e.driver import Atspi, screenshot
    acc, start = text_holding(note, needle)
    box = Atspi.Text.get_range_extents(acc, start, start + len(needle), Atspi.CoordType.SCREEN)
    pb = screenshot('/tmp/ink.png', (box.x, box.y, box.width, box.height))
    n, rowstride, data = pb.get_n_channels(), pb.get_rowstride(), pb.get_pixels()
    dark = 0
    for y in range(pb.get_height()):
        for x in range(pb.get_width()):
            i = y * rowstride + x * n
            if (data[i] + data[i + 1] + data[i + 2]) / 3 < 110:
                dark += 1
    return dark / max(1, pb.get_width() * pb.get_height())


def weights(note, needle):
    """The font weight of each character of needle, as shown."""
    from tests.e2e.driver import Atspi
    acc, start = text_holding(note, needle)
    out = []
    for i in range(start, start + len(needle)):
        attrs, _s, _e = Atspi.Text.get_attribute_run(acc, i, False)
        out.append(int(attrs.get('weight', '400')))
    return out
