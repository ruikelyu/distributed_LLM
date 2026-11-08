"""The stylized mechanism demo solves with HiGHS and shows the expected ordering."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demo"))

import mechanism_demo as demo  # noqa: E402


class MechanismDemoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table, cls.results = demo.run_all()

    def test_each_mechanism_reduces_capacity(self):
        new_fixed, new_shift, host_fixed, host_shift, multi_fixed, multi_routed = (
            self.table["additional_capacity_mw"].to_numpy())
        self.assertLess(host_fixed, new_fixed)        # co-location, no shifting
        self.assertLess(host_shift, new_shift)        # co-location, with shifting
        self.assertLess(new_shift, new_fixed)         # shifting at a new data center
        self.assertLess(host_shift, host_fixed)       # shifting at the host
        self.assertLess(multi_fixed, host_shift)      # several sites
        self.assertLess(multi_routed, 0.1 * multi_fixed)  # routing

    def test_all_demand_is_served(self):
        total = demo.FIRM_DEMAND.sum() + demo.FLEX_JOBS["energy_mwh"].sum()
        for result in self.results:
            self.assertAlmostEqual(result["served_mwh"], total, places=4)

    def test_battery_power_equals_additional_capacity(self):
        battery = demo.battery(self.results[3])
        self.assertAlmostEqual(battery["power_mw"], self.results[3]["additional_capacity_mw"], places=4)
        self.assertGreater(battery["energy_mwh"], battery["power_mw"])


if __name__ == "__main__":
    unittest.main()
