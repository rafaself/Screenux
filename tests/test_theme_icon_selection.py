import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import src.screenux_screenshot as screenshot


class _FakeSettings:
    def __init__(self, prefer_dark: bool):
        self._prefer_dark = prefer_dark

    def get_property(self, name: str):
        if name == "gtk-application-prefer-dark-theme":
            return self._prefer_dark
        return None


class _FakeGtk:
    class Settings:
        _settings = None

        @staticmethod
        def get_default():
            return _FakeGtk.Settings._settings


class ThemeIconSelectionTests(unittest.TestCase):
    def test_select_icon_name_uses_dark_icon_when_dark_theme_is_preferred(self):
        original_gtk = screenshot.Gtk
        try:
            _FakeGtk.Settings._settings = _FakeSettings(prefer_dark=True)
            screenshot.Gtk = _FakeGtk
            self.assertEqual(screenshot.select_icon_name(), f"{screenshot.APP_ID}-dark")
        finally:
            screenshot.Gtk = original_gtk

    def test_select_icon_name_uses_light_icon_when_dark_theme_is_not_preferred(self):
        original_gtk = screenshot.Gtk
        try:
            _FakeGtk.Settings._settings = _FakeSettings(prefer_dark=False)
            screenshot.Gtk = _FakeGtk
            self.assertEqual(screenshot.select_icon_name(), f"{screenshot.APP_ID}-light")
        finally:
            screenshot.Gtk = original_gtk


if __name__ == "__main__":
    unittest.main()
