"""A. Starting, saving, and files, in Ynote 2.0, whose notes are saved in
notes-2.json: see BEHAVIORS.md."""
import glob
import json
import os
import subprocess

import pytest

from tests.e2e.driver import settle, wait_until
from tests.e2e.web import WebNote, assert_saved, menu, menu_items, saved_note

pytestmark = [pytest.mark.web]


def note(title, text='', **fields):
    """A note as 2.0 saves it, with one line of text."""
    content = [{'type': 'text', 'text': text}] if text else []
    return dict({'id': title, 'title': title, 'x': 100, 'y': 80, 'w': 500, 'h': 400,
                 'doc': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': content}]}},
                **fields)


def write(app, notes):
    """notes-2.json as given, raw if a string."""
    os.makedirs(app.conf, exist_ok=True)
    with open(app.notes_file, 'w', encoding='utf-8') as f:
        if isinstance(notes, str):
            f.write(notes)
        else:
            json.dump(notes, f, ensure_ascii=False)


def inside(box, x, y):
    bx, by, bw, bh = box
    return bx <= x <= bx + bw and by <= y <= by + bh


def test_A1_web_with_no_notes_a_new_note_opens_at_the_pointer(app):
    app.inp.move(700, 500)
    app.start()
    notes = app.notes()
    assert len(notes) == 1
    assert inside(notes[0].box(), 700, 500)


def test_A2_web_one_hidden_note_and_none_shown_opens_it_where_it_was(app):
    write(app, [note('only', 'text', hidden=True, x=300, y=200)])
    app.inp.move(1300, 800)
    app.start()
    assert app.note('only').box()[:2] == (300, 200)


def test_A3_web_several_hidden_notes_and_none_shown_list_them(app):
    write(app, [note('a', hidden=True), note('b', hidden=True)])
    app.inp.move(800, 500)
    app.start(wait_for_window=False)
    menu(app, timeout=15)
    names = [i.get_name() for i in menu_items(app)]
    assert any(n.startswith('a') for n in names) and any(n.startswith('b') for n in names), names
    assert not app.notes()


def test_A4_web_a_change_is_saved_without_quitting(app):
    write(app, [note('t', 'x')])
    app.start()
    n = WebNote(app, app.note('t').frame)
    n.click_text(0, 10)
    app.inp.key('end')
    app.inp.type(' saved text')
    assert_saved(app, "paragraph('x saved text')", note_id='t', timeout=10)


def test_A5_web_starting_keeps_a_copy_of_the_notes_as_the_backup(app):
    write(app, [note('t', 'kept')])
    app.start()
    with open(app.notes_file + '.bak', encoding='utf-8') as f:
        assert json.load(f)[0]['doc'] == note('t', 'kept')['doc']


def test_A5b_web_the_first_start_reads_the_notes_of_1x_and_leaves_them(app):
    app.write_notes([{'id': 'old', 'title': 'old', 'text': 'from 1.x',
                      'x': 100, 'y': 80, 'w': 500, 'h': 400}])
    one = os.path.join(app.conf, 'notes.json')
    with open(one, encoding='utf-8') as f:
        before = f.read()
    app.start()
    app.note('old')
    app.quit()
    assert_saved(app, "paragraph('from 1.x')", note_id='old')
    with open(one, encoding='utf-8') as f:
        assert f.read() == before


def test_A6_web_an_empty_notes_file_does_not_replace_a_good_backup(app):
    write(app, [])
    with open(app.notes_file + '.bak', 'w') as f:
        json.dump([note('t', 'precious')], f)
    app.start()
    with open(app.notes_file + '.bak') as f:
        assert json.load(f)[0]['doc'] == note('t', 'precious')['doc']


def test_A7_web_an_unreadable_notes_file_is_kept_aside_with_a_warning(app):
    write(app, '{ not json')
    app.start()
    dialog = app.dialog()
    assert any('could not read' in t for t in app.texts_in(dialog))
    broken = glob.glob(app.notes_file + '.broken-*')
    assert len(broken) == 1
    with open(broken[0]) as f:
        assert f.read() == '{ not json'


def test_A8_web_a_note_that_fails_to_open_is_saved_back_unchanged(app):
    bad = note('bad', 'x', font_size='not a number')
    write(app, [note('good', 'fine'), bad])
    app.start()
    app.dialog()
    app.quit()
    saved = {n['title']: n for n in app.saved()}
    assert saved['bad'] == bad
    assert saved['good']['doc'] == note('good', 'fine')['doc']


def test_A9_web_notes_open_stacked_as_they_were_saved(app):
    from tests.e2e.test_window import color_at
    low = note('low', x=200, y=150, w=400, h=400, color='yellow', stack=1)
    high = note('high', x=400, y=350, w=400, h=400, color='blue', stack=0)
    write(app, [low, high])
    app.start()
    settle(0.5)
    # Low was on top when saved, so the place they share shows it.
    over = color_at(500, 500)
    assert over == color_at(250, 300), 'the shared place shows low'
    assert over != color_at(750, 700)


def test_A10_web_notes_are_saved_readably_with_korean_as_it_is(app):
    write(app, [note('t', 'x')])
    app.start()
    n = WebNote(app, app.note('t').frame)
    n.click_text(0, 10)
    app.inp.key('end')
    app.inp.type(' 한글')
    app.quit()
    with open(app.notes_file, encoding='utf-8') as f:
        raw = f.read()
    assert '한글' in raw and '\\u' not in raw


def test_A11_web_starting_ynote_again_keeps_one_running(app):
    write(app, [note('t')])
    app.start()
    env = dict(os.environ, HOME=app.home, YNOTE_WEB='1')
    second = subprocess.run(app.command, env=env, timeout=20)
    assert second.returncode == 0
    settle(0.5)
    assert len(app.notes()) == 1
    assert app.proc.poll() is None


def test_A13_web_quitting_while_delete_asks_quits_and_keeps_the_note(app):
    write(app, [note('t', 'some text')])
    app.start()
    n = WebNote(app, app.note('t').frame)
    n.press('Note menu')
    from tests.e2e.web import choose
    choose(app, 'Delete')
    n.button('Delete')
    app.quit()
    assert app.proc.poll() is not None
    assert saved_note(app, 't')['doc'] == note('t', 'some text')['doc']


def test_A14_web_a_note_saved_off_screen_is_moved_onto_it(app):
    write(app, [note('far', x=5000, y=4000)])
    app.start()
    x, y, w, h = app.note('far').box()
    assert 0 <= x < 1600 and 0 <= y < 1000


def test_A17_web_a_moved_and_resized_note_opens_where_it_was(app):
    write(app, [note('t', x=200, y=150, w=500, h=400)])
    app.start()
    t = app.note('t')
    x, y, w, h = t.box()
    # Drag the title bar, away from its buttons.
    app.inp.drag((x + 120, y + 16), (x + 120 + 300, y + 16 + 200))
    wait_until(lambda: t.box()[0] >= x + 250, what='the note to move')
    mx, my, mw, mh = t.box()
    app.inp.drag((mx + mw - 2, my + mh // 2), (mx + mw + 100, my + mh // 2))
    wait_until(lambda: t.box()[2] >= mw + 80, what='the note to widen')
    moved = t.box()
    app.quit()
    saved = saved_note(app, 't')
    assert (saved['x'], saved['y'], saved['w'], saved['h']) == moved
    app.start()
    assert app.note('t').box() == moved
