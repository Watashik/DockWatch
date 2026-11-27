#!/usr/bin/env python3
"""dockwatch — live port map of a docking station and laptop, ThinkPad style.

  dockwatch            app: window + tray icon; closing the window keeps it in the tray (default)
  dockwatch tray       start hidden in the tray (for autostart)
  dockwatch gui        window only, no tray
  dockwatch tui        the same in a terminal (curses); q — quit, c — calibrate
  dockwatch dump       current state as text
  dockwatch calibrate  bind system USB ports to physical connectors (plug a flash drive into each)
  --lang uk|ru|en      interface language (default: from config, then $LANG)

Docks and laptops are described by JSON profiles in profiles/ — add your model there.
Only /sys is read, no root needed. PySide6 is required for tray/gui.
User config: ~/.config/dockwatch/config.json
"""
import argparse
import glob
import json
import os
import random
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.realpath(__file__))
PROFILES = os.path.join(HERE, "profiles")
CONFIG_DIR = os.path.expanduser("~/.config/dockwatch")
CONFIG = os.path.join(CONFIG_DIR, "config.json")
OLD_CONFIG = os.path.join(CONFIG_DIR, "ports.json")
LANGS = ("uk", "ru", "en")

# ---------------------------------------------------------------- translations
TR = {
    "docked": {"uk": "у доці", "ru": "в доке", "en": "docked"},
    "undocked": {"uk": "не в доці", "ru": "не в доке", "en": "not docked"},
    "busy": {"uk": "зайнято {n} з {m}", "ru": "занято {n} из {m}", "en": "{n} of {m} in use"},
    "connected": {"uk": "Підключено", "ru": "Подключено", "en": "Connected"},
    "events": {"uk": "Події", "ru": "События", "en": "Events"},
    "nothing": {"uk": "нічого не підключено", "ru": "ничего не подключено", "en": "nothing connected"},
    "quiet": {"uk": "поки тихо", "ru": "пока тихо", "en": "all quiet"},
    "free": {"uk": "вільно", "ru": "свободно", "en": "free"},
    "audio": {"uk": "Аудіо", "ru": "Аудио", "en": "Audio"},
    "power": {"uk": "Живлення", "ru": "Питание", "en": "Power"},
    "card": {"uk": "Картка", "ru": "Карта", "en": "Card"},
    "dock": {"uk": "Док", "ru": "Док", "en": "Dock"},
    "on_dock": {"uk": "док", "ru": "док", "en": "dock"},
    "on_laptop": {"uk": "ноутбук", "ru": "ноутбук", "en": "laptop"},
    "monitor": {"uk": "монітор", "ru": "монитор", "en": "monitor"},
    "no_edid": {"uk": "без EDID", "ru": "без EDID", "en": "no EDID"},
    "in_dock": {"uk": "🔗 ноутбук стоїть у доці", "ru": "🔗 ноутбук стоит в доке", "en": "🔗 laptop is docked"},
    "eth_item": {"uk": "🌐 {s} Мбіт/с · ↓{rx} ↑{tx}", "ru": "🌐 {s} Мбит/с · ↓{rx} ↑{tx}", "en": "🌐 {s} Mbit/s · ↓{rx} ↑{tx}"},
    "bat_item": {"uk": "⚡ батарея {p}% · {st} · {w} Вт", "ru": "⚡ батарея {p}% · {st} · {w} Вт", "en": "⚡ battery {p}% · {st} · {w} W"},
    "bat_head": {"uk": "🔋 {p}% · {st}", "ru": "🔋 {p}% · {st}", "en": "🔋 {p}% · {st}"},
    "W": {"uk": "Вт", "ru": "Вт", "en": "W"},
    "Charging": {"uk": "заряджається", "ru": "заряжается", "en": "charging"},
    "Discharging": {"uk": "розряджається", "ru": "разряжается", "en": "discharging"},
    "Full": {"uk": "повна", "ru": "полная", "en": "full"},
    "Not charging": {"uk": "не заряджається", "ru": "не заряжается", "en": "not charging"},
    "ev_docked": {"uk": "🔗 Ноутбук у доці", "ru": "🔗 Ноутбук в доке", "en": "🔗 Laptop docked"},
    "ev_undocked": {"uk": "⛓️‍💥 Ноутбук знято з дока", "ru": "⛓️‍💥 Ноутбук снят с дока", "en": "⛓️‍💥 Laptop undocked"},
    "ev_on": {"uk": "підключено", "ru": "подключено", "en": "connected"},
    "ev_off": {"uk": "відключено", "ru": "отключено", "en": "disconnected"},
    "loose_hint": {"uk": "Не прив'язано до роз'єму (dockwatch calibrate):", "ru": "Не привязано к разъёму (dockwatch calibrate):",
                   "en": "Not bound to a connector (dockwatch calibrate):"},
    "m_show": {"uk": "Схема", "ru": "Схема", "en": "Port map"},
    "m_tui": {"uk": "Відкрити в терміналі", "ru": "Открыть в терминале", "en": "Open in terminal"},
    "m_cal": {"uk": "Калібрування портів…", "ru": "Калибровка портов…", "en": "Calibrate ports…"},
    "m_lang": {"uk": "Мова", "ru": "Язык", "en": "Language"},
    "m_quit": {"uk": "Вийти", "ru": "Выход", "en": "Quit"},
    "tui_foot": {"uk": "q — вихід · c — калібрування", "ru": "q — выход · c — калибровка", "en": "q — quit · c — calibrate"},
    "need_qt": {"uk": "Потрібен PySide6: sudo pacman -S pyside6   (або: dockwatch tui)",
                "ru": "Нужен PySide6: sudo pacman -S pyside6   (или: dockwatch tui)",
                "en": "PySide6 is required: pip install PySide6   (or: dockwatch tui)"},
    "cal_intro": {
        "uk": "Калібрування роз'ємів. Потрібна флешка (краще USB 3).\nДля кожного роз'єму: вийми флешку → Enter → встав у названий роз'єм → зачекай пару секунд.\n"
              "s — пропустити, q — закінчити. Порти дока калібруються, лише коли ноутбук у доці й док живиться.\n",
        "ru": "Калибровка разъёмов. Нужна флешка (лучше USB 3).\nДля каждого разъёма: вытащи флешку → Enter → воткни в названный разъём → подожди пару секунд.\n"
              "s — пропустить, q — закончить. Порты дока калибруются, только когда ноутбук в доке и у дока есть питание.\n",
        "en": "Connector calibration. You need a flash drive (USB 3 preferred).\nFor each connector: unplug the drive → Enter → plug it into the named connector → wait a couple of seconds.\n"
              "s — skip, q — finish. Dock ports can be calibrated only while docked and the dock is powered.\n"},
    "cal_ask": {"uk": "[{g} → {p}] флешку вийняв? Enter / s / q: ", "ru": "[{g} → {p}] флешку вытащил? Enter / s / q: ",
                "en": "[{g} → {p}] drive unplugged? Enter / s / q: "},
    "cal_plug": {"uk": "  тепер встав… ", "ru": "  теперь воткни… ", "en": "  now plug it in… "},
    "cal_none": {"uk": "нічого не з'явилось, пропускаю", "ru": "ничего не появилось, пропускаю", "en": "nothing appeared, skipping"},
    "cal_video": {"uk": "\nВідеовиходи: підключи монітор у роз'єм і напиши його id ({ids}). Enter — закінчити.",
                  "ru": "\nВидеовыходы: подключи монитор в разъём и напиши его id ({ids}). Enter — закончить.",
                  "en": "\nVideo outputs: connect a monitor and type the connector id ({ids}). Enter — finish."},
    "cal_vask": {"uk": "  зараз підключено: {c}. Який це роз'єм? ", "ru": "  сейчас подключено: {c}. Какой это разъём? ",
                 "en": "  currently connected: {c}. Which connector is it? "},
    "cal_saved": {"uk": "\nЗбережено: {f}", "ru": "\nСохранено: {f}", "en": "\nSaved: {f}"},
    "nothing_short": {"uk": "нічого", "ru": "ничего", "en": "nothing"},
    "m_stats": {"uk": "Показувати споживання й навантаження", "ru": "Показывать потребление и нагрузку", "en": "Show power & load"},
    "m_hidedock": {"uk": "Ховати док, коли він неактивний", "ru": "Скрывать док, когда он неактивен", "en": "Hide the dock when inactive"},
    "m_laptop": {"uk": "Ноутбук", "ru": "Ноутбук", "en": "Laptop"},
    "m_dock": {"uk": "Док-станція", "ru": "Док-станция", "en": "Docking station"},
    "auto": {"uk": "Авто ({x})", "ru": "Авто ({x})", "en": "Auto ({x})"},
    "not_found": {"uk": "не визначено", "ru": "не определено", "en": "not detected"},
    "no_dock": {"uk": "Без дока", "ru": "Без дока", "en": "No dock"},
    "per_s": {"uk": "/с", "ru": "/с", "en": "/s"},
    "mode_mtp": {"uk": "передача файлів (MTP)", "ru": "передача файлов (MTP)", "en": "file transfer (MTP)"},
    "mode_ptp": {"uk": "передача фото (PTP)", "ru": "передача фото (PTP)", "en": "photo transfer (PTP)"},
    "mode_adb": {"uk": "налагодження (ADB)", "ru": "отладка (ADB)", "en": "debugging (ADB)"},
    "mode_tether": {"uk": "USB-модем", "ru": "USB-модем", "en": "USB tethering"},
    "mode_midi": {"uk": "MIDI", "ru": "MIDI", "en": "MIDI"},
    "pd_source": {"uk": "🔌 віддає живлення · {mode} · до {a} A", "ru": "🔌 отдаёт питание · {mode} · до {a} A",
                  "en": "🔌 supplying power · {mode} · up to {a} A"},
    "pd_sink": {"uk": "🔌 заряджається · {mode} · {w}", "ru": "🔌 заряжается · {mode} · {w}", "en": "🔌 charging · {mode} · {w}"},
    "dock_hidden": {"uk": "док прихований (неактивний)", "ru": "док скрыт (неактивен)", "en": "dock hidden (inactive)"},
}
LANG = "en"


def tr(key, **kw):
    v = TR.get(key, {})
    s = v.get(LANG) or v.get("en") or key
    return s.format(**kw) if kw else s


def pick(d):
    """Profile string: {"uk":…, "ru":…, "en":…} or plain text; "@key" — from TR."""
    if isinstance(d, dict):
        return d.get(LANG) or d.get("en") or next(iter(d.values()), "")
    if isinstance(d, str) and d.startswith("@"):
        return tr(d[1:])
    return d


def detect_lang(cfg, arg=None):
    for v in (arg, os.environ.get("DOCKWATCH_LANG"), cfg.get("lang")):
        if v in LANGS:
            return v
    loc = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "").lower()
    return "uk" if loc.startswith("uk") else "ru" if loc.startswith(("ru", "be")) else "en"


# ---------------------------------------------------------------- /sys
def rd(path, default=""):
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "replace").strip()
    except OSError:
        return default


def load_config():
    cfg = {}
    for f in (CONFIG, OLD_CONFIG):
        try:
            with open(f) as fh:
                cfg = json.load(fh)
            break
        except (OSError, ValueError):
            continue
    cfg.setdefault("usb", {})      # port key ("dock3.2", "lap:4-2") -> connector id
    cfg.setdefault("video", {})    # DRM connector ("DP-3") -> connector id
    cfg.setdefault("labels", {})   # custom connector names
    cfg.setdefault("eth", "")
    cfg.setdefault("lang", "")
    cfg.setdefault("dock", "")             # last detected dock profile id
    cfg.setdefault("dock_choice", "auto")  # auto | <profile id> | none
    cfg.setdefault("laptop_choice", cfg.pop("laptop", "") or "auto")  # auto | <profile id>
    cfg.setdefault("show_stats", True)
    cfg.setdefault("hide_dock", False)
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_profiles(kind):
    out = []
    for f in sorted(glob.glob(os.path.join(PROFILES, kind, "*.json"))):
        try:
            with open(f) as fh:
                out.append(json.load(fh))
        except (OSError, ValueError) as e:
            print(f"profile {f}: {e}", file=sys.stderr)
    return out


def usb_devices():
    devs = {}
    for p in glob.glob("/sys/bus/usb/devices/*"):
        name = os.path.basename(p)
        if ":" in name or not os.path.exists(os.path.join(p, "idVendor")):
            continue
        ifc = glob.glob(f"{p}/{name}:1.0/bInterfaceClass")
        ifaces = [(rd(f"{i}/bInterfaceClass"), rd(f"{i}/bInterfaceSubClass"), rd(f"{i}/bInterfaceProtocol"), rd(f"{i}/interface"))
                  for i in sorted(glob.glob(f"{p}/{name}:*"))]
        devs[name] = {
            "name": name, "vid": rd(f"{p}/idVendor"), "pid": rd(f"{p}/idProduct"),
            "product": rd(f"{p}/product"), "maker": rd(f"{p}/manufacturer"),
            "speed": rd(f"{p}/speed"), "cls": rd(f"{p}/bDeviceClass"),
            "ifcls": rd(ifc[0]) if ifc else "", "removable": rd(f"{p}/removable"), "ifaces": ifaces,
        }
    return devs


def detect_profiles(cfg, devs):
    """Автоопределение: док — по VID:PID его хабов, ноутбук — по DMI. Возвращает (док, ноутбук) или None."""
    ids = {f"{d['vid']}:{d['pid']}" for d in devs.values()}
    dock = next((p for p in load_profiles("docks")
                 if any(f"{v}:{pid}" in ids for v, pid in p.get("match", {}).get("usb_hubs", []))), None)
    if dock and cfg.get("dock") != dock["id"]:
        cfg["dock"] = dock["id"]  # запоминаем: без питания док не виден, но схема должна остаться
        try:
            save_config(cfg)
        except OSError:
            pass
    dmi = " ".join(rd(f"/sys/class/dmi/id/{k}") for k in ("product_version", "product_name", "product_family")).lower()
    laptop = next((p for p in load_profiles("laptops")
                   if any(m.lower() in dmi for m in p.get("match", {}).get("dmi", []))), None)
    return dock, laptop


def select_profiles(cfg, devs):
    det_dock, det_laptop = detect_profiles(cfg, devs)
    docks = {p["id"]: p for p in load_profiles("docks")}
    laptops = {p["id"]: p for p in load_profiles("laptops")}
    dc = cfg.get("dock_choice", "auto")
    dock = None if dc == "none" else docks.get(dc) if dc != "auto" else (det_dock or docks.get(cfg.get("dock")))
    lc = cfg.get("laptop_choice", "auto")
    laptop = laptops.get(lc) if lc != "auto" else det_laptop
    return dock, laptop


def peer_of(name):
    """Companion port (USB 3 <-> USB 2 of the same connector) via /sys/.../portN/peer."""
    if "-" not in name:
        return None
    if "." in name:
        parent, _, num = name.rpartition(".")
        port_dir = f"/sys/bus/usb/devices/{parent}/{parent}:1.0/{parent}-port{num}"
    else:
        bus, num = name.split("-")
        port_dir = f"/sys/bus/usb/devices/usb{bus}/{bus}-0:1.0/usb{bus}-port{num}"
    link = os.path.join(port_dir, "peer")
    if not os.path.exists(link):
        return None
    m = re.search(r"/(usb(\d+)|([\d.-]+)):1\.0/(?:usb\d+|[\d.-]+)-port(\d+)$", os.path.realpath(link))
    if not m:
        return None
    if m.group(2):
        return f"{m.group(2)}-{m.group(4)}"
    if m.group(3).endswith("-0"):
        return f"{m.group(3)[:-2]}-{m.group(4)}"
    return f"{m.group(3)}.{m.group(4)}"


USB_CLASS = {"01": "🔊", "02": "📡", "03": "⌨️", "06": "📷", "07": "🖨", "08": "💾", "09": "🔀", "0e": "🎥", "e0": "📶", "ff": "🔧"}
VENDOR_ICON = {"045e": "🎮", "057e": "🎮", "054c": "🎮", "28de": "🎮"}


def phone_modes(d):
    """Режимы телефона по интерфейсам: MTP/PTP/ADB/модем/MIDI."""
    modes = []
    for cls, sub, proto, name in d.get("ifaces", []):
        n = name.upper()
        if "MTP" in n:
            modes.append("mode_mtp")
        elif cls == "06" or "PTP" in n:
            modes.append("mode_ptp")
        elif (cls, sub, proto) == ("ff", "42", "01"):
            modes.append("mode_adb")
        elif (cls, sub, proto) in (("e0", "01", "03"), ("ef", "04", "01")) or (cls == "02" and sub in ("02", "0d", "06")):
            modes.append("mode_tether")
        elif cls == "01" and sub == "03":
            modes.append("mode_midi")
    return list(dict.fromkeys(modes))


def usb_icon(d):
    if {"mode_mtp", "mode_adb", "mode_tether"} & set(phone_modes(d)):
        return "📱"
    if d["vid"] in VENDOR_ICON:
        return VENDOR_ICON[d["vid"]]
    cls = d["cls"] if d["cls"] not in ("00", "ef") else d["ifcls"]
    return USB_CLASS.get(cls, "🔌")


def speed_text(s):
    return {"1.5": "USB 1", "12": "USB 1", "480": "USB 2", "5000": "USB 3 · 5G", "10000": "USB 3 · 10G",
            "20000": "USB 3 · 20G"}.get(s, "")


def dock_roots(devs, dock):
    hub_ids = set((dock or {}).get("usb_hubs", {}))
    hubs = [n for n, d in devs.items() if f"{d['vid']}:{d['pid']}" in hub_ids]
    return [n for n in hubs if not any(n.startswith(o + ".") for o in hubs if o != n)], hub_ids


def port_key(name, devs, roots, dock):
    for r in roots:
        if name.startswith(r + "."):
            d = devs[r]
            tag = "dock3" if (dock or {}).get("usb_hubs", {}).get(f"{d['vid']}:{d['pid']}") == "usb3" else "dock2"
            return tag + "." + name[len(r) + 1:].split(".")[0], True
    return "lap:" + name.split(".")[0], False


def scan_usb(dock, devs=None):
    devs = devs or usb_devices()
    roots, hub_ids = dock_roots(devs, dock)
    out = []
    for n, d in devs.items():
        if n.startswith("usb") or f"{d['vid']}:{d['pid']}" in hub_ids:
            continue
        key, on_dock = port_key(n, devs, roots, dock)
        top = n.split(".")[0]
        if not on_dock and devs.get(top, {}).get("removable") == "fixed":
            continue  # built-in: camera, Bluetooth, fingerprint reader
        out.append(dict(d, key=key, dock=on_dock))
    return out, bool(roots), devs, roots


def edid_name(raw):
    if len(raw) < 128:
        return ""
    for i in range(54, 126, 18):
        blk = raw[i:i + 18]
        if blk[:3] == b"\0\0\0" and blk[3] == 0xFC:
            return blk[5:18].split(b"\n")[0].decode("ascii", "replace").strip()
    m = (raw[8] << 8) | raw[9]
    return "".join(chr(((m >> s) & 31) + 64) for s in (10, 5, 0))


def video_outputs():
    out = {}
    for p in sorted(glob.glob("/sys/class/drm/card*-*")):
        conn = os.path.basename(p).split("-", 1)[1]
        if conn.startswith(("eDP", "LVDS", "Writeback", "DSI")):
            continue
        try:
            with open(f"{p}/edid", "rb") as f:
                raw = f.read()
        except OSError:
            raw = b""
        modes = rd(f"{p}/modes").splitlines()
        out[conn] = {"conn": conn, "connected": rd(f"{p}/status") == "connected", "monitor": edid_name(raw),
                     "mode": modes[0] if modes else "", "edid": len(raw)}
    return out


def ethernet(cfg):
    names = [cfg["eth"]] if cfg.get("eth") else sorted(os.path.basename(p) for p in glob.glob("/sys/class/net/en*"))
    for n in names:
        p = f"/sys/class/net/{n}"
        if os.path.exists(p):
            up = rd(f"{p}/carrier") == "1"
            return {"up": up, "speed": rd(f"{p}/speed") if up else "",
                    "rx": int(rd(f"{p}/statistics/rx_bytes", "0") or 0), "tx": int(rd(f"{p}/statistics/tx_bytes", "0") or 0)}
    return {"up": False, "speed": "", "rx": 0, "tx": 0}


def power():
    ac = any(rd(f"{p}/online") == "1" for p in glob.glob("/sys/class/power_supply/*") if rd(f"{p}/type") == "Mains")
    bat = next(iter(glob.glob("/sys/class/power_supply/BAT*")), None)
    w = 0.0
    if bat:
        if rd(f"{bat}/power_now"):
            w = int(rd(f"{bat}/power_now")) / 1e6
        elif rd(f"{bat}/current_now") and rd(f"{bat}/voltage_now"):
            w = int(rd(f"{bat}/current_now")) * int(rd(f"{bat}/voltage_now")) / 1e12
    return {"ac": ac, "status": rd(f"{bat}/status") if bat else "", "watts": round(w, 1), "pct": rd(f"{bat}/capacity") if bat else ""}


def docked_flag():
    for p in glob.glob("/sys/devices/platform/dock.*/docked"):
        return rd(p) == "1"
    return None


_PREV = {}


def rate(key, value):
    """Скорость изменения счётчика (в секунду) между вызовами."""
    t = time.monotonic()
    old = _PREV.get(key)
    _PREV[key] = (t, value)
    if not old or t <= old[0] or value < old[1]:
        return 0.0
    return (value - old[1]) / (t - old[0])


def in_usb_path(path, name):
    return f"/{name}/" in path or path.endswith(f"/{name}")


def usb_stats(name):
    """Что можно узнать о нагрузке USB-устройства без root: заявленный ток, диск (чтение/запись), сеть."""
    p = f"/sys/bus/usb/devices/{name}"
    out = []
    mp = rd(f"{p}/bMaxPower")
    if mp and mp not in ("0mA", "0"):
        out.append("⚡ " + mp.replace("mA", " mA"))
    rx = tx = 0.0
    disk = False
    for b in glob.glob("/sys/block/sd*"):
        if in_usb_path(os.path.realpath(b), name):
            f = rd(f"{b}/stat").split()
            if len(f) > 6:
                disk = True
                rx += rate(f"blk-r-{b}", int(f[2]) * 512)
                tx += rate(f"blk-w-{b}", int(f[6]) * 512)
    if disk:
        out.append(f"💾 ↓{human(rx)}{tr('per_s')} ↑{human(tx)}{tr('per_s')}")
    for n in glob.glob("/sys/class/net/*"):
        dev = os.path.join(n, "device")
        if os.path.exists(dev) and in_usb_path(os.path.realpath(dev), name):
            r = rate(f"net-r-{n}", int(rd(f"{n}/statistics/rx_bytes", "0") or 0))
            w = rate(f"net-w-{n}", int(rd(f"{n}/statistics/tx_bytes", "0") or 0))
            out.append(f"🌐 ↓{human(r)}{tr('per_s')} ↑{human(w)}{tr('per_s')}")
    return " · ".join(out)


def typec_power():
    """USB-C Power Delivery (ucsi): какие порты сейчас дают питание и сколько ватт."""
    out = []
    for p in sorted(glob.glob("/sys/class/power_supply/ucsi-*")):
        if rd(f"{p}/online") != "1":
            continue
        v, a = rd(f"{p}/voltage_now"), rd(f"{p}/current_now") or rd(f"{p}/current_max")
        if v and a:
            out.append(f"USB-C {int(v) / 1e6:.0f} V × {int(a) / 1e6:.1f} A = {int(v) * int(a) / 1e12:.0f} W")
    return out


def typec_info(port):
    """Состояние USB-C порта (typec + ucsi): кто кому даёт питание и сколько. port — "port1"."""
    base = f"/sys/class/typec/{port}"
    if not os.path.exists(f"{base}-partner"):
        return ""
    role = re.search(r"\[(\w+)\]", rd(f"{base}/power_role"))
    mode = rd(f"{base}/power_operation_mode").replace("usb_power_delivery", "USB PD").replace("_", " ")
    n = int(re.sub(r"\D", "", port) or 0) + 1
    psy = next(iter(glob.glob(f"/sys/class/power_supply/ucsi-*USBC000:{n:03d}")), "")
    cur = int(rd(f"{psy}/current_now", "0") or 0) if psy else 0
    volt = int(rd(f"{psy}/voltage_now", "0") or 0) if psy else 0
    if role and role.group(1) == "source":
        return tr("pd_source", mode=mode or "USB-C", a=f"{cur / 1e6:.1f}" if cur else "?")
    w = f"{volt * cur / 1e12:.0f} W" if volt and cur else ""
    return tr("pd_sink", mode=mode or "USB-C", w=w).rstrip(" ·")


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def snapshot(cfg=None):
    cfg = cfg or load_config()
    devs = usb_devices()
    dock, laptop = select_profiles(cfg, devs)
    usb, hubs, _, _ = scan_usb(dock, devs)
    flag = docked_flag()
    docked = flag if flag is not None else hubs
    eth, pw = ethernet(cfg), power()
    groups, ports = [], {}
    dock_hidden = bool(dock and cfg.get("hide_dock") and not docked)
    for prof, where in ((dock, "dock"), (laptop, "laptop")):
        if not prof or (where == "dock" and dock_hidden):
            continue
        for g in prof.get("groups", []):
            groups.append(dict(g, owner=where, title=pick(g.get("title", g["id"]))))
        for p in prof.get("ports", []):
            ports[p["id"]] = dict(p, owner=where, label=cfg["labels"].get(p["id"]) or pick(p.get("label", p["id"])),
                                  busy=False, items=[], stats=[])
    loose, loose_stats = [], []
    show = cfg.get("show_stats", True)

    def put(pid, item, stat=""):
        ports[pid]["busy"] = True
        ports[pid]["items"].append(item)
        ports[pid]["stats"].append(stat if show else "")

    def by_role(role, owner):
        return next((pid for pid, p in ports.items() if p.get("role") == role and p["owner"] == owner), None)

    for d in usb:
        nm = d["product"] or d["maker"] or d["vid"] + ":" + d["pid"]
        if d["maker"] and d["product"] and d["maker"].split()[0].lower() not in d["product"].lower() and len(d["maker"]) < 16:
            nm = f"{d['maker']} {d['product']}"
        item = f"{usb_icon(d)} {nm}"
        modes = phone_modes(d)
        if modes:
            item += " · " + " + ".join(tr(m) for m in modes)
        if speed_text(d["speed"]):
            item += f" · {speed_text(d['speed'])}"
        stat = usb_stats(d["name"]) if show else ""
        pid = cfg["usb"].get(d["key"])
        if pid in ports:
            put(pid, item, stat)
        else:
            loose.append(f"{item}  [{tr('on_dock') if d['dock'] else tr('on_laptop')} · {d['key']}]")
            loose_stats.append(stat)
    drm_default = {c: pid for pid, p in ports.items() for c in p.get("drm", [])}
    for v in video_outputs().values():
        if not v["connected"]:
            continue
        item = f"🖥 {v['monitor'] or tr('monitor')} · {v['mode']}" + ("" if v["edid"] else f" · {tr('no_edid')}")
        pid = cfg["video"].get(v["conn"]) or drm_default.get(v["conn"])
        if pid in ports:
            put(pid, item)
        else:
            loose.append(f"{item}  [{v['conn']}]")
            loose_stats.append("")
    owner = "dock" if docked and dock else "laptop"
    if eth["up"]:
        pid = by_role("eth", owner) or by_role("eth", "laptop")
        item = tr("eth_item", s=eth["speed"], rx=human(eth["rx"]), tx=human(eth["tx"]))
        r, w = rate("eth-r", eth["rx"]), rate("eth-w", eth["tx"])
        stat = f"↓{human(r)}{tr('per_s')} ↑{human(w)}{tr('per_s')}"
        if pid:
            put(pid, item, stat)
        else:
            loose.append(item); loose_stats.append(stat if show else "")
    if pw["ac"]:
        pid = by_role("power", owner) or by_role("power", "laptop")
        item = tr("bat_item", p=pw["pct"], st=tr(pw["status"]) if pw["status"] else "", w=pw["watts"])
        stat = " · ".join([f"{pw['watts']} {tr('W')}"] + typec_power())
        if pid:
            put(pid, item, stat)
        else:
            loose.append(item); loose_stats.append(stat if show else "")
    for pid, p in ports.items():  # USB-C: питание по Power Delivery
        if p.get("typec"):
            info = typec_info(p["typec"])
            if info and show:
                if p["items"]:
                    p["stats"][0] = " · ".join(x for x in (p["stats"][0], info) if x)
                else:
                    put(pid, info.split(" · ")[0], info)
    if docked and by_role("dock", "laptop"):
        put(by_role("dock", "laptop"), tr("in_dock"))
    busy = sum(p["busy"] for p in ports.values())
    return {"docked": docked, "groups": groups, "ports": ports, "loose": loose, "loose_stats": loose_stats,
            "busy": busy, "total": len(ports), "power": pw, "dock": dock, "laptop": laptop, "dock_hidden": dock_hidden,
            "show_stats": show, "ts": time.time()}


def diff(old, new):
    ev = []
    if old is None:
        return ev
    if old["docked"] != new["docked"]:
        ev.append(tr("ev_docked") if new["docked"] else tr("ev_undocked"))
    norm = lambda x: x[:1] if x.startswith(("⚡", "🌐", "🔗")) else x  # noqa: E731 — watts/traffic change constantly
    for pid, p in new["ports"].items():
        o = old["ports"].get(pid, {"items": []})
        a, b = {norm(x): x for x in o["items"]}, {norm(x): x for x in p["items"]}
        for k in sorted(set(b) - set(a)):
            ev.append(f"🔴 {p['label']}: " + (tr("ev_on") if len(k) == 1 else b[k]))
        for k in sorted(set(a) - set(b)):
            ev.append(f"⚫ {p['label']}: {tr('ev_off')}" + ("" if len(k) == 1 else f" {a[k]}"))
    strip = lambda s: s.rsplit("  [", 1)[0]  # noqa: E731
    for x in sorted(set(map(strip, new["loose"])) - set(map(strip, old["loose"]))):
        ev.append(f"🔴 {x}")
    for x in sorted(set(map(strip, old["loose"])) - set(map(strip, new["loose"]))):
        ev.append(f"⚫ {tr('ev_off')} {x}")
    return ev


def dump():
    s = snapshot()
    names = " + ".join(p["name"] for p in (s["dock"], s["laptop"]) if p)
    print(f"{names} · {tr('docked') if s['docked'] else tr('undocked')} · {tr('busy', n=s['busy'], m=s['total'])}")
    for g in s["groups"]:
        print(g["title"] + ":")
        for p in s["ports"].values():
            if p["g"] == g["id"]:
                det = "; ".join(i + (f"  [{st}]" if st else "") for i, st in zip(p["items"], p["stats"]))
                print(f"  {'●' if p['busy'] else '○'} {p['label']:<9} {det}")
    if s["loose"]:
        print(tr("loose_hint"))
        for x in s["loose"]:
            print("  •", x)


# ---------------------------------------------------------------- calibration
def calibrate():
    cfg = load_config()
    print(tr("cal_intro"))
    s = snapshot(cfg)
    titles = {g["id"]: g["title"] for g in s["groups"]}
    for p in s["ports"].values():
        if p["kind"] not in ("usb", "usbc"):
            continue
        ans = input(tr("cal_ask", g=titles.get(p["g"], p["g"]), p=p["label"])).strip().lower()
        if ans == "q":
            break
        if ans == "s":
            continue
        before = {d["name"] for d in scan_usb(s["dock"])[0]}
        print(tr("cal_plug"), end="", flush=True)
        new = []
        for _ in range(40):
            time.sleep(0.5)
            if any(d["name"] not in before for d in scan_usb(s["dock"])[0]):
                time.sleep(1.5)
                new = [d for d in scan_usb(s["dock"])[0] if d["name"] not in before]
                break
        if not new:
            print(tr("cal_none"))
            continue
        _, _, devs, roots = scan_usb(s["dock"])
        keys = set()
        for d in new:
            keys.add(d["key"])
            n = d["name"]
            r = next((r for r in roots if n.startswith(r + ".")), None)
            top = r + "." + n[len(r) + 1:].split(".")[0] if r else n.split(".")[0]
            peer = peer_of(top)
            if peer:
                keys.add(port_key(peer, devs, roots, s["dock"])[0])
        for k in keys:
            cfg["usb"][k] = p["id"]
        print("✔", ", ".join(sorted(keys)))
    vids = [pid for pid, p in s["ports"].items() if p.get("video")]
    print(tr("cal_video", ids=" / ".join(vids)))
    while True:
        conn = [v["conn"] for v in video_outputs().values() if v["connected"]]
        ans = input(tr("cal_vask", c=", ".join(conn) or "—")).strip().lower()
        if not ans or not conn:
            break
        if ans in vids:
            for c in conn:
                cfg["video"][c] = ans
            print("  ✔", ", ".join(conn), "→", ans)
    save_config(cfg)
    print(tr("cal_saved", f=CONFIG))


# ---------------------------------------------------------------- TUI
def rows_of(groups):
    rows = {}
    for g in groups:
        rows.setdefault(g.get("row", 0), []).append(g)
    return [rows[k] for k in sorted(rows)]


def tui():
    import curses

    def main(w):
        curses.curs_set(0)
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_RED, -1)
        curses.init_pair(2, 8 if curses.COLORS > 8 else curses.COLOR_WHITE, -1)
        curses.init_pair(3, curses.COLOR_WHITE, -1)
        red, dim, wht = curses.color_pair(1), curses.color_pair(2), curses.color_pair(3)
        w.timeout(1000)
        prev, log = None, []
        glyph = {"usb": "▭", "usbc": "⊂⊃", "vga": "▽", "dp": "◺", "hdmi": "⬡", "dc": "▣", "rj45": "⊞",
                 "audio": "◉", "card": "▬", "dockport": "⊂▭⊃"}
        while True:
            s = snapshot()
            for e in diff(prev, s):
                log.insert(0, time.strftime("%H:%M:%S ") + e)
            prev, log = s, log[:6]
            w.erase()
            H, W = w.getmaxyx()

            def put(y, x, t, a=0):
                if 0 <= y < H and 0 <= x < W - 1:
                    try:
                        w.addstr(y, x, t[:W - 1 - x], a)
                    except curses.error:
                        pass
            put(0, 1, "ThinkPad", wht | curses.A_BOLD | curses.A_ITALIC)
            put(0, 3, "•", red | curses.A_BOLD)
            put(0, 11, f"· {tr('docked') if s['docked'] else tr('undocked')} · {tr('busy', n=s['busy'], m=s['total'])}", dim)
            y = 2
            for row in rows_of(s["groups"]):
                x0 = 1
                for g in row:
                    gw = int((W - 3) * g.get("w", 1.0)) - 1
                    put(y, x0, g["title"], wht | curses.A_BOLD)
                    put(y + 1, x0, "┏" + "━" * (gw - 2) + "┓", dim)
                    for k in (2, 3):
                        put(y + k, x0, "┃", dim); put(y + k, x0 + gw - 1, "┃", dim)
                    put(y + 4, x0, "┗" + "━" * (gw - 2) + "┛", dim)
                    for p in s["ports"].values():
                        if p["g"] != g["id"]:
                            continue
                        x = x0 + 2 + int(p["x"] * (gw - 4))
                        gl = glyph.get(p["kind"], "□")
                        put(y + 2, x - len(gl) // 2, gl, (red | curses.A_BOLD) if p["busy"] else dim)
                        lab = p["label"][:7]
                        put(y + 3, x - len(lab) // 2, lab, red if p["busy"] else dim)
                    x0 += gw + 1
                y += 6
            put(y, 1, tr("connected"), wht | curses.A_BOLD)
            y += 1
            rows = [(p["label"], it, red) for p in s["ports"].values() for it in p["items"]]
            rows += [("?", it, wht) for it in s["loose"]]
            for lab, it, a in rows[:max(0, H - y - 9)]:
                put(y, 3, f"{lab:<9}", a); put(y, 13, it, wht); y += 1
            if not rows:
                put(y, 3, tr("nothing_short"), dim); y += 1
            y += 1
            put(y, 1, tr("events"), wht | curses.A_BOLD)
            for i, e in enumerate(log):
                put(y + 1 + i, 3, e, dim)
            put(H - 1, 1, tr("tui_foot"), dim)
            w.refresh()
            k = w.getch()
            if k in (ord("q"), ord("Q"), 27):
                return None
            if k in (ord("c"), ord("C")):
                return "calibrate"

    if curses.wrapper(main) == "calibrate":
        calibrate()


# ---------------------------------------------------------------- GUI + tray (PySide6), ThinkPad style
def qt_app(mode):
    tray_mode = mode in ("app", "tray")
    try:
        from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
        from PySide6.QtNetwork import QLocalServer, QLocalSocket
        from PySide6.QtGui import (QAction, QActionGroup, QBrush, QColor, QFont, QFontMetricsF, QIcon, QLinearGradient,
                                   QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)
        from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget
    except ImportError:
        sys.exit(tr("need_qt"))

    RED = QColor("#E2231A")
    BODY = QColor("#1b1b1c")
    EDGE = QColor("#2c2c2e")
    HOLE = QColor("#070707")
    METAL = QColor("#8e9196")
    INK = QColor("#6d6f73")
    TXT = QColor("#e9e9ea")
    DIM = QColor("#7c7e82")
    UI_FONT = "Liberation Sans"
    BASE_W = 1100.0  # logical width: bigger windows scale everything up

    def asset(name):
        if os.environ.get("DOCKWATCH_NO_ASSETS"):
            return None
        pm = QPixmap(os.path.join(HERE, "assets", name))
        return None if pm.isNull() else pm

    def texture(w, h, base, seed=7):
        pm = QPixmap(max(1, w), max(1, h))
        pm.fill(base)
        q = QPainter(pm)
        rnd = random.Random(seed)
        for _ in range(w * h // 6):
            c = rnd.randint(-7, 7)
            q.setPen(QColor(max(0, base.red() + c), max(0, base.green() + c), max(0, base.blue() + c)))
            q.drawPoint(rnd.randrange(w), rnd.randrange(h))
        q.end()
        return pm

    def font(px, bold=False, italic=False):
        f = QFont(UI_FONT)
        f.setPixelSize(int(px))
        f.setBold(bold)
        f.setItalic(italic)
        return f

    class DockView(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("dockwatch")
            self.setMinimumSize(900, 560)
            self.resize(1100, 640)
            self.s = snapshot()
            self.log = []
            self.rects = {}
            self.bg = None
            self.blink = 0
            self.scale = 1.0
            self.logos = {n: asset(f"{n}.png") for n in ("thinkpad", "ibm", "lenovo")}
            self.setMouseTracking(True)

        def update_state(self, s, events):
            self.s = s
            for e in events:
                self.log.insert(0, time.strftime("%H:%M:%S  ") + e)
            self.log = self.log[:5]
            self.blink ^= 1
            self.update()

        def connector(self, q, kind, c, busy):
            q.save()
            q.translate(c)
            path, inner = QPainterPath(), QPainterPath()
            if kind == "usb":
                path.addRoundedRect(QRectF(-17, -8, 34, 16), 1.5, 1.5); inner.addRect(QRectF(-13, -5, 26, 4.5))
            elif kind == "usbc":
                path.addRoundedRect(QRectF(-13, -5, 26, 10), 5, 5); inner.addRoundedRect(QRectF(-8, -1.4, 16, 2.8), 1.4, 1.4)
            elif kind == "dockport":
                path.addRoundedRect(QRectF(-34, -10, 68, 20), 10, 10)
                inner.addRect(QRectF(-26, -5, 22, 10)); inner.addRoundedRect(QRectF(2, -4, 22, 8), 4, 4)
            elif kind == "vga":
                path.moveTo(-26, -10); path.lineTo(26, -10); path.lineTo(21, 10); path.lineTo(-21, 10); path.closeSubpath()
                for row in (-5, 0, 5):
                    for i in range(5):
                        inner.addEllipse(QPointF(-12 + i * 6, row), 1.1, 1.1)
            elif kind == "dp":
                path.moveTo(-21, -9); path.lineTo(21, -9); path.lineTo(21, 9); path.lineTo(-15, 9); path.lineTo(-21, 3); path.closeSubpath()
                inner.addRect(QRectF(-15, -4, 30, 4))
            elif kind == "hdmi":
                path.moveTo(-21, -8); path.lineTo(21, -8); path.lineTo(21, 2); path.lineTo(15, 8); path.lineTo(-15, 8)
                path.lineTo(-21, 2); path.closeSubpath(); inner.addRect(QRectF(-15, -3, 30, 3.5))
            elif kind == "dc":
                path.addRect(QRectF(-16, -9, 32, 18)); inner.addRect(QRectF(-9, -3, 18, 6))
            elif kind == "rj45":
                path.moveTo(-18, -16); path.lineTo(18, -16); path.lineTo(18, 8); path.lineTo(7, 8); path.lineTo(7, 14)
                path.lineTo(-7, 14); path.lineTo(-7, 8); path.lineTo(-18, 8); path.closeSubpath()
                for i in range(8):
                    inner.addRect(QRectF(-12 + i * 3.2, -13, 1.6, 6))
            elif kind == "audio":
                path.addEllipse(QPointF(0, 0), 7.5, 7.5); inner.addEllipse(QPointF(0, 0), 3.2, 3.2)
            elif kind == "card":
                path.addRoundedRect(QRectF(-22, -9, 44, 6), 2, 2); path.addRoundedRect(QRectF(-22, 0, 44, 10), 3, 3)
                inner.addEllipse(QPointF(-15, 5), 1.6, 1.6)
            else:
                path.addRoundedRect(QRectF(-12, -8, 24, 16), 3, 3)
            if busy:
                g = QRadialGradient(QPointF(0, 0), 46)
                cg = QColor(RED); cg.setAlpha(95); g.setColorAt(0, cg)
                cg = QColor(RED); cg.setAlpha(0); g.setColorAt(1, cg)
                q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(0, 0), 46, 30)
            q.setPen(QPen(QColor("#3a3a3d"), 1.6)); q.setBrush(HOLE); q.drawPath(path)
            q.setPen(Qt.NoPen); q.setBrush(RED if busy else QColor("#2a2a2c")); q.drawPath(inner)
            if kind == "vga":
                for sx in (-34, 34):
                    q.setBrush(METAL); q.setPen(QPen(QColor("#555"), 1)); q.drawEllipse(QPointF(sx, 0), 5, 5)
                    q.setBrush(HOLE); q.drawEllipse(QPointF(sx, 0), 2, 2)
            if kind == "rj45":
                for lx, on, col in ((-13, busy, QColor("#3ddc84")), (13, busy and self.blink, QColor("#ffb020"))):
                    q.setPen(Qt.NoPen); q.setBrush(col if on else QColor("#333")); q.drawRect(QRectF(lx - 3, -19, 6, 3))
            q.restore()

        def tower(self, q, r):
            q.setPen(QPen(EDGE, 1.5)); q.setBrush(QColor("#161617")); q.drawRoundedRect(r, 6, 6)
            c = QPointF(r.center().x(), r.top() + r.height() * 0.32)
            if self.s["docked"]:
                g = QRadialGradient(c, 22); cg = QColor(RED); cg.setAlpha(120); g.setColorAt(0, cg)
                cg.setAlpha(0); g.setColorAt(1, cg); q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(c, 22, 22)
            q.setPen(QPen(QColor("#3a3a3d"), 2)); q.setBrush(HOLE); q.drawEllipse(c, 10, 10)
            q.setPen(QPen(RED if self.s["docked"] else QColor("#444"), 2))
            q.drawArc(QRectF(c.x() - 5, c.y() - 5, 10, 10), 120 * 16, 300 * 16)
            q.drawLine(QPointF(c.x(), c.y() - 7), QPointF(c.x(), c.y() - 1))
            k = QPointF(r.center().x(), r.top() + r.height() * 0.74)
            q.setPen(QPen(QColor("#2e2e30"), 3)); q.setBrush(QColor("#0d0d0e")); q.drawEllipse(k, 11, 11)
            q.setPen(QPen(METAL, 2.5)); q.drawLine(QPointF(k.x() - 6, k.y()), QPointF(k.x() + 6, k.y()))

        def logo(self, q, x, y, size):
            pm = self.logos.get("thinkpad")
            if pm:
                h = size * 1.55
                q.drawPixmap(QRectF(x, y - h * 0.86, pm.width() * h / pm.height(), h), pm, QRectF(pm.rect()))
                return x + pm.width() * h / pm.height()
            f = font(size, True, True); q.setFont(f); q.setPen(TXT)
            q.drawText(QPointF(x, y), "ThinkPad")
            fm = QFontMetricsF(f)
            xi = x + fm.horizontalAdvance("Th") + fm.horizontalAdvance("i") * 0.62 + size * 0.05
            q.setPen(Qt.NoPen); q.setBrush(RED); q.drawEllipse(QPointF(xi, y - fm.ascent() * 0.80), size * 0.095, size * 0.095)
            return x + fm.horizontalAdvance("ThinkPad")

        def body(self, q, r, g):
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, QColor("#222224")); grad.setColorAt(0.12, BODY); grad.setColorAt(1, QColor("#151516"))
            q.setPen(QPen(EDGE, 1.5)); q.setBrush(QBrush(grad)); q.drawRoundedRect(r, 7, 7)
            q.setPen(QPen(QColor(255, 255, 255, 14), 1)); q.drawLine(r.left() + 8, r.top() + 1.5, r.right() - 8, r.top() + 1.5)
            if g.get("vents"):
                a, b = g["vents"]
                q.setPen(Qt.NoPen); q.setBrush(HOLE)
                x = r.left() + r.width() * a
                while x < r.left() + r.width() * b - 10:
                    q.drawRoundedRect(QRectF(x, r.center().y() - 12, 10, 24), 2, 2); x += 19

        def paintEvent(self, ev):
            q = QPainter(self)
            q.setRenderHint(QPainter.Antialiasing)
            q.setRenderHint(QPainter.SmoothPixmapTransform)
            if self.bg is None or self.bg.size() != self.size():
                self.bg = texture(self.width(), self.height(), QColor("#111112"))
            q.drawPixmap(0, 0, self.bg)
            self.scale = s = max(1.0, self.width() / BASE_W)
            q.scale(s, s)
            W, H = self.width() / s, self.height() / s
            # header
            x_after = self.logo(q, 24, 52, 32)
            q.setFont(font(14, italic=True)); q.setPen(DIM)
            q.drawText(QPointF(x_after + 26, 46), f"{tr('docked') if self.s['docked'] else tr('undocked')}   ·   "
                                                  f"{tr('busy', n=self.s['busy'], m=self.s['total'])}")
            lp = self.logos.get("lenovo")
            if lp:
                q.drawPixmap(QRectF(W - 24 - 100, 22, 100, 100 * lp.height() / lp.width()), lp, QRectF(lp.rect()))
            p = self.s["power"]
            if p["pct"]:
                txt = tr("bat_head", p=p["pct"], st=tr(p["status"]) if p["status"] else "")
                if p["watts"]:
                    txt += f" · {p['watts']} {tr('W')}"
                q.drawText(QRectF(W - 424, 44, 400, 20), Qt.AlignRight, txt)
            # bodies, row by row
            self.rects = {}
            y = 78
            for row in rows_of(self.s["groups"]):
                h = max(g.get("height", 70) for g in row)
                tower_w = 84 if any(g.get("tower") for g in row) else 0
                gap = 14
                avail = W - 48 - tower_w - gap * (len(row) - 1)
                x = 24.0
                for g in row:
                    gw = avail * g.get("w", 1.0)
                    q.setFont(font(13, italic=True)); q.setPen(DIM); q.drawText(QPointF(x + 4, y + 12), g["title"])
                    r = QRectF(x, y + 20, gw, h)
                    self.body(q, r, g)
                    for pt in self.s["ports"].values():
                        if pt["g"] != g["id"]:
                            continue
                        cx, cy = r.left() + r.width() * pt["x"], r.center().y() + 3
                        busy = pt["busy"]
                        self.connector(q, pt["kind"], QPointF(cx, cy), busy)
                        q.setFont(font(10)); q.setPen(INK)
                        q.drawText(QRectF(cx - 40, r.top() + 3, 80, 14), Qt.AlignCenter, pt.get("mark", ""))
                        q.setFont(font(11, bold=busy)); q.setPen(RED if busy else DIM)
                        q.drawText(QRectF(cx - 50, r.bottom() + 3, 100, 16), Qt.AlignCenter, pt["label"])
                        st = next((x for x in pt["stats"] if x), "")
                        if st and self.s["show_stats"]:
                            short = st.split(" · ")[-1] if len(st) > 18 else st
                            q.setFont(font(9)); q.setPen(QColor("#b5565a"))
                            q.drawText(QRectF(cx - 60, r.bottom() + 18, 120, 14), Qt.AlignCenter, short)
                        self.rects[pt["id"]] = QRectF(cx - 36, r.top(), 72, r.height() + 20)
                    if g.get("tower"):
                        self.tower(q, QRectF(W - 24 - tower_w + 8, y + 2, tower_w - 8, h + 18))
                    x += gw + gap
                y += h + (64 if self.s["show_stats"] else 52)
            # connected / events
            q.setFont(font(14, bold=True)); q.setPen(TXT); q.drawText(QPointF(28, y + 6), tr("connected"))
            q.setFont(font(13))
            yy = y + 28
            rows = [(pt["label"], it, st, RED) for pt in self.s["ports"].values() for it, st in zip(pt["items"], pt["stats"])]
            rows += [("?", it, st, QColor("#c9a227")) for it, st in zip(self.s["loose"], self.s["loose_stats"])]
            if self.s.get("dock_hidden"):
                rows.append(("—", tr("dock_hidden"), "", DIM))
            if not rows:
                q.setPen(DIM); q.drawText(QPointF(40, yy), tr("nothing")); yy += 20
            ex = W * 0.60
            colw = ex - 150 - 20  # текст списка не должен залезать на колонку «События»
            for lab, it, st, col in rows:
                if yy > H - 50 - (16 if st else 0):
                    break
                q.setPen(Qt.NoPen); q.setBrush(col); q.drawEllipse(QPointF(36, yy - 4), 3.5, 3.5)
                q.setFont(font(13)); q.setPen(col); q.drawText(QPointF(48, yy), lab)
                fm = QFontMetricsF(font(13))
                q.setPen(TXT); q.drawText(QPointF(140, yy), fm.elidedText(it, Qt.ElideRight, colw))
                if st:  # потребление/нагрузка — отдельной строкой под устройством
                    yy += 16
                    q.setFont(font(11)); q.setPen(QColor("#b5565a"))
                    q.drawText(QPointF(150, yy), QFontMetricsF(font(11)).elidedText(st, Qt.ElideRight, colw - 10))
                yy += 21
            q.setFont(font(14, bold=True)); q.setPen(TXT); q.drawText(QPointF(ex, y + 6), tr("events"))
            q.setFont(font(12)); q.setPen(DIM)
            efm = QFontMetricsF(font(12))
            for i, e in enumerate(self.log or [tr("quiet")]):
                q.drawText(QPointF(ex + 8, y + 28 + i * 19), efm.elidedText(e, Qt.ElideRight, W - ex - 32))
            # footer like the wallpaper: IBM — red line — Technologies and Design
            fy = H - 24
            ib = self.logos.get("ibm")
            if ib:
                q.drawPixmap(QRectF(26, fy - 11, ib.width() * 22 / ib.height(), 22), ib, QRectF(ib.rect()))
            q.setPen(QPen(QColor("#a1121a"), 1))
            q.drawLine(QPointF(78 if ib else 26, fy), QPointF(W - 230, fy)); q.drawLine(QPointF(W - 230, fy), QPointF(W - 230, fy - 14))
            q.setFont(font(12, italic=True)); q.setPen(QColor("#cfcfd1"))
            q.drawText(QRectF(W - 222, fy - 16, 210, 18), Qt.AlignLeft, "Technologies and Design")
            q.end()

        def contextMenuEvent(self, e):
            m = QMenu(self)
            populate(m, in_window=True)
            m.exec(e.globalPos())

        def mouseMoveEvent(self, e):
            pos = e.position() / self.scale
            hit = next((k for k, r in self.rects.items() if r.contains(pos)), None)
            if hit:
                pt = self.s["ports"][hit]
                lines = [i + (f" <span style='color:#d06a6e'>{st}</span>" if st else "") for i, st in zip(pt["items"], pt["stats"])]
                self.setToolTip(f"<b>{pt['label']}</b><br>" + ("<br>".join(lines) or tr("free")))
            else:
                self.setToolTip("")

    def tray_icon(n, docked):
        pm = QPixmap(64, 64); pm.fill(Qt.transparent)
        q = QPainter(pm); q.setRenderHint(QPainter.Antialiasing)
        q.setPen(QPen(QColor("#9a9a9a"), 2.5)); q.setBrush(QColor("#1b1b1c"))
        q.drawRoundedRect(QRectF(4, 20, 56, 26), 4, 4)
        for i in range(4):
            q.setPen(Qt.NoPen); q.setBrush(RED if i < min(n, 4) else QColor("#3a3a3c"))
            q.drawRect(QRectF(11 + i * 11, 30, 7, 5))
        q.setBrush(RED if docked else QColor("#555"))
        q.drawEllipse(QPointF(52, 12), 7, 7)
        q.end()
        return QIcon(pm)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(not tray_mode)
    app.setApplicationName("dockwatch")
    app.setDesktopFileName("dockwatch")
    icon = QIcon.fromTheme("dockwatch")
    if icon.isNull():
        icon = QIcon(os.path.join(HERE, "data", "dockwatch.svg"))
    app.setWindowIcon(icon)
    # одна копия: повторный запуск (иконка, команда в терминале) просто показывает окно уже запущенной
    sock_name = f"dockwatch-{os.getuid()}"
    if tray_mode and not os.environ.get("DOCKWATCH_SCREENSHOT"):
        probe = QLocalSocket()
        probe.connectToServer(sock_name)
        if probe.waitForConnected(300):
            probe.write(b"show" if mode == "app" else b"noop")
            probe.waitForBytesWritten(300)
            probe.disconnectFromServer()
            return
        QLocalServer.removeServer(sock_name)
    view = DockView()
    state = {"prev": view.s}
    tray = None

    def tick():
        s = snapshot()
        ev = diff(state["prev"], s)
        state["prev"] = s
        view.update_state(s, ev)
        if tray:
            tray.setIcon(tray_icon(s["busy"], s["docked"]))
            tray.setToolTip(f"dockwatch · {tr('docked') if s['docked'] else tr('undocked')} · {tr('busy', n=s['busy'], m=s['total'])}")
            for e in ev[:3]:
                tray.showMessage("dockwatch", e, QSystemTrayIcon.Information, 4000)

    def apply(**kw):
        global LANG
        cfg = load_config()
        cfg.update(kw)
        save_config(cfg)
        if "lang" in kw:
            LANG = kw["lang"]
            view.log = []
        state["prev"] = None  # смена языка/профиля — не событие подключения
        tick()

    def populate(menu, in_window=False):
        menu.clear()
        cfg = load_config()
        me = os.path.abspath(__file__)
        if not in_window:
            menu.addAction(tr("m_show"), lambda: (view.show(), view.raise_(), view.activateWindow()))
        menu.addAction(tr("m_tui"), lambda: subprocess.Popen(["konsole", "-e", sys.executable, me, "tui"]))
        menu.addAction(tr("m_cal"), lambda: subprocess.Popen(["konsole", "-e", sys.executable, me, "calibrate"]))
        menu.addSeparator()
        for key, opt in (("m_stats", "show_stats"), ("m_hidedock", "hide_dock")):
            a = menu.addAction(tr(key))
            a.setCheckable(True)
            a.setChecked(bool(cfg.get(opt)))
            a.toggled.connect(lambda v, o=opt: apply(**{o: v}))
        det_dock, det_laptop = detect_profiles(cfg, usb_devices())
        for title, kind, choice_key, det, extra in (
                ("m_laptop", "laptops", "laptop_choice", det_laptop, []),
                ("m_dock", "docks", "dock_choice", det_dock or {"name": cfg.get("dock") and next(
                    (p["name"] for p in load_profiles("docks") if p["id"] == cfg.get("dock")), None) or tr("not_found")},
                 [("none", tr("no_dock"))])):
            sub = menu.addMenu(tr(title))
            grp = QActionGroup(sub)
            cur = cfg.get(choice_key, "auto")
            opts = [("auto", tr("auto", x=(det or {}).get("name") or tr("not_found")))]
            opts += [(p["id"], p["name"]) for p in load_profiles(kind)] + extra
            for val, name in opts:
                a = sub.addAction(name)
                a.setCheckable(True)
                a.setChecked(val == cur)
                grp.addAction(a)
                a.triggered.connect(lambda _=False, k=choice_key, v=val: apply(**{k: v}))
        sub = menu.addMenu(tr("m_lang"))
        grp = QActionGroup(sub)
        for code, name in (("uk", "Українська"), ("ru", "Русский"), ("en", "English")):
            a = sub.addAction(name)
            a.setCheckable(True)
            a.setChecked(code == LANG)
            grp.addAction(a)
            a.triggered.connect(lambda _=False, c=code: apply(lang=c))
        menu.addSeparator()
        menu.addAction(tr("m_quit"), app.quit)

    if tray_mode and QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon(tray_icon(view.s["busy"], view.s["docked"]))
        menu = QMenu()
        populate(menu)
        menu.aboutToShow.connect(lambda: populate(menu))
        tray.setContextMenu(menu)
        tray.activated.connect(lambda r: (view.setVisible(not view.isVisible()), view.raise_())
                               if r == QSystemTrayIcon.Trigger else None)
        tray.show()
    else:
        view.show()
    if tray_mode:
        def show_view():
            view.show(); view.raise_(); view.activateWindow()

        server = QLocalServer(app)
        server.listen(sock_name)

        def on_conn():
            c = server.nextPendingConnection()
            c.waitForReadyRead(300)
            if bytes(c.readAll()) == b"show":
                show_view()
            c.deleteLater()
        server.newConnection.connect(on_conn)
        if mode == "app":
            show_view()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(1000)
    if os.environ.get("DOCKWATCH_SCREENSHOT"):
        sz = os.environ.get("DOCKWATCH_SIZE", "1100x640").split("x")
        view.resize(int(sz[0]), int(sz[1]))
        QTimer.singleShot(400, lambda: (view.grab().save(os.environ["DOCKWATCH_SCREENSHOT"]), app.quit()))
        view.show()
    sys.exit(app.exec())


def main():
    global LANG
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", default="app", choices=["app", "tray", "gui", "tui", "calibrate", "dump"])
    ap.add_argument("--lang", choices=LANGS)
    a = ap.parse_args()
    LANG = detect_lang(load_config(), a.lang)
    {"tui": tui, "calibrate": calibrate, "dump": dump}.get(a.mode, lambda: qt_app(a.mode))()


if __name__ == "__main__":
    main()
