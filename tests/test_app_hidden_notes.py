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


def test_tray_click_creates_note_when_none_are_visible():
    app = make_app({'a': StubNote('Hidden')})
    app._notes_raised = False
    app.new_note_calls = 0
    app.new_note = lambda: setattr(app, 'new_note_calls', app.new_note_calls + 1)

    app._on_tray_click(None)

    assert app.new_note_calls == 1
    assert app._notes_raised is True


def test_clipboard_owner_change_clears_rich_clipboard_state():
    app = make_app({})
    app._rich_clipboard = {'text': 'same text'}
    app._rich_clipboard_owned = True
    app._ignore_next_clipboard_owner_change = False

    app._on_clipboard_owner_change()

    assert app.rich_clipboard_state() is None


def test_own_clipboard_change_keeps_rich_clipboard_state_once():
    app = make_app({})
    state = {'text': 'same text'}
    app._rich_clipboard = state
    app._rich_clipboard_owned = True
    app._ignore_next_clipboard_owner_change = True

    app._on_clipboard_owner_change()

    assert app.rich_clipboard_state() == state
    assert app._ignore_next_clipboard_owner_change is False
