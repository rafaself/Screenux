import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_FILE = ROOT / "packaging" / "linux" / "screenux-screenshot.desktop"
BUILD_SCRIPT = ROOT / "scripts" / "build_deb.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


class DebianPackagingTests(unittest.TestCase):
    def test_desktop_entry_exists_and_declares_expected_fields(self):
        content = DESKTOP_FILE.read_text(encoding="utf-8")
        self.assertIn("Exec=screenux-screenshot", content)
        self.assertIn("Icon=screenux-screenshot", content)
        self.assertIn("Type=Application", content)
        self.assertIn("Categories=Utility;Graphics;", content)

    def test_build_script_emits_expected_deb_name_and_install_paths(self):
        with tempfile.TemporaryDirectory(prefix="screenux-deb-test-") as tmpdir:
            tmp_path = Path(tmpdir)
            mock_bin = tmp_path / "bin"
            mock_bin.mkdir(parents=True, exist_ok=True)
            out_dir = tmp_path / "out"
            out_dir.mkdir(parents=True, exist_ok=True)
            log_file = tmp_path / "commands.log"

            _write_executable(
                mock_bin / "python3",
                """#!/usr/bin/env bash
set -euo pipefail
echo "python3 $*" >> "${MOCK_LOG_FILE}"
if [[ "${1:-}" == "-m" && "${2:-}" == "venv" ]]; then
  venv_path="${3}"
  mkdir -p "${venv_path}/bin"
  cat > "${venv_path}/bin/pip" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "pip $*" >> "${MOCK_LOG_FILE}"
exit 0
EOF
  cat > "${venv_path}/bin/pyinstaller" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "pyinstaller $*" >> "${MOCK_LOG_FILE}"
mkdir -p dist
cat > dist/screenux-screenshot <<'EOS'
#!/usr/bin/env bash
echo "screenux"
EOS
chmod +x dist/screenux-screenshot
exit 0
EOF
  chmod +x "${venv_path}/bin/pip" "${venv_path}/bin/pyinstaller"
  exit 0
fi
exit 0
""",
            )
            _write_executable(
                mock_bin / "dpkg-deb",
                """#!/usr/bin/env bash
set -euo pipefail
echo "dpkg-deb $*" >> "${MOCK_LOG_FILE}"
touch "${@: -1}"
""",
            )

            env = os.environ.copy()
            env["PATH"] = f"{mock_bin}:{env['PATH']}"
            env["MOCK_LOG_FILE"] = str(log_file)
            env["OUT_DIR"] = str(out_dir)
            env["APP_VERSION"] = "9.9.9"
            env["APP_NAME"] = "screenux-screenshot"
            env["APP_ARCH"] = "amd64"

            result = subprocess.run(
                [str(BUILD_SCRIPT)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            log = log_file.read_text(encoding="utf-8")

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("pyinstaller --onefile", log)
            self.assertIn("dpkg-deb --build --root-owner-group", log)
            self.assertTrue((out_dir / "screenux-screenshot_9.9.9_amd64.deb").is_file())


if __name__ == "__main__":
    unittest.main()
