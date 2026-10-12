"""Build boards from text so tests read like pictures of the board."""

from bejeweled_bot.gems import HYPERCUBE, UNKNOWN, power

LETTERS = {"R": "red", "O": "orange", "Y": "yellow", "G": "green", "B": "blue", "P": "purple", "W": "white"}


def board_from(text: str, confidence: float = 0.9):
    """
    One row per line, cells separated by spaces:
    R G B ... plain gems, R* power gem, HC hypercube, ? unknown.
    """
    rows = [line.split() for line in text.strip().splitlines()]
    assert len(rows) == 8 and all(len(r) == 8 for r in rows), "boards are 8x8"
    return [[(_gem(token), confidence) for token in row] for row in rows]


def _gem(token: str) -> str:
    if token == "HC":
        return HYPERCUBE
    if token == "?":
        return UNKNOWN
    if token.endswith("*"):
        return power(LETTERS[token[0]])
    return LETTERS[token]


# A board with no matches and no possible moves, used as a quiet background.
DEAD_BOARD = """
R G B Y R G B Y
B Y R G B Y R G
R G B Y R G B Y
B Y R G B Y R G
R G B Y R G B Y
B Y R G B Y R G
R G B Y R G B Y
B Y R G B Y R G
"""
