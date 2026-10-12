"""Command line: `bejeweled-bot play`, `watch`, `calibrate`, `devices`, `analyze`, `test-connection`."""

from __future__ import annotations

import argparse
import logging
import threading
import time
from pathlib import Path

from .config import Config, load_config

DEFAULT_CONFIG = Path("config.toml")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="bejeweled-bot",
        description="Plays Bejeweled 2 on an Xbox 360 through a capture card and a Raspberry Pi.",
    )
    parser.add_argument("-c", "--config", type=Path, help="settings file (default: config.toml if it exists)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show debug messages")
    commands = parser.add_subparsers(dest="command", required=True)

    play = commands.add_parser("play", help="play the game (F1 start/pause, F3 reconnect, Esc quit)")
    play.add_argument("--dry-run", action="store_true", help="log button presses instead of sending them")
    play.add_argument("--show", action="store_true", help="show what the bot sees in a window")
    watch = commands.add_parser("watch", help="show the best move without pressing anything")
    watch.add_argument("--no-overlay", action="store_true", help="text only, no overlay window")
    commands.add_parser("calibrate", help="find the board, check the readings, sample gem colors")
    commands.add_parser("devices", help="list video devices (capture cards and webcams)")
    analyze = commands.add_parser("analyze", help="read a saved screenshot and print the best move")
    analyze.add_argument("image", type=Path)
    analyze.add_argument("--save-overlay", type=Path, metavar="PNG", help="also save an annotated copy")
    test = commands.add_parser("test-connection", help="send a square of D-pad presses to the Pi")
    test.add_argument("--swap", action="store_true", help="finish with a swap to the right")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    config = _config(args.config)

    if args.command == "play":
        _play(config, args.dry_run, args.show)
    elif args.command == "watch":
        from .watch import watch as run_watch

        run_watch(config, show_overlay=not args.no_overlay)
    elif args.command == "calibrate":
        from .calibrate import calibrate as run_calibrate

        run_calibrate(config)
    elif args.command == "devices":
        _devices()
    elif args.command == "analyze":
        _analyze(config, args.image, args.save_overlay)
    elif args.command == "test-connection":
        _test_connection(config, args.swap)


def _config(path: Path | None) -> Config:
    if path is None and DEFAULT_CONFIG.exists():
        path = DEFAULT_CONFIG
    return load_config(path)


def _play(config: Config, dry_run: bool, show: bool) -> None:
    import keyboard

    from .bot import Bot
    from .capture import open_source
    from .controller import DryRunLink, PiLink

    link = DryRunLink() if dry_run else PiLink(config.pi_host, config.pi_port)
    source = open_source(config)
    bot = Bot(config, link, source, on_frame=_preview if show else None)
    keyboard.add_hotkey("f1", bot.toggle)
    keyboard.add_hotkey("f3", bot.refresh_capture)
    keyboard.add_hotkey("esc", bot.stop)

    print("Bejeweled Bot")
    print("  F1   start / pause (the cursor resets to the corner on start)")
    print("  F3   reconnect to the capture and find the board again")
    print("  Esc  quit")
    print(
        f"Reading {source.describe()}; sending moves to {'nowhere (dry run)' if dry_run else config.pi_host}."
    )
    loop = threading.Thread(target=bot.run, daemon=True)
    loop.start()
    try:
        while not bot.stopped.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        bot.stop()
    loop.join(timeout=3)
    source.close()
    print("Bye!")


def _preview(image, board, grid) -> None:
    """Show the bot's latest look (runs on the bot's thread, which owns the window)."""
    import cv2

    from .display import draw_overlay

    cv2.imshow("Bejeweled Bot: playing", draw_overlay(image, board, grid))
    cv2.waitKey(1)


def _devices() -> None:
    from .capture import list_devices

    print("Checking video devices...")
    found = list_devices()
    if not found:
        print("None found. Is the capture card plugged in, and is its app (or OBS) closed?")
    for index, width, height in found:
        print(f"  device = {index}   ({width}x{height})")
    if found:
        print("Webcams show up here too. Run `bejeweled-bot calibrate` to check you picked the right one.")


def _analyze(config: Config, image_path: Path, overlay_path: Path | None) -> None:
    import cv2

    from .display import board_text, draw_overlay, move_text
    from .solver import find_best_move, legal_moves
    from .vision import HypercubeDetector, read_board

    image = cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f"Couldn't open {image_path}")
    grid = config.grid
    if grid is None:
        from .autogrid import find_grid

        grid, lock = find_grid(image)
        print(f"Found the board at grid = {list(grid)} ({lock:.0%} of cells look like gems)\n")
    # A single frame can't show flicker, but most hypercubes still read correctly from one.
    board = read_board(image, grid, HypercubeDetector())
    print(board_text(board))
    print()
    best = find_best_move(board)
    print(move_text(board, best) if best else "No move found.")
    if best:
        count = len(legal_moves(board))
        print(f"({count} scoring move{'s' if count != 1 else ''} on the board)")
    if overlay_path:
        cv2.imwrite(str(overlay_path), draw_overlay(image, board, grid, best))
        print(f"Saved {overlay_path}")


def _test_connection(config: Config, swap: bool) -> None:
    from .controller import PiLink

    link = PiLink(config.pi_host, config.pi_port)
    commands = ["RIGHT", "DOWN", "LEFT", "UP"] + (["SWAP_RIGHT"] if swap else [])
    print(f"Sending {', '.join(commands)} to {config.pi_host}:{config.pi_port}")
    ok = True
    for command in commands:
        ok = link.send(command) and ok
        time.sleep(0.5)
    print("Done. Did the cursor move in a square?" if ok else "Some commands didn't get through.")


if __name__ == "__main__":
    main()
