#!/usr/bin/env bash
set -euo pipefail

APP_ID="io.github.rafa.ScreenuxScreenshot"
APP_NAME="Screenux Screenshot"
WRAPPER_DIR="${HOME}/.local/bin"
WRAPPER_PATH="${WRAPPER_DIR}/screenux-screenshot"
DESKTOP_DIR="${HOME}/.local/share/applications"
DESKTOP_FILE="${DESKTOP_DIR}/${APP_ID}.desktop"

SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA="${SCHEMA}.custom-keybinding"
KEY="custom-keybindings"
BASE_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"

usage() {
  cat <<'EOF'
Usage:
  ./install-screenux.sh /path/to/screenux-screenshot.flatpak "['<Control><Shift>s']"

Arguments:
  1) Flatpak bundle path (required)
  2) GNOME keybinding list syntax (optional, default: ['<Control><Shift>s'])

Examples:
  ./install-screenux.sh ./screenux-screenshot.flatpak
  ./install-screenux.sh ./screenux-screenshot.flatpak "['Print']"
EOF
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

check_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

strip_single_quotes() {
  local value="$1"
  value="${value#\'}"
  value="${value%\'}"
  printf '%s' "${value}"
}

path_in_array() {
  local needle="$1"
  shift
  local item
  for item in "$@"; do
    if [[ "${item}" == "${needle}" ]]; then
      return 0
    fi
  done
  return 1
}

build_gsettings_list() {
  local items=("$@")
  local out="["
  local i
  for ((i = 0; i < ${#items[@]}; i++)); do
    if ((i > 0)); then
      out+=", "
    fi
    out+="'${items[i]}'"
  done
  out+="]"
  printf '%s' "${out}"
}

configure_gnome_shortcut() {
  local binding="$1"

  if ! command -v gsettings >/dev/null 2>&1; then
    echo "NOTE: gsettings not available; skipping shortcut setup."
    return 0
  fi

  if ! gsettings list-schemas | grep -qx "${SCHEMA}"; then
    echo "NOTE: GNOME media-keys schema not found; skipping shortcut setup."
    return 0
  fi

  if [[ "${binding}" != \[*\] ]]; then
    fail "Keybinding must be a gsettings list, e.g. \"['Print']\" or \"['<Super>s']\""
  fi

  echo "==> Configuring GNOME custom shortcut: ${binding}"

  local existing
  existing="$(gsettings get "${SCHEMA}" "${KEY}")"

  local path_array=()
  mapfile -t path_array < <(printf '%s\n' "${existing}" | grep -oE "'${BASE_PATH}/custom[0-9]+/'" | tr -d "'" || true)

  local target_path=""
  local p current_name current_command
  for p in "${path_array[@]}"; do
    current_name="$(gsettings get "${CUSTOM_SCHEMA}:${p}" name 2>/dev/null || true)"
    current_command="$(gsettings get "${CUSTOM_SCHEMA}:${p}" command 2>/dev/null || true)"
    current_name="$(strip_single_quotes "${current_name}")"
    current_command="$(strip_single_quotes "${current_command}")"

    if [[ "${current_name}" == "${APP_NAME}" || "${current_command}" == "${WRAPPER_PATH} --capture" ]]; then
      target_path="${p}"
      break
    fi
  done

  if [[ -z "${target_path}" ]]; then
    local idx=0
    while :; do
      local candidate="${BASE_PATH}/custom${idx}/"
      if ! path_in_array "${candidate}" "${path_array[@]}"; then
        target_path="${candidate}"
        break
      fi
      ((idx += 1))
    done
  fi

  if ! path_in_array "${target_path}" "${path_array[@]}"; then
    path_array+=("${target_path}")
    gsettings set "${SCHEMA}" "${KEY}" "$(build_gsettings_list "${path_array[@]}")"
  fi

  gsettings set "${CUSTOM_SCHEMA}:${target_path}" name "${APP_NAME}"
  gsettings set "${CUSTOM_SCHEMA}:${target_path}" command "${WRAPPER_PATH} --capture"
  gsettings set "${CUSTOM_SCHEMA}:${target_path}" binding "${binding}"

  echo "==> GNOME shortcut configured"
  echo "    Name: ${APP_NAME}"
  echo "    Command: ${WRAPPER_PATH} --capture"
  echo "    Binding: ${binding}"
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    exit 0
  fi

  local flatpak_file="${1:-}"
  local keybinding="${2:-['<Control><Shift>s']}"

  [[ -n "${flatpak_file}" ]] || fail "Provide the .flatpak bundle path as first argument."
  [[ -f "${flatpak_file}" ]] || fail "File not found: ${flatpak_file}"

  check_command flatpak

  echo "==> Installing Flatpak bundle: ${flatpak_file}"
  flatpak install -y --user "${flatpak_file}"

  echo "==> Creating wrapper command: ${WRAPPER_PATH}"
  mkdir -p "${WRAPPER_DIR}"
  cat >"${WRAPPER_PATH}" <<EOF
#!/usr/bin/env bash
exec flatpak run ${APP_ID} "\$@"
EOF
  chmod +x "${WRAPPER_PATH}"

  if ! printf '%s\n' "${PATH}" | tr ':' '\n' | grep -qx "${WRAPPER_DIR}"; then
    echo "NOTE: ${WRAPPER_DIR} is not in PATH for this session."
    echo "      Add this to your shell profile (e.g. ~/.bashrc or ~/.zshrc):"
    echo "      export PATH=\"${WRAPPER_DIR}:\$PATH\""
  fi

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

  configure_gnome_shortcut "${keybinding}"

  echo "==> Done."
  echo "Run:"
  echo "  ${WRAPPER_PATH}"
  echo "Or capture directly:"
  echo "  ${WRAPPER_PATH} --capture"
}

main "$@"
