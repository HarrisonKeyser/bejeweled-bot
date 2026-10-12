"""
Pressing buttons.

The laptop sends short text commands ("UP", "SWAP_LEFT", ...) over Wi-Fi to a
Raspberry Pi Zero 2W. The Pi poses as a USB keyboard plugged into a Cronus Zen,
which turns arrow keys into the D-pad and Space into the A button on the Xbox.
See pi/ for the Pi side.

The in-game cursor is too subtle to track reliably on screen, so the bot keeps
track of it itself (dead reckoning). The cursor doesn't wrap around, so seven
presses down and seven left always land in the bottom-left corner. That gives a
known starting point whenever the bot loses track.
"""

from __future__ import annotations

import logging
import socket
import time

from .gems import GRID_COLS, GRID_ROWS
from .solver import Move

log = logging.getLogger(__name__)

COMMANDS = {"UP", "DOWN", "LEFT", "RIGHT", "SWAP_UP", "SWAP_DOWN", "SWAP_LEFT", "SWAP_RIGHT"}


class PiLink:
    """Sends one command per TCP connection to the listener running on the Pi."""

    def __init__(self, host: str, port: int = 65432, timeout: float = 2.0):
        self.host, self.port, self.timeout = host, port, timeout

    def send(self, command: str) -> bool:
        if command not in COMMANDS:
            raise ValueError(f"Unknown command: {command}")
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as conn:
                conn.sendall(f"{command}\n".encode())
            return True
        except OSError as error:
            log.error("Couldn't send %s to the Pi at %s:%s: %s", command, self.host, self.port, error)
            return False


class DryRunLink:
    """Logs commands instead of sending them, for trying the bot without the hardware."""

    def __init__(self):
        self.sent: list[str] = []

    def send(self, command: str) -> bool:
        if command not in COMMANDS:
            raise ValueError(f"Unknown command: {command}")
        self.sent.append(command)
        log.info("[dry run] %s", command)
        return True


class Cursor:
    """Moves the in-game cursor and remembers where it is."""

    HOME = (GRID_ROWS - 1, 0)  # bottom-left corner

    def __init__(self, link, input_delay: float = 0.01, pre_swap_delay: float = 0.01, sleep=time.sleep):
        self.link = link
        self.input_delay = input_delay
        self.pre_swap_delay = pre_swap_delay
        self._sleep = sleep
        self.row, self.col = self.HOME

    def go_home(self) -> None:
        """Push the cursor into the bottom-left corner so its position is known again."""
        log.info("Resetting the cursor to the bottom-left corner")
        for _ in range(GRID_ROWS - 1):
            self._press("DOWN")
        for _ in range(GRID_COLS - 1):
            self._press("LEFT")
        self.row, self.col = self.HOME

    def move_to(self, row: int, col: int) -> None:
        while self.row > row:
            self._press("UP")
            self.row -= 1
        while self.row < row:
            self._press("DOWN")
            self.row += 1
        while self.col > col:
            self._press("LEFT")
            self.col -= 1
        while self.col < col:
            self._press("RIGHT")
            self.col += 1

    def swap(self, move: Move) -> None:
        """Drive to the first gem and swap it toward the second. The cursor stays on the first cell."""
        log.info("Swapping (%d,%d) %s", move.row1, move.col1, move.direction)
        self.move_to(move.row1, move.col1)
        self._sleep(self.pre_swap_delay)
        self.link.send(f"SWAP_{move.direction}")

    def _press(self, command: str) -> None:
        self.link.send(command)
        self._sleep(self.input_delay)
