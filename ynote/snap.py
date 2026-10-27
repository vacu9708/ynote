"""Snapping used by the Ctrl + Super + arrow note shortcut.

Each monitor's work area is split into COLS columns. A snapped note takes the
column's width and keeps its own height. Rectangles are (x, y, width, height)
tuples so this module stays free of GTK.
"""

COLS = 2

HORIZONTAL = ('left', 'right')
VERTICAL = ('up', 'down')


def _clamp(value, low, high):
    return max(low, min(high, int(value)))


def _neighbor(areas, index, key):
    """Return the index of the closest work area beside areas[index]."""
    ax, ay, aw, ah = areas[index]
    best = None
    for i, (bx, by, bw, bh) in enumerate(areas):
        if i == index or by >= ay + ah or by + bh <= ay:
            continue
        if key == 'right' and bx >= ax + aw:
            gap = bx - (ax + aw)
        elif key == 'left' and bx + bw <= ax:
            gap = ax - (bx + bw)
        else:
            continue
        if best is None or gap < best[0]:
            best = (gap, i)
    return None if best is None else best[1]


def _place(area, col, y, height):
    ax, ay, aw, ah = area
    w = aw // COLS
    h = min(height, ah)
    return (ax + col * w, _clamp(y, ay, ay + ah - h), w, h)


def snap_rect(keys, rect, areas, index):
    """Return where a note at rect moves when the arrows in keys are held.

    keys lists the held arrows with the latest press last. Left/Right pick a
    column, Up/Down move the note by its own height, and a horizontal plus a
    vertical arrow go straight to that corner. Pressing Left/Right again from a
    note already in that edge column moves it onto the neighboring monitor.
    """
    area = areas[index]
    ax, ay, aw, ah = area
    w = aw // COLS
    x, y, cur_w, cur_h = rect
    h = min(cur_h, ah)
    col = _clamp((x + cur_w / 2 - ax) // w, 0, COLS - 1)

    diagonal = (any(k in HORIZONTAL for k in keys)
                and any(k in VERTICAL for k in keys))
    if not diagonal and keys[-1] in HORIZONTAL:
        key = keys[-1]
        edge = 0 if key == 'left' else COLS - 1
        if col == edge and (x, cur_w) == (ax + col * w, w):
            other = _neighbor(areas, index, key)
            if other is not None:
                return _place(areas[other], COLS - 1 - edge, y, h)

    # Later keys win when opposite arrows are both held.
    for key in keys:
        if key == 'left':
            col = 0
        elif key == 'right':
            col = COLS - 1
        elif diagonal:
            y = ay if key == 'up' else ay + ah - h
        else:
            y += -h if key == 'up' else h
    return _place(area, col, y, h)
