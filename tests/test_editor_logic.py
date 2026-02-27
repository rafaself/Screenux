import io
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import screenux_editor as editor


class DrawArea:
    def __init__(self):
        self.draw_calls = 0
        self.controllers = []
        self.focused = False

    def queue_draw(self):
        self.draw_calls += 1

    def add_controller(self, ctrl):
        self.controllers.append(ctrl)

    def set_vexpand(self, *_):
        pass

    def set_hexpand(self, *_):
        pass

    def set_content_width(self, *_):
        pass

    def set_content_height(self, *_):
        pass

    def set_draw_func(self, *_):
        pass

    def set_focusable(self, *_):
        pass

    def set_can_focus(self, *_):
        pass

    def grab_focus(self):
        self.focused = True


class FakeSurface:
    def __init__(self, w=200, h=100):
        self.w = w
        self.h = h

    def get_width(self):
        return self.w

    def get_height(self):
        return self.h


class FakeCr:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def _fn(*args):
            self.calls.append((name, args))

        return _fn


class DummyRGBA:
    def __init__(self, r=1, g=0, b=0, a=1):
        self.red = r
        self.green = g
        self.blue = b
        self.alpha = a


class DummyColorButton:
    def __init__(self, rgba=None):
        self._rgba = rgba or DummyRGBA()

    def get_rgba(self):
        return self._rgba


class DummyToggle:
    def __init__(self, active):
        self._active = active

    def get_active(self):
        return self._active


class FakeEditorSelf:
    def __init__(self):
        self._annotations = []
        self._undo_stack = []
        self._redo_stack = []
        self._selected_index = None
        self._drawing_area = DrawArea()
        self._current_tool = "rectangle"
        self._current_color = (1, 0, 0, 1)
        self._dragging = False
        self._drag_start = None
        self._drag_end = None
        self._widget_drag_start = None
        self._move_dragging = False
        self._move_drag_start_img = None
        self._move_orig_ann = None
        self._pre_move_snapshot = None
        self._pan_dragging = False
        self._pan_drag_start = None
        self._pan_start_values = None
        self._base_scale = 1.0
        self._zoom = 1.0
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._surface = FakeSurface()
        self._source_uri = "file:///tmp/source.png"
        self._build_output_path = lambda _uri: Path("/tmp/out.png")
        self.saved = None
        self.error = None
        self._on_save = lambda p: setattr(self, "saved", p)
        self._on_error = lambda msg: setattr(self, "error", msg)
        self._on_discard = lambda: None
        self._push_undo = lambda: editor.AnnotationEditor._push_undo(self)
        self._update_viewport = lambda w, h: editor.AnnotationEditor._update_viewport(self, w, h)
        self._widget_to_image = lambda wx, wy: editor.AnnotationEditor._widget_to_image(self, wx, wy)
        self._annotation_moved = lambda current, original: editor.AnnotationEditor._annotation_moved(self, current, original)
        self._update_pan = lambda ox, oy: editor.AnnotationEditor._update_pan(self, ox, oy)
        self._start_move = lambda hit_index, ix, iy, wx, wy: editor.AnnotationEditor._start_move(self, hit_index, ix, iy, wx, wy)
        self._start_pan = lambda wx, wy: editor.AnnotationEditor._start_pan(self, wx, wy)
        self._on_mid_pan_update = lambda gesture, offset_x, offset_y: editor.AnnotationEditor._on_mid_pan_update(self, gesture, offset_x, offset_y)
        self._set_select_tool = lambda: editor.AnnotationEditor._set_select_tool(self)
        self._render_output_surface = lambda: editor.AnnotationEditor._render_output_surface(self)
        self._update_draw_cursor = lambda: None

    def append(self, *_):
        pass


def test_load_image_surface_paths(monkeypatch):
    marker = object()

    class ImgSurface:
        @staticmethod
        def create_from_png(path_or_bytes):
            if path_or_bytes == "raise":
                raise RuntimeError("x")
            return marker

    class Pixbuf:
        @staticmethod
        def new_from_file(_):
            return SimpleNamespace(save_to_bufferv=lambda *_: (True, b"123"))

    monkeypatch.setattr(editor, "cairo", SimpleNamespace(ImageSurface=ImgSurface))
    monkeypatch.setattr(editor, "GdkPixbuf", SimpleNamespace(Pixbuf=Pixbuf))

    assert editor.load_image_surface("ok") is marker
    assert editor.load_image_surface("raise") is marker

    class PixbufFail:
        @staticmethod
        def new_from_file(_):
            return SimpleNamespace(save_to_bufferv=lambda *_: (False, b""))

    monkeypatch.setattr(editor, "GdkPixbuf", SimpleNamespace(Pixbuf=PixbufFail))
    try:
        editor.load_image_surface("raise")
        assert False
    except RuntimeError as err:
        assert "failed to convert image" in str(err)


def test_annotation_helpers_and_renderers():
    ann_text = {"kind": "text", "x1": 2, "y1": 10, "x2": 2, "y2": 10, "text": "hi", "color": (1, 0, 0, 1)}
    ann_rect = {"kind": "rectangle", "x1": 10, "y1": 20, "x2": 2, "y2": 5, "color": (1, 0, 0, 1)}

    assert editor._annotation_bbox(ann_text) == (2, -14, 30, 14)
    assert editor._annotation_bbox(ann_rect) == (2, 5, 10, 20)
    assert editor._hit_test(ann_rect, 4, 7)
    assert not editor._hit_test(ann_rect, -100, -100)

    cr = FakeCr()
    editor._render_annotation(cr, ann_rect)
    assert any(name == "rectangle" for name, _ in cr.calls)

    cr2 = FakeCr()
    circle = {"kind": "circle", "x1": 0, "y1": 0, "x2": 8, "y2": 6, "color": (1, 0, 0, 1)}
    editor._render_annotation(cr2, circle)
    assert any(name == "arc" for name, _ in cr2.calls)

    cr3 = FakeCr()
    circle_zero = {"kind": "circle", "x1": 0, "y1": 0, "x2": 0, "y2": 6, "color": (1, 0, 0, 1)}
    editor._render_annotation(cr3, circle_zero)
    assert not any(name == "arc" for name, _ in cr3.calls)

    cr4 = FakeCr()
    editor._render_annotation(cr4, ann_text)
    assert any(name == "show_text" for name, _ in cr4.calls)

    cr5 = FakeCr()
    editor._render_selection_indicator(cr5, ann_rect)
    assert sum(1 for name, _ in cr5.calls if name == "rectangle") >= 5

    copied = editor._deep_copy_annotations([ann_rect])
    copied[0]["x1"] = 999
    assert ann_rect["x1"] != 999

    shape = editor._make_shape_annotation("rectangle", (1, 2), (3, 4), (1, 1, 1, 1))
    assert shape["kind"] == "rectangle"
    text = editor._make_text_annotation("hello", (9, 8), (1, 1, 1, 1))
    assert text["kind"] == "text" and text["text"] == "hello"


def test_editor_core_methods(monkeypatch):
    self = FakeEditorSelf()

    self._annotations = [{"kind": "rectangle", "x1": 1, "y1": 1, "x2": 2, "y2": 2, "color": (1, 0, 0, 1)}]
    editor.AnnotationEditor._push_undo(self)
    assert len(self._undo_stack) == 1

    editor.AnnotationEditor._on_undo(self)
    assert self._selected_index is None
    assert self._drawing_area.draw_calls >= 1

    editor.AnnotationEditor._on_redo(self)
    assert self._selected_index is None

    editor.AnnotationEditor._on_tool_toggled(self, DummyToggle(True), "select")
    assert self._current_tool == "select"

    editor.AnnotationEditor._on_tool_toggled(self, DummyToggle(False), "rectangle")

    editor.AnnotationEditor._on_color_changed(self, DummyColorButton(DummyRGBA(0.2, 0.3, 0.4, 0.5)), None)
    assert self._current_color == (0.2, 0.3, 0.4, 0.5)

    self._scale = 0
    assert editor.AnnotationEditor._widget_to_image(self, 5, 6) == (5, 6)
    self._scale = 2
    self._offset_x = 1
    self._offset_y = 3
    assert editor.AnnotationEditor._widget_to_image(self, 5, 7) == (2, 2)

    self._surface = FakeSurface(0, 10)
    editor.AnnotationEditor._update_viewport(self, 100, 100)
    self._surface = FakeSurface(200, 100)
    editor.AnnotationEditor._update_viewport(self, 100, 50)
    assert self._scale > 0

    self._annotations = [
        {"kind": "rectangle", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "color": (1, 0, 0, 1)},
        {"kind": "rectangle", "x1": 5, "y1": 5, "x2": 10, "y2": 10, "color": (1, 0, 0, 1)},
    ]
    assert editor.AnnotationEditor._find_hit(self, 6, 6) == 1
    assert editor.AnnotationEditor._find_hit(self, -100, -100) is None

    editor.AnnotationEditor._start_move(self, 0, 1, 2, 11, 12)
    assert self._move_dragging is True and self._selected_index == 0

    editor.AnnotationEditor._start_pan(self, 3, 4)
    assert self._pan_dragging is True

    self._pan_start_values = None
    editor.AnnotationEditor._update_pan(self, 3, 4)
    self._pan_start_values = (1, 1)
    self._scale = 2
    editor.AnnotationEditor._update_pan(self, 4, 2)

    ann_a = {"x1": 1, "y1": 1, "x2": 2, "y2": 2}
    ann_b = {"x1": 1, "y1": 1, "x2": 2, "y2": 3}
    assert editor.AnnotationEditor._annotation_moved(self, ann_a, ann_b)


def test_editor_draw_drag_click_and_keys(monkeypatch):
    self = FakeEditorSelf()
    self._surface = FakeSurface(100, 100)
    self._annotations = [{"kind": "rectangle", "x1": 1, "y1": 1, "x2": 6, "y2": 6, "color": (1, 0, 0, 1)}]
    self._selected_index = 0
    self._dragging = True
    self._drag_start = (1, 1)
    self._drag_end = (2, 2)
    self._current_tool = "rectangle"

    cr = FakeCr()
    editor.AnnotationEditor._on_draw(self, None, cr, 50, 50)
    assert len(cr.calls) > 0

    # drag begin select hit and pan
    self._current_tool = "select"
    self._find_hit = lambda *_: 0
    editor.AnnotationEditor._on_drag_begin(self, None, 10, 10)
    self._find_hit = lambda *_: None
    editor.AnnotationEditor._on_drag_begin(self, None, 20, 20)

    # drag begin shape
    self._current_tool = "rectangle"
    editor.AnnotationEditor._on_drag_begin(self, None, 5, 5)
    assert self._dragging is True

    # update move
    self._selected_index = 0
    self._move_dragging = True
    self._widget_drag_start = (0, 0)
    self._move_drag_start_img = (0, 0)
    self._move_orig_ann = dict(self._annotations[0])
    editor.AnnotationEditor._on_drag_update(self, None, 3, 3)

    # update pan
    self._move_dragging = False
    self._pan_dragging = True
    self._pan_start_values = (0, 0)
    editor.AnnotationEditor._on_drag_update(self, None, 1, 1)

    # update drawing
    self._pan_dragging = False
    self._dragging = True
    self._widget_drag_start = (0, 0)
    editor.AnnotationEditor._on_drag_update(self, None, 4, 4)

    # drag end move changed + unchanged path
    self._move_dragging = True
    self._selected_index = 0
    self._pre_move_snapshot = []
    self._move_orig_ann = {"x1": 0, "y1": 0, "x2": 1, "y2": 1}
    self._annotations[0] = {"x1": 0, "y1": 0, "x2": 2, "y2": 1}
    editor.AnnotationEditor._on_drag_end(self, None, 0, 0)

    self._move_dragging = True
    self._pre_move_snapshot = []
    self._move_orig_ann = {"x1": 0, "y1": 0, "x2": 1, "y2": 1}
    self._annotations[0] = {"x1": 0, "y1": 0, "x2": 1, "y2": 1}
    editor.AnnotationEditor._on_drag_end(self, None, 0, 0)

    # drag end pan
    self._pan_dragging = True
    self._pan_start_values = (0, 0)
    editor.AnnotationEditor._on_drag_end(self, None, 0, 0)

    # drag end shape add annotation
    self._dragging = True
    self._widget_drag_start = (0, 0)
    self._drag_start = (1, 1)
    self._current_tool = "circle"
    self._undo_stack = []
    editor.AnnotationEditor._on_drag_end(self, None, 2, 2)
    assert self._annotations[-1]["kind"] == "circle"

    # mid pan
    editor.AnnotationEditor._on_mid_pan_begin(self, None, 1, 2)
    editor.AnnotationEditor._on_mid_pan_update(self, None, 3, 4)
    editor.AnnotationEditor._on_mid_pan_end(self, None, 5, 6)

    # click paths
    editor.AnnotationEditor._on_click_released(self, None, 2, 1, 1)
    self._current_tool = "select"
    self._find_hit = lambda *_: 0
    editor.AnnotationEditor._on_click_released(self, None, 1, 1, 1)
    self._current_tool = "text"
    called = {"popover": 0}
    self._show_text_popover = lambda *_: called.__setitem__("popover", called["popover"] + 1)
    self._dragging = False
    editor.AnnotationEditor._on_click_released(self, None, 1, 1, 1)
    assert called["popover"] == 1

    # key handling
    key = SimpleNamespace(ModifierType=SimpleNamespace(CONTROL_MASK=1, SHIFT_MASK=2), KEY_Delete=10, KEY_BackSpace=11, KEY_z=12, KEY_Z=13)
    monkeypatch.setattr(editor, "Gdk", key)

    self._annotations = [{"kind": "rectangle", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "color": (1, 0, 0, 1)}]
    self._selected_index = 0
    assert editor.AnnotationEditor._on_key_pressed(self, None, 10, 0, 0) is True

    self._on_redo = lambda *_: setattr(self, "redo", True)
    self._on_undo = lambda *_: setattr(self, "undo", True)
    assert editor.AnnotationEditor._on_key_pressed(self, None, 12, 0, 1) is True
    assert editor.AnnotationEditor._on_key_pressed(self, None, 12, 0, 3) is True
    assert editor.AnnotationEditor._on_key_pressed(self, None, 13, 0, 1) is True
    assert editor.AnnotationEditor._on_key_pressed(self, None, 99, 0, 0) is False


def test_editor_popover_scroll_zoom_save(monkeypatch):
    self = FakeEditorSelf()

    class DummyEntry:
        def __init__(self):
            self.callback = None

        def set_placeholder_text(self, *_):
            pass

        def connect(self, _signal, cb):
            self.callback = cb

        def get_text(self):
            return " hello "

    class DummyPopover:
        def __init__(self):
            self.popped = False

        def set_child(self, *_):
            pass

        def set_parent(self, *_):
            pass

        def set_pointing_to(self, *_):
            pass

        def popup(self):
            pass

        def popdown(self):
            self.popped = True

    class DummyRect:
        x = y = width = height = 0

    entry = DummyEntry()
    popover = DummyPopover()

    fake_gtk = SimpleNamespace(Ppopover=None, Popover=lambda: popover, Entry=lambda: entry)
    fake_gdk = SimpleNamespace(Rectangle=DummyRect)
    monkeypatch.setattr(editor, "Gtk", fake_gtk)
    monkeypatch.setattr(editor, "Gdk", fake_gdk)

    editor.AnnotationEditor._show_text_popover(self, 5, 6, 7, 8)
    entry.callback(None)
    assert self._annotations[-1]["kind"] == "text"
    assert popover.popped is True

    # scroll paths
    key = SimpleNamespace(ModifierType=SimpleNamespace(CONTROL_MASK=1, SHIFT_MASK=2))
    monkeypatch.setattr(editor, "Gdk", key)

    ctrl = SimpleNamespace(get_current_event_state=lambda: 1)
    editor.AnnotationEditor._on_scroll(self, ctrl, 0, -1)

    ctrl_shift = SimpleNamespace(get_current_event_state=lambda: 2)
    self._scale = 2
    editor.AnnotationEditor._on_scroll(self, ctrl_shift, 0, 1)

    ctrl_none = SimpleNamespace(get_current_event_state=lambda: 0)
    editor.AnnotationEditor._on_scroll(self, ctrl_none, 0, 1)

    # zoom
    self._zoom = 3.9
    editor.AnnotationEditor._on_zoom_in(self, None)
    self._zoom = 0.2
    editor.AnnotationEditor._on_zoom_out(self, None)

    # save
    rendered = []

    class OutSurface:
        def __init__(self, *_):
            pass

        def write_to_png(self, path):
            rendered.append(path)

    class Ctx:
        def __init__(self, _surface):
            pass

        def set_source_surface(self, *_):
            pass

        def paint(self):
            pass

    monkeypatch.setattr(editor, "cairo", SimpleNamespace(FORMAT_ARGB32=0, ImageSurface=OutSurface, Context=Ctx))
    monkeypatch.setattr(editor, "_render_annotation", lambda *_: None)

    self._annotations = [{"kind": "rectangle", "x1": 0, "y1": 0, "x2": 1, "y2": 1, "color": (1, 0, 0, 1)}]
    editor.AnnotationEditor._do_save(self)
    assert rendered and self.saved == Path("/tmp/out.png")


def test_editor_drag_end_ignores_invalid_selected_index():
    self = FakeEditorSelf()
    self._move_dragging = True
    self._selected_index = 3
    self._annotations = [{"x1": 0, "y1": 0, "x2": 1, "y2": 1}]
    self._pre_move_snapshot = []
    self._move_orig_ann = {"x1": 0, "y1": 0, "x2": 1, "y2": 1}

    editor.AnnotationEditor._on_drag_end(self, None, 0, 0)
    assert self._move_dragging is False


def test_editor_save_failure_reports_error(monkeypatch):
    self = FakeEditorSelf()

    class OutSurface:
        def write_to_png(self, _path):
            raise OSError("disk full")

    self._render_output_surface = lambda: OutSurface()
    editor.AnnotationEditor._do_save(self)

    assert self.error == "could not save image (disk full)"
