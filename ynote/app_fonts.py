"""The fonts that come with Ynote, for it alone.

A heading is bold, and bold in a heading makes it bolder, as in Confluence.
The heading font's heaviest weight on most systems is its bold, so Ynote
brings the Black weight of Noto Serif, and of Noto Serif KR for Korean, in
ynote/fonts/, under the SIL Open Font License that comes with them.
"""
import ctypes
import ctypes.util
import os

FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')


def register_fonts(fonts_dir=FONTS_DIR):
    """Make the fonts in fonts_dir usable by this process, not installed for
    others. Call it before the first text is laid out: Pango reads the fonts
    fontconfig has when it starts. Returns whether they were added."""
    if not os.path.isdir(fonts_dir):
        return False
    name = ctypes.util.find_library('fontconfig')
    if name is None:
        return False
    try:
        fontconfig = ctypes.CDLL(name)
        add_dir = fontconfig.FcConfigAppFontAddDir
    except (OSError, AttributeError):
        return False
    add_dir.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    add_dir.restype = ctypes.c_int
    # No config means the current one, which Pango uses as well.
    return bool(add_dir(None, os.fsencode(fonts_dir)))
