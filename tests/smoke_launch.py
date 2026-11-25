#!/usr/bin/env python3
"""Headless smoke test: launch Ynote on a sample note and fail on Python errors.

Run it under a virtual X server:

    xvfb-run -a python3 tests/smoke_launch.py

It starts the real app with a throwaway HOME, lets it draw a note that uses
each kind of formatting, quits it, and fails if any Python error was printed.
It checks that the app runs, not how it looks. Not collected by pytest.
"""
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_SECONDS = 4
QUIT_TIMEOUT = 5

# GTK prints exceptions raised in callbacks and failed argument conversions,
# such as the missing cairo converter, as "SomeError: ..." without exiting.
ERROR_RE = re.compile(
    r'Traceback \(most recent call last\)|^\w*(Error|Exception): ', re.M)


def sample_note():
    bold = 'Bold text'
    code = 'sudo apt-get install --no-install-recommends python3-gi-cairo'
    inline = 'between(code)letters'
    lines = [
        bold,
        'A long prose line that has to wrap to fit the narrow note width.',
        '• a bullet',
        '    ☐ a to-do with a 한글 word',
        '☑ a done to-do',
        inline,
        '---',
        code,
        'last line',
    ]
    text = '\n'.join(lines)
    code_start = text.index(code)
    inline_start = text.index('code', text.index(inline))
    return {
        'id': 'smoke',
        'title': 'smoke',
        'text': text,
        'x': 0, 'y': 0, 'w': 260, 'h': 300,
        'bold_ranges': [[0, len(bold)]],
        'code_ranges': [[code_start, code_start + len(code)]],
        'backtick_ranges': [[inline_start, inline_start + 4]],
    }


def _wait_for_group(proc):
    """Wait until every process the app started has gone, not only the one
    dbus-run-session starts it from. The app saves its notes as it quits, and
    the folder must not be removed while it is still writing there."""
    deadline = time.monotonic() + QUIT_TIMEOUT
    while time.monotonic() < deadline:
        try:
            os.killpg(proc.pid, 0)
        except ProcessLookupError:
            break
        try:
            proc.wait(0.1)
        except subprocess.TimeoutExpired:
            pass
    else:
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def main():
    if not os.environ.get('DISPLAY'):
        sys.exit('smoke test needs an X display; run it under xvfb-run')

    with tempfile.TemporaryDirectory(prefix='ynote-smoke-') as home:
        conf = os.path.join(home, '.config', 'ynote')
        os.makedirs(conf)
        with open(os.path.join(conf, 'notes.json'), 'w') as f:
            json.dump([sample_note()], f)

        env = dict(os.environ, HOME=home, GDK_BACKEND='x11',
                   PYTHONDONTWRITEBYTECODE='1')
        env.pop('WAYLAND_DISPLAY', None)
        log_path = os.path.join(home, 'ynote.log')

        # dbus-run-session keeps this instance apart from a running Ynote.
        with open(log_path, 'w') as log:
            proc = subprocess.Popen(
                ['dbus-run-session', '--', sys.executable,
                 os.path.join(ROOT, 'ynote.py')],
                cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True)

            time.sleep(RUN_SECONDS)
            exited_early = proc.poll() is not None
            if not exited_early:
                os.killpg(proc.pid, signal.SIGTERM)
                _wait_for_group(proc)

        with open(log_path) as f:
            output = f.read()

    error_lines = [ln for ln in output.splitlines() if ERROR_RE.search(ln)]
    if exited_early or error_lines:
        print('smoke test FAILED')
        if exited_early:
            # The reason for an early exit is usually at the end of the log.
            print(f'app exited early with status {proc.returncode}:')
            print('\n'.join(output.splitlines()[-20:]))
        # Draw callbacks repeat the same error on every frame, so list each
        # distinct error once with its count.
        for line in dict.fromkeys(error_lines):
            print(f'{error_lines.count(line)}x {line}')
        return 1
    print('smoke test passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
