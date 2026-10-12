import time

import numpy as np
import pytest

from bejeweled_bot import capture
from bejeweled_bot.config import Config, load_config


def write(tmp_path, text):
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_defaults_read_the_capture_card_and_find_the_board():
    config = Config()
    assert config.source == "device"
    assert config.grid is None


def test_example_config_loads():
    config = load_config("config.example.toml")
    assert config.source == "device"
    assert config.grid is None


def test_reads_every_setting(tmp_path):
    config = load_config(
        write(
            tmp_path,
            """
        [pi]
        host = "10.0.0.7"
        port = 5000
        [capture]
        source = "window"
        window_title = "OBS"
        grid = [1, 2, 800, 800]
        [timing]
        input_delay = 0.05
    """,
        )
    )
    assert (config.pi_host, config.pi_port) == ("10.0.0.7", 5000)
    assert (config.source, config.window_title, config.grid) == ("window", "OBS", (1, 2, 800, 800))
    assert config.input_delay == 0.05


@pytest.mark.parametrize("bad", ['source = "camera"', "grid = [1, 2]", 'grid = "manual"'])
def test_rejects_bad_capture_settings(tmp_path, bad):
    with pytest.raises(ValueError):
        load_config(write(tmp_path, f"[capture]\n{bad}\n"))


class FakeVideoCapture:
    """Stands in for cv2.VideoCapture: hands out numbered frames."""

    def __init__(self, *_):
        self.count = 0
        self.released = False

    def isOpened(self):  # noqa: N802 (OpenCV's name)
        return True

    def set(self, *_):
        return True

    def get(self, prop):
        return {capture.cv2.CAP_PROP_FRAME_WIDTH: 1920, capture.cv2.CAP_PROP_FRAME_HEIGHT: 1080}.get(prop, 0)

    def read(self):
        self.count += 1
        return True, np.full((4, 4, 3), self.count % 250, np.uint8)

    def release(self):
        self.released = True


def test_device_source_hands_out_the_newest_frame(monkeypatch):
    monkeypatch.setattr(capture.cv2, "VideoCapture", FakeVideoCapture)
    source = capture.DeviceSource(0)
    try:
        first = source.read()
        time.sleep(0.05)
        later = source.read()
        assert later[0, 0, 0] != first[0, 0, 0]  # frames keep arriving in the background
    finally:
        source.close()
    assert source._capture is None


def test_open_source_picks_the_configured_kind():
    assert isinstance(capture.open_source(Config(source="device")), capture.DeviceSource)
    assert isinstance(capture.open_source(Config(source="window")), capture.WindowSource)
