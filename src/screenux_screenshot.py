#!/usr/bin/env python3
from __future__ import annotations

import io as _io
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from typing import Any

GI_IMPORT_ERROR: Exception | None = None
try:
    import gi

    gi.require_version("Gdk", "4.0")
    gi.require_version("Gtk", "4.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango
except Exception as exc:  # pragma: no cover - handled at runtime
    GI_IMPORT_ERROR = exc
    Gdk = None  # type: ignore[assignment]
    GdkPixbuf = None  # type: ignore[assignment]
    Gio = None  # type: ignore[assignment]
    GLib = None  # type: ignore[assignment]
    Gtk = None  # type: ignore[assignment]
    Pango = None  # type: ignore[assignment]

try:
    import cairo
except ImportError:  # pragma: no cover
    cairo = None  # type: ignore[assignment]

APP_ID = "io.github.rafa.ScreenuxScreenshot"
PORTAL_DEST = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_SCREENSHOT_IFACE = "org.freedesktop.portal.Screenshot"
PORTAL_REQUEST_IFACE = "org.freedesktop.portal.Request"

Color = tuple[float, float, float, float]
Point = tuple[float, float]
Annotation = dict[str, Any]


# --- Config persistence ---


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


# --- Path helpers ---


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


# --- Portal helpers ---


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


# --- Image loading ---


def _load_image_surface(file_path: str):
    """Load an image file as a Cairo ImageSurface."""
    try:
        return cairo.ImageSurface.create_from_png(file_path)
    except Exception:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
        success, png_data = pixbuf.save_to_bufferv("png", [], [])
        if not success:
            raise RuntimeError("failed to convert image to PNG")
        return cairo.ImageSurface.create_from_png(_io.BytesIO(png_data))


# --- Annotation helpers ---

_SELECTION_COLOR = (0.2, 0.5, 1.0, 0.8)
_HANDLE_SIZE = 6.0


def _annotation_bbox(ann: Annotation) -> tuple[float, float, float, float]:
    """Return (x_min, y_min, x_max, y_max) in image coordinates."""
    kind = ann["kind"]
    if kind == "text":
        text = ann.get("text", "")
        x = ann["x1"]
        y = ann["y1"]
        return (x, y - 24, x + max(len(text) * 14, 20), y + 4)
    return (
        min(ann["x1"], ann["x2"]),
        min(ann["y1"], ann["y2"]),
        max(ann["x1"], ann["x2"]),
        max(ann["y1"], ann["y2"]),
    )


def _hit_test(ann: Annotation, ix: float, iy: float, padding: float = 8.0) -> bool:
    """Return True if (ix, iy) is within the annotation bounding box."""
    x1, y1, x2, y2 = _annotation_bbox(ann)
    return (x1 - padding) <= ix <= (x2 + padding) and (y1 - padding) <= iy <= (y2 + padding)


def _render_annotation(cr, ann: Annotation) -> None:
    """Render a single annotation onto a Cairo context in image coordinates."""
    cr.new_path()
    r, g, b, a = ann["color"]
    cr.set_source_rgba(r, g, b, a)
    cr.set_line_width(3.0)
    kind = ann["kind"]

    if kind == "rectangle":
        x = min(ann["x1"], ann["x2"])
        y = min(ann["y1"], ann["y2"])
        w = abs(ann["x2"] - ann["x1"])
        h = abs(ann["y2"] - ann["y1"])
        cr.rectangle(x, y, w, h)
        cr.stroke()
    elif kind == "circle":
        cx = (ann["x1"] + ann["x2"]) / 2
        cy = (ann["y1"] + ann["y2"]) / 2
        rx = abs(ann["x2"] - ann["x1"]) / 2
        ry = abs(ann["y2"] - ann["y1"]) / 2
        if rx > 0 and ry > 0:
            cr.save()
            cr.translate(cx, cy)
            cr.scale(rx, ry)
            cr.arc(0, 0, 1, 0, 2 * math.pi)
            cr.restore()
            cr.stroke()
    elif kind == "text":
        cr.set_font_size(24)
        cr.move_to(ann["x1"], ann["y1"])
        cr.show_text(ann.get("text", ""))


def _render_selection_indicator(cr, ann: Annotation) -> None:
    """Draw a dashed bounding box with handles around the selected annotation."""
    cr.new_path()
    x1, y1, x2, y2 = _annotation_bbox(ann)
    pad = 4.0
    x1, y1, x2, y2 = x1 - pad, y1 - pad, x2 + pad, y2 + pad

    r, g, b, a = _SELECTION_COLOR
    cr.set_source_rgba(r, g, b, a)
    cr.set_line_width(1.5)
    cr.set_dash([6.0, 4.0])
    cr.rectangle(x1, y1, x2 - x1, y2 - y1)
    cr.stroke()
    cr.set_dash([])

    hs = _HANDLE_SIZE / 2
    for hx, hy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
        cr.rectangle(hx - hs, hy - hs, _HANDLE_SIZE, _HANDLE_SIZE)
        cr.fill()


def _deep_copy_annotations(annotations: list[Annotation]) -> list[Annotation]:
    return [dict(a) for a in annotations]


def _make_shape_annotation(
    kind: str,
    start: Point,
    end: Point,
    color: Color,
) -> Annotation:
    return {
        "kind": kind,
        "x1": start[0],
        "y1": start[1],
        "x2": end[0],
        "y2": end[1],
        "color": color,
    }


def _make_text_annotation(text: str, position: Point, color: Color) -> Annotation:
    return {
        "kind": "text",
        "x1": position[0],
        "y1": position[1],
        "x2": position[0],
        "y2": position[1],
        "color": color,
        "text": text,
    }


# --- Annotation Editor ---


class AnnotationEditor(Gtk.Box):  # type: ignore[misc]
    """Editor shown after capturing a screenshot for drawing annotations."""

    def __init__(
        self,
        surface,
        source_uri: str,
        on_save,
        on_discard,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._surface = surface
        self._source_uri = source_uri
        self._on_save = on_save
        self._on_discard = on_discard

        # Annotations
        self._annotations: list[Annotation] = []
        self._undo_stack: list[list[Annotation]] = []
        self._redo_stack: list[list[Annotation]] = []

        # Tools
        self._current_tool = "rectangle"
        self._current_color: Color = (1.0, 0.0, 0.0, 1.0)

        # Selection
        self._selected_index: int | None = None

        # Shape drawing drag state
        self._dragging = False
        self._drag_start: Point | None = None
        self._drag_end: Point | None = None
        self._widget_drag_start: Point | None = None

        # Move drag state
        self._move_dragging = False
        self._move_drag_start_img: Point | None = None
        self._move_orig_ann: Annotation | None = None
        self._pre_move_snapshot: list[Annotation] | None = None

        # Pan drag state (select on empty space)
        self._pan_dragging = False
        self._pan_drag_start: Point | None = None
        self._pan_start_values: Point | None = None

        # Viewport
        self._base_scale = 1.0
        self._zoom = 1.0
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        self._build_toolbar()
        self._build_canvas()
        self._build_actions()

    # --- Undo / Redo ---

    def _push_undo(self) -> None:
        self._undo_stack.append(_deep_copy_annotations(self._annotations))
        self._redo_stack.clear()

    def _on_undo(self, *_args) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(_deep_copy_annotations(self._annotations))
        self._annotations = self._undo_stack.pop()
        self._selected_index = None
        self._drawing_area.queue_draw()

    def _on_redo(self, *_args) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(_deep_copy_annotations(self._annotations))
        self._annotations = self._redo_stack.pop()
        self._selected_index = None
        self._drawing_area.queue_draw()

    # --- UI construction ---

    def _build_toolbar(self) -> None:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(8)

        def _tool_btn(label: str, tooltip: str, tool_name: str) -> Gtk.ToggleButton:
            btn = Gtk.ToggleButton()
            btn.set_child(Gtk.Label(label=label))
            btn.set_tooltip_text(tooltip)
            btn.connect("toggled", self._on_tool_toggled, tool_name)
            return btn

        select_btn = _tool_btn("\u2190\u2196", "Select / Move", "select")
        # Use a simpler arrow: just the northwest arrow
        select_btn.set_child(Gtk.Label(label="\u21F1"))
        rect_btn = _tool_btn("\u25AD", "Rectangle", "rectangle")
        rect_btn.set_active(True)
        circle_btn = _tool_btn("\u25CB", "Circle", "circle")
        text_btn = _tool_btn("A", "Text", "text")

        rect_btn.set_group(select_btn)
        circle_btn.set_group(select_btn)
        text_btn.set_group(select_btn)

        for btn in (select_btn, rect_btn, circle_btn, text_btn):
            toolbar.append(btn)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        color_dialog = Gtk.ColorDialog()
        self._color_btn = Gtk.ColorDialogButton(dialog=color_dialog)
        rgba = Gdk.RGBA()
        rgba.parse("red")
        self._color_btn.set_rgba(rgba)
        self._color_btn.connect("notify::rgba", self._on_color_changed)
        self._color_btn.set_tooltip_text("Annotation color")
        toolbar.append(self._color_btn)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        undo_btn = Gtk.Button.new_from_icon_name("edit-undo-symbolic")
        undo_btn.set_tooltip_text("Undo (Ctrl+Z)")
        undo_btn.connect("clicked", self._on_undo)
        toolbar.append(undo_btn)

        redo_btn = Gtk.Button.new_from_icon_name("edit-redo-symbolic")
        redo_btn.set_tooltip_text("Redo (Ctrl+Shift+Z)")
        redo_btn.connect("clicked", self._on_redo)
        toolbar.append(redo_btn)

        toolbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        zoom_out_btn = Gtk.Button.new_from_icon_name("zoom-out-symbolic")
        zoom_out_btn.set_tooltip_text("Zoom Out")
        zoom_out_btn.connect("clicked", self._on_zoom_out)
        toolbar.append(zoom_out_btn)

        zoom_in_btn = Gtk.Button.new_from_icon_name("zoom-in-symbolic")
        zoom_in_btn.set_tooltip_text("Zoom In")
        zoom_in_btn.connect("clicked", self._on_zoom_in)
        toolbar.append(zoom_in_btn)

        self.append(toolbar)

    def _build_canvas(self) -> None:
        self._drawing_area = Gtk.DrawingArea()
        self._drawing_area.set_vexpand(True)
        self._drawing_area.set_hexpand(True)
        self._drawing_area.set_content_width(640)
        self._drawing_area.set_content_height(480)
        self._drawing_area.set_draw_func(self._on_draw)
        self._drawing_area.set_focusable(True)
        self._drawing_area.set_can_focus(True)

        # Primary drag (button 1): shapes, select-move, select-pan
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self._drawing_area.add_controller(drag)

        # Middle mouse drag (button 2): always pan
        pan_drag = Gtk.GestureDrag(button=2)
        pan_drag.connect("drag-begin", self._on_mid_pan_begin)
        pan_drag.connect("drag-update", self._on_mid_pan_update)
        pan_drag.connect("drag-end", self._on_mid_pan_end)
        self._drawing_area.add_controller(pan_drag)

        # Click for select and text placement
        click = Gtk.GestureClick()
        click.connect("released", self._on_click_released)
        self._drawing_area.add_controller(click)

        # Scroll: Ctrl+scroll=zoom, plain=vertical pan, Shift=horizontal pan
        scroll_ctrl = Gtk.EventControllerScroll(
            flags=(
                Gtk.EventControllerScrollFlags.VERTICAL
                | Gtk.EventControllerScrollFlags.HORIZONTAL
            )
        )
        scroll_ctrl.connect("scroll", self._on_scroll)
        self._drawing_area.add_controller(scroll_ctrl)

        # Keyboard: Delete, Ctrl+Z, Ctrl+Shift+Z
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self._drawing_area.add_controller(key_ctrl)

        self.append(self._drawing_area)

    def _build_actions(self) -> None:
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_margin_start(8)
        actions.set_margin_end(8)
        actions.set_margin_bottom(8)
        actions.set_halign(Gtk.Align.END)

        discard_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        discard_btn.set_tooltip_text("Discard")
        discard_btn.connect("clicked", lambda _: self._on_discard())

        save_btn = Gtk.Button.new_from_icon_name("document-save-symbolic")
        save_btn.set_tooltip_text("Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self._do_save())

        actions.append(discard_btn)
        actions.append(save_btn)
        self.append(actions)

    # --- Tool & color ---

    def _on_tool_toggled(self, button: Gtk.ToggleButton, tool_name: str) -> None:
        if button.get_active():
            self._current_tool = tool_name
            if tool_name != "select":
                self._selected_index = None
            if hasattr(self, "_drawing_area"):
                self._drawing_area.queue_draw()

    def _on_color_changed(self, button: Gtk.ColorDialogButton, _pspec) -> None:
        rgba = button.get_rgba()
        self._current_color = (rgba.red, rgba.green, rgba.blue, rgba.alpha)

    # --- Coordinate transforms ---

    def _widget_to_image(self, wx: float, wy: float) -> tuple[float, float]:
        if self._scale == 0:
            return wx, wy
        return (
            (wx - self._offset_x) / self._scale,
            (wy - self._offset_y) / self._scale,
        )

    def _update_viewport(self, width: float, height: float) -> None:
        img_w = self._surface.get_width()
        img_h = self._surface.get_height()
        if img_w == 0 or img_h == 0:
            return
        self._base_scale = min(width / img_w, height / img_h)
        self._scale = self._base_scale * self._zoom
        self._offset_x = (width - img_w * self._scale) / 2 - self._pan_x * self._scale
        self._offset_y = (height - img_h * self._scale) / 2 - self._pan_y * self._scale

    # --- Hit testing ---

    def _find_hit(self, ix: float, iy: float) -> int | None:
        """Return index of top-most annotation under (ix, iy), or None."""
        for i in range(len(self._annotations) - 1, -1, -1):
            if _hit_test(self._annotations[i], ix, iy):
                return i
        return None

    def _start_move(self, hit_index: int, ix: float, iy: float, wx: float, wy: float) -> None:
        self._selected_index = hit_index
        self._move_dragging = True
        self._move_drag_start_img = (ix, iy)
        self._move_orig_ann = dict(self._annotations[hit_index])
        self._pre_move_snapshot = _deep_copy_annotations(self._annotations)
        self._widget_drag_start = (wx, wy)

    def _start_pan(self, wx: float, wy: float) -> None:
        self._selected_index = None
        self._pan_dragging = True
        self._pan_drag_start = (wx, wy)
        self._pan_start_values = (self._pan_x, self._pan_y)

    def _update_pan(self, offset_x: float, offset_y: float) -> None:
        if not self._pan_start_values:
            return
        px0, py0 = self._pan_start_values
        if self._scale:
            self._pan_x = px0 - offset_x / self._scale
            self._pan_y = py0 - offset_y / self._scale
        self._drawing_area.queue_draw()

    def _annotation_moved(self, current: Annotation, original: Annotation) -> bool:
        return any(
            current[key] != original[key]
            for key in ("x1", "y1", "x2", "y2")
        )

    # --- Drawing ---

    def _on_draw(self, _area, cr, width, height) -> None:
        self._update_viewport(width, height)

        cr.set_source_rgb(0.2, 0.2, 0.2)
        cr.paint()

        cr.save()
        cr.translate(self._offset_x, self._offset_y)
        cr.scale(self._scale, self._scale)
        cr.set_source_surface(self._surface, 0, 0)
        cr.paint()

        for ann in self._annotations:
            _render_annotation(cr, ann)

        # Draw preview of shape being drawn
        if self._dragging and self._drag_start and self._drag_end:
            _render_annotation(
                cr,
                _make_shape_annotation(
                    self._current_tool,
                    self._drag_start,
                    self._drag_end,
                    self._current_color,
                ),
            )

        # Draw selection indicator
        if (
            self._selected_index is not None
            and 0 <= self._selected_index < len(self._annotations)
        ):
            _render_selection_indicator(cr, self._annotations[self._selected_index])

        cr.restore()

    # --- Primary drag (button 1) ---

    def _on_drag_begin(self, _gesture, start_x: float, start_y: float) -> None:
        self._drawing_area.grab_focus()
        ix, iy = self._widget_to_image(start_x, start_y)

        if self._current_tool == "select":
            hit = self._find_hit(ix, iy)
            if hit is not None:
                should_redraw = hit != self._selected_index
                self._start_move(hit, ix, iy, start_x, start_y)
                if should_redraw:
                    self._drawing_area.queue_draw()
            else:
                self._start_pan(start_x, start_y)
                self._drawing_area.queue_draw()
            return

        if self._current_tool in ("rectangle", "circle"):
            self._widget_drag_start = (start_x, start_y)
            self._drag_start = (ix, iy)
            self._drag_end = (ix, iy)
            self._dragging = True

    def _on_drag_update(self, _gesture, offset_x: float, offset_y: float) -> None:
        # Move selected annotation
        if self._move_dragging and self._widget_drag_start and self._move_orig_ann:
            wx = self._widget_drag_start[0] + offset_x
            wy = self._widget_drag_start[1] + offset_y
            ix, iy = self._widget_to_image(wx, wy)
            sx, sy = self._move_drag_start_img
            dx, dy = ix - sx, iy - sy
            ann = self._annotations[self._selected_index]
            orig = self._move_orig_ann
            ann["x1"] = orig["x1"] + dx
            ann["y1"] = orig["y1"] + dy
            ann["x2"] = orig["x2"] + dx
            ann["y2"] = orig["y2"] + dy
            self._drawing_area.queue_draw()
            return

        # Pan via select on empty space
        if self._pan_dragging and self._pan_start_values:
            self._update_pan(offset_x, offset_y)
            return

        # Draw shape
        if self._dragging and self._widget_drag_start:
            wx = self._widget_drag_start[0] + offset_x
            wy = self._widget_drag_start[1] + offset_y
            self._drag_end = self._widget_to_image(wx, wy)
            self._drawing_area.queue_draw()

    def _on_drag_end(self, _gesture, offset_x: float, offset_y: float) -> None:
        # End move
        if self._move_dragging:
            self._move_dragging = False
            if self._pre_move_snapshot is not None and self._move_orig_ann is not None:
                # Check if position actually changed
                ann = self._annotations[self._selected_index]
                orig = self._move_orig_ann
                if self._annotation_moved(ann, orig):
                    self._undo_stack.append(self._pre_move_snapshot)
                    self._redo_stack.clear()
            self._pre_move_snapshot = None
            self._move_orig_ann = None
            self._drawing_area.queue_draw()
            return

        # End pan
        if self._pan_dragging:
            self._pan_dragging = False
            self._pan_drag_start = None
            self._pan_start_values = None
            return

        # End shape drawing
        if self._dragging and self._widget_drag_start:
            wx = self._widget_drag_start[0] + offset_x
            wy = self._widget_drag_start[1] + offset_y
            self._drag_end = self._widget_to_image(wx, wy)
            self._dragging = False
            self._push_undo()
            self._annotations.append(
                _make_shape_annotation(
                    self._current_tool,
                    self._drag_start,
                    self._drag_end,
                    self._current_color,
                )
            )
            self._drawing_area.queue_draw()

    # --- Middle mouse pan ---

    def _on_mid_pan_begin(self, _gesture, start_x: float, start_y: float) -> None:
        self._pan_drag_start = (start_x, start_y)
        self._pan_start_values = (self._pan_x, self._pan_y)

    def _on_mid_pan_update(self, _gesture, offset_x: float, offset_y: float) -> None:
        self._update_pan(offset_x, offset_y)

    def _on_mid_pan_end(self, _gesture, offset_x: float, offset_y: float) -> None:
        self._on_mid_pan_update(_gesture, offset_x, offset_y)
        self._pan_drag_start = None
        self._pan_start_values = None

    # --- Click ---

    def _on_click_released(self, _gesture, n_press: int, x: float, y: float) -> None:
        if n_press != 1:
            return

        ix, iy = self._widget_to_image(x, y)

        if self._current_tool == "select":
            hit = self._find_hit(ix, iy)
            self._selected_index = hit
            self._drawing_area.queue_draw()
            return

        if self._current_tool == "text" and not self._dragging:
            self._show_text_popover(x, y, ix, iy)

    def _show_text_popover(
        self, wx: float, wy: float, ix: float, iy: float
    ) -> None:
        popover = Gtk.Popover()
        entry = Gtk.Entry()
        entry.set_placeholder_text("Type text\u2026")

        def on_activate(_entry):
            text = entry.get_text().strip()
            if text:
                self._push_undo()
                self._annotations.append(
                    _make_text_annotation(text, (ix, iy), self._current_color)
                )
                self._drawing_area.queue_draw()
            popover.popdown()

        entry.connect("activate", on_activate)
        popover.set_child(entry)
        popover.set_parent(self._drawing_area)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(wx), int(wy), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    # --- Keyboard ---

    def _on_key_pressed(self, _ctrl, keyval, _keycode, state) -> bool:
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)

        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            if self._selected_index is not None and self._selected_index < len(self._annotations):
                self._push_undo()
                self._annotations.pop(self._selected_index)
                self._selected_index = None
                self._drawing_area.queue_draw()
                return True

        if ctrl and keyval == Gdk.KEY_z:
            if shift:
                self._on_redo()
            else:
                self._on_undo()
            return True

        if ctrl and keyval == Gdk.KEY_Z:
            self._on_redo()
            return True

        return False

    # --- Scroll (zoom + pan) ---

    def _on_scroll(self, ctrl, dx: float, dy: float) -> bool:
        state = ctrl.get_current_event_state()

        if state & Gdk.ModifierType.CONTROL_MASK:
            factor = 1.15 if dy < 0 else (1 / 1.15)
            new_zoom = max(0.25, min(4.0, self._zoom * factor))
            if new_zoom != self._zoom:
                self._zoom = new_zoom
            self._drawing_area.queue_draw()
            return True

        if state & Gdk.ModifierType.SHIFT_MASK:
            self._pan_x += dy * 30 / self._scale if self._scale else 0
            self._drawing_area.queue_draw()
            return True

        self._pan_y += dy * 30 / self._scale if self._scale else 0
        self._drawing_area.queue_draw()
        return True

    # --- Zoom buttons ---

    def _on_zoom_in(self, _btn) -> None:
        self._zoom = min(4.0, self._zoom * 1.25)
        self._drawing_area.queue_draw()

    def _on_zoom_out(self, _btn) -> None:
        self._zoom = max(0.25, self._zoom / 1.25)
        self._drawing_area.queue_draw()

    # --- Save ---

    def _do_save(self) -> None:
        img_w = self._surface.get_width()
        img_h = self._surface.get_height()
        output = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_w, img_h)
        cr = cairo.Context(output)

        cr.set_source_surface(self._surface, 0, 0)
        cr.paint()

        for ann in self._annotations:
            _render_annotation(cr, ann)

        dest = build_output_path(self._source_uri)
        output.write_to_png(str(dest))
        self._on_save(dest)


# --- Main Window ---


class MainWindow(Gtk.ApplicationWindow):  # type: ignore[misc]
    def __init__(self, app: Gtk.Application):  # type: ignore[name-defined]
        super().__init__(application=app, title="Screenux Screenshot")
        self.set_default_size(360, 180)

        self._request_counter = 0
        self._bus = None
        self._signal_sub_id: int | None = None

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._main_box.set_margin_top(16)
        self._main_box.set_margin_bottom(16)
        self._main_box.set_margin_start(16)
        self._main_box.set_margin_end(16)

        self._button = Gtk.Button(label="Take Screenshot")
        self._button.connect("clicked", self._on_take_screenshot)
        self._main_box.append(self._button)

        self._status_label = Gtk.Label(label="Ready")
        self._status_label.set_xalign(0.0)
        self._main_box.append(self._status_label)

        folder_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        folder_row.append(Gtk.Label(label="Save to:"))

        self._folder_label = Gtk.Label(label=str(resolve_save_dir()))
        self._folder_label.set_xalign(0.0)
        self._folder_label.set_hexpand(True)
        self._folder_label.set_ellipsize(Pango.EllipsizeMode.START)
        folder_row.append(self._folder_label)

        change_btn = Gtk.Button(label="Change…")
        change_btn.connect("clicked", self._on_change_folder)
        folder_row.append(change_btn)

        self._main_box.append(folder_row)

        self.set_child(self._main_box)

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
        dialog.set_initial_folder(Gio.File.new_for_path(str(resolve_save_dir())))
        dialog.select_folder(self, None, self._on_folder_selected)

    def _on_folder_selected(
        self, dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                path = folder.get_path()
                config = load_config()
                config["save_dir"] = path
                save_config(config)
                self._folder_label.set_text(path)
        except GLib.Error:
            pass

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
        uri_path = unquote(urlparse(source_uri).path)
        try:
            surface = _load_image_surface(uri_path)
        except Exception as err:
            self._fail(f"could not load image ({err})")
            return

        editor = AnnotationEditor(
            surface,
            source_uri,
            on_save=self._on_editor_save,
            on_discard=self._on_editor_discard,
        )
        self.set_child(editor)

    def _on_editor_save(self, saved_path: Path) -> None:
        self._show_main_panel()
        self._button.set_sensitive(True)
        self._set_status(format_status_saved(saved_path))

    def _on_editor_discard(self) -> None:
        self._show_main_panel()
        self._button.set_sensitive(True)
        self._set_status("Ready")

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
