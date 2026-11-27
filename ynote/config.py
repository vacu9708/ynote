import os


APP_ID = 'io.github.youngsikyang.ynote'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(PACKAGE_DIR)
ICON_PATH = os.path.join(PROJECT_DIR, 'icon.png')

CONF_DIR = os.path.expanduser('~/.config/ynote')
NOTES_FILE = os.path.join(CONF_DIR, 'notes.json')
IMAGES_DIR = os.path.join(CONF_DIR, 'images')
SETTINGS_FILE = os.path.join(CONF_DIR, 'settings.json')

# Per-user XDG autostart entry that starts Ynote at login.
AUTOSTART_FILE = os.path.expanduser('~/.config/autostart/ynote.desktop')

IMAGE_ANCHOR = '\uFFFC'

# Invisible sentinel used so an otherwise empty line can carry the code tag.
# Older versions used NBSP (\u00a0), which renders as a visible space.
CODE_ANCHOR = '\u2060'

# The padding of inline code: one of these at each end of it, in the body font.
# An en space is half an em wide, so the box has room for its padding and for
# a gap from the text beside it. It is copied out as a plain space.
CODE_PAD_CHAR = '\u2002'

# A line holding exactly this text is drawn as a divider, like in Markdown.
DIVIDER_TEXT = '---'

# List markers are plain text at the start of a line, after any indent, so
# a note stays readable as text and needs no extra saved fields.
BULLET_MARKER = '• '
CHECKBOX_MARKER = '\u2610 '        # ☐, an open to-do
CHECKED_MARKER = '\u2611 '         # ☑, a done to-do
# A quote is a marker too, so it works like a list item: Enter continues it
# and an empty one ends it. As text, a bar before the line reads as a quote.
QUOTE_MARKER = '\u258d '          # ▍

# A section that folds away: its title line starts with one of these, open or
# folded, and a line holding only EXPAND_END ends it. What is between them is
# its content, of any kind. Sections can be inside sections.
EXPAND_OPEN = '\u25be '           # ▾
EXPAND_CLOSED = '\u25b8 '         # ▸
EXPAND_END = '\u2064'

# A line that starts with this invisible character is a row of a table, and
# its cells are separated by tabs. Like a list marker it is text, so a table
# is saved, undone, and copied between notes as its text. Consecutive rows are
# one table, and the first of them is its header.
TABLE_MARKER = '\u2063'

# Shown for a note without a title. Kept apart from NEW_NOTE_LABEL, the action
# that creates a note, so renaming one never changes the other.
UNTITLED_LABEL = 'Untitled'
NEW_NOTE_LABEL = 'New Note'

# The width and height of a new note, which is square, unless its bottom bar
# needs it wider.
NEW_NOTE_SIDE = 260


def display_path(path):
    """Show a path under the home directory as ~/..., for messages."""
    home = os.path.expanduser('~')
    if path.startswith(home + os.sep):
        return '~' + path[len(home):]
    return path
