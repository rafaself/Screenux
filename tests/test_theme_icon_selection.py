import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import src.screenux_screenshot as screenshot


class ThemeIconSelectionTests(unittest.TestCase):
    def test_select_icon_name_returns_app_id(self):
        self.assertEqual(screenshot.select_icon_name(), screenshot.APP_ID)


if __name__ == "__main__":
    unittest.main()
