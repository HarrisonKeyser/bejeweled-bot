"""
Choosing a move.

Every legal swap of two neighboring gems is tried on a copy of the board. The
simulation clears matches, explodes power gems, lets gems fall, and repeats
until nothing else matches, so chain reactions count. The swap with the highest
score wins.

Scores are heuristics for ranking moves, not the game's real points:

- Using a hypercube scores highest, more for a color with more gems on the board.
- Making a hypercube (five in a row) beats making a power gem (four in a row,
  or an L/T shape), which beats a plain match.
- Each cleared gem is worth 50, multiplied by how deep into the cascade it fell.
- Moves lower on the board get a small bonus, since they shake up more gems
  above them and tend to start longer cascades.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from .gems import GRID_COLS, GRID_ROWS, HYPERCUBE, UNKNOWN, base_color, is_power

# Cascade scoring
POINTS_PER_GEM = 50
POINTS_HYPERCUBE_LINE = 10_000  # added for each cell found in a line of 5+
POINTS_POWER_GEM_LINE = 2_500  # added for each cell found in a line of 4 or an L/T

# Bonuses on top of the cascade score
BONUS_CREATES_HYPERCUBE = 20_000
BONUS_CREATES_POWER_GEM = 5_000
BONUS_PER_ROW_DOWN = 100

# Using a hypercube
HYPERCUBE_BASE = 15_000
HYPERCUBE_PER_TARGET_GEM = 500

DEFAULT_MIN_CONFIDENCE = 0.10  # trust every cell the vision could identify


class Move(NamedTuple):
    """Swap the gem at (row1, col1) with its neighbor at (row2, col2)."""

    row1: int
    col1: int
    row2: int
    col2: int
    score: int
    reason: str

    @property
    def cells(self) -> tuple[int, int, int, int]:
        return self.row1, self.col1, self.row2, self.col2

    @property
    def direction(self) -> str:
        if self.row2 < self.row1:
            return "UP"
        if self.row2 > self.row1:
            return "DOWN"
        return "LEFT" if self.col2 < self.col1 else "RIGHT"


# A board here is any 8x8 grid of (gem, confidence) pairs, such as vision.Board.
Board = Sequence[Sequence[tuple[str, float]]]
Grid = list[list[str]]


def gem_at(board: Board, row: int, col: int) -> str:
    return board[row][col][0]


def confidence_at(board: Board, row: int, col: int) -> float:
    return board[row][col][1]


def match_lengths(grid: Grid, row: int, col: int) -> tuple[int, int]:
    """Length of the horizontal and vertical runs of same-colored gems through (row, col)."""
    color = base_color(grid[row][col])
    if not color or color in (UNKNOWN, HYPERCUBE):
        return 0, 0

    horizontal = 1
    c = col - 1
    while c >= 0 and base_color(grid[row][c]) == color:
        horizontal += 1
        c -= 1
    c = col + 1
    while c < GRID_COLS and base_color(grid[row][c]) == color:
        horizontal += 1
        c += 1

    vertical = 1
    r = row - 1
    while r >= 0 and base_color(grid[r][col]) == color:
        vertical += 1
        r -= 1
    r = row + 1
    while r < GRID_ROWS and base_color(grid[r][col]) == color:
        vertical += 1
        r += 1

    return horizontal, vertical


def simulate_cascade(grid: Grid) -> tuple[int, str]:
    """
    Clear matches and apply gravity until the board is still.

    Returns (score, special) where special is "hypercube", "power gem" or "" for
    the first special gem the cascade would create. New gems falling in from the
    top are unknown, so they never match.
    """
    total, special_created, depth = 0, "", 0
    while True:
        depth += 1
        to_clear: set[tuple[int, int]] = set()
        created_this_step = None

        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                horizontal, vertical = match_lengths(grid, r, c)
                if horizontal >= 5 or vertical >= 5:
                    created_this_step = "hypercube"
                    total += POINTS_HYPERCUBE_LINE
                elif (horizontal >= 3 and vertical >= 3) or horizontal == 4 or vertical == 4:
                    if not created_this_step:
                        created_this_step = "power gem"
                        total += POINTS_POWER_GEM_LINE

                if horizontal >= 3:
                    for nc in range(c - (horizontal - 1), c + horizontal):
                        if 0 <= nc < GRID_COLS and match_lengths(grid, r, nc)[0] >= 3:
                            to_clear.add((r, nc))
                if vertical >= 3:
                    for nr in range(r - (vertical - 1), r + vertical):
                        if 0 <= nr < GRID_ROWS and match_lengths(grid, nr, c)[1] >= 3:
                            to_clear.add((nr, c))

        if not to_clear:
            break

        # Power gems explode, clearing their 3x3 neighborhood.
        explosions = set()
        for r, c in to_clear:
            if is_power(grid[r][c]):
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        if 0 <= r + dr < GRID_ROWS and 0 <= c + dc < GRID_COLS:
                            explosions.add((r + dr, c + dc))
        to_clear |= explosions

        total += len(to_clear) * POINTS_PER_GEM * depth
        if created_this_step and not special_created:
            special_created = created_this_step

        grid = _apply_gravity(grid, to_clear)

    return total, special_created


def _apply_gravity(grid: Grid, cleared: set[tuple[int, int]]) -> Grid:
    new_grid: Grid = [[UNKNOWN] * GRID_COLS for _ in range(GRID_ROWS)]
    for c in range(GRID_COLS):
        write_row = GRID_ROWS - 1
        for r in range(GRID_ROWS - 1, -1, -1):
            if (r, c) not in cleared:
                new_grid[write_row][c] = grid[r][c]
                write_row -= 1
    return new_grid


def score_swap(board: Board, row1: int, col1: int, row2: int, col2: int) -> tuple[int, str]:
    """Score swapping two neighboring cells. Returns (score, reason); score 0 means no match."""
    gem1, gem2 = gem_at(board, row1, col1), gem_at(board, row2, col2)

    if gem1 == HYPERCUBE or gem2 == HYPERCUBE:
        target = base_color(gem2 if gem1 == HYPERCUBE else gem1)
        if target == UNKNOWN:
            return 0, "hypercube next to an unknown cell"
        count = sum(1 for row in board for cell in row if cell[0] == target)
        return (
            HYPERCUBE_BASE + count * HYPERCUBE_PER_TARGET_GEM,
            f"hypercube clears every {target} gem ({count} on the board)",
        )

    grid = [[gem_at(board, r, c) for c in range(GRID_COLS)] for r in range(GRID_ROWS)]
    grid[row1][col1], grid[row2][col2] = grid[row2][col2], grid[row1][col1]
    cascade_score, special = simulate_cascade(grid)
    if cascade_score == 0:
        return 0, "no match"

    score = cascade_score + max(row1, row2) * BONUS_PER_ROW_DOWN
    if special == "hypercube":
        return score + BONUS_CREATES_HYPERCUBE, "makes a hypercube"
    if special == "power gem":
        return score + BONUS_CREATES_POWER_GEM, "makes a power gem"
    return score, "match"


def legal_moves(board: Board, min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> list[Move]:
    """Every scoring swap, in board order (left to right, top to bottom)."""
    moves = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if confidence_at(board, r, c) < min_confidence:
                continue
            for nr, nc in ((r, c + 1), (r + 1, c)):
                if nr < GRID_ROWS and nc < GRID_COLS and confidence_at(board, nr, nc) >= min_confidence:
                    score, reason = score_swap(board, r, c, nr, nc)
                    if score > 0:
                        moves.append(Move(r, c, nr, nc, score, reason))
    return moves


def find_best_move(board: Board, min_confidence: float = DEFAULT_MIN_CONFIDENCE) -> Move | None:
    """The highest-scoring swap, or None. Ties go to the first move found."""
    best = None
    for move in legal_moves(board, min_confidence):
        if best is None or move.score > best.score:
            best = move
    return best


def uses_hypercube(board: Board, move: Move) -> bool:
    return (
        gem_at(board, move.row1, move.col1) == HYPERCUBE or gem_at(board, move.row2, move.col2) == HYPERCUBE
    )
