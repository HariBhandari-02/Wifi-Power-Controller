# SPDX-License-Identifier: MIT
"""Pure-function tests: no root, no GUI, no Wi-Fi hardware required."""

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "wifi-power-toggle.py"
_spec = importlib.util.spec_from_file_location("wifi_power_toggle", SCRIPT)
wpt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wpt)

IW_DEV_SIMPLE = """\
phy#0
\tInterface wlp2s0
\t\tifindex 3
\t\twdev 0x1
\t\taddr aa:bb:cc:dd:ee:ff
\t\ttype managed
\t\tchannel 36 (5180 MHz), width: 80 MHz, center1: 5210 MHz
\t\ttxpower 22.00 dBm
"""

IW_DEV_P2P_FIRST = """\
phy#1
\tInterface p2p-dev-wlan0
\t\tifindex 5
\t\ttype P2P-device
phy#0
\tInterface wlan0
\t\tifindex 4
\t\ttype managed
"""


class ParseInterfacesTests(unittest.TestCase):
    def test_single_interface(self):
        self.assertEqual(wpt.parse_interfaces(IW_DEV_SIMPLE), [("wlp2s0", "managed")])

    def test_multiple_interfaces(self):
        self.assertEqual(
            wpt.parse_interfaces(IW_DEV_P2P_FIRST),
            [("p2p-dev-wlan0", "P2P-device"), ("wlan0", "managed")],
        )

    def test_empty(self):
        self.assertEqual(wpt.parse_interfaces(""), [])

    def test_missing_type(self):
        self.assertEqual(wpt.parse_interfaces("phy#0\n\tInterface wlan9\n"), [("wlan9", None)])


class PickInterfaceTests(unittest.TestCase):
    def test_prefers_managed_over_p2p(self):
        self.assertEqual(wpt.pick_interface(wpt.parse_interfaces(IW_DEV_P2P_FIRST)), "wlan0")

    def test_skips_p2p_and_monitor(self):
        self.assertIsNone(wpt.pick_interface([("p2p0", "P2P-device"), ("mon0", "monitor")]))

    def test_falls_back_to_untyped(self):
        self.assertEqual(wpt.pick_interface([("wlan9", None)]), "wlan9")

    def test_none_found(self):
        self.assertIsNone(wpt.pick_interface([]))


class ParsePowerSaveTests(unittest.TestCase):
    def test_on(self):
        self.assertEqual(wpt.parse_power_save("Power save: on\n"), "on")

    def test_off(self):
        self.assertEqual(wpt.parse_power_save("Power save: off\n"), "off")

    def test_extra_whitespace_and_case(self):
        self.assertEqual(wpt.parse_power_save("Power save:   OFF"), "off")

    def test_unrecognised(self):
        self.assertIsNone(wpt.parse_power_save("command failed: Operation not supported (-95)"))
        self.assertIsNone(wpt.parse_power_save(""))


class MessageTests(unittest.TestCase):
    def test_hints(self):
        self.assertIn("gaming", wpt.hint_for("off"))
        self.assertIn("Battery", wpt.hint_for("on"))
        self.assertEqual(wpt.hint_for(None), "Unable to read status.")

    def test_exit_codes(self):
        self.assertIn("dismissed", wpt.explain_exit_code(126))
        self.assertIn("Not authorized", wpt.explain_exit_code(127))
        self.assertEqual(wpt.explain_exit_code(1, " boom \n"), "boom")
        self.assertEqual(wpt.explain_exit_code(1, ""), "Failed to change power saving.")


class CliParserTests(unittest.TestCase):
    def test_flags(self):
        args = wpt.build_parser().parse_args(["--off", "--interface", "wlan0"])
        self.assertTrue(args.off)
        self.assertFalse(args.on)
        self.assertEqual(args.interface, "wlan0")

    def test_actions_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit):
            wpt.build_parser().parse_args(["--on", "--off"])


if __name__ == "__main__":
    unittest.main()
