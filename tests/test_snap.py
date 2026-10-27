from ynote.snap import snap_rect

# Two 2000x800 work areas side by side, so columns are 1000 wide.
LEFT_AREA = (0, 0, 2000, 800)
RIGHT_AREA = (2000, 0, 2000, 800)
AREAS = [LEFT_AREA, RIGHT_AREA]


def test_snap_rect_left_right_pick_column_and_keep_height_and_y():
    note = (300, 250, 400, 150)

    assert snap_rect(['left'], note, [LEFT_AREA], 0) == (0, 250, 1000, 150)
    assert snap_rect(['right'], note, [LEFT_AREA], 0) == (1000, 250, 1000, 150)


def test_snap_rect_up_down_move_by_note_height():
    note = (1000, 300, 1000, 150)

    assert snap_rect(['down'], note, [LEFT_AREA], 0) == (1000, 450, 1000, 150)
    assert snap_rect(['up'], note, [LEFT_AREA], 0) == (1000, 150, 1000, 150)


def test_snap_rect_up_down_stop_flush_with_screen_edges():
    near_top = (0, 100, 1000, 150)
    near_bottom = (0, 600, 1000, 150)

    assert snap_rect(['up'], near_top, [LEFT_AREA], 0) == (0, 0, 1000, 150)
    assert snap_rect(['down'], near_bottom, [LEFT_AREA], 0) == (0, 650, 1000, 150)


def test_snap_rect_two_arrows_go_to_corner():
    note = (1000, 300, 1000, 150)

    assert snap_rect(['left', 'down'], note, [LEFT_AREA], 0) == (0, 650, 1000, 150)
    assert snap_rect(['down', 'left'], note, [LEFT_AREA], 0) == (0, 650, 1000, 150)
    assert snap_rect(['right', 'up'], note, [LEFT_AREA], 0) == (1000, 0, 1000, 150)


def test_snap_rect_later_arrow_wins_when_opposite_arrows_are_held():
    note = (0, 0, 1000, 150)

    assert snap_rect(['left', 'right'], note, [LEFT_AREA], 0) == (1000, 0, 1000, 150)


def test_snap_rect_respects_work_area_offset():
    area = (70, 27, 2490, 1413)  # dock on the left, top bar above

    assert snap_rect(['right', 'down'], (500, 500, 300, 300), [area], 0) == \
        (1315, 1140, 1245, 300)


def test_snap_rect_limits_height_to_work_area():
    tall = (0, 0, 1000, 1200)

    assert snap_rect(['down'], tall, [LEFT_AREA], 0) == (0, 0, 1000, 800)


def test_snap_rect_crosses_to_neighbor_monitor_from_edge_column():
    right_edge = (1000, 400, 1000, 150)
    left_edge = (2000, 400, 1000, 150)

    assert snap_rect(['right'], right_edge, AREAS, 0) == (2000, 400, 1000, 150)
    assert snap_rect(['left'], left_edge, AREAS, 1) == (1000, 400, 1000, 150)


def test_snap_rect_stays_when_no_neighbor_monitor():
    left_edge = (0, 400, 1000, 150)

    assert snap_rect(['left'], left_edge, AREAS, 0) == left_edge


def test_snap_rect_unsnapped_note_snaps_before_crossing():
    near_right = (1200, 400, 500, 150)

    assert snap_rect(['right'], near_right, AREAS, 0) == (1000, 400, 1000, 150)


def test_snap_rect_diagonal_does_not_cross_monitors():
    right_edge = (1000, 0, 1000, 150)

    assert snap_rect(['right', 'down'], right_edge, AREAS, 0) == (1000, 650, 1000, 150)
