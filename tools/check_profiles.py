#!/usr/bin/env python3
"""Validate profiles/*/*.json: required keys, known connector kinds, groups referenced by ports, x in 0..1."""
import glob
import json
import os
import sys

KINDS = {"usb", "usbc", "hdmi", "dp", "vga", "rj45", "audio", "dc", "card", "dockport", "barrel", "sidedock", "smartcard", "sim", "lock", "sdslot", "barrel_led"}
ROLES = {"power", "eth", "dock", "card", "jack"}
root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles")
errors = 0
for f in sorted(glob.glob(os.path.join(root, "*", "*.json"))):
    rel = os.path.relpath(f, root)
    try:
        p = json.load(open(f))
    except ValueError as e:
        print(f"{rel}: invalid JSON: {e}"); errors += 1; continue
    def err(msg):
        global errors
        print(f"{rel}: {msg}"); errors += 1
    for k in ("id", "name", "groups", "ports"):
        if k not in p:
            err(f"missing '{k}'")
    if p.get("id") and os.path.basename(f) != p["id"] + ".json":
        err(f"file name must be {p['id']}.json")
    gids = {g.get("id") for g in p.get("groups", [])}
    for g in p.get("groups", []):
        if "id" not in g or "title" not in g:
            err(f"group without id/title: {g}")
    ids = set()
    for port in p.get("ports", []):
        pid = port.get("id")
        if not pid or pid in ids:
            err(f"port id missing or duplicate: {pid}")
        ids.add(pid)
        if port.get("kind") not in KINDS:
            err(f"{pid}: unknown kind {port.get('kind')!r} (one of {sorted(KINDS)})")
        if port.get("g") not in gids:
            err(f"{pid}: group {port.get('g')!r} is not defined")
        if not 0 <= float(port.get("x", -1)) <= 1:
            err(f"{pid}: x must be within 0..1")
        if port.get("role") and port["role"] not in ROLES:
            err(f"{pid}: unknown role {port['role']!r}")
    print(f"{rel}: {'ok' if not errors else 'checked'} ({len(ids)} ports)")
sys.exit(1 if errors else 0)
