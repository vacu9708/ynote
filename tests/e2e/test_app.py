"""A. Starting, saving, and files: see BEHAVIORS.md."""
import glob
import json
import os
import subprocess

from tests.e2e.driver import settle, wait_until


def note(title, text='', **fields):
    return dict({'id': title, 'title': title, 'text': text, 'x': 100,
                 'y': 80, 'w': 500, 'h': 400}, **fields)


def test_A1_with_no_notes_a_new_note_opens_at_the_pointer(app):
    app.inp.move(700, 500)
    app.start()
    notes = app.notes()
    assert len(notes) == 1
    x, y, w, h = notes[0].box()
    assert x <= 700 <= x + w and y <= 500 <= y + h


def test_A2_one_hidden_note_and_none_shown_opens_it_at_the_pointer(app):
    app.write_notes([note('only', 'text', hidden=True)])
    app.inp.move(900, 600)
    app.start()
    x, y, w, h = app.note('only').box()
    assert x <= 900 <= x + w and y <= 600 <= y + h


def test_A3_several_hidden_notes_and_none_shown_list_them(app):
    app.write_notes([note('a', hidden=True), note('b', hidden=True)])
    app.start()
    app.window('Hidden Notes')
    assert not app.notes() or all(n.title == 'Hidden Notes'
                                  for n in app.notes())


def test_A4_a_change_is_saved_without_quitting(app):
    app.write_notes([note('t')])
    app.start()
    app.note('t').body.click()
    app.inp.type('saved text')
    wait_until(lambda: 'saved text' in app.saved_note('t')['text'],
               timeout=10, what='the note to be saved')


def test_A5_starting_keeps_a_copy_of_the_notes_as_the_backup(app):
    app.write_notes([note('t', 'kept')])
    app.start()
    with open(app.notes_file + '.bak', encoding='utf-8') as f:
        assert json.load(f)[0]['text'] == 'kept'


def test_A6_an_empty_notes_file_does_not_replace_a_good_backup(app):
    os.makedirs(app.conf)
    with open(app.notes_file + '.bak', 'w') as f:
        json.dump([note('t', 'precious')], f)
    with open(app.notes_file, 'w') as f:
        json.dump([], f)
    app.start()
    with open(app.notes_file + '.bak') as f:
        assert json.load(f)[0]['text'] == 'precious'


def test_A7_an_unreadable_notes_file_is_kept_aside_with_a_warning(app):
    os.makedirs(app.conf)
    with open(app.notes_file, 'w') as f:
        f.write('{ not json')
    app.start()
    dialog = app.dialog()
    assert any('could not read' in t for t in app.texts_in(dialog))
    broken = glob.glob(app.notes_file + '.broken-*')
    assert len(broken) == 1
    with open(broken[0]) as f:
        assert f.read() == '{ not json'


def test_A8_a_note_that_fails_to_open_is_saved_back_unchanged(app):
    bad = note('bad', 'x', font_size='not a number')
    app.write_notes([note('good', 'fine'), bad])
    app.start()
    app.dialog()
    app.quit()
    saved = {n['title']: n for n in app.saved()}
    assert saved['bad'] == bad
    assert saved['good']['text'] == 'fine'


def test_A10_notes_are_saved_readably_with_korean_as_it_is(app):
    app.write_notes([note('t')])
    app.start()
    app.note('t').body.click()
    app.inp.type('한글 **굵게**')
    app.quit()
    with open(app.notes_file, encoding='utf-8') as f:
        raw = f.read()
    assert '한글' in raw and '\\u' not in raw
    assert any(line.strip().startswith('[') and line.strip().endswith(']')
               and ',' in line for line in raw.splitlines())


def test_A12_ynote_version_prints_the_version():
    out = subprocess.run(['ynote', '--version'], capture_output=True,
                         text=True, timeout=20)
    assert out.stdout.startswith('Ynote ')


def test_A13_quitting_with_a_dialog_open_quits_and_keeps_the_note(app):
    app.write_notes([note('t', 'some text')])
    app.start()
    n = app.note('t')
    n.open_menu()
    n.press('Delete Note')
    app.dialog()
    app.quit()
    assert app.proc.poll() is not None
    assert app.saved_note('t')['text'] == 'some text'


def test_A14_a_note_saved_off_screen_is_moved_onto_it(app):
    app.write_notes([note('far', x=5000, y=4000)])
    app.start()
    x, y, w, h = app.note('far').box()
    assert 0 <= x < 1600 and 0 <= y < 1000


def test_A11_starting_ynote_again_keeps_one_running(app):
    app.write_notes([note('t')])
    app.start()
    env = dict(os.environ, HOME=app.home)
    second = subprocess.run(app.command, env=env, timeout=20)
    assert second.returncode == 0
    settle(0.5)
    assert len(app.notes()) == 1
    assert app.proc.poll() is None
