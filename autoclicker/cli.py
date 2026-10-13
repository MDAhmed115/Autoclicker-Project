"""Interactive command-line front end."""
from __future__ import annotations

import msvcrt
import os
import time

from . import __version__
from . import core
from .core import Settings

try:
    import winsound
except ImportError:  # pragma: no cover
    winsound = None


def clear() -> None:
    os.system("cls")


def beep() -> None:
    if winsound:
        try:
            winsound.Beep(1000, 300)
            winsound.Beep(1300, 300)
        except RuntimeError:
            pass


def flush_input() -> None:
    """Drop keystrokes typed while hotkeys were being used (e.g. F6, Esc)."""
    while msvcrt.kbhit():
        msvcrt.getwch()


def ask_number(prompt, default, cast=float, minimum=0):
    while True:
        flush_input()
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = cast(raw)
            if value < minimum:
                raise ValueError
            return value
        except ValueError:
            print(f"  Please enter a number >= {minimum}.")


def ask_choice(prompt, choices, default):
    """choices: dict of key -> label. Returns the chosen key."""
    options = "  ".join(f"[{k}] {v}" for k, v in choices.items())
    while True:
        flush_input()
        raw = input(f"{prompt} {options} (default {default}): ").strip().lower()
        if not raw:
            return default
        if raw in choices:
            return raw
        print("  Not a valid option.")


def ask_yes_no(prompt, default=False):
    d = "y" if default else "n"
    while True:
        flush_input()
        raw = input(f"{prompt} (y/n) [{d}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False


def fmt_time(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def banner() -> None:
    print(f"AutoClicker v{__version__}")
    print("Hotkeys:  F6 = lock position / start   F8 = pause / resume   F9 or Esc = stop")
    print("-" * 70)


def run_round(prefs: dict, stats: dict) -> None:
    clear()
    banner()

    prefs["click_mode"] = ask_choice(
        "Click mode:", {"n": "normal", "f": "super-fast", "h": "hold"}, prefs["click_mode"]
    )
    prefs["count"] = ask_number("Clicks to make (0 = keep going until the target disappears or you stop)",
                                prefs["count"], int, 0)
    if prefs["click_mode"] == "f":
        prefs["delay"] = 0.0
        prefs["jitter"] = 0.0
        prefs["super_fast"] = True
        prefs["hold_seconds"] = 0.0
    elif prefs["click_mode"] == "h":
        prefs["super_fast"] = False
        prefs["hold_seconds"] = ask_number("Hold each click for (seconds)", prefs["hold_seconds"], float, 0.01)
        prefs["delay"] = ask_number("Delay between clicks (seconds)", prefs["delay"], float, 0.01)
        prefs["jitter"] = ask_number("Random extra delay, 0 = none (seconds)", prefs["jitter"], float, 0)
    else:
        prefs["super_fast"] = False
        prefs["hold_seconds"] = 0.02
        prefs["delay"] = ask_number("Delay between clicks (seconds)", prefs["delay"], float, 0.01)
        prefs["jitter"] = ask_number("Random extra delay, 0 = none (seconds)", prefs["jitter"], float, 0)
    prefs["button"] = ask_choice("Mouse button:", {"l": "left", "r": "right", "m": "middle"}, prefs["button"])
    prefs["double"] = ask_yes_no("Double-click?", prefs["double"])
    prefs["mode"] = ask_choice(
        "Target:",
        {"1": "lock a spot with F6", "2": "click it once", "3": "follow my cursor"},
        prefs["mode"],
    )
    if prefs["mode"] in ("1", "2"):
        prefs["watch"] = ask_yes_no("Stop automatically if the button disappears?", prefs["watch"])

    names = {"l": "left", "r": "right", "m": "middle"}
    settings = Settings(
        count=prefs["count"],
        delay=prefs["delay"],
        jitter=prefs["jitter"],
        button=names[prefs["button"]],
        double=prefs["double"],
        watch=prefs["watch"],
        super_fast=prefs["super_fast"],
        hold_seconds=prefs["hold_seconds"],
    )

    print()
    if prefs["mode"] == "1":
        print("Switch to your target window (you can hide this one), hover over the")
        print("button and press F6 to lock it. Esc cancels.")
        if not core.wait_for_key(core.LOCK_KEY):
            print("Cancelled.")
            time.sleep(1)
            return
        settings.pos = core.get_cursor_pos()
    elif prefs["mode"] == "2":
        print("Click the target once. That click counts as click #1. Esc cancels.")
        pos = core.wait_for_click()
        if pos is None:
            print("Cancelled.")
            time.sleep(1)
            return
        settings.pos = pos
        settings.already_done = 1
        if settings.count == 1:
            print("Done. Clicked 1 time.")
            return
        if not settings.super_fast:
            time.sleep(settings.delay)  # let the UI settle before remembering the target
    else:
        print("Hover where you want to click and press F6 to start. Esc cancels.")
        if not core.wait_for_key(core.LOCK_KEY):
            print("Cancelled.")
            time.sleep(1)
            return

    if settings.pos:
        print(f"Target locked at {settings.pos}")
    for i in (3, 2, 1):
        print(f"Starting in {i}...  ", end="\r")
        time.sleep(1)
    print(" " * 30, end="\r")

    total = f"/{settings.count}" if settings.count else ""
    result = core.run(
        settings,
        progress=lambda n: print(f"Clicks: {n}{total}   ", end="\r")
        if not settings.super_fast or n % 100 == 0 or (settings.count and n >= settings.count)
        else None,
        event=lambda msg: print(f"\n{msg}"),
    )

    messages = {
        "completed": "Finished.",
        "stopped": "Stopped by you.",
        "target_gone": "Stopped: the target button is no longer detected (list finished or a popup appeared).",
    }
    print(f"\n{messages[result.reason]} {result.clicks} clicks in {fmt_time(result.seconds)}.")
    beep()

    stats["rounds"] += 1
    stats["clicks"] += result.clicks
    stats["seconds"] += result.seconds


def main() -> None:
    core.enable_dpi_awareness()
    prefs = {
        "count": 0, "delay": 0.8, "jitter": 0.0, "button": "l",
        "double": False, "mode": "1", "watch": True, "super_fast": False,
        "click_mode": "n", "hold_seconds": 0.1,
    }
    stats = {"rounds": 0, "clicks": 0, "seconds": 0.0}

    try:
        while True:
            run_round(prefs, stats)
            print()
            flush_input()
            if input("Run another round? (y/n): ").strip().lower() not in ("y", "yes"):
                break
    except KeyboardInterrupt:
        print()

    if stats["rounds"]:
        print("\nSession summary")
        print(f"  Rounds : {stats['rounds']}")
        print(f"  Clicks : {stats['clicks']}")
        print(f"  Time   : {fmt_time(stats['seconds'])}")
    print("Bye.")


if __name__ == "__main__":
    main()
