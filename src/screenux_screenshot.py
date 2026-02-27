#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
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
PORTAL_DEST = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SCREENSHOT_IFACE = "org.freedesktop.portal.Screenshot"
PORTAL_REQUEST_IFACE = "org.freedesktop.portal.Request"


def resolve_save_dir() -> Path:
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


def _normalize_bus_name(unique_name: str) -> str:
    return unique_name.lstrip(":").replace(".", "_")


def _extract_uri(results: object) -> str | None:
    if not isinstance(results, dict):
        return None
    value = results.get("uri")
    if value is None:
        return None
    if hasattr(value, "unpack"):
        value = value.unpack()
    return value if isinstance(value, str) and value else None


class MainWindow(Gtk.ApplicationWindow):  # type: ignore[misc]
    def __init__(self, app: Gtk.Application):  # type: ignore[name-defined]
        super().__init__(application=app, title="Screenux Screenshot")
        self.set_default_size(360, 140)

        self._request_counter = 0
        self._bus = None
        self._signal_sub_id: int | None = None

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        self._button = Gtk.Button(label="Take Screenshot")
        self._button.connect("clicked", self._on_take_screenshot)
        box.append(self._button)

        self._status_label = Gtk.Label(label="Ready")
        self._status_label.set_xalign(0.0)
        box.append(self._status_label)

        self.set_child(box)

    def _build_handle_token(self) -> str:
        self._request_counter += 1
        return f"screenux_{os.getpid()}_{self._request_counter}_{int(time.time() * 1000)}"

    def _set_status(self, text: str) -> None:
        self._status_label.set_text(text)

    def _unsubscribe_signal(self) -> None:
        if self._bus is not None and self._signal_sub_id is not None:
            self._bus.signal_unsubscribe(self._signal_sub_id)
            self._signal_sub_id = None

    def _finish(self, status: str) -> None:
        self._unsubscribe_signal()
        self._button.set_sensitive(True)
        self._set_status(status)

    def _fail(self, reason: str) -> None:
        self._finish(f"Failed: {reason}")

    def _on_take_screenshot(self, _button: Gtk.Button) -> None:  # type: ignore[name-defined]
        self._button.set_sensitive(False)
        self._set_status("Capturing...")

        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            sender_name = self._bus.get_unique_name()
            if not sender_name:
                raise RuntimeError("missing DBus unique name")

            token = self._build_handle_token()
            request_path = (
                f"/org/freedesktop/portal/desktop/request/{_normalize_bus_name(sender_name)}/{token}"
            )

            self._signal_sub_id = self._bus.signal_subscribe(
                PORTAL_DEST,
                PORTAL_REQUEST_IFACE,
                "Response",
                request_path,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_portal_response,
            )

            options = {
                "handle_token": GLib.Variant("s", token),
                "interactive": GLib.Variant("b", True),
            }
            params = GLib.Variant("(sa{sv})", ("", options))

            result = self._bus.call_sync(
                PORTAL_DEST,
                PORTAL_PATH,
                PORTAL_SCREENSHOT_IFACE,
                "Screenshot",
                params,
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )

            returned_request_path = result.unpack()[0]
            if returned_request_path != request_path:
                # Keep listening on the path returned by the portal if it differs.
                self._unsubscribe_signal()
                self._signal_sub_id = self._bus.signal_subscribe(
                    PORTAL_DEST,
                    PORTAL_REQUEST_IFACE,
                    "Response",
                    returned_request_path,
                    None,
                    Gio.DBusSignalFlags.NONE,
                    self._on_portal_response,
                )
        except GLib.Error as err:
            self._fail(f"portal unavailable ({err.message})")
        except Exception as err:
            self._fail(str(err))

    def _save_uri(self, source_uri: str) -> None:
        destination_path = build_output_path(source_uri)
        source = Gio.File.new_for_uri(source_uri)
        target = Gio.File.new_for_path(str(destination_path))
        source.copy(target, Gio.FileCopyFlags.OVERWRITE, None, None, None)
        self._finish(format_status_saved(destination_path))

    def _on_portal_response(
        self,
        _connection: Gio.DBusConnection,
        _sender_name: str,
        _object_path: str,
        _interface_name: str,
        _signal_name: str,
        parameters: GLib.Variant,
    ) -> None:
        try:
            response_code, results = parameters.unpack()
            if response_code == 0:
                source_uri = _extract_uri(results)
                if not source_uri:
                    self._fail("no screenshot returned")
                    return
                self._save_uri(source_uri)
                return
            if response_code == 1:
                self._finish("Cancelled")
                return
            self._fail("portal error")
        except GLib.Error as err:
            self._fail(f"could not save ({err.message})")
        except Exception as err:
            self._fail(str(err))


class ScreenuxScreenshotApp(Gtk.Application):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

    def do_activate(self) -> None:
        window = self.props.active_window
        if window is None:
            window = MainWindow(self)
        window.present()


def main(argv: list[str]) -> int:
    if GI_IMPORT_ERROR is not None or Gtk is None:
        print(
            f"Missing GTK4/PyGObject dependencies: {GI_IMPORT_ERROR}",
            file=sys.stderr,
        )
        return 1
    app = ScreenuxScreenshotApp()
    return app.run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
