import cv2
import numpy as np
import pytest

from bejeweled_bot.gems import HYPERCUBE, UNKNOWN
from bejeweled_bot.vision import HypercubeDetector, board_state, classify_cell, read_board

CELL = 108  # pixels, the size of a cell in a 1080p capture

# A typical (hue, saturation, value) for each gem in OpenCV's HSV scale.
TYPICAL_HSV = {
    "red": (4, 230, 220),
    "orange": (18, 230, 220),
    "yellow": (30, 245, 220),
    "green": (45, 220, 220),
    "blue": (105, 200, 220),
    "purple": (140, 220, 220),
}


def cell_of(hsv, size=CELL):
    image = np.zeros((size, size, 3), np.uint8)
    image[:] = hsv
    return cv2.cvtColor(image, cv2.COLOR_HSV2BGR)


@pytest.mark.parametrize("color", list(TYPICAL_HSV))
def test_reads_each_gem_color(color):
    gem, confidence = classify_cell(cell_of(TYPICAL_HSV[color]))
    assert gem == color
    assert confidence > 0.9


def test_reads_white():
    assert classify_cell(cell_of((0, 15, 230))).gem == "white"


def test_dark_cells_are_unknown():
    assert classify_cell(cell_of((0, 0, 20))) == (UNKNOWN, 0.0)


def test_empty_image_is_unknown():
    assert classify_cell(np.zeros((0, 0, 3), np.uint8)) == (UNKNOWN, 0.0)


def test_sparkle_in_the_middle_marks_a_power_gem():
    hsv = np.zeros((CELL, CELL, 3), np.uint8)
    hsv[:] = TYPICAL_HSV["green"]
    cv2.circle(hsv, (CELL // 2, CELL // 2), 12, (0, 0, 255), -1)  # white-hot center
    image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    assert classify_cell(image).gem == "power_green"


def test_flicker_detector_keeps_static_cells_white():
    detector = HypercubeDetector()
    results = [detector.update(0, 0, 0.75, "white") for _ in range(8)]
    assert set(results) == {"white"}


def test_flicker_detector_spots_a_hypercube():
    detector = HypercubeDetector()
    readings = [0.3, 0.8, 0.35, 0.75, 0.4]
    results = [detector.update(0, 0, r, "white") for r in readings]
    assert results[:3] == ["white"] * 3  # not enough history yet
    assert results[-1] == HYPERCUBE


def test_reset_forgets_the_flicker():
    detector = HypercubeDetector()
    for r in [0.3, 0.8, 0.35, 0.75]:
        detector.update(0, 0, r, "white")
    detector.reset()
    assert detector.update(0, 0, 0.75, "white") == "white"


def test_reads_a_whole_board():
    colors = list(TYPICAL_HSV)
    expected = [[colors[(r + c) % len(colors)] for c in range(8)] for r in range(8)]
    hsv = np.zeros((40 + 8 * CELL, 60 + 8 * CELL, 3), np.uint8)
    for r in range(8):
        for c in range(8):
            hsv[40 + r * CELL : 40 + (r + 1) * CELL, 60 + c * CELL : 60 + (c + 1) * CELL] = TYPICAL_HSV[
                expected[r][c]
            ]
    image = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    board = read_board(image, (60, 40, 8 * CELL, 8 * CELL), HypercubeDetector())
    assert [[cell.gem for cell in row] for row in board] == expected
    assert len(board_state(board)) == 64
