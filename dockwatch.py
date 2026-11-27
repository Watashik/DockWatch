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
    "rpm": {"uk": "об/хв", "ru": "об/мин", "en": "RPM"},
    "fan_off": {"uk": "вентилятор стоїть", "ru": "вентилятор стоит", "en": "fan stopped"},
    "mic": {"uk": "Мікрофон", "ru": "Микрофон", "en": "Microphone"},
    "cam": {"uk": "Камера", "ru": "Камера", "en": "Camera"},
    "spk": {"uk": "Звук", "ru": "Звук", "en": "Sound"},
    "muted": {"uk": "вимкнено", "ru": "выключен", "en": "muted"},
    "on": {"uk": "увімкнено", "ru": "включён", "en": "on"},
    "recording": {"uk": "пише: {x}", "ru": "пишет: {x}", "en": "recording: {x}"},
    "cam_free": {"uk": "не використовується", "ru": "не используется", "en": "not in use"},
    "cam_busy": {"uk": "увімкнена: {x}", "ru": "включена: {x}", "en": "in use: {x}"},
    "cam_none": {"uk": "немає", "ru": "нет", "en": "none"},
    "shutter": {"uk": "шторка ThinkShutter системою не визначається", "ru": "шторка ThinkShutter системой не определяется",
                "en": "the ThinkShutter cover is not visible to the OS"},
    "bezel": {"uk": "рамка екрана", "ru": "рамка экрана", "en": "display bezel"},
    "headphones": {"uk": "🎧 навушники", "ru": "🎧 наушники", "en": "🎧 headphones"},
    "headset": {"uk": "🎧 гарнітура (з мікрофоном)", "ru": "🎧 гарнитура (с микрофоном)", "en": "🎧 headset (with mic)"},
    "sd_card": {"uk": "💾 картка {size}", "ru": "💾 карта {size}", "en": "💾 card {size}"},
    "off": {"uk": "вимкнено", "ru": "выключен", "en": "off"},
    "eject": {"uk": "⏏ Безпечно вийняти", "ru": "⏏ Безопасно извлечь", "en": "⏏ Safely remove"},
    "open_files": {"uk": "📂 Відкрити у файловому менеджері", "ru": "📂 Открыть в файловом менеджере", "en": "📂 Open in file manager"},
    "ejected": {"uk": "⏏ {x}: можна виймати", "ru": "⏏ {x}: можно вынимать", "en": "⏏ {x}: safe to remove"},
    "eject_fail": {"uk": "Не вдалося вийняти {x}: {e}", "ru": "Не удалось извлечь {x}: {e}", "en": "Could not remove {x}: {e}"},
    "forgot": {"uk": "⚠️ Не забудь: ще підключено {x}", "ru": "⚠️ Не забудь: ещё подключено {x}", "en": "⚠️ Don't forget: {x} is still mounted"},
    "m_autostart": {"uk": "Запускати при вході в систему", "ru": "Запускать при входе в систему", "en": "Start at login"},
    "m_history": {"uk": "Журнал підключень", "ru": "Журнал подключений", "en": "Connection log"},
    "m_lid": {"uk": "Блимати точкою на кришці при подіях", "ru": "Мигать точкой на крышке при событиях", "en": "Blink the lid dot on events"},
    "m_lid_on": {"uk": "Точка на кришці горить постійно", "ru": "Точка на крышке горит постоянно", "en": "Keep the lid dot lit"},
    "m_lid_na": {"uk": "Точка на кришці: потрібне правило udev (install-root.sh)", "ru": "Точка на крышке: нужно правило udev (install-root.sh)",
                 "en": "Lid dot: needs the udev rule (install-root.sh)"},
    "m_profile": {"uk": "Профіль живлення", "ru": "Профиль питания", "en": "Power profile"},
    "power-saver": {"uk": "Енергозбереження", "ru": "Энергосбережение", "en": "Power saver"},
    "balanced": {"uk": "Збалансований", "ru": "Сбалансированный", "en": "Balanced"},
    "performance": {"uk": "Продуктивність", "ru": "Производительность", "en": "Performance"},
    "bat_health": {"uk": "знос {w}% · {c} циклів", "ru": "износ {w}% · {c} циклов", "en": "wear {w}% · {c} cycles"},
    "bt_bat": {"uk": "{n} {b}%", "ru": "{n} {b}%", "en": "{n} {b}%"},
    "m_settings": {"uk": "Налаштування…", "ru": "Настройки…", "en": "Settings…"},
    "rename_dev": {"uk": "✏️ Перейменувати пристрій…", "ru": "✏️ Переименовать устройство…", "en": "✏️ Rename device…"},
    "rename_port": {"uk": "✏️ Перейменувати порт…", "ru": "✏️ Переименовать порт…", "en": "✏️ Rename port…"},
    "new_name": {"uk": "Нова назва (порожньо — як було):", "ru": "Новое название (пусто — как было):", "en": "New name (empty — default):"},
    "s_general": {"uk": "Загальні", "ru": "Общие", "en": "General"},
    "s_ports": {"uk": "Порти", "ru": "Порты", "en": "Ports"},
    "s_devices": {"uk": "Пристрої", "ru": "Устройства", "en": "Devices"},
    "s_theme": {"uk": "Тема", "ru": "Тема", "en": "Theme"},
    "s_scale": {"uk": "Масштаб", "ru": "Масштаб", "en": "Scale"},
    "s_sound": {"uk": "Звук при підключенні", "ru": "Звук при подключении", "en": "Sound on plug/unplug"},
    "s_anim": {"uk": "Анімації", "ru": "Анимации", "en": "Animations"},
    "s_port": {"uk": "Порт", "ru": "Порт", "en": "Port"},
    "s_name": {"uk": "Назва", "ru": "Название", "en": "Name"},
    "s_device": {"uk": "Пристрій", "ru": "Устройство", "en": "Device"},
    "s_my_name": {"uk": "Моя назва", "ru": "Моё название", "en": "My name"},
    "s_hint_dev": {"uk": "Пристрої впізнаються за серійним номером. Порожня назва — заводська.",
                   "ru": "Устройства узнаются по серийному номеру. Пустое название — заводское.",
                   "en": "Devices are recognised by serial number. Empty name — factory name."},
    "theme_thinkpad": {"uk": "ThinkPad (чорна)", "ru": "ThinkPad (чёрная)", "en": "ThinkPad (black)"},
    "theme_ibm": {"uk": "IBM (червоний, синій, зелений)", "ru": "IBM (красный, синий, зелёный)", "en": "IBM (red, blue, green)"},
    "theme_hp": {"uk": "HP (алюміній, блакитний)", "ru": "HP (алюминий, голубой)", "en": "HP (aluminium, blue)"},
    "theme_auto": {"uk": "Авто (за ноутбуком)", "ru": "Авто (по ноутбуку)", "en": "Auto (by laptop)"},
    "theme_light": {"uk": "Світла", "ru": "Светлая", "en": "Light"},
    "close": {"uk": "Закрити", "ru": "Закрыть", "en": "Close"},
    "kbd": {"uk": "Підсвітка клавіатури", "ru": "Подсветка клавиатуры", "en": "Keyboard backlight"},
    "kbd_off": {"uk": "вимкнена", "ru": "выключена", "en": "off"},
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
    cfg.setdefault("lid_blink", False)
    cfg.setdefault("lid_on", False)
    cfg.setdefault("names", {})       # "vid:pid:serial" -> своё имя устройства
    cfg.setdefault("seen", {})        # "vid:pid:serial" -> имя от производителя (для окна настроек)
    cfg.setdefault("sound", True)
    cfg.setdefault("theme", "auto")
    cfg.setdefault("ui_scale", 1.0)
    cfg.setdefault("animations", True)
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
            "serial": rd(f"{p}/serial"),
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


def dev_key(d):
    return f"{d['vid']}:{d['pid']}:{d.get('serial') or '-'}"


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


def usb_disks(name):
    """Блочные устройства (sdX) этого USB-устройства."""
    return [os.path.basename(b) for b in glob.glob("/sys/block/sd*") if in_usb_path(os.path.realpath(b), name)]


def usb_stats(name):
    """Что можно узнать о нагрузке USB-устройства без root: заявленный ток, диск (чтение/запись), сеть.
    Возвращает (текст, суммарная скорость байт/с)."""
    p = f"/sys/bus/usb/devices/{name}"
    out = []
    total = 0.0
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
        total += rx + tx
    for n in glob.glob("/sys/class/net/*"):
        dev = os.path.join(n, "device")
        if os.path.exists(dev) and in_usb_path(os.path.realpath(dev), name):
            r = rate(f"net-r-{n}", int(rd(f"{n}/statistics/rx_bytes", "0") or 0))
            w = rate(f"net-w-{n}", int(rd(f"{n}/statistics/tx_bytes", "0") or 0))
            out.append(f"🌐 ↓{human(r)}{tr('per_s')} ↑{human(w)}{tr('per_s')}")
            total += r + w
    return " · ".join(out), total


def disk_parts(disk):
    """Разделы диска: [(dev, mountpoint, label)] через lsblk (без root)."""
    try:
        j = json.loads(subprocess.run(["lsblk", "-J", "-o", "NAME,MOUNTPOINT,LABEL,TYPE", f"/dev/{disk}"],
                                      capture_output=True, text=True, timeout=3).stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    out = []

    def walk(n):
        if n.get("type") in ("part", "disk") and (n.get("type") == "part" or not n.get("children")):
            out.append(("/dev/" + n["name"], n.get("mountpoint") or "", n.get("label") or ""))
        for c in n.get("children", []) or []:
            walk(c)
    for n in j.get("blockdevices", []):
        walk(n)
    return out


def mounted(disk):
    return [m for _, m, _ in disk_parts(disk) if m]


def eject_disk(disk):
    """Размонтировать все разделы и обесточить (udisks, через polkit — без root). Возвращает текст ошибки или ''."""
    for dev, mnt, _ in disk_parts(disk):
        if mnt:
            r = subprocess.run(["udisksctl", "unmount", "-b", dev], capture_output=True, text=True)
            if r.returncode:
                return (r.stderr or r.stdout).strip().splitlines()[-1] if (r.stderr or r.stdout) else "unmount"
    if not disk.startswith("mmcblk"):  # кард-ридер обесточивать не нужно — он встроенный
        subprocess.run(["udisksctl", "power-off", "-b", f"/dev/{disk}"], capture_output=True, text=True)
    return ""


def open_disk(disk):
    parts = disk_parts(disk)
    mnt = next((m for _, m, _ in parts if m), "")
    if not mnt and parts:
        r = subprocess.run(["udisksctl", "mount", "-b", parts[0][0]], capture_output=True, text=True)
        m = re.search(r" at (.+?)\.?$", r.stdout.strip())
        mnt = m.group(1) if m else ""
    if mnt:
        subprocess.Popen(["xdg-open", mnt], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def battery_info():
    bat = next(iter(glob.glob("/sys/class/power_supply/BAT*")), None)
    if not bat:
        return {}
    full = rd(f"{bat}/energy_full") or rd(f"{bat}/charge_full")
    design = rd(f"{bat}/energy_full_design") or rd(f"{bat}/charge_full_design")
    wear = round(100 - int(full) * 100 / int(design)) if full and design and int(design) else None
    return {"wear": wear, "cycles": rd(f"{bat}/cycle_count")}


def net_info():
    """Wi-Fi (NetworkManager) и Bluetooth-устройства с зарядом — без root."""
    out = {"wifi": None, "bt": []}
    try:
        r = subprocess.run(["nmcli", "-t", "-f", "ACTIVE,SSID,SIGNAL", "dev", "wifi"], capture_output=True, text=True, timeout=2).stdout
        for line in r.splitlines():
            a = line.split(":")
            if a[0] == "yes" and len(a) >= 3:
                out["wifi"] = (":".join(a[1:-1]), a[-1])
                break
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        r = subprocess.run(["bluetoothctl", "devices", "Connected"], capture_output=True, text=True, timeout=2).stdout
        for line in r.splitlines():
            parts = line.split(" ", 2)
            if len(parts) == 3 and parts[0] == "Device":
                info = subprocess.run(["bluetoothctl", "info", parts[1]], capture_output=True, text=True, timeout=2).stdout
                m = re.search(r"Battery Percentage:.*\((\d+)\)", info)
                out["bt"].append((parts[2], int(m.group(1)) if m else None))
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def power_profile(set_to=None):
    try:
        if set_to:
            subprocess.run(["powerprofilesctl", "set", set_to], capture_output=True, timeout=3)
        return subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


LID_DOT = "/sys/class/leds/tpacpi::lid_logo_dot/brightness"


def lid_dot_writable():
    return os.access(LID_DOT, os.W_OK)


def lid_dot(on):
    try:
        with open(LID_DOT, "w") as f:
            f.write("1" if on else "0")
    except OSError:
        pass


def lid_closed():
    return any("closed" in rd(p) for p in glob.glob("/proc/acpi/button/lid/*/state"))


SOUND_DIR = os.path.expanduser("~/.cache/dockwatch")


def chime(kind="in"):
    """Короткий сигнал: «вверх» при подключении, «вниз» при отключении. pw-play/paplay, без зависимостей."""
    import math
    import struct
    import wave
    f = os.path.join(SOUND_DIR, f"{kind}.wav")
    if not os.path.exists(f):
        os.makedirs(SOUND_DIR, exist_ok=True)
        rate, tones = 44100, ((880, 1320) if kind == "in" else (1320, 880))
        frames = bytearray()
        for hz in tones:
            n = int(rate * 0.07)
            for t in range(n):
                env = min(1, t / 300) * min(1, (n - t) / 900)
                frames += struct.pack("<h", int(9000 * env * math.sin(2 * math.pi * hz * t / rate)))
        with wave.open(f, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(frames))
    for player in (["pw-play", f], ["paplay", f], ["aplay", "-q", f]):
        try:
            subprocess.Popen(player, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except OSError:
            continue


def run_in_terminal(*args):
    """Открыть команду в терминале: Konsole, GNOME Terminal/Console, Ptyxis (Fedora), xterm…"""
    import shutil
    cmd = [sys.executable, os.path.abspath(__file__), *args]
    for term, pre in (("konsole", ["-e"]), ("ptyxis", ["--"]), ("gnome-terminal", ["--"]), ("kgx", ["--"]),
                      ("xfce4-terminal", ["-x"]), ("alacritty", ["-e"]), ("kitty", []), ("foot", []), ("xterm", ["-e"])):
        if shutil.which(term):
            subprocess.Popen([term, *pre, *cmd])
            return


HISTORY = os.path.expanduser("~/.local/share/dockwatch/history.log")


def log_event(text):
    try:
        os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
        with open(HISTORY, "a") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S  ") + text + "\n")
    except OSError:
        pass


AUTOSTART = os.path.expanduser("~/.config/autostart/dockwatch.desktop")


def autostart(enable=None):
    if enable is True:
        os.makedirs(os.path.dirname(AUTOSTART), exist_ok=True)
        with open(AUTOSTART, "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=DockWatch\nExec=dockwatch tray\nIcon=dockwatch\n"
                    "X-GNOME-Autostart-enabled=true\nNoDisplay=false\n")
    elif enable is False and os.path.exists(AUTOSTART):
        os.remove(AUTOSTART)
    return os.path.exists(AUTOSTART)


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


def _pactl_json(*args):
    try:
        out = subprocess.run(["pactl", "-f", "json", *args], capture_output=True, text=True, timeout=2).stdout
        return json.loads(out) if out.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def media_state():
    """Микрофон и звук (PipeWire/PulseAudio, светодиоды F1/F4 ThinkPad) и камера (кто открыл /dev/video*)."""
    led = lambda n: rd(f"/sys/class/leds/{n}/brightness") == "1" if os.path.exists(f"/sys/class/leds/{n}") else None  # noqa: E731
    m = {"mic_muted": led("platform::micmute"), "spk_muted": led("platform::mute"),
         "mic_vol": None, "spk_vol": None, "mic_users": [], "cam_present": False, "cam_users": [], "cam_name": ""}
    for kind, key in (("source", "mic"), ("sink", "spk")):
        mu = _pactl_json(f"get-{kind}-mute", f"@DEFAULT_{kind.upper()}@")
        if isinstance(mu, dict) and "mute" in mu:
            m[f"{key}_muted"] = bool(mu["mute"])
        vol = _pactl_json(f"get-{kind}-volume", f"@DEFAULT_{kind.upper()}@")
        try:
            ch = next(iter(vol["volume"].values()))
            m[f"{key}_vol"] = int(str(ch["value_percent"]).rstrip("%"))
        except (TypeError, KeyError, StopIteration, ValueError):
            pass
    srcs = {x["index"]: x["name"] for x in (_pactl_json("list", "sources") or [])}
    for o in _pactl_json("list", "source-outputs") or []:
        name = srcs.get(o.get("source"), "")
        if name.endswith(".monitor") or o.get("corked"):
            continue  # слушают выход (визуализаторы), а не микрофон, или стоят на паузе
        pr = o.get("properties", {})
        m["mic_users"].append(pr.get("application.name") or pr.get("application.process.binary") or pr.get("media.name") or "?")
    kb = next(iter(glob.glob("/sys/class/leds/*kbd_backlight")), None)
    m["kbd"] = int(rd(f"{kb}/brightness", "0") or 0) if kb else None
    m["kbd_max"] = int(rd(f"{kb}/max_brightness", "0") or 0) if kb else 0
    cams = sorted(glob.glob("/dev/video*"))
    m["cam_present"] = bool(cams)
    m["cam_name"] = rd("/sys/class/video4linux/video0/name").split(":")[0]
    users = set()
    for fd in glob.glob("/proc/[0-9]*/fd/*"):
        try:
            if os.readlink(fd) in cams:
                users.add(rd(f"/proc/{fd.split('/')[2]}/comm"))
        except OSError:
            pass
    m["cam_users"] = sorted(users)
    return m


def media_lines(m):
    mic = f"🎙 {tr('mic')}: " + (tr("muted") + " (F4)" if m["mic_muted"] else tr("on") + (f" · {m['mic_vol']}%" if m["mic_vol"] is not None else ""))
    if m["mic_users"]:
        mic += " · " + tr("recording", x=", ".join(dict.fromkeys(m["mic_users"])))
    cam = f"📷 {tr('cam')}: " + (tr("cam_none") if not m["cam_present"] else
                                 tr("cam_busy", x=", ".join(m["cam_users"])) if m["cam_users"] else tr("cam_free"))
    spk = f"🔊 {tr('spk')}: " + (tr("muted") + " (F1)" if m["spk_muted"] else tr("on") + (f" · {m['spk_vol']}%" if m["spk_vol"] is not None else ""))
    return mic, cam, spk


def audio_jack():
    """Что воткнуто в 3.5-мм гнездо: по доступности портов звуковой карты (наушники / микрофон гарнитуры)."""
    hp = mic = False
    for kind in ("sinks", "sources"):
        for x in _pactl_json("list", kind) or []:
            for pt in x.get("ports", []):
                if pt.get("availability") == "available":
                    if "headphone" in pt["name"] or "headset" in pt["name"]:
                        hp = True
                    if pt["name"].endswith("-mic") or "headset-mic" in pt["name"]:
                        mic = True
    return "headset" if hp and mic else "headphones" if hp else ""


def sd_cards():
    """Карты памяти в кард-ридере: размер, метка, где смонтирована, скорость чтения/записи."""
    out = []
    for b in sorted(glob.glob("/sys/block/mmcblk[0-9]")):
        if rd(f"{b}/device/type") not in ("SD", "SDIO"):
            continue  # встроенная eMMC — не карта памяти
        size = int(rd(f"{b}/size", "0") or 0) * 512
        if not size:
            continue
        dev = "/dev/" + os.path.basename(b)
        label = mnt = ""
        try:
            r = subprocess.run(["lsblk", "-nro", "LABEL,MOUNTPOINT", dev], capture_output=True, text=True, timeout=2).stdout
            for line in r.splitlines():
                parts = line.split(" ", 1)
                label = label or parts[0].replace("\\x20", " ")
                mnt = mnt or (parts[1].replace("\\x20", " ") if len(parts) > 1 else "")
        except (OSError, subprocess.SubprocessError):
            pass
        f = rd(f"{b}/stat").split()
        r_ = rate(f"blk-r-{b}", int(f[2]) * 512) if len(f) > 6 else 0
        w_ = rate(f"blk-w-{b}", int(f[6]) * 512) if len(f) > 6 else 0
        item = tr("sd_card", size=human(size)) + (f" · «{label}»" if label else "") + (f" · {mnt}" if mnt else "")
        out.append((item, f"↓{human(r_)}{tr('per_s')} ↑{human(w_)}{tr('per_s')}", r_ + w_, os.path.basename(b)))
    return out


def os_info():
    """Система: название и логотип из /etc/os-release, ядро, окружение рабочего стола."""
    rel = {}
    for line in rd("/etc/os-release").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            rel[k] = v.strip().strip('"')
    logo = rel.get("LOGO") or rel.get("ID", "")
    path = next((f for f in (f"/usr/share/icons/{logo}.svg", f"/usr/share/icons/{logo}.png",
                             f"/usr/share/pixmaps/{logo}.svg", f"/usr/share/pixmaps/{logo}.png") if os.path.exists(f)), "")
    de = os.environ.get("XDG_CURRENT_DESKTOP", "").split(":")[0]
    if de.upper() == "KDE":
        de = "KDE Plasma" + (f" {os.environ['KDE_SESSION_VERSION']}" if os.environ.get("KDE_SESSION_VERSION") else "")
    return {"name": rel.get("NAME") or rel.get("PRETTY_NAME") or "Linux", "version": rel.get("VERSION_ID", ""),
            "logo": logo, "logo_path": path, "kernel": os.uname().release, "desktop": de}


def sensors():
    """Температуры (CPU, GPU, SSD) и обороты вентиляторов из hwmon — без root."""
    temps, fans = {}, []
    want = {"k10temp": ("CPU", "Tctl"), "coretemp": ("CPU", "Package id 0"), "zenpower": ("CPU", "Tdie"),
            "amdgpu": ("GPU", "edge"), "nouveau": ("GPU", ""), "nvme": ("SSD", "Composite")}
    for h in sorted(glob.glob("/sys/class/hwmon/hwmon*")):
        name = rd(f"{h}/name")
        if name in want:
            key, label = want[name]
            for t in sorted(glob.glob(f"{h}/temp*_input")):
                if not label or rd(t.replace("_input", "_label")) == label:
                    v = rd(t)
                    if v.lstrip("-").isdigit() and key not in temps:
                        temps[key] = int(v) / 1000
                    break
        if name == "thinkpad" and "CPU" not in temps:
            v = rd(f"{h}/temp1_input")
            if v.isdigit() and int(v) > 0:
                temps["CPU"] = int(v) / 1000
        for f in sorted(glob.glob(f"{h}/fan*_input")):
            v = rd(f)
            if v.isdigit():
                fans.append(int(v))
    return {"temps": temps, "fans": fans}


def sensors_lines(sn):
    order = sorted(sn["temps"].items(), key=lambda kv: ("CPU", "GPU", "SSD").index(kv[0]) if kv[0] in ("CPU", "GPU", "SSD") else 9)
    temps = ("🌡 " + " · ".join(f"{k} {v:.0f}°C" for k, v in order)) if order else ""
    fans = " · ".join((f"🌀 {f} {tr('rpm')}" if f else f"🌀 {tr('fan_off')}") for f in sn["fans"])
    return [x for x in (temps, fans) if x]


def sensors_text(sn):
    return "   ".join(sensors_lines(sn))


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


OS_INFO = os_info()


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
            lab = p.get("label_docked") if docked and p.get("label_docked") else p.get("label", p["id"])
            ports[p["id"]] = dict(p, owner=where, label=cfg["labels"].get(p["id"]) or pick(lab), label_default=pick(lab),
                                  busy=False, items=[], stats=[], disks=[], rate=0.0)
    loose, loose_stats = [], []
    show = cfg.get("show_stats", True)

    def put(pid, item, stat=""):
        ports[pid]["busy"] = True
        ports[pid]["items"].append(item)
        ports[pid]["stats"].append(stat if show else "")

    def by_role(role, owner):
        return next((pid for pid, p in ports.items() if p.get("role") == role and p["owner"] == owner), None)

    seen_dirty = False
    for d in usb:
        nm = d["product"] or d["maker"] or d["vid"] + ":" + d["pid"]
        if d["maker"] and d["product"] and d["maker"].split()[0].lower() not in d["product"].lower() and len(d["maker"]) < 16:
            nm = f"{d['maker']} {d['product']}"
        k = dev_key(d)
        if cfg["seen"].get(k) != nm:
            cfg["seen"][k] = nm
            seen_dirty = True
        nm = cfg["names"].get(k) or nm
        item = f"{usb_icon(d)} {nm}"
        modes = phone_modes(d)
        if modes:
            item += " · " + " + ".join(tr(m) for m in modes)
        if speed_text(d["speed"]):
            item += f" · {speed_text(d['speed'])}"
        stat, spd = usb_stats(d["name"])
        stat = stat if show else ""
        pid = cfg["usb"].get(d["key"])
        if pid in ports:
            put(pid, item, stat)
            ports[pid]["disks"] += usb_disks(d["name"])
            ports[pid].setdefault("devkeys", []).append(dev_key(d))
            ports[pid]["rate"] += spd
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
            ports[pid]["rate"] += r + w
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
    if seen_dirty:
        try:
            save_config(cfg)
        except OSError:
            pass
    card = by_role("card", "laptop")
    for item, stat, spd, disk in sd_cards():
        if card:
            put(card, item, stat)
            ports[card]["disks"].append(disk)
            ports[card]["rate"] += spd
        else:
            loose.append(item); loose_stats.append(stat if show else "")
    jack = audio_jack()
    if jack:
        pid = by_role("jack", owner) or by_role("jack", "laptop")
        if pid:
            put(pid, tr(jack))
        else:
            loose.append(tr(jack)); loose_stats.append("")
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
            "show_stats": show, "sensors": sensors(), "media": media_state(),
            "battery": battery_info(), "net": net_info(), "lid_closed": lid_closed(), "os": OS_INFO, "ts": time.time()}


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
    om, nm = old.get("media", {}), new.get("media", {})
    if om and nm:
        if om.get("mic_muted") != nm.get("mic_muted"):
            ev.append(f"🎙 {tr('mic')}: {tr('muted') if nm['mic_muted'] else tr('on')}")
        if om.get("cam_users") != nm.get("cam_users"):
            ev.append(f"📷 {tr('cam')}: " + (tr("cam_busy", x=", ".join(nm["cam_users"])) if nm["cam_users"] else tr("cam_free")))
        if om.get("kbd") != nm.get("kbd") and nm.get("kbd") is not None:
            ev.append(f"⌨ {tr('kbd')}: " + (f"{nm['kbd']}/{nm['kbd_max']}" if nm["kbd"] else tr("kbd_off")))
        if bool(om.get("mic_users")) != bool(nm.get("mic_users")):
            ev.append(f"🎙 {tr('mic')}: " + (tr("recording", x=", ".join(nm["mic_users"])) if nm["mic_users"] else tr("cam_free")))
    strip = lambda s: s.rsplit("  [", 1)[0]  # noqa: E731
    for x in sorted(set(map(strip, new["loose"])) - set(map(strip, old["loose"]))):
        ev.append(f"🔴 {x}")
    for x in sorted(set(map(strip, old["loose"])) - set(map(strip, new["loose"]))):
        ev.append(f"⚫ {tr('ev_off')} {x}")
    return ev


def state_json(s, events=None):
    """Состояние для виджета и телефона: схема (группы и порты с координатами) + всё, что видно в окне."""
    cfg = load_config()
    return {"docked": s["docked"], "busy": s["busy"], "total": s["total"], "lang": LANG,
            "theme": cfg.get("theme", "thinkpad"), "show_stats": s["show_stats"],
            "dock": (s["dock"] or {}).get("name"), "laptop": (s["laptop"] or {}).get("name"),
            "groups": [{k: g.get(k) for k in ("id", "title", "row", "w", "tower", "vents", "bezel")} for g in s["groups"]],
            "ports": [{"id": p["id"], "label": p["label"], "group": p["g"], "kind": p["kind"], "x": p["x"],
                       "mark": p.get("mark", ""), "busy": p["busy"], "items": p["items"], "stats": p["stats"]}
                      for p in s["ports"].values()],
            "loose": s["loose"], "loose_stats": s["loose_stats"], "media": s["media"], "sensors": s["sensors"],
            "power": s["power"], "battery": s.get("battery"), "net": s.get("net"), "os": s["os"],
            "events": events or [], "dock_hidden": s.get("dock_hidden"),
            "tr": {k: tr(k) for k in ("docked", "undocked", "connected", "events", "nothing", "quiet", "free", "mic", "cam", "spk",
                                      "muted", "on", "cam_free", "cam_none", "kbd", "kbd_off", "rpm", "dock_hidden")}}


def dump_json():
    print(json.dumps(state_json(snapshot()), ensure_ascii=False))


# ---------------------------------------------------------------- плагины
PLUGIN_DIRS = [os.path.expanduser("~/.local/share/dockwatch/plugins"), os.path.join(HERE, "plugins")]
PLUGINS = []


def load_plugins():
    """Дополнительные модули: *.py из ~/.local/share/dockwatch/plugins (и plugins/ рядом с программой).
    Плагин может определить: TR (переводы), CLI {"режим": функция}, on_start(ctx), on_tick(s, events, ctx),
    menu(add, ctx) — пункты меню. Модуль получает ссылку на DockWatch в атрибуте dw."""
    import importlib.util
    if PLUGINS:
        return PLUGINS
    me = sys.modules[__name__]
    for d in PLUGIN_DIRS:
        for f in sorted(glob.glob(os.path.join(d, "*.py"))):
            try:
                spec = importlib.util.spec_from_file_location(f"dockwatch_plugin_{os.path.basename(f)[:-3]}", f)
                mod = importlib.util.module_from_spec(spec)
                mod.dw = me
                spec.loader.exec_module(mod)
                TR.update(getattr(mod, "TR", {}))
                PLUGINS.append(mod)
            except Exception as e:  # noqa: BLE001 — сломанный плагин не должен ронять программу
                print(f"plugin {f}: {e}", file=sys.stderr)
    return PLUGINS


def plugin_call(name, *a):
    for m in PLUGINS:
        fn = getattr(m, name, None)
        if fn:
            try:
                fn(*a)
            except Exception as e:  # noqa: BLE001
                print(f"plugin {getattr(m, '__name__', m)}.{name}: {e}", file=sys.stderr)


def dump():
    s = snapshot()
    names = " + ".join(p["name"] for p in (s["dock"], s["laptop"]) if p)
    print(f"{names} · {tr('docked') if s['docked'] else tr('undocked')} · {tr('busy', n=s['busy'], m=s['total'])}")
    for g in s["groups"]:
        if g.get("bezel"):
            continue
        print(g["title"] + ":")
        for p in s["ports"].values():
            if p["g"] == g["id"]:
                det = "; ".join(i + (f"  [{st}]" if st else "") for i, st in zip(p["items"], p["stats"]))
                print(f"  {'●' if p['busy'] else '○'} {p['label']:<9} {det}")
    o = s["os"]
    print(f"🐧 {o['name']} {o['version']}".rstrip() + f" · {o['kernel']}" + (f" · {o['desktop']}" if o["desktop"] else ""))
    print("   ".join(media_lines(s["media"])))
    if sensors_text(s["sensors"]):
        print(sensors_text(s["sensors"]))
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
                 "audio": "◉", "card": "▬", "dockport": "⊂▭⊃", "barrel": "◎", "sidedock": "▮", "smartcard": "▬",
                 "sim": "|", "lock": "🔒", "sdslot": "▬", "barrel_led": "◎|", "barrel_dot": "·◎"}
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
            for row in rows_of([g for g in s["groups"] if not g.get("bezel")]):
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
            if sensors_text(s["sensors"]):
                put(y - 1, 3, sensors_text(s["sensors"]), dim)
                y += 1
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
        from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                                       QFormLayout, QHeaderView, QInputDialog, QLabel, QMenu, QSystemTrayIcon,
                                       QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)
    except ImportError:
        sys.exit(tr("need_qt"))

    THEMES = {
        "thinkpad": dict(red="#E2231A", body="#1b1b1c", edge="#2c2c2e", hole="#070707", metal="#8e9196", ink="#6d6f73",
                         txt="#e9e9ea", dim="#7c7e82", bg="#111112", body_hi="#222224", body_lo="#151516", stat="#b5565a", line="#a1121a"),
        "ibm": dict(red="#E2231A", body="#1c1e22", edge="#2d3036", hole="#070708", metal="#8e9196", ink="#6d7078",
                    txt="#e8eaee", dim="#7d818a", bg="#101215", body_hi="#24272c", body_lo="#16181c", stat="#6f9fe0", line="#1F70C1",
                    blue="#1F70C1", green="#2EA44F"),
        "hp": dict(red="#0096D6", body="#b9bcc0", edge="#8e9196", hole="#141518", metal="#6c6f73", ink="#5c5f63",
                   txt="#eef1f4", dim="#8d939b", bg="#16191d", body_hi="#d6d8db", body_lo="#9a9da1", stat="#5fb7e6", line="#0096D6",
                   port_edge="#5a5d61", pin="#2c2e31", key="#1d2025", key_edge="#33373d", led_on="#ffffff", lens="#0d0e10"),
        "light": dict(red="#E2231A", body="#f2f2f3", edge="#c9c9cc", hole="#f7f7f8", metal="#b4b4b8", ink="#8a8a8e",
                      txt="#1d1d1f", dim="#6e6e73", bg="#fafafa", body_hi="#ffffff", body_lo="#e4e4e7", stat="#c0392b", line="#E2231A",
                      port_edge="#b9b9be", pin="#d4d4d8", key="#ffffff", key_edge="#cfcfd3", led_off="#d8d8dc", lens="#e9e9ec",
                      led_on="#f5a623"),
    }
    RED = BODY = EDGE = HOLE = METAL = INK = TXT = DIM = BGC = BODY_HI = BODY_LO = STATC = LINEC = None
    PORT_EDGE = PIN = KEYC = KEY_EDGE = LED_OFF = LENS = LED_ON = None
    ACCENT = {}  # вид разъёма -> цвет подсветки (в теме IBM — три цвета, иначе везде красный)
    THEME = {"name": "thinkpad"}

    def accent(kind):
        return ACCENT.get(kind, RED)

    def apply_theme(name):
        nonlocal RED, BODY, EDGE, HOLE, METAL, INK, TXT, DIM, BGC, BODY_HI, BODY_LO, STATC, LINEC
        nonlocal PORT_EDGE, PIN, KEYC, KEY_EDGE, LED_OFF, LENS, LED_ON
        base = dict(port_edge="#3a3a3d", pin="#2a2a2c", key="#0f0f10", key_edge="#2e2e30", led_off="#333333", lens="#0b0b0c",
                    led_on="#f4f4f4")
        t = {k: QColor(v) for k, v in {**base, **THEMES.get(name, THEMES["thinkpad"])}.items()}
        PORT_EDGE, PIN, KEYC, KEY_EDGE, LED_OFF, LENS = t["port_edge"], t["pin"], t["key"], t["key_edge"], t["led_off"], t["lens"]
        LED_ON = t["led_on"]
        RED, BODY, EDGE, HOLE, METAL, INK = t["red"], t["body"], t["edge"], t["hole"], t["metal"], t["ink"]
        TXT, DIM, BGC, BODY_HI, BODY_LO, STATC, LINEC = t["txt"], t["dim"], t["bg"], t["body_hi"], t["body_lo"], t["stat"], t["line"]
        THEME["name"] = name if name in THEMES else "thinkpad"
        ACCENT.clear()
        if "blue" in t:
            b, g = t["blue"], t["green"]
            ACCENT.update(usb=b, usbc=b, card=b, hdmi=b, dp=b, vga=b, dockport=b, rj45=g, audio=g, dc=RED)

    def resolve_theme(cfg=None):
        cfg = cfg or load_config()
        t = cfg.get("theme", "auto")
        if t in THEMES:
            return t
        d, l = detect_profiles(cfg, usb_devices())  # «авто»: тема по ноутбуку (или доку)
        chosen = {p["id"]: p for p in load_profiles("laptops")}.get(cfg.get("laptop_choice"))
        return next((p.get("theme") for p in (chosen or l, d) if p and p.get("theme") in THEMES), "thinkpad")

    apply_theme(resolve_theme())
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
            q.setPen(QColor(*(min(255, max(0, v + c)) for v in (base.red(), base.green(), base.blue()))))
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
            self.hist = {}
            self.lit = {}        # pid -> когда порт загорелся (для плавного зажигания)
            self.fan_angle = 0.0
            self.anim_t = time.monotonic()
            self.profile = power_profile()
            self.setMouseTracking(True)

        def update_state(self, s, events):
            self.s = s
            from collections import deque
            for pid, pt in s["ports"].items():
                if pt["busy"]:
                    self.hist.setdefault(pid, deque(maxlen=60)).append(pt.get("rate", 0.0))
                    self.lit.setdefault(pid, time.monotonic())
                else:
                    self.hist.pop(pid, None)
                    self.lit.pop(pid, None)
            for e in events:
                self.log.insert(0, time.strftime("%H:%M:%S  ") + e)
            self.log = self.log[:5]
            self.blink ^= 1
            self.update()

        def dark(self):
            return BGC.lightness() < 100  # логотипы с обоев белые — на светлых темах рисуем надпись

        def animating(self):
            if not load_config().get("animations", True):
                return False
            now = time.monotonic()
            return any(now - t < 0.8 for t in self.lit.values())

        def connector(self, q, kind, c, busy, k=1.0, pid=None):
            fade = 1.0
            if busy and pid in self.lit and load_config().get("animations", True):
                fade = min(1.0, (time.monotonic() - self.lit[pid]) / 0.6)
            q.save()
            q.translate(c)
            q.scale(k, k)
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
                # сверху — лоток SIM с отверстием для скрепки, снизу — тонкий слот microSD (светится только он)
                tray = QPainterPath(); tray.addRoundedRect(QRectF(-22, -11, 44, 10), 3, 3)
                q.setPen(QPen(PORT_EDGE, 1.6)); q.setBrush(BODY_LO); q.drawPath(tray)
                q.setPen(Qt.NoPen); q.setBrush(HOLE); q.drawEllipse(QPointF(-15, -6), 1.6, 1.6)
                path.addRoundedRect(QRectF(-22, 3, 44, 5), 2, 2)
                inner.addRect(QRectF(-18, 4.6, 36, 1.8))
            elif kind in ("barrel", "barrel_led", "barrel_dot"):  # круглый разъём питания (с лампочкой сбоку/точкой)
                path.addEllipse(QPointF(0, 0), 8, 8); inner.addEllipse(QPointF(0, 0), 2.6, 2.6)
            elif kind == "sdslot":  # тонкий слот карты памяти
                path.addRoundedRect(QRectF(-16, -2.5, 32, 5), 2, 2); inner.addRect(QRectF(-12, -0.8, 24, 1.6))
            elif kind == "sidedock":  # длинный боковой разъём дока (HP) — вытянут вдоль боковины
                path.addRoundedRect(QRectF(-34, -6, 68, 12), 3, 3); inner.addRect(QRectF(-30, -1.6, 60, 3.2))
            elif kind == "smartcard":
                path.addRoundedRect(QRectF(-44, -2.8, 88, 5.6), 2, 2); inner.addRect(QRectF(-40, -0.8, 80, 1.6))
            elif kind == "sim":
                path.addRoundedRect(QRectF(-2.5, -11, 5, 22), 2, 2); inner.addEllipse(QPointF(0, 7), 1, 1)
            elif kind == "lock":  # замок Kensington
                path.addRoundedRect(QRectF(-7, -4, 14, 8), 2, 2); inner.addRect(QRectF(-4, -1, 8, 2))
            else:
                path.addRoundedRect(QRectF(-12, -8, 24, 16), 3, 3)
            if busy:
                if kind == "card":
                    q.translate(0, 5.5)  # свечение — вокруг слота карты, а не лотка SIM
                g = QRadialGradient(QPointF(0, 0), 46)
                cg = QColor(accent(kind)); cg.setAlpha(int(95 * fade)); g.setColorAt(0, cg)
                cg = QColor(accent(kind)); cg.setAlpha(0); g.setColorAt(1, cg)
                q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(0, 0), 46, 30)
                if kind == "card":
                    q.translate(0, -5.5)
            q.setPen(QPen(PORT_EDGE, 1.6)); q.setBrush(HOLE); q.drawPath(path)
            q.setPen(Qt.NoPen); q.setBrush(accent(kind) if busy else PIN); q.drawPath(inner)
            if kind == "vga":
                for sx in (-34, 34):
                    q.setBrush(METAL); q.setPen(QPen(QColor("#555"), 1)); q.drawEllipse(QPointF(sx, 0), 5, 5)
                    q.setBrush(HOLE); q.drawEllipse(QPointF(sx, 0), 2, 2)
            if kind == "barrel_dot":  # точка-индикатор зарядки рядом с разъёмом
                q.setPen(Qt.NoPen); q.setBrush(QColor("#f6f6f6") if busy else LED_OFF); q.drawEllipse(QPointF(-15, 0), 2, 2)
            if kind == "barrel_led":  # вертикальная лампочка справа от разъёма: горит, когда док под питанием
                led = QRectF(14, -9, 3.5, 18)
                if busy:
                    g2 = QRadialGradient(led.center(), 14); c2 = QColor("#ffffff"); c2.setAlpha(150); g2.setColorAt(0, c2)
                    c2.setAlpha(0); g2.setColorAt(1, c2); q.setPen(Qt.NoPen); q.setBrush(QBrush(g2)); q.drawEllipse(led.center(), 14, 14)
                q.setPen(Qt.NoPen); q.setBrush(QColor("#f6f6f6") if busy else LED_OFF); q.drawRoundedRect(led, 1.5, 1.5)
            if kind == "rj45":
                for lx, on, col in ((-13, busy, QColor("#3ddc84")), (13, busy and self.blink, QColor("#ffb020"))):
                    q.setPen(Qt.NoPen); q.setBrush(col if on else LED_OFF); q.drawRect(QRectF(lx - 3, -19, 6, 3))
            q.restore()

        def tower(self, q, r):
            q.setPen(QPen(EDGE, 1.5)); q.setBrush(BODY_LO); q.drawRoundedRect(r, 6, 6)
            c = QPointF(r.center().x(), r.top() + r.height() * 0.32)
            if self.s["docked"]:
                g = QRadialGradient(c, 22); cg = QColor(RED); cg.setAlpha(120); g.setColorAt(0, cg)
                cg.setAlpha(0); g.setColorAt(1, cg); q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(c, 22, 22)
            q.setPen(QPen(PORT_EDGE, 2)); q.setBrush(HOLE); q.drawEllipse(c, 10, 10)
            q.setPen(QPen(RED if self.s["docked"] else QColor("#444"), 2))
            q.drawArc(QRectF(c.x() - 5, c.y() - 5, 10, 10), 120 * 16, 300 * 16)
            q.drawLine(QPointF(c.x(), c.y() - 7), QPointF(c.x(), c.y() - 1))
            k = QPointF(r.center().x(), r.top() + r.height() * 0.74)
            q.setPen(QPen(KEY_EDGE, 3)); q.setBrush(KEYC); q.drawEllipse(k, 11, 11)
            q.setPen(QPen(METAL, 2.5)); q.drawLine(QPointF(k.x() - 6, k.y()), QPointF(k.x() + 6, k.y()))

        def ibm_logo(self, q, x, y, h, colors=("#E2231A", "#2EA44F", "#1F70C1")):
            """Полосатый логотип IBM (8 полос), буквы — красная, зелёная, синяя. y — нижняя линия, h — высота букв."""
            f = QFont("Liberation Sans"); f.setPixelSize(int(h * 1.38)); f.setBold(True); f.setStretch(125)
            fm = QFontMetricsF(f)
            stripes = QPainterPath()
            bar = h / 15.0  # 8 полос и 7 зазоров: полоса чуть толще зазора
            top = y - h
            for i in range(8):
                stripes.addRect(QRectF(x - 2, top + i * bar * 2 - bar * 0.15, fm.horizontalAdvance("IBM") + 8, bar * 1.3))
            cx = x
            for ch, col in zip("IBM", colors):
                path = QPainterPath(); path.addText(QPointF(cx, y), f, ch)
                q.setPen(Qt.NoPen); q.setBrush(QColor(col)); q.drawPath(path.intersected(stripes))
                cx += fm.horizontalAdvance(ch) + h * 0.08
            return cx

        def brand_logo(self, q, x, y, size, text):
            """Надпись бренда для не-ThinkPad (напр. EliteBook): тонкий шрифт с разрядкой и акцентная черта."""
            f = QFont("Liberation Sans"); f.setPixelSize(int(size * 0.95)); f.setLetterSpacing(QFont.AbsoluteSpacing, size * 0.06)
            f.setWeight(QFont.Light)
            q.setFont(f); q.setPen(TXT); q.drawText(QPointF(x, y - 4), text)
            w = QFontMetricsF(f).horizontalAdvance(text)
            q.setPen(Qt.NoPen); q.setBrush(RED); q.drawRect(QRectF(x, y + 2, w * 0.28, 2.5))
            return x + w

        def logo(self, q, x, y, size):
            brand = (self.s.get("laptop") or {}).get("brand")
            if brand and THEME["name"] not in ("ibm",) and brand != "ThinkPad":
                return self.brand_logo(q, x, y, size, brand)
            if THEME["name"] == "ibm":  # тема IBM: вместо ThinkPad — полосатый IBM в трёх цветах
                return self.ibm_logo(q, x, y - 4, size * 1.05)
            pm = self.logos.get("thinkpad") if self.dark() and THEME["name"] != "ibm" else None
            if pm:
                h = size * 1.55
                q.drawPixmap(QRectF(x, y - h * 0.86, pm.width() * h / pm.height(), h), pm, QRectF(pm.rect()))
                return x + pm.width() * h / pm.height()
            f = font(size, True, True); q.setFont(f); q.setPen(TXT)
            q.drawText(QPointF(x, y), "ThinkPad")
            fm = QFontMetricsF(f)
            xi = x + fm.horizontalAdvance("Th") + fm.horizontalAdvance("i") * 0.62 + size * 0.05
            if THEME["name"] == "ibm":  # как на ThinkPad времён IBM: красный, зелёный, синий квадратики
                sq = size * 0.11
                for i, col in enumerate(("#E2231A", "#2EA44F", "#1F70C1")):
                    q.setPen(Qt.NoPen); q.setBrush(QColor(col))
                    q.drawRect(QRectF(xi - sq * 1.6 + i * sq * 1.1, y - fm.ascent() * 0.86 - sq / 2, sq, sq))
            else:
                q.setPen(Qt.NoPen); q.setBrush(RED); q.drawEllipse(QPointF(xi, y - fm.ascent() * 0.80), size * 0.095, size * 0.095)
            return x + fm.horizontalAdvance("ThinkPad")

        def body(self, q, r, g):
            grad = QLinearGradient(r.topLeft(), r.bottomLeft())
            grad.setColorAt(0, BODY_HI); grad.setColorAt(0.12, BODY); grad.setColorAt(1, BODY_LO)
            q.setPen(QPen(EDGE, 1.5)); q.setBrush(QBrush(grad)); q.drawRoundedRect(r, 7, 7)
            q.setPen(QPen(QColor(255, 255, 255, 14), 1)); q.drawLine(r.left() + 8, r.top() + 1.5, r.right() - 8, r.top() + 1.5)
            if g.get("vents"):
                a, b = g["vents"]
                sn = self.s.get("sensors", {"temps": {}, "fans": []})
                hot = max(sn["temps"].values(), default=0)
                k = min(1.0, max(0.0, (hot - 45) / 45))  # 45°C — тёмная, 90°C — раскалённая
                h0 = HOLE if BGC.lightness() > 150 else QColor(7, 7, 7)  # на светлой теме решётка светлая
                fill = QColor(int(h0.red() + (150 - h0.red()) * k), int(h0.green() + (18 - h0.green()) * k), int(h0.blue() + (14 - h0.blue()) * k))
                if BGC.lightness() > 150:
                    q.setPen(QPen(PORT_EDGE, 1))
                else:
                    q.setPen(Qt.NoPen)
                q.setBrush(fill)
                x0, x1 = r.left() + r.width() * a, r.left() + r.width() * b
                x = x0
                while x < x1 - 10:
                    q.drawRoundedRect(QRectF(x, r.center().y() - 12, 10, 24), 2, 2); x += 19
                lines = sensors_lines(sn)
                if lines:  # подпись под решёткой, сама решётка остаётся открытой
                    f = font(11)
                    fm = QFontMetricsF(f)
                    q.setFont(f)
                    for i, t in enumerate(lines):
                        q.setPen((QColor("#e0a0a3") if k > 0.5 else TXT) if i == 0 else DIM)
                        q.drawText(QRectF(x0, r.bottom() + 3 + i * 16, x1 - x0, 16), Qt.AlignCenter,
                                   fm.elidedText(t, Qt.ElideRight, x1 - x0))

        def key(self, q, k, top, bottom, led):
            q.setPen(QPen(KEY_EDGE, 1)); q.setBrush(KEYC); q.drawRoundedRect(k, 4, 4)
            q.setFont(font(10)); q.setPen(TXT); q.drawText(QRectF(k.left() + 6, k.top() + 3, k.width() - 6, 14), Qt.AlignLeft, top)
            q.setFont(font(9)); q.setPen(DIM); q.drawText(QRectF(k.left() + 6, k.bottom() - 15, k.width() - 6, 13), Qt.AlignLeft, bottom)
            c = QPointF(k.right() - 8, k.top() + 8)
            if led:
                g = QRadialGradient(c, 10); cg = QColor(LED_ON); cg.setAlpha(150)
                g.setColorAt(0, cg); cg.setAlpha(0); g.setColorAt(1, cg); q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(c, 10, 10)
            if led is not None:  # None — у клавиши свой индикатор (рисуется отдельно)
                q.setPen(Qt.NoPen); q.setBrush(LED_ON if led is True else LED_OFF)
                q.drawEllipse(c, 2.3, 2.3)

        def header_media(self, q, kx, cx, cy, maxw):
            """F1/F4 со светодиодами после логотипа; микрофоны и камера — по центру шапки, строка состояния под ними."""
            m = self.s.get("media") or {}
            keys = {"spk": "F1", "mic": "F4", "kbd": "Fn+Space", **((self.s.get("laptop") or {}).get("keys") or {})}
            self.key(q, QRectF(kx, cy - 17, 54, 34), "🔇", "" if keys["spk"] == "🔇" else keys["spk"], bool(m.get("spk_muted")))
            self.key(q, QRectF(kx + 62, cy - 17, 54, 34), "🎙", "" if keys["mic"] == "🎙" else keys["mic"], bool(m.get("mic_muted")))
            if m.get("kbd") is not None:  # подсветка клавиатуры (Fn+Space): уровни полосками
                k = QRectF(kx + 124, cy - 17, 70, 34)
                self.key(q, k, "⌨", "" if keys["kbd"] == "⌨" else keys["kbd"], None)
                lvl, mx_ = m["kbd"], max(1, m["kbd_max"])
                for i in range(mx_):
                    on = i < lvl
                    q.setPen(Qt.NoPen); q.setBrush(LED_ON if on else LED_OFF)
                    q.drawRoundedRect(QRectF(k.right() - 10, k.top() + 5 + (mx_ - 1 - i) * 7, 5, 5), 1, 1)
            live = bool(m.get("mic_users")) and not m.get("mic_muted")
            for x in (cx - 56, cx + 56):
                if live:
                    g = QRadialGradient(QPointF(x, cy), 13); cg = QColor(RED); cg.setAlpha(150); g.setColorAt(0, cg)
                    cg.setAlpha(0); g.setColorAt(1, cg); q.setPen(Qt.NoPen); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(x, cy), 13, 13)
                q.setPen(QPen(PORT_EDGE, 1)); q.setBrush(HOLE if BGC.lightness() < 150 else PIN); q.drawEllipse(QPointF(x, cy), 3, 3)
                if m.get("mic_muted"):
                    q.setPen(QPen(QColor("#8a8a8d"), 1.3)); q.drawLine(QPointF(x - 6, cy + 6), QPointF(x + 6, cy - 6))
            cam_on = bool(m.get("cam_users"))
            q.setPen(QPen(PORT_EDGE, 2)); q.setBrush(LENS); q.drawEllipse(QPointF(cx, cy), 13, 13)
            q.setBrush(BODY_LO); q.drawEllipse(QPointF(cx, cy), 8, 8)
            q.setPen(Qt.NoPen); q.setBrush(RED if m.get("cam_present") else QColor("#333")); q.drawEllipse(QPointF(cx, cy), 2.6, 2.6)
            lx = cx + 26
            if cam_on:
                g = QRadialGradient(QPointF(lx, cy), 12); cg = QColor("#ffffff"); cg.setAlpha(170); g.setColorAt(0, cg)
                cg.setAlpha(0); g.setColorAt(1, cg); q.setBrush(QBrush(g)); q.drawEllipse(QPointF(lx, cy), 12, 12)
            q.setBrush(QColor("#fafafa") if cam_on else LED_OFF); q.drawEllipse(QPointF(lx, cy), 2.4, 2.4)
            if not m:
                return
            mic = tr("muted") if m["mic_muted"] else (tr("recording", x=", ".join(dict.fromkeys(m["mic_users"]))) if m["mic_users"]
                                                      else f"{m['mic_vol']}%" if m["mic_vol"] is not None else tr("on"))
            cam = tr("cam_none") if not m["cam_present"] else (", ".join(m["cam_users"]) if m["cam_users"] else tr("cam_free"))
            spk = tr("muted") if m["spk_muted"] else (f"{m['spk_vol']}%" if m["spk_vol"] is not None else tr("on"))
            line = f"🎙 {mic}     📷 {cam}     🔊 {spk}"
            f = font(11, bold=live or cam_on)
            q.setFont(f); q.setPen(RED if live or cam_on else DIM)
            q.drawText(QRectF(cx - maxw / 2, cy + 20, maxw, 16), Qt.AlignCenter,
                       QFontMetricsF(f).elidedText(line, Qt.ElideRight, maxw))

        def paintEvent(self, ev):
            q = QPainter(self)
            q.setRenderHint(QPainter.Antialiasing)
            q.setRenderHint(QPainter.SmoothPixmapTransform)
            if self.bg is None or self.bg.size() != self.size():
                self.bg = texture(self.width(), self.height(), BGC)
            q.drawPixmap(0, 0, self.bg)
            # мягкое масштабирование: на большом экране чуть крупнее, но не во всю ширину (1920 px → ×1.3)
            ui = float(load_config().get("ui_scale", 1.0) or 1.0)
            self.scale = s = min(1.3, max(1.0, 1 + (self.width() / BASE_W - 1) * 0.4)) * ui
            q.scale(s, s)
            W, H = self.width() / s, self.height() / s
            # header
            x_after = self.logo(q, 24, 52, 32)
            q.setFont(font(12, italic=True)); q.setPen(DIM)
            q.drawText(QPointF(26, 76), f"{tr('docked') if self.s['docked'] else tr('undocked')}  ·  "
                                        f"{tr('busy', n=self.s['busy'], m=self.s['total'])}")
            is_tp = (self.s.get("laptop") or {}).get("brand", "ThinkPad") == "ThinkPad" if self.s.get("laptop") else True
            lp = self.logos.get("lenovo") if self.dark() and THEME["name"] != "ibm" and is_tp else None
            if lp:
                q.drawPixmap(QRectF(W - 24 - 100, 22, 100, 100 * lp.height() / lp.width()), lp, QRectF(lp.rect()))
            p = self.s["power"]
            if p["pct"]:
                txt = tr("bat_head", p=p["pct"], st=tr(p["status"]) if p["status"] else "")
                if p["watts"]:
                    txt += f" · {p['watts']} {tr('W')}"
                q.setFont(font(12, italic=True))
                q.drawText(QRectF(W - 284, 46, 260, 20), Qt.AlignRight, txt)
            b, n = self.s.get("battery") or {}, self.s.get("net") or {}
            extra = []
            if b.get("wear") is not None:
                extra.append(tr("bat_health", w=b["wear"], c=b.get("cycles") or "?"))
            if self.profile:
                extra.append(tr(self.profile))
            line2 = []
            if n.get("wifi"):
                line2.append(f"📶 {n['wifi'][0]} {n['wifi'][1]}%")
            for name, bat in n.get("bt", []):
                line2.append(f"ᛒ {name}" + (f" {bat}%" if bat is not None else ""))
            q.setFont(font(10)); q.setPen(DIM)
            if extra:
                q.drawText(QRectF(W - 324, 64, 300, 16), Qt.AlignRight, " · ".join(extra))
            if line2:
                q.drawText(QRectF(W - 324, 79, 300, 16), Qt.AlignRight,
                           QFontMetricsF(font(10)).elidedText("   ".join(line2), Qt.ElideRight, 300))
            if any(g.get("bezel") for g in self.s["groups"]):
                left = max(x_after + 28, 190)
                self.header_media(q, left, W / 2, 38, min(W - 2 * (left + 130), 2 * (W - 300 - W / 2)))
            # bodies, row by row
            self.rects = {}
            y = 98
            # корпуса во всю ширину, но тонкие (по высоте — впритык к разъёмам); на широком окне разъёмы крупнее
            CW, off = W, 0.0
            kz = min(1.45, max(1.0, W / BASE_W))
            for row in rows_of([g for g in self.s["groups"] if not g.get("bezel")]):
                h = 26 + 32 * kz
                tower_w = 84 * (1 + (kz - 1) * 0.5) if any(g.get("tower") for g in row) else 0
                gap = 14
                avail = CW - 48 - tower_w - gap * (len(row) - 1)
                x = off + 24.0
                wsum = sum(g.get("w", 1.0) for g in row)
                for g in row:
                    gw = avail * g.get("w", 1.0) / max(1.0, wsum)  # несколько профилей в одном ряду — делим ширину
                    q.setFont(font(13, italic=True)); q.setPen(DIM); q.drawText(QPointF(x + 4, y + 12), g["title"])
                    r = QRectF(x, y + 20, gw, h)
                    self.body(q, r, g)
                    for pt in self.s["ports"].values():
                        if pt["g"] != g["id"]:
                            continue
                        cx, cy = r.left() + r.width() * pt["x"], r.center().y() + 3
                        busy = pt["busy"]
                        self.connector(q, pt["kind"], QPointF(cx, cy), busy, kz, pt["id"])
                        q.setFont(font(10)); q.setPen(INK)
                        q.drawText(QRectF(cx - 40, r.top() + 3, 80, 14), Qt.AlignCenter, pt.get("mark", ""))
                        q.setFont(font(11, bold=busy)); q.setPen(accent(pt["kind"]) if busy else DIM)
                        q.drawText(QRectF(cx - 50, r.bottom() + 3, 100, 16), Qt.AlignCenter, pt["label"])
                        st = next((x for x in pt["stats"] if x), "")
                        if st and self.s["show_stats"]:
                            short = st.split(" · ")[-1] if len(st) > 18 else st
                            q.setFont(font(9)); q.setPen(STATC)
                            q.drawText(QRectF(cx - 60, r.bottom() + 18, 120, 14), Qt.AlignCenter, short)
                        self.rects[pt["id"]] = QRectF(cx - 36 * kz, r.top(), 72 * kz, r.height() + 20)
                    if g.get("tower"):
                        self.tower(q, QRectF(off + CW - 24 - tower_w + 8, y + 2, tower_w - 8, h + 18))
                    x += gw + gap
                y += h + (34 if all(g.get("bezel") for g in row) else
                          64 if self.s["show_stats"] or any(g.get("vents") for g in row) else 52)
            # connected / events — в той же центральной колонке, что и схема
            q.save(); q.translate(off, 0); W_full, W = W, CW
            q.setFont(font(14, bold=True)); q.setPen(TXT); q.drawText(QPointF(28, y + 6), tr("connected"))
            q.setFont(font(13))
            yy = y + 28
            rows = [(pt["label"], it, st, accent(pt["kind"])) for pt in self.s["ports"].values() for it, st in zip(pt["items"], pt["stats"])]
            pid_of = {(pt["label"], pt["items"][0]): pt["id"] for pt in self.s["ports"].values() if pt["items"]}
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
                    q.setFont(font(11)); q.setPen(STATC)
                    fm11 = QFontMetricsF(font(11))
                    st_e = fm11.elidedText(st, Qt.ElideRight, colw - 90)
                    q.drawText(QPointF(150, yy), st_e)
                    hist = self.hist.get(pid_of.get((lab, it)))
                    if hist and max(hist) > 0:  # мини-график скорости за последнюю минуту
                        gx, gw_, gh = 158 + fm11.horizontalAdvance(st_e), 70, 12
                        mx_ = max(hist)
                        path = QPainterPath()
                        for i, v in enumerate(hist):
                            px_, py_ = gx + gw_ * i / max(1, len(hist) - 1), yy - gh * v / mx_
                            path.lineTo(px_, py_) if i else path.moveTo(px_, py_)
                        q.setPen(QPen(QColor("#d0464c"), 1.2)); q.setBrush(Qt.NoBrush); q.drawPath(path)
                yy += 21
            q.setFont(font(14, bold=True)); q.setPen(TXT); q.drawText(QPointF(ex, y + 6), tr("events"))
            q.setFont(font(12)); q.setPen(DIM)
            efm = QFontMetricsF(font(12))
            for i, e in enumerate(self.log or [tr("quiet")]):
                q.drawText(QPointF(ex + 8, y + 28 + i * 19), efm.elidedText(e, Qt.ElideRight, W - ex - 32))
            q.restore(); W = W_full
            # footer like the wallpaper: IBM — red line — Technologies and Design
            fy = H - 24
            is_tp = (self.s.get("laptop") or {}).get("brand", "ThinkPad") == "ThinkPad" if self.s.get("laptop") else True
            ib = self.logos.get("ibm") if self.dark() and THEME["name"] != "ibm" and is_tp else None
            if THEME["name"] == "ibm":
                self.ibm_logo(q, 26, fy + 8, 16, (LINEC.name(),) * 3)
                ib = True
            elif ib:
                q.drawPixmap(QRectF(26, fy - 11, ib.width() * 22 / ib.height(), 22), ib, QRectF(ib.rect()))
            q.setPen(QPen(LINEC, 1))
            q.drawLine(QPointF(78 if ib else 26, fy), QPointF(W - 230, fy)); q.drawLine(QPointF(W - 230, fy), QPointF(W - 230, fy - 14))
            q.setFont(font(12, italic=True)); q.setPen(TXT)
            q.drawText(QRectF(W - 222, fy - 16, 210, 18), Qt.AlignLeft,
                       (self.s.get("laptop") or {}).get("footer") or "Technologies and Design")
            o = self.s.get("os") or {}
            if o:  # система: логотип дистрибутива + название, ядро, рабочий стол
                if not hasattr(self, "os_icon"):
                    ic = QIcon.fromTheme(o["logo"]) if o["logo"] else QIcon()
                    if ic.isNull() and o["logo_path"]:
                        ic = QIcon(o["logo_path"])
                    if ic.isNull():
                        ic = QIcon.fromTheme("distributor-logo")
                    self.os_icon = None if ic.isNull() else ic.pixmap(64, 64)
                txt = f"{o['name']} {o['version']}".rstrip() + f"  ·  {o['kernel']}" + (f"  ·  {o['desktop']}" if o["desktop"] else "")
                q.setFont(font(11)); fm = QFontMetricsF(font(11))
                tw = fm.horizontalAdvance(txt)
                x0 = (W - tw) / 2 + 12
                if self.os_icon is not None:
                    q.drawPixmap(QRectF(x0 - 24, fy - 23, 18, 18), self.os_icon, QRectF(self.os_icon.rect()))
                q.setPen(DIM); q.drawText(QPointF(x0, fy - 9), txt)
            q.end()

        def contextMenuEvent(self, e):
            m = QMenu(self)
            pos = e.pos() / self.scale
            hit = next((k for k, r in self.rects.items() if r.contains(pos)), None)
            disks = list(dict.fromkeys(self.s["ports"][hit]["disks"])) if hit else []
            if hit:
                pt = self.s["ports"][hit]
                m.addSection(pt["label"])
                if disks:
                    m.addAction(tr("open_files"), lambda: [open_disk(d) for d in disks])
                    m.addAction(tr("eject"), lambda: do_eject(pt["label"], disks))
                for dk in dict.fromkeys(pt.get("devkeys", [])):
                    m.addAction(tr("rename_dev") + f"  ({load_config()['seen'].get(dk, dk)})", lambda d=dk: rename("names", d))
                m.addAction(tr("rename_port"), lambda p_=hit: rename("labels", p_))
                m.addSeparator()
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
    ctx = {}  # передаётся плагинам; заполняется ниже, когда всё создано

    def notify(text):
        if tray:
            tray.showMessage("dockwatch", text, QSystemTrayIcon.Information, 5000)
        else:
            subprocess.Popen(["notify-send", "-a", "dockwatch", "dockwatch", text], stderr=subprocess.DEVNULL)

    def blink(n=3):
        if not (load_config().get("lid_blink") and lid_dot_writable()):
            return
        was = rd(LID_DOT) == "1" or bool(load_config().get("lid_on"))
        state["blinking_until"] = time.time() + n * 2 * 0.22 + 0.5
        for i in range(n * 2):
            QTimer.singleShot(i * 220, lambda on=(i % 2 == 0) != was: lid_dot(on))
        QTimer.singleShot(n * 2 * 220, lambda: lid_dot(was))

    def rename(section, key):
        cfg = load_config()
        cur = cfg[section].get(key, "")
        default = cfg["seen"].get(key, key) if section == "names" else next(
            (pick(p.get("label", p["id"])) for prof in (view.s["dock"], view.s["laptop"]) if prof
             for p in prof.get("ports", []) if p["id"] == key), key)
        text, ok = QInputDialog.getText(view, "dockwatch", f"{default}\n{tr('new_name')}", text=cur)
        if ok:
            cfg = load_config()
            if text.strip():
                cfg[section][key] = text.strip()
            else:
                cfg[section].pop(key, None)
            save_config(cfg)
            state["prev"] = None
            tick()

    def settings():
        cfg = load_config()
        dlg = QDialog(view)
        dlg.setWindowTitle("dockwatch — " + tr("m_settings").rstrip("…"))
        dlg.resize(620, 480)
        tabs = QTabWidget(dlg)
        # общие
        gen = QWidget(); form = QFormLayout(gen)
        lang = QComboBox(); [lang.addItem(n, c) for c, n in (("uk", "Українська"), ("ru", "Русский"), ("en", "English"))]
        lang.setCurrentIndex(LANGS.index(LANG))
        theme = QComboBox(); [theme.addItem(tr(f"theme_{t}"), t) for t in ("auto", *THEMES)]
        theme.setCurrentIndex(max(0, ["auto", *THEMES].index(cfg.get("theme", "auto")) if cfg.get("theme") in ("auto", *THEMES) else 0))
        scale = QDoubleSpinBox(); scale.setRange(0.8, 1.6); scale.setSingleStep(0.05); scale.setValue(float(cfg.get("ui_scale", 1.0)))
        form.addRow(tr("m_lang"), lang); form.addRow(tr("s_theme"), theme); form.addRow(tr("s_scale"), scale)
        checks = {}
        opts = [("show_stats", "m_stats"), ("hide_dock", "m_hidedock"), ("sound", "s_sound"), ("animations", "s_anim")]
        if lid_dot_writable():
            opts += [("lid_blink", "m_lid"), ("lid_on", "m_lid_on")]
        for opt, key in opts:
            c = QCheckBox(tr(key)); c.setChecked(bool(cfg.get(opt))); form.addRow(c); checks[opt] = c
        auto = QCheckBox(tr("m_autostart")); auto.setChecked(autostart()); form.addRow(auto)
        tabs.addTab(gen, tr("s_general"))
        # порты
        ports = [(pid, p) for pid, p in view.s["ports"].items()]
        pt = QTableWidget(len(ports), 2); pt.setHorizontalHeaderLabels([tr("s_port"), tr("s_name")])
        pt.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, (pid, p) in enumerate(ports):
            gt = next((g["title"] for g in view.s["groups"] if g["id"] == p["g"]), p["g"])
            it = QTableWidgetItem(f"{p.get('label_default', pid)}  ·  {gt}"); it.setFlags(Qt.ItemIsEnabled); pt.setItem(i, 0, it)
            pt.setItem(i, 1, QTableWidgetItem(cfg["labels"].get(pid, "")))
        tabs.addTab(pt, tr("s_ports"))
        # устройства
        seen = sorted(cfg["seen"].items(), key=lambda kv: kv[1].lower())
        dw = QWidget(); dl = QVBoxLayout(dw); dl.addWidget(QLabel(tr("s_hint_dev")))
        dt = QTableWidget(len(seen), 2); dt.setHorizontalHeaderLabels([tr("s_device"), tr("s_my_name")])
        dt.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for i, (k, nm) in enumerate(seen):
            it = QTableWidgetItem(nm); it.setToolTip(k); it.setFlags(Qt.ItemIsEnabled); dt.setItem(i, 0, it)
            dt.setItem(i, 1, QTableWidgetItem(cfg["names"].get(k, "")))
        dl.addWidget(dt); tabs.addTab(dw, tr("s_devices"))
        lay = QVBoxLayout(dlg); lay.addWidget(tabs)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); lay.addWidget(bb)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        cfg = load_config()
        for opt, c in checks.items():
            cfg[opt] = c.isChecked()
        cfg["theme"] = theme.currentData(); cfg["ui_scale"] = round(scale.value(), 2)
        for i, (pid, _) in enumerate(ports):
            v = (pt.item(i, 1).text() if pt.item(i, 1) else "").strip()
            cfg["labels"].pop(pid, None) if not v else cfg["labels"].__setitem__(pid, v)
        for i, (k, _) in enumerate(seen):
            v = (dt.item(i, 1).text() if dt.item(i, 1) else "").strip()
            cfg["names"].pop(k, None) if not v else cfg["names"].__setitem__(k, v)
        save_config(cfg)
        autostart(auto.isChecked())
        if cfg.get("lid_on") and lid_dot_writable():
            lid_dot(True)
        apply_theme(resolve_theme(cfg))
        view.bg = None
        apply(lang=lang.currentData())

    def do_eject(label, disks):
        err = next((e for e in (eject_disk(d) for d in disks) if e), "")
        notify(tr("eject_fail", x=label, e=err) if err else tr("ejected", x=label))
        log_event(("eject failed " if err else "ejected ") + label)

    def tick():
        s = snapshot()
        prev = state["prev"]
        ev = diff(prev, s)
        state["prev"] = s
        view.update_state(s, ev)
        plugin_call("on_tick", s, ev, ctx)
        for e in ev:
            log_event(e)
        if ev:
            blink()
            if load_config().get("sound", True):
                chime("in" if any(e.startswith("🔴") for e in ev) else "out")
        elif load_config().get("lid_on") and lid_dot_writable() and rd(LID_DOT) != "1" and not state.get("blinking_until", 0) > s["ts"]:
            lid_dot(True)  # держим точку включённой (после сна система её гасит)
        # «не забудь флешку»: сняли с дока или закрыли крышку, а носитель всё ещё смонтирован
        if prev and ((prev["docked"] and not s["docked"]) or (not prev.get("lid_closed") and s.get("lid_closed"))):
            left = [pt["label"] for pt in prev["ports"].values() if any(mounted(d) for d in pt.get("disks", []))]
            if left:
                notify(tr("forgot", x=", ".join(left)))
        if tray:
            tray.setIcon(tray_icon(s["busy"], s["docked"]))
            tray.setToolTip(f"dockwatch · {tr('docked') if s['docked'] else tr('undocked')} · {tr('busy', n=s['busy'], m=s['total'])}")
            for e in ev[:3]:
                tray.showMessage("dockwatch", e, QSystemTrayIcon.Information, 4000)
        if s["ts"] - state.get("prof_ts", 0) > 10:
            view.profile = power_profile()
            state["prof_ts"] = s["ts"]

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
        menu.addAction(tr("m_settings"), settings)
        plugin_call("menu", lambda title, fn: menu.addAction(title, fn), ctx)
        menu.addAction(tr("m_tui"), lambda: run_in_terminal("tui"))
        menu.addAction(tr("m_cal"), lambda: run_in_terminal("calibrate"))
        menu.addSeparator()
        for key, opt in (("m_stats", "show_stats"), ("m_hidedock", "hide_dock")):
            a = menu.addAction(tr(key))
            a.setCheckable(True)
            a.setChecked(bool(cfg.get(opt)))
            a.toggled.connect(lambda v, o=opt: apply(**{o: v}))
        if lid_dot_writable():
            a = menu.addAction(tr("m_lid"))
            a.setCheckable(True)
            a.setChecked(bool(cfg.get("lid_blink")))
            a.toggled.connect(lambda v: (apply(lid_blink=v), v and blink(2)))
            a = menu.addAction(tr("m_lid_on"))
            a.setCheckable(True)
            a.setChecked(bool(cfg.get("lid_on")))
            a.toggled.connect(lambda v: (apply(lid_on=v), lid_dot(v)))
        elif os.path.exists(LID_DOT):
            a = menu.addAction(tr("m_lid_na"))
            a.setEnabled(False)
        a = menu.addAction(tr("m_autostart"))
        a.setCheckable(True)
        a.setChecked(autostart())
        a.toggled.connect(lambda v: autostart(v))
        cur = power_profile()
        if cur:
            sub = menu.addMenu(tr("m_profile"))
            grp = QActionGroup(sub)
            for prof in ("power-saver", "balanced", "performance"):
                a = sub.addAction(tr(prof))
                a.setCheckable(True)
                a.setChecked(prof == cur)
                grp.addAction(a)
                a.triggered.connect(lambda _=False, pr=prof: (power_profile(pr), setattr(view, "profile", power_profile()), view.update()))
        menu.addAction(tr("m_history"), lambda: (os.makedirs(os.path.dirname(HISTORY), exist_ok=True),
                                                  open(HISTORY, "a").close(),
                                                  subprocess.Popen(["xdg-open", HISTORY], stderr=subprocess.DEVNULL)))
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

    def anim_tick():
        if view.isVisible() and view.animating():
            view.update()
        else:
            view.anim_t = time.monotonic()

    ctx.update({"view": view, "tray": lambda: tray, "app": app, "notify": notify,
                "QtWidgets": __import__("PySide6.QtWidgets", fromlist=["x"]), "QtGui": __import__("PySide6.QtGui", fromlist=["x"]), "Qt": Qt})
    plugin_call("on_start", ctx)
    anim = QTimer()
    anim.timeout.connect(anim_tick)
    anim.start(50)
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
    load_plugins()
    extra = {k: v for m in PLUGINS for k, v in getattr(m, "CLI", {}).items()}
    ap.add_argument("mode", nargs="?", default="app", choices=["app", "tray", "gui", "tui", "calibrate", "dump", "json", *extra])
    ap.add_argument("--lang", choices=LANGS)
    a = ap.parse_args()
    LANG = detect_lang(load_config(), a.lang)
    {"tui": tui, "calibrate": calibrate, "dump": dump, "json": dump_json, **extra}.get(a.mode, lambda: qt_app(a.mode))()


if __name__ == "__main__":
    main()
