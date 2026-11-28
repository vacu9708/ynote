"""Fixtures of the end-to-end tests. They run only in the test container
(tests/e2e/run.sh), where Ynote is installed from its package; elsewhere,
such as a plain `pytest` of the unit tests, they are not collected."""
import os
import shutil
import tempfile

import pytest

if not os.environ.get('YNOTE_E2E'):
    collect_ignore_glob = ['*']
else:
    from tests.e2e.driver import App, Input, screenshot

    OUT = os.environ.get('YNOTE_E2E_OUT', '/out')
    # The installed app; YNOTE_COMMAND runs another, such as a checkout.
    COMMAND = os.environ.get('YNOTE_COMMAND', 'ynote').split()


    @pytest.fixture(scope='session')
    def inp():
        return Input()

    @pytest.fixture
    def home():
        path = tempfile.mkdtemp(prefix='ynote-home-')
        yield path
        shutil.rmtree(path, ignore_errors=True)

    def pytest_configure(config):
        config.addinivalue_line(
            'markers', 'ime: Ynote takes keys through the Korean input method')
        config.addinivalue_line(
            'markers', "gnome: Ynote runs on GNOME's window manager (tests/e2e/gnome.py)")

    @pytest.fixture
    def app(home, inp, request):
        """Ynote with a HOME of its own, not started yet, typed into
        through the input method for a test marked ime."""
        a = App(home, inp, COMMAND,
                ime=request.node.get_closest_marker('ime') is not None)
        yield a
        if getattr(request.node, 'failed', False):
            name = request.node.name.replace('/', '_')
            try:
                screenshot(os.path.join(OUT, f'{name}.png'))
                shutil.copy(a.log, os.path.join(OUT, f'{name}.log'))
            except Exception:
                pass
        a.quit()

    def pytest_collection_modifyitems(config, items):
        """SHARD=i/n keeps every n-th test from the i-th, so n containers
        share the tests evenly."""
        shard = os.environ.get('SHARD')
        if not shard:
            return
        index, count = (int(v) for v in shard.split('/'))
        keep = [t for i, t in enumerate(items) if i % count == index]
        config.hook.pytest_deselected(
            items=[t for t in items if t not in keep])
        items[:] = keep

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(item, call):
        outcome = yield
        report = outcome.get_result()
        if report.when == 'call' and report.failed:
            item.failed = True
