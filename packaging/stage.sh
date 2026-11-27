#!/bin/sh
# Раскладывает DockWatch по системным путям в каталог $1 (общий шаг для .deb и .rpm).
set -e
D="$1"; cd "$(dirname "$0")/.."
install -Dm755 dockwatch.py "$D/usr/share/dockwatch/dockwatch.py"
mkdir -p "$D/usr/share/dockwatch"
cp -r profiles data "$D/usr/share/dockwatch/"
[ -d plasmoid ] && cp -r plasmoid "$D/usr/share/dockwatch/"
find "$D/usr/share/dockwatch" -name '__pycache__' -prune -exec rm -rf {} +
install -dm755 "$D/usr/bin"
ln -sf /usr/share/dockwatch/dockwatch.py "$D/usr/bin/dockwatch"
install -Dm644 data/dockwatch.desktop "$D/usr/share/applications/dockwatch.desktop"
install -Dm644 data/dockwatch.svg "$D/usr/share/icons/hicolor/scalable/apps/dockwatch.svg"
install -Dm644 data/99-dockwatch.rules "$D/usr/lib/udev/rules.d/99-dockwatch.rules"
install -Dm644 LICENSE "$D/usr/share/licenses/dockwatch/LICENSE"
