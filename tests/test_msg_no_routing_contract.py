#!/usr/bin/env python3
"""Contract tests for the internal MSG-no-routing paired mechanism control."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from run_group_architecture_core import (  # noqa: E402
    COORDINATION_EFFECT_METRICS,
    build_coordination_effect_row,
    normalized_fixed_site_shares,
)


class MsgNoRoutingContractTests(unittest.TestCase):
    def test_registered_representative_counts_define_ex_ante_shares(self) -> None:
        shares = normalized_fixed_site_shares([2 / 9, 2 / 9, 2 / 9, 2 / 9, 1 / 9], 5)
        np.testing.assert_allclose(shares, np.array([2, 2, 2, 2, 1]) / 9.0)

    def test_invalid_fixed_shares_are_rejected(self) -> None:
        for shares, site_count in [([0.5, 0.5], 3), ([0.6, 0.5], 2), ([1.1, -0.1], 2)]:
            with self.subTest(shares=shares):
                with self.assertRaises(ValueError):
                    normalized_fixed_site_shares(shares, site_count)

    def test_effect_direction_is_no_routing_minus_coordinated(self) -> None:
        no_routing = {metric: float(index + 2) for index, metric in enumerate(COORDINATION_EFFECT_METRICS)}
        coordinated = {metric: float(index + 1) for index, metric in enumerate(COORDINATION_EFFECT_METRICS)}
        coordinated.update(
            {
                "model_version": "v1.0.0",
                "common_it_effective_efficiency_case": "it_efficiency_3p0",
                "common_it_effective_efficiency_multiplier": 3.0,
                "planning_reserve_fraction": 0.15,
                "n_plus_spare_server_groups": 0,
                "reference_server_group": "dual_accelerator_reference_server_group",
            }
        )
        row = build_coordination_effect_row("C36", no_routing, coordinated)
        self.assertEqual(row["effect_definition"], "MSG_no_routing_minus_MSG_coordinated")
        self.assertEqual(row["control_code"], "MSG_NO_ROUTING")
        self.assertEqual(row["treatment_code"], "MSG")
        for metric in COORDINATION_EFFECT_METRICS:
            self.assertEqual(row[f"coordination_effect_{metric}"], 1.0)

    def test_registry_keeps_control_outside_formal_architecture_set(self) -> None:
        registry = yaml.safe_load(
            (ROOT / "config/scenarios/group_multisite_core_v1.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(registry["architectures"], ["PF", "SHG", "MSG"])
        control = registry["mechanism_controls"]["MSG_no_routing"]
        self.assertTrue(control["enabled"])
        self.assertFalse(control["formal_architecture"])
        self.assertEqual(control["paired_treatment"], "MSG")
        self.assertEqual(control["fixed_share_source"], "registered_represented_factory_counts")


if __name__ == "__main__":
    unittest.main()
