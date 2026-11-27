import types

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

from ynote import tray
from ynote.app import PostItApp


class FakeIndicator:
    created = []

    def __init__(self, *args):
        self.args = args
        self.theme_path = self.title = self.status = None
        self.menu = self.secondary = None
        FakeIndicator.created.append(self)

    @classmethod
    def new(cls, *args):
        return cls(*args)

    def set_icon_theme_path(self, path):
        self.theme_path = path

    def set_title(self, title):
        self.title = title

    def set_status(self, status):
        self.status = status

    def set_menu(self, menu):
        self.menu = menu

    def set_secondary_activate_target(self, item):
        self.secondary = item


FAKE_MODULE = types.SimpleNamespace(
    Indicator=FakeIndicator,
    IndicatorCategory=types.SimpleNamespace(APPLICATION_STATUS='app'),
    IndicatorStatus=types.SimpleNamespace(ACTIVE='active'))


def test_indicator_is_named_after_the_icon_file_and_looks_in_its_folder(tmp_path):
    icon = tmp_path / 'icon.png'
    icon.write_bytes(b'')

    indicator = tray.make_indicator(FAKE_MODULE, str(icon))

    assert indicator.args == ('ynote', 'icon', 'app')
    assert indicator.theme_path == str(tmp_path)
    assert (indicator.title, indicator.status) == ('Ynote', 'active')


def test_indicator_falls_back_to_a_theme_icon_without_the_icon_file(tmp_path):
    indicator = tray.make_indicator(FAKE_MODULE, str(tmp_path / 'missing.png'))

    assert indicator.args == ('ynote', tray.FALLBACK_ICON_NAME, 'app')
    assert indicator.theme_path is None


def test_load_returns_none_when_no_indicator_library_is_installed(monkeypatch):
    def refuse(name, version):
        raise ValueError(f'Namespace {name} not available')

    monkeypatch.setattr(tray.gi, 'require_version', refuse)

    assert tray.load_app_indicator() is None


def test_a_note_is_named_by_its_title_then_its_first_line_then_untitled():
    assert tray.note_label('Deploy', 'ignored') == '\u2022 Deploy'
    assert tray.note_label('  ', '\n  kubectl   get pods\nmore') == \
        '\u2022 kubectl get pods'
    assert tray.note_label('', '￼\n⁠\n') == '\u2022 Untitled'
    assert tray.note_label('', '') == '\u2022 Untitled'


def test_a_long_label_is_cut():
    label = tray.note_label('x' * 80, '')
    assert len(label) == len(tray.NOTE_BULLET) + tray.MENU_LABEL_CHARS
    assert label.endswith('…')


def test_hidden_notes_label_shows_the_count():
    assert tray.hidden_notes_label(3) == 'Hidden Notes (3)'


class StubNote:
    def __init__(self, title, text='', visible=True):
        self.title = title
        self.text = text
        self._visible = visible
        self.sort_order = 0.0

    def get_visible(self):
        return self._visible

    def first_text(self):
        return self.text

    def set_hidden_count(self, count):
        self.hidden_count = count


def make_app(notes=None):
    app = PostItApp.__new__(PostItApp)
    app.notes = notes or {}
    app._indicator = FakeIndicator()
    app._hidden_notes_window = None
    app._tray_menu = None
    app.calls = []
    app.new_note = lambda: app.calls.append('new_note')
    app.raise_all = lambda: app.calls.append('raise_all')
    return app


def labels(menu):
    out = []
    for item in menu.get_children():
        if not item.get_visible():
            continue
        out.append('---' if isinstance(item, Gtk.SeparatorMenuItem)
                   else item.get_label())
    return out


def test_menu_lists_open_notes_under_a_header_then_the_actions():
    app = make_app({'a': StubNote('Alpha'),
                    'b': StubNote('', 'second line\nmore'),
                    'c': StubNote('Hidden', visible=False)})

    app._rebuild_indicator_menu()

    assert labels(app._indicator.menu) == [
        'Open Notes', '\u2022 Alpha', '\u2022 second line', '---',
        'New Note', 'Bring All to Front', 'Hidden Notes (1)', 'Quit']
    assert not app._indicator.menu.get_children()[0].get_sensitive()


def test_menu_with_one_open_note_and_no_hidden_ones_is_short():
    app = make_app({'a': StubNote('Alpha')})

    app._rebuild_indicator_menu()

    assert labels(app._indicator.menu) == [
        'Open Notes', '\u2022 Alpha', '---', 'New Note',
        'Bring All to Front', 'Quit']


def test_every_note_shows_how_many_notes_are_hidden():
    notes = {'a': StubNote('Alpha'), 'b': StubNote('Beta', visible=False),
             'c': StubNote('Gamma', visible=False)}
    app = make_app(notes)

    app._rebuild_indicator_menu()

    assert [n.hidden_count for n in notes.values()] == [2, 2, 2]


def test_menu_without_open_notes_has_no_header_or_separator():
    app = make_app({'c': StubNote('Hidden', visible=False)})

    app._rebuild_indicator_menu()

    assert labels(app._indicator.menu) == [
        'New Note', 'Hidden Notes (1)', 'Quit']
    assert labels(_rebuilt(make_app())) == ['New Note', 'Quit']


def _rebuilt(app):
    app._rebuild_indicator_menu()
    return app._indicator.menu


def test_bring_all_to_front_is_listed_and_is_the_middle_click_target():
    # The indicator library ignores a middle click on a hidden target.
    for notes in ({'a': StubNote('Alpha')},
                  {'a': StubNote('Alpha'), 'b': StubNote('Beta')}):
        app = make_app(notes)

        app._rebuild_indicator_menu()

        target = app._indicator.secondary
        assert target.get_label() == 'Bring All to Front'
        assert target in app._indicator.menu.get_children()
        assert target.get_visible() and target.get_sensitive()


def test_the_indicator_keeps_one_menu_whose_items_follow_the_notes():
    notes = {'a': StubNote('Alpha')}
    app = make_app(notes)
    menus = []
    app._indicator.set_menu = menus.append

    app._rebuild_indicator_menu()
    notes['b'] = StubNote('Beta')
    app._rebuild_indicator_menu()

    assert len(menus) == 1
    assert labels(menus[0]) == [
        'Open Notes', '\u2022 Alpha', '\u2022 Beta', '---',
        'New Note', 'Bring All to Front', 'Quit']


def test_without_an_indicator_there_is_no_menu_to_build():
    app = make_app({'a': StubNote('Alpha')})
    app._indicator = None

    app._rebuild_indicator_menu()

    assert app._tray_menu is None


def test_show_notes_raises_the_notes_or_makes_one_when_none_are_visible():
    app = make_app({'a': StubNote('Alpha', visible=False)})
    app._show_notes()
    assert app.calls == ['new_note']

    app = make_app({'a': StubNote('Alpha')})
    app._show_notes()
    assert app.calls == ['raise_all']
