"""Sections that fold away, found in a note's lines."""
from ynote.config import EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN
from ynote.sections import Section, find_sections, hidden_lines, section_at

O, C, E = EXPAND_OPEN, EXPAND_CLOSED, EXPAND_END


def test_a_section_runs_from_its_title_to_its_end_line():
    sections, orphans = find_sections([O + 'Test', 'a', E, 'after'])

    assert sections == [Section(0, 2, True)] and orphans == []


def test_sections_nest_and_each_end_closes_the_innermost():
    lines = [O + 'outer', C + 'inner', 'x', E, 'y', E]

    sections, _ = find_sections(lines)

    assert sections == [Section(0, 5, True), Section(1, 3, False)]
    assert section_at(sections, 2) == Section(1, 3, False)
    assert section_at(sections, 4) == Section(0, 5, True)


def test_an_end_without_a_section_is_an_orphan_and_code_is_content():
    sections, orphans = find_sections([E, O + 'x', E, E], skip={2})

    assert sections == [Section(1, 3, True)] and orphans == [0]


def test_a_folded_section_hides_its_content_and_end_an_open_one_nothing():
    sections, _ = find_sections([C + 'f', 'a', 'b', E, O + 'o', 'c', E])

    assert hidden_lines(sections, 7) == {1, 2, 3}
