from ynote.images import (
    cleanup_orphaned_images,
    image_path,
    normalize_image_meta,
    referenced_image_files,
)


def test_normalize_image_meta_keeps_only_portable_fields():
    assert normalize_image_meta(
        {
            'file': 'nested/photo.PNG',
            'original_name': 'Photo.PNG',
            'offset': '12',
            'ignored': True,
        },
        include_offset=True,
    ) == {
        'file': 'photo.PNG',
        'original_name': 'Photo.PNG',
        'offset': 12,
    }


def test_normalize_image_meta_preserves_absolute_file_paths():
    assert normalize_image_meta({'file': '/tmp/photo.png'}) == {
        'file': '/tmp/photo.png',
    }


def test_image_path_resolves_relative_files_under_images_dir(tmp_path):
    assert image_path({'file': 'nested/photo.png'}, tmp_path) == str(
        tmp_path / 'photo.png'
    )


def test_image_path_returns_absolute_files_unchanged(tmp_path):
    assert image_path({'file': '/tmp/photo.png'}, tmp_path) == '/tmp/photo.png'


def test_referenced_image_files_uses_basenames_and_ignores_absolute_paths():
    notes = [
        {
            'images': [
                {'file': 'one.png'},
                {'file': 'nested/two.jpg'},
                {'file': '/tmp/external.png'},
                {'file': ''},
            ],
        },
        {'images': [{'file': 'three.webp'}]},
    ]

    assert referenced_image_files(notes, history_files={'history.png'}) == {
        'one.png',
        'two.jpg',
        'three.webp',
        'history.png',
    }


def test_cleanup_orphaned_images_removes_only_unreferenced_files(tmp_path):
    images_dir = tmp_path / 'images'
    images_dir.mkdir()
    keep = images_dir / 'keep.png'
    remove = images_dir / 'remove.png'
    nested = images_dir / 'nested'
    keep.write_text('keep')
    remove.write_text('remove')
    nested.mkdir()

    removed = cleanup_orphaned_images(images_dir, {'keep.png'})

    assert removed == ['remove.png']
    assert keep.exists()
    assert not remove.exists()
    assert nested.exists()


def test_cleanup_orphaned_images_missing_directory_is_noop(tmp_path):
    assert cleanup_orphaned_images(tmp_path / 'missing', set()) == []
