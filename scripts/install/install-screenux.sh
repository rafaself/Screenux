#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/install/lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"
# shellcheck source=scripts/install/lib/gnome_shortcuts.sh
source "${SCRIPT_DIR}/lib/gnome_shortcuts.sh"

DEFAULT_BUNDLE_NAME="screenux-screenshot.flatpak"
PRINT_KEYBINDING="['Print']"

usage() {
  cat << 'EOF'
Usage:
  ./install-screenux.sh [--bundle /path/to/screenux-screenshot.flatpak] [--shortcut "['<Control><Shift>s']"]
  ./install-screenux.sh [--bundle /path/to/screenux-screenshot.flatpak] --print-screen

Options:
  --bundle PATH           Flatpak bundle path. If omitted and app is not installed, tries ./screenux-screenshot.flatpak
  --shortcut BINDING      Configure GNOME shortcut with gsettings list syntax
  --print-screen          Shortcut preset for ['Print'] + disable native GNOME Print bindings
  --no-shortcut           Skip shortcut setup (default)
  -h, --help              Show this help

Examples:
  ./install-screenux.sh
  ./install-screenux.sh --bundle ./screenux-screenshot.flatpak
  ./install-screenux.sh --bundle ./screenux-screenshot.flatpak --print-screen
  ./install-screenux.sh --bundle ./screenux-screenshot.flatpak --shortcut "['<Control><Shift>s']"
EOF
}

resolve_default_bundle() {
  if [[ -f "./${DEFAULT_BUNDLE_NAME}" ]]; then
    printf '%s' "./${DEFAULT_BUNDLE_NAME}"
    return 0
  fi

  local repo_bundle="${SCRIPT_DIR}/../../${DEFAULT_BUNDLE_NAME}"
  if [[ -f "${repo_bundle}" ]]; then
    printf '%s' "${repo_bundle}"
    return 0
  fi

  return 1
}

install_bundle() {
  local flatpak_file="$1"
  if ! command -v flatpak > /dev/null 2>&1; then
    fail "Required command not found: flatpak. Install Flatpak first, then rerun."
  fi

  if [[ -n "${flatpak_file}" ]]; then
    [[ -f "${flatpak_file}" ]] || fail "Flatpak bundle not found: ${flatpak_file}"
    echo "==> Installing Flatpak bundle: ${flatpak_file}"
    flatpak install -y --user --or-update "${flatpak_file}"
  elif flatpak info --user "${APP_ID}" > /dev/null 2>&1; then
    echo "==> ${APP_ID} is already installed for this user; skipping bundle install"
  else
    local inferred_bundle=""
    inferred_bundle="$(resolve_default_bundle || true)"
    [[ -n "${inferred_bundle}" ]] || fail "Bundle not provided and ${APP_ID} is not installed. Use --bundle /path/to/${DEFAULT_BUNDLE_NAME}."
    echo "==> Installing Flatpak bundle: ${inferred_bundle}"
    flatpak install -y --user --or-update "${inferred_bundle}"
  fi

  create_wrapper
  create_desktop_entry
  create_icon_asset
  refresh_icon_cache
}

validate_installation() {
  echo "==> Validating installation"

  if ! flatpak info --user "${APP_ID}" > /dev/null 2>&1; then
    fail "Validation failed: ${APP_ID} is not installed for current user."
  fi
  [[ -x "${WRAPPER_PATH}" ]] || fail "Validation failed: wrapper not executable at ${WRAPPER_PATH}"
  [[ -f "${DESKTOP_FILE}" ]] || fail "Validation failed: desktop entry missing at ${DESKTOP_FILE}"
  [[ -f "${ICON_FILE}" ]] || fail "Validation failed: icon asset missing at ${ICON_FILE}"
  [[ -f "${ICON_FILE_SVG}" ]] || fail "Validation failed: icon asset missing at ${ICON_FILE_SVG}"
  [[ -f "${ICON_FILE_LIGHT}" ]] || fail "Validation failed: icon asset missing at ${ICON_FILE_LIGHT}"
  [[ -f "${ICON_FILE_DARK}" ]] || fail "Validation failed: icon asset missing at ${ICON_FILE_DARK}"
}

configure_shortcut() {
  local shortcut_mode="$1"
  local keybinding="$2"

  case "${shortcut_mode}" in
    none)
      echo "==> Shortcut setup skipped"
      ;;
    custom)
      configure_gnome_shortcut "${keybinding}"
      ;;
    print)
      configure_gnome_shortcut "${PRINT_KEYBINDING}"
      disable_native_print_keys
      ;;
    *)
      fail "Unexpected shortcut mode: ${shortcut_mode}"
      ;;
  esac
}

main() {
  local bundle_path=""
  local shortcut_mode="none"
  local keybinding=""
  local shortcut_option_seen="false"
  local positional=()

  while (($# > 0)); do
    case "$1" in
      -h | --help)
        usage
        exit 0
        ;;
      --bundle)
        shift
        (($# > 0)) || fail "--bundle requires a path"
        bundle_path="$1"
        ;;
      --shortcut)
        shift
        (($# > 0)) || fail "--shortcut requires a binding list value"
        [[ "${shortcut_option_seen}" == "false" ]] || fail "Only one of --shortcut, --print-screen, or --no-shortcut can be used."
        shortcut_option_seen="true"
        shortcut_mode="custom"
        keybinding="$1"
        ;;
      --print-screen)
        [[ "${shortcut_option_seen}" == "false" ]] || fail "Only one of --shortcut, --print-screen, or --no-shortcut can be used."
        shortcut_option_seen="true"
        shortcut_mode="print"
        ;;
      --no-shortcut)
        [[ "${shortcut_option_seen}" == "false" ]] || fail "Only one of --shortcut, --print-screen, or --no-shortcut can be used."
        shortcut_option_seen="true"
        shortcut_mode="none"
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

  if ((${#positional[@]} > 1)); then
    fail "Unexpected positional arguments. Use --bundle PATH and optional shortcut flags."
  fi

  if [[ -z "${bundle_path}" && ${#positional[@]} -eq 1 ]]; then
    bundle_path="${positional[0]}"
  fi

  install_bundle "${bundle_path}"
  configure_shortcut "${shortcut_mode}" "${keybinding}"
  validate_installation

  echo "==> Installation complete"
  echo "Run:"
  echo "  ${WRAPPER_PATH}"
  echo "Or capture directly:"
  echo "  ${WRAPPER_PATH} --capture"
}

main "$@"
