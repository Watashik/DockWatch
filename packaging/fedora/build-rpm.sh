#!/bin/sh
# Сборка .rpm (Fedora 40+): sh packaging/fedora/build-rpm.sh  →  ~/rpmbuild/RPMS/noarch/dockwatch-*.rpm
set -e
cd "$(dirname "$0")/../.."
V=$(sed -n 's/^VERSION = "\(.*\)"/\1/p' dockwatch.py)
mkdir -p ~/rpmbuild/SOURCES
git archive --format=tar.gz --prefix="dockwatch-$V/" -o ~/rpmbuild/SOURCES/dockwatch-$V.tar.gz HEAD
rpmbuild -bb --define "ver $V" packaging/fedora/dockwatch.spec
ls ~/rpmbuild/RPMS/noarch/dockwatch-$V-*.rpm
