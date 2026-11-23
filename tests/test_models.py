from ynote.models import normalize_note_data


def test_normalize_note_data_fills_defaults_for_old_saved_notes():
    note = normalize_note_data({'id': 'note-1', 'text': 'hello'})

    assert note['id'] == 'note-1'
    assert note['title'] == ''
    assert note['text'] == 'hello'
    assert note['x'] == 200
    assert note['y'] == 200
    assert note['w'] == 200
    assert note['h'] == 300
    assert note['on_top'] is False
    assert note['hidden'] is False
    assert note['sort_order'] == 0.0
    assert note['bold_ranges'] == []
    assert note['code_ranges'] == []
    assert note['backtick_ranges'] == []
    assert note['images'] == []
    assert note['font_size'] == 14


def test_normalize_note_data_generates_missing_id_with_injected_factory():
    note = normalize_note_data({}, note_id_factory=lambda: 'generated-id')

    assert note['id'] == 'generated-id'


def test_normalize_note_data_copies_mutable_defaults():
    first = normalize_note_data({'id': 'first'})
    second = normalize_note_data({'id': 'second'})

    first['images'].append({'file': 'one.png'})
    first['bold_ranges'].append([0, 1])
    first['backtick_ranges'].append([2, 4])

    assert second['images'] == []
    assert second['bold_ranges'] == []
    assert second['backtick_ranges'] == []


def test_normalize_note_data_casts_boolean_and_integer_fields():
    note = normalize_note_data(
        {
            'id': 'note-1',
            'x': '10',
            'y': '20',
            'w': '300',
            'h': '400',
            'on_top': 1,
            'hidden': '',
            'sort_order': '2.5',
            'font_size': '18',
        }
    )

    assert note['x'] == 10
    assert note['y'] == 20
    assert note['w'] == 300
    assert note['h'] == 400
    assert note['on_top'] is True
    assert note['hidden'] is False
    assert note['sort_order'] == 2.5
    assert note['font_size'] == 18


def test_color_defaults_to_yellow_and_unknown_names_fall_back():
    assert normalize_note_data({'id': 'a'})['color'] == 'yellow'
    assert normalize_note_data({'id': 'a', 'color': 'teal'})['color'] == 'yellow'
    assert normalize_note_data({'id': 'a', 'color': 'blue'})['color'] == 'blue'


def test_opacity_defaults_to_opaque_and_is_clamped():
    assert normalize_note_data({'id': 'a'})['opacity'] == 1.0
    assert normalize_note_data({'id': 'a', 'opacity': -1})['opacity'] == 0.0
    assert normalize_note_data({'id': 'a', 'opacity': 5})['opacity'] == 1.0
    assert normalize_note_data({'id': 'a', 'opacity': '0.6'})['opacity'] == 0.6
    assert normalize_note_data({'id': 'a', 'opacity': 'x'})['opacity'] == 1.0
    assert normalize_note_data({'id': 'a', 'opacity': None})['opacity'] == 1.0


def test_collapsed_defaults_to_false():
    assert normalize_note_data({'id': 'a'})['collapsed'] is False
    assert normalize_note_data({'id': 'a', 'collapsed': 1})['collapsed'] is True
