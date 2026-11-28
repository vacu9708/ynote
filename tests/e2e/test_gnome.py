"""X. Alt+scroll on GNOME's window manager, which stacks and focuses notes
otherwise than openbox, and gives a scroll after a note comes up under the
pointer no amount. See BEHAVIORS.md."""
import os
import time

import pytest

from tests.e2e.gnome import ALT, Gnome, started

pytestmark = [pytest.mark.gnome]

# A large note with two small ones on it, apart, and the pointer over the
# large one and one of the small: each step brings up a note, now under the
# pointer, now away from it.
NOTES = [
    {'id': 'a', 'title': 'a', 'text': 'a', 'x': 60, 'y': 40, 'w': 900, 'h': 760},
    {'id': 'b', 'title': 'b', 'text': 'b', 'x': 520, 'y': 380, 'w': 360, 'h': 320},
    {'id': 'c', 'title': 'c', 'text': 'c', 'x': 250, 'y': 300, 'w': 260, 'h': 260},
]
POINTER = (300, 350)


@pytest.fixture
def gnome(app):
    g = Gnome(os.path.join(app.home, 'mutter.log'))
    yield g
    app.quit()
    g.stop()


@pytest.fixture
def desk(app, gnome):
    started(app, gnome, NOTES)
    gnome.move(*POINTER)
    return gnome


def steps(g, notches):
    """Alt held, a notch at a time: the active note and the top one after
    each, and the active one once Alt is let go."""
    seen = []
    g.key(ALT, True)
    for _ in range(notches):
        g.scroll(1)
        seen.append((g.active(), g.stacking()[0]))
    g.key(ALT, False)
    return seen


def test_X9_every_alt_scroll_notch_steps_on_gnome(desk):
    first = desk.active()
    for round_ in range(2):
        seen = steps(desk, 3)
        active = [a for a, _top in seen]
        # Each notch a step: all three, back to the one it started from.
        assert len(set(active[:2] + [first])) == 3 and active[2] == first, (round_, first, seen)
        assert all(a == top for a, top in seen), seen


def test_X10_letting_go_of_alt_leaves_the_note_stepped_to_active_on_gnome(desk):
    first = desk.active()
    seen = steps(desk, 1)
    target = seen[0][0]
    assert target != first, seen
    time.sleep(0.8)
    assert desk.active() == target == desk.stacking()[0]
