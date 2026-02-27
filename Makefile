SHELL := /usr/bin/env bash

INSTALLER := ./install-screenux.sh
DEFAULT_KEYBINDING := ['<Control><Shift>s']

.PHONY: help install-flatpak install-print-screen restore-native-print check-install-scripts

help:
	@echo "Screenux helper targets"
	@echo ""
	@echo "  make install-flatpak BUNDLE=./screenux-screenshot.flatpak [KEYBINDING=\"['Print']\"]"
	@echo "  make install-print-screen BUNDLE=./screenux-screenshot.flatpak"
	@echo "  make restore-native-print"
	@echo "  make check-install-scripts"

install-flatpak:
	@test -n "$(BUNDLE)" || (echo "Usage: make install-flatpak BUNDLE=./screenux-screenshot.flatpak [KEYBINDING=\"['Print']\"]" && exit 1)
	@binding="$(DEFAULT_KEYBINDING)"; \
	if [[ -n "$(KEYBINDING)" ]]; then binding="$(KEYBINDING)"; fi; \
	$(INSTALLER) "$(BUNDLE)" "$$binding"

install-print-screen:
	@test -n "$(BUNDLE)" || (echo "Usage: make install-print-screen BUNDLE=./screenux-screenshot.flatpak" && exit 1)
	@$(INSTALLER) --print-screen "$(BUNDLE)"

restore-native-print:
	@$(INSTALLER) --restore-native-print

check-install-scripts:
	@bash -n install-screenux.sh scripts/install/install-screenux.sh scripts/install/lib/common.sh scripts/install/lib/gnome_shortcuts.sh
	@echo "Installer scripts syntax: OK"
