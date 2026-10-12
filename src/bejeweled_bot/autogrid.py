"""
Finding the board in a screenshot automatically.

Every capture card and window size puts the board somewhere different, so instead
of asking people to line up a grid by hand, try every plausible square 8x8 grid
and keep the one whose cells look most like gems.

"Looks like a gem" uses the same idea as the vision: the middle of each cell should
be mostly one gem color (or gem white). A grid that's off by half a cell straddles
four gems, so no color dominates its cells and it scores poorly.

To keep it fast, every pixel is labeled with a gem color once, and per-color
running totals (integral images) give any cell's pixel counts in constant time.
"""

from __future__ import annotations

import cv2
import numpy as np

from .vision import GEM_HSV_RANGES, SAMPLE_MARGIN

# White gems (and the white of hypercubes): pale and bright.
WHITE_RANGE = (0, 180, 0, 50, 170, 255)
GOOD_CELL = 0.30  # a cell this dominated by one color counts as "a gem"
COARSE_CELL_PX = 16  # search at a scale where cells are about this big
SAME_NEIGHBOR_PENALTY = 0.5
EXPECTED_SAME_NEIGHBORS = 30  # of the 112 neighboring pairs, a real board has roughly 15-25
REFINE_ROUNDS = 3
MIN_BOARD_SHARE = 0.45  # the board is at least this share of the frame height
MAX_BOARD_SHARE = 1.0


def _label_counts(image_bgr: np.ndarray) -> np.ndarray:
    """Integral images of per-color pixel masks: shape (colors, H+1, W+1)."""
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    masks = []
    for ranges in list(GEM_HSV_RANGES.values()) + [[WHITE_RANGE]]:
        mask = np.zeros(hsv.shape[:2], np.uint8)
        for h_lo, h_hi, s_lo, s_hi, v_lo, v_hi in ranges:
            mask |= cv2.inRange(
                hsv, np.array([h_lo, s_lo, v_lo], np.uint8), np.array([h_hi, s_hi, v_hi], np.uint8)
            )
        masks.append((mask > 0).astype(np.int32))
    sums = np.zeros((len(masks), hsv.shape[0] + 1, hsv.shape[1] + 1), np.int64)
    for i, mask in enumerate(masks):
        sums[i, 1:, 1:] = mask.cumsum(0).cumsum(1)
    return sums


def _score_grids(sums: np.ndarray, xs: np.ndarray, ys: np.ndarray, size: int):
    """
    Score every square grid of this size with its corner at (x, y) for x in xs, y in ys.
    Returns (cells that look like gems, mean dominance, neighboring cells with the same
    color), each shaped (len(ys), len(xs)).
    """
    pitch = size // 8  # the same whole-pixel cells that vision.read_board uses
    margin = int(pitch * SAMPLE_MARGIN)
    inner = pitch - 2 * margin
    shape = (len(ys), len(xs))
    if inner <= 0:
        return np.zeros(shape), np.zeros(shape), np.zeros(shape)
    area = inner * inner
    good = np.zeros(shape)
    total = np.zeros(shape)
    labels = np.zeros((8, 8, *shape), np.int8)
    for r in range(8):
        top = (ys + r * pitch + margin)[:, None]
        bottom = top + inner
        for c in range(8):
            left = (xs + c * pitch + margin)[None, :]
            right = left + inner
            counts = sums[:, bottom, right] - sums[:, top, right] - sums[:, bottom, left] + sums[:, top, left]
            dominance = counts.max(axis=0) / area
            good += dominance >= GOOD_CELL
            total += dominance
            labels[r, c] = counts.argmax(axis=0)
    # Neighboring gems are usually different colors; a patch of sky or wall is all one.
    same_neighbors = (labels[:, 1:] == labels[:, :-1]).sum(axis=(0, 1)) + (
        labels[1:, :] == labels[:-1, :]
    ).sum(axis=(0, 1))
    return good, total / 64, same_neighbors


def _search(sums, sizes, ys_for, xs_for):
    best_score, best = -1.0, None
    for size in sizes:
        ys, xs = ys_for(size), xs_for(size)
        if len(xs) == 0 or len(ys) == 0:
            continue
        good, mean, same = _score_grids(sums, xs, ys, size)
        # Mostly "how many cells look like gems", minus a penalty for uniform areas.
        score = good + mean - SAME_NEIGHBOR_PENALTY * np.maximum(0, same - EXPECTED_SAME_NEIGHBORS)
        i, j = np.unravel_index(int(np.argmax(score)), score.shape)
        if score[i, j] > best_score:
            best_score, best = float(score[i, j]), (int(xs[j]), int(ys[i]), int(size))
    return best_score, best


def find_grid(image_bgr: np.ndarray) -> tuple[tuple[int, int, int, int], float]:
    """
    Best guess for the board's [x, y, width, height] in `image_bgr`, and a confidence:
    the share of the 64 cells that look like a gem (above ~0.8 is a solid lock).
    """
    height, width = image_bgr.shape[:2]

    # 1. Coarse search on a small copy.
    scale = min(1.0, COARSE_CELL_PX * 8 / (height * 0.8))
    small = cv2.resize(image_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    sh, sw = small.shape[:2]
    sums = _label_counts(small)
    sizes = range(int(sh * MIN_BOARD_SHARE), min(sh, sw, int(sh * MAX_BOARD_SHARE)), 2)
    _, coarse = _search(
        sums,
        sizes,
        ys_for=lambda s: np.arange(0, sh - s),
        xs_for=lambda s: np.arange(0, sw - s),
    )
    if coarse is None:
        return (0, 0, 0, 0), 0.0

    # 2. Refine at full size: find each gem's center and fit the grid to them.
    x, y, size = (v / scale for v in coarse)
    gem_mask = _gem_mask(image_bgr)
    pitch_x = pitch_y = size / 8
    for _ in range(REFINE_ROUNDS):
        x, pitch_x, y, pitch_y = _fit_to_gem_centers(gem_mask, x, y, pitch_x, pitch_y)
    pitch = (pitch_x + pitch_y) / 2
    size = int(round(pitch * 8 / 8)) * 8
    grid = (int(round(x)), int(round(y)), size, size)

    sums = _label_counts(image_bgr)
    good, _, _ = _score_grids(sums, np.array([grid[0]]), np.array([grid[1]]), size)
    return grid, float(good[0, 0]) / 64


def _gem_mask(image_bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    mask = np.zeros(hsv.shape[:2], np.uint8)
    for ranges in list(GEM_HSV_RANGES.values()) + [[WHITE_RANGE]]:
        for h_lo, h_hi, s_lo, s_hi, v_lo, v_hi in ranges:
            mask |= cv2.inRange(
                hsv, np.array([h_lo, s_lo, v_lo], np.uint8), np.array([h_hi, s_hi, v_hi], np.uint8)
            )
    return mask > 0


def _fit_to_gem_centers(mask, x, y, pitch_x, pitch_y):
    """
    Find the center of the gem-colored pixels in each cell, then fit evenly spaced
    rows and columns through them (least squares). Gems sit in the middle of their
    cells, so this lines the grid up to within a pixel or two.
    """
    height, width = mask.shape
    cols, centers_x, rows, centers_y = [], [], [], []
    for r in range(8):
        for c in range(8):
            left, top = int(x + c * pitch_x), int(y + r * pitch_y)
            right, bottom = int(x + (c + 1) * pitch_x), int(y + (r + 1) * pitch_y)
            cell = mask[max(0, top) : min(height, bottom), max(0, left) : min(width, right)]
            if cell.size == 0 or cell.mean() < 0.1:
                continue  # empty or unreadable cell: leave it out of the fit
            ys, xs = np.nonzero(cell)
            cols.append(c)
            centers_x.append(max(0, left) + xs.mean())
            rows.append(r)
            centers_y.append(max(0, top) + ys.mean())
    if len(cols) < 16:
        return x, pitch_x, y, pitch_y
    pitch_x, start_x = np.polyfit(cols, centers_x, 1)
    pitch_y, start_y = np.polyfit(rows, centers_y, 1)
    # The fit gives the center of column 0; the grid starts half a cell before it.
    return start_x - pitch_x / 2, pitch_x, start_y - pitch_y / 2, pitch_y
