# Screenux Screenshot

Simple, private screenshot tool for Linux desktops.

Screenux focuses on a clean capture flow: take a screenshot, optionally annotate it, and save locally with safe defaults.

## ✨ Why Screenux

- 🧭 Clean interface with one primary action and clear status messages
- 🔒 Local-first behavior (no cloud upload flow)
- 🖼️ Wayland-friendly capture via desktop portal APIs
- 📁 Practical folder defaults (Desktop, then Home fallback)

## 🧩 Features

- Capture with `Take Screenshot`
- Status updates: `Ready`, `Capturing...`, `Saved: <path>`, `Cancelled`, `Failed: <reason>`
- Built-in editor for quick annotations (shapes/text)
- Editor zoom controls with `Best fit` and quick presets (`33%` to `2000%`)
- Timestamped output names with safe, non-overwriting writes

## 🚀 Quick start

### 1) Install system dependencies

- `python3`
- `python3-gi`
- GTK4 introspection (`gir1.2-gtk-4.0` on Debian/Ubuntu)
- `xdg-desktop-portal` plus a desktop backend (GNOME/KDE/etc.)

### 2) Clone the project

```bash
git clone https://github.com/rafaself/Screenux.git
cd Screenux
```

### 3) Run Screenux

```bash
./screenux-screenshot
```

### 4) Install Flatpak bundle + optional GNOME shortcut

If you built or downloaded a Screenux Flatpak bundle, use the installer helper:

To build a local bundle first:

```bash
make build-flatpak-bundle FLATPAK_BUNDLE=./screenux-screenshot.flatpak
```

```bash
./install-screenux.sh ./screenux-screenshot.flatpak "['<Control><Shift>s']"

# if already installed for current user
./install-screenux.sh
```

Or with Make targets:

```bash
make install-flatpak [BUNDLE=./screenux-screenshot.flatpak]
```

Use Print Screen directly with Screenux (GNOME):

```bash
./install-screenux.sh --print-screen ./screenux-screenshot.flatpak

# if already installed for current user
./install-screenux.sh --print-screen

# or
make install [BUNDLE=./screenux-screenshot.flatpak]

# or (explicit target)
make install-print-screen [BUNDLE=./screenux-screenshot.flatpak]
```

Restore GNOME native Print Screen behavior:

```bash
./install-screenux.sh --restore-native-print

# or
make restore-native-print
```

Notes:

- The first argument is optional only when Screenux is already installed for the current user; otherwise provide a local `.flatpak` file.
- The second argument is optional and uses GNOME `gsettings` binding syntax.
- If Screenux is already installed for the current user, bundle install is skipped and only wrapper/shortcut setup is applied.
- On non-GNOME desktops, install still completes and shortcut setup is skipped.
- `--restore-native-print` removes the Screenux custom GNOME shortcut and resets GNOME screenshot keybindings.
- Installer internals are organized under `scripts/install/` with reusable helper modules.

## 🖱️ Usage

1. Launch the app.
2. Click `Take Screenshot`.
3. Confirm or cancel in the system screenshot flow.
4. (Optional) annotate in the editor.
5. Save and check the status line for the resulting file path.

Save folder behavior:

- Default target is Desktop.
- If Desktop is unavailable or not writable, Screenux falls back to Home.
- You can change the destination from the app (`Save to` → `Change…`).

## 🖼️ UI example

<img width="730" height="660" alt="image" src="https://github.com/user-attachments/assets/e7bf2baa-afe9-48a8-a84d-4f7126fde637" />

## 🛠️ Development

### Project layout

- `src/screenux_screenshot.py`: app entrypoint, config/path helpers, offline enforcement
- `src/screenux_window.py`: GTK window, portal flow, save-folder picker
- `src/screenux_editor.py`: annotation editor and secure file writing
- `tests/`: automated tests for path, window, screenshot, and editor logic
- `screenux-screenshot`: launcher script for host and Flatpak runtime

### Install dev dependencies

```bash
python3 -m pip install -r requirements-dev.txt
```

### Local dev run

```bash
./screenux-screenshot
```

## ✅ Testing

Run fast checks locally:

```bash
python3 -m py_compile src/screenux_screenshot.py
pytest -q
```

Manual sanity checklist:

1. App starts with `Ready`.
2. Capture shows `Capturing...` and returns to interactive state.
3. Save shows `Saved: <path>` and writes a file.
4. Cancel shows `Cancelled`.
5. Invalid/failed portal path shows `Failed: ...` with a clear reason.

## ⚙️ CI/CD

Main workflow: `.github/workflows/ci.yml`

Runs automatically on:

- Pull requests targeting `main`
- Pushes to `main`
- Published releases

Quality gates include:

- Compile validation (`python -m compileall -q src`)
- Automated tests (`pytest -q`)
- Security checks (`bandit`, `pip-audit`)
- Shell script hardening (`ShellCheck`, `shfmt`, policy checks, installer SHA256 artifact)
- Dependency checks (`pip check`, dependency review action)
- Build/package validation (launcher, Flatpak manifest, desktop entry, Docker Compose, Docker build)

Release artifacts workflow: `.github/workflows/release-artifacts.yml`

- Builds `screenux-screenshot.flatpak`
- Generates `screenux-screenshot.flatpak.sha256`
- Verifies installability in CI before publishing
- Uploads artifacts to workflow results and GitHub Release assets
- Uses least-privilege job permissions

## 📦 Packaging

### Docker (dev/build environment)

Use Docker for reproducible tests and checks (GUI screenshot capture is not intended for Docker):

```bash
# optional one-time setup
cp .env.example .env

export LOCAL_UID=$(id -u) LOCAL_GID=$(id -g)
docker compose build dev
docker compose run --rm dev python3 -m py_compile src/screenux_screenshot.py
docker compose run --rm dev pytest -q
docker compose run --rm dev bandit -q -r src -x tests
```

Notes:

- `dev` runs as host UID/GID (`LOCAL_UID`/`LOCAL_GID`, default `1000:1000`) to avoid root-owned files.
- You can store `LOCAL_UID` and `LOCAL_GID` in `.env` to avoid exporting every session.
- `.env` must be at repository root (same directory as `docker-compose.yml`) for Compose auto-loading.
- `.env` config is for Docker Compose only; Screenux runtime does not read it.
- Python bytecode and pytest cache are disabled in container runs to reduce bind-mount noise/permission issues.

### Flatpak

Requirements:

- `flatpak`
- `flatpak-builder`

Install tools (examples):

```bash
# Debian/Ubuntu
sudo apt-get install -y flatpak flatpak-builder

# Fedora
sudo dnf install -y flatpak flatpak-builder

# Arch
sudo pacman -S --needed flatpak flatpak-builder
```

Build a local bundle and install with Print Screen mapping:

```bash
make build-flatpak-bundle FLATPAK_BUNDLE=./screenux-screenshot.flatpak
make install-print-screen BUNDLE=./screenux-screenshot.flatpak
```

```bash
flatpak-builder --force-clean build-dir flatpak/io.github.rafa.ScreenuxScreenshot.json
flatpak-builder --run build-dir flatpak/io.github.rafa.ScreenuxScreenshot.json screenux-screenshot
```

Flatpak permissions stay intentionally narrow (portal access + Desktop filesystem).

## 🔐 Privacy & security

- Offline-only runtime behavior blocks networking and DNS calls.
- Screenshot sources are validated as local, readable `file://` URIs.
- Config parsing is defensive (invalid/non-object/oversized files are ignored).
- Save operations use exclusive file creation to avoid accidental overwrite.
