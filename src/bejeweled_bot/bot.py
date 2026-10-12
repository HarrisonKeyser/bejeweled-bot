"""
The play loop: look, choose, move, wait, repeat.

The capture card adds about three seconds of delay, so the bot can't time its
moves. It works in a closed loop instead:

1. Read the board and pick the best move.
2. If the move uses a hypercube, look again first (see `_recheck_hypercube`).
3. Drive the cursor there and swap.
4. Wait until the board on screen changes (the swap registered), then until it
   reads the same twice in a row with no empty cells (the cascade finished).

Safety nets for running unattended:
- If it picks the exact same move three times in a row, the swap isn't landing,
  which almost always means the cursor isn't where the bot thinks. It resets the
  cursor in the corner and carries on.
- Every move ends with the flicker history cleared, so falling gems aren't
  mistaken for hypercubes.
"""

from __future__ import annotations

import logging
import threading
import time

from . import screen
from .config import Config
from .controller import Cursor
from .gems import UNKNOWN
from .solver import Move, find_best_move, uses_hypercube
from .vision import Board, HypercubeDetector, board_state, read_board

log = logging.getLogger(__name__)

POLL_INTERVAL = 0.5  # wait between looks when there's no move
FRAME_INTERVAL = 0.1  # wait between looks while watching an animation
SWAP_START_READS = 25  # looks to wait for a swap to show up on screen
SETTLE_READS = 2  # identical reads in a row that count as "settled"
SETTLE_TIMEOUT = 30.0  # give up waiting for a cascade after this long
HYPERCUBE_RECHECK_PAUSE = 0.6
HYPERCUBE_RECHECK_READS = 5
SAME_MOVE_LIMIT = 3  # identical moves in a row before resetting the cursor
WINDOW_RETRY_DELAY = 3.0


class Bot:
    def __init__(
        self,
        config: Config,
        link,
        *,
        find_window=screen.find_window,
        capture=screen.capture,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.config = config
        self.cursor = Cursor(link, config.input_delay, config.pre_swap_delay, sleep=sleep)
        self.detector = HypercubeDetector()
        self._find_window = find_window
        self._capture = capture
        self._sleep = sleep
        self._clock = clock

        self.running = threading.Event()
        self.stopped = threading.Event()
        self._needs_cursor_reset = False
        self._window = None

        self._last_state = None
        self._last_move: tuple | None = None
        self._same_move_count = 0

    # Controls (called from the hotkey thread) -------------------------------

    def toggle(self) -> None:
        if self.running.is_set():
            self.running.clear()
            log.info("Paused")
        else:
            self._needs_cursor_reset = True  # the loop thread does it, so inputs never interleave
            self.running.set()
            log.info("Started")

    def refind_window(self) -> None:
        self._window = None
        log.info("Looking for the capture window again")

    def stop(self) -> None:
        self.running.clear()
        self.stopped.set()

    # Main loop ----------------------------------------------------------------

    def run(self) -> None:
        log.info("Ready. Press F1 to start.")
        while not self.stopped.is_set():
            if not self.running.is_set():
                self._last_state = None
                self._sleep(0.2)
                continue
            try:
                self.step()
            except Exception:  # keep going overnight no matter what
                log.exception("Unexpected error; retrying in a second")
                self._sleep(1)

    def step(self) -> None:
        if self._needs_cursor_reset:
            self._needs_cursor_reset = False
            self._reset_cursor()
            return

        if self._window is None:
            self._window = self._find_window(self.config.window_title)
            if self._window is None:
                log.warning("Capture window '%s' not found; retrying", self.config.window_title)
                self._sleep(WINDOW_RETRY_DELAY)
                return

        board = self._look()
        state = board_state(board)
        if self._last_state is not None and state != self._last_state:
            self.detector.reset()
        self._last_state = state

        move = find_best_move(board)
        if move and uses_hypercube(board, move):
            board, move = self._recheck_hypercube()
            if move is None:
                return

        if move is None:
            log.debug("No move found (%d/64 cells unknown)", state.count(UNKNOWN))
            self._sleep(POLL_INTERVAL)
            return

        if self._is_stuck(move):
            log.warning(
                "Tried %s %d times in a row; the cursor is probably off. Resetting it.",
                move.cells,
                SAME_MOVE_LIMIT,
            )
            self._reset_cursor()
            return

        log.info("Move: %s (score %d)", move.reason, move.score)
        self.cursor.swap(move)
        self._wait_for_board_to_settle(state)
        self.detector.reset()
        self._last_state = None

    # Helpers --------------------------------------------------------------------

    def _look(self) -> Board:
        return read_board(self._capture(self._window), self.config.grid, self.detector)

    def _recheck_hypercube(self) -> tuple[Board, Move | None]:
        """
        White gems that just fell look like they flicker, which can fake a hypercube.
        Before acting on one, pause, forget the flicker history, and read the now-still
        board several times. A real hypercube keeps flickering; a white gem doesn't.
        """
        log.info("Hypercube spotted; double-checking it on a still board")
        self._sleep(HYPERCUBE_RECHECK_PAUSE)
        self.detector.reset()
        board = None
        for _ in range(HYPERCUBE_RECHECK_READS):
            board = self._look()
        move = find_best_move(board)
        if move is None or not uses_hypercube(board, move):
            log.info("False alarm: it was a white gem")
        return board, move

    def _is_stuck(self, move: Move) -> bool:
        if move.cells == self._last_move:
            self._same_move_count += 1
        else:
            self._last_move = move.cells
            self._same_move_count = 1
        return self._same_move_count >= SAME_MOVE_LIMIT

    def _wait_for_board_to_settle(self, before: tuple[str, ...]) -> None:
        # 1. Wait for the swap to show up (the capture card is ~3 seconds behind).
        for _ in range(SWAP_START_READS):
            self._sleep(FRAME_INTERVAL)
            if board_state(self._look()) != before:
                break
        else:
            log.warning("The board didn't change; the swap may have missed")
            return

        # 2. Wait until it reads the same twice in a row with no gaps.
        deadline = self._clock() + SETTLE_TIMEOUT
        matches, previous = 0, None
        while matches < SETTLE_READS:
            self._sleep(FRAME_INTERVAL)
            state = board_state(self._look())
            if state == previous and UNKNOWN not in state:
                matches += 1
            else:
                matches, previous = 0, state
            if self._clock() >= deadline:
                log.warning("The board hasn't settled after %.0f seconds; moving on", SETTLE_TIMEOUT)
                return

    def _reset_cursor(self) -> None:
        self.cursor.go_home()
        self._last_state = None
        self._last_move = None
        self._same_move_count = 0
        self._sleep(1.0)
