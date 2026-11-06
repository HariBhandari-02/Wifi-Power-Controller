# Wi-Fi Power Controller

A tiny Linux utility to view and toggle **Wi-Fi power saving** with one click.
Power saving can add latency spikes and jitter on some adapters — turning it off
often gives a steadier ping for gaming and calls, while turning it on saves
battery on a laptop.

<!-- TODO: add a screenshot (docs/screenshot.png) and reference it here -->

## Features

- Small Tk GUI showing the detected adapter and current power-saving state
- One-click **Turn On / Turn Off**, with a context hint (gaming ping vs. battery)
- Status auto-refreshes every 5 seconds
- Friendly error dialogs (auth dismissed, not authorized, command failure)
- CLI mode for scripts and hotkeys: `--status`, `--on`, `--off`, `--interface`
- No dependencies beyond Python 3, tkinter, `iw` and `pkexec`
- Optional Polkit rule to skip the password prompt

## Supported distributions

Works on any Linux distribution with Python 3, tkinter, `iw` and Polkit
(`pkexec`). Developed and tested on Ubuntu/Zorin OS; `install.sh` prints package
hints for Debian/Ubuntu, Fedora/RHEL, Arch and openSUSE families.

The optional Polkit rule uses the JavaScript rules format (polkit ≥ 0.106, e.g.
Ubuntu 22.04+, Fedora, Arch).

## Quick start

```bash
git clone https://github.com/HariBhandari-02/Wifi-Power-Controller.git
cd Wifi-Power-Controller
./install.sh
```

Then launch **Wi-Fi Power Controller** from your app menu, or run
`~/.local/bin/wifi-power-toggle.py`.

Missing something? On Debian/Ubuntu:

```bash
sudo apt install python3 python3-tk iw policykit-1
```

To skip the password prompt on every toggle, see
[Optional Polkit rule](#optional-polkit-rule).

## Usage

| Command | What it does |
| --- | --- |
| `wifi-power-toggle.py` | Open the GUI (default) |
| `wifi-power-toggle.py --status` | Print the current power-saving state |
| `wifi-power-toggle.py --on` | Enable power saving |
| `wifi-power-toggle.py --off` | Disable power saving |
| `wifi-power-toggle.py --interface wlan0` | Use a specific interface (combine with any of the above) |

`--status`, `--on` and `--off` are mutually exclusive. Exit code is `0` on
success and `1` on error. Example:

```console
$ wifi-power-toggle.py --off
wlp3s0: power saving off
```

## How it works

- Detects your Wi-Fi interface with `iw dev` (preferring a "managed" interface
  and ignoring P2P-device/monitor ones).
- Reads the state with `iw dev <interface> get power_save`.
- Changes it with `iw dev <interface> set power_save on|off`, elevated through
  `pkexec` when you are not root.
- Binaries are found via `PATH` (plus `/usr/sbin` and `/sbin`), so nothing is
  hard-coded.

The setting is **not persistent**: it resets after a reboot or when the
adapter/driver reloads.

## Optional Polkit rule

By default each toggle asks for your password via `pkexec`. Installing with

```bash
./install.sh --with-polkit
```

adds `/etc/polkit-1/rules.d/50-wifi-power-toggle.rules` (one `sudo` prompt
during install). It lets members of the `sudo` (or `wheel`) group run
`pkexec <iw> dev <interface> set power_save on|off` without a password.

**Security note:** the rule matches the exact `iw` binary and a command line of
the form `iw dev <interface> set power_save on|off` — any other `iw` invocation
still requires authentication. It relies on Polkit exposing the
`command_line` detail of the `pkexec` action; if that detail is unavailable the
rule does not match and you simply get the normal password prompt. Still, it
grants passwordless privilege to every admin user of the machine for this one
operation, so only enable it on machines where you are comfortable with that.
Remove it with `./uninstall.sh`.

## Troubleshooting

- **"Wi-Fi adapter: Not found"** — run `iw dev` in a terminal. If it shows no
  interface, the driver isn't loaded or the adapter is disabled.
- **"Unable to read status"** — some drivers don't support querying power
  save; try `iw dev <interface> get power_save` directly.
- **"Required program not found: iw"** — install `iw` (see Quick start).
- **Command not found after install** — make sure `~/.local/bin` is on your
  `PATH`, or launch it from the app menu.
- **Setting reverts** — NetworkManager or TLP may re-apply power saving; check
  `/etc/NetworkManager/conf.d/` (`wifi.powersave`) and your TLP config.
- **No password prompt appears** — you need a running Polkit authentication
  agent (present on all common desktop environments).

## Uninstall

```bash
./uninstall.sh
```

Removes the script, desktop entry, icon, refreshes caches and (with `sudo`)
removes the Polkit rule if present.

## Contributing

Issues and pull requests are welcome. Before submitting:

```bash
python3 -m py_compile wifi-power-toggle.py
python3 -m unittest discover -s tests -v
shellcheck install.sh uninstall.sh
```

CI runs the same checks plus `desktop-file-validate`. Parsing logic lives in
pure functions so it can be tested without root, a GUI or Wi-Fi hardware.

## Acknowledgements

Inspired by a tip on the Zorin OS forum about turning off Wi-Fi power saving.
This project is an independent implementation and contains no code copied from
that post.

## License

[MIT](LICENSE) © 2026 Hari Bhandari
