#!/bin/sh
# Optional, needs root: lets DockWatch blink the red dot on the ThinkPad lid. Nothing else.
set -e
cd "$(dirname "$0")"
install -Dm644 data/99-dockwatch.rules /etc/udev/rules.d/99-dockwatch.rules
udevadm control --reload
udevadm trigger --action=add --subsystem-match=leds --sysname-match='tpacpi::lid_logo_dot' || true
echo "Done. If your user is not in the 'users' group: sudo usermod -aG users \$USER (and log in again)."
