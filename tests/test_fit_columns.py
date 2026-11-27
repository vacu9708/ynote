"""How wide a table's columns are, given how wide their text is and the
room the note has, as a browser shares it."""
from ynote.table import fit_columns


def test_columns_keep_their_width_when_they_fit():
    assert fit_columns([100, 50], 300, 40) == [100, 50]


def test_narrow_columns_keep_their_width_and_wide_ones_share_the_rest():
    widths = fit_columns([60, 400, 200, 80], 500, 40)

    assert widths[0] == 60 and widths[3] == 80
    assert widths[1] + widths[2] <= 360 and widths[1] > widths[2]
