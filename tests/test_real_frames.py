"""
Real frames from the Xbox 360 (captured during the original run), read end to end:
find the board automatically, then classify all 64 cells.

The expected boards were checked by eye against the screenshots. Letters as in
helpers.py: R O Y G B P W, * for a power gem, HC for a hypercube.
"""

from pathlib import Path

import cv2
import pytest
from helpers import board_from

from bejeweled_bot.autogrid import find_grid
from bejeweled_bot.solver import find_best_move
from bejeweled_bot.vision import HypercubeDetector, read_board

FRAMES = Path(__file__).parent / "frames"

EXPECTED = {
    # Level 11, 1015x538 (half resolution), two power gems sparkling
    "framed_small.webp": """
        O Y Y B G W R G
        R G W G R O W O
        B P R W G R R W
        W R* Y B O R R O
        W B G* G Y G B P
        P B P P B R G W
        Y G Y P G O O G
        R W R B G B B Y
    """,
    # Level 13: no board frame, on a yellow sky that's nearly gem-colored
    "frameless.webp": """
        W B G Y B W P B
        R R P W O O Y W
        R R O G B G R G
        O P Y O Y O B W
        B P R R B P P Y
        B Y G W Y Y B B
        W W B P O W R Y
        P HC Y Y G O P R
    """,
    # Level 29, a hypercube and three power gems mid-sparkle
    "framed_hypercube.webp": """
        Y B B O P G P W
        W G R Y O W P O
        R R B P O R W P
        B O W R R Y O O
        Y R HC Y B G W G
        G B B P W G O B
        G P O B P B W P
        B B* G Y R W* Y* G
    """,
}


@pytest.mark.parametrize("name", list(EXPECTED))
def test_finds_and_reads_the_board(name):
    image = cv2.imread(str(FRAMES / name))
    grid, lock = find_grid(image)
    assert lock >= 0.8, f"weak lock on the board: {lock:.2f} at {grid}"

    board = read_board(image, grid, HypercubeDetector())
    expected = [[gem for gem, _ in row] for row in board_from(EXPECTED[name])]
    assert [[cell.gem for cell in row] for row in board] == expected
    assert find_best_move(board) is not None
