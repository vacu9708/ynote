from ynote.config import CODE_ANCHOR, IMAGE_ANCHOR
from ynote.search import Note, find_matches, snippet


def test_matches_are_case_insensitive_and_keep_note_order():
    notes = [Note('a', 'tmux', False, 'Reload config\ntmux source-file'),
             Note('b', 'git', True, 'git reset\nreload remote')]

    matches = find_matches(notes, 'RELOAD')

    assert [(m.note_id, m.start, m.end, m.hidden) for m in matches] == [
        ('a', 0, 6, False), ('b', 10, 16, True)]
    assert matches[1].snippet == 'reload remote'


def test_offsets_match_the_original_text_even_after_case_folding():
    # 'İ' lowercases to two characters; offsets must still index the original.
    notes = [Note('a', 't', False, 'İİ needle')]

    [match] = find_matches(notes, 'NEEDLE')

    assert notes[0].text[match.start:match.end] == 'needle'


def test_query_is_matched_literally():
    notes = [Note('a', 't', False, 'a.b axb (x)')]

    assert [m.start for m in find_matches(notes, 'a.b')] == [0]
    assert [m.start for m in find_matches(notes, '(x)')] == [8]


def test_empty_query_and_limit():
    notes = [Note('a', 't', False, 'aaaa')]

    assert find_matches(notes, '') == []
    assert len(find_matches(notes, 'a', limit=3)) == 3


def test_snippet_shows_only_the_matching_line_without_placeholders():
    text = f'first line\n{CODE_ANCHOR}code {IMAGE_ANCHOR}here\nlast'
    start = text.index('here')

    assert snippet(text, start, start + 4) == 'code here'


def test_snippet_cuts_a_long_line_around_the_match():
    text = 'x' * 100 + 'needle' + 'y' * 100
    start = text.index('needle')

    piece = snippet(text, start, start + 6)

    assert piece.startswith('…') and piece.endswith('…')
    assert 'needle' in piece and len(piece) <= 62


def test_find_matches_can_match_case():
    from ynote.search import Note, find_matches
    notes = [Note('n', 't', False, 'Error error')]
    assert [m.start for m in find_matches(notes, 'Error', case_sensitive=True)] == [0]
    assert [m.start for m in find_matches(notes, 'Error')] == [0, 6]


def test_find_matches_as_a_regular_expression():
    from ynote.search import Note, find_matches
    notes = [Note('n', 't', False, 'err 502\nerror 110')]
    found = find_matches(notes, r'err(or)?\s+\d+', regex=True)
    assert [(m.start, m.end) for m in found] == [(0, 7), (8, 17)]
    assert find_matches(notes, '(', regex=True) == []


def test_a_match_is_marked_in_its_snippet():
    from ynote.search import Note, find_matches
    text = 'x' * 50 + ' kubectl rollout restart deploy/api'
    (m,) = find_matches([Note('n', 't', False, text)], 'restart')
    start, end = m.mark
    assert m.snippet[start:end] == 'restart'
