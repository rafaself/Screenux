from __future__ import annotations

import io as _io
import math
import os
from pathlib import Path
from typing import Any, Callable

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

import cairo

Color = tuple[float, float, float, float]
Point = tuple[float, float]
Annotation = dict[str, Any]

_SELECTION_COLOR = (0.2, 0.5, 1.0, 0.8)
_HANDLE_SIZE = 6.0


def load_image_surface(file_path: str):
    try:
        return cairo.ImageSurface.create_from_png(file_path)
    except Exception:
        pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
        success, png_data = pixbuf.save_to_bufferv("png", [], [])
        if not success:
            raise RuntimeError("failed to convert image to PNG")
        return cairo.ImageSurface.create_from_png(_io.BytesIO(png_data))


def _annotation_bbox(ann: Annotation) -> tuple[float, float, float, float]:
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
    x1, y1, x2, y2 = _annotation_bbox(ann)
    return (x1 - padding) <= ix <= (x2 + padding) and (y1 - padding) <= iy <= (y2 + padding)


def _render_annotation(cr, ann: Annotation) -> None:
    cr.new_path()
    r, g, b, a = ann["color"]
    cr.set_source_rgba(r, g, b, a)
    cr.set_line_width(3.0)
    kind = ann["kind"]

    if kind in ("rectangle", "fill_rectangle"):
        x = min(ann["x1"], ann["x2"])
        y = min(ann["y1"], ann["y2"])
        w = abs(ann["x2"] - ann["x1"])
        h = abs(ann["y2"] - ann["y1"])
        cr.rectangle(x, y, w, h)
        if kind == "fill_rectangle":
            cr.fill_preserve()
        cr.stroke()
    elif kind in ("circle", "fill_circle"):
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
            if kind == "fill_circle":
                cr.fill_preserve()
            cr.stroke()
    elif kind == "text":
        cr.set_font_size(24)
        cr.move_to(ann["x1"], ann["y1"])
        cr.show_text(ann.get("text", ""))


def _render_selection_indicator(cr, ann: Annotation) -> None:
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


def _make_shape_annotation(kind: str, start: Point, end: Point, color: Color) -> Annotation:
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


def _write_surface_png_securely(surface, dest: Path) -> None:
    destination = dest.expanduser().resolve()
    parent = destination.parent
    if not parent.is_dir():
        raise RuntimeError("destination directory does not exist")

    png_buffer = _io.BytesIO()
    surface.write_to_png(png_buffer)
    data = png_buffer.getvalue()

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW

    fd = os.open(destination, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            destination.unlink(missing_ok=True)
        except Exception:
            pass
        raise


class AnnotationEditor(Gtk.Box):  # type: ignore[misc]
    def __init__(
        self,
        surface,
        source_uri: str,
        build_output_path: Callable[[str], Path],
        on_save: Callable[[Path], None],
        on_discard: Callable[[], None],
        on_error: Callable[[str], None],
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._surface = surface
        self._source_uri = source_uri
        self._build_output_path = build_output_path
        self._on_save = on_save
        self._on_discard = on_discard
        self._on_error = on_error

        self._annotations: list[Annotation] = []
        self._undo_stack: list[list[Annotation]] = []
        self._redo_stack: list[list[Annotation]] = []

        self._current_tool = "rectangle"
        self._current_color: Color = (1.0, 0.0, 0.0, 1.0)
        self._selected_index: int | None = None

        self._dragging = False
        self._drag_start: Point | None = None
        self._drag_end: Point | None = None
        self._widget_drag_start: Point | None = None

        self._move_dragging = False
        self._move_drag_start_img: Point | None = None
        self._move_orig_ann: Annotation | None = None
        self._pre_move_snapshot: list[Annotation] | None = None

        self._pan_dragging = False
        self._pan_drag_start: Point | None = None
        self._pan_start_values: Point | None = None

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

    def _build_toolbar(self) -> None:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        toolbar.set_margin_start(8)
        toolbar.set_margin_end(8)
        toolbar.set_margin_top(8)
        icon_dir = Path(__file__).resolve().parent / "icons"
        self._tool_icon_bindings: list[tuple[Gtk.Image, Path, str]] = []

        settings = Gtk.Settings.get_default()
        if settings is not None:
            settings.connect("notify::gtk-application-prefer-dark-theme", self._on_theme_changed)
            settings.connect("notify::gtk-theme-name", self._on_theme_changed)

        def _tool_btn(icon_file: str, fallback_label: str, tooltip: str, tool_name: str) -> Gtk.ToggleButton:
            btn = Gtk.ToggleButton()
            icon_path = icon_dir / icon_file
            image = Gtk.Image()
            image.set_pixel_size(18)
            if icon_path.is_file():
                self._load_svg_icon(image, icon_path)
                btn.set_child(image)
                self._tool_icon_bindings.append((image, icon_path, fallback_label))
            else:
                btn.set_child(Gtk.Label(label=fallback_label))
            btn.set_tooltip_text(tooltip)
            btn.connect("toggled", self._on_tool_toggled, tool_name)
            return btn

        select_btn = _tool_btn("tool-select.svg", "⇱", "Select / Move", "select")
        rect_btn = _tool_btn("tool-rectangle-outline.svg", "▭", "Rectangle", "rectangle")
        fill_rect_btn = _tool_btn("tool-rectangle-fill.svg", "▮", "Filled Rectangle", "fill_rectangle")
        rect_btn.set_active(True)
        circle_btn = _tool_btn("tool-circle-outline.svg", "○", "Circle", "circle")
        fill_circle_btn = _tool_btn("tool-circle-fill.svg", "◉", "Filled Circle", "fill_circle")
        text_btn = _tool_btn("tool-text.svg", "✎", "Text", "text")

        rect_btn.set_group(select_btn)
        fill_rect_btn.set_group(select_btn)
        circle_btn.set_group(select_btn)
        fill_circle_btn.set_group(select_btn)
        text_btn.set_group(select_btn)

        self._select_btn = select_btn

        for btn in (select_btn, rect_btn, fill_rect_btn, circle_btn, fill_circle_btn, text_btn):
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

    def _toolbar_icon_color(self) -> str:
        settings = Gtk.Settings.get_default()
        is_dark = False
        if settings is not None:
            prefers_dark = bool(settings.get_property("gtk-application-prefer-dark-theme"))
            theme_name = str(settings.get_property("gtk-theme-name") or "").lower()
            is_dark = prefers_dark or ("dark" in theme_name)
        return "#F5F7FA" if is_dark else "#111318"

    def _on_theme_changed(self, *_args) -> None:
        self._refresh_tool_icons()

    def _load_svg_icon(self, image: Gtk.Image, icon_path: Path) -> bool:
        if not icon_path.is_file():
            image.set_from_icon_name(None)
            return False
        try:
            fill = self._toolbar_icon_color()
            svg = icon_path.read_text(encoding="utf-8").replace("currentColor", fill)
            loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
            loader.write(svg.encode("utf-8"))
            loader.close()
            pixbuf = loader.get_pixbuf()
            if pixbuf is None:
                image.set_from_icon_name(None)
                return False
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            image.set_from_paintable(texture)
            return True
        except Exception:
            image.set_from_icon_name(None)
            return False

    def _refresh_tool_icons(self) -> None:
        for image, icon_path, _fallback in getattr(self, "_tool_icon_bindings", []):
            self._load_svg_icon(image, icon_path)

    def _build_canvas(self) -> None:
        self._drawing_area = Gtk.DrawingArea()
        self._drawing_area.set_vexpand(True)
        self._drawing_area.set_hexpand(True)
        self._drawing_area.set_content_width(640)
        self._drawing_area.set_content_height(480)
        self._drawing_area.set_draw_func(self._on_draw)
        self._drawing_area.set_focusable(True)
        self._drawing_area.set_can_focus(True)

        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self._drawing_area.add_controller(drag)

        pan_drag = Gtk.GestureDrag(button=2)
        pan_drag.connect("drag-begin", self._on_mid_pan_begin)
        pan_drag.connect("drag-update", self._on_mid_pan_update)
        pan_drag.connect("drag-end", self._on_mid_pan_end)
        self._drawing_area.add_controller(pan_drag)

        click = Gtk.GestureClick()
        click.connect("released", self._on_click_released)
        self._drawing_area.add_controller(click)

        scroll_ctrl = Gtk.EventControllerScroll(
            flags=(
                Gtk.EventControllerScrollFlags.VERTICAL
                | Gtk.EventControllerScrollFlags.HORIZONTAL
            )
        )
        scroll_ctrl.connect("scroll", self._on_scroll)
        self._drawing_area.add_controller(scroll_ctrl)

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

        def _icon_label_button(icon_name: str, label: str) -> Gtk.Button:
            btn = Gtk.Button()
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.append(Gtk.Image.new_from_icon_name(icon_name))
            row.append(Gtk.Label(label=label))
            btn.set_child(row)
            return btn

        discard_btn = _icon_label_button("user-trash-symbolic", "Discard")
        discard_btn.set_tooltip_text("Discard")
        discard_btn.connect("clicked", lambda _: self._on_discard())

        copy_btn = _icon_label_button("edit-copy-symbolic", "Copy")
        copy_btn.set_tooltip_text("Copy to Clipboard (Ctrl+C)")
        copy_btn.connect("clicked", lambda _: self._copy_to_clipboard())

        save_btn = _icon_label_button("document-save-symbolic", "Save")
        save_btn.set_tooltip_text("Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda _: self._do_save())

        actions.append(discard_btn)
        actions.append(copy_btn)
        actions.append(save_btn)
        self.append(actions)

    def _set_select_tool(self) -> None:
        self._current_tool = "select"
        if hasattr(self, "_select_btn"):
            self._select_btn.set_active(True)
        self._update_draw_cursor()
        if hasattr(self, "_drawing_area"):
            self._drawing_area.queue_draw()

    def _update_draw_cursor(self) -> None:
        if not hasattr(self, "_drawing_area"):
            return
        if self._current_tool in ("rectangle", "fill_rectangle", "circle", "fill_circle", "text"):
            self._drawing_area.set_cursor_from_name("crosshair")
        else:
            self._drawing_area.set_cursor_from_name(None)

    def _render_output_surface(self):
        img_w = self._surface.get_width()
        img_h = self._surface.get_height()
        output = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_w, img_h)
        cr = cairo.Context(output)
        cr.set_source_surface(self._surface, 0, 0)
        cr.paint()
        for ann in self._annotations:
            _render_annotation(cr, ann)
        return output

    def _copy_to_clipboard(self) -> None:
        try:
            output = self._render_output_surface()
            png_buffer = _io.BytesIO()
            output.write_to_png(png_buffer)
            bytes_value = GLib.Bytes.new(png_buffer.getvalue())
            provider = Gdk.ContentProvider.new_for_bytes("image/png", bytes_value)
            clipboard = self.get_display().get_clipboard()
            clipboard.set_content(provider)
        except Exception as err:
            self._on_error(f"could not copy image ({err})")

    def _on_tool_toggled(self, button: Gtk.ToggleButton, tool_name: str) -> None:
        if button.get_active():
            self._current_tool = tool_name
            self._update_draw_cursor()
            if tool_name != "select":
                self._selected_index = None
            if hasattr(self, "_drawing_area"):
                self._drawing_area.queue_draw()

    def _on_color_changed(self, button: Gtk.ColorDialogButton, _pspec) -> None:
        rgba = button.get_rgba()
        self._current_color = (rgba.red, rgba.green, rgba.blue, rgba.alpha)

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

    def _find_hit(self, ix: float, iy: float) -> int | None:
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
        return any(current[key] != original[key] for key in ("x1", "y1", "x2", "y2"))

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

        if self._selected_index is not None and 0 <= self._selected_index < len(self._annotations):
            _render_selection_indicator(cr, self._annotations[self._selected_index])

        cr.restore()

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

        if self._current_tool in ("rectangle", "fill_rectangle", "circle", "fill_circle"):
            self._widget_drag_start = (start_x, start_y)
            self._drag_start = (ix, iy)
            self._drag_end = (ix, iy)
            self._dragging = True

    def _on_drag_update(self, _gesture, offset_x: float, offset_y: float) -> None:
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

        if self._pan_dragging and self._pan_start_values:
            self._update_pan(offset_x, offset_y)
            return

        if self._dragging and self._widget_drag_start:
            wx = self._widget_drag_start[0] + offset_x
            wy = self._widget_drag_start[1] + offset_y
            self._drag_end = self._widget_to_image(wx, wy)
            self._drawing_area.queue_draw()

    def _on_drag_end(self, _gesture, offset_x: float, offset_y: float) -> None:
        if self._move_dragging:
            self._move_dragging = False
            if self._pre_move_snapshot is not None and self._move_orig_ann is not None:
                if self._selected_index is not None and 0 <= self._selected_index < len(self._annotations):
                    ann = self._annotations[self._selected_index]
                    orig = self._move_orig_ann
                    if self._annotation_moved(ann, orig):
                        self._undo_stack.append(self._pre_move_snapshot)
                        self._redo_stack.clear()
            self._pre_move_snapshot = None
            self._move_orig_ann = None
            self._drawing_area.queue_draw()
            return

        if self._pan_dragging:
            self._pan_dragging = False
            self._pan_drag_start = None
            self._pan_start_values = None
            return

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
            self._set_select_tool()
            self._drawing_area.queue_draw()

    def _on_mid_pan_begin(self, _gesture, start_x: float, start_y: float) -> None:
        self._pan_drag_start = (start_x, start_y)
        self._pan_start_values = (self._pan_x, self._pan_y)

    def _on_mid_pan_update(self, _gesture, offset_x: float, offset_y: float) -> None:
        self._update_pan(offset_x, offset_y)

    def _on_mid_pan_end(self, _gesture, offset_x: float, offset_y: float) -> None:
        self._on_mid_pan_update(_gesture, offset_x, offset_y)
        self._pan_drag_start = None
        self._pan_start_values = None

    def _on_click_released(self, _gesture, n_press: int, x: float, y: float) -> None:
        if n_press not in (1, 2):
            return

        ix, iy = self._widget_to_image(x, y)

        if self._current_tool == "select":
            hit = self._find_hit(ix, iy)
            if n_press == 2 and hit is not None and self._annotations[hit]["kind"] == "text":
                self._selected_index = hit
                self._show_text_popover(x, y, ix, iy, hit)
                self._drawing_area.queue_draw()
                return
            self._selected_index = hit
            self._drawing_area.queue_draw()
            return

        if n_press == 1 and self._current_tool == "text" and not self._dragging:
            self._show_text_popover(x, y, ix, iy)

    def _show_text_popover(
        self,
        wx: float,
        wy: float,
        ix: float,
        iy: float,
        annotation_index: int | None = None,
    ) -> None:
        popover = Gtk.Popover()
        entry = Gtk.Entry()
        entry.set_placeholder_text("Type text…")

        if annotation_index is not None:
            existing_text = self._annotations[annotation_index].get("text", "")
            entry.set_text(existing_text)

        def on_activate(_entry):
            text = entry.get_text().strip()
            if text:
                self._push_undo()
                if annotation_index is not None:
                    self._annotations[annotation_index]["text"] = text
                else:
                    self._annotations.append(_make_text_annotation(text, (ix, iy), self._current_color))
                    self._set_select_tool()
                self._drawing_area.queue_draw()
            popover.popdown()

        entry.connect("activate", on_activate)
        popover.set_child(entry)
        popover.set_parent(self._drawing_area)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(wx), int(wy), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

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

        key_c = getattr(Gdk, "KEY_c", None)
        key_C = getattr(Gdk, "KEY_C", None)
        if ctrl and keyval in (key_c, key_C):
            self._copy_to_clipboard()
            return True

        return False

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

    def _on_zoom_in(self, _btn) -> None:
        self._zoom = min(4.0, self._zoom * 1.25)
        self._drawing_area.queue_draw()

    def _on_zoom_out(self, _btn) -> None:
        self._zoom = max(0.25, self._zoom / 1.25)
        self._drawing_area.queue_draw()

    def _do_save(self) -> None:
        try:
            output = self._render_output_surface()
            dest = self._build_output_path(self._source_uri)
            _write_surface_png_securely(output, dest)
            self._on_save(dest)
        except Exception as err:
            self._on_error(f"could not save image ({err})")
