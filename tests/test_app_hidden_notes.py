from ynote.app import PostItApp


class StubNote:
    def __init__(self, title, sort_order=0.0, visible=False):
        self.title = title
        self.sort_order = sort_order
        self._visible = visible

    def get_visible(self):
        return self._visible


def make_app(notes):
    app = PostItApp.__new__(PostItApp)
    app.notes = notes
    app.save_calls = 0
    app.menu_rebuilds = 0
    app.save_all = lambda: setattr(app, 'save_calls', app.save_calls + 1)
    app._rebuild_indicator_menu = (
        lambda: setattr(app, 'menu_rebuilds', app.menu_rebuilds + 1)
    )
    return app


def test_hidden_notes_sort_by_order_and_title():
    app = make_app(
        {
            'b': StubNote('Beta', sort_order=1),
            'a': StubNote('Alpha', sort_order=2),
            'c': StubNote('Gamma', sort_order=0),
            'd': StubNote('Visible', sort_order=0, visible=True),
        }
    )

    assert [note_id for note_id, _ in app.hidden_notes()] == ['c', 'b', 'a']


def test_move_hidden_note_reorders_hidden_notes():
    app = make_app(
        {
            'a': StubNote('Alpha', sort_order=0),
            'b': StubNote('Beta', sort_order=1),
            'c': StubNote('Gamma', sort_order=2),
        }
    )

    app.move_hidden_note('b', -1)

    assert app.notes['b'].sort_order == 0.0
    assert app.notes['a'].sort_order == 1.0
    assert app.notes['c'].sort_order == 2.0
    assert app.save_calls == 1
    assert app.menu_rebuilds == 1


def test_hiding_a_note_puts_it_first_in_the_hidden_list():
    app = make_app(
        {
            'a': StubNote('Alpha', sort_order=0),
            'b': StubNote('Beta', sort_order=1),
            'c': StubNote('Gamma', sort_order=0, visible=True),
        }
    )

    app.notes['c']._visible = False
    app.put_first_in_hidden([app.notes['c']])

    assert [note_id for note_id, _ in app.hidden_notes()] == ['c', 'a', 'b']


def test_hiding_several_notes_puts_them_first_in_their_order():
    app = make_app(
        {
            'a': StubNote('Alpha', sort_order=0),
            'b': StubNote('Beta', sort_order=0, visible=True),
            'c': StubNote('Gamma', sort_order=0, visible=True),
        }
    )

    for note_id in ('b', 'c'):
        app.notes[note_id]._visible = False
    app.put_first_in_hidden([app.notes['b'], app.notes['c']])

    assert [note_id for note_id, _ in app.hidden_notes()] == ['b', 'c', 'a']


def test_a_note_that_fails_to_open_is_saved_back_unchanged(monkeypatch):
    import ynote.app as app_module

    saved = [{'id': 'ok', 'text': 'fine'}, {'id': 'bad', 'text': 'keep me'}]

    class Window:
        def __init__(self, app, data):
            if data['id'] == 'bad':
                raise TypeError('cannot open')
            self.note_id = data['id']

        def to_dict(self):
            return {'id': self.note_id, 'text': 'fine'}

    written = []
    backed_up = []
    monkeypatch.setattr(app_module, 'load_notes', lambda path: saved)
    monkeypatch.setattr(app_module, 'back_up', backed_up.append)
    monkeypatch.setattr(app_module, 'save_notes',
                        lambda data, path: written.append(data))
    monkeypatch.setattr(app_module, 'NoteWindow', Window)
    monkeypatch.setattr(app_module.GLib, 'idle_add', lambda *a: None)
    app = PostItApp.__new__(PostItApp)
    app.notes = {}
    app._unopened_notes = []
    app._keep_all_images = False
    app._work_areas = lambda: ([], None)
    app._rebuild_indicator_menu = lambda: None
    app._cleanup_orphaned_images = lambda *a, **k: None

    app._load()
    app.save_all()

    assert backed_up == [app_module.NOTES_FILE]
    assert list(app.notes) == ['ok']
    assert app._keep_all_images
    assert written == [[{'id': 'ok', 'text': 'fine'},
                        {'id': 'bad', 'text': 'keep me'}]]


def _start(monkeypatch, notes_file):
    """Run the start-up load against a real notes file, with no windows."""
    import ynote.app as app_module

    class Window:
        def __init__(self, app, data):
            self.note_id = data['id']

        def to_dict(self):
            return {'id': self.note_id}

    monkeypatch.setattr(app_module, 'NOTES_FILE', str(notes_file))
    monkeypatch.setattr(app_module, 'NoteWindow', Window)
    monkeypatch.setattr(app_module.GLib, 'idle_add', lambda *a, **k: None)
    app = PostItApp.__new__(PostItApp)
    app.notes = {}
    app._unopened_notes = []
    app._keep_all_images = False
    app._work_areas = lambda: ([], None)
    app._rebuild_indicator_menu = lambda: None
    app._cleanup_orphaned_images = lambda *a, **k: None
    app.new_note = lambda: None
    app._load()
    return app


def test_starting_with_notes_keeps_a_copy_of_them_as_the_backup(tmp_path, monkeypatch):
    notes = tmp_path / 'notes.json'
    notes.write_text('[{"id": "a"}, {"id": "b"}]')

    _start(monkeypatch, notes)

    assert (tmp_path / 'notes.json.bak').read_text() == notes.read_text()


def test_an_empty_notes_file_does_not_replace_a_good_backup(tmp_path, monkeypatch):
    # After notes were lost, starting Ynote again to look must not overwrite
    # the copy of them with the empty file.
    (tmp_path / 'notes.json.bak').write_text('[{"id": "a"}]')
    notes = tmp_path / 'notes.json'
    notes.write_text('[]')

    _start(monkeypatch, notes)
    _start(monkeypatch, notes)

    assert (tmp_path / 'notes.json.bak').read_text() == '[{"id": "a"}]'


def test_an_unreadable_notes_file_does_not_replace_a_good_backup(tmp_path, monkeypatch):
    (tmp_path / 'notes.json.bak').write_text('[{"id": "a"}]')
    notes = tmp_path / 'notes.json'
    notes.write_text('{this is not json')

    _start(monkeypatch, notes)

    assert (tmp_path / 'notes.json.bak').read_text() == '[{"id": "a"}]'
    assert not notes.exists()
    assert list(tmp_path.glob('notes.json.broken-*'))


def test_quitting_closes_an_open_dialog_so_its_loop_ends(monkeypatch):
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk

    # A dialog's run() keeps its own loop going until the dialog closes.
    dialog = Gtk.Dialog()
    closed = []
    dialog.connect('destroy', lambda _d: closed.append(True))
    app = make_app({})
    app.save_all = lambda include_history=True: None
    app.release = lambda: None
    monkeypatch.setattr(Gtk.Application, 'quit', lambda self: None)

    app.quit_app()

    assert closed == [True]
