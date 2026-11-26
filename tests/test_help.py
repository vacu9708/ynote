import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.help import HELP, help_grid


def test_the_help_grid_has_a_heading_per_section_and_a_row_per_item():
    grid = help_grid()

    labels = [w for w in grid.get_children() if isinstance(w, Gtk.Label)]
    assert len(labels) == sum(1 + 2 * len(items) for _, items in HELP)
    texts = {w.get_text() for w in labels}
    assert {'Typing', 'Ctrl+Enter', '--- alone on a line', 'Step through notes, latest used first'} <= texts
