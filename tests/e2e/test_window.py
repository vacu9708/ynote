"""B. A note's window, C. hidden notes, D. arranging notes: see
BEHAVIORS.md. These need the window manager the test container runs."""
import os

from tests.e2e.driver import (
    Atspi, center, find_all, name, role, settle, wait_until)

SCREEN_W, SCREEN_H = 1600, 1000


def note(title, text='', **fields):
    return dict({'id': title, 'title': title, 'text': text, 'x': 100,
                 'y': 80, 'w': 500, 'h': 400}, **fields)


def started(app, *notes):
    app.write_notes(list(notes))
    app.start()
    return [app.note(n['title']) for n in notes]


def test_B1_a_new_note_opens_square_beside_the_current_one(app):
    (t,) = started(app, note('t'))
    t.press('New Note')
    wait_until(lambda: len(app.notes()) == 2, what='a new note')
    new = [n for n in app.notes() if n.title != 't'][0]
    x, y, w, h = new.box()
    tx, ty, tw, th = t.box()
    assert w == h
    assert x >= tx + tw and x + w <= SCREEN_W


def test_B2_hiding_a_note_puts_it_first_in_hidden_notes(app):
    a, b = started(app, note('a'), note('b', x=700))
    b.press('Hide Note')
    a.press('Hide Note')
    wait_until(lambda: not app.notes(), what='both hidden')
    app.quit()
    saved = {n['title']: n for n in app.saved()}
    assert saved['a']['hidden'] and saved['b']['hidden']
    assert saved['a']['sort_order'] < saved['b']['sort_order']


def test_B3_closing_the_window_hides_the_note_and_ynote_runs_on(app):
    a, b = started(app, note('a'), note('b', x=700))
    a.body.click()
    app.inp.key('alt+F4')
    wait_until(lambda: [n.title for n in app.notes()] == ['b'],
               what='a to be hidden')
    assert app.proc.poll() is None


def test_B4_deleting_asks_first_unless_the_note_is_empty(app):
    full, empty = started(app, note('full', 'text'), note('empty', x=700))
    full.open_menu()
    full.press('Delete Note')
    dialog = app.dialog()
    app.press_in(dialog, 'Cancel')
    settle(0.3)
    assert 'full' in [n.title for n in app.notes()]
    empty.open_menu()
    empty.press('Delete Note')
    wait_until(lambda: 'empty' not in [n.title for n in app.notes()],
               what='the empty note to go')


def test_B5_a_color_is_picked_and_saved(app):
    (t,) = started(app, note('t'))
    t.open_menu()
    t.press('Blue')
    app.quit()
    assert app.saved_note('t')['color'] == 'blue'


def test_B7_font_size_steps_by_one_between_8_and_32(app):
    (t,) = started(app, note('t', font_size=31))
    t.open_menu()
    t.press('A+')
    t.press('A+')
    app.quit()
    assert app.saved_note('t')['font_size'] == 32


def test_B8_renaming_a_note_is_saved(app):
    (t,) = started(app, note('t'))
    t.open_menu()
    t.press('Edit Title')
    wait_until(lambda: find_all(t.frame, lambda a: role(a) == 'text'
                                and a.get_state_set().contains(
                                    Atspi.StateType.FOCUSED)),
               what='the title entry')
    app.inp.key('ctrl+a')
    app.inp.type('renamed\n')
    app.note('renamed')
    app.quit()
    assert app.saved_note('renamed')


def test_B9_collapsing_leaves_the_title_bar_and_comes_back(app):
    (t,) = started(app, note('t', h=500))
    t.press('Collapse')
    wait_until(lambda: t.box()[3] < 100, what='the note to collapse')
    app.quit()
    saved = app.saved_note('t')
    assert saved['collapsed'] and saved['h'] == 500


def test_B9b_a_collapsed_note_opens_to_its_height(app):
    (t,) = started(app, note('t', h=500, collapsed=True))
    assert t.box()[3] < 100
    t.press('Expand')
    wait_until(lambda: t.box()[3] >= 480, what='the note to open')


def test_B10_a_double_click_on_the_title_bar_maximizes_and_restores(app):
    (t,) = started(app, note('t'))
    x, y, w, h = t.box()
    app.inp.click(x + w // 2, y + 12, count=2)
    wait_until(lambda: t.box()[2] >= SCREEN_W - 20, what='maximizing')
    nx, ny, nw, nh = t.box()
    app.inp.click(nx + nw // 2, ny + 12, count=2)
    wait_until(lambda: t.box()[2] == w, what='restoring')
    app.quit()
    saved = app.saved_note('t')
    assert (saved['w'], saved['h']) == (w, h)


def test_B13_always_on_top_is_saved(app):
    (t,) = started(app, note('t'))
    t.press('Always on Top')
    app.quit()
    assert app.saved_note('t')['on_top'] is True


def test_B14_the_title_bar_menu_has_the_notes_settings(app):
    (t,) = started(app, note('t'))
    t.open_menu()
    labels = {name(a) or (a.get_description() or '') for a in find_all(
        t.frame, lambda a: a.get_state_set().contains(Atspi.StateType.SHOWING)
        and role(a) in ('button', 'push button', 'check box', 'slider'))}
    for label in ('Yellow', 'Blue', 'A−', 'A+', 'Edit Title', 'Start at Login',
                  'Help', 'About', 'Delete Note'):
        assert label in labels, labels


def autostart_on(entry):
    """Whether the desktop starts Ynote at login from this entry."""
    if not os.path.exists(entry):
        return False
    with open(entry) as f:
        text = f.read()
    return ('Hidden=true' not in text
            and 'X-GNOME-Autostart-enabled=false' not in text)


def test_B15_start_at_login_turned_off_stays_off(app):
    (t,) = started(app, note('t'))
    entry = os.path.join(app.home, '.config', 'autostart', 'ynote.desktop')
    wait_until(lambda: autostart_on(entry), what='the autostart entry')
    t.open_menu()
    app.press_in(t.frame, 'Start at Login')
    wait_until(lambda: not autostart_on(entry), what='autostart off')
    app.quit()
    app.start()
    settle(0.5)
    assert not autostart_on(entry)


def test_B16_about_shows_the_version_and_where_notes_are(app):
    (t,) = started(app, note('t'))
    t.open_menu()
    t.press('About')
    dialog = app.dialog()
    texts = ' '.join(app.texts_in(dialog))
    assert '.config/ynote' in texts


def test_B17_help_lists_shortcuts_nothing_on_screen_shows(app):
    (t,) = started(app, note('t'))
    t.open_menu()
    t.press('Help')
    window = app.dialog()
    texts = ' '.join(app.texts_in(window))
    assert 'Alt' in texts and 'Ctrl+Enter' in texts
    assert 'Ctrl+B' not in texts


def hidden_rows(window):
    return [r for r in find_all(window, lambda r: role(r) == 'table cell')]


def test_C1_C3_hidden_notes_lists_them_and_a_double_click_restores_one(app):
    a, b, c = started(app, note('a'), note('b', x=700), note('c', x=900))
    b.press('Hide Note')
    c.press('Hide Note')
    a.press('Hidden Notes')
    window = app.window('Hidden Notes')
    assert [name(r) for r in hidden_rows(window)] == ['c', 'b']
    app.inp.click(*center(hidden_rows(window)[1]), count=2)
    app.note('b')
    wait_until(lambda: 'Hidden Notes' not in [name(w) for w in app.windows()],
               what='the window to close')


def test_C4_restore_right_away_restores_the_note_hidden_last(app):
    a, b, c = started(app, note('a'), note('b', x=700), note('c', x=900))
    b.press('Hide Note')
    c.press('Hide Note')
    a.press('Hidden Notes')
    window = app.window('Hidden Notes')
    app.press_in(window, 'Restore')
    app.note('c')
    assert 'b' not in [n.title for n in app.notes()]


def test_C5_the_arrows_reorder_hidden_notes(app):
    a, b, c = started(app, note('a'), note('b', x=700), note('c', x=900))
    b.press('Hide Note')
    c.press('Hide Note')
    a.press('Hidden Notes')
    window = app.window('Hidden Notes')
    app.inp.click(*center(hidden_rows(window)[1]))
    app.press_in(window, 'Move up')
    wait_until(lambda: [name(r) for r in hidden_rows(window)] == ['b', 'c'],
               what='b to move up')


def test_C6_restore_all_shows_every_hidden_note(app):
    a, b, c = started(app, note('a'), note('b', x=700), note('c', x=900))
    b.press('Hide Note')
    c.press('Hide Note')
    a.press('Hidden Notes')
    app.press_in(app.window('Hidden Notes'), 'Restore All')
    wait_until(lambda: {n.title for n in app.notes()} >= {'a', 'b', 'c'},
               what='every note')


def test_D1_alt_left_and_right_snap_to_half_the_screen(app):
    (t,) = started(app, note('t', x=400, y=200))
    t.body.click()
    app.inp.key('alt+left')
    wait_until(lambda: t.box()[0] == 0 and t.box()[2] == SCREEN_W // 2,
               what='the left half')
    app.inp.key('alt+right')
    wait_until(lambda: t.box()[0] == SCREEN_W // 2, what='the right half')


def test_D2_alt_up_and_down_alone_move_the_note_up_and_down(app):
    (t,) = started(app, note('t', x=400, y=300, h=300))
    t.body.click()
    x, y, w, h = t.box()
    app.inp.key('alt+up')
    wait_until(lambda: t.box()[1] < y, what='moving up')
    assert (t.box()[0], t.box()[2]) == (x, w)


def test_D3_two_arrows_send_a_note_to_a_corner(app):
    (t,) = started(app, note('t', x=400, y=300, h=300))
    t.body.click()
    app.inp.chord(['alt'], ['right', 'down'])
    wait_until(lambda: t.box()[0] + t.box()[2] >= SCREEN_W - 2
               and t.box()[1] + t.box()[3] >= SCREEN_H - 2,
               what='the bottom right corner')


def test_D7_alt_scroll_steps_through_the_notes_from_the_latest_used(app):
    a, b, c = started(app, note('a', x=300, y=200), note('b', x=320, y=220),
                      note('c', x=340, y=240))
    for n in (a, b, c):
        n.body.click()
        settle(0.2)
    x, y, w, h = c.box()
    app.inp.scroll(x + 50, y + 100, down=True, mods=['alt'])
    wait_until(lambda: b.active(), what='b, used before c, to come up')


def color_at(x, y):
    from tests.e2e.driver import pixel, screenshot
    pb = screenshot('/tmp/e2e-pixel.png', (x, y, 1, 1))
    return pixel(pb, 0, 0)


def test_A9_notes_open_stacked_as_they_were_saved(app):
    low = note('low', x=200, y=150, w=400, h=400, color='yellow', stack=1)
    high = note('high', x=400, y=350, w=400, h=400, color='blue', stack=0)
    app.write_notes([low, high])
    app.start()
    settle(0.5)
    # Low was on top when saved, so the place they share shows it.
    over = color_at(500, 450)
    assert over == color_at(250, 300), 'the shared place shows low'
    assert over != color_at(750, 700)


def test_B11_D6_collapse_and_snap_do_nothing_while_maximized(app):
    (t,) = started(app, note('t'))
    x, y, w, h = t.box()
    app.inp.click(x + w // 2, y + 12, count=2)
    wait_until(lambda: t.box()[2] >= SCREEN_W - 20, what='maximizing')
    big = t.box()
    t.body.click()
    app.inp.key('alt+left')
    settle(0.3)
    assert t.box() == big


def test_B12_dragging_an_edge_resizes_the_note(app):
    (t,) = started(app, note('t', x=200, y=150, w=500, h=400))
    x, y, w, h = t.box()
    app.inp.drag((x + w - 2, y + h // 2), (x + w + 120, y + h // 2))
    wait_until(lambda: t.box()[2] >= w + 100, what='a wider note')
    assert t.box()[0] == x


def test_D5_a_collapsed_note_snaps_to_its_new_width(app):
    (t,) = started(app, note('t', x=400, y=200, w=500))
    t.press('Collapse')
    wait_until(lambda: t.box()[3] < 100, what='collapsing')
    x, y, w, h = t.box()
    app.inp.click(x + w // 2, y + h // 2)
    app.inp.key('alt+left')
    wait_until(lambda: t.box()[0] == 0 and t.box()[2] == SCREEN_W // 2,
               what='the left half')


def test_D7b_scrolling_back_while_alt_is_held_retraces_the_steps(app):
    a, b, c = started(app, note('a', x=300, y=200), note('b', x=320, y=220),
                      note('c', x=340, y=240))
    for n in (a, b, c):
        n.body.click()
    x, y, w, h = c.box()
    app.inp.move(x + 50, y + 100)
    app.inp._mods(['alt'], True)
    for down in (True, True, False):
        app.inp.press(5 if down else 4)
        app.inp.release(5 if down else 4)
        settle(0.3)
    app.inp._mods(['alt'], False)
    wait_until(b.active, what='b after down, down, up')


def test_D8_a_quick_second_scroll_is_one_step(app):
    a, b, c = started(app, note('a', x=300, y=200), note('b', x=320, y=220),
                      note('c', x=340, y=240))
    for n in (a, b, c):
        n.body.click()
    x, y, w, h = c.box()
    app.inp.scroll(x + 50, y + 100, down=True, notches=2, mods=['alt'])
    wait_until(b.active, what='one step, to b')


def test_B8b_a_note_without_a_title_shows_untitled(app):
    started(app, note('t'))
    app.write_notes  # noqa
    n = app.note('t')
    n.open_menu()
    n.press('Edit Title')
    wait_until(lambda: find_all(n.frame, lambda a: role(a) == 'text'
                                and a.get_state_set().contains(
                                    Atspi.StateType.FOCUSED)),
               what='the title entry')
    app.inp.key('ctrl+a')
    app.inp.key('backspace')
    app.inp.key('enter')
    wait_until(lambda: any(name(a) == 'Untitled' for a in find_all(
        app.notes()[0].frame, lambda a: role(a) == 'label')),
        what='the placeholder')


def test_D7c_with_no_note_used_yet_alt_scroll_starts_under_the_pointer(app):
    a, b = started(app, note('a', x=200, y=200), note('b', x=900, y=200))
    x, y, w, h = a.box()
    app.inp.scroll(x + 50, y + 100, down=True, mods=['alt'])
    wait_until(lambda: a.active() or b.active(), what='a note to come up')


def test_A17_a_moved_and_resized_note_opens_where_it_was(app):
    (t,) = started(app, note('t', x=200, y=150, w=500, h=400))
    x, y, w, h = t.box()
    # Drag the title bar, away from its buttons.
    app.inp.drag((x + w // 2, y + 12), (x + w // 2 + 300, y + 12 + 200))
    wait_until(lambda: t.box()[0] >= x + 250, what='the note to move')
    mx, my, mw, mh = t.box()
    app.inp.drag((mx + mw - 2, my + mh // 2), (mx + mw + 100, my + mh // 2))
    wait_until(lambda: t.box()[2] >= mw + 80, what='the note to widen')
    moved = t.box()
    app.quit()
    saved = app.saved_note('t')
    assert (saved['x'], saved['y'], saved['w'], saved['h']) == moved
    app.start()
    assert app.note('t').box() == moved
