import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import screenux_screenshot as app


def test_resolve_save_dir_uses_desktop_when_available(tmp_path, monkeypatch):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    class FakeGLib:
        class UserDirectory:
            DIRECTORY_DESKTOP = object()

        @staticmethod
        def get_user_special_dir(_directory):
            return str(desktop)

    monkeypatch.setattr(app, "GLib", FakeGLib)
    monkeypatch.setattr(app.Path, "home", staticmethod(lambda: home))

    assert app.resolve_save_dir() == desktop


def test_resolve_save_dir_falls_back_to_home_when_desktop_missing(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()

    class FakeGLib:
        class UserDirectory:
            DIRECTORY_DESKTOP = object()

        @staticmethod
        def get_user_special_dir(_directory):
            return None

    monkeypatch.setattr(app, "GLib", FakeGLib)
    monkeypatch.setattr(app.Path, "home", staticmethod(lambda: home))

    assert app.resolve_save_dir() == home


def test_build_output_path_preserves_extension(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "resolve_save_dir", lambda: tmp_path)
    output_path = app.build_output_path("file:///tmp/capture.jpeg")
    assert output_path.parent == tmp_path
    assert output_path.suffix == ".jpeg"
    assert re.match(r"^Screenshot_\d{8}_\d{6}_\d{6}\.jpeg$", output_path.name)


def test_build_output_path_defaults_to_png(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "resolve_save_dir", lambda: tmp_path)
    output_path = app.build_output_path("file:///tmp/capture")
    assert output_path.parent == tmp_path
    assert output_path.suffix == ".png"
    assert re.match(r"^Screenshot_\d{8}_\d{6}_\d{6}\.png$", output_path.name)


def test_format_status_saved(tmp_path):
    saved_path = tmp_path / "Screenshot_20260101_000000_000000.png"
    assert app.format_status_saved(saved_path) == f"Saved: {saved_path}"
