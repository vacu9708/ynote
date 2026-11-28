"""Find a query in every note, for the search bar's All notes mode.

Kept free of GTK so it can be unit-tested. Offsets are character offsets
into the note text, the same ones GtkTextBuffer uses.
"""
import re
from collections import namedtuple

from .config import CODE_ANCHOR, EXPAND_END, IMAGE_ANCHOR, TABLE_MARKER

Match = namedtuple('Match', 'note_id title hidden start end snippet mark',
                   defaults=((-1, -1),))
Note = namedtuple('Note', 'note_id title hidden text')

SNIPPET_LEAD = 20
SNIPPET_LENGTH = 60


def _clean(piece):
    for char in (IMAGE_ANCHOR, CODE_ANCHOR, TABLE_MARKER, EXPAND_END):
        piece = piece.replace(char, '')
    return piece.replace('\t', ' ')


def snippet_marked(text, start, end):
    """The line holding text[start:end], cut to show the match near its
    start, and where the match is in it, as (snippet, (start, end))."""
    line_start = text.rfind('\n', 0, start) + 1
    line_end = text.find('\n', end)
    if line_end == -1:
        line_end = len(text)
    cut = max(line_start, start - SNIPPET_LEAD)
    stop = min(line_end, cut + SNIPPET_LENGTH)
    before = _clean(text[cut:start]).lstrip()
    hit = _clean(text[start:min(end, stop)])
    after = _clean(text[min(end, stop):stop])
    if not before:
        hit = hit.lstrip()
    piece = (before + hit + after).rstrip()
    lead = '…' if cut > line_start else ''
    mark = (len(lead) + len(before), len(lead) + min(len(before) + len(hit), len(piece)))
    piece = lead + piece
    if cut + SNIPPET_LENGTH < line_end:
        piece += '…'
    return piece, mark


def snippet(text, start, end):
    """The line holding text[start:end], cut to show the match near its start."""
    return snippet_marked(text, start, end)[0]


def find_matches(notes, query, limit=100, case_sensitive=False, regex=False):
    """Matches of query in notes, in the order notes are given: ignoring
    case unless case_sensitive, and as a regular expression if regex, which
    finds nothing if it does not compile."""
    if not query:
        return []
    try:
        pattern = re.compile(query if regex else re.escape(query),
                             0 if case_sensitive else re.IGNORECASE)
    except re.error:
        return []
    matches = []
    for note in notes:
        for m in pattern.finditer(note.text):
            if m.end() == m.start():
                continue
            piece, mark = snippet_marked(note.text, m.start(), m.end())
            matches.append(Match(note.note_id, note.title, note.hidden,
                                 m.start(), m.end(), piece, mark))
            if len(matches) >= limit:
                return matches
    return matches
