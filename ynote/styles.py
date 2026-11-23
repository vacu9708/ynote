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

CODE_MIX_TARGET = '#EEEEEE'
CODE_MIX_AMOUNT = 0.7


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
    return mix(PALETTE[color][0], CODE_MIX_TARGET, CODE_MIX_AMOUNT)


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
    background: rgba(0,0,0,0.18);
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
box.hdr button:hover, box.btmbar button:hover { background: rgba(0,0,0,0.35); }
box.hdr button.pinned, box.btmbar button.pinned { background: rgba(0,0,0,0.55); color: #000; }
/* The popover lives inside the note's own window, so it must stay short
   enough for a default 200x300 note. */
popover modelbutton { min-height: 20px; padding: 1px 6px; }
popover scale { min-height: 16px; }
popover scale trough { min-height: 4px; }
/* A multi-line selection inside a code block is drawn by the note itself. */
textview.code-selection text selection { background-color: transparent; }
modelbutton.danger label { color: #C62828; }
label.title {
    color: #444;
    font-weight: bold;
    font-size: 16px;
    padding: 0 4px;
}
entry.title-edit {
    background: transparent;
    border: 1px solid rgba(0,0,0,0.25);
    border-radius: 3px;
    box-shadow: none;
    color: #333;
    font-weight: bold;
    font-size: 15px;
    min-height: 20px;
    padding: 0 4px;
}
textview, textview text {
    background: transparent;
    font-family: Ubuntu, Cantarell, DejaVu Sans, sans-serif;
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

BASE_CSS = (_BASE + swatch_css()).encode()
