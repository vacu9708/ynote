"""Web views for Ynote 2.0's pages: a note's (note.html) and the menus'
(menu.html), each a page of ynote/web/ that talks to its window as JSON."""
import json
import os
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('WebKit2', '4.1')
from gi.repository import Gdk, GLib, WebKit2

from .config import PACKAGE_DIR

WEB_DIR = os.path.join(PACKAGE_DIR, 'web')


def page_uri(name):
    return GLib.filename_to_uri(os.path.join(WEB_DIR, name), None)


# Every page runs in one web process: a process each would take about 250 MB
# per note. A new view is related to a view that is still open.
_views = []
_settings = None


def _shared_settings():
    """The settings of every view, one object made before the first view.
    A view made with the default settings starts its page with hardware
    acceleration; turned off after, with a second page in the process, the
    web process crashed on a real GPU (not under Xvfb)."""
    global _settings
    if _settings is None:
        _settings = WebKit2.Settings()
        _settings.set_allow_file_access_from_file_urls(True)
        # GL compositing costs hundreds of MB per note on some systems and
        # gives a note nothing it needs.
        _settings.set_hardware_acceleration_policy(
            WebKit2.HardwareAccelerationPolicy.NEVER)
        _settings.set_enable_back_forward_navigation_gestures(False)
        # The wheel moves the text at once, as GTK's views and 1.x do: an
        # animated scroll, drawn in software, lagged behind the wheel.
        _settings.set_enable_smooth_scrolling(False)
        _settings.set_enable_developer_extras(bool(os.environ.get('YNOTE_DEBUG')))
        _settings.set_enable_write_console_messages_to_stdout(True)
    return _settings


def new_web_view(on_message, page):
    """A web view showing a page of ynote/web/, whose messages, as dicts,
    go to on_message(). Nothing navigates away from the page."""
    live = [v for v in _views if v.get_parent() is not None]
    # A view of its own content manager, or the pages' messages would reach
    # every view: a related view shares its relative's.
    props = {'settings': _shared_settings(),
             'user_content_manager': WebKit2.UserContentManager()}
    if live:
        props['related_view'] = live[0]
    view = WebKit2.WebView(**props)
    view.set_background_color(Gdk.RGBA(0, 0, 0, 0))
    uri = page_uri(page)

    def received(_manager, result):
        try:
            message = json.loads(result.get_js_value().to_string())
        except (ValueError, AttributeError):
            return
        on_message(message)

    def decide(_view, decision, kind):
        # A file dropped on the page, or a link, would navigate away from it.
        if kind != WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            return False
        if decision.get_navigation_action().get_request().get_uri() == uri:
            return False
        decision.ignore()
        return True

    manager = view.get_user_content_manager()
    manager.register_script_message_handler('ynote')
    manager.connect('script-message-received::ynote', received)
    view.connect('decide-policy', decide)
    view.connect('context-menu', lambda *_: True)
    _views.append(view)
    view.load_uri(uri)
    return view


def run_js(view, script):
    view.evaluate_javascript(script, -1, None, None, None, None, None)


def call_js(view, function, *args):
    """Call a function of the page with arguments sent as JSON."""
    run_js(view, f'{function}({", ".join(json.dumps(a) for a in args)})')


def unhandled(kind, page):
    print(f'ynote: {page} sent {kind!r}, which is not handled', file=sys.stderr)
