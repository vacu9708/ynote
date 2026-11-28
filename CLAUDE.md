# Working on Ynote

How the code is organized is in [ARCHITECTURE.md](ARCHITECTURE.md), and how
to run, test, and package it in [CONTRIBUTING.md](CONTRIBUTING.md). This file
holds what those don't: how the user wants the work done.

## Talking with the user

- The user writes in Korean. Answer in Korean, but write everything in the
  repository in English: code, comments, docs, commit messages, and test
  data, but for Korean text that tests how Korean is handled.
- They try each change themselves: see "After every change".

## Docs

- **README.md is taken in at a glance.** One look at it tells what Ynote is:
  a short list of features and the pictures, then install. Nothing in it is
  tedious to read. Say each thing once; fold a new feature into an existing
  line rather than adding a bullet; leave out what the UI shows (menus,
  tooltips) and what the keyboard shortcuts list. The one hidden thing it
  keeps is the way to them: F1. Re-read the whole README after editing it.
- **The README pictures show as much of what Ynote does as they can**: every
  element a note holds, colors, the note menu, find, hidden notes.
  A new feature goes into them (`tools/readme_screenshot.py`).
- **The keyboard shortcuts** (F1, `menus.helpPage()`) are made from the
  actions (`web/src/actions.js`): every action with keys or Markdown. The
  README does not list shortcuts; tooltips and menus show each action's.
- Update ARCHITECTURE.md when a mechanism changes. After a visible UI change,
  regenerate the README screenshots (see CONTRIBUTING.md).

## Testing: end to end

- **Every behavior is proven in the real app, end to end.** A change gets an
  end-to-end test of what it does, one test per intended behavior, listed in
  [tests/e2e/BEHAVIORS.md](tests/e2e/BEHAVIORS.md): normal cases and the
  small edge cases alike. Not a unit test of internals: unit tests with fake
  windows passed while about ten real bugs were there. Unit tests stay only
  for pure logic (Markdown, storage, models, snapping, search).
- `tests/e2e/run.sh all` installs the built package in Ubuntu 26.04 and 22.04
  containers with a window manager and drives it with real input, about a
  minute. Only there is a test meaningful: without a window manager, focus
  between windows behaves otherwise.
- After writing a test for a fixed bug, put the bug back and see the test
  fail: several tests passed without testing anything until checked so.
- Test where edge cases hide, down to the small details: editing, the cursor
  and selections, formats, tables, expands, the clipboard, wrapping. A simple
  feature with little room for edge cases, or whose failure hardly matters,
  is left out until it matters, as the tray, opacity (it needs a compositor),
  and two monitors are; weigh that before building test machinery for it.
- When what should happen is unclear, follow Confluence, and note any
  exception and why in BEHAVIORS.md.

## After every change

1. Run every check: `./test.sh`, then `tests/e2e/run.sh all`. If pytest cannot import `tests.…`, another
   installed `tests` package is shadowing the repo's; run the suite with the
   repo's folder registered first:

   ```bash
   python3 -c "import sys,types,os; sys.path.insert(0,os.getcwd()); \
   m=types.ModuleType('tests'); m.__path__=[os.path.join(os.getcwd(),'tests')]; \
   sys.modules['tests']=m; import pytest; sys.exit(pytest.main(['-q']))"
   ```

2. Rebuild the package (`./build-deb.sh`). Do not start, stop, or restart
   Ynote, any version: the user runs it themselves, with their own `./dev.sh`
   (rebuild, reinstall, run; excluded from git in `.git/info/exclude`).
3. After each commit, tell the user to run `./dev.sh`: installing needs their
   sudo, and it reinstalls with `--reinstall`, as apt skips a build that keeps
   the released version, as every build between releases does.

## Test note

The user tries each change in their note titled "test note", written in
[tools/test-note.md](tools/test-note.md). When a change adds something the
note should show, or changes how something in it looks or works, edit that
file, and ask the user to quit Ynote before running `python3 tools/test_note.py`.
It writes the note into the real `~/.config/ynote/notes.json`, after copying
the file to `notes.json.bak`, keeping where the note is and its size.

## Checking UI headlessly

- To look at something, as when a test fails: each failed end-to-end test
  leaves a screenshot and the app's log in `tests/e2e/out/`. For a look of
  your own, render the real window under
  `xvfb-run -a dbus-run-session -- python3 …`.
- Capture by cropping the screen (`Gdk.pixbuf_get_from_window` on the root
  window), never a window's own surface: that aborts inside cairo since a
  libxrender1 update.
- Never write to the real `~/.config/ynote` (`tools/test_note.py` aside):
  give the script a throwaway HOME.

## Design rules learned so far

- Markdown shown in a menu or tooltip must also work when typed.
- Icons are drawn with 2px strokes (`web/src/icons.js`), to stand beside the
  bold labels.
- Every command must keep the cursor in view (`scrollIntoView()` on its
  transaction).
- Where Ynote 1.x and Confluence differ, or what should happen is unclear,
  try it in Confluence and do as it does.

## Branches, commits, and releases

- Work happens on `dev`, each feature on its own branch off it. `main` gets
  only finished, tested work, and every release is made from it.
- Commit each feature, or each step of a large one, as soon as it is done and
  its checks pass, so every commit builds and passes the tests on its own.
  Features batched and committed later can't be split, since they change the
  same lines.
- Messages: `[feature]`, `[fix]`, `[docs]`, `[test]`, or `[release]`, a summary
  in plain words, then bullets on what the user sees.
- A release bumps `__version__` in `ynote/__init__.py`, is committed as
  `[release] Release X.Y.Z`, and is tagged `Release_X.Y.Z` (a lightweight tag).
  Push the commit and the tag. The GitHub release with the `.deb` from `dist/`
  is made by the user.
