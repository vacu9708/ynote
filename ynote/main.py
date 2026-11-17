import os
import sys

from . import __version__
from .app import PostItApp


def main(argv=None):
    if argv is None:
        argv = sys.argv

    if '--version' in argv[1:]:
        print(f'Ynote {__version__}')
        return 0

    if (os.environ.get('WAYLAND_DISPLAY')
            and os.environ.get('GDK_BACKEND') != 'x11'):
        os.environ['GDK_BACKEND'] = 'x11'
        os.execv(sys.executable, [sys.executable] + list(argv))

    app = PostItApp()
    return app.run(argv)


if __name__ == '__main__':
    sys.exit(main())

