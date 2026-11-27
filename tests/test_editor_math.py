"""The arithmetic of the editor that needs no window: where an undone edit
ends, and the spacing that evens out lines of different fonts."""


def test_changed_end_is_where_an_edit_ends_in_the_new_text():
    from ynote.editor import changed_end

    # Undoing typed text: the cursor goes where the text was.
    assert changed_end('ab typed cd', 'ab cd') == 3
    # Redoing it: the cursor goes after the text that came back.
    assert changed_end('ab cd', 'ab typed cd') == 9
    # A line deleted from the middle, and text added to the end.
    assert changed_end('one\nzzz\nthree', 'one\nthree') == 4
    assert changed_end('one', 'one two') == 7
    # Repeated characters do not confuse the two ends.
    assert changed_end('aaa', 'aaaa') == 4
    assert changed_end('aaaa', 'aaa') == 3
    assert changed_end('', 'new') == 3
    assert changed_end('old', '') == 0


def test_even_slots_leave_a_note_of_one_font_as_it_is():
    from ynote.editor import even_slots

    base = (14.2, 3.0)
    assert even_slots([base, base, base], base, (2, 2)) == [(2, 2)] * 3
    assert even_slots([], base, (2, 2)) == []


def test_even_slots_give_every_line_the_same_room_above_and_below_the_baseline():
    from ynote.editor import even_slots

    base = (14.0, 3.0)
    tall = (17.0, 5.0)
    slots = even_slots([base, tall, base], base, (2, 2))

    # A tall line has all the room it needs, and the spacing on the other lines
    # makes up the difference, so every line takes 22 px.
    assert slots == [(3, 2), (0, 0), (3, 2)]
    for (a, d), (above, below) in zip([base, tall, base], slots):
        assert a + above == 17 and d + below == 5


def test_even_slots_never_take_less_than_a_line_of_the_notes_font():
    from ynote.editor import even_slots

    # A font only a little taller than the note's own fits in its spacing.
    base = (14.0, 3.0)
    slots = even_slots([base, (15.0, 3.5)], base, (2, 2))

    assert slots == [(2, 2), (1, 2)]


def test_even_slots_never_go_negative_for_a_line_taller_than_the_rest_need():
    from ynote.editor import even_slots

    base = (14.0, 3.0)
    assert all(a >= 0 and b >= 0 for a, b in
               even_slots([(30.0, 9.0), base], base, (2, 2)))


def test_slot_ascent_is_where_every_baseline_lies_below_the_top_of_its_line():
    from ynote.editor import even_slots, slot_ascent

    base = (14, 3)
    # A note of one font: the spacing above, and the font's own ascent.
    assert slot_ascent([base, base], base, (3, 2)) == 17
    # A taller font takes the place of the spacing.
    metrics = [base, (17, 5)]
    assert slot_ascent(metrics, base, (3, 2)) == 17
    for (ascent, _), (above, _) in zip(metrics, even_slots(metrics, base, (3, 2))):
        assert ascent + above == 17
