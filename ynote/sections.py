"""Expands, sections of a note that fold away, found in its text. Kept free of
GTK so it can be unit-tested.

A section's title line starts with EXPAND_OPEN or EXPAND_CLOSED, and the next
line holding only EXPAND_END that is not taken by a section inside it ends
it. Everything between them is its content.
"""
from collections import namedtuple

from .config import EXPAND_CLOSED, EXPAND_END, EXPAND_OPEN

# title and end are line numbers; end is None for a section never ended.
Section = namedtuple('Section', 'title end open')


def is_title(line):
    return line.startswith(EXPAND_OPEN) or line.startswith(EXPAND_CLOSED)


def find_sections(lines, skip=()):
    """(sections in order of their titles, end lines that end no section).

    Lines in skip, such as lines of code, are content and never a title or
    an end."""
    open_titles = []
    sections, orphans = [], []
    for number, line in enumerate(lines):
        if number in skip:
            continue
        if is_title(line):
            open_titles.append(number)
        elif line == EXPAND_END:
            if open_titles:
                title = open_titles.pop()
                sections.append(Section(title, number,
                                        lines[title].startswith(EXPAND_OPEN)))
            else:
                orphans.append(number)
    for title in open_titles:
        sections.append(Section(title, None,
                                lines[title].startswith(EXPAND_OPEN)))
    sections.sort()
    return sections, orphans


def hidden_lines(sections, line_count):
    """The lines not shown: the content and end of a folded section. An open
    one's end line is the room at the bottom of its box."""
    hidden = set()
    for section in sections:
        end = line_count - 1 if section.end is None else section.end
        if not section.open:
            hidden.update(range(section.title + 1, end + 1))
    return hidden


def section_at(sections, line):
    """The innermost section whose content holds line, or None."""
    inside = [s for s in sections
              if s.title < line and (s.end is None or line < s.end)]
    return max(inside, key=lambda s: s.title, default=None)
