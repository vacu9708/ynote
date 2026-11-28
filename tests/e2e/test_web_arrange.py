"""B. A note's window, C. hidden notes, D. arranging notes, in Ynote 2.0:
see BEHAVIORS.md. These need the window manager the test container runs."""
import os

import pytest

from tests.e2e.driver import settle, wait_until
from tests.e2e.test_window import autostart_on
from tests.e2e.web import WebNote, choose, menu_items, saved_field, saved_note

pytestmark = [pytest.mark.web]

SCREEN_W, SCREEN_H = 1600, 1000


def note(title, text='', **fields):
    return dict({'id': title, 'title': title, 'text': text or title, 'x': 100, 'y': 80,
                 'w': 500, 'h': 400}, **fields)


def started(app, *notes):
    app.write_notes(list(notes))
    app.start()
    return [WebNote(app, app.note(n['title']).frame) for n in notes]


def titles(app):
    return sorted(n.title for n in app.notes())


def into(n):
    """Click into the note's text, so its keys go to it."""
    n.click_text(5, 8)


def test_B1_web_a_new_note_opens_square_beside_the_current_one(app):
    (t,) = started(app, note('t'))
    into(t)
    app.inp.key('ctrl+n')
    wait_until(lambda: len(app.notes()) == 2, what='a new note')
    new = [n for n in app.notes() if n.title != 't'][0]
    x, y, w, h = new.box()
    tx, ty, tw, th = t.box
    assert w == h
    assert x >= tx + tw and x + w <= SCREEN_W


def test_B2_web_hiding_a_note_puts_it_first_in_hidden_notes(app):
    a, b = started(app, note('a'), note('b', x=700))
    b.press('Hide note')
    a.press('Hide note')
    wait_until(lambda: not app.notes(), what='both hidden')
    app.quit()
    saved = {n['title']: n for n in app.saved()}
    assert saved['a']['hidden'] and saved['b']['hidden']
    assert saved['a']['sort_order'] < saved['b']['sort_order']


def test_B3_web_closing_the_window_hides_the_note_and_ynote_runs_on(app):
    a, b = started(app, note('a'), note('b', x=700))
    into(a)
    app.inp.key('alt+F4')
    wait_until(lambda: titles(app) == ['b'], what='a to be hidden')
    assert app.proc.poll() is None
    saved_field(app, 'hidden', True, note_id='a')


def test_B10_web_a_double_click_on_the_title_bar_maximizes_and_restores(app):
    (t,) = started(app, note('t'))
    x, y, w, h = t.box
    app.inp.click(x + 150, y + 16, count=2)
    wait_until(lambda: t.box[2] >= SCREEN_W - 20, what='maximizing')
    nx, ny, nw, nh = t.box
    # A while apart and elsewhere, or the clicks, at the same place in the
    # window, would count as a triple click.
    settle(0.6)
    app.inp.click(nx + 400, ny + 16, count=2)
    wait_until(lambda: t.box[2] == w, what='restoring')
    app.quit()
    saved = saved_note(app, 't')
    assert (saved['w'], saved['h']) == (w, h)


def test_B11_D6_web_collapse_and_snap_do_nothing_while_maximized(app):
    (t,) = started(app, note('t'))
    x, y, w, h = t.box
    app.inp.click(x + 150, y + 16, count=2)
    wait_until(lambda: t.box[2] >= SCREEN_W - 20, what='maximizing')
    big = t.box
    into(t)
    app.inp.key('alt+left')
    settle(0.3)
    assert t.box == big
    t.press('Collapse')
    settle(0.3)
    assert t.box == big


def test_B12_web_dragging_an_edge_resizes_the_note(app):
    (t,) = started(app, note('t', x=200, y=150, w=500, h=400))
    x, y, w, h = t.box
    app.inp.drag((x + w - 2, y + h // 2), (x + w + 120, y + h // 2))
    wait_until(lambda: t.box[2] >= w + 100, what='a wider note')
    assert t.box[0] == x
    x, y, w, h = t.box
    app.inp.drag((x + w // 2, y + h - 2), (x + w // 2, y + h + 80))
    wait_until(lambda: t.box[3] >= h + 60, what='a taller note')


def test_B13_web_always_on_top_is_saved(app):
    (t,) = started(app, note('t'))
    t.press('Always on top')
    app.quit()
    assert saved_note(app, 't')['on_top'] is True


def test_B15_web_start_at_login_turned_off_stays_off(app):
    (t,) = started(app, note('t'))
    entry = os.path.join(app.home, '.config', 'autostart', 'ynote.desktop')
    wait_until(lambda: autostart_on(entry), what='the autostart entry')
    t.press('Note menu')
    choose(app, 'Start at login')
    wait_until(lambda: not autostart_on(entry), what='autostart off')
    app.quit()
    app.start()
    settle(0.5)
    assert not autostart_on(entry)


def test_C7_web_the_note_menu_tells_how_many_notes_are_hidden(app):
    a, b, c = started(app, note('a', x=40, w=400), note('b', x=500, w=400), note('c', x=960, w=400))
    b.press('Hide note')
    c.press('Hide note')
    a.press('Note menu')
    row = next(i for i in menu_items(app) if i.get_name().startswith('Hidden notes'))
    assert '2' in row.get_name(), row.get_name()


def test_D1_web_alt_left_and_right_snap_to_half_the_screen(app):
    (t,) = started(app, note('t', x=400, y=200))
    into(t)
    app.inp.key('alt+left')
    wait_until(lambda: t.box[0] == 0 and t.box[2] == SCREEN_W // 2, what='the left half')
    app.inp.key('alt+right')
    wait_until(lambda: t.box[0] == SCREEN_W // 2, what='the right half')


def test_D2_web_alt_up_and_down_alone_move_the_note_up_and_down(app):
    (t,) = started(app, note('t', x=400, y=300, h=300))
    into(t)
    x, y, w, h = t.box
    app.inp.key('alt+up')
    wait_until(lambda: t.box[1] < y, what='moving up')
    assert (t.box[0], t.box[2]) == (x, w)
    app.inp.key('alt+down')
    wait_until(lambda: t.box[1] == y, what='moving back down')


def test_D3_web_two_arrows_send_a_note_to_a_corner(app):
    (t,) = started(app, note('t', x=400, y=300, h=300))
    into(t)
    app.inp.chord(['alt'], ['right', 'down'])
    wait_until(lambda: t.box[0] + t.box[2] >= SCREEN_W - 2
               and t.box[1] + t.box[3] >= SCREEN_H - 2, what='the bottom right corner')


def test_D5_web_a_collapsed_note_snaps_to_its_new_width(app):
    (t,) = started(app, note('t', x=400, y=200, w=500))
    t.press('Collapse')
    wait_until(lambda: t.box[3] < 60, what='collapsing')
    x, y, w, h = t.box
    app.inp.click(x + 150, y + h // 2)
    app.inp.key('alt+left')
    wait_until(lambda: t.box[0] == 0 and t.box[2] == SCREEN_W // 2, what='the left half')
    assert t.box[3] < 60


def test_B8b_web_a_note_without_a_title_shows_untitled(app):
    (t,) = started(app, note('t'))
    into(t)
    app.inp.key('F2')
    app.inp.key('ctrl+a')
    app.inp.key('backspace')
    app.inp.key('enter')
    saved_field(app, 'title', '', note_id='t')
    from tests.e2e.driver import find_all, name, showing
    wait_until(lambda: find_all(t.frame, lambda a: name(a) == 'Untitled' and showing(a)),
               what='the title shown as Untitled')
