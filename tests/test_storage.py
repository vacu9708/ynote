import json

from ynote.storage import load_notes, save_notes


def test_load_notes_returns_none_for_missing_file(tmp_path):
    assert load_notes(tmp_path / 'missing.json') is None


def test_load_notes_returns_none_for_invalid_json(tmp_path):
    notes_file = tmp_path / 'notes.json'
    notes_file.write_text('{not valid json')

    assert load_notes(notes_file) is None


def test_save_notes_writes_json_and_replaces_temp_file(tmp_path):
    notes_file = tmp_path / 'notes.json'
    data = [{'id': 'note-1', 'title': 'Build log', 'images': []}]

    save_notes(data, notes_file)

    assert json.loads(notes_file.read_text()) == data
    assert not notes_file.with_name(notes_file.name + '.tmp').exists()

