import datetime
import json

import pytest

from ynote.storage import (
    UnreadableNotesError, load_notes, save_notes, set_aside,
)


def test_load_notes_returns_none_for_missing_file(tmp_path):
    assert load_notes(tmp_path / 'missing.json') is None


def test_load_notes_rejects_invalid_json(tmp_path):
    notes_file = tmp_path / 'notes.json'
    notes_file.write_text('[{"id": "a"}],')

    with pytest.raises(UnreadableNotesError):
        load_notes(notes_file)


def test_load_notes_rejects_json_that_is_not_a_list_of_notes(tmp_path):
    notes_file = tmp_path / 'notes.json'
    for content in ('{"id": "a"}', '["a"]'):
        notes_file.write_text(content)
        with pytest.raises(UnreadableNotesError):
            load_notes(notes_file)


def test_load_notes_accepts_an_empty_list(tmp_path):
    notes_file = tmp_path / 'notes.json'
    notes_file.write_text('[]')

    assert load_notes(notes_file) == []


def test_set_aside_keeps_the_damaged_file_under_a_timestamped_name(tmp_path):
    notes_file = tmp_path / 'notes.json'
    notes_file.write_text('damaged')

    kept = set_aside(notes_file, now=datetime.datetime(2026, 11, 17, 15, 30, 12))

    assert kept == str(tmp_path / 'notes.json.broken-20261117-153012')
    assert not notes_file.exists()
    assert (tmp_path / 'notes.json.broken-20261117-153012').read_text() == 'damaged'


def test_save_notes_writes_json_and_replaces_temp_file(tmp_path):
    notes_file = tmp_path / 'notes.json'
    data = [{'id': 'note-1', 'title': 'Build log', 'images': []}]

    save_notes(data, notes_file)

    assert json.loads(notes_file.read_text()) == data
    assert not notes_file.with_name(notes_file.name + '.tmp').exists()



def test_back_up_copies_the_file_next_to_it_and_replaces_an_old_copy(tmp_path):
    from ynote.storage import back_up

    notes = tmp_path / 'notes.json'
    notes.write_text('[{"id": "new"}]')
    (tmp_path / 'notes.json.bak').write_text('[{"id": "old"}]')

    kept = back_up(notes)

    assert kept == str(tmp_path / 'notes.json.bak')
    assert (tmp_path / 'notes.json.bak').read_text() == '[{"id": "new"}]'
    assert notes.read_text() == '[{"id": "new"}]'
    assert not (tmp_path / 'notes.json.bak.tmp').exists()
