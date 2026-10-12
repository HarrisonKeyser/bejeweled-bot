import socket
import threading

import pytest

from bejeweled_bot.controller import Cursor, DryRunLink, PiLink
from bejeweled_bot.solver import Move


def make_cursor():
    link = DryRunLink()
    return Cursor(link, sleep=lambda _: None), link


def test_going_home_pushes_into_the_bottom_left_corner():
    cursor, link = make_cursor()
    cursor.row, cursor.col = 3, 5
    cursor.go_home()
    assert link.sent == ["DOWN"] * 7 + ["LEFT"] * 7
    assert (cursor.row, cursor.col) == (7, 0)


def test_moves_vertically_then_horizontally():
    cursor, link = make_cursor()
    cursor.move_to(2, 5)
    assert link.sent == ["UP"] * 5 + ["RIGHT"] * 5
    assert (cursor.row, cursor.col) == (2, 5)


def test_swap_drives_to_the_first_gem_and_swaps_toward_the_second():
    cursor, link = make_cursor()
    cursor.swap(Move(6, 1, 6, 0, 150, "match"))
    assert link.sent == ["UP", "RIGHT", "SWAP_LEFT"]
    assert (cursor.row, cursor.col) == (6, 1)  # the cursor stays where the swap started


@pytest.mark.parametrize(
    "move, command",
    [
        (Move(3, 3, 2, 3, 1, ""), "SWAP_UP"),
        (Move(3, 3, 4, 3, 1, ""), "SWAP_DOWN"),
        (Move(3, 3, 3, 2, 1, ""), "SWAP_LEFT"),
        (Move(3, 3, 3, 4, 1, ""), "SWAP_RIGHT"),
    ],
)
def test_swap_directions(move, command):
    cursor, link = make_cursor()
    cursor.swap(move)
    assert link.sent[-1] == command


def test_rejects_unknown_commands():
    with pytest.raises(ValueError):
        DryRunLink().send("JUMP")


def test_pi_link_sends_one_line_per_connection():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    received = []

    def accept_two():
        for _ in range(2):
            conn, _ = server.accept()
            with conn:
                received.append(conn.recv(64))

    thread = threading.Thread(target=accept_two)
    thread.start()
    link = PiLink("127.0.0.1", server.getsockname()[1])
    assert link.send("UP")
    assert link.send("SWAP_LEFT")
    thread.join(timeout=5)
    server.close()
    assert received == [b"UP\n", b"SWAP_LEFT\n"]


def test_pi_link_reports_failure_instead_of_crashing():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    server.close()  # nothing is listening on this port now
    assert PiLink("127.0.0.1", port, timeout=0.5).send("UP") is False
