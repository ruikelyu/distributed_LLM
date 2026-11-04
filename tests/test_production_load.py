from pathlib import Path
import sys
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.production_load import (  # noqa: E402
    _power_weights,
    resolve_site_load_profile,
    resolve_site_mean_load_mw,
)


class ProductionLoadBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "production_load": {
                "registry_path": "02_data/manufacturing_production_load_calibration.csv",
                "default_mode": "legacy_industry_electricity_share",
                "mode_by_industry": {"C36": "calibrated_registry"},
            }
        }

    def test_c36_calibrated_mean_and_separate_identifiers(self) -> None:
        mean, meta = resolve_site_mean_load_mw(
            root=ROOT,
            config=self.config,
            industry="C36",
            industry_mean_load_mw=260.829,
            ai_service_group_share=0.085,
            legacy_load_site_count=7,
        )
        self.assertAlmostEqual(mean, 43.6597, places=3)
        self.assertEqual(meta["load_site_count"], 9)
        self.assertEqual(meta["load_site_power_weight_source"], "equal_site_power_proxy")
        self.assertAlmostEqual(sum(meta["load_site_power_weights"]), 1.0)
        self.assertNotIn("ai_factory_count", meta)
        self.assertAlmostEqual(meta["production_activity_share"], 0.085)
        self.assertAlmostEqual(meta["ai_service_group_share"], 0.085)
        self.assertEqual(meta["formal_national_pool_eligible"], True)

    def test_calibrated_profile_uses_shape_not_industry_magnitude(self) -> None:
        profile, meta = resolve_site_load_profile(
            root=ROOT,
            config=self.config,
            industry="C36",
            industry_profile_mw=np.array([100.0, 300.0]),
            ai_service_group_share=0.085,
            legacy_load_site_count=7,
        )
        self.assertAlmostEqual(float(profile.mean()), meta["representative_site_mean_load_mw"])
        self.assertAlmostEqual(float(profile[1] / profile[0]), 3.0)

    def test_uncalibrated_industry_is_explicit_legacy_only(self) -> None:
        mean, meta = resolve_site_mean_load_mw(
            root=ROOT,
            config=self.config,
            industry="C35",
            industry_mean_load_mw=100.0,
            ai_service_group_share=0.10,
            legacy_load_site_count=5,
        )
        self.assertAlmostEqual(mean, 2.0)
        self.assertEqual(meta["mode"], "legacy_industry_electricity_share")
        self.assertEqual(meta["formal_national_pool_eligible"], False)

    def test_explicit_site_power_weights_are_normalized(self) -> None:
        weights, source = _power_weights("1;2;3", 3, "C99")
        self.assertEqual(source, "calibrated_site_power_weights")
        self.assertEqual(weights, [1 / 6, 2 / 6, 3 / 6])


if __name__ == "__main__":
    unittest.main()
