# dockwatch

Live port map of your **docking station and laptop** — in ThinkPad style. Shows which connectors are in use,
what is plugged in, and pops up a notification when something is connected or removed.

![screenshot](docs/screenshot.png)

**Languages:** українська · русский · English (auto from `$LANG`, switch in the tray menu or `--lang`).

## Views
| Command | What it does |
|---|---|
| `dockwatch` / `dockwatch tray` | tray icon (KDE/any SNI tray), click → port map, plug/unplug notifications |
| `dockwatch gui` | window with the port map (scales with window size / fullscreen) |
| `dockwatch tui` | the same in a terminal (curses) |
| `dockwatch dump` | plain-text state |
| `dockwatch calibrate` | bind system USB ports to physical connectors — plug a flash drive into each one |

Only `/sys` is read — no root, no daemons. GUI/tray need **PySide6** (`sudo pacman -S pyside6` / `pip install PySide6`).

## Supported hardware
| Type | Model | Profile |
|---|---|---|
| Dock | Lenovo ThinkPad Ultra Docking Station (40AJ) | `profiles/docks/lenovo-thinkpad-ultra-dock-40aj.json` |
| Laptop | Lenovo ThinkPad L14 Gen 1 | `profiles/laptops/lenovo-thinkpad-l14-gen1.json` |

### Adding your dock or laptop
Profiles are plain JSON — copy an existing one:
- `match` — how to detect it: `usb_hubs` (VID:PID of the dock's internal hubs, see `lsusb`) or `dmi` (substring of `/sys/class/dmi/id/product_version`).
- `groups` — physical sides (rear panel, left/right side); `row` + `w` put several on one line.
- `ports` — connectors left→right: `kind` (`usb`, `usbc`, `hdmi`, `dp`, `vga`, `rj45`, `audio`, `dc`, `card`, `dockport`),
  `x` — centre position as a fraction of the side's width, `label`, optional `role` (`power`, `eth`, `dock`), `label_docked` (label while docked — e.g. a USB-C that becomes the dock connector), `typec` (e.g. `port0` for USB-C Power Delivery info) and `drm` (e.g. `["HDMI-A-1"]`).

Then run `dockwatch calibrate` once. Pull requests with new profiles (and a photo of the ports) are welcome.

## Config
`~/.config/dockwatch/config.json` — port bindings, custom labels, language.

## Logos
`assets/` may contain `thinkpad.png`, `lenovo.png`, `ibm.png` for the header/footer. They are trademarks of their owners
and are **not** distributed with the project; without them the header falls back to a drawn wordmark.

## License
MIT
