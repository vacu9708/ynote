"""Bold in a heading, which is bold already, makes it bolder, as in
Confluence: in a real note, where bold and a heading meet, the heading's
Black weight is put, and taken away with either."""
import os
import subprocess
import sys

from gi.repository import Pango

from tests.real_note import make_note, settle


def bolder(note):
    return note._get_tag_ranges(note._heading_bold_tag)


def test_bold_in_a_heading_is_bolder_and_only_there():
    note = make_note(['Title here', 'body'])
    buf = note.tv.get_buffer()
    it = buf.get_iter_at_offset
    buf.apply_tag(note._heading_tag, it(0), it(10))
    buf.apply_tag(note._bold_tag, it(6), it(13))
    settle()

    assert bolder(note) == [[6, 10]]
    assert note._heading_bold_tag.get_property('weight') == Pango.Weight.HEAVY

    buf.remove_tag(note._heading_tag, it(0), it(10))
    settle()
    assert bolder(note) == []


def test_the_fonts_ynote_brings_are_found():
    # In a process of its own, as Ynote registers them before Pango starts.
    script = (
        'from ynote.app_fonts import register_fonts\n'
        'assert register_fonts()\n'
        'from gi.repository import PangoCairo\n'
        'faces = {(f.get_name(), face.get_face_name()) for f in\n'
        '         PangoCairo.FontMap.get_default().list_families()\n'
        '         for face in f.list_faces()}\n'
        "print(('Noto Serif', 'Black') in faces,\n"
        "      ('Noto Serif KR', 'Black') in faces)\n")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    found = subprocess.run([sys.executable, '-c', script], cwd=root,
                           capture_output=True, text=True)
    assert found.stdout.split() == ['True', 'True'], found.stderr
