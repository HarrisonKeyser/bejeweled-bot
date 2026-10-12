"""Showing what the bot sees: a text board for the terminal and an overlay image."""

from __future__ import annotations

import cv2
import numpy as np

from .gems import GRID_COLS, GRID_ROWS, label, overlay_color
from .solver import Move

COLUMN_LETTERS = "ABCDEFGH"
LOW_CONFIDENCE = 0.30


def cell_name(row: int, col: int) -> str:
    """Chess-style name: columns A-H left to right, rows 1-8 top to bottom."""
    return f"{COLUMN_LETTERS[col]}{row + 1}"


def board_text(board) -> str:
    """The board as text. Lowercase labels mark low-confidence cells."""
    lines = ["     " + "   ".join(COLUMN_LETTERS[:GRID_COLS])]
    for r in range(GRID_ROWS):
        cells = []
        for c in range(GRID_COLS):
            gem, confidence = board[r][c]
            text = label(gem)
            cells.append((text.lower() if confidence < LOW_CONFIDENCE else text).ljust(2))
        lines.append(f" {r + 1}  " + "  ".join(cells))
    return "\n".join(lines)


def move_text(board, move: Move) -> str:
    gem1, conf1 = board[move.row1][move.col1]
    gem2, conf2 = board[move.row2][move.col2]
    return (
        f"Swap {cell_name(move.row1, move.col1)} ({gem1}, {conf1:.0%}) {move.direction} "
        f"with {cell_name(move.row2, move.col2)} ({gem2}, {conf2:.0%}): "
        f"{move.reason} [score {move.score:,}]"
    )


def draw_overlay(
    image: np.ndarray, board, grid_rect, move: Move | None = None, status: str = ""
) -> np.ndarray:
    """Outline every cell in the color it was read as, with its confidence, and arrow the move."""
    out = image.copy()
    gx, gy, gw, gh = grid_rect
    cw, ch = gw // GRID_COLS, gh // GRID_ROWS
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            gem, confidence = board[r][c]
            color = overlay_color(gem)
            x, y = gx + c * cw + 2, gy + r * ch + 2
            thickness = 1 if confidence < LOW_CONFIDENCE else 3
            cv2.rectangle(out, (x, y), (x + cw - 4, y + ch - 4), color, thickness)
            cv2.putText(out, label(gem), (x + 5, y + ch // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            cv2.putText(
                out,
                f"{confidence:.0%}",
                (x + 5, y + ch - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35,
                (200, 200, 200),
                1,
            )
    if move:
        start = (gx + move.col1 * cw + cw // 2, gy + move.row1 * ch + ch // 2)
        end = (gx + move.col2 * cw + cw // 2, gy + move.row2 * ch + ch // 2)
        cv2.arrowedLine(out, start, end, (0, 255, 255), 4, tipLength=0.4)
    if status:
        cv2.putText(out, status, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    return out
