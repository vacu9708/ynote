from ynote.app import SWITCH_PAUSE_MS, PostItApp


class StubNote:
    def __init__(self, name):
        self.name = name
        self.active = False
        self.presented = 0

    def get_visible(self):
        return True

    def is_active(self):
        return self.active

    def present_with_time(self, _time):
        self.presented += 1


def make_app(*names):
    notes = [StubNote(n) for n in names]
    app = PostItApp.__new__(PostItApp)
    app.notes = {n.name: n for n in notes}
    app._current_note = None
    app._recent = []
    app._switch_order = None
    app._switch_index = 0
    app._switch_amount = 0.0
    app._switch_time = None
    return app, {n.name: n for n in notes}


def focus(app, notes, name):
    """What the window manager does: one note has the focus."""
    for n in notes.values():
        n.active = n.name == name
    app._on_note_focus_in(notes[name])


class Scroller:
    """Alt + scroll notches, far enough apart in time to each make a step.
    The note brought forward takes the focus, as the window manager does."""

    def __init__(self, app, notes):
        self.app, self.notes, self.time = app, notes, 1000

    def __call__(self, dy, under='A'):
        self.time += SWITCH_PAUSE_MS
        self.app.scroll_notes(self.notes[under], dy, self.time)
        current = self.app._current_note
        focus(self.app, self.notes, current.name)
        return current.name


def test_scrolling_down_goes_back_through_the_notes_used_before():
    app, notes = make_app('A', 'B', 'C')
    for name in ('C', 'B', 'A'):
        focus(app, notes, name)
    scroll = Scroller(app, notes)

    assert [scroll(1) for _ in range(3)] == ['B', 'C', 'A']


def test_the_order_holds_while_alt_is_held_and_scrolling_up_retraces_it():
    app, notes = make_app('A', 'B', 'C')
    for name in ('C', 'B', 'A'):
        focus(app, notes, name)
    scroll = Scroller(app, notes)

    assert [scroll(1), scroll(1), scroll(-1), scroll(-1)] == ['B', 'C', 'B', 'A']


def test_letting_go_of_alt_makes_the_note_stopped_on_the_latest():
    app, notes = make_app('A', 'B', 'C')
    for name in ('C', 'B', 'A'):
        focus(app, notes, name)
    scroll = Scroller(app, notes)
    scroll(1)
    scroll(1)

    app.end_note_switch()

    assert app._recent == [notes['C'], notes['A'], notes['B']]
    # So one notch goes back to the note used just before, as Alt+Tab does.
    assert scroll(1) == 'A'


def test_with_no_note_in_use_it_starts_from_the_one_under_the_pointer():
    app, notes = make_app('A', 'B', 'C')
    for name in ('C', 'B', 'A'):
        focus(app, notes, name)
    for n in notes.values():
        n.active = False

    assert Scroller(app, notes)(1, under='B') == 'C'


def test_small_scrolls_add_up_to_one_step_and_a_quick_one_is_ignored():
    app, notes = make_app('A', 'B')
    focus(app, notes, 'B')
    focus(app, notes, 'A')

    for _ in range(3):
        app.scroll_notes(notes['A'], 0.3, 1000)
    assert notes['B'].presented == 0
    app.scroll_notes(notes['A'], 0.3, 1000)
    assert notes['B'].presented == 1

    app.scroll_notes(notes['A'], 1, 1000 + SWITCH_PAUSE_MS - 1)
    assert notes['A'].presented == 0
