"""
Reading the board from a screenshot.

Each of the 64 cells is classified on its own by color (OpenCV's HSV color space):

1. Count how many pixels in the middle of the cell fall inside each gem's hue /
   saturation / brightness range. The color with the most pixels wins, and the
   share of matching pixels is the "confidence".
2. Power gems glow and pulse, which drags their confidence down. Their dead
   center stays a bright, saturated version of their color, so a strong center
   restores confidence. A cluster of near-white sparkle pixels in the middle
   marks the gem as a power gem.
3. Cells with little color but plenty of brightness are white gems or
   hypercubes. A white gem is uniformly unsaturated. A hypercube has a white
   core with a rainbow rim that cycles every frame.

White gems and hypercubes can still look alike in a single frame, so
`HypercubeDetector` watches each cell across several frames: a white gem reads
the same every time, while a hypercube's confidence keeps jumping around.

All thresholds were tuned by hand against an Xbox 360 capture at 1080p and held
up for roughly 200 hours of unattended play.
"""

from __future__ import annotations

from collections import deque
from typing import NamedTuple

import cv2
import numpy as np

from .gems import GRID_COLS, GRID_ROWS, HYPERCUBE, UNKNOWN, power

# (hue low, hue high, saturation low, saturation high, value low, value high)
# OpenCV hue runs 0-180. Red wraps around, so it needs two ranges.
GEM_HSV_RANGES = {
    "red": [(0, 8, 200, 255, 150, 255), (172, 180, 200, 255, 150, 255)],
    "orange": [(10, 26, 200, 255, 150, 255)],
    "yellow": [(20, 38, 235, 255, 60, 255)],  # S >= 235 keeps the yellow sky background out
    "green": [(38, 55, 130, 255, 120, 255)],
    "blue": [(96, 118, 40, 255, 100, 255)],
    "purple": [(123, 155, 180, 255, 130, 255)],
}

SAMPLE_MARGIN = 0.20  # ignore the outer 20% of each cell (borders, neighbors' glow)
MIN_COLOR_CONFIDENCE = 0.12  # below this share of matching pixels the cell is "unknown"

# Power gems: rescue a low reading using the gem's bright center
POWER_CENTER_RESCUE_BELOW = 0.30
POWER_CENTER_MIN_VALUE = 200
POWER_CENTER_MIN_SATURATION = 150
POWER_RESCUED_CONFIDENCE = 0.85

# Power gems: sparkle detection in the inner 30% of the cell
SPARKLE_MARGIN = 0.35
SPARKLE_MIN_BRIGHTNESS = 220
SPARKLE_MAX_SATURATION = 70
SPARKLE_MIN_SHARE = 0.05
SPARKLE_MIN_CONFIDENCE = 0.15

# White gems and hypercubes
PALE_MAX_COLOR_CONFIDENCE = 0.25
PALE_MAX_AVG_SATURATION = 80
PALE_MIN_AVG_VALUE = 100
WHITE_MAX_P90_SATURATION = 50  # a white gem has almost no saturated pixels at all
POWER_WHITE_CENTER_MIN_VALUE = 248
POWER_WHITE_CENTER_MAX_SATURATION = 10


class Cell(NamedTuple):
    gem: str
    confidence: float


Board = list[list[Cell]]


def classify_cell(cell_bgr: np.ndarray | None) -> Cell:
    """Classify one cell image (BGR) as a gem with a confidence from 0 to 1."""
    if cell_bgr is None or cell_bgr.size == 0:
        return Cell(UNKNOWN, 0.0)
    height, width = cell_bgr.shape[:2]
    hsv = cv2.cvtColor(cell_bgr, cv2.COLOR_BGR2HSV)

    margin = int(min(height, width) * SAMPLE_MARGIN)
    sample = hsv[margin : height - margin, margin : width - margin]
    if sample.size == 0:
        return Cell(UNKNOWN, 0.0)
    total_pixels = sample.size // 3
    avg_saturation = float(np.mean(sample[:, :, 1]))
    avg_value = float(np.mean(sample[:, :, 2]))

    # 1. Which color has the most pixels in range?
    best_color, best_count = UNKNOWN, 0
    for color, ranges in GEM_HSV_RANGES.items():
        count = sum(_count_in_range(sample, r) for r in ranges)
        if count > best_count:
            best_color, best_count = color, count
    confidence = best_count / total_pixels if total_pixels > 0 else 0.0

    # 2a. Pulsing power gems read weakly; trust a bright, saturated center instead.
    if confidence < POWER_CENTER_RESCUE_BELOW and best_color != UNKNOWN:
        center = hsv[height // 2 - 2 : height // 2 + 2, width // 2 - 2 : width // 2 + 2]
        if (
            float(np.mean(center[:, :, 2])) > POWER_CENTER_MIN_VALUE
            and float(np.mean(center[:, :, 1])) > POWER_CENTER_MIN_SATURATION
        ):
            confidence = POWER_RESCUED_CONFIDENCE

    # 2b. Sparkle in the middle marks a power gem.
    is_power_gem = (
        confidence > SPARKLE_MIN_CONFIDENCE and best_color != UNKNOWN and _has_sparkle(hsv, height, width)
    )

    # 3. Bright but colorless: a white gem, a power white gem, or a hypercube.
    if (
        confidence < PALE_MAX_COLOR_CONFIDENCE
        and avg_saturation < PALE_MAX_AVG_SATURATION
        and avg_value > PALE_MIN_AVG_VALUE
    ):
        p90_saturation = float(np.percentile(sample[:, :, 1].flatten().astype(float), 90))
        if p90_saturation < WHITE_MAX_P90_SATURATION:
            center_s, center_v = hsv[height // 2, width // 2][1], hsv[height // 2, width // 2][2]
            gem = (
                power("white")
                if center_v >= POWER_WHITE_CENTER_MIN_VALUE and center_s < POWER_WHITE_CENTER_MAX_SATURATION
                else "white"
            )
            return Cell(gem, round(1.0 - avg_saturation / PALE_MAX_AVG_SATURATION, 3))
        return Cell(HYPERCUBE, round(min(p90_saturation / 100.0, 1.0), 3))

    if confidence > MIN_COLOR_CONFIDENCE:
        return Cell(power(best_color) if is_power_gem else best_color, round(confidence, 3))
    return Cell(UNKNOWN, 0.0)


def _count_in_range(hsv: np.ndarray, hsv_range: tuple) -> int:
    h_lo, h_hi, s_lo, s_hi, v_lo, v_hi = hsv_range
    mask = cv2.inRange(
        hsv, np.array([h_lo, s_lo, v_lo], dtype=np.uint8), np.array([h_hi, s_hi, v_hi], dtype=np.uint8)
    )
    return int(np.sum(mask > 0))


def _has_sparkle(hsv: np.ndarray, height: int, width: int) -> bool:
    inner = int(min(height, width) * SPARKLE_MARGIN)
    center = hsv[inner : height - inner, inner : width - inner]
    sparkle = cv2.inRange(
        center,
        np.array([0, 0, SPARKLE_MIN_BRIGHTNESS], dtype=np.uint8),
        np.array([180, SPARKLE_MAX_SATURATION, 255], dtype=np.uint8),
    )
    # Note: center.size counts all three channels, so this is 15% of the pixels.
    return np.sum(sparkle > 0) > center.size * SPARKLE_MIN_SHARE


class HypercubeDetector:
    """
    Tells hypercubes from white gems by how much a cell's reading flickers.

    Each pale cell's confidence is remembered for the last few frames. A white
    gem is static, so its readings barely move. A hypercube's rim cycles through
    colors, so its readings jump around. Call `reset()` whenever gems move,
    or the motion itself looks like flicker.
    """

    def __init__(self, history_length: int = 8, min_readings: int = 4, flicker_threshold: float = 0.07):
        self.min_readings = min_readings
        self.flicker_threshold = flicker_threshold
        self._history = [[deque(maxlen=history_length) for _ in range(GRID_COLS)] for _ in range(GRID_ROWS)]

    def update(self, row: int, col: int, confidence: float, gem: str) -> str:
        """Record a reading. Returns "hypercube" if the cell is flickering, otherwise `gem`."""
        history = self._history[row][col]
        history.append(confidence)
        if len(history) < self.min_readings:
            return gem
        return HYPERCUBE if float(np.std(list(history))) >= self.flicker_threshold else gem

    def reset(self) -> None:
        for row in self._history:
            for history in row:
                history.clear()


# Cells whose identity can depend on flicker (unknown cells are included so that a
# hypercube caught on a dark frame still builds up history).
_FLICKER_CANDIDATES = {"white", power("white"), HYPERCUBE, UNKNOWN}
UNKNOWN_FLICKER_READING = 0.5


def read_board(image: np.ndarray, grid_rect: tuple[int, int, int, int], detector: HypercubeDetector) -> Board:
    """Classify all 64 cells. `grid_rect` is (x, y, width, height) of the board in `image`."""
    gx, gy, gw, gh = grid_rect
    cell_w, cell_h = gw // GRID_COLS, gh // GRID_ROWS
    board: Board = []
    for row in range(GRID_ROWS):
        board_row = []
        for col in range(GRID_COLS):
            x, y = gx + col * cell_w, gy + row * cell_h
            gem, confidence = classify_cell(image[y : y + cell_h, x : x + cell_w])
            if gem in _FLICKER_CANDIDATES:
                reading = confidence if gem != UNKNOWN else UNKNOWN_FLICKER_READING
                gem = detector.update(row, col, reading, gem)
                if gem == HYPERCUBE:
                    confidence = max(confidence, 0.85)
            board_row.append(Cell(gem, confidence))
        board.append(board_row)
    return board


def board_state(board: Board) -> tuple[str, ...]:
    """The 64 gem names, ignoring confidence. Used to tell when the board has changed."""
    return tuple(cell[0] for row in board for cell in row)
