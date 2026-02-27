#!/usr/bin/env bash
set -euo pipefail

APP_ID="io.github.rafa.ScreenuxScreenshot"
APP_NAME="Screenux Screenshot"
WRAPPER_DIR="${HOME}/.local/bin"
WRAPPER_PATH="${WRAPPER_DIR}/screenux-screenshot"
DESKTOP_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${DESKTOP_DIR}/${APP_ID}.desktop"

DEFAULT_KEYBINDING="['<Control><Shift>s']"
PRINT_KEYBINDING="['Print']"

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
