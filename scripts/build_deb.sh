#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

APP_NAME="${APP_NAME:-screenux-screenshot}"
APP_VERSION="${APP_VERSION:-0.1.0}"
APP_ARCH="${APP_ARCH:-amd64}"
OUT_DIR="${OUT_DIR:-/out}"

BUILD_WORKDIR="$(mktemp -d -t "${APP_NAME}-deb-XXXXXX")"
PKG_ROOT="${BUILD_WORKDIR}/pkg"
DEBIAN_DIR="${PKG_ROOT}/DEBIAN"
DEB_FILE="${BUILD_WORKDIR}/${APP_NAME}_${APP_VERSION}_${APP_ARCH}.deb"
VENV_DIR="${VENV_DIR:-${BUILD_WORKDIR}/venv}"

cleanup() {
  rm -rf -- "${BUILD_WORKDIR}"
}
trap cleanup EXIT

cd "${ROOT_DIR}"

python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --upgrade pip
"${VENV_DIR}/bin/pip" install "pyinstaller==6.*"

rm -rf -- "${ROOT_DIR}/build" "${ROOT_DIR}/dist" "${ROOT_DIR}/${APP_NAME}.spec"

"${VENV_DIR}/bin/pyinstaller" \
  --onefile \
  --name "${APP_NAME}" \
  --paths "${ROOT_DIR}/src" \
  --hidden-import "screenux_window" \
  --hidden-import "screenux_editor" \
  --hidden-import "screenux_hotkey" \
  --hidden-import "gi" \
  --hidden-import "gi.repository.Gio" \
  --hidden-import "gi.repository.GLib" \
  --hidden-import "gi.repository.Gtk" \
  --hidden-import "cairo" \
  --add-data "${ROOT_DIR}/src/icons:icons" \
  "${ROOT_DIR}/src/screenux_screenshot.py"

mkdir -p "${DEBIAN_DIR}"
cat > "${DEBIAN_DIR}/control" <<EOF
Package: ${APP_NAME}
Version: ${APP_VERSION}
Section: utils
Priority: optional
Architecture: ${APP_ARCH}
Maintainer: Screenux Developers <noreply@example.com>
Description: Screenux Screenshot utility
 Offline-first Linux screenshot utility with optional annotation editor.
EOF

install -Dm755 \
  "${ROOT_DIR}/dist/${APP_NAME}" \
  "${PKG_ROOT}/usr/bin/${APP_NAME}"
install -Dm644 \
  "${ROOT_DIR}/packaging/linux/${APP_NAME}.desktop" \
  "${PKG_ROOT}/usr/share/applications/${APP_NAME}.desktop"
install -Dm644 \
  "${ROOT_DIR}/packaging/linux/${APP_NAME}.png" \
  "${PKG_ROOT}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"

dpkg-deb --build --root-owner-group "${PKG_ROOT}" "${DEB_FILE}"

mkdir -p "${OUT_DIR}"
cp -f -- "${DEB_FILE}" "${OUT_DIR}/${APP_NAME}_${APP_VERSION}_${APP_ARCH}.deb"
echo "Built package: ${OUT_DIR}/${APP_NAME}_${APP_VERSION}_${APP_ARCH}.deb"
