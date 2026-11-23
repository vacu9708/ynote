"""The tray icon as a StatusNotifierItem, which GNOME Shell and KDE draw and
position themselves.

Gtk.StatusIcon placed its menu from the icon's X window, which GNOME Shell
under Wayland does not keep where the icon is drawn, so the menu opened in the
middle of the screen. The package depends on an application indicator library
instead. Run from a source checkout without one, Ynote has no tray icon."""
import importlib
import os

import gi

NAMESPACES = ('AyatanaAppIndicator3', 'AppIndicator3')
FALLBACK_ICON_NAME = 'accessories-text-editor'


def load_app_indicator():
    """The first application indicator module that can be loaded, or None."""
    for name in NAMESPACES:
        try:
            gi.require_version(name, '0.1')
            return importlib.import_module(f'gi.repository.{name}')
        except (ValueError, ImportError):
            continue
    return None


def make_indicator(module, icon_path):
    """A visible indicator showing the icon at `icon_path`, with no menu yet."""
    category = module.IndicatorCategory.APPLICATION_STATUS
    if os.path.exists(icon_path):
        # The icon is named by its file name without the extension, inside the
        # folder it is in.
        name = os.path.splitext(os.path.basename(icon_path))[0]
        indicator = module.Indicator.new('ynote', name, category)
        indicator.set_icon_theme_path(os.path.dirname(icon_path))
    else:
        indicator = module.Indicator.new('ynote', FALLBACK_ICON_NAME, category)
    indicator.set_title('Ynote')
    indicator.set_status(module.IndicatorStatus.ACTIVE)
    return indicator


MENU_LABEL_CHARS = 32
UNTITLED = 'Untitled'
OPEN_NOTES_HEADER = 'Open Notes'
RAISE_ALL_LABEL = 'Bring All to Front'
NOTE_BULLET = '\u2022 '


def note_label(title, text):
    """How an open note appears in the tray menu, under the Open Notes header
    and with a bullet that the action items lack: its title, else the first
    line of its text, else Untitled, cut to a length that fits the menu."""
    label = (title or '').strip()
    if not label:
        # Image anchors and the invisible mark that lets an empty code line
        # carry its tag are not text.
        for line in text.replace('\uFFFC', ' ').replace('\u2060', '').splitlines():
            if line.strip():
                label = ' '.join(line.split())
                break
    if not label:
        label = UNTITLED
    if len(label) > MENU_LABEL_CHARS:
        label = label[:MENU_LABEL_CHARS - 1].rstrip() + '\u2026'
    return NOTE_BULLET + label


def hidden_notes_label(count):
    return f'Hidden Notes ({count})'
