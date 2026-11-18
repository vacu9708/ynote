"""Find web links in note text, so they can be shown and opened as links.

Kept free of GTK so it can be unit-tested. Offsets are character offsets
into the note text, the same ones GtkTextBuffer uses.
"""
import re

# A URL runs to the next space or a character that rarely ends one in prose.
# The placeholders for images and empty code lines also end it.
_URL = re.compile(r'\bhttps?://[^\s<>"\'`⁠￼]+', re.IGNORECASE)

# Punctuation that usually belongs to the sentence, not the URL.
_TRAILING = '.,;:!?\'"]}>'


def _trim(url):
    while url:
        last = url[-1]
        if last in _TRAILING:
            url = url[:-1]
        elif last == ')' and url.count('(') < url.count(')'):
            # "(see https://x.org/a)" drops the ")", but a URL that opens a
            # parenthesis of its own, like a Wikipedia page, keeps it.
            url = url[:-1]
        else:
            break
    return url


def find_links(text):
    """(start, end, url) for every http or https link in text."""
    links = []
    for m in _URL.finditer(text):
        url = _trim(m.group())
        if '://' in url and not url.endswith('://'):
            links.append((m.start(), m.start() + len(url), url))
    return links
