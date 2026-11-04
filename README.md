# AutoClicker

Press a hotkey (default F6) to arm it. While armed, holding the left mouse button fires rapid left-clicks until you let go. Tap Ctrl while armed to lock the clicking on without holding the button; tap Ctrl again (or disarm) to stop.

## Install
Grab `AutoClicker-Setup.exe` from the latest [release](https://github.com/jadanduffin/AutoClicker/releases/latest). It asks for admin, defaults to Program Files (any folder works), and adds Start Menu and Desktop shortcuts plus an uninstaller.

## Updates
On launch the app checks the latest GitHub release. If it is newer, a `v1.x available · UPDATE` row appears; UPDATE downloads the new setup and runs it.

## Folders
- `src\` — `AutoClicker.pyw` (the app), icons, `make_icon.py` (redraws the icon), `test_autoclicker.py` (self-test)
- `installer\` — Inno Setup script
- `dist\` — build output: `AutoClicker.exe` (portable) and `AutoClicker-Setup.exe` (installer). Not in git.

## Release a new version
1. Bump `VERSION` in `src\AutoClicker.pyw`.
2. Commit, then:
```
powershell -File build.ps1 -Release
```
That builds both exes and publishes a GitHub release tagged `v<VERSION>` with the setup attached. Installed copies see it on their next launch.

Needs Python 3.14 with Pillow + PyInstaller, Inno Setup 6 (`winget install JRSoftware.InnoSetup`) and a logged-in `gh`.

Settings live in `%APPDATA%\AutoClicker.json`.
