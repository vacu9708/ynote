import types

from ynote import tray


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
