from ynote.note_manager_window import HiddenNotesWindow


class StubApp:
    def __init__(self):
        self.shown_notes = []

    def show_note(self, note_id):
        self.shown_notes.append(note_id)


def test_restore_selected_shows_selected_note_and_closes_manager():
    app = StubApp()
    window = HiddenNotesWindow.__new__(HiddenNotesWindow)
    window.app = app
    window._selected_note_id = lambda: 'note-1'
    window.destroyed = False
    window.destroy = lambda: setattr(window, 'destroyed', True)

    window._restore_selected()

    assert app.shown_notes == ['note-1']
    assert window.destroyed is True


def test_restore_selected_without_selection_does_nothing():
    app = StubApp()
    window = HiddenNotesWindow.__new__(HiddenNotesWindow)
    window.app = app
    window._selected_note_id = lambda: None
    window.destroyed = False
    window.destroy = lambda: setattr(window, 'destroyed', True)

    window._restore_selected()

    assert app.shown_notes == []
    assert window.destroyed is False
