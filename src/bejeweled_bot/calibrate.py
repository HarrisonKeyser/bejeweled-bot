"""
Calibration: line the grid up with the board and sample gem colors.

Opens a live view of the capture window with the 8x8 grid and each cell's
reading drawn on top.

    W A S D   move the grid by 2 px          I / K   shorter / taller
    J / L     narrower / wider               P       print the grid for your config file
    click     print the HSV color under the mouse
    SPACE     save a snapshot (useful with `bejeweled-bot analyze`)
    Q / ESC   quit
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from . import screen
from .config import Config
from .display import draw_overlay
from .vision import HypercubeDetector, read_board

WINDOW_NAME = "Bejeweled Bot: calibration"
STEP = 2
SAMPLE_RADIUS = 10


def calibrate(config: Config) -> None:
    rect = screen.find_window(config.window_title)
    if rect is None:
        raise SystemExit(f"Couldn't find a window titled '{config.window_title}'. Is the capture app open?")

    gx, gy, gw, gh = config.grid
    clicked: list[tuple[int, int]] = []
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    def on_mouse(event, x, y, *_):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicked.append((x, y))

    cv2.setMouseCallback(WINDOW_NAME, on_mouse)
    print(__doc__)

    while True:
        image = screen.capture(rect)
        grid = (gx, gy, gw, gh)
        board = read_board(image, grid, HypercubeDetector())
        view = draw_overlay(image, board, grid, status=f"grid = [{gx}, {gy}, {gw}, {gh}]")

        while clicked:
            _print_sample(image, *clicked.pop())

        cv2.imshow(WINDOW_NAME, view)
        key = cv2.waitKey(100) & 0xFF
        if key in (ord("q"), 27):
            break
        moves = {
            ord("w"): (0, -STEP, 0, 0),
            ord("s"): (0, STEP, 0, 0),
            ord("a"): (-STEP, 0, 0, 0),
            ord("d"): (STEP, 0, 0, 0),
            ord("i"): (0, 0, 0, -STEP),
            ord("k"): (0, 0, 0, STEP),
            ord("j"): (0, 0, -STEP, 0),
            ord("l"): (0, 0, STEP, 0),
        }
        if key in moves:
            dx, dy, dw, dh = moves[key]
            gx, gy, gw, gh = gx + dx, gy + dy, gw + dw, gh + dh
        elif key == ord("p"):
            print(f"\n[capture]\ngrid = [{gx}, {gy}, {gw}, {gh}]   # cells are {gw // 8} x {gh // 8} px\n")
        elif key == ord(" "):
            name = f"snapshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
            cv2.imwrite(name, image)
            print(f"Saved {name}")

    cv2.destroyAllWindows()


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
