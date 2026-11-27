#!/bin/sh
# Сборка .deb (Debian 13+, Ubuntu 24.04+): sh packaging/debian/build-deb.sh  →  dockwatch_<версия>_all.deb
set -e
cd "$(dirname "$0")/../.."
V=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' dockwatch.py)
B=$(mktemp -d)/dockwatch
sh packaging/stage.sh "$B"
mkdir -p "$B/DEBIAN"
sed "s/@VERSION@/$V/" packaging/debian/control > "$B/DEBIAN/control"
dpkg-deb --root-owner-group --build "$B" "dockwatch_${V}_all.deb"
echo "dockwatch_${V}_all.deb"
