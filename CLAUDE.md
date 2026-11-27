# Working on Ynote

How the code is organized is in [ARCHITECTURE.md](ARCHITECTURE.md), and how
to run, test, and package it in [CONTRIBUTING.md](CONTRIBUTING.md). This file
holds what those don't: how the user wants the work done.

## Talking with the user

- The user writes in Korean. Answer in Korean.
- They want each change visible right away: see "After every change".

## Docs

- **README.md must stay as short as possible, well organized, and without any
  redundancy.** A long README makes users not want to read it. Say each thing
  once, in the section it belongs to; fold a new feature into an existing line
  rather than adding a bullet; leave out what the UI already shows (menus,
  tooltips). Re-read the whole README after editing it.
- **Help** (`ynote/help.py`) lists only what nothing on screen shows. The
  Format and Insert menus show each item's shortcut and Markdown, so those are
  not in Help.
- Update ARCHITECTURE.md when a mechanism changes. After a visible UI change,
  regenerate the README screenshots (see CONTRIBUTING.md).

## After every change

1. Run every check: `./test.sh`. If pytest cannot import `tests.…`, another
   installed `tests` package is shadowing the repo's; run the suite with the
   repo's folder registered first:

   ```bash
   python3 -c "import sys,types,os; sys.path.insert(0,os.getcwd()); \
   m=types.ModuleType('tests'); m.__path__=[os.path.join(os.getcwd(),'tests')]; \
   sys.modules['tests']=m; import pytest; sys.exit(pytest.main(['-q']))"
   ```

2. Rebuild the package (`./build-deb.sh`) and restart the running Ynote from
   the checkout, without being asked: find it with
   `pgrep -a python3 | grep ynote.py` (`pgrep -f` matches its own shell), stop
   it with `kill -TERM` (it saves first), then
   `setsid nohup python3 <checkout>/ynote.py &`. Installing the `.deb` needs
   sudo, so give the user `sudo apt install ./dist/ynote_<version>.deb`.

## Checking UI headlessly

- Render the real window under `xvfb-run -a dbus-run-session -- python3 …`.
- Capture by cropping the screen (`Gdk.pixbuf_get_from_window` on the root
  window), never a window's own surface: that aborts inside cairo since a
  libxrender1 update.
- Never write to the real `~/.config/ynote`: give the script a throwaway HOME,
  or point `ynote.note_window.IMAGES_DIR` at a scratch folder before inserting
  images.

## Design rules learned so far

- Structure lives in the note's text when it can (list markers,
  `TABLE_MARKER`, expand marks), so no saved field is needed, undo, search and
  copying work as they are, and an older version still shows readable text.
- Markdown shown in a menu must also work when typed.
- Bar icons are drawn (`StrokeIcon`, 2px lines): the theme's symbolic icons
  are 1px and too thin beside the bold labels.
- Every key the note handles itself must keep the cursor in view
  (`_on_tv_key_press` scrolls after any handled key).

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
