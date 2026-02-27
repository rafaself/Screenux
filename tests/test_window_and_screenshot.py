import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import screenux_screenshot as screenshot
import screenux_window as window


class DummyLabel:
    def __init__(self):
        self.text = ""

    def set_text(self, text):
        self.text = text


class DummyButton:
    def __init__(self):
        self.sensitive = True

    def set_sensitive(self, value):
        self.sensitive = value


class DummyEntry:
    def __init__(self, text=""):
        self.text = text

    def get_text(self):
        return self.text

    def set_text(self, text):
        self.text = text

    def set_position(self, _position):
        return None


class DummyHotkeyManager:
    def __init__(self):
        self.last_applied = None

    def apply_shortcut(self, value):
        self.last_applied = value
        return SimpleNamespace(shortcut=value, warning=None)


class DummyBus:
    def __init__(self, unique_name=":1.23"):
        self.unique_name = unique_name
        self.unsubscribe_calls = []
        self.subscriptions = []
        self.call_return_path = "/org/freedesktop/portal/desktop/request/abc/expected"

    def get_unique_name(self):
        return self.unique_name

    def signal_unsubscribe(self, sid):
        self.unsubscribe_calls.append(sid)

    def signal_subscribe(self, *_args):
        self.subscriptions.append(_args)
        return len(self.subscriptions)

    def call_sync(self, *_args):
        return SimpleNamespace(unpack=lambda: (self.call_return_path,))


class DummyVariant:
    def __init__(self, _sig, value):
        self.value = value

    def unpack(self):
        return self.value


class FakeWindowSelf:
    def __init__(self):
        self._request_counter = 0
        self._bus = None
        self._signal_sub_id = None
        self._present_after_capture = False
        self._present_calls = 0
        self._button = DummyButton()
        self._status_label = DummyLabel()
        self._main_box = object()
        self._set_child_value = None
        self._load_config = lambda: {}
        self._save_config = lambda _config: None
        self._resolve_save_dir = lambda: Path("/tmp")
        self._build_output_path = lambda _uri: Path("/tmp/out.png")
        self._format_status_saved = lambda p: f"Saved: {p}"
        self._set_status = lambda text: window.MainWindow._set_status(self, text)
        self._unsubscribe_signal = lambda: window.MainWindow._unsubscribe_signal(self)
        self._finish = lambda status: window.MainWindow._finish(self, status)
        self._fail = lambda reason: window.MainWindow._fail(self, reason)
        self._show_main_panel = lambda: window.MainWindow._show_main_panel(self)
        self._build_handle_token = lambda: window.MainWindow._build_handle_token(self)
        self._on_portal_response = (
            lambda connection, sender_name, object_path, interface_name, signal_name, parameters: window.MainWindow._on_portal_response(
                self,
                connection,
                sender_name,
                object_path,
                interface_name,
                signal_name,
                parameters,
            )
        )
        self._on_editor_save = lambda saved_path: window.MainWindow._on_editor_save(self, saved_path)
        self._on_editor_discard = lambda: window.MainWindow._on_editor_discard(self)
        self._on_editor_error = lambda message: window.MainWindow._on_editor_error(self, message)

    def set_child(self, child):
        self._set_child_value = child

    def present(self):
        self._present_calls += 1


def test_window_take_screenshot_public_method():
    self = FakeWindowSelf()
    called = []
    self._on_take_screenshot = lambda button: called.append(button)

    window.MainWindow.take_screenshot(self)

    assert called == [self._button]


def test_window_trigger_shortcut_capture_sets_deferred_presentation_flag():
    self = FakeWindowSelf()
    calls = []
    self.take_screenshot = lambda: calls.append("capture")

    window.MainWindow.trigger_shortcut_capture(self)

    assert calls == ["capture"]
    assert self._present_after_capture is True


def test_window_finish_presents_when_shortcut_capture_is_deferred():
    self = FakeWindowSelf()
    self._present_after_capture = True

    window.MainWindow._finish(self, "Done")

    assert self._present_calls == 1
    assert self._present_after_capture is False


def test_window_hotkey_apply_accepts_printscreen_alias():
    manager = DummyHotkeyManager()
    self = SimpleNamespace(
        _hotkey_manager=manager,
        _hotkey_entry=DummyEntry("ctrl+print screen"),
        _set_status=lambda text: setattr(self, "_status_text", text),
        _apply_hotkey_result=lambda result: setattr(self, "_applied_result", result),
    )
    self._status_text = ""
    self._applied_result = None

    window.MainWindow._on_hotkey_apply(self, None)

    assert manager.last_applied == "ctrl+print screen"
    assert self._applied_result is not None
    assert self._applied_result.shortcut == "ctrl+print screen"


def test_window_hotkey_apply_rejects_empty_and_mentions_clear():
    manager = DummyHotkeyManager()
    self = SimpleNamespace(
        _hotkey_manager=manager,
        _hotkey_entry=DummyEntry(""),
        _set_status=lambda text: setattr(self, "_status_text", text),
        _apply_hotkey_result=lambda result: setattr(self, "_applied_result", result),
    )
    self._status_text = ""
    self._applied_result = None

    window.MainWindow._on_hotkey_apply(self, None)

    assert "use Clear" in self._status_text
    assert self._applied_result is None


def test_window_hotkey_restore_default():
    manager = DummyHotkeyManager()
    self = SimpleNamespace(
        _hotkey_manager=manager,
        _apply_hotkey_result=lambda result: setattr(self, "_applied_result", result),
    )
    self._applied_result = None

    window.MainWindow._on_hotkey_restore_default(self, None)

    assert manager.last_applied == "Ctrl+Print"
    assert self._applied_result is not None
    assert self._applied_result.shortcut == "Ctrl+Print"


def test_window_hotkey_entry_activate_triggers_apply():
    calls = []
    self = SimpleNamespace(
        _on_hotkey_apply=lambda button: calls.append(button),
    )

    window.MainWindow._on_hotkey_entry_activate(self, "entry")

    assert calls == ["entry"]


def test_window_hotkey_capture_builds_shortcut_from_key_event(monkeypatch):
    fake_gdk = SimpleNamespace(
        ModifierType=SimpleNamespace(
            CONTROL_MASK=1,
            ALT_MASK=2,
            SHIFT_MASK=4,
            SUPER_MASK=8,
        ),
        KEY_Control_L=1000,
        KEY_Control_R=1001,
        KEY_Shift_L=1002,
        KEY_Shift_R=1003,
        KEY_Alt_L=1004,
        KEY_Alt_R=1005,
        KEY_Super_L=1006,
        KEY_Super_R=1007,
        KEY_Meta_L=1008,
        KEY_Meta_R=1009,
        KEY_ISO_Left_Tab=1010,
        KEY_Return=1011,
        KEY_KP_Enter=1012,
        keyval_name=lambda keyval: {115: "s", 1111: "Print", 1112: "F5"}.get(keyval),
    )
    monkeypatch.setattr(window, "Gdk", fake_gdk)

    self = SimpleNamespace(
        _hotkey_entry=DummyEntry(""),
        _set_status=lambda text: setattr(self, "_status_text", text),
    )
    self._status_text = ""

    consumed = window.MainWindow._on_hotkey_entry_key_pressed(
        self,
        None,
        115,
        0,
        fake_gdk.ModifierType.CONTROL_MASK | fake_gdk.ModifierType.SHIFT_MASK,
    )
    assert consumed is True
    assert self._hotkey_entry.text == "Ctrl + Shift + S"

    consumed_modifier = window.MainWindow._on_hotkey_entry_key_pressed(
        self,
        None,
        fake_gdk.KEY_Control_L,
        0,
        fake_gdk.ModifierType.CONTROL_MASK,
    )
    assert consumed_modifier is True
    assert self._hotkey_entry.text == "Ctrl + Shift + S"


def test_window_hotkey_capture_ignores_unmapped_key(monkeypatch):
    fake_gdk = SimpleNamespace(
        ModifierType=SimpleNamespace(
            CONTROL_MASK=1,
            ALT_MASK=2,
            SHIFT_MASK=4,
            SUPER_MASK=8,
        ),
        KEY_Control_L=1000,
        KEY_Control_R=1001,
        KEY_Shift_L=1002,
        KEY_Shift_R=1003,
        KEY_Alt_L=1004,
        KEY_Alt_R=1005,
        KEY_Super_L=1006,
        KEY_Super_R=1007,
        KEY_Meta_L=1008,
        KEY_Meta_R=1009,
        KEY_ISO_Left_Tab=1010,
        KEY_Return=1011,
        KEY_KP_Enter=1012,
        keyval_name=lambda _keyval: None,
    )
    monkeypatch.setattr(window, "Gdk", fake_gdk)

    self = SimpleNamespace(
        _hotkey_entry=DummyEntry("Ctrl + S"),
        _set_status=lambda text: setattr(self, "_status_text", text),
    )
    self._status_text = ""

    consumed = window.MainWindow._on_hotkey_entry_key_pressed(
        self,
        None,
        61,
        0,
        0,
    )
    assert consumed is True
    assert self._hotkey_entry.text == "Ctrl + S"
    assert self._status_text == ""


class DummyError(Exception):
    def __init__(self, message):
        self.message = message


def test_window_top_level_helpers():
    assert window._normalize_bus_name(":1.90") == "1_90"
    assert window._extract_uri(None) is None
    assert window._extract_uri({}) is None
    assert window._extract_uri({"uri": ""}) is None

    wrapped = SimpleNamespace(unpack=lambda: "file:///tmp/x.png")
    assert window._extract_uri({"uri": wrapped}) == "file:///tmp/x.png"
    assert window._extract_uri({"uri": "file:///tmp/y.png"}) == "file:///tmp/y.png"


def test_window_initial_size_and_center_helpers():
    width, height = window._initial_window_size()
    assert width >= 480
    assert height >= 180

    x, y = window._center_position(
        monitor_x=100,
        monitor_y=50,
        monitor_width=1920,
        monitor_height=1080,
        window_width=width,
        window_height=height,
    )
    assert x == 100 + (1920 - width) // 2
    assert y == 50 + (1080 - height) // 2


def test_window_uri_to_local_path(tmp_path):
    local = tmp_path / "cap.png"
    local.write_bytes(b"x")

    assert window._uri_to_local_path(f"file://{local}") == local.resolve()
    assert window._uri_to_local_path("https://example.com/cap.png") is None
    assert window._uri_to_local_path("file://remotehost/tmp/cap.png") is None
    assert window._uri_to_local_path("file:///does/not/exist.png") is None


def test_window_status_unsubscribe_finish_fail():
    self = FakeWindowSelf()
    self._bus = DummyBus()
    self._signal_sub_id = 7

    window.MainWindow._set_status(self, "OK")
    assert self._status_label.text == "OK"

    window.MainWindow._unsubscribe_signal(self)
    assert self._bus.unsubscribe_calls == [7]
    assert self._signal_sub_id is None

    self._signal_sub_id = 1
    window.MainWindow._finish(self, "Done")
    assert self._button.sensitive is True
    assert self._status_label.text == "Done"

    self._signal_sub_id = None
    window.MainWindow._fail(self, "broken")
    assert self._status_label.text == "Failed: broken"


def test_window_build_handle_token(monkeypatch):
    self = FakeWindowSelf()
    monkeypatch.setattr(window.os, "getpid", lambda: 999)
    monkeypatch.setattr(window.time, "time", lambda: 1234.567)
    token = window.MainWindow._build_handle_token(self)
    assert token == "screenux_999_1_1234567"


def test_window_show_panel_and_editor_callbacks():
    self = FakeWindowSelf()
    window.MainWindow._show_main_panel(self)
    assert self._set_child_value is self._main_box

    window.MainWindow._on_editor_save(self, Path("/tmp/a.png"))
    assert self._set_child_value is self._main_box
    assert self._button.sensitive is True
    assert self._status_label.text == "Saved: /tmp/a.png"

    window.MainWindow._on_editor_discard(self)
    assert self._status_label.text == "Ready"

    window.MainWindow._on_editor_error(self, "save broke")
    assert self._set_child_value is self._main_box
    assert self._button.sensitive is True
    assert self._status_label.text == "Failed: save broke"


def test_window_take_screenshot_success_and_resubscribe(monkeypatch):
    self = FakeWindowSelf()
    bus = DummyBus()
    self._bus = bus

    expected_token = "tok"
    request_path = "/org/freedesktop/portal/desktop/request/1_23/tok"
    bus.call_return_path = request_path + "_different"

    monkeypatch.setattr(window.MainWindow, "_build_handle_token", lambda _self: expected_token)

    fake_gio = SimpleNamespace(
        BusType=SimpleNamespace(SESSION=1),
        DBusSignalFlags=SimpleNamespace(NONE=0),
        DBusCallFlags=SimpleNamespace(NONE=0),
        bus_get_sync=lambda *_args: bus,
    )
    fake_glib = SimpleNamespace(
        Variant=DummyVariant,
        VariantType=lambda s: s,
        Error=DummyError,
    )
    monkeypatch.setattr(window, "Gio", fake_gio)
    monkeypatch.setattr(window, "GLib", fake_glib)

    window.MainWindow._on_take_screenshot(self, None)

    assert self._button.sensitive is False
    assert self._status_label.text == "Capturing..."
    assert len(bus.subscriptions) == 2
    assert self._signal_sub_id == 2


def test_window_take_screenshot_failures(monkeypatch):
    self = FakeWindowSelf()

    class ErrBus:
        def get_unique_name(self):
            return None

    fake_gio = SimpleNamespace(
        BusType=SimpleNamespace(SESSION=1),
        DBusSignalFlags=SimpleNamespace(NONE=0),
        DBusCallFlags=SimpleNamespace(NONE=0),
        bus_get_sync=lambda *_args: ErrBus(),
    )
    fake_glib = SimpleNamespace(
        Variant=DummyVariant,
        VariantType=lambda s: s,
        Error=DummyError,
    )
    monkeypatch.setattr(window, "Gio", fake_gio)
    monkeypatch.setattr(window, "GLib", fake_glib)

    window.MainWindow._on_take_screenshot(self, None)
    assert "Failed:" in self._status_label.text

    def raise_glib(*_args):
        raise DummyError("portal down")

    fake_gio_2 = SimpleNamespace(
        BusType=SimpleNamespace(SESSION=1),
        DBusSignalFlags=SimpleNamespace(NONE=0),
        DBusCallFlags=SimpleNamespace(NONE=0),
        bus_get_sync=raise_glib,
    )
    monkeypatch.setattr(window, "Gio", fake_gio_2)
    window.MainWindow._on_take_screenshot(self, None)
    assert self._status_label.text == "Failed: portal unavailable (portal down)"


def test_window_save_uri_success_and_failure(monkeypatch):
    self = FakeWindowSelf()
    self._bus = DummyBus()
    self._signal_sub_id = 3

    marker = object()
    monkeypatch.setattr(window, "_uri_to_local_path", lambda _uri: Path("/tmp/test x.png"))
    monkeypatch.setattr(window, "load_image_surface", lambda _p: marker)
    monkeypatch.setattr(
        window,
        "AnnotationEditor",
        lambda *args, **kwargs: {"args": args, "kwargs": kwargs},
    )

    window.MainWindow._save_uri(self, "file:///tmp/test%20x.png")
    assert isinstance(self._set_child_value, dict)
    assert self._bus.unsubscribe_calls == [3]

    self._signal_sub_id = None

    def broken(_p):
        raise RuntimeError("bad image")

    monkeypatch.setattr(window, "load_image_surface", broken)
    window.MainWindow._save_uri(self, "file:///tmp/xx.png")
    assert self._status_label.text.startswith("Failed: could not load image")


def test_window_save_uri_rejects_invalid_source(monkeypatch):
    self = FakeWindowSelf()
    self._bus = DummyBus()
    self._signal_sub_id = 3

    monkeypatch.setattr(window, "_uri_to_local_path", lambda _uri: None)
    window.MainWindow._save_uri(self, "https://example.com/cap.png")
    assert self._status_label.text == "Failed: invalid screenshot source path"


def test_window_folder_selected(monkeypatch, tmp_path):
    self = FakeWindowSelf()
    saved = {}
    self._load_config = lambda: {"foo": "bar"}
    self._save_config = lambda cfg: saved.update(cfg)
    self._folder_label = DummyLabel()

    chosen_dir = tmp_path / "screens"
    chosen_dir.mkdir()
    fake_folder = SimpleNamespace(get_path=lambda: str(chosen_dir))
    fake_dialog = SimpleNamespace(select_folder_finish=lambda _r: fake_folder)

    fake_glib = SimpleNamespace(Error=DummyError)
    monkeypatch.setattr(window, "GLib", fake_glib)

    window.MainWindow._on_folder_selected(self, fake_dialog, object())
    assert saved["save_dir"] == str(chosen_dir)
    assert self._folder_label.text == str(chosen_dir)

    class RaiseDialog:
        def select_folder_finish(self, _r):
            raise DummyError("cancel")

    window.MainWindow._on_folder_selected(self, RaiseDialog(), object())
    assert self._status_label.text == "Failed: could not change folder (cancel)"


def test_window_folder_selected_rejects_non_local_and_unwritable(monkeypatch, tmp_path):
    self = FakeWindowSelf()
    self._folder_label = DummyLabel()

    fake_glib = SimpleNamespace(Error=DummyError)
    monkeypatch.setattr(window, "GLib", fake_glib)

    non_local_dialog = SimpleNamespace(
        select_folder_finish=lambda _r: SimpleNamespace(get_path=lambda: None)
    )
    window.MainWindow._on_folder_selected(self, non_local_dialog, object())
    assert self._status_label.text == "Failed: selected folder is not local"

    unwritable = tmp_path / "screens"
    unwritable.mkdir()
    monkeypatch.setattr(window.os, "access", lambda *_args: False)
    unwritable_dialog = SimpleNamespace(
        select_folder_finish=lambda _r: SimpleNamespace(get_path=lambda: str(unwritable))
    )
    window.MainWindow._on_folder_selected(self, unwritable_dialog, object())
    assert self._status_label.text == "Failed: selected folder is not writable"


def test_window_portal_response_paths(monkeypatch):
    self = FakeWindowSelf()
    calls = {"save": 0, "finish": [], "fail": []}
    self._save_uri = lambda _uri: calls.__setitem__("save", calls["save"] + 1)
    self._finish = lambda text: calls["finish"].append(text)
    self._fail = lambda text: calls["fail"].append(text)

    window.MainWindow._on_portal_response(
        self,
        None,
        "",
        "",
        "",
        "",
        SimpleNamespace(unpack=lambda: (0, {"uri": "file:///a"})),
    )
    assert calls["save"] == 1

    window.MainWindow._on_portal_response(
        self, None, "", "", "", "", SimpleNamespace(unpack=lambda: (0, {}))
    )
    assert calls["fail"][-1] == "no screenshot returned"

    window.MainWindow._on_portal_response(
        self, None, "", "", "", "", SimpleNamespace(unpack=lambda: (1, {}))
    )
    assert calls["finish"][-1] == "Cancelled"

    window.MainWindow._on_portal_response(
        self, None, "", "", "", "", SimpleNamespace(unpack=lambda: (2, {}))
    )
    assert calls["fail"][-1] == "portal error"

    fake_glib = SimpleNamespace(Error=DummyError)
    monkeypatch.setattr(window, "GLib", fake_glib)

    class BadParams:
        def unpack(self):
            raise DummyError("boom")

    window.MainWindow._on_portal_response(self, None, "", "", "", "", BadParams())
    assert calls["fail"][-1] == "could not save (boom)"


def test_screenshot_main_and_extension_helpers(monkeypatch, capsys, tmp_path):
    assert screenshot._extension_from_uri("file:///tmp/a.JPG") == ".jpg"
    assert screenshot._extension_from_uri("file:///tmp/noext") == ".png"
    assert screenshot._extension_from_uri("file:///tmp/a.exe") == ".png"

    monkeypatch.setattr(screenshot, "enforce_offline_mode", lambda: None)

    monkeypatch.setattr(screenshot, "GI_IMPORT_ERROR", RuntimeError("missing"))
    monkeypatch.setattr(screenshot, "Gtk", None)
    monkeypatch.setattr(screenshot, "MainWindow", None)
    assert screenshot.main(["app"]) == 1
    assert "Missing GTK4/PyGObject dependencies" in capsys.readouterr().err

    seen = {}

    class App:
        def __init__(self, auto_capture=False):
            seen["auto_capture"] = auto_capture

        def run(self, argv):
            seen["argv"] = argv
            return len(argv)

    monkeypatch.setattr(screenshot, "GI_IMPORT_ERROR", None)
    monkeypatch.setattr(screenshot, "Gtk", object())
    monkeypatch.setattr(screenshot, "MainWindow", object())
    monkeypatch.setattr(screenshot, "ScreenuxScreenshotApp", App)
    assert screenshot.main(["a", "b"]) == 2
    assert seen == {"auto_capture": False, "argv": ["a", "b"]}

    seen.clear()
    assert screenshot.main(["a", "--capture"]) == 2
    assert seen == {"auto_capture": True, "argv": ["a", "--capture"]}

    class FakeGLib:
        @staticmethod
        def get_user_config_dir():
            return str(tmp_path / "cfg")

    monkeypatch.setattr(screenshot, "GLib", FakeGLib)
    assert screenshot._config_path() == tmp_path / "cfg" / "screenux" / "settings.json"

    monkeypatch.setattr(screenshot, "GLib", None)
    monkeypatch.setattr(screenshot.Path, "home", staticmethod(lambda: tmp_path / "home"))
    assert screenshot._config_path() == tmp_path / "home" / ".config" / "screenux" / "settings.json"


def test_screenshot_help_and_version_do_not_require_gtk(monkeypatch, capsys):
    monkeypatch.setattr(screenshot, "enforce_offline_mode", lambda: None)
    monkeypatch.setattr(screenshot, "GI_IMPORT_ERROR", RuntimeError("missing"))
    monkeypatch.setattr(screenshot, "Gtk", None)
    monkeypatch.setattr(screenshot, "MainWindow", None)

    assert screenshot.main(["screenux-screenshot", "--help"]) == 0
    assert "Usage: screenux-screenshot" in capsys.readouterr().out

    assert screenshot.main(["screenux-screenshot", "--version"]) == 0
    assert screenshot.APP_VERSION in capsys.readouterr().out


def test_screenshot_app_command_line_can_request_capture_on_existing_instance():
    if not hasattr(screenshot.ScreenuxScreenshotApp, "do_command_line"):
        return

    app = SimpleNamespace(_auto_capture_pending=False, activate=lambda: setattr(app, "activated", True))
    setattr(app, "activated", False)

    class FakeCommandLine:
        @staticmethod
        def get_arguments():
            return ["screenux-screenshot", "--capture"]

    result = screenshot.ScreenuxScreenshotApp.do_command_line(app, FakeCommandLine())

    assert result == 0
    assert app._auto_capture_pending is True
    assert app.activated is True


def test_screenshot_app_command_line_emits_capture_detection_log(caplog):
    if not hasattr(screenshot.ScreenuxScreenshotApp, "do_command_line"):
        return

    app = SimpleNamespace(_auto_capture_pending=False, activate=lambda: None)

    class FakeCommandLine:
        @staticmethod
        def get_arguments():
            return ["screenux-screenshot", "--capture"]

    with caplog.at_level("INFO", logger="screenux.app"):
        screenshot.ScreenuxScreenshotApp.do_command_line(app, FakeCommandLine())

    assert "hotkey.event.detected source=command-line" in caplog.text
    assert "--capture" in caplog.text


def test_screenshot_app_do_activate_auto_capture_skips_initial_present(monkeypatch):
    if not hasattr(screenshot.ScreenuxScreenshotApp, "do_activate"):
        return

    created = {}

    class FakeWindow:
        def __init__(self, *_args, **_kwargs):
            self.present_calls = 0
            self.capture_calls = 0
            created["window"] = self

        def present(self):
            self.present_calls += 1

        def set_icon_name(self, _name):
            return None

        def set_nonblocking_warning(self, _text):
            return None

        def trigger_shortcut_capture(self):
            self.capture_calls += 1

    class FakeGtkWindow:
        @staticmethod
        def set_default_icon_name(_name):
            return None

    monkeypatch.setattr(screenshot, "MainWindow", FakeWindow)
    monkeypatch.setattr(screenshot, "Gtk", SimpleNamespace(Window=FakeGtkWindow))

    app = SimpleNamespace(
        _auto_capture_pending=True,
        _hotkey_manager=SimpleNamespace(
            ensure_registered=lambda: SimpleNamespace(warning=None)
        ),
        props=SimpleNamespace(active_window=None),
    )

    screenshot.ScreenuxScreenshotApp.do_activate(app)

    assert app._auto_capture_pending is False
    assert created["window"].capture_calls == 1
    assert created["window"].present_calls == 0


def test_screenshot_enforce_offline_mode_blocks_network(monkeypatch):
    original_socket = screenshot.socket.socket
    original_create_connection = screenshot.socket.create_connection
    original_getaddrinfo = screenshot.socket.getaddrinfo
    original_gethostbyname = screenshot.socket.gethostbyname
    original_gethostbyname_ex = screenshot.socket.gethostbyname_ex
    original_gethostbyaddr = screenshot.socket.gethostbyaddr
    original_getnameinfo = screenshot.socket.getnameinfo

    screenshot.enforce_offline_mode()

    try:
        socket_obj = screenshot.socket.socket()
        socket_obj.connect(("127.0.0.1", 80))
        assert False
    except RuntimeError as err:
        assert "network access is disabled" in str(err)

    monkeypatch.setattr(screenshot.socket, "socket", original_socket)
    monkeypatch.setattr(screenshot.socket, "create_connection", original_create_connection)
    monkeypatch.setattr(screenshot.socket, "getaddrinfo", original_getaddrinfo)
    monkeypatch.setattr(screenshot.socket, "gethostbyname", original_gethostbyname)
    monkeypatch.setattr(screenshot.socket, "gethostbyname_ex", original_gethostbyname_ex)
    monkeypatch.setattr(screenshot.socket, "gethostbyaddr", original_gethostbyaddr)
    monkeypatch.setattr(screenshot.socket, "getnameinfo", original_getnameinfo)
