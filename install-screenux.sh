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
SHELL_SCHEMA="org.gnome.shell.keybindings"

usage() {
  cat <<'EOF'
Usage:
  ./install-screenux.sh [--print-screen] /path/to/screenux-screenshot.flatpak "['<Control><Shift>s']"
  ./install-screenux.sh --restore-native-print

Arguments:
  1) Flatpak bundle path (required for install mode)
  2) GNOME keybinding list syntax (optional, default: ['<Control><Shift>s'])

Options:
  --print-screen          Bind Screenux to ['Print'] and disable GNOME native Print keys
  --restore-native-print  Remove Screenux shortcut (if present) and restore native GNOME Print keys
  -h, --help              Show this help

Examples:
  ./install-screenux.sh ./screenux-screenshot.flatpak
  ./install-screenux.sh --print-screen ./screenux-screenshot.flatpak
  ./install-screenux.sh ./screenux-screenshot.flatpak "['Print']"
  ./install-screenux.sh --restore-native-print
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

schema_exists() {
  local schema="$1"
  gsettings list-schemas | grep -qx "${schema}"
}

key_exists() {
  local schema="$1"
  local key="$2"
  gsettings list-keys "${schema}" | grep -qx "${key}"
}

get_custom_paths() {
  local existing
  existing="$(gsettings get "${SCHEMA}" "${KEY}")"
  grep -oE "'${BASE_PATH}/custom[0-9]+/'" <<<"${existing}" | tr -d "'" || true
}

find_screenux_path() {
  local p current_name current_command
  while IFS= read -r p; do
    [[ -n "${p}" ]] || continue
    current_name="$(gsettings get "${CUSTOM_SCHEMA}:${p}" name 2>/dev/null || true)"
    current_command="$(gsettings get "${CUSTOM_SCHEMA}:${p}" command 2>/dev/null || true)"
    current_name="$(strip_single_quotes "${current_name}")"
    current_command="$(strip_single_quotes "${current_command}")"
    if [[ "${current_name}" == "${APP_NAME}" || "${current_command}" == "${WRAPPER_PATH} --capture" ]]; then
      printf '%s' "${p}"
      return 0
    fi
  done < <(get_custom_paths)
  return 1
}

remove_screenux_shortcut() {
  if ! command -v gsettings >/dev/null 2>&1; then
    return 0
  fi
  if ! schema_exists "${SCHEMA}"; then
    return 0
  fi

  local screenux_path
  screenux_path="$(find_screenux_path || true)"
  [[ -n "${screenux_path}" ]] || return 0

  local path_array=()
  mapfile -t path_array < <(get_custom_paths)

  local updated_paths=()
  local p
  for p in "${path_array[@]}"; do
    if [[ "${p}" != "${screenux_path}" ]]; then
      updated_paths+=("${p}")
    fi
  done

  gsettings set "${SCHEMA}" "${KEY}" "$(build_gsettings_list "${updated_paths[@]}")"
  echo "==> Removed Screenux GNOME custom shortcut: ${screenux_path}"
}

set_key_if_exists() {
  local schema="$1"
  local key="$2"
  local value="$3"
  if schema_exists "${schema}" && key_exists "${schema}" "${key}"; then
    gsettings set "${schema}" "${key}" "${value}"
    return 0
  fi
  return 1
}

reset_key_if_exists() {
  local schema="$1"
  local key="$2"
  if schema_exists "${schema}" && key_exists "${schema}" "${key}"; then
    gsettings reset "${schema}" "${key}"
    return 0
  fi
  return 1
}

disable_native_print_keys() {
  if ! command -v gsettings >/dev/null 2>&1; then
    echo "NOTE: gsettings not available; cannot disable native Print bindings."
    return 0
  fi

  set_key_if_exists "${SHELL_SCHEMA}" "show-screenshot" "[]" || true
  set_key_if_exists "${SHELL_SCHEMA}" "show-screenshot-ui" "[]" || true
  set_key_if_exists "${SHELL_SCHEMA}" "show-screen-recording-ui" "[]" || true

  set_key_if_exists "${SCHEMA}" "screenshot" "[]" || true
  set_key_if_exists "${SCHEMA}" "window-screenshot" "[]" || true
  set_key_if_exists "${SCHEMA}" "area-screenshot" "[]" || true

  echo "==> Native GNOME Print Screen bindings disabled"
}

restore_native_print_keys() {
  if ! command -v gsettings >/dev/null 2>&1; then
    echo "NOTE: gsettings not available; cannot restore native Print bindings."
    return 0
  fi

  reset_key_if_exists "${SHELL_SCHEMA}" "show-screenshot" || true
  reset_key_if_exists "${SHELL_SCHEMA}" "show-screenshot-ui" || true
  reset_key_if_exists "${SHELL_SCHEMA}" "show-screen-recording-ui" || true

  reset_key_if_exists "${SCHEMA}" "screenshot" || true
  reset_key_if_exists "${SCHEMA}" "window-screenshot" || true
  reset_key_if_exists "${SCHEMA}" "area-screenshot" || true

  echo "==> Native GNOME Print Screen bindings restored"
}

configure_gnome_shortcut() {
  local binding="$1"

  if ! command -v gsettings >/dev/null 2>&1; then
    echo "NOTE: gsettings not available; skipping shortcut setup."
    return 0
  fi

  if ! schema_exists "${SCHEMA}"; then
    echo "NOTE: GNOME media-keys schema not found; skipping shortcut setup."
    return 0
  fi

  if [[ "${binding}" != \[*\] ]]; then
    fail "Keybinding must be a gsettings list, e.g. \"['Print']\" or \"['<Super>s']\""
  fi

  echo "==> Configuring GNOME custom shortcut: ${binding}"

  local path_array=()
  mapfile -t path_array < <(get_custom_paths)

  local target_path=""
  target_path="$(find_screenux_path || true)"

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
  local keybinding="${positional[1]:-['<Control><Shift>s']}"

  if [[ "${use_print_screen}" == "true" ]]; then
    keybinding="['Print']"
  fi

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

  if [[ "${keybinding}" == "['Print']" ]]; then
    disable_native_print_keys
  fi

  echo "==> Done."
  echo "Run:"
  echo "  ${WRAPPER_PATH}"
  echo "Or capture directly:"
  echo "  ${WRAPPER_PATH} --capture"
}

main "$@"
