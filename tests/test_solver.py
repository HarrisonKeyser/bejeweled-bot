from helpers import DEAD_BOARD, board_from

from bejeweled_bot.solver import (
    find_best_move,
    legal_moves,
    match_lengths,
    score_swap,
    simulate_cascade,
)


def test_background_board_has_no_moves():
    assert legal_moves(board_from(DEAD_BOARD)) == []
    assert find_best_move(board_from(DEAD_BOARD)) is None


def test_finds_a_simple_three_match():
    board = board_from("""
        O O P Y R G B Y
        B Y O G B Y R G
        R G B Y R G B Y
        B Y R G B Y R G
        R G B Y R G B Y
        B Y R G B Y R G
        R G B Y R G B Y
        B Y R G B Y R G
    """)
    move = find_best_move(board)
    # Swapping P (row 0, col 2) down with O completes O O O.
    assert move.cells == (0, 2, 1, 2)
    assert move.direction == "DOWN"
    assert move.reason == "match"


def test_match_lengths_counts_both_directions_and_power_gems():
    grid = [
        [gem for gem, _ in row]
        for row in board_from("""
        G G* G G R B Y P
        G R B Y P O R B
        G B Y P O R B Y
        R Y P O R B Y P
        B P O R B Y P O
        Y O R B Y P O R
        P R B Y P O R B
        O B Y P O R B Y
    """)
    ]
    assert match_lengths(grid, 0, 0) == (4, 3)


def test_four_in_a_row_beats_three():
    board = board_from("""
        R R B R Y P O G
        O P R Y G O P Y
        Y G O P R Y G O
        G O P R Y G O P
        P Y G O P R Y G
        O R Y G O P R Y
        Y G O P R Y G O
        G O P R Y G O P
    """)
    move = find_best_move(board)
    assert move.reason == "makes a power gem"
    assert move.cells == (0, 2, 1, 2)  # pulls the R down into R R _ R


def test_five_in_a_row_beats_four():
    board = board_from("""
        G G Y G G P O R
        P O G R Y G R O
        Y R O P R O P Y
        O P R Y O R Y P
        R Y P O P Y O R
        P O Y R Y P R O
        Y R O P O R P Y
        O P R Y R O Y P
    """)
    move = find_best_move(board)
    assert move.reason == "makes a hypercube"
    assert move.cells == (0, 2, 1, 2)


def test_hypercube_targets_the_most_common_neighbor_color():
    # The hypercube at (3,3) touches purple, orange, white and yellow.
    # Yellow is by far the most common of those, so that's the swap to make.
    board = board_from(DEAD_BOARD)
    board[3][3] = ("hypercube", 0.9)
    board[2][3] = ("purple", 0.9)
    board[3][2] = ("orange", 0.9)
    board[3][4] = ("white", 0.9)
    board[4][3] = ("yellow", 0.9)
    move = find_best_move(board)
    assert move.reason.startswith("hypercube clears every yellow")
    assert move.cells == (3, 3, 4, 3)


def _grid(text):
    return [[gem for gem, _ in row] for row in board_from(text)]


def test_power_gem_explosion_scores_more_than_a_plain_match():
    plain = _grid(DEAD_BOARD)
    plain[7][1:4] = ["green", "green", "green"]
    powered = [row[:] for row in plain]
    powered[7][2] = "power_green"
    assert simulate_cascade(plain)[0] > 0
    assert simulate_cascade(powered)[0] > simulate_cascade(plain)[0]


def test_cascades_count_gems_that_fall_into_new_matches():
    # Clearing the three greens in column 1 drops the red above them between
    # two reds on the bottom row, which makes a second match worth double.
    grid = _grid(DEAD_BOARD)
    for r in (5, 6, 7):
        grid[r][1] = "green"
    grid[4][1] = "red"
    grid[7][0] = "red"  # (7,2) is already red
    score, _ = simulate_cascade(grid)
    assert score >= 3 * 50 + 3 * 50 * 2


def test_score_includes_a_bonus_for_lower_rows():
    board = board_from("""
        O O P Y R G B Y
        B Y O G B Y R G
        R G B Y R G B Y
        B Y R G B Y R G
        R G B Y R G B Y
        B Y R G B Y R G
        R G B Y R G B Y
        B Y R G B Y R G
    """)
    assert score_swap(board, 0, 2, 1, 2) == (3 * 50 + 1 * 100, "match")
