from __future__ import annotations

from pathlib import Path
import json
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.capacity import arrival_time_required_server_groups, local_installed_capacity_floor
from core.adoption import conditioning_from_config
from core.config import deep_merge, load_config, validate_config
from core.data import (
    load_industry_inputs,
    read_battery_cost_parameters,
    read_core_grid_energy_prices,
    read_industry_rooftop_parameters,
    reference_energy_mwh,
    scale_workload,
)
from core.representative_group import read_representative_groups, scenario_scale


class CoreConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(
            ROOT,
            Path("config/defaults.yaml"),
            Path("config/runs/single_industry_core.yaml"),
        )

    def test_deep_merge_preserves_nested_defaults(self) -> None:
        merged = deep_merge({"a": {"x": 1, "y": 2}}, {"a": {"x": 3}})
        self.assertEqual(merged, {"a": {"x": 3, "y": 2}})

    def test_default_config_is_valid(self) -> None:
        validate_config(self.config)
        self.assertEqual(self.config["selected_industries"], ["C36"])
        self.assertRegex(self.config["model_version"], r"^v\d+\.\d+\.\d+$")
        self.assertEqual(self.config["model_version"], "v1.0.0")
        self.assertEqual(
            self.config["model"]["grid_capacity_upgrade_boundary"],
            "no_ai_optimized_net_peak_zero_headroom_credit",
        )
        self.assertNotIn("existing_headroom_fraction", self.config["model"])
        self.assertFalse(self.config["model"]["server_groups_integer"])
        self.assertAlmostEqual(
            self.config["server"]["normal_dispatch_reserve_fraction"], 0.0
        )
        self.assertAlmostEqual(self.config["server"]["installed_reserve_fraction"], 0.15)
        self.assertEqual(self.config["server"]["n_plus_spare_server_groups"], 0)
        self.assertEqual(
            self.config["energy"]["grid_energy_price_mode"],
            "guangdong_spot_retail_representative_week",
        )
        self.assertEqual(
            self.config["energy"]["pv_capacity_mode"],
            "none",
        )
        self.assertFalse(self.config["energy"]["battery_investment_enabled"])
        self.assertEqual(
            self.config["demand"]["external_energy_alignment"]["per_industry_check"],
            "diagnostic",
        )
        self.assertAlmostEqual(self.config["server"]["maximum_wall_power_kw"], 1.5)
        self.assertEqual(
            self.config["enterprise_payment"]["cloud_product_boundary"],
            "dual_L20_GPU_IaaS_price_proxy_not_model_API_or_SaaS",
        )
        self.assertEqual(
            self.config["enterprise_payment"]["price_cases"],
            ["low", "base", "high"],
        )
        self.assertEqual(
            self.config["paths"]["enterprise_ai_cost_parameters"],
            "02_data/china_enterprise_ai_cost_parameters.csv",
        )
        self.assertEqual(
            self.config["demand"]["adopter_conditioning"]["mode"],
            "conditional_on_adopted_group",
        )

    def test_invalid_model_version_is_rejected(self) -> None:
        invalid = deep_merge(self.config, {"model_version": "latest"})
        with self.assertRaises(ValueError):
            validate_config(invalid)

    def test_invalid_server_power_is_rejected(self) -> None:
        invalid = deep_merge(
            self.config,
            {"server": {"maximum_wall_power_kw": 0.3}},
        )
        with self.assertRaises(ValueError):
            validate_config(invalid)

    def test_positive_existing_headroom_credit_is_rejected(self) -> None:
        invalid = deep_merge(
            self.config,
            {"model": {"existing_headroom_fraction": 0.0025}},
        )
        with self.assertRaises(ValueError):
            validate_config(invalid)

    def test_nonzero_headroom_boundary_is_rejected(self) -> None:
        invalid = deep_merge(
            self.config,
            {"model": {"grid_capacity_upgrade_boundary": "measured_existing_headroom"}},
        )
        with self.assertRaises(ValueError):
            validate_config(invalid)

    def test_one_day_horizon_is_allowed_for_horizon_sensitivity(self) -> None:
        daily = deep_merge(self.config, {"model": {"horizon_hours": 24}})
        validate_config(daily)

    def test_invalid_reserve_and_fixed_battery_are_rejected(self) -> None:
        for field in ("installed_reserve_fraction", "normal_dispatch_reserve_fraction"):
            invalid = deep_merge(self.config, {"server": {field: 1.0}})
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_config(invalid)
        invalid = deep_merge(self.config, {"energy": {"battery_fixed_power_mw": -1.0}})
        with self.assertRaises(ValueError):
            validate_config(invalid)

    def test_local_capacity_floor_separates_headroom_from_n_plus_one(self) -> None:
        self.assertAlmostEqual(local_installed_capacity_floor(4.0, 0.15, 0), 4.6)
        self.assertAlmostEqual(local_installed_capacity_floor(4.0, 0.15, 1), 5.0)
        self.assertAlmostEqual(local_installed_capacity_floor(4.2, 0.15, 1), 5.2)
        self.assertAlmostEqual(local_installed_capacity_floor(20.0, 0.15, 1), 23.0)

    def test_reference_energy_is_continuous_and_scale_homogeneous(self) -> None:
        profile = np.array([1.0, 2.0, 3.0, 2.0])
        calibration = {
            "accelerators_per_server": 2.0,
            "installed_utilization": 0.65,
            "maximum_power_kw": 1.25,
            "online_idle_power_kw": 0.36,
            "pue": 1.20,
        }
        energy, groups = reference_energy_mwh(profile, calibration, 0.15, 0)
        scaled_energy, scaled_groups = reference_energy_mwh(
            profile * 7.5, calibration, 0.15, 0
        )
        self.assertAlmostEqual(scaled_energy, energy * 7.5)
        self.assertAlmostEqual(scaled_groups, groups * 7.5)

    def test_arrival_time_capacity_is_calculated_without_optimization(self) -> None:
        required = arrival_time_required_server_groups(
            np.array([2.0, 1.0, 0.0]),
            [(1, 5.0), (1, 2.0), (2, 3.0)],
            reference_compute_h_per_service_unit=0.5,
            accelerators_per_server_group=2.0,
        )
        self.assertAlmostEqual(required, 2.0)

    def test_core_spot_retail_week_is_complete_and_nonflat(self) -> None:
        if not (ROOT / self.config["paths"]["spot_price_source"]).exists():
            self.skipTest("hourly spot-price file is not redistributable and is absent")
        prices = read_core_grid_energy_prices(self.config)
        self.assertEqual(prices.shape, (168,))
        self.assertTrue(np.isfinite(prices).all())
        self.assertGreater(float(np.ptp(prices)), 0.0)

    def test_spot_price_week_is_rotated_to_start_on_monday(self) -> None:
        import copy
        import tempfile

        start = pd.Timestamp("2026-05-28")  # Thursday
        rows = [
            {
                "business_date": (start + pd.Timedelta(days=day)).date().isoformat(),
                "business_hour": hour,
                "province_code": "GD",
                "settlement_type": "dayahead",
                "price_rmb_mwh": float(day),
            }
            for day in range(7)
            for hour in range(24)
            for _ in range(4)
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prices.csv"
            pd.DataFrame(rows).to_csv(path, index=False)
            config = copy.deepcopy(self.config)
            config["paths"]["spot_price_source"] = str(path)
            config["energy"]["grid_energy_price_mode"] = "guangdong_spot_retail_representative_week"
            config["energy"].pop("spot_period", None)
            config["energy"]["spot_representative_week"] = {
                "province_code": "GD",
                "settlement_type": "dayahead",
                "start_date": "2026-05-28",
                "end_date": "2026-06-03",
            }
            prices = read_core_grid_energy_prices(config)
        adder = prices[0] - 4.0  # Monday 2026-06-01 is day 4 of the period.
        daily = prices.reshape(7, 24)[:, 0] - adder
        np.testing.assert_allclose(daily, [4, 5, 6, 0, 1, 2, 3], atol=1e-9)

    def test_existing_pv_boundary_uses_positive_roof_limit(self) -> None:
        factory = self.config["factory"]
        rooftop = read_industry_rooftop_parameters(self.config, "C36")
        roof_limit_mw = (
            float(rooftop["roof_area_proxy_m2"])
            * float(factory["roof_usable_fraction"])
            * float(factory["pv_module_efficiency"])
            * float(factory["pv_realization_fraction"])
            / 1000.0
        )
        self.assertGreater(roof_limit_mw, 0.0)

    def test_rooftop_table_is_industry_specific_and_traceable(self) -> None:
        frame = pd.read_csv(
            ROOT / self.config["paths"]["model_ready_industry_rooftop"],
            encoding="utf-8-sig",
        )
        self.assertEqual(len(frame), 31)
        self.assertEqual(frame["industry_code"].nunique(), 31)
        self.assertGreater(frame["roof_area_proxy_m2"].nunique(), 10)
        c36 = frame.set_index("industry_code").loc["C36"]
        self.assertEqual(int(c36["us_naics_3"]), 336)
        self.assertAlmostEqual(float(c36["roof_area_proxy_m2"]), 17211.510568421054)
        self.assertEqual(c36["roof_area_case"], "us_mecs_2022_reference")

    def test_battery_costs_are_read_from_split_2025_source(self) -> None:
        battery = read_battery_cost_parameters(self.config)
        self.assertAlmostEqual(battery.energy_capex_rmb_per_kwh, 773.6795742)
        self.assertAlmostEqual(battery.power_capex_rmb_per_kw, 470.3124972)
        self.assertAlmostEqual(battery.energy_lifetime_years, 22.5)
        self.assertAlmostEqual(battery.power_lifetime_years, 10.0)
        self.assertAlmostEqual(battery.power_fom_fraction_per_year, 0.0025)
        self.assertAlmostEqual(battery.roundtrip_efficiency, 0.96)
        self.assertAlmostEqual(
            battery.annualized_cost_rmb_per_mw_year(2.0, 0.08),
            221677.215732856,
        )

class CoreScalingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(
            ROOT,
            Path("config/defaults.yaml"),
            Path("config/runs/single_industry_core.yaml"),
        )
        cls.groups = read_representative_groups(
            ROOT / cls.config["paths"]["representative_group_report"]
        )

    def test_representative_group_table_and_c36_values(self) -> None:
        self.assertEqual(len(self.groups), 31)
        c36 = self.groups["C36"]
        self.assertAlmostEqual(c36.share_base, 0.085)
        self.assertEqual(c36.factories_base, 9)

    def test_all_core_scenarios_reconstruct_one_industry_service(self) -> None:
        c36 = self.groups["C36"]
        conditioning = conditioning_from_config(ROOT, self.config, "C36")
        q = conditioning.adopter_activity_share
        expected = {
            "PF": (0.085 / q / 9.0, q * 9.0 / 0.085),
            "SHG": (0.085 / q, q / 0.085),
            "II_1host": (1.0, 1.0),
        }
        for scenario, (ai_scale, multiplier) in expected.items():
            scale = scenario_scale(
                c36, "base", scenario, adopter_activity_share=q
            )
            self.assertAlmostEqual(scale.ai_service_scale_per_host, ai_scale)
            self.assertAlmostEqual(scale.equivalent_host_multiplier, multiplier)
            self.assertAlmostEqual(scale.industry_service_reconstruction, 1.0)

    def test_c36_adopter_conditioning_matches_shared_figure_scenario(self) -> None:
        conditioning = conditioning_from_config(ROOT, self.config, "C36")
        self.assertAlmostEqual(
            conditioning.adopter_activity_share, 0.6183866117445506
        )
        group_scale = conditioning.group_service_scale(0.085)
        multiplier = conditioning.industry_equivalent_multiplier(0.085)
        self.assertAlmostEqual(group_scale, 0.085 / conditioning.adopter_activity_share)
        self.assertAlmostEqual(group_scale * multiplier, 1.0)

    def test_c36_input_service_and_flexibility_are_conserved(self) -> None:
        inputs = load_industry_inputs(self.config, "C36")
        reconstructed = float(np.sum(inputs.rigid_service_units)) + sum(
            job.amount_service_units for job in inputs.flexible_jobs
        )
        represented_days = self.config["model"]["horizon_hours"] / 24
        self.assertAlmostEqual(reconstructed / represented_days, inputs.daily_effective_service_units, places=4)
        conditioning = conditioning_from_config(ROOT, self.config, "C36")
        conditional_group_scale = 0.085 / conditioning.adopter_activity_share
        rigid, jobs = scale_workload(inputs, conditional_group_scale)
        group_service = float(np.sum(rigid)) + sum(job.amount_service_units for job in jobs)
        self.assertAlmostEqual(
            group_service / represented_days,
            inputs.daily_effective_service_units * conditional_group_scale,
            places=4,
        )

    def test_active_horizon_has_cross_day_jobs(self) -> None:
        inputs = load_industry_inputs(self.config, "C36")
        self.assertEqual(len(inputs.rigid_service_units), 168)
        self.assertEqual(len(inputs.base_load_mw), 168)
        self.assertEqual(len(inputs.pv_capacity_factor), 168)
        self.assertGreaterEqual(max(job.deadline_hours for job in inputs.flexible_jobs), 72)
        self.assertTrue(
            any(
                job.release_hour // 24
                != ((job.release_hour + job.deadline_hours) % 168) // 24
                for job in inputs.flexible_jobs
            )
        )

    def test_industry_energy_allocation_remains_diagnostic(self) -> None:
        inputs = load_industry_inputs(self.config, "C36")
        self.assertGreaterEqual(inputs.derived_reference_energy_twh, inputs.external_energy_low_twh)
        self.assertLessEqual(inputs.derived_reference_energy_twh, inputs.external_energy_high_twh)
        self.assertNotAlmostEqual(
            inputs.derived_reference_energy_twh,
            inputs.external_energy_central_twh,
            places=8,
        )

    def test_model_ready_service_has_complete_task_and_case_coverage(self) -> None:
        path = ROOT / self.config["paths"]["model_ready_task_service"]
        frame = pd.read_csv(path, encoding="utf-8-sig")
        self.assertEqual(len(frame), 31 * 6 * 3)
        self.assertEqual(set(frame["parameter_case"]), {"low", "base", "high"})
        for _, group in frame.groupby(["industry_code", "parameter_case"]):
            self.assertEqual(
                set(group["task_id"]),
                {"office", "agent", "vision", "maintenance", "scheduling", "simulation"},
            )

    def test_national_service_is_unscaled_and_derives_reference_energy(self) -> None:
        national_config = load_config(
            ROOT,
            Path("config/defaults.yaml"),
            Path("config/runs/all_industries_core.yaml"),
        )
        service_path = ROOT / national_config["paths"]["model_ready_task_service"]
        service = pd.read_csv(service_path, encoding="utf-8-sig")
        self.assertNotIn("national_energy_anchor", national_config["demand"])
        self.assertTrue((service["demand_scaling_factor"] == 1.0).all())
        self.assertEqual(
            set(service["demand_scaling_method"]),
            {"none_bottom_up_six_task_ledger"},
        )
        np.testing.assert_allclose(
            service["effective_service_units_day"],
            service["structural_service_weight"],
            rtol=0.0,
            atol=0.0,
        )

        derived_reference_energy: dict[str, float] = {}
        for case in ("low", "base", "high"):
            case_config = deep_merge(
                national_config,
                {"demand": {"effective_service": {"parameter_case": case}}},
            )
            derived_reference_energy[case] = sum(
                load_industry_inputs(
                    case_config, code, enforce_external_alignment=False
                ).derived_reference_energy_twh
                for code in national_config["selected_industries"]
            )
        self.assertGreater(derived_reference_energy["low"], 0.0)
        self.assertLess(
            derived_reference_energy["low"], derived_reference_energy["base"]
        )
        self.assertLess(
            derived_reference_energy["base"], derived_reference_energy["high"]
        )

    def test_active_service_parameters_match_validated_bottom_up_case(self) -> None:
        validated = json.loads(
            (ROOT / self.config["paths"]["model_ready_service_done"]).read_text(
                encoding="utf-8"
            )
        )
        service = self.config["demand"]["effective_service"]
        self.assertEqual(service["parameter_case"], validated["selected_parameter_case"])
        self.assertEqual(validated["per_industry_check"], "diagnostic")
        self.assertGreaterEqual(validated["industries_inside_warning_band"], 0)
        self.assertLessEqual(validated["industries_inside_warning_band"], 31)
        self.assertEqual(validated["demand_method"], "unscaled_bottom_up_six_task_ledger")
        self.assertEqual(validated["demand_scaling_factor"], 1.0)
        self.assertFalse(validated["external_values_used_as_model_inputs"])
        national_config = load_config(
            ROOT,
            Path("config/defaults.yaml"),
            Path("config/runs/all_industries_core.yaml"),
        )
        selected_inputs = [
            load_industry_inputs(
                national_config, code, enforce_external_alignment=False
            )
            for code in national_config["selected_industries"]
        ]
        self.assertAlmostEqual(
            validated["derived_reference_energy_twh"],
            sum(item.derived_reference_energy_twh for item in selected_inputs),
            places=8,
        )

    def test_common_it_efficiency_cases_follow_confirmed_contract(self) -> None:
        raw = pd.read_csv(
            ROOT / self.config["paths"]["raw_common_it_effective_efficiency_scenarios"],
            encoding="utf-8-sig",
        )
        processed = pd.read_csv(
            ROOT / self.config["paths"]["model_ready_common_it_effective_efficiency"],
            encoding="utf-8-sig",
        )
        expected = {
            "it_efficiency_1p5": 1.5,
            "it_efficiency_3p0": 3.0,
            "it_efficiency_5p0": 5.0,
        }
        self.assertEqual(set(processed["efficiency_case"]), set(expected))
        self.assertEqual(len(raw), 3)
        multipliers = processed.set_index("efficiency_case")["common_it_effective_efficiency_multiplier"]
        compute = processed.set_index("efficiency_case")["reference_compute_h_per_service_unit"]
        for case, multiplier in expected.items():
            self.assertAlmostEqual(multipliers[case], multiplier)
            self.assertAlmostEqual(compute[case], 1.0 / multiplier)
        self.assertTrue(bool(processed.set_index("efficiency_case").loc["it_efficiency_3p0", "is_main_scenario"]))
        self.assertAlmostEqual(
            self.config["demand"]["effective_service"]["reference_compute_h_per_service_unit"],
            compute["it_efficiency_3p0"],
        )

    def test_diagnostic_industry_alignment_does_not_block_active_case(self) -> None:
        inputs = load_industry_inputs(self.config, "C16")
        alignment = self.config["demand"]["external_energy_alignment"]
        self.assertGreater(inputs.external_energy_alignment_ratio, alignment["warning_ratio_high"])

    def test_simple_model_state_bundle_is_feasible_and_bounded(self) -> None:
        state = self.config["model_state"]
        self.assertTrue(state["enabled"])
        self.assertEqual(state["model_name"], "Qwen2.5-32B-Instruct")
        self.assertEqual(state["precision"], "INT4/AWQ")
        self.assertEqual(state["required_model_replicas"], 1)
        self.assertGreaterEqual(state["minimum_server_groups_for_model_state"], 1)
        self.assertLessEqual(
            state["model_storage_required_gb_per_deployment"],
            state["bundled_storage_gb_per_server_group"]
            * state["minimum_server_groups_for_model_state"],
        )
        self.assertIn("per_request_kv_cache_scheduling", state["excluded_details"])


if __name__ == "__main__":
    unittest.main()
