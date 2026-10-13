"""Low-level Windows helpers and the click engine.

Uses only the standard library (ctypes), so there is nothing to pip install.
The engine knows nothing about the terminal, so a GUI can reuse it later.
"""
from __future__ import annotations

import ctypes
import random
import sys
import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

if sys.platform != "win32":
    raise SystemExit("This autoclicker only runs on Windows.")

Point = Tuple[int, int]
Snapshot = List[Tuple[int, int, int]]

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

user32.GetDC.restype = ctypes.c_void_p
user32.GetDC.argtypes = [ctypes.c_void_p]
user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
gdi32.GetPixel.restype = ctypes.c_uint32
gdi32.GetPixel.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

# ---- Hotkeys (virtual-key codes). Change these if a key clashes with your app.
VK_LBUTTON = 0x01
VK_ESCAPE = 0x1B
VK_F6 = 0x75
VK_F8 = 0x77
VK_F9 = 0x78

LOCK_KEY = VK_F6          # lock the target position / start
PAUSE_KEY = VK_F8         # pause and resume
STOP_KEYS = (VK_F9, VK_ESCAPE)  # stop the current run

_BUTTONS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def enable_dpi_awareness() -> None:
    """Make coordinates match real pixels on scaled displays."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass


def get_cursor_pos() -> Point:
    pt = _POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def any_down(vks) -> bool:
    return any(key_down(k) for k in vks)


def click(button: str = "left", double: bool = False, pos: Optional[Point] = None,
          super_fast: bool = False, hold_seconds: float = 0.02) -> None:
    """Click at pos (or at the current cursor position if pos is None)."""
    if pos is not None:
        user32.SetCursorPos(int(pos[0]), int(pos[1]))
    down, up = _BUTTONS[button]
    for _ in range(2 if double else 1):
        user32.mouse_event(down, 0, 0, 0, 0)
        if hold_seconds > 0:
            time.sleep(hold_seconds)
        user32.mouse_event(up, 0, 0, 0, 0)
        if double and not super_fast:
            time.sleep(0.04)


# ---- Waiting for the user (works no matter which window has focus) ----------

def wait_for_key(vk: int, cancel=(VK_ESCAPE,)) -> bool:
    """Block until vk is pressed (True) or a cancel key is pressed (False)."""
    while key_down(vk) or any_down(cancel):
        time.sleep(0.02)
    while True:
        if key_down(vk):
            return True
        if any_down(cancel):
            return False
        time.sleep(0.02)


def wait_for_click(cancel=(VK_ESCAPE,)) -> Optional[Point]:
    """Block until the left mouse button is clicked; return where. None if cancelled."""
    while key_down(VK_LBUTTON) or any_down(cancel):
        time.sleep(0.02)
    while True:
        if key_down(VK_LBUTTON):
            pos = get_cursor_pos()
            while key_down(VK_LBUTTON):
                time.sleep(0.02)
            return pos
        if any_down(cancel):
            return None
        time.sleep(0.02)


# ---- Target-still-there detection ------------------------------------------

def _grid(pos: Point, w: int = 31, h: int = 13, step: int = 3):
    x0, y0 = pos[0] - w // 2, pos[1] - h // 2
    return [(x0 + dx, y0 + dy) for dx in range(0, w, step) for dy in range(0, h, step)]


def snapshot(pos: Point) -> Snapshot:
    """Remember the pixel colours around pos."""
    hdc = user32.GetDC(None)
    try:
        return [(x, y, gdi32.GetPixel(hdc, x, y)) for x, y in _grid(pos)]
    finally:
        user32.ReleaseDC(None, hdc)


def similarity(snap: Snapshot) -> float:
    """Fraction (0-1) of the remembered pixels that still have the same colour."""
    hdc = user32.GetDC(None)
    try:
        same = sum(1 for x, y, c in snap if gdi32.GetPixel(hdc, x, y) == c)
    finally:
        user32.ReleaseDC(None, hdc)
    return same / len(snap)


# ---- Engine ------------------------------------------------------------------

@dataclass
class Settings:
    count: int = 0                  # 0 = unlimited (until stopped / target gone)
    delay: float = 0.8              # seconds between clicks
    jitter: float = 0.0             # random extra 0..jitter seconds per click
    button: str = "left"
    double: bool = False
    pos: Optional[Point] = None     # None = click wherever the cursor is
    watch: bool = True              # stop automatically if the target disappears
    threshold: float = 0.6          # similarity below this counts as "gone"
    already_done: int = 0           # clicks already made before the run starts
    super_fast: bool = False        # no intentional click hold or inter-click delay
    hold_seconds: float = 0.02      # button-down duration for each click


@dataclass
class Result:
    clicks: int
    reason: str                     # "completed" | "stopped" | "target_gone"
    seconds: float


def _sleep(seconds: float) -> bool:
    """Sleep in small slices. Returns True if a stop key was pressed."""
    end = time.time() + seconds
    while time.time() < end:
        if any_down(STOP_KEYS):
            return True
        time.sleep(min(0.05, max(0.0, end - time.time())))
    return any_down(STOP_KEYS)


def run(
    s: Settings,
    progress: Optional[Callable[[int], None]] = None,
    event: Optional[Callable[[str], None]] = None,
) -> Result:
    start = time.time()
    paused_for = 0.0
    done = s.already_done
    snap = snapshot(s.pos) if (s.pos is not None and s.watch and not s.super_fast) else None

    def finish(reason: str) -> Result:
        return Result(done, reason, time.time() - start - paused_for)

    while s.count == 0 or done < s.count:
        if any_down(STOP_KEYS):
            return finish("stopped")

        if key_down(PAUSE_KEY):
            if event:
                event("Paused. Press F8 to resume.")
            t0 = time.time()
            time.sleep(0.4)
            while not key_down(PAUSE_KEY):
                if any_down(STOP_KEYS):
                    return finish("stopped")
                time.sleep(0.05)
            time.sleep(0.4)
            paused_for += time.time() - t0
            if event:
                event("Resumed.")

        if snap is not None and similarity(snap) < s.threshold:
            time.sleep(0.6)  # give a laggy UI one more chance
            if similarity(snap) < s.threshold:
                return finish("target_gone")

        click(s.button, s.double, s.pos, s.super_fast, s.hold_seconds)
        done += 1
        if progress:
            progress(done)

        if s.count and done >= s.count:
            break
        if _sleep(0 if s.super_fast else s.delay + random.uniform(0, s.jitter)):
            return finish("stopped")

    return finish("completed")
