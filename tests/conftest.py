"""Run the tests as Ynote runs: on GTK's X11 backend.

main() sets this before GTK loads, so that a Wayland session does not make GTK
pick Wayland. The focus tests need an X11 window, and on a machine that has a
Wayland socket they failed without it. It is set here, before any test imports
GTK, and an X display (a real one, or xvfb-run) is still needed.
"""
import os

os.environ.setdefault('GDK_BACKEND', 'x11')
