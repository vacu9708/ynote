from ynote.styles import DEFAULT_COLOR, PALETTE


def test_palette_has_the_seven_colors_and_yellow_is_the_default():
    assert list(PALETTE) == [
        'yellow', 'orange', 'pink', 'purple', 'blue', 'green', 'gray']
    assert DEFAULT_COLOR == 'yellow'


def test_the_page_knows_the_same_colors():
    import os
    import re
    js = open(os.path.join(os.path.dirname(__file__), '..', 'web', 'src', 'palette.js')).read()
    assert re.findall(r"^\s*(\w+): \{", js, re.M) == list(PALETTE)
