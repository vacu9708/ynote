"""The fonts Ynote brings for itself are found once registered."""
import os
import subprocess
import sys


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
