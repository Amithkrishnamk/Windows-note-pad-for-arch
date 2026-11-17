#!/usr/bin/env bash
# Remove the per-user Notepad installation.
#
# Usage: ./uninstall.sh [--yes] [--purge]
#   --yes    do not ask for confirmation
#   --purge  also remove saved settings (~/.config/NotepadLinux)
set -euo pipefail

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/notepad"
BIN_PATH="$HOME/.local/bin/notepad"
APPLICATIONS_DIR="$DATA_HOME/applications"
DESKTOP_PATH="$APPLICATIONS_DIR/notepad.desktop"
ICON_BASE="$DATA_HOME/icons/hicolor"

assume_yes=0
purge=0
for arg in "$@"; do
    case "$arg" in
        -y|--yes) assume_yes=1 ;;
        --purge) purge=1 ;;
        -h|--help)
            sed -n '2,6p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
    esac
done

if [ "$assume_yes" -eq 0 ]; then
    printf 'Remove Notepad, its launcher, menu entry and icons? [y/N] '
    read -r reply || reply=""
    case "$reply" in
        y|Y|yes|YES) ;;
        *) echo "Cancelled."; exit 0 ;;
    esac
fi

printf 'Removing Notepad...\n'

if command -v xdg-icon-resource >/dev/null 2>&1; then
    for size in 256 128 64 48 32; do
        xdg-icon-resource uninstall --context apps --size "$size" notepad \
            >/dev/null 2>&1 || true
    done
fi
for size in 256 128 64 48 32; do
    rm -f "$ICON_BASE/${size}x${size}/apps/notepad.png"
done
rm -f "$ICON_BASE/scalable/apps/notepad.svg"

rm -f "$BIN_PATH" "$DESKTOP_PATH"
rm -rf "$APP_DIR"

if [ "$purge" -eq 1 ]; then
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/NotepadLinux"
    printf 'Removed saved settings.\n'
fi
command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database "$APPLICATIONS_DIR" >/dev/null 2>&1 || true
if [ -f "$ICON_BASE/index.theme" ] && command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$ICON_BASE" >/dev/null 2>&1 || true
fi

printf 'Notepad was removed.\n'
if [ "$purge" -eq 0 ] && [ -d "${XDG_CONFIG_HOME:-$HOME/.config}/NotepadLinux" ]; then
    printf 'Saved settings were kept in %s/NotepadLinux (use --purge to remove them).\n' "${XDG_CONFIG_HOME:-$HOME/.config}"
fi
