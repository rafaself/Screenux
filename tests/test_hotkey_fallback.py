import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import screenux_hotkey as hotkey


def test_resolve_shortcut_uses_first_fallback_when_default_is_taken():
    taken = {"Ctrl+Print"}
    shortcut, warning = hotkey.resolve_shortcut_with_fallback(
        "Ctrl+Print", lambda value: value in taken
    )

    assert shortcut == "Ctrl+Shift+S"
    assert warning is not None
    assert "Ctrl+Print" in warning


def test_resolve_shortcut_skips_taken_first_fallback():
    taken = {"Ctrl+Print", "Ctrl+Shift+S"}
    shortcut, warning = hotkey.resolve_shortcut_with_fallback(
        "Ctrl+Print", lambda value: value in taken
    )

    assert shortcut == "Ctrl+Alt+S"
    assert warning is not None
    assert "Ctrl+Alt+S" in warning


def test_resolve_shortcut_disables_when_all_candidates_are_taken():
    taken = {
        "Ctrl+Print",
        "Ctrl+Shift+S",
        "Ctrl+Alt+S",
        "Alt+Shift+S",
        "Super+Shift+S",
    }
    shortcut, warning = hotkey.resolve_shortcut_with_fallback(
        "Ctrl+Print", lambda value: value in taken
    )

    assert shortcut is None
    assert warning is not None
    assert "disabled" in warning.lower()
