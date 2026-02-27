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
        expected_targets = (
            f"/app/share/icons/hicolor/256x256/apps/{APP_ID}.png",
            f"/app/share/icons/hicolor/scalable/apps/{APP_ID}.svg",
            f"/app/share/icons/hicolor/scalable/apps/{APP_ID}-light.svg",
            f"/app/share/icons/hicolor/scalable/apps/{APP_ID}-dark.svg",
        )
        for target in expected_targets:
            self.assertTrue(any(command.endswith(f" {target}") for command in build_commands))

        icon_files = (
            ROOT / "assets" / "icons" / f"{APP_ID}.png",
            ROOT / "assets" / "icons" / f"{APP_ID}.svg",
            ROOT / "assets" / "icons" / f"{APP_ID}-light.svg",
            ROOT / "assets" / "icons" / f"{APP_ID}-dark.svg",
        )
        for icon_file in icon_files:
            self.assertTrue(icon_file.exists())


if __name__ == "__main__":
    unittest.main()
