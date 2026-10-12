"""The Pi-side listener, with a plain file standing in for /dev/hidg0."""

import importlib.util
import socket
import threading
from pathlib import Path

import pytest

LISTENER = Path(__file__).parent.parent / "pi" / "listener.py"


@pytest.fixture
def listener(monkeypatch):
    spec = importlib.util.spec_from_file_location("listener", LISTENER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    return module


def reports(path):
    data = path.read_bytes()
    return [data[i : i + 8] for i in range(0, len(data), 8)]


def test_tap_presses_and_releases(listener, tmp_path):
    device = tmp_path / "hidg0"
    device.write_bytes(b"")
    keyboard = listener.Keyboard(str(device))
    listener.run_command(keyboard, "LEFT")
    assert reports(device) == [bytes([0, 0, 0x50, 0, 0, 0, 0, 0]), bytes(8)]


def test_swap_holds_a_then_taps_the_direction(listener, tmp_path):
    device = tmp_path / "hidg0"
    device.write_bytes(b"")
    keyboard = listener.Keyboard(str(device))
    listener.run_command(keyboard, "SWAP_UP")
    assert reports(device) == [
        bytes([0, 0, 0x2C, 0, 0, 0, 0, 0]),
        bytes([0, 0, 0x2C, 0x52, 0, 0, 0, 0]),
        bytes(8),
    ]


def test_unknown_commands_press_nothing(listener, tmp_path):
    device = tmp_path / "hidg0"
    device.write_bytes(b"")
    listener.run_command(listener.Keyboard(str(device)), "JUMP")
    assert device.read_bytes() == b""


def test_accepts_old_and_new_message_formats_over_the_network(listener, tmp_path):
    device = tmp_path / "hidg0"
    device.write_bytes(b"")
    keyboard = listener.Keyboard(str(device))

    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    threading.Thread(target=listener.serve, args=(port, keyboard), daemon=True).start()

    def send(payload):
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1) as conn:
                    conn.sendall(payload)
                return
            except ConnectionRefusedError:
                threading.Event().wait(0.05)
        raise AssertionError("listener never started")

    send(b"UP")  # the original laptop script: no newline
    send(b"DOWN\nRIGHT\n")  # newline-separated
    for _ in range(100):
        if len(reports(device)) >= 6:
            break
        threading.Event().wait(0.02)
    keys = [r[2] for r in reports(device) if r != bytes(8)]
    assert keys == [0x52, 0x51, 0x4F]
