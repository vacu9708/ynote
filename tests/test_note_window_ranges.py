import random

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote.config import IMAGE_ANCHOR
from ynote.note_window import NoteWindow


class FakeTextView:
    def __init__(self, buf):
        self._buf = buf

    def get_buffer(self):
        return self._buf


def make_window(text):
    buf = Gtk.TextBuffer()
    buf.set_text(text)
    win = NoteWindow.__new__(NoteWindow)
    win.tv = FakeTextView(buf)
    return win, buf


def ranges_by_scanning(buf, tag):
    """Reference: visit every character, as the original implementation did."""
    ranges, start = [], None
    for offset in range(buf.get_char_count()):
        tagged = buf.get_iter_at_offset(offset).has_tag(tag)
        if tagged and start is None:
            start = offset
        elif not tagged and start is not None:
            ranges.append([start, offset])
            start = None
    if start is not None:
        ranges.append([start, buf.get_char_count()])
    return ranges


def tag(buf, name, spans):
    t = buf.create_tag(name)
    for s, e in spans:
        buf.apply_tag(t, buf.get_iter_at_offset(s), buf.get_iter_at_offset(e))
    return t


def test_tag_ranges_cover_both_buffer_edges_and_split_ranges():
    win, buf = make_window('bold at start, middle, and end')
    t = tag(buf, 'bold', [(0, 4), (15, 21), (26, 30)])

    assert win._get_tag_ranges(t) == [[0, 4], [15, 21], [26, 30]]


def test_tag_ranges_of_an_unused_tag_and_an_empty_buffer_are_empty():
    win, buf = make_window('')
    assert win._get_tag_ranges(tag(buf, 'code', [])) == []

    win, buf = make_window('plain text')
    assert win._get_tag_ranges(tag(buf, 'code', [])) == []


def test_tag_ranges_match_a_character_scan_on_random_text():
    rng = random.Random(7)
    alphabet = 'ab \n한글😀'
    for _ in range(200):
        text = ''.join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        win, buf = make_window(text)
        n = len(text)
        spans = []
        for _ in range(rng.randint(0, 4)):
            s = rng.randint(0, n)
            spans.append((s, rng.randint(s, n)))
        t = tag(buf, 'bold', spans)

        assert win._get_tag_ranges(t) == ranges_by_scanning(buf, t), (text, spans)


def test_images_state_lists_image_anchors_with_their_offsets():
    win, buf = make_window('a\nbc')
    win._normalize_image_meta = lambda meta, include_offset=False: dict(meta)
    for offset, name in ((4, 'two.png'), (0, 'one.png')):
        anchor = buf.create_child_anchor(buf.get_iter_at_offset(offset))
        anchor.ynote_image = {'file': name}
    # The placeholder character typed as plain text is not an image.
    buf.insert(buf.get_end_iter(), IMAGE_ANCHOR)

    assert win._get_images_state() == [
        {'file': 'one.png', 'offset': 0},
        {'file': 'two.png', 'offset': 5},
    ]
