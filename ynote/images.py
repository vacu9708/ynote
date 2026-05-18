import os
import sys


def normalize_image_meta(meta, include_offset=False):
    # Image metadata schema:
    # {"file": "<uuid>.<ext>", "original_name": "...", "offset": N}
    meta = dict(meta or {})
    name = meta.get('file', '')

    normalized = {}
    if name:
        normalized['file'] = name if os.path.isabs(name) else os.path.basename(name)
    if meta.get('original_name'):
        normalized['original_name'] = meta.get('original_name')
    if include_offset:
        normalized['offset'] = int(meta.get('offset', 0))
    return normalized


def image_path(meta, images_dir):
    meta = normalize_image_meta(meta)
    name = meta.get('file', '')
    if not name:
        return ''
    if os.path.isabs(name):
        return name
    return os.path.join(os.fspath(images_dir), os.path.basename(name))


def referenced_image_files(notes_data, history_files=()):
    referenced = set()

    for note in notes_data or []:
        for meta in note.get('images', []):
            name = meta.get('file', '')
            if not name or os.path.isabs(name):
                continue
            referenced.add(os.path.basename(name))

    for name in history_files or ():
        if name and not os.path.isabs(name):
            referenced.add(os.path.basename(name))

    return referenced


def cleanup_orphaned_images(images_dir, referenced):
    if not os.path.isdir(images_dir):
        return []

    removed = []
    referenced = set(referenced or ())
    for name in os.listdir(images_dir):
        path = os.path.join(images_dir, name)
        if not os.path.isfile(path):
            continue
        if name in referenced:
            continue
        try:
            os.remove(path)
            removed.append(name)
        except OSError as e:
            print(f'ynote: failed to remove unused image {path}: {e}',
                  file=sys.stderr)

    return removed
