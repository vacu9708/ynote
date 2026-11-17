import json

from ynote import autostart


def paths(tmp_path):
    return tmp_path / 'autostart' / 'ynote.desktop', tmp_path / 'settings.json'


def test_first_run_of_installed_app_enables_autostart(tmp_path):
    entry, settings = paths(tmp_path)

    assert autostart.enable_on_first_run(entry, settings, installed=True)

    assert autostart.is_enabled(entry)
    assert 'Exec=ynote' in entry.read_text()
    assert json.loads(settings.read_text()) == {'autostart_configured': True}


def test_turning_autostart_off_survives_later_runs(tmp_path):
    entry, settings = paths(tmp_path)
    autostart.enable_on_first_run(entry, settings, installed=True)

    autostart.set_enabled(entry, False)

    assert not autostart.enable_on_first_run(entry, settings, installed=True)
    assert not autostart.is_enabled(entry)


def test_source_checkout_without_package_leaves_autostart_alone(tmp_path):
    entry, settings = paths(tmp_path)

    assert not autostart.enable_on_first_run(entry, settings, installed=False)

    assert not entry.exists()
    assert not settings.exists()
    # The first run is still available once the package is installed.
    assert autostart.enable_on_first_run(entry, settings, installed=True)


def test_first_run_keeps_other_settings(tmp_path):
    entry, settings = paths(tmp_path)
    settings.write_text(json.dumps({'other': 1}))

    autostart.enable_on_first_run(entry, settings, installed=True)

    assert json.loads(settings.read_text()) == {
        'other': 1, 'autostart_configured': True}


def test_entry_switched_off_by_desktop_keys_counts_as_disabled(tmp_path):
    entry, _ = paths(tmp_path)
    entry.parent.mkdir()

    entry.write_text('[Desktop Entry]\nExec=ynote\nHidden=true\n')
    assert not autostart.is_enabled(entry)

    entry.write_text('[Desktop Entry]\nExec=ynote\n'
                     'X-GNOME-Autostart-enabled=false\n')
    assert not autostart.is_enabled(entry)


def test_disabling_a_missing_entry_is_a_no_op(tmp_path):
    entry, _ = paths(tmp_path)

    autostart.set_enabled(entry, False)

    assert not autostart.is_enabled(entry)
