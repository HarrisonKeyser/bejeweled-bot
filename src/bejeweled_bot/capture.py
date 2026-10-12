"""
Where frames come from.

- DeviceSource reads the capture card directly, the way a webcam is read. Most
  capture cards from the last several years work this way (they're "UVC" devices),
  and it's the lowest-latency option. Only one program can use the card at a time,
  so close the card's own app (or OBS) first.
- WindowSource screenshots another program's window that shows the game, such as
  the capture card's app or OBS. This is how the original bot ran, with a 2012
  Elgato Game Capture HD whose app was the only way to see the video.
"""

from __future__ import annotations

import logging
import sys
import threading
import time

import cv2
import numpy as np

from . import screen

log = logging.getLogger(__name__)


class WindowSource:
    def __init__(self, title: str):
        self.title = title
        self._rect = None

    def read(self) -> np.ndarray | None:
        if self._rect is None:
            self._rect = screen.find_window(self.title)
            if self._rect is None:
                return None
        return screen.capture(self._rect)

    def reset(self) -> None:
        """Look for the window again (it moved or was reopened)."""
        self._rect = None

    def close(self) -> None:
        pass

    def describe(self) -> str:
        return f"the window titled '{self.title}'"


class DeviceSource:
    """
    Reads a video device on a background thread and always hands out the newest frame,
    so the bot never acts on a frame that sat in a buffer.
    """

    def __init__(self, index: int = 0, width: int = 1920, height: int = 1080):
        self.index, self.width, self.height = index, width, height
        self._capture = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self._thread = None

    def _open(self) -> bool:
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        capture = cv2.VideoCapture(self.index, backend)
        if not capture.isOpened():
            log.warning(
                "Couldn't open video device %d. Is another program using the capture card?", self.index
            )
            return False
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        actual = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
        if actual != (self.width, self.height):
            log.warning("Asked the capture card for %dx%d but got %dx%d", self.width, self.height, *actual)
        self._capture = capture
        self._running = True
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()
        return True

    def _pump(self) -> None:
        while self._running:
            ok, frame = self._capture.read()
            if ok:
                with self._lock:
                    self._frame = frame
            else:
                time.sleep(0.01)

    def read(self) -> np.ndarray | None:
        if self._capture is None and not self._open():
            return None
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            with self._lock:
                if self._frame is not None:
                    return self._frame.copy()
            time.sleep(0.01)
        log.warning("No frames from video device %d yet", self.index)
        return None

    def reset(self) -> None:
        self.close()

    def close(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        if self._capture is not None:
            self._capture.release()
        self._capture, self._frame, self._thread = None, None, None

    def describe(self) -> str:
        return f"video device {self.index}"


def open_source(config) -> WindowSource | DeviceSource:
    if config.source == "device":
        return DeviceSource(config.device, *config.resolution)
    return WindowSource(config.window_title)


def list_devices(max_index: int = 6) -> list[tuple[int, int, int]]:
    """Video devices that open, as (index, width, height). Webcams show up here too."""
    found = []
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    for index in range(max_index):
        capture = cv2.VideoCapture(index, backend)
        if capture.isOpened():
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
            ok, frame = capture.read()
            if ok:
                found.append((index, frame.shape[1], frame.shape[0]))
        capture.release()
    return found
