"""
Watch mode: read the board live and print the best move, without pressing anything.

This was the first working version of the project ("the advisor"), built to prove
the vision and move choice were right before the Raspberry Pi arrived. It's still
the quickest way to check the vision on a new setup.
"""

from __future__ import annotations

import logging
import time

import cv2

from . import screen
from .config import Config
from .display import board_text, draw_overlay, move_text
from .solver import find_best_move
from .vision import HypercubeDetector, board_state, read_board

log = logging.getLogger(__name__)

WINDOW_NAME = "Bejeweled Bot: what it sees"


def watch(config: Config, show_overlay: bool = True) -> None:
    rect = screen.find_window(config.window_title)
    if rect is None:
        raise SystemExit(f"Couldn't find a window titled '{config.window_title}'. Is the capture app open?")

    detector = HypercubeDetector()
    last_state, last_move = None, None
    print("Watching the board. Press Q in the overlay window (or Ctrl+C) to stop.\n")
    try:
        while True:
            image = screen.capture(rect)
            board = read_board(image, config.grid, detector)
            state = board_state(board)
            if last_state is not None and state != last_state:
                detector.reset()
            last_state = state

            move = find_best_move(board)
            if move != last_move:
                print(board_text(board))
                print(move_text(board, move) if move else "No move found (the board may be moving)")
                print()
                last_move = move

            if show_overlay:
                cv2.imshow(WINDOW_NAME, draw_overlay(image, board, config.grid, move, "Watching"))
                if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                    break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        cv2.destroyAllWindows()
