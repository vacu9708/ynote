"""X. A 2.0 note's window among other windows: on top, Alt+scroll, and
showing a hidden note where it was. See BEHAVIORS.md."""
import pytest

from tests.e2e.driver import Gtk, pump, settle, wait_until
from tests.e2e.web import WebNote, saved_note




def note(title, **fields):
    return dict({'id': title, 'title': title, 'text': title, 'x': 100, 'y': 80, 'w': 300, 'h': 300}, **fields)


def started(app, *notes):
    app.write_notes(list(notes))
    app.start()
    return [WebNote(app, app.note(n['title']).frame) for n in notes]


def active(note):
    """Whether the window manager has made the note the active window, as X
    tells it."""
    d = note.app.inp.d
    root = d.screen().root
    prop = root.get_full_property(d.intern_atom('_NET_ACTIVE_WINDOW'), 0)
    if not prop or not prop.value[0]:
        return False
    w = d.create_resource_object('window', prop.value[0])
    name = w.get_full_property(d.intern_atom('_NET_WM_NAME'), 0)
    return bool(name) and name.value.decode() == note.frame.get_name()


def stacking(inp):
    """The X windows of the screen, bottom to top, by their names."""
    from Xlib import X  # noqa: F401
    d = inp.d
    root = d.screen().root
    order = root.get_full_property(d.intern_atom('_NET_CLIENT_LIST_STACKING'), 0).value
    names = []
    for xid in order:
        w = d.create_resource_object('window', xid)
        prop = w.get_full_property(d.intern_atom('_NET_WM_NAME'), 0)
        names.append(prop.value.decode() if prop else '')
    return names


def test_X1_a_note_on_top_stays_above_another_apps_window(app, inp):
    (t,) = started(app, note('pinned'))
    t.press('Always on top')
    settle(0.3)
    other = Gtk.Window(title='another app')
    other.set_default_size(500, 500)
    other.move(50, 50)
    other.show_all()
    other.present()
    pump()
    settle(0.8)
    pump()
    try:
        order = stacking(inp)
        assert order.index('pinned') > order.index('another app'), order
    finally:
        other.destroy()
        pump()


def three(app):
    a, b, c = started(app, note('a', x=40, y=200), note('b', x=380, y=200), note('c', x=720, y=200))
    for n in (a, b, c):
        n.click_text(10, 8)
        settle(0.2)
    return a, b, c


def test_X2_alt_scroll_steps_through_the_notes_from_the_latest_used(app, inp):
    a, b, c = three(app)
    x, y, w, h = c.box
    inp.scroll(x + 50, y + 100, down=True, mods=['alt'])
    wait_until(lambda: active(b), what='b, used before c, to come up')


def test_X3_scrolling_back_while_alt_is_held_retraces_the_steps(app, inp):
    a, b, c = three(app)
    x, y, w, h = c.box
    inp.move(x + 50, y + 100)
    inp._mods(['alt'], True)
    for down in (True, True, False):
        inp.press(5 if down else 4)
        inp.release(5 if down else 4)
        settle(0.3)
    inp._mods(['alt'], False)
    wait_until(lambda: active(b), what='b after down, down, up')


def test_X4_a_quick_second_scroll_is_one_step(app, inp):
    a, b, c = three(app)
    x, y, w, h = c.box
    inp.scroll(x + 50, y + 100, down=True, notches=2, mods=['alt'])
    wait_until(lambda: active(b), what='one step, to b')


def test_X5_a_hidden_note_shows_again_where_it_was(app, inp):
    t, other = started(app, note('test', x=100, y=80), note('away', x=700, y=400, w=320, h=260))
    before = other.box
    other.press('Hide note')
    wait_until(lambda: saved_note(app, 'away').get('hidden') is True, what='away hidden')
    t.press('Note menu')
    from tests.e2e.web import choose
    choose(app, 'Hidden notes')
    choose(app, 'away')
    shown = WebNote(app, app.note('away').frame)
    wait_until(lambda: shown.box == before, what=f'away at {before}, not {shown.box}')


def test_X6_alt_scroll_brings_up_stacked_notes_one_after_another(app, inp):
    stacked = [note(n, x=300 + 20 * i, y=200 + 20 * i) for i, n in enumerate('abc')]
    app.write_notes(stacked)
    app.start()
    settle(0.5)
    top = app.note('c')
    x, y = 520, 420                   # inside all three
    inp.move(x, y)
    inp._mods(['alt'], True)
    seen = []
    for _ in range(2):
        inp.press(5)
        inp.release(5)
        settle(0.5)
        d = inp.d
        prop = d.screen().root.get_full_property(d.intern_atom('_NET_ACTIVE_WINDOW'), 0)
        w = d.create_resource_object('window', prop.value[0])
        seen.append(w.get_full_property(d.intern_atom('_NET_WM_NAME'), 0).value.decode())
    inp._mods(['alt'], False)
    assert len(set(seen)) == 2 and 'c' not in seen, seen
    del top


def test_X7_letting_go_of_alt_gives_the_note_stepped_to_the_focus(app, inp):
    a, b, c = three(app)
    x, y, w, h = c.box
    inp.move(x + 50, y + 100)
    inp._mods(['alt'], True)
    inp.press(5)
    inp.release(5)
    settle(0.3)
    inp._mods(['alt'], False)
    wait_until(lambda: active(b), what='b with the focus once Alt is let go')
