"""Note colors and the app's GTK CSS. Pure strings, no GTK import."""

# name -> (body, bar). The first entry is the default.
PALETTE = {
    'yellow': ('#FFFF99', '#E8D800'),
    'orange': ('#FFD8A8', '#EFA03A'),
    'pink': ('#FFC9DC', '#E9779F'),
    'purple': ('#E1CCFF', '#A97BE0'),
    'blue': ('#BFE0FF', '#5AA9E6'),
    'green': ('#C8F0C0', '#6CC070'),
    'gray': ('#E4E4E4', '#A8A8A8'),
}
DEFAULT_COLOR = 'yellow'

# The title sits on the saturated bar. #444 was 3.1:1 on purple and 3.8:1 on
# blue; this is at least 5:1 on every bar color.
TITLE_COLOR = '#222222'

# The font of note text. NoteWindow also measures it to size code.
BODY_FONT = 'Ubuntu, Cantarell, DejaVu Sans, sans-serif'

# Code blocks and inline code have their own backgrounds, made from the note
# color: a block a light gray, as GitHub shows it, and inline code a little
# darker than the note, so the two are told apart.
CODE_BLOCK_TARGET = '#F2F2F2'
CODE_BLOCK_AMOUNT = 0.75
INLINE_CODE_TARGET = '#D0D0D0'
INLINE_CODE_AMOUNT = 0.3

# Every line of a note has this room above and below it, whatever its format.
# How it divides above and below follows from the fonts, so that an inline code
# box sits in the middle of its line: with the room above and below it equal,
# it is as far from the line above as from the line below. This is the total,
# or a pixel more where that is what it takes to divide it evenly.
LINE_SPACING = 3
# Bullets and to-do boxes are drawn, not set in type, so their size follows
# the note's font size and does not depend on a font, and a larger one does
# not make its line taller. All in em, then the room between a shape and the
# text after it.
BULLET_SIZE = 0.42
CHECKBOX_SIZE = 0.86
MARKER_GAP = 0.30
# A quote's bar, as wide as this many em, runs down the whole line.
QUOTE_BAR = 0.2
# An open expand is a box with rounded corners around its title and content,
# with this room in pixels inside it and outside above and below it. Its title
# is set smaller than the text, at this scale.
EXPAND_PAD = 6
EXPAND_MARGIN = 4
EXPAND_TITLE_SCALE = 0.9
# The chevron of an expand's title is a button, with this room in pixels
# around the chevron, and this room in em between the button and the title.
EXPAND_BUTTON_PAD = 7
EXPAND_GAP = 0.3

# Inline code and code blocks share a monospace font, a filled box, and a thin
# outline, so each reads as a unit on every note color.
# DejaVu Sans Mono reads better at small sizes than Ubuntu Mono, whose letters
# are small for their size.
CODE_FONT = 'DejaVu Sans Mono, Noto Sans Mono, Ubuntu Mono, monospace'
CODE_TEXT_COLOR = '#C53030'
CODE_OUTLINE = (0, 0, 0, 0.28)
CODE_RADIUS = 4
# The same box for code blocks and inline code, as in CSS: the box is the
# font's own line area, ascent above the baseline and descent below it, plus
# padding that is the same on all four sides. It does not depend on which
# letters are in it. Both are the space between the outline and that area. (The
# padding of inline code beside the text is a space at each end of it instead,
# as wide as the body font's space.)
CODE_PAD = 5
CODE_PAD_Y = 1
# The box of inline code stops this far inside the space that is its padding,
# which leaves a gap between it and the text beside it.
CODE_GAP = 2
# A code block also keeps this room from the lines around it, as a block of
# its own. Inline code is part of its line and has none.
CODE_BLOCK_MARGIN = 4
# Code text is sized so its lowercase letters are as tall as the text beside
# it, since monospace fonts differ in how large they look at the same size.
# Inline code is raised a little to sit centered in its box.
INLINE_CODE_RISE = 1

# A table keeps this room in pixels from the lines around it. Its cells have
# the room of a note's text inside them, and a header row in bold.
TABLE_MARGIN = 4

# A heading is told from body text by its size, its weight, and a serif face,
# which sets it apart from the sans body font even at the same size.
HEADING_FONT = 'Noto Serif, DejaVu Serif, serif'
# Bold in a heading, which is bold already, is its Black weight: Noto Serif
# and, for Korean, Noto Serif KR, which come with Ynote (see app_fonts.py).
HEADING_BOLD_FONT = 'Noto Serif, Noto Serif KR, DejaVu Serif, serif'
HEADING_SCALE = 1.25


def _rgb(hex_color):
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return '#%02X%02X%02X' % tuple(max(0, min(255, round(c))) for c in rgb)


def mix(color, target, amount):
    """Move `color` `amount` (0-1) of the way toward `target`."""
    return _hex(tuple(a + (b - a) * amount
                      for a, b in zip(_rgb(color), _rgb(target))))


def code_background(color):
    """Code block background: the note body pulled toward light gray."""
    return mix(PALETTE[color][0], CODE_BLOCK_TARGET, CODE_BLOCK_AMOUNT)


def inline_code_background(color):
    """Inline code background: the note body pulled toward gray."""
    return mix(PALETTE[color][0], INLINE_CODE_TARGET, INLINE_CODE_AMOUNT)


def rgba(color, alpha=1.0):
    r, g, b = _rgb(color)
    return f'rgba({r},{g},{b},{alpha:.2f})'


def note_css(color, opacity=1.0):
    """Per-window CSS for the note, header, and bottom bar backgrounds.

    Only the note body takes the opacity. The two bars stay opaque so they
    remain visible, and so do text, buttons, and images, which are not styled
    here.
    """
    body, bar = PALETTE[color]
    return (f'window.note {{ background: {rgba(body, opacity)}; }}\n'
            f'box.hdr {{ background: {bar}; }}\n'
            f'box.btmbar {{ background: {bar}; }}\n')


def swatch_css():
    """Circular color swatches for the popover, generated from PALETTE."""
    css = ('button.swatch {\n'
           '    min-width: 18px; min-height: 18px; padding: 0;\n'
           '    border-radius: 50%; border: 2px solid; box-shadow: none;\n'
           '    background-image: none;\n}\n'
           'button.swatch.selected {\n'
           '    border-color: #333;\n'
           '    box-shadow: inset 0 0 0 2px #FFFFFF;\n}\n')
    for name, (body, _bar) in PALETTE.items():
        css += (f'button.swatch-{name} {{ background-color: {body}; '
                f'border-color: {mix(body, "#000000", 0.25)}; }}\n'
                f'button.swatch-{name}.selected {{ border-color: #333; }}\n')
    return css


_BASE = """
box.hdr {
    padding: 2px 4px 2px 2px;
}
box.hdr > eventbox { min-height: 26px; }
box.btmbar {
    padding: 3px 0;
    min-height: 30px;
}
box.btmbar .tool-group {
    padding: 0 2px;
}
separator.tool-separator {
    background: rgba(0,0,0,0.25);
    min-width: 1px;
    margin: 3px 3px;
}

box.hdr button, box.btmbar button {
    padding: 1px 4px;
    min-width: 20px;
    min-height: 20px;
    border-radius: 10px;
    border: none;
    box-shadow: none;
    background: rgba(0,0,0,0.09);
    font-size: 12px;
    font-weight: bold;
    color: #333;
}
box.hdr button.pin-top {
    min-width: 18px;
    min-height: 18px;
    padding: 1px 6px;
    border-radius: 14px;
    font-size: 18px;
}
/* The icons of the Format and Insert menus, as large as the menu's text. */
menuitem label.menu-icon {
    font-size: 15px;
    min-width: 20px;
    padding: 0 2px;
    border-radius: 4px;
    color: #333;
}
/* A format that is on at the cursor. */
menuitem label.menu-icon.on {
    background: rgba(0,0,0,0.55);
    color: #fff;
}
/* The code block icon is the inline code icon inside a box. */
box.btmbar button label.boxed, menuitem label.boxed {
    border: 1px solid #333;
    border-radius: 3px;
    padding: 1px 2px;
}
box.btmbar button:disabled { color: rgba(0,0,0,0.25); }
box.hdr button:hover, box.btmbar button:hover { background: rgba(0,0,0,0.25); }
box.hdr button.pinned, box.btmbar button.pinned { background: rgba(0,0,0,0.55); color: #000; }
/* The popover lives inside the note's own window, so it must stay short
   enough for a default 200x300 note. */
popover modelbutton { min-height: 20px; padding: 1px 6px; }
popover scale { min-height: 16px; }
popover button.step { min-width: 24px; min-height: 18px; padding: 0 6px; }
popover scale trough { min-height: 4px; }
modelbutton.danger label { color: #C62828; }
label.title {
    color: %(title)s;
    font-weight: bold;
    font-size: 16px;
    padding: 0 4px;
}
/* A note without a title shows a placeholder that reads as one. */
label.title.untitled {
    font-weight: normal;
    font-style: italic;
    opacity: 0.6;
}
entry.title-edit {
    background: transparent;
    border: 1px solid rgba(0,0,0,0.25);
    border-radius: 3px;
    box-shadow: none;
    color: %(title)s;
    font-weight: bold;
    font-size: 15px;
    min-height: 20px;
    padding: 0 4px;
}
textview, textview text {
    background: transparent;
    font-family: %(body_font)s;
    font-size: 14px;
}
box.search-bar {
    background: rgba(0,0,0,0.08);
    padding: 2px 4px;
    border-top: 1px solid rgba(0,0,0,0.15);
}
box.search-bar entry {
    min-height: 22px;
    font-size: 12px;
}
box.search-bar checkbutton label,
box.search-bar list label {
    font-size: 12px;
}
box.search-bar list {
    background: transparent;
}
box.search-bar list row {
    padding: 2px 4px;
}
"""

BASE_CSS = (_BASE % {'title': TITLE_COLOR, 'body_font': BODY_FONT}
            + swatch_css()).encode()
