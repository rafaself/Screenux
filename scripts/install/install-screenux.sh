#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/common.sh"
source "${SCRIPT_DIR}/lib/gnome_shortcuts.sh"

usage() {
  cat <<'EOF'
Usage:
  ./install-screenux.sh [--print-screen] [/path/to/screenux-screenshot.flatpak] "['<Control><Shift>s']"
  ./install-screenux.sh --restore-native-print

Arguments:
  1) Flatpak bundle path (optional if Screenux is already installed for user)
  2) GNOME keybinding list syntax (optional, default: ['<Control><Shift>s'])

Options:
  --print-screen          Bind Screenux to ['Print'] and disable GNOME native Print keys
  --restore-native-print  Remove Screenux shortcut (if present) and restore native GNOME Print keys
  -h, --help              Show this help

Examples:
  ./install-screenux.sh ./screenux-screenshot.flatpak
  ./install-screenux.sh
  ./install-screenux.sh --print-screen ./screenux-screenshot.flatpak
  ./install-screenux.sh --print-screen
  ./install-screenux.sh ./screenux-screenshot.flatpak "['Print']"
  ./install-screenux.sh --restore-native-print
EOF
}

install_bundle() {
  local flatpak_file="$1"

  if ! command -v flatpak >/dev/null 2>&1; then
    fail "Required command not found: flatpak. Install it first (Debian/Ubuntu): apt-get update && sudo apt-get install -y flatpak"
  fi

  if flatpak info --user "${APP_ID}" >/dev/null 2>&1; then
    echo "==> ${APP_ID} is already installed for this user; skipping bundle install"
  else
    [[ -n "${flatpak_file}" ]] || fail "Screenux is not installed. Provide a local .flatpak bundle path as first argument."
    [[ -f "${flatpak_file}" ]] || fail "File not found: ${flatpak_file}"
    echo "==> Installing Flatpak bundle: ${flatpak_file}"
    flatpak install -y --user "${flatpak_file}"
  fi

  create_wrapper
  create_desktop_entry
}

main() {
  local use_print_screen="false"
  local restore_native_print="false"
  local positional=()

  while (($# > 0)); do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --print-screen)
        use_print_screen="true"
        ;;
      --restore-native-print)
        restore_native_print="true"
        ;;
      --)
        shift
        while (($# > 0)); do
          positional+=("$1")
          shift
        done
        break
        ;;
      -*)
        fail "Unknown option: $1"
        ;;
      *)
        positional+=("$1")
        ;;
    esac
    shift
  done

  if [[ "${restore_native_print}" == "true" ]]; then
    remove_screenux_shortcut
    restore_native_print_keys
    echo "==> Done. Native Print Screen behavior restored (GNOME)."
    exit 0
  fi

  local flatpak_file="${positional[0]:-}"
  local keybinding="${positional[1]:-${DEFAULT_KEYBINDING}}"

  if [[ "${use_print_screen}" == "true" ]]; then
    keybinding="${PRINT_KEYBINDING}"
  fi

  install_bundle "${flatpak_file}"

  configure_gnome_shortcut "${keybinding}"
  if [[ "${keybinding}" == "${PRINT_KEYBINDING}" ]]; then
    disable_native_print_keys
  fi

  echo "==> Done."
  echo "Run:"
  echo "  ${WRAPPER_PATH}"
  echo "Or capture directly:"
  echo "  ${WRAPPER_PATH} --capture"
}

main "$@"
