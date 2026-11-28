"""The popup window that shows Ynote 2.0's menus: Format, Insert, a note's
menu, right-click menus, and the menu that follows / as it is typed.

It is a window of its own, as GTK's menus are, so a menu may be larger than
its note, or reach past a collapsed one. A note's page says what the menu
holds and where it hangs (web/src/menus.js); this window shows it there,
inside the monitor, and sends back what was chosen.

Opened by a click or a key, a menu takes the keyboard and the mouse, as a
GTK menu does: a click anywhere else closes it, and its keys are its own. The
menu that follows typed text takes nothing: the note keeps the keys and
passes on the ones that move in the menu (key()).
"""
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk

from .web_view import call_js, new_web_view, unhandled

# Transparent room around the menu's card for its shadow (--room in menu.css).
SHADOW_ROOM = 14
# Between the menu and what it hangs from.
GAP = 2

KEYS = {
    Gdk.KEY_Up: 'up', Gdk.KEY_Down: 'down', Gdk.KEY_Home: 'home',
    Gdk.KEY_End: 'end', Gdk.KEY_Return: 'enter', Gdk.KEY_KP_Enter: 'enter',
    Gdk.KEY_space: 'enter', Gdk.KEY_Tab: 'down', Gdk.KEY_ISO_Left_Tab: 'up',
}


class WebPopup(Gtk.Window):
    def __init__(self):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
        self.set_app_paintable(True)
        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        self._composited = visual is not None and screen.is_composited()
        if self._composited:
            self.set_visual(visual)
        # The room around the menu for its shadow, which only a compositor
        # draws; without one it would be black.
        self._room = SHADOW_ROOM if self._composited else 0
        self.view = new_web_view(self._on_message, 'menu.html')
        self.add(self.view)
        self.view.show()
        self._ready = False
        self._waiting = None
        self._owner = None
        self._anchor = None
        self._side = 'below'
        self._takes_input = False
        self._typing = False
        self._grabbed = None
        self._size = (0, 0)
        self._focus_watch = None
        self._active_at_open = 0
        self.connect('key-press-event', self._on_key)
        self.connect('button-press-event', self._on_press)
        self.view.connect('web-process-terminated', self._on_crash)

    # --- opening and closing ----------------------------------------------

    def open(self, owner, spec, anchor, side='below', takes_input=True):
        """Show a menu for a note. anchor is (x, y, width, height) on the
        screen; the menu hangs below it or above it (side), or flips to the
        other side where the monitor ends."""
        # A new menu of the same note replaces its menu, which is not closed
        # for it: the note already keeps the new one.
        if self._owner is not None and self._owner is not owner:
            self.close()
        else:
            self._release()
        self._owner = owner
        self._anchor = anchor
        self._side = side
        self._takes_input = takes_input
        # A menu with a field to type in, as the emoji picker's, takes keys
        # in its page: typing, Korean too, and moving with the arrows.
        self._typing = bool(spec.get('emoji'))
        spec = dict(spec, flat=not self._composited)
        if self._ready:
            call_js(self.view, 'menu.show', spec)
        else:
            self._waiting = spec

    def close(self):
        """Close the menu, and tell the note it is closed."""
        owner, self._owner = self._owner, None
        self._release()
        self.hide()
        if owner is not None:
            owner.popup_closed()

    @property
    def owner(self):
        return self._owner

    @property
    def grabbed(self):
        return self._grabbed is not None

    def key(self, name):
        """A key typed into the note while a menu follows the text."""
        call_js(self.view, 'menu.key', name)

    def _show(self, width, height):
        if self._owner is None:
            return
        self._size = (width, height)
        ax, ay, aw, ah = self._anchor
        display = Gdk.Display.get_default()
        monitor = (display.get_monitor_at_point(ax, ay)
                   or display.get_primary_monitor() or display.get_monitor(0))
        area = monitor.get_workarea()
        # Taller than the monitor, the menu scrolls.
        height = min(height, area.height - 2 * GAP)
        below = ay + ah + GAP
        above = ay - GAP - height
        fits_below = below + height <= area.y + area.height
        fits_above = above >= area.y
        if self._side == 'above':
            y = above if fits_above or not fits_below else below
        else:
            y = below if fits_below or not fits_above else above
        y = max(area.y, min(y, area.y + area.height - height))
        x = max(area.x, min(ax, area.x + area.width - width))
        room = self._room
        self.resize(width + 2 * room, height + 2 * room)
        self.move(x - room, y - room)
        self.show()
        if self._takes_input:
            # A window not mapped yet cannot be grabbed; try again once it is.
            if not self._grab():
                GLib.timeout_add(30, self._grab_later, 20)
            self._watch_focus()
            if self._typing:
                self.view.grab_focus()

    # --- closing when the focus goes elsewhere ----------------------------
    #
    # On GNOME, Ynote's windows are X windows in a Wayland desktop: a click
    # on another app, or on the desktop, never reaches the X server, so the
    # grab cannot see it. The window manager's active window does change, to
    # a window not Ynote's or to none, and that closes the menu.

    def _active_xid(self):
        window = Gdk.Screen.get_default().get_active_window()
        if window is None:
            return 0
        try:
            return window.get_xid()
        except AttributeError:
            return 0

    def _ours(self):
        xids = set()
        for window in Gtk.Window.list_toplevels():
            gdk_window = window.get_window()
            if gdk_window is not None and hasattr(gdk_window, 'get_xid'):
                xids.add(gdk_window.get_xid())
        return xids

    def _watch_focus(self):
        if self._focus_watch:
            GLib.source_remove(self._focus_watch)
        self._active_at_open = self._active_xid()
        self._focus_watch = GLib.timeout_add(150, self._check_focus)

    def _check_focus(self):
        if self._owner is None or not self.get_visible():
            self._focus_watch = None
            return False
        active = self._active_xid()
        # Opened from the tray, no window of Ynote's is active: only a change
        # from that counts.
        if active != self._active_at_open and active not in self._ours():
            self._focus_watch = None
            self.close()
            return False
        return True

    def _grab(self):
        """Take the mouse and keys, as a GTK menu does; whether it could."""
        window = self.get_window()
        if window is None or self._owner is None:
            return False
        if self._grabbed:
            return True
        seat = window.get_display().get_default_seat()
        status = seat.grab(window, Gdk.SeatCapabilities.ALL, True,
                           None, None, None, None)
        if status != Gdk.GrabStatus.SUCCESS:
            return False
        self._grabbed = seat
        # Within Ynote, a click on another of its windows comes here too.
        self.grab_add()
        return True

    def _grab_later(self, tries):
        if self._owner is None or self._grab() or tries <= 1:
            return False
        GLib.timeout_add(30, self._grab_later, tries - 1)
        return False

    def _release(self):
        if self._grabbed is not None:
            self._grabbed.ungrab()
            self._grabbed = None
        if Gtk.grab_get_current() is self:
            self.grab_remove()

    # --- events -------------------------------------------------------------

    def _inside(self, x_root, y_root):
        window = self.get_window()
        if window is None or not self.get_visible():
            return False
        _ok, wx, wy = window.get_origin()
        width, height = self._size
        left, top = wx + self._room, wy + self._room
        return left <= x_root < left + width and top <= y_root < top + height

    def _on_press(self, _window, event):
        # A press on the menu goes to its page; one anywhere else, on a note
        # or past Ynote's windows, closes the menu and does nothing more.
        if self._inside(event.x_root, event.y_root):
            return False
        self.close()
        return True

    def _on_key(self, _window, event):
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if self._typing:
            return False
        name = KEYS.get(event.keyval)
        if name is None:
            char = chr(Gdk.keyval_to_unicode(event.keyval) or 0)
            name = char if char.isprintable() and char.strip() else None
        if name is not None:
            self.key(name)
        return True

    def _on_crash(self, _view, reason):
        # The menus' page reloads, as a note's does, or no menu would open.
        print(f'ynote: the menus stopped ({reason}); reloading', file=sys.stderr)
        self._ready = False
        self.close()
        self.view.reload()

    def _on_message(self, message):
        kind = message.get('type')
        if kind == 'ready':
            self._ready = True
            if self._waiting is not None:
                spec, self._waiting = self._waiting, None
                call_js(self.view, 'menu.show', spec)
        elif kind == 'size':
            self._show(int(message['width']), int(message['height']))
        elif kind == 'pick':
            # The note hears what was chosen before it hears the menu close,
            # which would end the menu it was chosen from.
            owner = self._owner
            if owner is not None:
                owner.popup_pick(message.get('id'), message.get('value'))
            self.close()
        elif kind == 'change':
            if self._owner is not None:
                self._owner.popup_change(message.get('id'), message.get('value'))
        else:
            unhandled(kind, 'menu.html')


_popup = None


def popup():
    """The one popup window, made when a menu is first opened."""
    global _popup
    if _popup is None:
        _popup = WebPopup()
    return _popup

