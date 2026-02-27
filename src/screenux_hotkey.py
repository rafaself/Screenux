from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Callable

DEFAULT_SHORTCUT = "Ctrl+Shift+S"
FALLBACK_SHORTCUTS = ("Ctrl+Alt+S", "Alt+Shift+S", "Super+Shift+S")
HOTKEY_CONFIG_KEY = "global_hotkey"

GNOME_MEDIA_SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_CUSTOM_SCHEMA = f"{GNOME_MEDIA_SCHEMA}.custom-keybinding"
GNOME_CUSTOM_KEY = "custom-keybindings"
GNOME_SHELL_SCHEMA = "org.gnome.shell.keybindings"
GNOME_CUSTOM_BASE_PATH = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

SCREENUX_SHORTCUT_NAME = "Screenux Screenshot"
SCREENUX_CAPTURE_COMMAND = "screenux-screenshot --capture"

Runner = Callable[[list[str]], object]

_MODIFIER_ORDER = ("Ctrl", "Alt", "Shift", "Super")
_MODIFIER_ALIASES = {
    "CTRL": "Ctrl",
    "CONTROL": "Ctrl",
    "ALT": "Alt",
    "SHIFT": "Shift",
    "SUPER": "Super",
    "WIN": "Super",
    "META": "Super",
}
_GSETTINGS_MODIFIER = {
    "Ctrl": "<Control>",
    "Alt": "<Alt>",
    "Shift": "<Shift>",
    "Super": "<Super>",
}

_NATIVE_SHORTCUT_KEYS = (
    (GNOME_SHELL_SCHEMA, "show-screenshot"),
    (GNOME_SHELL_SCHEMA, "show-screenshot-ui"),
    (GNOME_SHELL_SCHEMA, "show-screen-recording-ui"),
    (GNOME_MEDIA_SCHEMA, "screenshot"),
    (GNOME_MEDIA_SCHEMA, "window-screenshot"),
    (GNOME_MEDIA_SCHEMA, "area-screenshot"),
)


@dataclass(frozen=True)
class HotkeyRegistrationResult:
    shortcut: str | None
    warning: str | None = None


def _default_runner(command: list[str]) -> object:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def _run(command: list[str], runner: Runner) -> object:
    try:
        return runner(command)
    except FileNotFoundError:
        return SimpleNamespace(returncode=127, stdout="", stderr=f"{command[0]} not found")


def _stdout(result: object) -> str:
    return str(getattr(result, "stdout", "") or "").strip()


def _success(result: object) -> bool:
    return int(getattr(result, "returncode", 1)) == 0


def _normalize_key_token(token: str) -> str:
    text = token.strip()
    if not text:
        raise ValueError("shortcut key cannot be empty")
    if len(text) == 1:
        return text.upper()

    upper = text.upper()
    if upper == "PRINT":
        return "Print"
    if upper.startswith("F") and upper[1:].isdigit():
        return upper
    if upper in ("SPACE", "TAB", "ESC", "ESCAPE", "ENTER"):
        mapping = {
            "SPACE": "Space",
            "TAB": "Tab",
            "ESC": "Esc",
            "ESCAPE": "Escape",
            "ENTER": "Enter",
        }
        return mapping[upper]

    if text.isalpha():
        return text.title()
    raise ValueError(f"unsupported shortcut key: {token}")


def _normalize_modifier_token(token: str) -> str:
    normalized = _MODIFIER_ALIASES.get(token.strip().strip("<>").upper())
    if normalized is None:
        raise ValueError(f"unsupported shortcut modifier: {token}")
    return normalized


def normalize_shortcut(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("shortcut cannot be empty")

    parts = [part.strip() for part in text.split("+") if part.strip()]
    if not parts:
        raise ValueError("shortcut cannot be empty")

    modifiers: list[str] = []
    key: str | None = None
    for part in parts:
        try:
            modifier = _normalize_modifier_token(part)
        except ValueError:
            if key is not None:
                raise ValueError("shortcut must contain exactly one non-modifier key")
            key = _normalize_key_token(part)
            continue
        if modifier not in modifiers:
            modifiers.append(modifier)

    if key is None:
        raise ValueError("shortcut must include a key")

    ordered_modifiers = [item for item in _MODIFIER_ORDER if item in modifiers]
    return "+".join([*ordered_modifiers, key])


def read_hotkey_from_config(config: dict) -> str | None:
    raw = config.get(HOTKEY_CONFIG_KEY, DEFAULT_SHORTCUT)
    if raw is None:
        return None
    if not isinstance(raw, str):
        return DEFAULT_SHORTCUT
    try:
        return normalize_shortcut(raw)
    except ValueError:
        return DEFAULT_SHORTCUT


def write_hotkey_to_config(config: dict, value: str | None) -> None:
    if value is None:
        config[HOTKEY_CONFIG_KEY] = None
        return
    config[HOTKEY_CONFIG_KEY] = normalize_shortcut(value)


def resolve_shortcut_with_fallback(
    preferred: str | None, is_taken: Callable[[str], bool]
) -> tuple[str | None, str | None]:
    if preferred is None:
        return None, None

    normalized_preferred = normalize_shortcut(preferred)
    candidates: list[str] = [normalized_preferred]
    for fallback in FALLBACK_SHORTCUTS:
        if fallback not in candidates:
            candidates.append(fallback)

    for index, candidate in enumerate(candidates):
        if not is_taken(candidate):
            if index == 0:
                return candidate, None
            return candidate, f"Shortcut {normalized_preferred} is in use. Using {candidate}."

    return None, "No available global shortcut candidate; hotkey disabled."


def parse_gsettings_binding(raw_value: str) -> str | None:
    matches = re.findall(r"'([^']+)'", raw_value or "")
    if not matches:
        return None

    accel = matches[0].strip()
    if not accel:
        return None

    modifiers: list[str] = []
    if accel.startswith("<"):
        for token in re.findall(r"<([^>]+)>", accel):
            try:
                modifier = _normalize_modifier_token(token)
            except ValueError:
                return None
            if modifier not in modifiers:
                modifiers.append(modifier)
        key = re.sub(r"(?:<[^>]+>)+", "", accel).strip()
    else:
        key = accel

    if not key:
        return None

    try:
        normalized_key = _normalize_key_token(key)
    except ValueError:
        return None
    ordered_modifiers = [item for item in _MODIFIER_ORDER if item in modifiers]
    return "+".join([*ordered_modifiers, normalized_key])


def shortcut_to_gsettings_binding(shortcut: str) -> str:
    normalized = normalize_shortcut(shortcut)
    parts = normalized.split("+")
    key = parts[-1]
    modifiers = parts[:-1]
    modifier_prefix = "".join(_GSETTINGS_MODIFIER[item] for item in modifiers)
    key_token = key.lower() if len(key) == 1 else key
    return f"['{modifier_prefix}{key_token}']"


def _schema_exists(schema: str, runner: Runner) -> bool:
    result = _run(["gsettings", "list-schemas"], runner)
    if not _success(result):
        return False
    return schema in _stdout(result).splitlines()


def _gsettings_get(schema: str, key: str, runner: Runner) -> str | None:
    result = _run(["gsettings", "get", schema, key], runner)
    if not _success(result):
        return None
    return _stdout(result)


def _gsettings_set(schema: str, key: str, value: str, runner: Runner) -> bool:
    result = _run(["gsettings", "set", schema, key, value], runner)
    return _success(result)


def _gsettings_available(runner: Runner) -> bool:
    result = _run(["gsettings", "--version"], runner)
    return _success(result)


def _build_gsettings_list(paths: list[str]) -> str:
    return "[" + ", ".join(f"'{path}'" for path in paths) + "]"


def _custom_paths(runner: Runner) -> list[str]:
    raw = _gsettings_get(GNOME_MEDIA_SCHEMA, GNOME_CUSTOM_KEY, runner)
    if raw is None:
        return []
    return re.findall(r"/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom\d+/", raw)


def _strip_single_quotes(value: str | None) -> str:
    if value is None:
        return ""
    text = value.strip()
    if text.startswith("'") and text.endswith("'"):
        return text[1:-1]
    return text


def _find_screenux_custom_path(paths: list[str], runner: Runner) -> str | None:
    for path in paths:
        schema = f"{GNOME_CUSTOM_SCHEMA}:{path}"
        current_name = _strip_single_quotes(_gsettings_get(schema, "name", runner))
        current_command = _strip_single_quotes(_gsettings_get(schema, "command", runner))
        if current_name == SCREENUX_SHORTCUT_NAME or current_command == SCREENUX_CAPTURE_COMMAND:
            return path
    return None


def collect_gnome_taken_shortcuts(runner: Runner = _default_runner, exclude_path: str | None = None) -> set[str]:
    if not _gsettings_available(runner):
        return set()
    if not _schema_exists(GNOME_MEDIA_SCHEMA, runner):
        return set()

    taken: set[str] = set()

    for path in _custom_paths(runner):
        if path == exclude_path:
            continue
        schema = f"{GNOME_CUSTOM_SCHEMA}:{path}"
        current_binding = parse_gsettings_binding(_gsettings_get(schema, "binding", runner) or "")
        if current_binding:
            taken.add(current_binding)

    for schema, key in _NATIVE_SHORTCUT_KEYS:
        if not _schema_exists(schema, runner):
            continue
        parsed = parse_gsettings_binding(_gsettings_get(schema, key, runner) or "")
        if parsed:
            taken.add(parsed)

    return taken


def _remove_screenux_shortcut(paths: list[str], runner: Runner) -> None:
    screenux_path = _find_screenux_custom_path(paths, runner)
    if screenux_path is None:
        return
    updated_paths = [path for path in paths if path != screenux_path]
    _gsettings_set(GNOME_MEDIA_SCHEMA, GNOME_CUSTOM_KEY, _build_gsettings_list(updated_paths), runner)


def _next_available_custom_path(paths: list[str]) -> str:
    index = 0
    existing = set(paths)
    while True:
        candidate = f"{GNOME_CUSTOM_BASE_PATH}/custom{index}/"
        if candidate not in existing:
            return candidate
        index += 1


def register_gnome_shortcut(
    shortcut: str | None,
    runner: Runner = _default_runner,
) -> HotkeyRegistrationResult:
    if not _gsettings_available(runner):
        return HotkeyRegistrationResult(shortcut, "gsettings is unavailable; global hotkey not configured.")
    if not _schema_exists(GNOME_MEDIA_SCHEMA, runner):
        return HotkeyRegistrationResult(shortcut, "GNOME media key schema not available; global hotkey not configured.")

    paths = _custom_paths(runner)
    screenux_path = _find_screenux_custom_path(paths, runner)

    if shortcut is None:
        _remove_screenux_shortcut(paths, runner)
        return HotkeyRegistrationResult(None, None)

    preferred = normalize_shortcut(shortcut)
    taken = collect_gnome_taken_shortcuts(runner=runner, exclude_path=screenux_path)
    resolved, warning = resolve_shortcut_with_fallback(preferred, lambda candidate: candidate in taken)

    if resolved is None:
        _remove_screenux_shortcut(paths, runner)
        return HotkeyRegistrationResult(None, warning)

    target_path = screenux_path or _next_available_custom_path(paths)
    if target_path not in paths:
        paths.append(target_path)
        _gsettings_set(GNOME_MEDIA_SCHEMA, GNOME_CUSTOM_KEY, _build_gsettings_list(paths), runner)

    target_schema = f"{GNOME_CUSTOM_SCHEMA}:{target_path}"
    _gsettings_set(target_schema, "name", SCREENUX_SHORTCUT_NAME, runner)
    _gsettings_set(target_schema, "command", SCREENUX_CAPTURE_COMMAND, runner)
    _gsettings_set(target_schema, "binding", shortcut_to_gsettings_binding(resolved), runner)
    return HotkeyRegistrationResult(resolved, warning)


def _is_gnome_desktop(env: dict[str, str]) -> bool:
    desktop = env.get("XDG_CURRENT_DESKTOP", "").upper()
    session = env.get("DESKTOP_SESSION", "").upper()
    return "GNOME" in desktop or "GNOME" in session


def register_portal_shortcut(shortcut: str | None) -> HotkeyRegistrationResult:
    if shortcut is None:
        return HotkeyRegistrationResult(None, None)
    try:
        normalized = normalize_shortcut(shortcut)
    except ValueError:
        return HotkeyRegistrationResult(DEFAULT_SHORTCUT, "Invalid shortcut value; using default shortcut.")
    return HotkeyRegistrationResult(
        normalized,
        "Portal hotkey backend is best-effort on this desktop; GNOME keybindings are required for closed-app behavior.",
    )


class HotkeyManager:
    def __init__(
        self,
        load_config: Callable[[], dict],
        save_config: Callable[[dict], None],
        *,
        env: dict[str, str] | None = None,
        runner: Runner = _default_runner,
    ) -> None:
        self._load_config = load_config
        self._save_config = save_config
        self._runner = runner
        self._env = env or dict(os.environ)
        self._current_shortcut: str | None = None
        self.last_warning: str | None = None

    def current_shortcut(self) -> str | None:
        return self._current_shortcut

    def ensure_registered(self) -> HotkeyRegistrationResult:
        config = self._load_config()
        has_explicit_hotkey = HOTKEY_CONFIG_KEY in config
        preferred = read_hotkey_from_config(config)
        if _is_gnome_desktop(self._env):
            result = register_gnome_shortcut(preferred, runner=self._runner)
        else:
            result = register_portal_shortcut(preferred)

        if result.shortcut != preferred or not has_explicit_hotkey:
            write_hotkey_to_config(config, result.shortcut)
            self._save_config(config)

        self._current_shortcut = result.shortcut
        self.last_warning = result.warning
        return result

    def apply_shortcut(self, value: str | None) -> HotkeyRegistrationResult:
        config = self._load_config()
        write_hotkey_to_config(config, value)
        self._save_config(config)
        return self.ensure_registered()

    def disable_shortcut(self) -> HotkeyRegistrationResult:
        return self.apply_shortcut(None)
