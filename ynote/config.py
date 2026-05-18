import os


APP_ID = 'io.github.youngsikyang.ynote'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(PACKAGE_DIR)
ICON_PATH = os.path.join(PROJECT_DIR, 'icon.png')

CONF_DIR = os.path.expanduser('~/.config/ynote')
NOTES_FILE = os.path.join(CONF_DIR, 'notes.json')
IMAGES_DIR = os.path.join(CONF_DIR, 'images')

IMAGE_ANCHOR = '\uFFFC'

# Invisible sentinel used so an otherwise empty line can carry the code tag.
# Older versions used NBSP (\u00a0), which renders as a visible space.
CODE_ANCHOR = '\u2060'

