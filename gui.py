"""
gui.py

Laserline Research Controller GUI

Requires:
    laser.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from laser import Laser


POLL_TIME_MS = 250


class LaserGUI:

    def __init__(self):

        self.laser = Laser()

        self.root = tk.Tk()

        self.root.title("Laserline Research Controller")

        self.root.geometry("850x650")

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

        #
        # -----------------------------------------------------
        # DIGITAL OUTPUTS
        # -----------------------------------------------------
        #

        outputs = ttk.LabelFrame(
            self.root,
            text="Digital Outputs",
        )

        outputs.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        self.do_vars = {

            "Threshold": tk.BooleanVar(),

            "Shutter": tk.BooleanVar(),

            "Laser": tk.BooleanVar(),

            "Pilot": tk.BooleanVar(),

        }

        ttk.Checkbutton(
            outputs,
            text="Threshold",
            variable=self.do_vars["Threshold"],
            command=self.update_outputs,
        ).grid(row=0, column=0, sticky="w", padx=10)

        ttk.Checkbutton(
            outputs,
            text="Shutter",
            variable=self.do_vars["Shutter"],
            command=self.update_outputs,
        ).grid(row=0, column=1, sticky="w", padx=10)

        ttk.Checkbutton(
            outputs,
            text="Laser ON",
            variable=self.do_vars["Laser"],
            command=self.update_outputs,
        ).grid(row=0, column=2, sticky="w", padx=10)

        ttk.Checkbutton(
            outputs,
            text="Pilot",
            variable=self.do_vars["Pilot"],
            command=self.update_outputs,
        ).grid(row=0, column=3, sticky="w", padx=10)

        ttk.Button(
            outputs,
            text="Reset",
            command=self.reset,
        ).grid(
            row=1,
            column=0,
            pady=10,
            padx=10,
        )

        ttk.Button(
            outputs,
            text="EMERGENCY OFF",
            command=self.emergency_off,
        ).grid(
            row=1,
            column=1,
            columnspan=2,
            sticky="ew",
            padx=10,
        )

        #
        # -----------------------------------------------------
        # DIGITAL INPUTS
        # -----------------------------------------------------
        #

        inputs = ttk.LabelFrame(
            self.root,
            text="Digital Inputs",
        )

        inputs.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        self.input_labels = {}

        names = [
            "K:Sleep",
            "Laser ON",
            "K:Warn",
            "Threshold",
            "Fiber Break",
            "Shutter Open",
            "Error",
            "Warn LED",
            "Shutter Closed",
        ]

        for row, name in enumerate(names):

            ttk.Label(
                inputs,
                text=name,
                width=20,
            ).grid(
                row=row,
                column=0,
                sticky="w",
                padx=10,
            )

            lbl = tk.Label(
                inputs,
                width=3,
                bg="red",
            )

            lbl.grid(
                row=row,
                column=1,
                padx=5,
                pady=2,
            )

            self.input_labels[name] = lbl

        #
        # -----------------------------------------------------
        # ANALOG OUTPUT
        # -----------------------------------------------------
        #

        analog = ttk.LabelFrame(
            self.root,
            text="Analog Output",
        )

        analog.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        ttk.Label(
            analog,
            text="Voltage (0-10 V)",
        ).grid(
            row=0,
            column=0,
            padx=10,
            pady=10,
        )

        self.voltage = tk.DoubleVar(value=0.0)

        ttk.Entry(
            analog,
            width=10,
            textvariable=self.voltage,
        ).grid(
            row=0,
            column=1,
        )

        ttk.Button(
            analog,
            text="Set Voltage",
            command=self.set_voltage,
        ).grid(
            row=0,
            column=2,
            padx=10,
        )

        #
        # -----------------------------------------------------
        #

        self.status = ttk.Label(
            self.root,
            text="Connected",
        )

        self.status.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        self.poll_inputs()

    # =======================================================
    # OUTPUTS
    # =======================================================

    def update_outputs(self):

        self.laser.all_off()

        if self.do_vars["Threshold"].get():
            self.laser.threshold(True)

        if self.do_vars["Shutter"].get():
            self.laser.shutter(True)

        if self.do_vars["Laser"].get():
            self.laser.laser(True)

        if self.do_vars["Pilot"].get():
            self.laser.pilot(True)

        self.status.config(
            text=f"Outputs = 0x{self.laser.outputs:02X}"
        )

    # =======================================================

    def set_voltage(self):

        try:

            value = float(
                self.voltage.get()
            )

            self.laser.set_voltage(value)

            self.status.config(
                text=f"AO = {value:.2f} V"
            )

        except Exception as exc:

            messagebox.showerror(
                "Error",
                str(exc),
            )

    # =======================================================

    def reset(self):

        self.laser.reset()

    # =======================================================

    def emergency_off(self):

        self.laser.shutdown()

        for var in self.do_vars.values():

            var.set(False)

        self.status.config(
            text="Emergency OFF"
        )

    # =======================================================
    # INPUT POLLING
    # =======================================================

    def poll_inputs(self):

        try:

            inputs = self.laser.read_inputs()

            for name, state in inputs.items():

                if name not in self.input_labels:
                    continue

                self.input_labels[name].config(
                    bg="lime" if state else "red"
                )

        except Exception as exc:

            self.status.config(
                text=str(exc)
            )

        self.root.after(
            POLL_TIME_MS,
            self.poll_inputs,
        )

    # =======================================================

    def on_close(self):

        try:

            self.laser.shutdown()

        except Exception:
            pass

        self.root.destroy()

    # =======================================================

    def run(self):

        self.root.mainloop()