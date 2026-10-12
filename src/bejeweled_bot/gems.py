"""Names for everything that can sit in a cell of the 8x8 board."""

GRID_ROWS = 8
GRID_COLS = 8

COLORS = ("red", "orange", "yellow", "green", "blue", "purple", "white")

HYPERCUBE = "hypercube"
UNKNOWN = "unknown"  # empty, mid-animation, or unreadable

# A power gem (made by matching four) is stored as "power_<color>", e.g. "power_green".
POWER_PREFIX = "power_"


def power(color: str) -> str:
    return POWER_PREFIX + color


def is_power(gem: str) -> bool:
    return bool(gem) and gem.startswith(POWER_PREFIX)


def base_color(gem: str) -> str:
    """The color a gem matches as: a power gem matches its plain color."""
    return gem[len(POWER_PREFIX) :] if is_power(gem) else gem


# Short labels for the text board printout: R, G*, HC, ...
_LETTERS = {
    "red": "R",
    "orange": "O",
    "yellow": "Y",
    "green": "G",
    "blue": "B",
    "purple": "P",
    "white": "W",
    HYPERCUBE: "HC",
    UNKNOWN: "?",
}


def label(gem: str) -> str:
    if is_power(gem):
        return _LETTERS.get(base_color(gem), "?") + "*"
    return _LETTERS.get(gem, "?")


# BGR colors for drawing debug overlays with OpenCV.
OVERLAY_COLORS = {
    "red": (0, 0, 230),
    "orange": (0, 150, 255),
    "yellow": (0, 230, 230),
    "green": (0, 210, 0),
    "blue": (230, 120, 0),
    "purple": (230, 0, 230),
    "white": (235, 235, 235),
    HYPERCUBE: (255, 200, 0),
    UNKNOWN: (70, 70, 70),
}


def overlay_color(gem: str) -> tuple[int, int, int]:
    return OVERLAY_COLORS.get(base_color(gem), OVERLAY_COLORS[UNKNOWN])
