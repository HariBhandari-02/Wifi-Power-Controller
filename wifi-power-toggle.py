#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Hari Bhandari
"""Wi-Fi Power Controller: view and toggle Wi-Fi power saving on Linux.

Runs as a small Tk GUI by default, or as a CLI with --status / --on / --off.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

try:
    import tkinter as tk
    from tkinter import messagebox, ttk
except ImportError:  # CLI still works without tkinter
    tk = None

REFRESH_MS = 5000
APP_TITLE = "Wi-Fi Power Controller"


# --------------------------------------------------------------------------
# Pure parsing helpers (no I/O, unit-tested)
# --------------------------------------------------------------------------


def parse_interfaces(text):
    """Parse `iw dev` output into a list of (name, type) tuples.

    `type` is None when the interface block has no "type" line.
    """
    interfaces = []
    name = None
    iftype = None
    for line in text.splitlines():
        stripped = line.strip()
        match = re.match(r"Interface\s+(\S+)", stripped)
        if match:
            if name is not None:
                interfaces.append((name, iftype))
            name, iftype = match.group(1), None
            continue
        match = re.match(r"type\s+(\S+)", stripped)
        if match and name is not None:
            iftype = match.group(1)
    if name is not None:
        interfaces.append((name, iftype))
    return interfaces


def pick_interface(interfaces):
    """Choose the interface to control from parse_interfaces() output.

    Prefers a "managed" (station) interface; skips P2P-device and monitor
    interfaces, which don't support power saving.
    """
    for name, iftype in interfaces:
        if iftype == "managed":
            return name
    for name, iftype in interfaces:
        if iftype not in ("P2P-device", "monitor"):
            return name
    return None


def parse_power_save(text):
    """Parse `iw dev <if> get power_save` output into "on", "off" or None."""
    match = re.search(r"Power save:\s*(on|off)\b", text, re.IGNORECASE)
    return match.group(1).lower() if match else None


def hint_for(status):
    """Return the hint line shown for a status of "on" or "off"."""
    if status == "off":
        return "Better for stable gaming ping."
    if status == "on":
        return "Battery saving mode enabled."
    return "Unable to read status."


def explain_exit_code(returncode, stderr=""):
    """Turn a failed set-power-save exit code into a user-facing message."""
    if returncode == 126:
        return "Authentication was dismissed."
    if returncode == 127:
        return "Not authorized to change power saving."
    return (stderr or "").strip() or "Failed to change power saving."


# --------------------------------------------------------------------------
# System interaction
# --------------------------------------------------------------------------


def find_tool(name):
    """Resolve an executable via PATH (plus sbin dirs that users often lack)."""
    path = os.environ.get("PATH", os.defpath)
    extra = os.pathsep.join(["/usr/sbin", "/sbin"])
    found = shutil.which(name, path=path) or shutil.which(
        name, path=path + os.pathsep + extra
    )
    if not found:
        raise RuntimeError("Required program not found: %s" % name)
    return found


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(str(exc)) from exc


def get_interface():
    result = run([find_tool("iw"), "dev"])
    if result.returncode != 0:
        return None
    return pick_interface(parse_interfaces(result.stdout))


def get_status(interface):
    """Return "on", "off" or None."""
    result = run([find_tool("iw"), "dev", interface, "get", "power_save"])
    if result.returncode != 0:
        return None
    return parse_power_save(result.stdout)


def set_power_save(interface, enable):
    """Set power saving. Returns (ok, error_message)."""
    cmd = [find_tool("iw"), "dev", interface, "set", "power_save", "on" if enable else "off"]
    if os.geteuid() != 0:
        cmd = [find_tool("pkexec")] + cmd
    result = run(cmd)
    if result.returncode == 0:
        return True, None
    return False, explain_exit_code(result.returncode, result.stderr)


# --------------------------------------------------------------------------
# GUI
# --------------------------------------------------------------------------


class App:
    def __init__(self, root, forced_interface=None):
        self.root = root
        self.forced_interface = forced_interface
        self.interface = None
        self.busy = False

        root.title(APP_TITLE)
        root.resizable(False, False)

        frame = ttk.Frame(root, padding=20)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text=APP_TITLE, font=("Sans", 15, "bold")).grid(
            row=0, column=0, columnspan=3, pady=(0, 14)
        )

        self.interface_var = tk.StringVar(value="Wi-Fi adapter: detecting...")
        ttk.Label(frame, textvariable=self.interface_var).grid(
            row=1, column=0, columnspan=3, pady=2
        )

        self.status_var = tk.StringVar(value="Power Saving: unknown")
        ttk.Label(frame, textvariable=self.status_var, font=("Sans", 12, "bold")).grid(
            row=2, column=0, columnspan=3, pady=(2, 2)
        )

        self.hint_var = tk.StringVar(value="")
        ttk.Label(
            frame, textvariable=self.hint_var, foreground="#555555", wraplength=320
        ).grid(row=3, column=0, columnspan=3, pady=(0, 14))

        self.off_button = ttk.Button(
            frame, text="Turn Off", width=12, command=lambda: self.apply(False)
        )
        self.off_button.grid(row=4, column=0, padx=4)

        self.on_button = ttk.Button(
            frame, text="Turn On", width=12, command=lambda: self.apply(True)
        )
        self.on_button.grid(row=4, column=1, padx=4)

        self.refresh_button = ttk.Button(
            frame, text="Refresh Status", width=14, command=self.refresh
        )
        self.refresh_button.grid(row=4, column=2, padx=4)

        self.refresh()
        self.root.after(REFRESH_MS, self.auto_refresh)

    def detect_interface(self):
        return self.forced_interface or get_interface()

    def set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in (self.off_button, self.on_button, self.refresh_button):
            button.config(state=state)

    def refresh(self):
        if self.busy:
            return
        try:
            self.interface = self.detect_interface()
            status = get_status(self.interface) if self.interface else None
        except RuntimeError as exc:
            self.interface_var.set("Wi-Fi adapter: unavailable")
            self.status_var.set("Power Saving: unknown")
            self.hint_var.set(str(exc))
            return

        if not self.interface:
            self.interface_var.set("Wi-Fi adapter: Not found")
            self.status_var.set("Power Saving: unknown")
            self.hint_var.set("No Wi-Fi interface found.")
            return

        self.interface_var.set("Wi-Fi adapter: %s" % self.interface)
        if status is None:
            self.status_var.set("Power Saving: Unknown")
        else:
            self.status_var.set("Power Saving: %s" % status.upper())
        self.hint_var.set(hint_for(status))

    def auto_refresh(self):
        self.refresh()
        self.root.after(REFRESH_MS, self.auto_refresh)

    def apply(self, enable):
        if self.busy:
            return
        try:
            self.interface = self.detect_interface()
        except RuntimeError as exc:
            messagebox.showerror("Power saving", str(exc))
            return
        if not self.interface:
            messagebox.showerror("No Wi-Fi adapter", "No Wi-Fi interface found.")
            return

        self.set_busy(True)
        self.status_var.set("Power Saving: applying...")
        self.root.update_idletasks()
        try:
            ok, error = set_power_save(self.interface, enable)
        except RuntimeError as exc:
            ok, error = False, str(exc)
        finally:
            self.set_busy(False)

        if not ok:
            messagebox.showerror("Power saving", error)
        self.refresh()


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(
        prog="wifi-power-toggle",
        description="View or toggle Wi-Fi power saving. Opens the GUI when no action is given.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true", help="print the current power-saving state")
    group.add_argument("--on", action="store_true", help="enable power saving")
    group.add_argument("--off", action="store_true", help="disable power saving")
    parser.add_argument(
        "--interface", metavar="NAME", help="Wi-Fi interface to use (default: auto-detect)"
    )
    return parser


def run_cli(args):
    try:
        interface = args.interface or get_interface()
        if not interface:
            print("error: no Wi-Fi interface found", file=sys.stderr)
            return 1

        if args.on or args.off:
            ok, error = set_power_save(interface, args.on)
            if not ok:
                print("error: %s" % error, file=sys.stderr)
                return 1

        status = get_status(interface)
    except RuntimeError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1

    if status is None:
        print("error: unable to read power-saving status for %s" % interface, file=sys.stderr)
        return 1
    print("%s: power saving %s" % (interface, status))
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.status or args.on or args.off:
        return run_cli(args)

    if tk is None:
        print(
            "error: tkinter is not installed; install it or use --status/--on/--off",
            file=sys.stderr,
        )
        return 1
    root = tk.Tk()
    App(root, forced_interface=args.interface)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
