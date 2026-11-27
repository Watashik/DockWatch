# DockWatch

Live port map of your **docking station and laptop**, in ThinkPad style. It shows which connectors are in use,
what is plugged into each one, how much power and bandwidth it takes, and pops up a notification on plug/unplug.

![screenshot](docs/screenshot.png)

| IBM theme | Light theme |
|---|---|
| ![IBM](docs/theme-ibm.png) | ![Light](docs/theme-light.png) |

Screenshots in other languages: [українська](docs/screenshot-uk.png) · [русский](docs/screenshot-ru.png)

**Languages:** українська · русский · English (auto from `$LANG`; switch in the menu or with `--lang`).

## Features
- Real port layout of the dock (rear panel) and the laptop sides; connectors glow red when in use.
- Per port: device name, USB speed, declared current, **disk read/write and network speed** with a one-minute sparkline,
  USB-C **Power Delivery** role and current, LAN speed and traffic.
- Phones: detects the USB mode (MTP file transfer, PTP, ADB, tethering, MIDI).
- SD card slot, 3.5 mm jack (headphones / headset), HDMI/DP/VGA monitors (name from EDID, resolution).
- Header: camera and microphones state (in use by which app, muted), F1/F4 mute LEDs, sound volume,
  battery level, wear and cycles, power profile, Wi‑Fi network, connected Bluetooth devices with battery.
- Temperatures (CPU/GPU/SSD) and fan RPM under the vent grille, which glows as the laptop heats up.
- Right-click a port with a drive: **open** it or **safely remove** it.
- "Don't forget your flash drive" reminder when you undock or close the lid with a drive still mounted.
- Connection log (`~/.local/share/dockwatch/history.log`), start at login, power profile switching.
- ThinkPad extra: blink the red dot on the lid when something is plugged in (needs a small udev rule).
- A USB-C that is also the dock connector is shown as USB-C when undocked and as the dock when docked.
- **Settings window**: language, theme, scale, sound, animations, options; rename ports; give your own names to devices
  (recognised by serial number — right-click a port → *Rename device*).
- **Themes**: ThinkPad (black, red), IBM (red/green/blue accents and the striped IBM logo), Light (white ports and keys).
- Smooth glow when a port lights up, a fan icon spinning at the real RPM, a short chime on plug/unplug (can be turned off).
- **Plasma 6 panel widget**: dock icon with the number of busy ports, click for the list (installed by `install.sh`;
  right-click the panel → Add Widgets → DockWatch).
- `dockwatch json` — machine-readable state for scripts and widgets.

## Views
| Command | What it does |
|---|---|
| `dockwatch` | window + tray icon; closing the window keeps it in the tray, a second launch just shows the window |
| `dockwatch tray` | start hidden in the tray (used for autostart) |
| `dockwatch gui` | window only |
| `dockwatch tui` | terminal version (curses) |
| `dockwatch dump` | plain-text state |
| `dockwatch calibrate` | bind system USB ports to physical connectors: plug a flash drive into each one |

## Install
```sh
git clone https://github.com/Watashik/DockWatch && cd DockWatch
./install.sh               # `dockwatch` command, menu entry and icon (per user, no root)
./install.sh --autostart   # same + start in the tray at login
sudo ./install-root.sh     # optional: allow blinking the ThinkPad lid dot
```
Arch/CachyOS: an AUR `PKGBUILD` is in `packaging/aur/`.

Fedora:
```sh
sudo dnf install python3-pyside6 pulseaudio-utils udisks2 bluez
# KDE Plasma: the tray icon and the panel widget work out of the box.
# GNOME: install the "AppIndicator and KStatusNotifierItem Support" extension for the tray icon.
```
On Fedora regular users are not in the `users` group, so for the lid-dot blink also run `sudo usermod -aG users $USER`.

Requirements: Python 3, PySide6 (`sudo pacman -S pyside6`). Optional: udisks2, pactl (PipeWire/PulseAudio),
NetworkManager, bluez-utils, power-profiles-daemon. Only `/sys` and these user-level tools are used — no root.

## Supported hardware
| Type | Model | Profile |
|---|---|---|
| Dock | Lenovo ThinkPad Ultra Docking Station (40AJ) | `profiles/docks/lenovo-thinkpad-ultra-dock-40aj.json` |
| Dock (draft) | Lenovo ThinkPad USB-C Dock Gen 2 (40AS) | `profiles/docks/lenovo-thinkpad-usb-c-dock-gen2-40as.json` |
| Dock (draft) | Dell WD19 | `profiles/docks/dell-wd19.json` |
| Laptop | Lenovo ThinkPad L14 Gen 1 | `profiles/laptops/lenovo-thinkpad-l14-gen1.json` |

*Draft* profiles are made from spec sheets and not verified on real hardware; they are only selectable manually in the menu until someone confirms them.

Docks are detected by the VID:PID of their internal USB hubs, laptops by DMI; both can be chosen manually in the menu.

### Adding your dock or laptop
Profiles are plain JSON — copy an existing one:
- `match` — detection: `usb_hubs` (VID:PID of the dock's hubs, see `lsusb`) or `dmi` (substring of `/sys/class/dmi/id/product_version`).
- `groups` — physical sides; `row` + `w` put several on one line; `vents` draws a grille with sensors (`"sensors": {"temps": ["CPU"], "fans": [0]}` gives each grille its own — e.g. CPU on the left, `dGPU`/SSD on the right); `bezel` enables the camera/mic header.
- `ports` — connectors left→right: `kind` (`usb`, `usbc`, `hdmi`, `dp`, `vga`, `rj45`, `audio`, `dc`, `card`, `dockport`),
  `x` — centre as a fraction of the side width, `label`, optional `role` (`power`, `eth`, `dock`, `card`, `jack`),
  `label_docked`, `typec` (e.g. `port0`) and `drm` (e.g. `["HDMI-A-1"]`).

Check it with `python tools/check_profiles.py` (also run by GitHub Actions on every push), then run `dockwatch calibrate` once. New profiles are welcome — open an issue with the **New dock / laptop profile** form
(photo of the ports + `lsusb`).

## Config
`~/.config/dockwatch/config.json` — port bindings, custom labels, language, chosen profiles, options.

## Logos
`assets/` may contain `thinkpad.png`, `lenovo.png`, `ibm.png` for the header/footer. They are trademarks of their owners
and are **not** distributed with the project; without them a drawn wordmark is used (as on the screenshot).

## License
MIT
