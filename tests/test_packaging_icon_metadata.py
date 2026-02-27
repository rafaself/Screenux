import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_ID = "io.github.rafa.ScreenuxScreenshot"


class PackagingIconMetadataTests(unittest.TestCase):
    def test_desktop_entry_declares_app_icon(self) -> None:
        desktop_file = ROOT / f"{APP_ID}.desktop"
        content = desktop_file.read_text(encoding="utf-8")

        self.assertIn(f"Icon={APP_ID}", content)

    def test_flatpak_manifest_installs_app_icon_asset(self) -> None:
        manifest_file = ROOT / "flatpak" / f"{APP_ID}.json"
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))

        build_commands = manifest["modules"][0]["build-commands"]
        self.assertTrue(
            any(
                command.endswith(
                    f" /app/share/icons/hicolor/scalable/apps/{APP_ID}.svg"
                )
                for command in build_commands
            )
        )

        icon_file = ROOT / "assets" / "icons" / f"{APP_ID}.svg"
        self.assertTrue(icon_file.exists())


if __name__ == "__main__":
    unittest.main()
