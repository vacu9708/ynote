from ynote.snap import center_at, snap_rect

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


def test_snap_rect_up_down_alone_keep_the_note_where_it_is_across():
    note = (300, 250, 400, 150)

    assert snap_rect(['down'], note, [LEFT_AREA], 0) == (300, 400, 400, 150)
    assert snap_rect(['up'], note, [LEFT_AREA], 0) == (300, 100, 400, 150)


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


from ynote.snap import keep_reachable, place_beside

# Two 2560x1440 monitors, then a 1920x1080 one starting 360px lower.
TALL_L = (0, 0, 2560, 1440)
TALL_R = (2560, 0, 2560, 1440)
SHORT = (5120, 360, 1920, 1080)
DESK = [TALL_L, TALL_R, SHORT]


def test_place_beside_goes_right_when_it_fits():
    assert place_beside((100, 100, 300, 300), (300, 300), DESK) == (410, 100)


def test_place_beside_crosses_monitors_when_it_fits_on_the_next():
    assert place_beside((2000, 400, 550, 300), (300, 300), DESK) == (2560, 400)


def test_place_beside_avoids_the_gap_above_a_lower_monitor():
    # A note flush with the right monitor's top-right corner: its right side
    # is above SHORT, where no monitor shows anything, so go left instead.
    assert place_beside((3840, 0, 1280, 1440), (300, 300), DESK) == (3530, 0)


def test_place_beside_clamps_into_the_notes_monitor_when_no_side_fits():
    assert place_beside((0, 0, 2560, 1440), (300, 300), [TALL_L]) == (2260, 0)


def test_keep_reachable_leaves_visible_notes_alone():
    assert keep_reachable((3840, 0, 1280, 1440), DESK, TALL_L) == (3840, 0)
    assert keep_reachable((5130, 340, 300, 300), DESK, TALL_L) == (5130, 340)


def test_keep_reachable_pulls_in_a_note_whose_title_bar_is_off_screen():
    assert keep_reachable((5130, 0, 335, 300), DESK, TALL_L) == (2225, 0)
    assert keep_reachable((9000, 9000, 300, 300), DESK, TALL_L) == (2260, 1140)


def test_center_at_centers_a_window_on_the_point():
    areas = [(0, 0, 1920, 1080)]

    assert center_at((960, 540), (200, 100), areas, areas[0]) == (860, 490)


def test_center_at_keeps_the_window_inside_the_monitor_of_the_point():
    areas = [(0, 0, 1920, 1080), (1920, 0, 1280, 1024)]

    # Near the right monitor's top left, the window stays on that monitor.
    assert center_at((1925, 5), (200, 100), areas, areas[0]) == (1920, 0)
