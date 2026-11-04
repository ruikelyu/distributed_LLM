from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_us_industry_heterogeneous_hardware",
    ROOT / "08_code" / "analyze_us_industry_heterogeneous_hardware.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class UsIndustryHeterogeneousCapacityTests(unittest.TestCase):
    def test_flat_profile_uses_china_average_demand_planning_floor(self) -> None:
        installed, online = MODULE.china_aligned_continuous_capacity(
            np.full(24, 8.0),
            service_capacity_per_server_group_h_per_h=2.0,
            planning_headroom_fraction=0.15,
            n_plus_spare_server_groups=0,
            normal_dispatch_reserve_fraction=0.0,
        )
        self.assertAlmostEqual(installed, 4.6)
        np.testing.assert_allclose(online, 4.0)

    def test_peaked_profile_uses_hourly_throughput_floor_without_utilization_derating(self) -> None:
        compute = np.zeros(24)
        compute[12] = 8.0
        installed, online = MODULE.china_aligned_continuous_capacity(
            compute,
            service_capacity_per_server_group_h_per_h=2.0,
            planning_headroom_fraction=0.15,
            n_plus_spare_server_groups=0,
            normal_dispatch_reserve_fraction=0.0,
        )
        self.assertAlmostEqual(installed, 4.0)
        self.assertAlmostEqual(online[12], 4.0)

    def test_n_plus_spare_and_dispatch_reserve_match_core_constraints(self) -> None:
        installed, _ = MODULE.china_aligned_continuous_capacity(
            np.full(24, 8.0),
            service_capacity_per_server_group_h_per_h=2.0,
            planning_headroom_fraction=0.15,
            n_plus_spare_server_groups=1,
            normal_dispatch_reserve_fraction=0.10,
        )
        self.assertAlmostEqual(installed, 5.0)

    def test_managed_delivery_is_removed_before_cloud_capacity(self) -> None:
        frame = pd.DataFrame(
            [
                {"task_id": "office", "effective_service_units_day": 24.0},
                {"task_id": "scheduling", "effective_service_units_day": 24.0},
            ]
        )
        shapes = {"office": np.full(24, 1 / 24), "scheduling": np.full(24, 1 / 24)}
        routing = {"scheduling": 0.8}
        delivery = {
            "office": {"managed_model_share": 1.0},
            "scheduling": {"managed_model_share": 0.35},
        }
        gpu, cpu, products = MODULE.task_profiles(
            frame,
            shapes,
            routing,
            {"scheduling": 1.0},
            reference_compute_h_per_service=1.0,
            delivery=delivery,
            product_by_task={"office": "ecs", "scheduling": "ecs"},
        )
        np.testing.assert_allclose(gpu, np.full(24, 0.13))
        np.testing.assert_allclose(cpu, np.full(24, 0.52))
        np.testing.assert_allclose(products["ecs"], cpu)

    def test_office_agent_managed_api_tokens_are_not_capacity_tokens(self) -> None:
        demand = pd.DataFrame(
            [
                {"parameter_case": "base", "task_id": "office", "effective_service_units_day": 10.0},
                {"parameter_case": "base", "task_id": "agent", "effective_service_units_day": 20.0},
                {"parameter_case": "base", "task_id": "vision", "effective_service_units_day": 4.0},
            ]
        )
        tokens = pd.DataFrame(
            [
                {"parameter_case": "base", "task_id": "office", "annual_input_tokens": 100.0, "annual_output_tokens": 50.0},
                {"parameter_case": "base", "task_id": "agent", "annual_input_tokens": 200.0, "annual_output_tokens": 80.0},
            ]
        )
        delivery = {
            "office": {"managed_model_share": 1.0},
            "agent": {"managed_model_share": 1.0},
            "vision": {
                "managed_model_share": 0.75,
                "calls_per_managed_service_unit": 0.5,
                "input_tokens_per_call": 1000,
                "output_tokens_per_call": 200,
            },
            "maintenance": {"managed_model_share": 0.5, "calls_per_managed_service_unit": 0, "input_tokens_per_call": 0, "output_tokens_per_call": 0},
            "scheduling": {"managed_model_share": 0.35, "calls_per_managed_service_unit": 0, "input_tokens_per_call": 0, "output_tokens_per_call": 0},
            "simulation": {"managed_model_share": 0.25, "calls_per_managed_service_unit": 0, "input_tokens_per_call": 0, "output_tokens_per_call": 0},
        }
        annual_input, annual_output = MODULE.managed_api_tokens(
            demand, tokens, "base", delivery
        )
        self.assertEqual(annual_input, 300.0 + 4.0 * 0.75 * 0.5 * 1000 * 365)
        self.assertEqual(annual_output, 130.0 + 4.0 * 0.75 * 0.5 * 200 * 365)


if __name__ == "__main__":
    unittest.main()
