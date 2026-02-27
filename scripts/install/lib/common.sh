#!/usr/bin/env bash
set -euo pipefail

APP_ID="io.github.rafa.ScreenuxScreenshot"
APP_NAME="Screenux Screenshot"
WRAPPER_DIR="${HOME}/.local/bin"
WRAPPER_PATH="${WRAPPER_DIR}/screenux-screenshot"
DESKTOP_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${DESKTOP_DIR}/${APP_ID}.desktop"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
ICON_FILE="${ICON_DIR}/${APP_ID}.svg"
ICON_FILE_LIGHT="${ICON_DIR}/${APP_ID}-light.svg"
ICON_FILE_DARK="${ICON_DIR}/${APP_ID}-dark.svg"
APP_DATA_DIR="${HOME}/.var/app/${APP_ID}"
COMMON_LIB_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_ICON_SOURCE="${COMMON_LIB_DIR}/../../../assets/icons/${APP_ID}.svg"
APP_ICON_LIGHT_SOURCE="${COMMON_LIB_DIR}/../../../assets/icons/${APP_ID}-light.svg"
APP_ICON_DARK_SOURCE="${COMMON_LIB_DIR}/../../../assets/icons/${APP_ID}-dark.svg"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

check_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

ensure_wrapper_path_notice() {
  if ! printf '%s\n' "${PATH}" | tr ':' '\n' | grep -qx "${WRAPPER_DIR}"; then
    echo "NOTE: ${WRAPPER_DIR} is not in PATH for this session."
    echo "      Add this to your shell profile (e.g. ~/.bashrc or ~/.zshrc):"
    echo "      export PATH=\"${WRAPPER_DIR}:\$PATH\""
  fi
}

create_wrapper() {
  echo "==> Creating wrapper command: ${WRAPPER_PATH}"
  mkdir -p "${WRAPPER_DIR}"
  cat >"${WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
exec flatpak run ${APP_ID} "\$@"
EOF
  chmod +x "${WRAPPER_PATH}"
  ensure_wrapper_path_notice
}

create_desktop_entry() {
  echo "==> Creating desktop entry: ${DESKTOP_FILE}"
  mkdir -p "${DESKTOP_DIR}"
  cat >"${DESKTOP_FILE}" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Exec=${WRAPPER_PATH}
Icon=${APP_ID}
Terminal=false
Categories=Utility;Graphics;
EOF
}

create_icon_asset() {
  [[ -f "${APP_ICON_SOURCE}" ]] || fail "App icon source file not found: ${APP_ICON_SOURCE}"
  [[ -f "${APP_ICON_LIGHT_SOURCE}" ]] || fail "App icon source file not found: ${APP_ICON_LIGHT_SOURCE}"
  [[ -f "${APP_ICON_DARK_SOURCE}" ]] || fail "App icon source file not found: ${APP_ICON_DARK_SOURCE}"
  echo "==> Installing app icon: ${ICON_FILE}"
  mkdir -p "${ICON_DIR}"
  cp -f -- "${APP_ICON_SOURCE}" "${ICON_FILE}"
  cp -f -- "${APP_ICON_LIGHT_SOURCE}" "${ICON_FILE_LIGHT}"
  cp -f -- "${APP_ICON_DARK_SOURCE}" "${ICON_FILE_DARK}"
}

remove_wrapper() {
  if [[ -e "${WRAPPER_PATH}" || -L "${WRAPPER_PATH}" ]]; then
    echo "==> Removing wrapper command: ${WRAPPER_PATH}"
    rm -f -- "${WRAPPER_PATH}"
  fi
}

remove_desktop_entry() {
  if [[ -e "${DESKTOP_FILE}" || -L "${DESKTOP_FILE}" ]]; then
    echo "==> Removing desktop entry: ${DESKTOP_FILE}"
    rm -f -- "${DESKTOP_FILE}"
  fi
}

remove_icon_asset() {
  if [[ -e "${ICON_FILE}" || -L "${ICON_FILE}" || -e "${ICON_FILE_LIGHT}" || -L "${ICON_FILE_LIGHT}" || -e "${ICON_FILE_DARK}" || -L "${ICON_FILE_DARK}" ]]; then
    echo "==> Removing app icon files from: ${ICON_DIR}"
    rm -f -- "${ICON_FILE}" "${ICON_FILE_LIGHT}" "${ICON_FILE_DARK}"
  fi
}

remove_app_data() {
  if [[ -d "${APP_DATA_DIR}" ]]; then
    echo "==> Removing user data: ${APP_DATA_DIR}"
    rm -rf -- "${APP_DATA_DIR}"
  fi
}

refresh_icon_cache() {
  local icon_theme_root="${HOME}/.local/share/icons/hicolor"
  if [[ ! -d "${icon_theme_root}" ]]; then
    return 0
  fi

  if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
    gtk4-update-icon-cache -f -t "${icon_theme_root}" >/dev/null 2>&1 || true
    return 0
  fi

  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "${icon_theme_root}" >/dev/null 2>&1 || true
  fi
}
