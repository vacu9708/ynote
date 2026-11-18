from ynote.config import CODE_ANCHOR, IMAGE_ANCHOR
from ynote.links import find_links


def urls(text):
    return [url for _, _, url in find_links(text)]


def test_offsets_point_at_the_url():
    text = 'PR: https://github.com/o/r/pull/12 done'

    [(start, end, url)] = find_links(text)

    assert text[start:end] == url == 'https://github.com/o/r/pull/12'


def test_sentence_punctuation_is_left_out():
    assert urls('See https://a.io/x. Or http://b.io/y, then') == [
        'https://a.io/x', 'http://b.io/y']
    assert urls('(see https://a.io/x)') == ['https://a.io/x']
    assert urls('"https://a.io/x"') == ['https://a.io/x']


def test_parentheses_inside_a_url_are_kept():
    assert urls('https://en.wikipedia.org/wiki/Go_(game)') == [
        'https://en.wikipedia.org/wiki/Go_(game)']


def test_query_strings_and_ports_are_kept():
    assert urls('http://localhost:8080/api?a=1&b=2#top') == [
        'http://localhost:8080/api?a=1&b=2#top']


def test_placeholders_and_backticks_end_a_url():
    text = f'https://a.io{IMAGE_ANCHOR}x `https://b.io` {CODE_ANCHOR}https://c.io'

    assert urls(text) == ['https://a.io', 'https://b.io', 'https://c.io']


def test_text_without_a_full_url_has_no_links():
    assert urls('https:// nothing, ftp://x.io, xhttps://y.io') == []
