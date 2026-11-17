# Notepad for Linux

A Windows 11-style Notepad clone built with Python 3 and PyQt6. It includes
find and replace, go to line, word wrap, zoom, printing, page setup, drag and
drop, and persistent settings.

## Install as a desktop app

```bash
./install.sh
```

This installs everything for your user only:

- the application and a private Python environment in `~/.local/share/notepad/`
- the `notepad` command in `~/.local/bin/`
- a **Notepad** entry in the application menu
- icons in the `hicolor` icon theme

The first install downloads PyQt6 into the private environment. After that,
launch **Notepad** from your application menu, or from a terminal:

```bash
notepad
notepad document.txt
```

The app registers itself for `text/plain` files so it appears in **Open With**
menus. It does **not** change your default text editor.

### Make it the default editor (optional)

```bash
xdg-mime default notepad.desktop text/plain
```

To restore your previous editor, set it again with `xdg-mime default`, or pick
one in your desktop's file-association settings.

### Uninstall

```bash
./uninstall.sh
```

The installed copy works too:

```bash
~/.local/share/notepad/uninstall.sh
```

Add `--purge` to also remove saved settings, and `--yes` to skip confirmation.

## Run without installing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 notepad.py
```

On Arch Linux you can instead install the system package:

```bash
sudo pacman -S python-pyqt6
```
