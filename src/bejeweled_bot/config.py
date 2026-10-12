"""Settings, loaded from a TOML file (see config.example.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    pi_host: str = "raspberrypi.local"
    pi_port: int = 65432
    window_title: str = "Game Capture HD"
    # Where the 8x8 board sits inside the capture window: x, y, width, height in pixels.
    grid: tuple[int, int, int, int] = (694, 88, 864, 864)
    input_delay: float = 0.01
    pre_swap_delay: float = 0.01


def load_config(path: str | Path | None) -> Config:
    if path is None:
        return Config()
    with open(path, "rb") as file:
        data = tomllib.load(file)

    pi = data.get("pi", {})
    capture = data.get("capture", {})
    timing = data.get("timing", {})
    defaults = Config()

    grid = tuple(capture.get("grid", defaults.grid))
    if len(grid) != 4:
        raise ValueError("capture.grid must be [x, y, width, height]")

    return Config(
        pi_host=pi.get("host", defaults.pi_host),
        pi_port=int(pi.get("port", defaults.pi_port)),
        window_title=capture.get("window_title", defaults.window_title),
        grid=tuple(int(v) for v in grid),
        input_delay=float(timing.get("input_delay", defaults.input_delay)),
        pre_swap_delay=float(timing.get("pre_swap_delay", defaults.pre_swap_delay)),
    )
