"""
Calibration: find the board, check every gem reads correctly, and sample colors.

Opens a live view with the 8x8 grid and each cell's reading drawn on top. The board
is found automatically when it opens; the keys are for fine-tuning.

    G         find the board automatically again
    W A S D   move the grid by 2 px          I / K   shorter / taller
    J / L     narrower / wider               P       print the grid for config.toml
    click     print the HSV color under the mouse
    SPACE     save a snapshot (useful with `bejeweled-bot analyze`)
    Q / ESC   quit
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from .autogrid import find_grid
from .capture import open_source
from .config import Config
from .display import draw_overlay
from .vision import HypercubeDetector, read_board

WINDOW_NAME = "Bejeweled Bot: calibration"
STEP = 2
SAMPLE_RADIUS = 10
KEY_MOVES = {
    ord("w"): (0, -STEP, 0, 0),
    ord("s"): (0, STEP, 0, 0),
    ord("a"): (-STEP, 0, 0, 0),
    ord("d"): (STEP, 0, 0, 0),
    ord("i"): (0, 0, 0, -STEP),
    ord("k"): (0, 0, 0, STEP),
    ord("j"): (0, 0, -STEP, 0),
    ord("l"): (0, 0, STEP, 0),
}


def calibrate(config: Config) -> None:
    source = open_source(config)
    image = source.read()
    if image is None:
        raise SystemExit(f"Couldn't read from {source.describe()}. Check the [capture] settings.")
    print(__doc__)
    print(f"Reading {source.describe()} at {image.shape[1]}x{image.shape[0]}.")

    grid = config.grid or _auto(image)
    clicked: list[tuple[int, int]] = []
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked.append((x, y))

    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    try:
        while True:
            image = source.read()
            if image is None:
                break
            board = read_board(image, grid, HypercubeDetector())
            cv2.imshow(WINDOW_NAME, draw_overlay(image, board, grid, status=f"grid = {list(grid)}"))
            while clicked:
                _print_sample(image, *clicked.pop())

            key = cv2.waitKey(100) & 0xFF
            if key in (ord("q"), 27):
                break
            if key in KEY_MOVES:
                grid = tuple(v + d for v, d in zip(grid, KEY_MOVES[key], strict=True))
            elif key == ord("g"):
                grid = _auto(image)
            elif key == ord("p"):
                print(f"\n[capture]\ngrid = {list(grid)}\n")
            elif key == ord(" "):
                name = f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
                cv2.imwrite(name, image)
                print(f"Saved {name}")
    finally:
        source.close()
        cv2.destroyAllWindows()


def _auto(image: np.ndarray) -> tuple[int, int, int, int]:
    print("Looking for the board...")
    grid, lock = find_grid(image)
    print(f"Found it at grid = {list(grid)} ({lock:.0%} of cells look like gems)")
    if lock < 0.8:
        print("That's a weak match. Make sure a game is on screen, then press G to try again.")
    return grid


def _print_sample(image: np.ndarray, x: int, y: int) -> None:
    region = image[
        max(0, y - SAMPLE_RADIUS) : y + SAMPLE_RADIUS, max(0, x - SAMPLE_RADIUS) : x + SAMPLE_RADIUS
    ]
    if region.size == 0:
        return
    h, s, v = (int(n) for n in cv2.cvtColor(region, cv2.COLOR_BGR2HSV).reshape(-1, 3).mean(axis=0))
    print(f"({x}, {y})  HSV = H {h}, S {s}, V {v}")
    print(
        f"  starting range for GEM_HSV_RANGES: ({max(0, h - 8)}, {min(180, h + 8)}, "
        f"{max(0, s - 40)}, {min(255, s + 40)}, {max(0, v - 40)}, {min(255, v + 40)})"
    )
