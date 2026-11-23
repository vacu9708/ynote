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


# ------------------------------------------------------------------ placement

GAP = 10
TITLE_BAR = 30


def _inside(rect, area):
    x, y, w, h = rect
    ax, ay, aw, ah = area
    return ax <= x and ay <= y and x + w <= ax + aw and y + h <= ay + ah


def _overlap(rect, area):
    x, y, w, h = rect
    ax, ay, aw, ah = area
    ow = min(x + w, ax + aw) - max(x, ax)
    oh = min(y + h, ay + ah) - max(y, ay)
    return max(0, ow) * max(0, oh)


def _clamp_into(rect, area):
    x, y, w, h = rect
    ax, ay, aw, ah = area
    w, h = min(w, aw), min(h, ah)
    return (_clamp(x, ax, ax + aw - w), _clamp(y, ay, ay + ah - h), w, h)


def _best_area(rect, areas):
    """The area overlapping rect most, or the first area when none does."""
    return max(areas, key=lambda a: _overlap(rect, a)) if any(
        _overlap(rect, a) for a in areas) else areas[0]


def place_beside(near, size, areas):
    """Return (x, y) for a new note of size next to the note rect near.

    The new note goes right of near, else left of it, as long as it lands
    wholly inside one work area. Otherwise it is pulled into the work area
    near is mostly on, so it never opens in a gap between monitors.
    """
    px, py, pw, _ph = near
    w, h = size
    for x in (px + pw + GAP, px - w - GAP):
        if any(_inside((x, py, w, h), a) for a in areas):
            return x, py
    x, y, _w, _h = _clamp_into((px + pw + GAP, py, w, h), _best_area(near, areas))
    return x, y


def keep_reachable(rect, areas, fallback):
    """Return (x, y) for a saved note so its title bar can be grabbed.

    A note whose title bar is off every monitor, for example after a monitor
    was unplugged, is pulled into the fallback area. Others stay put.
    """
    x, y, w, h = rect
    if any(_overlap((x, y, w, min(h, TITLE_BAR)), a) for a in areas):
        return x, y
    nx, ny, _w, _h = _clamp_into(rect, fallback)
    return nx, ny
