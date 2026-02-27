# Screenux Screenshot

Minimal Linux desktop screenshot app built with Python + GTK4 and xdg-desktop-portal.

## Features

- One button: `Take Screenshot`
- One status line: `Ready`, `Capturing...`, `Saved: <path>`, `Cancelled`, `Failed: <reason>`
- Wayland-compatible capture through `org.freedesktop.portal.Screenshot`
- Saves to Desktop with timestamped filename
- Falls back to Home when Desktop is unavailable
- Enforces offline-only runtime behavior (no network operations)
- Uses secure, non-overwriting image writes and strict local file URI validation

## Security Posture

- Offline-only: Python-level networking and DNS resolution are blocked at runtime.
- Least privilege: Flatpak requests only portal access and Desktop filesystem access (no full Home access).
- Safe file handling: output writes use exclusive create mode to avoid overwriting existing files.
- Defensive loading: screenshot sources must be local `file://` URIs that resolve to readable regular files.
- Defensive config parsing: invalid, non-object, or oversized config files are ignored.

## Project Layout

- `src/screenux_screenshot.py`: entrypoint + config/path helpers
- `src/screenux_window.py`: main window and portal flow
- `src/screenux_editor.py`: annotation editor and image rendering
- `screenux-screenshot`: launcher script
- `io.github.rafa.ScreenuxScreenshot.desktop`: desktop entry
- `flatpak/io.github.rafa.ScreenuxScreenshot.json`: Flatpak manifest
- `docker/Dockerfile.dev`: Docker dev/build image
- `docker-compose.yml`: Docker Compose service
- `tests/test_paths.py`: automated tests for save-path logic

## Run on Host

### Dependencies

- `python3`
- `python3-gi`
- GTK4 introspection (`gir1.2-gtk-4.0` on Debian/Ubuntu)
- `xdg-desktop-portal` with a desktop backend (GNOME/KDE/etc.)

### Run

```bash
./screenux-screenshot
```

## Automated Checks

Install test dependencies (once):

```bash
python3 -m pip install -r requirements-dev.txt
```

```bash
python3 -m py_compile src/screenux_screenshot.py
pytest -q
```

## Docker (Dev/Build Only)

Use Docker for reproducible checks. GUI capture is not intended to run inside Docker.

```bash
docker compose build dev
docker compose run --rm dev python3 -m py_compile src/screenux_screenshot.py
docker compose run --rm dev pytest -q
```

## Flatpak

Build and run locally:

```bash
flatpak-builder --force-clean build-dir flatpak/io.github.rafa.ScreenuxScreenshot.json
flatpak-builder --run build-dir flatpak/io.github.rafa.ScreenuxScreenshot.json screenux-screenshot
```

## Manual Test Scenarios

1. Launch app and verify status starts as `Ready`.
2. Click `Take Screenshot`; verify status becomes `Capturing...`.
3. Complete capture; verify status shows `Saved: <path>` and file exists.
4. Cancel capture; verify status becomes `Cancelled`.
5. Verify Desktop-missing fallback saves under Home.
6. Stop portal service to verify failure status and button recovery.
