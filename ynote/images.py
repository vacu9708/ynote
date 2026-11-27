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


def image_files_from_metadata(images):
    files = set()
    for meta in images or []:
        name = meta.get('file', '')
        if name and not os.path.isabs(name):
            files.add(os.path.basename(name))
    return files


def state_image_files(state):
    """The image files a note's text, or a rich state of it, uses: its own
    images and those in the cells of its tables, however deep."""
    files = image_files_from_metadata(state.get('images', []))
    if state.get('doc'):
        files.update(doc_image_files(state['doc']))
    for table in state.get('tables', []) or []:
        for row in table.get('rows', []):
            for cell in row:
                files.update(state_image_files(cell))
    return files


def doc_image_files(node):
    """The image files a note of 2.0 shows, from its document."""
    files = set()
    if node.get('type') == 'image':
        name = (node.get('attrs') or {}).get('file', '')
        if name and not os.path.isabs(name):
            files.add(os.path.basename(name))
    for child in node.get('content') or []:
        files.update(doc_image_files(child))
    return files


def referenced_image_files(notes_data, history_files=()):
    referenced = set()

    for note in notes_data or []:
        referenced.update(state_image_files(note))

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
