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
