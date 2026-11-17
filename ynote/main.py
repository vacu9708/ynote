import os
import sys

from . import __version__


def main(argv=None):
    if argv is None:
        argv = sys.argv

    if '--version' in argv[1:]:
        print(f'Ynote {__version__}')
        return 0

    # Ynote needs GTK's X11 backend (see ARCHITECTURE.md). GTK reads this when
    # it loads, so set it before importing the app. Left unset, GTK prefers any
    # Wayland socket it finds, even the desktop's own from an SSH session.
    os.environ['GDK_BACKEND'] = 'x11'
    from .app import PostItApp

    app = PostItApp()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main())
