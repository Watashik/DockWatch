#!/bin/sh
# Установка для текущего пользователя: команда dockwatch, иконка и пункт в меню. Без root.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
ln -sf "$DIR/dockwatch.py" ~/.local/bin/dockwatch
chmod +x "$DIR/dockwatch.py"
cp data/dockwatch.svg ~/.local/share/icons/hicolor/scalable/apps/dockwatch.svg
cp data/dockwatch.desktop ~/.local/share/applications/dockwatch.desktop
command -v update-desktop-database >/dev/null && update-desktop-database ~/.local/share/applications || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
echo "dockwatch installed: run 'dockwatch' or find DockWatch in the app menu."
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "Add ~/.local/bin to PATH.";; esac
