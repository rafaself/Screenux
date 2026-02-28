import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install-screenux.sh"
UNINSTALLER = ROOT / "uninstall-screenux.sh"
APP_ID = "io.github.rafa.ScreenuxScreenshot"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _setup_mock_environment(
    *,
    with_gsettings: bool = False,
    installed: bool = False,
    gsettings_has_shortcut: bool = False,
) -> tuple[Path, dict[str, str], Path]:
    tmpdir = Path(tempfile.mkdtemp(prefix="screenux-install-tests-"))
    home = tmpdir / "home"
    home.mkdir(parents=True, exist_ok=True)

    mock_bin = tmpdir / "bin"
    mock_bin.mkdir(parents=True, exist_ok=True)

    log_file = tmpdir / "commands.log"
    state_file = tmpdir / "flatpak-installed"
    if installed:
        state_file.write_text("1", encoding="utf-8")

    _write_executable(
        mock_bin / "flatpak",
        """#!/usr/bin/env bash
set -euo pipefail
echo "flatpak $*" >> "${MOCK_LOG_FILE}"

if [[ "${1:-}" == "info" && "${2:-}" == "--user" ]]; then
  if [[ -f "${MOCK_FLATPAK_STATE_FILE}" ]]; then
    exit 0
  fi
  exit 1
fi

if [[ "${1:-}" == "install" ]]; then
  touch "${MOCK_FLATPAK_STATE_FILE}"
  exit 0
fi

if [[ "${1:-}" == "uninstall" ]]; then
  rm -f "${MOCK_FLATPAK_STATE_FILE}"
  exit 0
fi

exit 0
""",
    )

    if with_gsettings:
        _write_executable(
            mock_bin / "gsettings",
            """#!/usr/bin/env bash
set -euo pipefail
echo "gsettings $*" >> "${MOCK_LOG_FILE}"

case "${1:-}" in
  list-schemas)
    cat <<'EOF'
org.gnome.settings-daemon.plugins.media-keys
org.gnome.settings-daemon.plugins.media-keys.custom-keybinding
org.gnome.shell.keybindings
EOF
    ;;
  list-keys)
    case "${2:-}" in
      org.gnome.settings-daemon.plugins.media-keys)
        cat <<'EOF'
custom-keybindings
screenshot
window-screenshot
area-screenshot
EOF
        ;;
      org.gnome.shell.keybindings)
        cat <<'EOF'
show-screenshot
show-screenshot-ui
show-screen-recording-ui
EOF
        ;;
      *)
        cat <<'EOF'
name
command
binding
EOF
        ;;
    esac
    ;;
  get)
    schema="${2:-}"
    key="${3:-}"
    if [[ "${schema}" == "org.gnome.settings-daemon.plugins.media-keys" && "${key}" == "custom-keybindings" ]]; then
      if [[ "${MOCK_GSETTINGS_HAS_SHORTCUT:-0}" == "1" ]]; then
        echo "['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/']"
      else
        echo "[]"
      fi
      exit 0
    fi

    if [[ "${schema}" == org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:* && "${key}" == "name" ]]; then
      echo "'Screenux Screenshot'"
      exit 0
    fi

    if [[ "${schema}" == org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:* && "${key}" == "command" ]]; then
      echo "'${HOME}/.local/bin/screenux-screenshot --capture'"
      exit 0
    fi

    echo "[]"
    ;;
  set|reset)
    ;;
esac
""",
        )

    env = os.environ.copy()
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    env["HOME"] = str(home)
    env["MOCK_LOG_FILE"] = str(log_file)
    env["MOCK_FLATPAK_STATE_FILE"] = str(state_file)
    env["MOCK_GSETTINGS_HAS_SHORTCUT"] = "1" if gsettings_has_shortcut else "0"

    return tmpdir, env, log_file


def _run_command(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


class InstallScriptTests(unittest.TestCase):
    def test_installer_declares_shellcheck_source_paths_for_libraries(self):
        content = (ROOT / "scripts/install/install-screenux.sh").read_text(encoding="utf-8")
        self.assertIn("# shellcheck source=scripts/install/lib/common.sh", content)
        self.assertIn("# shellcheck source=scripts/install/lib/gnome_shortcuts.sh", content)

    def test_installer_installs_bundle_and_creates_local_entries(self):
        tmpdir, env, log_file = _setup_mock_environment()
        bundle = tmpdir / "screenux.flatpak"
        bundle.write_text("bundle", encoding="utf-8")

        result = _run_command([str(INSTALLER), "--bundle", str(bundle)], env)
        log = log_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(f"flatpak install -y --user --or-update {bundle}", log)
        self.assertGreaterEqual(log.count(f"flatpak info --user {APP_ID}"), 1)

        wrapper_path = Path(env["HOME"]) / ".local/bin/screenux-screenshot"
        desktop_file = Path(env["HOME"]) / f".local/share/applications/{APP_ID}.desktop"
        icon_file = Path(env["HOME"]) / f".local/share/icons/hicolor/256x256/apps/{APP_ID}.png"
        icon_file_svg = Path(env["HOME"]) / f".local/share/icons/hicolor/scalable/apps/{APP_ID}.svg"
        icon_file_light = Path(env["HOME"]) / f".local/share/icons/hicolor/scalable/apps/{APP_ID}-light.svg"
        icon_file_dark = Path(env["HOME"]) / f".local/share/icons/hicolor/scalable/apps/{APP_ID}-dark.svg"

        self.assertTrue(wrapper_path.exists())
        self.assertTrue(os.access(wrapper_path, os.X_OK))
        self.assertIn(f"flatpak run {APP_ID}", wrapper_path.read_text(encoding="utf-8"))

        self.assertTrue(desktop_file.exists())
        self.assertIn(
            f"Exec={wrapper_path}",
            desktop_file.read_text(encoding="utf-8"),
        )
        self.assertTrue(icon_file.exists())
        self.assertTrue(icon_file_svg.exists())
        self.assertTrue(icon_file_light.exists())
        self.assertTrue(icon_file_dark.exists())

    def test_installer_skips_bundle_install_when_app_already_installed(self):
        _, env, log_file = _setup_mock_environment(installed=True)

        result = _run_command([str(INSTALLER)], env)
        log = log_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn("flatpak install -y --user --or-update", log)

    def test_installer_can_configure_print_screen_shortcut(self):
        tmpdir, env, log_file = _setup_mock_environment(with_gsettings=True)
        bundle = tmpdir / "screenux.flatpak"
        bundle.write_text("bundle", encoding="utf-8")

        result = _run_command([str(INSTALLER), "--bundle", str(bundle), "--print-screen"], env)
        log = log_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(
            "gsettings set org.gnome.shell.keybindings show-screenshot []",
            log,
        )
        self.assertIn(
            "gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/ binding Print",
            log,
        )


class UninstallScriptTests(unittest.TestCase):
    def test_uninstaller_declares_shellcheck_source_paths_for_libraries(self):
        content = (ROOT / "scripts/install/uninstall-screenux.sh").read_text(encoding="utf-8")
        self.assertIn("# shellcheck source=scripts/install/lib/common.sh", content)
        self.assertIn("# shellcheck source=scripts/install/lib/gnome_shortcuts.sh", content)

    def test_uninstaller_removes_flatpak_and_local_artifacts_by_default(self):
        _, env, log_file = _setup_mock_environment(
            with_gsettings=True,
            installed=True,
            gsettings_has_shortcut=True,
        )
        wrapper_path = Path(env["HOME"]) / ".local/bin/screenux-screenshot"
        desktop_file = Path(env["HOME"]) / f".local/share/applications/{APP_ID}.desktop"
        icon_file = Path(env["HOME"]) / f".local/share/icons/hicolor/256x256/apps/{APP_ID}.png"
        icon_file_svg = Path(env["HOME"]) / f".local/share/icons/hicolor/scalable/apps/{APP_ID}.svg"
        icon_file_light = Path(env["HOME"]) / f".local/share/icons/hicolor/scalable/apps/{APP_ID}-light.svg"
        icon_file_dark = Path(env["HOME"]) / f".local/share/icons/hicolor/scalable/apps/{APP_ID}-dark.svg"
        data_dir = Path(env["HOME"]) / f".var/app/{APP_ID}"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "config.json").write_text("{}", encoding="utf-8")
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        wrapper_path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        desktop_file.parent.mkdir(parents=True, exist_ok=True)
        desktop_file.write_text("[Desktop Entry]\n", encoding="utf-8")
        icon_file.parent.mkdir(parents=True, exist_ok=True)
        icon_file.write_bytes(b"png")
        icon_file_svg.parent.mkdir(parents=True, exist_ok=True)
        icon_file_svg.write_text("<svg/>", encoding="utf-8")
        icon_file_light.write_text("<svg/>", encoding="utf-8")
        icon_file_dark.write_text("<svg/>", encoding="utf-8")

        result = _run_command([str(UNINSTALLER)], env)
        log = log_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn(f"flatpak uninstall -y --user {APP_ID}", log)
        self.assertFalse(wrapper_path.exists())
        self.assertFalse(desktop_file.exists())
        self.assertFalse(icon_file.exists())
        self.assertFalse(icon_file_svg.exists())
        self.assertFalse(icon_file_light.exists())
        self.assertFalse(icon_file_dark.exists())
        self.assertFalse(data_dir.exists())
        self.assertIn(
            "gsettings reset org.gnome.shell.keybindings show-screenshot",
            log,
        )

    def test_uninstaller_preserves_user_data_when_requested(self):
        _, env, _ = _setup_mock_environment(installed=True)
        data_dir = Path(env["HOME"]) / f".var/app/{APP_ID}"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "settings.json").write_text("{}", encoding="utf-8")

        result = _run_command([str(UNINSTALLER), "--preserve-user-data"], env)

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(data_dir.exists())

    def test_uninstaller_is_idempotent_when_app_is_absent(self):
        _, env, log_file = _setup_mock_environment()

        result = _run_command([str(UNINSTALLER)], env)
        log = log_file.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertNotIn(f"flatpak uninstall -y --user {APP_ID}", log)


if __name__ == "__main__":
    unittest.main()
