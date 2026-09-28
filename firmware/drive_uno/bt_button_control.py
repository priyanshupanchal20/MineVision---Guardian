#!/usr/bin/env python3
"""
MineTruck — on-screen button drive for HC-05 + Arduino Uno.

Sends the same single-letter commands as a phone terminal:
  F B L R S   and speed digits 1–5

Usage (Windows, after pairing HC-05):
  pip install pyserial
  python bt_button_control.py

Pick the HC-05 *Outgoing* Bluetooth COM port if two appear.
Hold a direction button to move; release to stop (S).
ESP32 must be SAFE or WARNING — DANGER locks motors.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    raise SystemExit("Install pyserial first:  pip install pyserial")

BAUD = 9600


def bluetooth_ports():
    ports = []
    for p in list_ports.comports():
        name = f"{p.device} — {p.description}"
        ports.append((p.device, name))
    return ports


class DrivePad(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("MineTruck — HC-05 Button Drive")
        self.resizable(False, False)
        self.ser: serial.Serial | None = None
        self.speed = tk.IntVar(value=3)

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="HC-05 COM port").grid(row=0, column=0, columnspan=3, sticky="w")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(frm, textvariable=self.port_var, width=48, state="readonly")
        self.port_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Button(frm, text="Refresh", command=self.refresh_ports).grid(row=1, column=2, padx=(6, 0))

        self.status = tk.StringVar(value="Not connected")
        ttk.Label(frm, textvariable=self.status).grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 8))

        btns = ttk.Frame(frm)
        btns.grid(row=3, column=0, columnspan=3, pady=4)
        self._dir_btn(btns, "↑  Forward", "F", 0, 1)
        self._dir_btn(btns, "←  Left", "L", 1, 0)
        self._dir_btn(btns, "Stop", "S", 1, 1, hold=False)
        self._dir_btn(btns, "→  Right", "R", 1, 2)
        self._dir_btn(btns, "↓  Back", "B", 2, 1)

        spd = ttk.Frame(frm)
        spd.grid(row=4, column=0, columnspan=3, pady=(10, 4), sticky="w")
        ttk.Label(spd, text="Speed").pack(side="left")
        for n in range(1, 6):
            ttk.Radiobutton(
                spd, text=str(n), value=n, variable=self.speed, command=self.send_speed
            ).pack(side="left", padx=4)

        row = ttk.Frame(frm)
        row.grid(row=5, column=0, columnspan=3, pady=(10, 0), sticky="ew")
        ttk.Button(row, text="Connect", command=self.connect).pack(side="left")
        ttk.Button(row, text="Disconnect", command=self.disconnect).pack(side="left", padx=6)

        ttk.Label(
            frm,
            text="Hold arrows to drive · release = Stop\nMotors move only when ESP32 is SAFE or WARNING",
            justify="left",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_ports()

    def _dir_btn(self, parent, label, cmd, r, c, hold=True):
        b = ttk.Button(parent, text=label, width=12)
        b.grid(row=r, column=c, padx=4, pady=4)
        if hold:
            b.bind("<ButtonPress-1>", lambda e, ch=cmd: self.send(ch))
            b.bind("<ButtonRelease-1>", lambda e: self.send("S"))
        else:
            b.configure(command=lambda ch=cmd: self.send(ch))

    def refresh_ports(self) -> None:
        ports = bluetooth_ports()
        labels = [name for _, name in ports]
        self._port_map = {name: dev for dev, name in ports}
        self.port_box["values"] = labels
        if labels and not self.port_var.get():
            # Prefer "Bluetooth" outgoing-style ports
            pick = next((n for n in labels if "Bluetooth" in n), labels[0])
            self.port_var.set(pick)

    def connect(self) -> None:
        self.disconnect()
        label = self.port_var.get().strip()
        if not label or label not in self._port_map:
            messagebox.showerror("Port", "Select an HC-05 COM port first.")
            return
        dev = self._port_map[label]
        try:
            self.ser = serial.Serial(dev, BAUD, timeout=0.2)
        except Exception as exc:
            messagebox.showerror("Connect failed", str(exc))
            self.status.set(f"Failed: {exc}")
            return
        self.status.set(f"Connected {dev} @ {BAUD}")
        self.send_speed()

    def disconnect(self) -> None:
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(b"S")
            except Exception:
                pass
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.status.set("Not connected")

    def send(self, ch: str) -> None:
        if not self.ser or not self.ser.is_open:
            self.status.set("Connect HC-05 first")
            return
        try:
            self.ser.write(ch.encode("ascii"))
            self.status.set(f"Sent {ch}")
        except Exception as exc:
            self.status.set(f"Send error: {exc}")

    def send_speed(self) -> None:
        self.send(str(self.speed.get()))

    def on_close(self) -> None:
        self.disconnect()
        self.destroy()


if __name__ == "__main__":
    DrivePad().mainloop()
