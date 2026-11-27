"""J. Dividers, links, emoji, K. images, Q. drawing and wrapping, and
R. notes from older versions: see BEHAVIORS.md."""
import os

from tests.e2e.driver import Gdk, Gtk, pump, settle, wait_until

PAD = ' '


def note(title, text='', **fields):
    return dict({'id': title, 'title': title, 'text': text, 'x': 100,
                 'y': 80, 'w': 600, 'h': 500}, **fields)


def lines(n):
    return n.body.text().rstrip('\n').split('\n')


# ---------------------------------------------------------------- J

def fake_browser(home):
    """A browser for http links that writes down what it was asked to open."""
    apps = os.path.join(home, '.local', 'share', 'applications')
    os.makedirs(apps, exist_ok=True)
    opened = os.path.join(home, 'opened')
    with open(os.path.join(apps, 'fake-browser.desktop'), 'w') as f:
        f.write('[Desktop Entry]\nType=Application\nName=Fake\n'
                f"Exec=sh -c 'echo \"$1\" >> {opened}' sh %u\n"
                'MimeType=x-scheme-handler/http;x-scheme-handler/https;\n')
    conf = os.path.join(home, '.config')
    os.makedirs(conf, exist_ok=True)
    with open(os.path.join(conf, 'mimeapps.list'), 'w') as f:
        f.write('[Default Applications]\n'
                'x-scheme-handler/http=fake-browser.desktop\n'
                'x-scheme-handler/https=fake-browser.desktop\n')
    return opened


def test_J1_the_cursor_skips_a_divider_both_ways(write, app):
    n = write('above\n\n---\n\nbelow\n')
    n.body.click_text('below', at='start')
    app.inp.key('up')
    app.inp.key('up')
    app.inp.type('X')
    # Up from below skips the divider, onto the blank line above it.
    assert lines(n) == ['above', 'X', '---', '', 'below']


def test_J2_ctrl_click_opens_a_link_and_a_click_only_places_the_cursor(app):
    opened = fake_browser(app.home)
    app.write_notes([note('t', 'see https://example.com/page now')])
    app.start()
    n = app.note('t')
    n.body.click_text('example', at='middle')
    settle(0.5)
    assert not os.path.exists(opened)
    x, y = n.body.point_at(n.body.text().index('example'))
    app.inp.move(x, y)
    app.inp._mods(['ctrl'], True)
    app.inp.press()
    app.inp.release()
    app.inp._mods(['ctrl'], False)
    wait_until(lambda: os.path.exists(opened), timeout=10, what='the link')
    with open(opened) as f:
        assert f.read().strip() == 'https://example.com/page'


def test_J3_a_link_leaves_out_the_punctuation_after_it(app):
    opened = fake_browser(app.home)
    app.write_notes([note('t', 'go to https://example.com/a_(b).')])
    app.start()
    n = app.note('t')
    x, y = n.body.point_at(n.body.text().index('example'))
    app.inp.move(x, y)
    app.inp._mods(['ctrl'], True)
    app.inp.press()
    app.inp.release()
    app.inp._mods(['ctrl'], False)
    wait_until(lambda: os.path.exists(opened), timeout=10, what='the link')
    with open(opened) as f:
        assert f.read().strip() == 'https://example.com/a_(b)'


def test_J4_insert_emoji_is_first_in_the_text_menu(note, app):
    x, y = note.body.point_at(0)
    app.inp.click(x, y, button=3)
    items = note.menu_items()
    assert items and items[0].replace('_', '') == 'Insert Emoji'
    app.inp.key('esc')


# ---------------------------------------------------------------- K

def put_image_on_clipboard():
    from gi.repository import GdkPixbuf
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 80, 40)
    pb.fill(0x3366ccff)
    Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_image(pb)
    pump()


def images_dir(app):
    return os.path.join(app.conf, 'images')


def test_K1_K2_a_pasted_image_is_saved_and_cleaned_up_once_unused(note, app):
    put_image_on_clipboard()
    app.inp.key('ctrl+v')
    wait_until(lambda: os.path.isdir(images_dir(app))
               and os.listdir(images_dir(app)), what='the image file')
    app.quit()
    saved = app.saved_note('test')
    assert len(saved['images']) == 1
    app.start()
    n = app.note('test')
    n.body.click()
    app.inp.key('ctrl+a')
    app.inp.key('del')
    settle(1.0)
    app.quit()
    app.start()
    settle(0.5)
    assert os.listdir(images_dir(app)) == []


def test_K4_an_image_in_a_table_cell_is_kept(write, app):
    n = write('| A | B |\n| --- | --- |\n| x | y |\n')
    n.cell(1, 0).click_text('x', at='end')
    put_image_on_clipboard()
    app.inp.key('ctrl+v')
    wait_until(lambda: os.path.isdir(images_dir(app))
               and os.listdir(images_dir(app)), what='the image file')
    files = os.listdir(images_dir(app))
    app.quit()
    app.start()
    settle(0.5)
    assert os.listdir(images_dir(app)) == files
    assert app.saved_note('test')['tables'][0]['rows'][1][0]['images']


# ---------------------------------------------------------------- Q

LONG_CODE = ('ynote --open-note "테스트" --with-a-long-option-name '
             '--and-another-one-to-wrap --past-the-right-edge-of-a-note '
             '--so-that-it-goes-on-below')


def rows_of(area, start, end):
    """The y of each row the characters from start to end are drawn on."""
    return sorted({area.char_box(i)[1] for i in range(start, end)
                   if area.text()[i] not in (' ', PAD)})


def drawn_rows(boxes):
    """Character boxes grouped by the row they are drawn on: boxes of
    different fonts on one row differ in height but overlap."""
    rows = []
    for box in sorted(boxes, key=lambda b: b[1]):
        if rows and box[1] < max(b[1] + b[3] for b in rows[-1]) - 2:
            rows[-1].append(box)
        else:
            rows.append([box])
    return rows


def test_Q1_a_long_line_wraps_to_the_note(write, app):
    n = write('word ' * 60 + '\n')
    text = n.body.text()
    assert len(rows_of(n.body, 0, len(text.rstrip()))) > 1


def test_Q4_code_that_starts_a_line_wraps_in_line_with_its_first_row(write, app):
    n = write(f'`{LONG_CODE}`\n')
    body = n.body
    text = body.text()
    first = text.index('ynote')
    boxes = [(i, body.char_box(i)) for i in range(first, first + len(LONG_CODE))]
    rows = drawn_rows([b for _, b in boxes])
    assert len(rows) >= 2
    second_row_x = min(b[0] for b in rows[1])
    assert abs(second_row_x - body.char_box(first)[0]) <= 1


def test_Q6_rows_of_wrapped_code_with_korean_keep_their_spacing(write, app):
    n = write(f'한글 줄\n`{LONG_CODE}`\n')
    body = n.body
    text = body.text()
    first = text.index('ynote')
    rows = drawn_rows([body.char_box(i)
                       for i in range(first, first + len(LONG_CODE))])
    assert len(rows) >= 2
    bottom_of_first = max(b[1] + b[3] for b in rows[0])
    top_of_second = min(b[1] for b in rows[1])
    assert top_of_second - bottom_of_first >= 4


def test_Q7_a_word_of_code_too_long_for_its_row_starts_on_it(write, app):
    n = write('`' + 'a' * 150 + '`\n')
    body = n.body
    text = body.text()
    first = text.index('a')
    assert body.char_box(first)[1] == body.char_box(text.index(PAD))[1]


def test_Q10_enter_keeps_the_new_line_in_view(app):
    app.write_notes([note('t', '\n'.join(f'line {i}' for i in range(60)),
                          h=300)])
    app.start()
    n = app.note('t')
    n.body.click_text('line 3', at='end')
    app.inp.key('ctrl+end')
    for _ in range(5):
        app.inp.key('enter')
    app.inp.type('seen')
    x, y, w, h = n.box()
    cx, cy, cw, ch = n.body.char_box(n.body.text().index('seen'))
    assert y <= cy and cy + ch <= y + h


# ---------------------------------------------------------------- R

def test_R1_inline_code_padded_by_older_versions_gets_the_new_padding(app):
    app.write_notes([note('t', 'a  ls  b', backtick_ranges=[[2, 6]])])
    app.start()
    n = app.note('t')
    assert n.body.text().startswith(f'a {PAD}ls{PAD} b')
    assert n.body.formats('ls') == {'code'}
    app.quit()
    assert app.saved_note('t')['text'] == f'a {PAD}ls{PAD} b'


def test_R5_a_note_saved_with_only_its_text_opens(app):
    app.write_notes([{'id': 'n', 'title': 'bare', 'text': 'just text'}])
    app.start()
    assert app.note('bare').body.text().startswith('just text')


# ---------------------------------------------------------------- Q boxes

def screen():
    from tests.e2e.driver import screenshot
    return screenshot('/tmp/e2e-screen.png')


def color(pb, x, y):
    from tests.e2e.driver import pixel
    return pixel(pb, x, y)


def box_edge(pb, x, y, background):
    """Coming left from x, outside any box, where a box's right edge is:
    the first pixel that is not the note's background."""
    while color(pb, x, y) == background:
        x -= 1
    return x + 1


def test_Q3_a_wrapped_row_of_code_has_padding_where_it_wraps(write, app):
    n = write(f'`{LONG_CODE}`\n')
    body = n.body
    text = body.text()
    first = text.index('ynote')
    rows = drawn_rows([body.char_box(i)
                       for i in range(first, first + len(LONG_CODE))])
    last = max(rows[0], key=lambda b: b[0] + b[2])
    pb = screen()
    nx, ny, nw, nh = n.box()
    background = color(pb, nx + nw - 4, ny + nh // 2)
    edge = box_edge(pb, nx + nw - 4, last[1] + last[3] // 2, background)
    assert edge - (last[0] + last[2]) >= 3, 'room past the last character'


def test_I2_a_code_block_box_is_as_wide_as_its_longest_line(write, app):
    n = write('```\nls\nlonger line here\nx\n```\nafter\n')
    body = n.body
    text = body.text()
    short = body.char_box(text.index('ls'))
    nx, ny, nw, nh = n.box()

    def edge():
        pb = screen()
        background = color(pb, nx + nw - 4, ny + nh // 2)
        return box_edge(pb, nx + nw - 4, short[1] + short[3] // 2, background)

    end_long = body.char_box(text.index('here') + 3)
    assert 0 <= edge() - (end_long[0] + end_long[2]) <= 14
    body.click_text('here', at='end')
    app.inp.type(' and more')
    end_new = n.body.char_box(n.body.text().index('more') + 3)
    assert 0 <= edge() - (end_new[0] + end_new[2]) <= 14, 'the box follows'


def ink(pb, box):
    """How much of the box the text darkens: the sum of how far below the
    background each pixel's brightness is."""
    x, y, w, h = box
    background = sum(color(pb, x - 1, y + h // 2))
    total = 0
    for px in range(x, x + w):
        for py in range(y, y + h):
            total += max(0, background - sum(color(pb, px, py)))
    return total


def word_box(area, word):
    text = area.text()
    first = area.char_box(text.index(word))
    last = area.char_box(text.index(word) + len(word) - 1)
    return (first[0], first[1], last[0] + last[2] - first[0], first[3])


def test_Q11_bold_in_a_heading_is_drawn_bolder_in_english_and_korean(write, app):
    n = write('# HHHH 제목 **HHHH 제목**\n')
    body = n.body
    text = body.text()
    pb = screen()
    for plain, bolder in (('HHHH', 'HHHH'), ('제목', '제목')):
        i = text.index(plain)
        j = text.index(bolder, i + 1)
        a = body.char_box(i)
        b = body.char_box(j)
        width = len(plain)
        box_a = (a[0], a[1], body.char_box(i + width - 1)[0]
                 + body.char_box(i + width - 1)[2] - a[0], a[3])
        box_b = (b[0], b[1], body.char_box(j + width - 1)[0]
                 + body.char_box(j + width - 1)[2] - b[0], b[3])
        assert ink(pb, box_b) > ink(pb, box_a) * 1.1, plain
