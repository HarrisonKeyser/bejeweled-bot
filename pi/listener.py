#!/usr/bin/env python3
"""
Runs on the Raspberry Pi. Receives commands from the laptop over the network and
types them as keyboard presses through the USB gadget (/dev/hidg0).

The Pi is plugged into a Cronus Zen, which maps the keys to the Xbox controller:
arrow keys -> D-pad, Space -> A.

Commands (one per line, or one per connection):
    UP DOWN LEFT RIGHT                         tap a D-pad direction
    SWAP_UP SWAP_DOWN SWAP_LEFT SWAP_RIGHT     hold A, tap the direction, release

Uses only the Python standard library.
"""

import argparse
import logging
import socket
import time

HID_DEVICE = "/dev/hidg0"

# USB HID keyboard usage codes
KEY_RIGHT, KEY_LEFT, KEY_DOWN, KEY_UP, KEY_SPACE = 0x4F, 0x50, 0x51, 0x52, 0x2C
DIRECTIONS = {"UP": KEY_UP, "DOWN": KEY_DOWN, "LEFT": KEY_LEFT, "RIGHT": KEY_RIGHT}

# How long each key is held and the pause after releasing it. Holding for 0.3 s made
# the game read some presses as two moves; 0.2 s was reliable.
KEY_HOLD = 0.2
KEY_GAP = 0.2

log = logging.getLogger("listener")


class Keyboard:
    """Writes 8-byte boot-keyboard reports: [modifiers, reserved, key1 ... key6]."""

    def __init__(self, device=HID_DEVICE):
        self.device = open(device, "rb+", buffering=0)  # stays open while the service runs

    def hold(self, *keys):
        report = bytes([0, 0, *keys, *([0] * (6 - len(keys)))])
        self.device.write(report)

    def release_all(self):
        self.device.write(bytes(8))

    def tap(self, key):
        self.hold(key)
        time.sleep(KEY_HOLD)
        self.release_all()
        time.sleep(KEY_GAP)

    def swap(self, direction_key):
        self.hold(KEY_SPACE)  # A down
        time.sleep(KEY_HOLD)
        self.hold(KEY_SPACE, direction_key)  # direction while A is held
        time.sleep(KEY_HOLD)
        self.release_all()
        time.sleep(KEY_GAP)


def run_command(keyboard, command):
    if command in DIRECTIONS:
        keyboard.tap(DIRECTIONS[command])
    elif command.startswith("SWAP_") and command[5:] in DIRECTIONS:
        keyboard.swap(DIRECTIONS[command[5:]])
    else:
        log.warning("Ignoring unknown command %r", command)
        return
    log.debug("Did %s", command)


def serve(port, keyboard):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen()
    log.info("Listening on port %d", port)

    while True:
        conn, address = server.accept()
        with conn:
            buffer = b""
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                buffer += data
                *lines, buffer = buffer.split(b"\n")
                for line in lines:
                    if line.strip():
                        run_command(keyboard, line.decode(errors="replace").strip().upper())
            # Older laptop scripts send one command per connection without a newline.
            if buffer.strip():
                run_command(keyboard, buffer.decode(errors="replace").strip().upper())


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--port", type=int, default=65432)
    parser.add_argument("--device", default=HID_DEVICE)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(message)s"
    )

    keyboard = Keyboard(args.device)
    try:
        serve(args.port, keyboard)
    finally:
        keyboard.release_all()


if __name__ == "__main__":
    main()
