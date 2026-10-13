# AutoClicker

A lightweight, dependency-free auto clicker for Windows. Configure it from the terminal, then control it with global hotkeys while another window is active. It supports single- and multi-monitor setups, including display scaling.

Originally built to handle repetitive bank-feed tasks, it can automate other repetitive clicks too.

## Features

- **Three click modes:** normal clicks with a configurable interval, super-fast clicks with no intentional delay, or held clicks with a configurable button-down duration.
- Set a click count, or use `0` to continue until you stop the run or (when enabled) the target is no longer detected.
- Add random extra delay (jitter) to normal and held clicks.
- Choose the left, right, or middle mouse button, and enable double-clicks.
- Choose how to target the click:
  1. **Lock a position:** hover over the target and press F6.
  2. **Click the target once:** that initial left click counts toward the total.
  3. **Follow the cursor:** press F6, then clicks use the cursor's current position.
- Optionally stop when the pixels around a locked target change. This is available for normal and held clicks; it is disabled in super-fast mode.
- Pause and resume with F8, or stop with F9 or Esc.
- Beep when a run completes, then optionally start another round. Settings carry over between rounds, and a session summary reports total rounds, clicks, and time.

## Requirements

- Windows
- Python 3.8 or later

There are no runtime package dependencies.

## Run from source

In the project directory, run:

```powershell
py main.py
```

You can also run it as a module:

```powershell
py -m autoclicker
```

To install the `autoclicker` command:

```powershell
py -m pip install .
autoclicker
```

## How to use

1. Start the program and answer the configuration prompts.
2. Choose a target mode. For a locked position or cursor-following run, switch to the target window and press F6 when prompted. For click-to-target mode, click the target once; this initial left click counts as the first click.
3. A three-second countdown begins, then the run starts.
4. Press F8 to pause; press F8 again to resume. Press F9 or Esc to stop.

In locked-position mode, the program moves the real cursor to that position for each click. Avoid using the mouse during the run. In cursor-following mode, it clicks wherever the cursor is at each click.

## Hotkeys

| Key | Action |
| --- | --- |
| F6 | Lock a position or start a cursor-following run |
| F8 | Pause or resume the current run |
| F9 | Stop the current run |
| Esc | Cancel target selection or stop the current run |

Hotkeys work while another window is active. Esc is also sent to the focused application, so use F9 if Esc could close a dialog or trigger an action in that application. Hotkey constants can be changed in `autoclicker/core.py`.

## Build a standalone executable

Install PyInstaller and build from the project directory:

```powershell
py -m pip install pyinstaller
py -m PyInstaller --onefile --console --name AutoClicker main.py
```

The executable is written to `dist/AutoClicker.exe`. You can attach it to a GitHub Release for users who do not have Python installed.

## Notes

- Target detection compares a sample of screen pixels around the locked position with the original sample. Animations, hover effects, or other visual changes can trigger a stop; disable target watching for targets whose appearance changes. Target watching is not used in super-fast mode.
- Automated input may be restricted by some games and anti-cheat systems. Follow the rules of the software you use.

## License

MIT. See [LICENSE](LICENSE).
