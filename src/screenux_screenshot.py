#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
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
    Gio = None  # type: ignore[assignment]  # pragma: no cover
    GLib = None  # type: ignore[assignment]  # pragma: no cover
    Gtk = None  # type: ignore[assignment]  # pragma: no cover

APP_ID = "io.github.rafa.ScreenuxScreenshot"
_MAX_CONFIG_SIZE = 64 * 1024
_ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}


def enforce_offline_mode() -> None:
    blocked = RuntimeError("network access is disabled for this application")

    def _raise_blocked(*_args, **_kwargs):
        raise blocked

    socket.create_connection = _raise_blocked  # type: ignore[assignment]
    socket.getaddrinfo = _raise_blocked  # type: ignore[assignment]
    socket.gethostbyname = _raise_blocked  # type: ignore[assignment]
    socket.gethostbyname_ex = _raise_blocked  # type: ignore[assignment]
    socket.gethostbyaddr = _raise_blocked  # type: ignore[assignment]
    socket.getnameinfo = _raise_blocked  # type: ignore[assignment]

    original_socket = socket.socket

    class OfflineSocket(original_socket):
        def connect(self, *_args, **_kwargs):
            raise blocked

        def connect_ex(self, *_args, **_kwargs):
            raise blocked

        def sendto(self, *_args, **_kwargs):
            raise blocked

    socket.socket = OfflineSocket  # type: ignore[assignment]


def _config_path() -> Path:
    if GLib is not None:
        return Path(GLib.get_user_config_dir()) / "screenux" / "settings.json"
    return Path.home() / ".config" / "screenux" / "settings.json"


def load_config() -> dict:
    path = _config_path()
    if path.is_file():
        try:
            stat = path.stat()
            if stat.st_size > _MAX_CONFIG_SIZE:
                return {}
            config = json.loads(path.read_text(encoding="utf-8"))
            return config if isinstance(config, dict) else {}
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config: dict) -> None:
    if not isinstance(config, dict):
        raise TypeError("config must be a dictionary")
    path = _config_path()
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass

    temp_path = path.with_name(f".{path.name}.tmp")
    payload = json.dumps(config, indent=2)
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def resolve_save_dir() -> Path:
    config = load_config()
    custom_dir = config.get("save_dir")
    if isinstance(custom_dir, str) and custom_dir.strip():
        custom_path = Path(custom_dir).expanduser()
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
    return suffix if suffix in _ALLOWED_EXTENSIONS else ".png"


def build_output_path(source_uri: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    save_dir = resolve_save_dir().resolve()
    output_path = (save_dir / f"Screenshot_{timestamp}{_extension_from_uri(source_uri)}").resolve()
    if output_path.parent != save_dir:
        raise ValueError("resolved output path escapes save directory")
    return output_path


def format_status_saved(path: Path) -> str:
    return f"Saved: {path}"


def _parse_cli_args(argv: list[str]) -> tuple[list[str], bool]:
    filtered = [argv[0]] if argv else []
    auto_capture = False
    for arg in argv[1:]:
        if arg == "--capture":
            auto_capture = True
            continue
        filtered.append(arg)
    return filtered, auto_capture


MainWindow = None
if Gtk is not None:
    try:
        from screenux_window import MainWindow
    except Exception as exc:  # pragma: no cover - handled at runtime
        GI_IMPORT_ERROR = GI_IMPORT_ERROR or exc


if Gtk is not None:
    class ScreenuxScreenshotApp(Gtk.Application):  # type: ignore[misc]
        def __init__(self, auto_capture: bool = False) -> None:
            super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
            self._auto_capture_pending = auto_capture

        def _trigger_auto_capture(self, window: MainWindow) -> bool:
            window.take_screenshot()
            return False

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
            if self._auto_capture_pending:
                self._auto_capture_pending = False
                GLib.idle_add(self._trigger_auto_capture, window)
else:
    class ScreenuxScreenshotApp:  # pragma: no cover
        def run(self, _argv: list[str]) -> int:
            return 1


def main(argv: list[str]) -> int:
    enforce_offline_mode()
    if GI_IMPORT_ERROR is not None or Gtk is None or MainWindow is None:
        print(f"Missing GTK4/PyGObject dependencies: {GI_IMPORT_ERROR}", file=sys.stderr)
        return 1
    app_argv, auto_capture = _parse_cli_args(argv)
    app = ScreenuxScreenshotApp(auto_capture=auto_capture)
    return app.run(app_argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
