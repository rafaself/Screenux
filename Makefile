SHELL := /usr/bin/env bash

INSTALLER := ./install-screenux.sh
DEFAULT_KEYBINDING := ['<Control><Shift>s']
APP_ID := io.github.rafa.ScreenuxScreenshot
FLATPAK_MANIFEST := flatpak/io.github.rafa.ScreenuxScreenshot.json
FLATPAK_BUILD_DIR ?= build-dir
FLATPAK_REPO_DIR ?= repo
FLATPAK_BUNDLE ?= ./screenux-screenshot.flatpak
BUNDLE ?= $(FLATPAK_BUNDLE)
FLATPAK_REMOTE ?= flathub
FLATPAK_REMOTE_URL ?= https://flathub.org/repo/flathub.flatpakrepo
FLATPAK_RUNTIME_VERSION ?= 47
FLATPAK_PLATFORM_REF ?= org.gnome.Platform//$(FLATPAK_RUNTIME_VERSION)
FLATPAK_SDK_REF ?= org.gnome.Sdk//$(FLATPAK_RUNTIME_VERSION)

.PHONY: help build-flatpak-bundle ensure-flatpak-build-deps install install-flatpak install-print-screen restore-native-print check-install-scripts

help:
	@echo "Screenux helper targets"
	@echo ""
	@echo "  make build-flatpak-bundle [FLATPAK_BUNDLE=./screenux-screenshot.flatpak]"
	@echo "  make install [BUNDLE=./screenux-screenshot.flatpak] (auto-builds bundle if needed)"
	@echo "  make install-flatpak [BUNDLE=./screenux-screenshot.flatpak] [KEYBINDING=\"['Print']\"]"
	@echo "  make install-print-screen [BUNDLE=./screenux-screenshot.flatpak]"
	@echo "  make restore-native-print"
	@echo "  make check-install-scripts"

build-flatpak-bundle: ensure-flatpak-build-deps
	@command -v flatpak-builder >/dev/null 2>&1 || ( \
		echo "flatpak-builder not found."; \
		echo "Install it, then retry:"; \
		echo "  Debian/Ubuntu: sudo apt-get install -y flatpak-builder flatpak"; \
		echo "  Fedora:        sudo dnf install -y flatpak-builder flatpak"; \
		echo "  Arch:          sudo pacman -S --needed flatpak-builder flatpak"; \
		exit 1)
	@flatpak-builder --force-clean --repo="$(FLATPAK_REPO_DIR)" "$(FLATPAK_BUILD_DIR)" "$(FLATPAK_MANIFEST)"
	@flatpak build-bundle "$(FLATPAK_REPO_DIR)" "$(FLATPAK_BUNDLE)" io.github.rafa.ScreenuxScreenshot
	@echo "Bundle created: $(FLATPAK_BUNDLE)"

ensure-flatpak-build-deps:
	@command -v flatpak >/dev/null 2>&1 || ( \
		echo "flatpak not found."; \
		echo "Install it, then retry:"; \
		echo "  Debian/Ubuntu: sudo apt-get install -y flatpak"; \
		echo "  Fedora:        sudo dnf install -y flatpak"; \
		echo "  Arch:          sudo pacman -S --needed flatpak"; \
		exit 1)
	@if flatpak info "$(FLATPAK_PLATFORM_REF)" >/dev/null 2>&1 && flatpak info "$(FLATPAK_SDK_REF)" >/dev/null 2>&1; then \
		echo "Flatpak runtime deps already installed ($(FLATPAK_RUNTIME_VERSION))."; \
	else \
		echo "Installing missing Flatpak runtime deps: $(FLATPAK_PLATFORM_REF), $(FLATPAK_SDK_REF)"; \
		flatpak remote-add --user --if-not-exists "$(FLATPAK_REMOTE)" "$(FLATPAK_REMOTE_URL)"; \
		flatpak install -y --user "$(FLATPAK_REMOTE)" "$(FLATPAK_PLATFORM_REF)" "$(FLATPAK_SDK_REF)"; \
	fi

install-flatpak:
	@binding="$(DEFAULT_KEYBINDING)"; \
	if [[ -n "$(KEYBINDING)" ]]; then binding="$(KEYBINDING)"; fi; \
	$(INSTALLER) "$(BUNDLE)" "$$binding"

install:
	@if [[ -f "$(BUNDLE)" ]]; then \
		$(INSTALLER) --print-screen "$(BUNDLE)"; \
	elif command -v flatpak >/dev/null 2>&1 && flatpak info --user "$(APP_ID)" >/dev/null 2>&1; then \
		$(INSTALLER) --print-screen; \
	elif command -v flatpak-builder >/dev/null 2>&1; then \
		$(MAKE) build-flatpak-bundle FLATPAK_BUNDLE="$(BUNDLE)"; \
		$(INSTALLER) --print-screen "$(BUNDLE)"; \
	else \
		echo "Screenux is not installed and bundle not found: $(BUNDLE)"; \
		echo "Install flatpak-builder to auto-build, or pass an existing bundle:"; \
		echo "  make install BUNDLE=./screenux-screenshot.flatpak"; \
		echo "  make build-flatpak-bundle FLATPAK_BUNDLE=./screenux-screenshot.flatpak"; \
		exit 1; \
	fi

install-print-screen:
	@$(INSTALLER) --print-screen "$(BUNDLE)"

restore-native-print:
	@$(INSTALLER) --restore-native-print

check-install-scripts:
	@bash -n install-screenux.sh scripts/install/install-screenux.sh scripts/install/lib/common.sh scripts/install/lib/gnome_shortcuts.sh
	@echo "Installer scripts syntax: OK"
