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


def test_window_take_screenshot_public_method():
    self = FakeWindowSelf()
    called = []
    self._on_take_screenshot = lambda button: called.append(button)

    window.MainWindow.take_screenshot(self)

    assert called == [self._button]


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
