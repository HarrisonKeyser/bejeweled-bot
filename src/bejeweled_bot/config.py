"""Settings, loaded from a TOML file (see config.example.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

Grid = tuple[int, int, int, int]


@dataclass
class Config:
    pi_host: str = "raspberrypi.local"
    pi_port: int = 65432
    source: str = "device"  # "device" (read the capture card) or "window" (screenshot a window)
    device: int = 0
    resolution: tuple[int, int] = (1920, 1080)
    window_title: str = "Game Capture HD"
    # Where the 8x8 board sits in each frame: (x, y, width, height), or None to find it automatically.
    grid: Grid | None = None
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

    source = capture.get("source", defaults.source)
    if source not in ("device", "window"):
        raise ValueError('capture.source must be "device" or "window"')

    grid = capture.get("grid", "auto")
    if grid == "auto":
        grid = None
    elif isinstance(grid, list) and len(grid) == 4:
        grid = tuple(int(v) for v in grid)
    else:
        raise ValueError('capture.grid must be "auto" or [x, y, width, height]')

    resolution = tuple(int(v) for v in capture.get("resolution", defaults.resolution))
    if len(resolution) != 2:
        raise ValueError("capture.resolution must be [width, height]")

    return Config(
        pi_host=pi.get("host", defaults.pi_host),
        pi_port=int(pi.get("port", defaults.pi_port)),
        source=source,
        device=int(capture.get("device", defaults.device)),
        resolution=resolution,
        window_title=capture.get("window_title", defaults.window_title),
        grid=grid,
        input_delay=float(timing.get("input_delay", defaults.input_delay)),
        pre_swap_delay=float(timing.get("pre_swap_delay", defaults.pre_swap_delay)),
    )
