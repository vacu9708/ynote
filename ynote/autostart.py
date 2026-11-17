"""Start Ynote at login through a per-user XDG autostart entry.

Autostart is turned on once, the first time an installed Ynote runs for a
user. A flag in settings.json records that, so turning it off later sticks.
"""
import os

from .storage import load_json, save_json

# TryExec makes the session skip the entry once the package is removed.
ENTRY = """\
[Desktop Entry]
Type=Application
Name=Ynote
Comment=Engineer-friendly sticky notes for your desktop
TryExec=ynote
Exec=ynote
Icon=ynote
Terminal=false
StartupNotify=false
StartupWMClass=Ynote
X-GNOME-Autostart-enabled=true
"""

CONFIGURED_KEY = 'autostart_configured'


def is_enabled(entry_path):
    try:
        with open(entry_path) as f:
            lines = f.read().splitlines()
    except OSError:
        return False
    # An entry can exist but be switched off by either of these keys.
    for line in lines:
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip().lower()
        if key == 'Hidden' and value == 'true':
            return False
        if key == 'X-GNOME-Autostart-enabled' and value == 'false':
            return False
    return True


def set_enabled(entry_path, enabled):
    entry_path = os.fspath(entry_path)
    if not enabled:
        try:
            os.remove(entry_path)
        except FileNotFoundError:
            pass
        return
    os.makedirs(os.path.dirname(entry_path), exist_ok=True)
    tmp = entry_path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(ENTRY)
    os.replace(tmp, entry_path)


def enable_on_first_run(entry_path, settings_path, installed):
    """Turn autostart on once per user. Returns True if it did.

    `installed` is whether the `ynote` command exists. Running from a source
    checkout without the package leaves autostart alone, and does not use up
    the first run, because the entry could not start anything.
    """
    if not installed:
        return False
    settings = load_json(settings_path)
    if not isinstance(settings, dict):
        settings = {}
    if settings.get(CONFIGURED_KEY):
        return False
    set_enabled(entry_path, True)
    settings[CONFIGURED_KEY] = True
    save_json(settings, settings_path)
    return True
