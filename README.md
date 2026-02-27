# Screenux Screenshot

Simple, private screenshot tool for Linux desktops.

Screenux is built for people who want a clean screenshot flow without extra clutter. Open the app, capture your screen, make quick annotations if needed, and save locally.

## Why people use Screenux

- Clean interface: one main action, clear status messages.
- Local-first: screenshots stay on your machine.
- Wayland-friendly: uses desktop portal screenshot APIs.
- Practical defaults: saves to Desktop, then Home if Desktop is unavailable.

## What it does

- Capture via `Take Screenshot`.
- Show status updates: `Ready`, `Capturing...`, `Saved: <path>`, `Cancelled`, `Failed: <reason>`.
- Open an editor to add simple annotations (shapes/text) before saving.
- Save using timestamped filenames with safe, non-overwriting writes.

## Installation

### 1) System dependencies

Install:

- `python3`
- `python3-gi`
- GTK4 introspection (`gir1.2-gtk-4.0` on Debian/Ubuntu)
- `xdg-desktop-portal` with a desktop backend (GNOME/KDE/etc.)

### 2) Get the project

```bash
git clone https://github.com/rafaself/Screenux.git
cd Screenux
```

### 3) Start the app

```bash
./screenux-screenshot
```

## Usage

1. Launch the app.
2. Click `Take Screenshot`.
3. Confirm or cancel in your system screenshot flow.
4. (Optional) annotate in the editor.
5. Save and check the status line for the final file path.

Folder behavior:

- Default save folder is Desktop.
- If Desktop is not writable, it falls back to Home.
- You can change the target folder from the app (`Save to` → `Change…`).

## Development

### Project layout

- `src/screenux_screenshot.py`: app entrypoint, config, path helpers, offline enforcement
- `src/screenux_window.py`: GTK window, portal flow, save-folder picker
- `src/screenux_editor.py`: annotation editor and secure file writing
- `tests/`: automated tests for path, window, screenshot, and editor logic
- `screenux-screenshot`: launcher script used both on host and in Flatpak

### Local dev run

```bash
./screenux-screenshot
```

### Dev dependencies

```bash
python3 -m pip install -r requirements-dev.txt
```

## Testing

Run quick checks locally:

```bash
python3 -m py_compile src/screenux_screenshot.py
pytest -q
```

Manual sanity scenarios:

1. App starts with `Ready`.
2. Capture shows `Capturing...` and returns to interactive state.
3. Save shows `Saved: <path>` and creates a file.
4. Cancel shows `Cancelled`.
5. Invalid/failed portal path shows a clear `Failed: ...` message.

## CI

⚙️ This repository currently does not include a checked-in CI workflow.

Recommended CI baseline (same checks used locally):

- `python3 -m py_compile src/screenux_screenshot.py`
- `pytest -q`

If you want, you can add these commands to a GitHub Actions workflow under `.github/workflows/`.

## Packaging

### Docker (dev/build environment)

Use Docker for reproducible test runs (GUI screenshot capture is not meant to run in Docker):

```bash
docker compose build dev
docker compose run --rm dev python3 -m py_compile src/screenux_screenshot.py
docker compose run --rm dev pytest -q
```

### Flatpak

📦 Build and run locally:

```bash
flatpak-builder --force-clean build-dir flatpak/io.github.rafa.ScreenuxScreenshot.json
flatpak-builder --run build-dir flatpak/io.github.rafa.ScreenuxScreenshot.json screenux-screenshot
```

Flatpak permissions are intentionally narrow (portal access + Desktop filesystem).

## Privacy and security notes

- Offline-only runtime behavior: networking and DNS calls are blocked.
- Screenshot source validation accepts only local, readable `file://` URIs.
- Config parsing is defensive (invalid/non-object/oversized config files are ignored).
- Saved files are created with exclusive mode to avoid accidental overwrite.
