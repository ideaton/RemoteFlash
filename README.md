# ⚡ RemoteFlash

**Remote AVR flashing over SSH** — flash microcontrollers connected to a remote Linux machine (typically a Raspberry Pi) from the comfort of your Windows desktop.

RemoteFlash connects to the remote host over SSH, uploads your firmware via SFTP, and drives `avrdude` (or `esptool` / `dfu-util`) on the remote side. Pure Python — no OpenSSL, no PuTTY, no external tools required on your PC.

Developed by [IDEATON](https://www.ideaton.pl).

## Features

- **Guided 4-step workflow** — Connection → Firmware → Target → Flash, with live status in the sidebar. No way to get lost.
- **Pure Python SSH/SFTP** (paramiko) — works out of the box on Windows, macOS and Linux.
- **Connection profiles** — save multiple devices (IP, user, SSH key or password), rename them, switch in one click.
- **Device discovery** — automatically scans the remote host for serial ports (`ttyUSB`, `ttyACM`…) and USBasp programmers, with custom labels stored on the remote device itself.
- **AVR chip auto-detection** — reads the device signature through avrdude and adapts the `-p` flag automatically (~30 ATmega/ATtiny chips in the local database).
- **Live command preview** — always see the exact command that will run before you flash.
- **Read flash backup** — dump the current firmware from the controller to a local `.hex` before overwriting it.
- **Auto-update** — checks GitHub Releases at startup; when a newer version exists, a banner offers a one-click download of the installer.

## Installation

Grab the latest release from [Releases](https://github.com/ideaton/RemoteFlash/releases):

- `RemoteFlash_Setup_X.Y.Z.exe` — installer (per-user, no admin rights needed, Start menu + desktop shortcuts, auto-update friendly)
- `RemoteFlash_Portable_X.Y.Z.exe` — single-file portable executable, no installation

## Requirements on the remote host

The remote machine (Raspberry Pi or any Linux box) needs:

- SSH access (key or password)
- `avrdude` installed (`sudo apt install avrdude`) — or `esptool` / `dfu-util` for those workflows
- The programmer or serial adapter plugged into its USB ports

## Quick start

1. **Connection** — enter IP, username and SSH key/password, hit **Connect**. Ports and programmers are scanned automatically.
2. **Firmware** — pick your `.hex` / `.bin` file and the remote upload directory.
3. **Target** — choose Serial or USBasp mode, select the device, optionally hit **Detect AVR chip** to identify the MCU from its signature.
4. **Flash** — review the composed command, then **Upload & Flash**. Output streams into the console on the right.

## Running from source

```
pip install -r app/requirements.txt
python app/app.py
```

Requires Python 3.10+ with tkinter.

## Building the executables

On Windows, with [Inno Setup 6](https://jrsoftware.org/isdl.php) installed:

```
build\build.bat
```

This produces both the installer and the portable exe in `build/Output/`. See [`build/PUBLISH.md`](build/PUBLISH.md) for the full release process (version bump, tagging, GitHub release).

## Project structure

```
app/
  app.py            # main window + updater (Tk application)
  constants.py      # app identity + auto-update source
  theme.py          # colour palette, fonts, ttk styles
  models.py         # enums + data classes
  avr_signatures.py # AVR device-signature database
  ssh_client.py     # pure-Python SSH/SFTP client
  config_manager.py # JSON config persistence
  widgets.py        # custom Tk widgets
  requirements.txt
build/
  build.bat         # PyInstaller + Inno Setup build script
  installer.iss     # Inno Setup installer definition
  PUBLISH.md        # release / auto-update publishing guide
```

## License

© 2026 IDEATON — All rights reserved.
Contact: [p.bayle@ideaton.pl](mailto:p.bayle@ideaton.pl)
