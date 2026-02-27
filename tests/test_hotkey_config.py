import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import screenux_hotkey as hotkey


def test_read_hotkey_uses_default_when_unset():
    assert hotkey.read_hotkey_from_config({}) == hotkey.DEFAULT_SHORTCUT


def test_write_and_read_hotkey_round_trip():
    config = {}
    hotkey.write_hotkey_to_config(config, "ctrl+shift+s")
    assert config["global_hotkey"] == "Ctrl+Shift+S"
    assert hotkey.read_hotkey_from_config(config) == "Ctrl+Shift+S"


def test_write_and_read_disabled_hotkey():
    config = {}
    hotkey.write_hotkey_to_config(config, None)
    assert config["global_hotkey"] is None
    assert hotkey.read_hotkey_from_config(config) is None


def test_read_hotkey_ignores_invalid_config_value():
    assert hotkey.read_hotkey_from_config({"global_hotkey": 123}) == hotkey.DEFAULT_SHORTCUT


def test_hotkey_manager_persists_default_value_when_missing_from_config():
    state = {}

    def _load():
        return dict(state)

    def _save(config):
        state.clear()
        state.update(config)

    manager = hotkey.HotkeyManager(_load, _save, env={})
    result = manager.ensure_registered()

    assert result.shortcut == hotkey.DEFAULT_SHORTCUT
    assert state["global_hotkey"] == hotkey.DEFAULT_SHORTCUT
