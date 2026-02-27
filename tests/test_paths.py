import json
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
    monkeypatch.setattr(app, "load_config", lambda: {})
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
    monkeypatch.setattr(app, "load_config", lambda: {})
    monkeypatch.setattr(app.Path, "home", staticmethod(lambda: home))

    assert app.resolve_save_dir() == home


def test_resolve_save_dir_uses_config_when_set(tmp_path, monkeypatch):
    custom_dir = tmp_path / "Screenshots"
    custom_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setattr(app, "load_config", lambda: {"save_dir": str(custom_dir)})
    monkeypatch.setattr(app, "GLib", None)
    monkeypatch.setattr(app.Path, "home", staticmethod(lambda: home))

    assert app.resolve_save_dir() == custom_dir


def test_resolve_save_dir_ignores_invalid_config_dir(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setattr(app, "load_config", lambda: {"save_dir": "/nonexistent/path"})
    monkeypatch.setattr(app, "GLib", None)
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


def test_load_config_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "_config_path", lambda: tmp_path / "missing.json")
    assert app.load_config() == {}


def test_save_and_load_config(tmp_path, monkeypatch):
    config_file = tmp_path / "screenux" / "settings.json"
    monkeypatch.setattr(app, "_config_path", lambda: config_file)

    app.save_config({"save_dir": "/home/user/Screenshots"})
    assert config_file.is_file()

    loaded = app.load_config()
    assert loaded == {"save_dir": "/home/user/Screenshots"}


def test_load_config_handles_corrupt_json(tmp_path, monkeypatch):
    config_file = tmp_path / "settings.json"
    config_file.write_text("not valid json{{{", encoding="utf-8")
    monkeypatch.setattr(app, "_config_path", lambda: config_file)

    assert app.load_config() == {}
