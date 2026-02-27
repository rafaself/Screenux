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
            "['<Control>Print']\n",
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
            "['<Control>Print']\n",
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
        == [
            "gsettings",
            "set",
            f"{hotkey.GNOME_CUSTOM_SCHEMA}:{new_path}",
            "command",
            hotkey.SCREENUX_CAPTURE_COMMAND,
        ]
        for command in calls
    )
    assert any(
        command
        == [
            "gsettings",
            "set",
            f"{hotkey.GNOME_CUSTOM_SCHEMA}:{new_path}",
            "binding",
            "['<Control><Shift>s']",
        ]
        for command in calls
    )
