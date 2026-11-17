"""Find a query in every note, for the search bar's All notes mode.

Kept free of GTK so it can be unit-tested. Offsets are character offsets
into the note text, the same ones GtkTextBuffer uses.
"""
import re
from collections import namedtuple

from .config import CODE_ANCHOR, IMAGE_ANCHOR

Match = namedtuple('Match', 'note_id title hidden start end snippet')
Note = namedtuple('Note', 'note_id title hidden text')

SNIPPET_LEAD = 20
SNIPPET_LENGTH = 60


def snippet(text, start, end):
    """The line holding text[start:end], cut to show the match near its start."""
    line_start = text.rfind('\n', 0, start) + 1
    line_end = text.find('\n', end)
    if line_end == -1:
        line_end = len(text)
    cut = max(line_start, start - SNIPPET_LEAD)
    piece = text[cut:min(line_end, cut + SNIPPET_LENGTH)]
    piece = piece.replace(IMAGE_ANCHOR, '').replace(CODE_ANCHOR, '').strip()
    if cut > line_start:
        piece = '…' + piece
    if cut + SNIPPET_LENGTH < line_end:
        piece += '…'
    return piece


def find_matches(notes, query, limit=100):
    """Case-insensitive matches of query in notes, in the order notes are given."""
    if not query:
        return []
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches = []
    for note in notes:
        for m in pattern.finditer(note.text):
            matches.append(Match(note.note_id, note.title, note.hidden,
                                 m.start(), m.end(),
                                 snippet(note.text, m.start(), m.end())))
            if len(matches) >= limit:
                return matches
    return matches
