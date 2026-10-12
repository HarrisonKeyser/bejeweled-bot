"""The play loop, with the screen and the Pi replaced by fakes."""

from helpers import DEAD_BOARD, board_from

from bejeweled_bot.bot import Bot
from bejeweled_bot.config import Config
from bejeweled_bot.controller import DryRunLink

# One available move: swap (0,2) down to complete the orange row.
ONE_MOVE = """
O O P Y R G B Y
B Y O G B Y R G
R G B Y R G B Y
B Y R G B Y R G
R G B Y R G B Y
B Y R G B Y R G
R G B Y R G B Y
B Y R G B Y R G
"""


def make_bot(screens):
    """A bot whose eyes show `screens` in order (repeating the last one)."""
    link = DryRunLink()
    bot = Bot(
        Config(), link, find_window=lambda _: (0, 0, 10, 10), capture=lambda _: None, sleep=lambda _: None
    )
    queue = list(screens)
    bot._look = lambda: queue.pop(0) if len(queue) > 1 else queue[0]
    return bot, link


def test_makes_the_move_and_waits_for_the_board_to_settle():
    before = board_from(ONE_MOVE)
    falling = board_from(DEAD_BOARD)
    falling[0][0] = ("unknown", 0.0)
    after = board_from(DEAD_BOARD)
    bot, link = make_bot([before, before, falling, after, after, after])
    bot.step()
    assert link.sent == ["UP"] * 7 + ["RIGHT"] * 2 + ["SWAP_DOWN"]


def test_resets_the_cursor_after_three_identical_attempts():
    stuck = board_from(ONE_MOVE)  # the swap never shows up on screen
    bot, link = make_bot([stuck])
    for _ in range(3):
        bot.step()
    swaps = [c for c in link.sent if c.startswith("SWAP")]
    assert len(swaps) == 2
    assert link.sent[-14:] == ["DOWN"] * 7 + ["LEFT"] * 7


def test_double_checks_a_hypercube_before_using_it():
    with_cube = board_from(DEAD_BOARD)
    with_cube[3][3] = ("hypercube", 0.85)
    still = board_from(ONE_MOVE)  # on a still board it was just a white gem, and there's a normal move
    bot, link = make_bot([with_cube, still])
    bot.step()
    assert "SWAP_DOWN" in link.sent  # it made the normal move, not the hypercube swap
    assert link.sent.index("SWAP_DOWN") == 9


def test_cursor_reset_happens_in_the_loop_when_started():
    bot, link = make_bot([board_from(DEAD_BOARD)])
    bot.toggle()
    assert bot.running.is_set()
    assert link.sent == []  # nothing is pressed from the hotkey thread
    bot.step()
    assert link.sent == ["DOWN"] * 7 + ["LEFT"] * 7


def test_does_nothing_without_a_move():
    bot, link = make_bot([board_from(DEAD_BOARD)])
    bot.step()
    assert link.sent == []
