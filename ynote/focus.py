"""Showing a window in front of the others when the user asked for it from
somewhere outside Ynote, such as the tray menu."""
import gi
from gi.repository import GLib

try:
    gi.require_version('GdkX11', '3.0')
    from gi.repository import GdkX11
except (ImportError, ValueError):
    GdkX11 = None


AGAIN_MS = 250


def present_now(window):
    """Show `window` and bring it to the front.

    A choice in the tray menu reaches Ynote without the time of the click, so
    GNOME Shell takes the window for one that opened by itself and leaves it
    behind the window in use. The X server's current time says that the user
    just asked for it. The shell also hands the focus back to the window that
    had it as its menu closes, which may come after the first request, so the
    window is asked forward once more a moment later."""
    window.show()
    if not _present_with_server_time(window):
        window.present()
        return
    GLib.timeout_add(AGAIN_MS, _present_again, window)


def _present_with_server_time(window):
    gdk_window = window.get_window()
    if GdkX11 is None or not isinstance(gdk_window, GdkX11.X11Window):
        return False
    window.present_with_time(GdkX11.x11_get_server_time(gdk_window))
    return True


def _present_again(window):
    if window.get_visible():
        _present_with_server_time(window)
    return False
