"""Finding the capture card's window and taking screenshots of it (Windows)."""

from __future__ import annotations

import cv2
import mss
import numpy as np

Rect = tuple[int, int, int, int]  # left, top, right, bottom


def find_window(title: str) -> Rect | None:
    """Screen rectangle of the first visible window whose title contains `title`."""
    try:
        import win32gui
    except ImportError as error:
        raise RuntimeError("Finding the capture window needs Windows and the pywin32 package.") from error

    matches: list[Rect] = []

    def check(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and title.lower() in win32gui.GetWindowText(hwnd).lower():
            matches.append(win32gui.GetWindowRect(hwnd))

    win32gui.EnumWindows(check, None)
    return matches[0] if matches else None


def capture(rect: Rect) -> np.ndarray:
    """Screenshot of a screen rectangle as a BGR image. The window must be visible (not minimized)."""
    left, top, right, bottom = rect
    with mss.mss() as screen:
        shot = screen.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
    return cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
