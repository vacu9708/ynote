"""Driving a note of Ynote 2.0, whose window is a web page: its buttons and
editor as the page shows them through AT-SPI, the popup window that shows
its menus, and the content it saves (notes-2.json)."""
import time

from tests.e2e.driver import (
    TestError, _children, center, extents, find_all, name, quiet, role,
    showing, wait_until)

NOTE = {'id': 'test', 'title': 'test', 'text': '', 'x': 100, 'y': 80,
        'w': 420, 'h': 360}


def start(app, text='', **fields):
    """Ynote 2.0 with one note titled test, as 1.x saved it, clicked into at
    the end of its first line."""
    app.write_notes([dict(NOTE, text=text, **fields)])
    app.start()
    note = WebNote(app, app.note('test').frame)
    note.click_text(0, 10)
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


def assert_saved(app, expected, note_id='test', timeout=5):
    """The note's blocks, once saved, are as expected."""
    got = None
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        quiet()
        try:
            got = saved_blocks(app, note_id)
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
