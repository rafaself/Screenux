#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/install/lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=scripts/install/lib/gnome_shortcuts.sh
source "${SCRIPT_DIR}/lib/gnome_shortcuts.sh"

usage() {
  cat <<'EOF'
Usage:
  ./uninstall-screenux.sh [--preserve-user-data]

Options:
  --preserve-user-data  Keep ~/.var/app/io.github.rafa.ScreenuxScreenshot
  -h, --help            Show this help
EOF
}

remove_flatpak_app() {
  if ! command -v flatpak >/dev/null 2>&1; then
    echo "NOTE: flatpak not found; skipping Flatpak uninstall."
    return 0
  fi

  if flatpak info --user "${APP_ID}" >/dev/null 2>&1; then
    echo "==> Uninstalling Flatpak app: ${APP_ID}"
    flatpak uninstall -y --user "${APP_ID}"
  else
    echo "==> ${APP_ID} is not installed for this user; skipping Flatpak uninstall"
  fi
}

cleanup_local_entries() {
  remove_wrapper
  remove_desktop_entry
  remove_icon_asset
  refresh_icon_cache
}

cleanup_shortcuts() {
  remove_screenux_shortcut
  restore_native_print_keys
}

validate_uninstall() {
  local preserve_user_data="$1"

  echo "==> Validating uninstall"

  if command -v flatpak >/dev/null 2>&1 && flatpak info --user "${APP_ID}" >/dev/null 2>&1; then
    fail "Validation failed: ${APP_ID} is still installed for current user."
  fi

  [[ ! -e "${WRAPPER_PATH}" && ! -L "${WRAPPER_PATH}" ]] || fail "Validation failed: wrapper still exists at ${WRAPPER_PATH}"
  [[ ! -e "${DESKTOP_FILE}" && ! -L "${DESKTOP_FILE}" ]] || fail "Validation failed: desktop entry still exists at ${DESKTOP_FILE}"
  [[ ! -e "${ICON_FILE}" && ! -L "${ICON_FILE}" ]] || fail "Validation failed: icon asset still exists at ${ICON_FILE}"
  [[ ! -e "${ICON_FILE_LIGHT}" && ! -L "${ICON_FILE_LIGHT}" ]] || fail "Validation failed: icon asset still exists at ${ICON_FILE_LIGHT}"
  [[ ! -e "${ICON_FILE_DARK}" && ! -L "${ICON_FILE_DARK}" ]] || fail "Validation failed: icon asset still exists at ${ICON_FILE_DARK}"

  if [[ "${preserve_user_data}" == "false" && -d "${APP_DATA_DIR}" ]]; then
    fail "Validation failed: user data still exists at ${APP_DATA_DIR}"
  fi
}

main() {
  local preserve_user_data="false"

  while (($# > 0)); do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --preserve-user-data)
        preserve_user_data="true"
        ;;
      -*)
        fail "Unknown option: $1"
        ;;
      *)
        fail "Unexpected positional argument: $1"
        ;;
    esac
    shift
  done

  remove_flatpak_app
  cleanup_local_entries
  cleanup_shortcuts

  if [[ "${preserve_user_data}" == "true" ]]; then
    echo "==> Preserving user data: ${APP_DATA_DIR}"
  else
    remove_app_data
  fi

  validate_uninstall "${preserve_user_data}"
  echo "==> Uninstall complete"
}

main "$@"
