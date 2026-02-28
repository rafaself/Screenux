import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import screenux_hotkey as hotkey


def _make_runner(mapping: dict[tuple[str, ...], tuple[int, str, str]], calls: list[list[str]]):
    def _runner(command: list[str]):
        calls.append(command)
        code, stdout, stderr = mapping.get(tuple(command), (0, "", ""))
        return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)

    return _runner


def test_collect_gnome_taken_shortcuts_parses_custom_and_native_bindings():
    calls: list[list[str]] = []
    custom_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    mapping = {
        ("gsettings", "--version"): (0, "2.76.0\n", ""),
        ("gsettings", "list-schemas"): (
            0,
            "\n".join(
                [
                    hotkey.GNOME_MEDIA_SCHEMA,
                    hotkey.GNOME_CUSTOM_SCHEMA,
                    hotkey.GNOME_SHELL_SCHEMA,
                ]
            )
            + "\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, hotkey.GNOME_CUSTOM_KEY): (
            0,
            f"['{custom_path}']\n",
            "",
        ),
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{custom_path}", "binding"): (
            0,
            "'<Control>Print'\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot"): (0, "['Print']\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screen-recording-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot"): (0, "[]\n", ""),
    }
    runner = _make_runner(mapping, calls)

    taken = hotkey.collect_gnome_taken_shortcuts(runner=runner)

    assert "Ctrl+Print" in taken
    assert "Print" in taken


def test_register_gnome_shortcut_sets_command_and_uses_fallback_when_conflicting():
    calls: list[list[str]] = []
    existing_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    new_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom1/"
    mapping = {
        ("gsettings", "--version"): (0, "2.76.0\n", ""),
        ("gsettings", "list-schemas"): (
            0,
            "\n".join(
                [
                    hotkey.GNOME_MEDIA_SCHEMA,
                    hotkey.GNOME_CUSTOM_SCHEMA,
                    hotkey.GNOME_SHELL_SCHEMA,
                ]
            )
            + "\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, hotkey.GNOME_CUSTOM_KEY): (
            0,
            f"['{existing_path}']\n",
            "",
        ),
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{existing_path}", "name"): (
            0,
            "'Other Shortcut'\n",
            "",
        ),
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{existing_path}", "command"): (
            0,
            "'other-command'\n",
            "",
        ),
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{existing_path}", "binding"): (
            0,
            "'<Control>Print'\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screen-recording-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot"): (0, "[]\n", ""),
    }
    runner = _make_runner(mapping, calls)

    result = hotkey.register_gnome_shortcut("Ctrl+Print", runner=runner)

    assert result.shortcut == "Ctrl+Shift+S"
    assert result.warning is not None
    assert any(
        command
        and command[:4]
        == [
            "gsettings",
            "set",
            f"{hotkey.GNOME_CUSTOM_SCHEMA}:{new_path}",
            "command",
        ]
        and "screenux-screenshot" in command[4]
        and command[4].endswith(" --capture")
        for command in calls
    )
    assert any(
        command
        == [
            "gsettings",
            "set",
            f"{hotkey.GNOME_CUSTOM_SCHEMA}:{new_path}",
            "binding",
            "<Control><Shift>s",
        ]
        for command in calls
    )


def test_collect_gnome_taken_shortcuts_includes_native_clip_bindings():
    calls: list[list[str]] = []
    mapping = {
        ("gsettings", "--version"): (0, "2.76.0\n", ""),
        ("gsettings", "list-schemas"): (
            0,
            "\n".join(
                [
                    hotkey.GNOME_MEDIA_SCHEMA,
                    hotkey.GNOME_SHELL_SCHEMA,
                ]
            )
            + "\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, hotkey.GNOME_CUSTOM_KEY): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screen-recording-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot-clip"): (0, "'<Control>Print'\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot-clip"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot-clip"): (0, "[]\n", ""),
    }
    runner = _make_runner(mapping, calls)

    taken = hotkey.collect_gnome_taken_shortcuts(runner=runner)

    assert "Ctrl+Print" in taken


def test_register_gnome_shortcut_uses_fallback_when_native_clip_binding_cannot_be_cleared():
    calls: list[list[str]] = []
    new_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    mapping = {
        ("gsettings", "--version"): (0, "2.76.0\n", ""),
        ("gsettings", "list-schemas"): (
            0,
            "\n".join(
                [
                    hotkey.GNOME_MEDIA_SCHEMA,
                    hotkey.GNOME_CUSTOM_SCHEMA,
                    hotkey.GNOME_SHELL_SCHEMA,
                ]
            )
            + "\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, hotkey.GNOME_CUSTOM_KEY): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screen-recording-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot-clip"): (0, "'<Control>Print'\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot-clip"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot-clip"): (0, "[]\n", ""),
        ("gsettings", "set", hotkey.GNOME_MEDIA_SCHEMA, "screenshot-clip", "[]"): (1, "", "permission denied"),
    }
    runner = _make_runner(mapping, calls)

    result = hotkey.register_gnome_shortcut("Ctrl+PrintScreen", runner=runner)

    assert result.shortcut == "Ctrl+Shift+S"
    assert result.warning is not None
    assert "Ctrl+Print" in result.warning
    assert any(
        command
        == [
            "gsettings",
            "set",
            f"{hotkey.GNOME_CUSTOM_SCHEMA}:{new_path}",
            "binding",
            "<Control><Shift>s",
        ]
        for command in calls
    )


def test_register_gnome_shortcut_reclaims_native_clip_shortcut_when_requested():
    calls: list[list[str]] = []
    new_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    mapping = {
        ("gsettings", "--version"): (0, "2.76.0\n", ""),
        ("gsettings", "list-schemas"): (
            0,
            "\n".join(
                [
                    hotkey.GNOME_MEDIA_SCHEMA,
                    hotkey.GNOME_CUSTOM_SCHEMA,
                    hotkey.GNOME_SHELL_SCHEMA,
                ]
            )
            + "\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, hotkey.GNOME_CUSTOM_KEY): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screen-recording-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot-clip"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot-clip"): (0, "[]\n", ""),
    }
    state = {"clip_binding": "'<Control>Print'\n"}

    def runner(command: list[str]):
        calls.append(command)
        key = tuple(command)
        if key == ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot-clip"):
            return SimpleNamespace(returncode=0, stdout=state["clip_binding"], stderr="")
        if key == ("gsettings", "set", hotkey.GNOME_MEDIA_SCHEMA, "screenshot-clip", "[]"):
            state["clip_binding"] = "[]\n"
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        code, stdout, stderr = mapping.get(key, (0, "", ""))
        return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)

    result = hotkey.register_gnome_shortcut("Ctrl+Print", runner=runner)

    assert result.shortcut == "Ctrl+Print"
    assert any(
        command
        == [
            "gsettings",
            "set",
            hotkey.GNOME_MEDIA_SCHEMA,
            "screenshot-clip",
            "[]",
        ]
        for command in calls
    )


def test_find_screenux_custom_path_matches_absolute_capture_command():
    calls: list[list[str]] = []
    custom_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    mapping = {
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{custom_path}", "name"): (
            0,
            "'Other Name'\n",
            "",
        ),
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{custom_path}", "command"): (
            0,
            "'/usr/bin/screenux-screenshot --capture'\n",
            "",
        ),
    }
    runner = _make_runner(mapping, calls)

    found = hotkey._find_screenux_custom_path([custom_path], runner)  # noqa: SLF001 - internal helper coverage

    assert found == custom_path


def test_register_gnome_shortcut_emits_telemetry_logs(caplog):
    calls: list[list[str]] = []
    mapping = {
        ("gsettings", "--version"): (0, "2.76.0\n", ""),
        ("gsettings", "list-schemas"): (
            0,
            "\n".join(
                [
                    hotkey.GNOME_MEDIA_SCHEMA,
                    hotkey.GNOME_CUSTOM_SCHEMA,
                    hotkey.GNOME_SHELL_SCHEMA,
                ]
            )
            + "\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, hotkey.GNOME_CUSTOM_KEY): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screenshot-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_SHELL_SCHEMA, "show-screen-recording-ui"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "screenshot-clip"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "window-screenshot-clip"): (0, "[]\n", ""),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, "area-screenshot-clip"): (0, "[]\n", ""),
    }
    runner = _make_runner(mapping, calls)

    with caplog.at_level("INFO", logger="screenux.hotkey"):
        result = hotkey.register_gnome_shortcut("Ctrl+Print", runner=runner)

    assert result.shortcut == "Ctrl+Print"
    assert "hotkey.register.start" in caplog.text
    assert "hotkey.register.resolve" in caplog.text
    assert "hotkey.register.persisted" in caplog.text


def test_register_gnome_shortcut_disable_restores_native_print_bindings():
    calls: list[list[str]] = []
    existing_path = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/"
    mapping = {
        ("gsettings", "--version"): (0, "2.76.0\n", ""),
        ("gsettings", "list-schemas"): (
            0,
            "\n".join(
                [
                    hotkey.GNOME_MEDIA_SCHEMA,
                    hotkey.GNOME_CUSTOM_SCHEMA,
                    hotkey.GNOME_SHELL_SCHEMA,
                ]
            )
            + "\n",
            "",
        ),
        ("gsettings", "list-keys", hotkey.GNOME_SHELL_SCHEMA): (
            0,
            "\n".join(["show-screenshot-ui", "screenshot", "screenshot-window"]) + "\n",
            "",
        ),
        ("gsettings", "list-keys", hotkey.GNOME_MEDIA_SCHEMA): (
            0,
            "\n".join(["custom-keybindings", "screenshot", "window-screenshot", "area-screenshot"]) + "\n",
            "",
        ),
        ("gsettings", "get", hotkey.GNOME_MEDIA_SCHEMA, hotkey.GNOME_CUSTOM_KEY): (
            0,
            f"['{existing_path}']\n",
            "",
        ),
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{existing_path}", "name"): (
            0,
            "'Screenux Screenshot'\n",
            "",
        ),
        ("gsettings", "get", f"{hotkey.GNOME_CUSTOM_SCHEMA}:{existing_path}", "command"): (
            0,
            "'/usr/bin/screenux-screenshot --capture'\n",
            "",
        ),
    }
    runner = _make_runner(mapping, calls)

    result = hotkey.register_gnome_shortcut(None, runner=runner)

    assert result.shortcut is None
    assert any(
        command
        == [
            "gsettings",
            "set",
            hotkey.GNOME_MEDIA_SCHEMA,
            hotkey.GNOME_CUSTOM_KEY,
            "[]",
        ]
        for command in calls
    )
    assert any(
        command
        == [
            "gsettings",
            "reset",
            hotkey.GNOME_SHELL_SCHEMA,
            "show-screenshot-ui",
        ]
        for command in calls
    )
