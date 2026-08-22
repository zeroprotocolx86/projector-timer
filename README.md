# Seminar Timer

Dual-screen timer application for seminars and lectures.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-0078d4)
![License](https://img.shields.io/badge/License-MIT-green)

## Features

- **Dual-screen support** - control panel on laptop, fullscreen timer on projector
- **Two modes** - countdown from minutes/seconds, or countdown to specific time
- **Fullscreen projector** - opens automatically on the second monitor, no window borders
- **Projector editor** - customize colors, font size, progress bar
- **Quick adjust** - +/-1m, +/-5m, +/-10m buttons
- **Presets** - save and load timer configurations
- **Sound alerts** - beep when timer finishes
- **Always on top** - control panel stays above other windows

## Quick Start

### Run from Python

```bash
python timer.py
```

### Download EXE

Download `Timer.exe` from [Releases](../../releases) and run it directly.

## How to Use

1. Set minutes and seconds, or choose "To specific time" mode
2. Click **Start** - projector window opens on the second screen automatically
3. Drag the projector window to your projector/external monitor
4. Double-click or press **Pause** to pause/resume
5. Press **Stop** to reset

## Projector Editor

Click **"Editor projector"** to customize:
- Background color
- Timer color with gradient effect
- Label text color
- Status text color
- Progress bar color and height
- Font size
- Show/hide progress bar

Settings are saved automatically.

## Presets

Save your favorite timer configurations:
1. Set up the timer (minutes, seconds, mode, text, color)
2. Click **Save** in the presets section
3. Enter a name
4. Load anytime from the dropdown

## Controls

| Action | Button | Shortcut |
|--------|--------|----------|
| Start | Blue button | - |
| Pause/Resume | Orange button | Double-click, Escape |
| Stop/Reset | Red button | - |
| Hide panel | `_` button | - |

## Requirements

- Windows 10/11
- Python 3.10+ (for running from source)
- No external dependencies required

## Building from Source

```bash
pip install pyinstaller
python -m PyInstaller --onefile --windowed --icon=timer_icon.ico --name "Timer" timer.py
```

## License

MIT
