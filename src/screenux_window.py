from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import Any, Callable

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk, Pango

from screenux_editor import AnnotationEditor, load_image_surface

PORTAL_DEST = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SCREENSHOT_IFACE = "org.freedesktop.portal.Screenshot"
PORTAL_REQUEST_IFACE = "org.freedesktop.portal.Request"


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


def _uri_to_local_path(source_uri: str) -> Path | None:
    parsed = urlparse(source_uri)
    if parsed.scheme != "file":
        return None
    if parsed.netloc not in ("", "localhost"):
        return None

    decoded = unquote(parsed.path)
    if not decoded:
        return None

    path = Path(decoded)
    if not path.is_absolute():
        return None

    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None

    if not resolved.is_file() or not os.access(resolved, os.R_OK):
        return None
    return resolved


class MainWindow(Gtk.ApplicationWindow):  # type: ignore[misc]
    def __init__(
        self,
        app: Gtk.Application,
        icon_name: str,
        resolve_save_dir: Callable[[], Path],
        load_config: Callable[[], dict[str, Any]],
        save_config: Callable[[dict[str, Any]], None],
        build_output_path: Callable[[str], Path],
        format_status_saved: Callable[[Path], str],
        hotkey_manager: Any | None = None,
        initial_hotkey_warning: str | None = None,
    ):
        super().__init__(application=app, title="Screenux Screenshot")
        self.set_icon_name(icon_name)
        self.set_default_size(360, 180)

        self._resolve_save_dir = resolve_save_dir
        self._load_config = load_config
        self._save_config = save_config
        self._build_output_path = build_output_path
        self._format_status_saved = format_status_saved
        self._hotkey_manager = hotkey_manager

        self._request_counter = 0
        self._bus = None
        self._signal_sub_id: int | None = None
        self._hotkey_entry: Gtk.Entry | None = None
        self._hotkey_value_label: Gtk.Label | None = None

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._main_box.set_margin_top(16)
        self._main_box.set_margin_bottom(16)
        self._main_box.set_margin_start(16)
        self._main_box.set_margin_end(16)

        self._button = Gtk.Button(label="Take Screenshot")
        self._button.connect("clicked", lambda _button: self.take_screenshot())
        self._main_box.append(self._button)

        self._status_label = Gtk.Label(label="Ready")
        self._status_label.set_xalign(0.0)
        self._main_box.append(self._status_label)

        folder_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        folder_row.append(Gtk.Label(label="Save to:"))

        self._folder_label = Gtk.Label(label=str(self._resolve_save_dir()))
        self._folder_label.set_xalign(0.0)
        self._folder_label.set_hexpand(True)
        self._folder_label.set_ellipsize(Pango.EllipsizeMode.START)
        folder_row.append(self._folder_label)

        change_btn = Gtk.Button(label="Change…")
        change_btn.connect("clicked", self._on_change_folder)
        folder_row.append(change_btn)

        self._main_box.append(folder_row)
        self._build_hotkey_settings()
        self.set_child(self._main_box)

        if initial_hotkey_warning:
            self.set_nonblocking_warning(initial_hotkey_warning)

    def take_screenshot(self) -> None:
        self._on_take_screenshot(self._button)

    def set_nonblocking_warning(self, warning_text: str) -> None:
        self._set_status(f"Warning: {warning_text}")

    def _build_hotkey_settings(self) -> None:
        if self._hotkey_manager is None:
            return

        current_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        current_row.append(Gtk.Label(label="Global hotkey:"))
        self._hotkey_value_label = Gtk.Label(label="")
        self._hotkey_value_label.set_xalign(0.0)
        self._hotkey_value_label.set_hexpand(True)
        current_row.append(self._hotkey_value_label)
        self._main_box.append(current_row)

        edit_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._hotkey_entry = Gtk.Entry()
        self._hotkey_entry.set_hexpand(True)
        self._hotkey_entry.set_placeholder_text("Ctrl+Shift+S")
        edit_row.append(self._hotkey_entry)

        apply_btn = Gtk.Button(label="Apply")
        apply_btn.connect("clicked", self._on_hotkey_apply)
        edit_row.append(apply_btn)

        disable_btn = Gtk.Button(label="Disable")
        disable_btn.connect("clicked", self._on_hotkey_disable)
        edit_row.append(disable_btn)

        self._main_box.append(edit_row)
        self._refresh_hotkey_ui()

    def _refresh_hotkey_ui(self) -> None:
        if self._hotkey_manager is None:
            return
        current = self._hotkey_manager.current_shortcut()
        if self._hotkey_value_label is not None:
            self._hotkey_value_label.set_text(current or "Disabled")
        if self._hotkey_entry is not None:
            self._hotkey_entry.set_text(current or "")

    def _apply_hotkey_result(self, result: Any) -> None:
        if self._hotkey_value_label is not None:
            self._hotkey_value_label.set_text(result.shortcut or "Disabled")
        if self._hotkey_entry is not None:
            self._hotkey_entry.set_text(result.shortcut or "")
        if result.warning:
            self.set_nonblocking_warning(result.warning)
            return
        self._set_status("Ready")

    def _on_hotkey_apply(self, _button: Gtk.Button) -> None:
        if self._hotkey_manager is None or self._hotkey_entry is None:
            return
        user_value = self._hotkey_entry.get_text().strip()
        if not user_value:
            self._set_status("Failed: shortcut cannot be empty (use Disable)")
            return
        try:
            result = self._hotkey_manager.apply_shortcut(user_value)
        except ValueError as err:
            self._set_status(f"Failed: invalid shortcut ({err})")
            return
        self._apply_hotkey_result(result)

    def _on_hotkey_disable(self, _button: Gtk.Button) -> None:
        if self._hotkey_manager is None:
            return
        result = self._hotkey_manager.disable_shortcut()
        self._apply_hotkey_result(result)

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

    def _show_main_panel(self) -> None:
        self.set_child(self._main_box)

    def _on_change_folder(self, _button: Gtk.Button) -> None:
        dialog = Gtk.FileDialog()
        dialog.set_title("Choose Screenshot Folder")
        dialog.set_initial_folder(Gio.File.new_for_path(str(self._resolve_save_dir())))
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(self, dialog: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                if not path:
                    self._fail("selected folder is not local")
                    return
                chosen_dir = Path(path)
                if not chosen_dir.is_dir() or not os.access(chosen_dir, os.W_OK | os.X_OK):
                    self._fail("selected folder is not writable")
                    return
                config = self._load_config()
                config["save_dir"] = path
                self._save_config(config)
                self._folder_label.set_text(path)
        except GLib.Error as err:
            self._set_status(f"Failed: could not change folder ({err.message})")
        except Exception as err:
            self._set_status(f"Failed: could not change folder ({err})")

    def _on_take_screenshot(self, _button: Gtk.Button) -> None:
        self._button.set_sensitive(False)
        self._set_status("Capturing...")

        try:
            self._bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            sender_name = self._bus.get_unique_name()
            if not sender_name:
                raise RuntimeError("missing DBus unique name")

            token = self._build_handle_token()
            request_path = (
                f"/org/freedesktop/portal/desktop/request/"
                f"{_normalize_bus_name(sender_name)}/{token}"
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
        self._unsubscribe_signal()
        source_path = _uri_to_local_path(source_uri)
        if source_path is None:
            self._fail("invalid screenshot source path")
            return
        try:
            surface = load_image_surface(str(source_path))
        except Exception as err:
            self._fail(f"could not load image ({err})")
            return

        editor = AnnotationEditor(
            surface,
            source_uri,
            build_output_path=self._build_output_path,
            on_save=self._on_editor_save,
            on_discard=self._on_editor_discard,
            on_error=self._on_editor_error,
        )
        self.set_child(editor)

    def _on_editor_save(self, saved_path: Path) -> None:
        self._show_main_panel()
        self._button.set_sensitive(True)
        self._set_status(self._format_status_saved(saved_path))

    def _on_editor_discard(self) -> None:
        self._show_main_panel()
        self._button.set_sensitive(True)
        self._set_status("Ready")

    def _on_editor_error(self, message: str) -> None:
        self._show_main_panel()
        self._button.set_sensitive(True)
        self._set_status(f"Failed: {message}")

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
