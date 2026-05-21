import uuid


DEFAULT_NOTE = {
    'title': '',
    'text': '',
    'x': 200,
    'y': 200,
    'w': 200,
    'h': 300,
    'on_top': False,
    'hidden': False,
    'sort_order': 0.0,
    'bold_ranges': [],
    'code_ranges': [],
    'backtick_ranges': [],
    'images': [],
    'font_size': 14,
}


def normalize_note_data(data, note_id_factory=None):
    note = dict(DEFAULT_NOTE)
    note.update(dict(data or {}))

    if note_id_factory is None:
        note_id_factory = lambda: str(uuid.uuid4())

    note['id'] = note.get('id') or note_id_factory()
    note['title'] = note.get('title') or ''
    note['text'] = note.get('text') or ''
    note['on_top'] = bool(note.get('on_top', False))
    note['hidden'] = bool(note.get('hidden', False))
    note['sort_order'] = float(note.get('sort_order') or 0.0)
    note['bold_ranges'] = list(note.get('bold_ranges') or [])
    note['code_ranges'] = list(note.get('code_ranges') or [])
    note['backtick_ranges'] = list(note.get('backtick_ranges') or [])
    note['images'] = list(note.get('images') or [])
    note['font_size'] = int(note.get('font_size') or DEFAULT_NOTE['font_size'])

    for key in ('x', 'y', 'w', 'h'):
        note[key] = int(note.get(key, DEFAULT_NOTE[key]))

    return note
