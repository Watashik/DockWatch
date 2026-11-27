#!/bin/sh
# Установка для текущего пользователя: команда dockwatch, иконка и пункт в меню. Без root.
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
mkdir -p ~/.local/bin ~/.local/share/applications ~/.local/share/icons/hicolor/scalable/apps
ln -sf "$DIR/dockwatch.py" ~/.local/bin/dockwatch
chmod +x "$DIR/dockwatch.py"
cp data/dockwatch.svg ~/.local/share/icons/hicolor/scalable/apps/dockwatch.svg
# PNG-размеры: не все меню/панели берут SVG из пользовательской темы
python3 - <<PY 2>/dev/null || true
import os
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
app = QGuiApplication([])
r = QSvgRenderer("data/dockwatch.svg")
for n in (16, 22, 24, 32, 48, 64, 128, 256):
    d = os.path.expanduser(f"~/.local/share/icons/hicolor/{n}x{n}/apps")
    os.makedirs(d, exist_ok=True)
    img = QImage(n, n, QImage.Format_ARGB32); img.fill(Qt.transparent)
    p = QPainter(img); r.render(p); p.end()
    img.save(f"{d}/dockwatch.png")
PY
touch ~/.local/share/icons/hicolor
cp data/dockwatch.desktop ~/.local/share/applications/dockwatch.desktop
command -v update-desktop-database >/dev/null && update-desktop-database ~/.local/share/applications || true
command -v kbuildsycoca6 >/dev/null && kbuildsycoca6 >/dev/null 2>&1 || true
if [ "$1" = "--autostart" ]; then
  mkdir -p ~/.config/autostart
  printf '[Desktop Entry]\nType=Application\nName=DockWatch\nExec=dockwatch tray\nIcon=dockwatch\n' > ~/.config/autostart/dockwatch.desktop
  echo "autostart enabled"
fi
echo "dockwatch installed: run 'dockwatch' or find DockWatch in the app menu."
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "Add ~/.local/bin to PATH.";; esac
