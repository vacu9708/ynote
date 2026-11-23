from ynote.styles import (
    BASE_CSS, DEFAULT_COLOR, PALETTE, TITLE_COLOR, code_background, mix,
    note_css, swatch_css,
)


def test_palette_has_the_seven_colors_and_yellow_is_the_default():
    assert list(PALETTE) == [
        'yellow', 'orange', 'pink', 'purple', 'blue', 'green', 'gray']
    assert DEFAULT_COLOR == 'yellow'
    assert PALETTE['yellow'] == ('#FFFF99', '#E8D800')
    assert PALETTE['gray'] == ('#E4E4E4', '#A8A8A8')


def test_mix_moves_a_color_toward_a_target():
    assert mix('#000000', '#FFFFFF', 0) == '#000000'
    assert mix('#000000', '#FFFFFF', 1) == '#FFFFFF'
    assert mix('#000000', '#646464', 0.5) == '#323232'


def test_code_background_is_the_body_pulled_70_percent_toward_light_gray():
    # 0xFF + (0xEE - 0xFF) * 0.7 = 0xF3, 0x99 + (0xEE - 0x99) * 0.7 = 0xD4
    assert code_background('yellow') == '#F3F3D4'
    assert code_background('blue') != code_background('yellow')


def test_note_css_gives_only_the_body_the_alpha_and_keeps_the_bars_opaque():
    css = note_css('blue', 0.5)

    assert 'window.note { background: rgba(191,224,255,0.50); }' in css
    assert 'box.hdr { background: #5AA9E6; }' in css
    assert 'box.btmbar { background: #5AA9E6; }' in css


def test_note_css_defaults_to_fully_opaque():
    assert 'rgba(255,255,153,1.00)' in note_css('yellow')


def test_swatch_css_has_one_rule_per_palette_color_and_a_selected_ring():
    css = swatch_css()

    for name, (body, _bar) in PALETTE.items():
        assert f'button.swatch-{name} {{ background-color: {body};' in css
    assert 'button.swatch.selected' in css
    assert 'inset 0 0 0 2px #FFFFFF' in css


def test_base_css_no_longer_hard_codes_note_backgrounds():
    css = BASE_CSS.decode()

    assert 'window.note {' not in css
    assert 'E8D800' not in css
    assert 'padding: 2px 4px 2px 2px' in css
    assert 'delete' not in css


def test_bars_stay_opaque_at_zero_opacity():
    css = note_css('blue', 0.0)

    assert 'window.note { background: rgba(191,224,255,0.00); }' in css
    assert 'box.hdr { background: #5AA9E6; }' in css


def _luminance(color):
    channels = []
    for i in (1, 3, 5):
        c = int(color[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def test_the_title_is_readable_on_every_bar_color():
    for name, (_body, bar) in PALETTE.items():
        assert _contrast(TITLE_COLOR, bar) >= 4.5, name


def test_base_css_uses_the_title_color_and_dims_an_untitled_note():
    css = BASE_CSS.decode()
    assert f'color: {TITLE_COLOR};' in css
    assert 'label.title.untitled' in css
    assert '%(title)s' not in css
