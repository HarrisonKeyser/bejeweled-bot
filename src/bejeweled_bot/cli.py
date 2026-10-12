"""Command line: `bejeweled-bot play`, `watch`, `calibrate`, `analyze`, `test-connection`."""

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

    play = commands.add_parser("play", help="play the game (F1 start/pause, F3 find window again, Esc quit)")
    play.add_argument("--dry-run", action="store_true", help="log button presses instead of sending them")
    watch = commands.add_parser("watch", help="show the best move without pressing anything")
    watch.add_argument("--no-overlay", action="store_true", help="text only, no overlay window")
    commands.add_parser("calibrate", help="line up the grid and sample gem colors")
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
        _play(config, args.dry_run)
    elif args.command == "watch":
        from .watch import watch as run_watch

        run_watch(config, show_overlay=not args.no_overlay)
    elif args.command == "calibrate":
        from .calibrate import calibrate as run_calibrate

        run_calibrate(config)
    elif args.command == "analyze":
        _analyze(config, args.image, args.save_overlay)
    elif args.command == "test-connection":
        _test_connection(config, args.swap)


def _config(path: Path | None) -> Config:
    if path is None and DEFAULT_CONFIG.exists():
        path = DEFAULT_CONFIG
    return load_config(path)


def _play(config: Config, dry_run: bool) -> None:
    import keyboard

    from .bot import Bot
    from .controller import DryRunLink, PiLink

    link = DryRunLink() if dry_run else PiLink(config.pi_host, config.pi_port)
    bot = Bot(config, link)
    keyboard.add_hotkey("f1", bot.toggle)
    keyboard.add_hotkey("f3", bot.refind_window)
    keyboard.add_hotkey("esc", bot.stop)

    print("Bejeweled Bot")
    print("  F1   start / pause (the cursor resets to the corner on start)")
    print("  F3   find the capture window again (if it moved)")
    print("  Esc  quit")
    loop = threading.Thread(target=bot.run, daemon=True)
    loop.start()
    try:
        while not bot.stopped.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        bot.stop()
    print("Bye!")


def _analyze(config: Config, image_path: Path, overlay_path: Path | None) -> None:
    import cv2

    from .display import board_text, draw_overlay, move_text
    from .solver import find_best_move, legal_moves
    from .vision import HypercubeDetector, read_board

    image = cv2.imread(str(image_path))
    if image is None:
        raise SystemExit(f"Couldn't open {image_path}")
    # A single frame can't show flicker, so hypercubes may read as white here.
    board = read_board(image, config.grid, HypercubeDetector())
    print(board_text(board))
    print()
    best = find_best_move(board)
    print(move_text(board, best) if best else "No move found.")
    if best:
        count = len(legal_moves(board))
        print(f"({count} scoring move{'s' if count != 1 else ''} on the board)")
    if overlay_path:
        cv2.imwrite(str(overlay_path), draw_overlay(image, board, config.grid, best))
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
