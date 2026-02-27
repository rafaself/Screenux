#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

GI_IMPORT_ERROR: Exception | None = None
try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gio, GLib, Gtk
except Exception as exc:  # pragma: no cover - handled at runtime
    GI_IMPORT_ERROR = exc
    Gio = None  # type: ignore[assignment]
    GLib = None  # type: ignore[assignment]
    Gtk = None  # type: ignore[assignment]

APP_ID = "io.github.rafa.ScreenuxScreenshot"


def _config_path() -> Path:
    if GLib is not None:
        return Path(GLib.get_user_config_dir()) / "screenux" / "settings.json"
    return Path.home() / ".config" / "screenux" / "settings.json"


def load_config() -> dict:
    path = _config_path()
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


def resolve_save_dir() -> Path:
    config = load_config()
    custom_dir = config.get("save_dir")
    if custom_dir:
        custom_path = Path(custom_dir)
        if custom_path.is_dir() and os.access(custom_path, os.W_OK | os.X_OK):
            return custom_path

    desktop_dir: str | None = None
    if GLib is not None:
        desktop_dir = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DESKTOP)

    if desktop_dir:
        desktop_path = Path(desktop_dir).expanduser()
        if desktop_path.is_dir() and os.access(desktop_path, os.W_OK | os.X_OK):
            return desktop_path

    return Path.home()


def _extension_from_uri(source_uri: str) -> str:
    suffix = Path(unquote(urlparse(source_uri).path)).suffix.lower()
    return suffix if suffix else ".png"


def build_output_path(source_uri: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return resolve_save_dir() / f"Screenshot_{timestamp}{_extension_from_uri(source_uri)}"


def format_status_saved(path: Path) -> str:
    return f"Saved: {path}"


MainWindow = None
if Gtk is not None:
    try:
        from screenux_window import MainWindow
    except Exception as exc:  # pragma: no cover - handled at runtime
        GI_IMPORT_ERROR = GI_IMPORT_ERROR or exc


if Gtk is not None:
    class ScreenuxScreenshotApp(Gtk.Application):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

        def do_activate(self) -> None:
            window = self.props.active_window
            if window is None:
                window = MainWindow(
                    self,
                    resolve_save_dir=resolve_save_dir,
                    load_config=load_config,
                    save_config=save_config,
                    build_output_path=build_output_path,
                    format_status_saved=format_status_saved,
                )
            window.present()
else:
    class ScreenuxScreenshotApp:  # pragma: no cover
        def run(self, _argv: list[str]) -> int:
            return 1


def main(argv: list[str]) -> int:
    if GI_IMPORT_ERROR is not None or Gtk is None or MainWindow is None:
        print(f"Missing GTK4/PyGObject dependencies: {GI_IMPORT_ERROR}", file=sys.stderr)
        return 1
    app = ScreenuxScreenshotApp()
    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
