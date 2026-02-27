import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_make_with_mocks(info_should_succeed: bool) -> tuple[int, str]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        log_file = tmp_path / "commands.log"
        mock_bin = tmp_path / "bin"
        mock_bin.mkdir()

        _write_executable(
            mock_bin / "flatpak",
            """#!/usr/bin/env bash
set -euo pipefail

echo "flatpak $*" >> \"${MOCK_LOG_FILE}\"

if [[ \"$1\" == \"info\" ]]; then
  if [[ \"${MOCK_INFO_SUCCESS:-0}\" == \"1\" ]]; then
    exit 0
  fi
  exit 1
fi

if [[ \"$1\" == \"remote-add\" ]]; then
  exit 0
fi

if [[ \"$1\" == \"install\" ]]; then
  exit 0
fi

if [[ \"$1\" == \"build-bundle\" ]]; then
  exit 0
fi

exit 0
""",
        )

        _write_executable(
            mock_bin / "flatpak-builder",
            """#!/usr/bin/env bash
set -euo pipefail

echo "flatpak-builder $*" >> \"${MOCK_LOG_FILE}\"
exit 0
""",
        )

        env = os.environ.copy()
        env["PATH"] = f"{mock_bin}:{env['PATH']}"
        env["MOCK_LOG_FILE"] = str(log_file)
        env["MOCK_INFO_SUCCESS"] = "1" if info_should_succeed else "0"

        result = subprocess.run(
            [
                "make",
                "build-flatpak-bundle",
                f"FLATPAK_BUILD_DIR={tmp_path / 'build-dir'}",
                f"FLATPAK_REPO_DIR={tmp_path / 'repo'}",
                f"FLATPAK_BUNDLE={tmp_path / 'screenux.flatpak'}",
            ],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        if not log_file.exists():
            return result.returncode, ""

        return result.returncode, log_file.read_text(encoding="utf-8")


class BuildFlatpakBundleDepsTests(unittest.TestCase):
    def test_build_flatpak_bundle_installs_runtime_when_missing(self):
        code, log = _run_make_with_mocks(info_should_succeed=False)

        self.assertEqual(code, 0)
        self.assertIn(
            "flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo",
            log,
        )
        self.assertIn(
            "flatpak install -y --user flathub org.gnome.Platform//47 org.gnome.Sdk//47",
            log,
        )
        self.assertIn("flatpak-builder --force-clean", log)

    def test_build_flatpak_bundle_skips_runtime_install_when_present(self):
        code, log = _run_make_with_mocks(info_should_succeed=True)

        self.assertEqual(code, 0)
        self.assertNotIn("flatpak remote-add", log)
        self.assertNotIn(
            "flatpak install -y --user flathub org.gnome.Platform//47 org.gnome.Sdk//47",
            log,
        )
        self.assertIn("flatpak-builder --force-clean", log)


if __name__ == "__main__":
    unittest.main()
