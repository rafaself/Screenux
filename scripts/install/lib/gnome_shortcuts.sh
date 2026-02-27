#!/usr/bin/env bash
set -euo pipefail

SCHEMA="org.gnome.settings-daemon.plugins.media-keys"
CUSTOM_SCHEMA="${SCHEMA}.custom-keybinding"
KEY="custom-keybindings"
BASE_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings"
SHELL_SCHEMA="org.gnome.shell.keybindings"

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
  grep -oE "'${BASE_PATH}/custom[0-9]+/'" <<< "${existing}" | tr -d "'" || true
}

find_screenux_path() {
  local p current_name current_command
  while IFS= read -r p; do
    [[ -n "${p}" ]] || continue
    current_name="$(gsettings get "${CUSTOM_SCHEMA}:${p}" name 2> /dev/null || true)"
    current_command="$(gsettings get "${CUSTOM_SCHEMA}:${p}" command 2> /dev/null || true)"
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
  if ! command -v gsettings > /dev/null 2>&1; then
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
  if ! command -v gsettings > /dev/null 2>&1; then
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
  if ! command -v gsettings > /dev/null 2>&1; then
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

  if ! command -v gsettings > /dev/null 2>&1; then
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
