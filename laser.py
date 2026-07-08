"""
laser.py

Laserline LDM interface through the VIPA IM053 web interface.
"""

from __future__ import annotations

import re
from typing import Dict, List

import requests


class Laser:

    THRESHOLD = 0x01
    SHUTTER = 0x04
    LASER = 0x10
    PILOT = 0x40
    RESET = 0x80

    MODULE1_LABELS = [
        "K:Sleep",
        "Laser ON",
        "K:Warn",
        "Threshold",
        "Fiber Break",
        "Shutter Open",
        "Error",
        "Warn LED",
    ]

    MODULE2_LABELS = [
        "Shutter Closed",
        "Input 1",
        "Input 2",
        "Input 3",
        "Input 4",
        "Input 5",
        "Input 6",
        "Input 7",
    ]

    def __init__(self, ip="192.168.1.13"):

        self.ip = ip

        self.timeout = 2

        self._outputs = 0

        self.session = requests.Session()

        self._do_url = (
            f"http://{ip}/cgi/saveout.cgi?module=3"
        )

        self._ao_url = (
            f"http://{ip}/cgi/saveout.cgi?module=5"
        )

        self._module1_url = (
            f"http://{ip}/moduledata.html?module=1"
        )

        self._module2_url = (
            f"http://{ip}/moduledata.html?module=2"
        )

        self._module4_url = (
            f"http://{ip}/moduledata.html?module=4"
        )

        self._do_module = "0106afc8"
        self._ao_module = "050125d8"

    # =========================================================

    def _post_do(self):

        self.session.post(
            self._do_url,
            data={
                "module": self._do_module,
                "Data0": f"{self._outputs:02X}",
            },
            timeout=self.timeout,
        ).raise_for_status()

    # =========================================================

    def _post_ao(self, ch0, ch1=0):

        self.session.post(
            self._ao_url,
            data={
                "module": self._ao_module,
                "Data0": f"{ch0:04X}",
                "Data1": f"{ch1:04X}",
            },
            timeout=self.timeout,
        ).raise_for_status()

    # =========================================================
    # Digital Outputs
    # =========================================================

    @property
    def outputs(self):
        return self._outputs

    def write_outputs(self, value):

        self._outputs = value & 0xFF

        self._post_do()

    def all_off(self):

        self.write_outputs(0)

    def _set_bit(self, mask, state):

        if state:
            self._outputs |= mask
        else:
            self._outputs &= ~mask

        self._post_do()

    def threshold(self, state):
        self._set_bit(self.THRESHOLD, state)

    def shutter(self, state):
        self._set_bit(self.SHUTTER, state)

    def laser(self, state):
        self._set_bit(self.LASER, state)

    def pilot(self, state):
        self._set_bit(self.PILOT, state)

    def reset(self):

        self._outputs |= self.RESET
        self._post_do()

        self._outputs &= ~self.RESET
        self._post_do()

    # =========================================================
    # Analog Output
    # =========================================================

    def set_voltage(self, volts):

        volts = max(0.0, min(10.0, volts))

        #
        # Measured calibration
        #
        # 0x0036 = 5 V
        # 0x006C = 10 V
        #

        counts = round(volts * 10.8)

        self._post_ao(counts)

    # =========================================================
    # Digital Inputs
    # =========================================================

    @staticmethod
    def _parse_di_byte(html):

        values = re.findall(
            r"<td[^>]*>\s*([0-9A-Fa-f]{2})\s*</td>",
            html,
        )

        return int(values[-1], 16)

    def _read_module(self, url, labels):

        r = self.session.get(
            url,
            timeout=self.timeout,
        )

        r.raise_for_status()

        value = self._parse_di_byte(r.text)

        result = {}

        for bit, label in enumerate(labels):

            result[label] = bool(value & (1 << bit))

        return result

    def read_inputs(self):

        data = {}

        data.update(
            self._read_module(
                self._module1_url,
                self.MODULE1_LABELS,
            )
        )

        data.update(
            self._read_module(
                self._module2_url,
                self.MODULE2_LABELS,
            )
        )

        return data

    # =========================================================
    # Analog Inputs
    # =========================================================

    def read_analog_inputs(self) -> List[int]:

        r = self.session.get(
            self._module4_url,
            timeout=self.timeout,
        )

        r.raise_for_status()

        values = re.findall(
            r">\s*([0-9A-Fa-f]{4})\s*<",
            r.text,
        )

        values = values[-4:]

        return [
            int(v, 16)
            for v in values
        ]

    # ---------------------------------------------------------

    def read_temperature_c(self) -> float:

        raw = self.read_analog_inputs()[2]

        #
        # Measured calibration
        #
        # 20.2 °C -> 8264
        #

        return raw / 409.6

    # =========================================================

    def shutdown(self):

        self.set_voltage(0.0)

        self.all_off()