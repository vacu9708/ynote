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

# A line holding exactly this text is drawn as a divider, like in Markdown.
DIVIDER_TEXT = '---'

# List markers are plain text at the start of a line, after any indent, so
# a note stays readable as text and needs no extra saved fields.
BULLET_MARKER = '• '
CHECKBOX_MARKER = '\u2610 '        # ☐, an open to-do
CHECKED_MARKER = '\u2611 '         # ☑, a done to-do

# Shown for a note without a title. Kept apart from NEW_NOTE_LABEL, the action
# that creates a note, so renaming one never changes the other.
UNTITLED_LABEL = 'Untitled'
NEW_NOTE_LABEL = 'New Note'


def display_path(path):
    """Show a path under the home directory as ~/..., for messages."""
    home = os.path.expanduser('~')
    if path.startswith(home + os.sep):
        return '~' + path[len(home):]
    return path
