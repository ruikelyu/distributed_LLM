from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.config import load_config


class HybridCloudConfigTests(unittest.TestCase):
    def test_default_core_keeps_hybrid_cloud_disabled(self) -> None:
        config = load_config(
            ROOT,
            Path("config/defaults.yaml"),
            Path("config/runs/all_industries_core.yaml"),
        )
        self.assertFalse(config["hybrid_cloud"]["enabled"])
        self.assertIsNone(config["energy"]["grid_expansion_limit_mw"])
        self.assertEqual(
            config["energy"]["grid_expansion_objective_penalty_rmb_per_mw_year"],
            0.0,
        )

    def test_zero_grid_hybrid_case_has_explicit_structural_controls(self) -> None:
        override = {
            "energy": {
                "battery_investment_enabled": False,
                "grid_expansion_limit_mw": 0.0,
            },
            "hybrid_cloud": {
                "enabled": True,
                "maximum_cloud_service_share": 1.0,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.yaml"
            path.write_text(yaml.safe_dump(override), encoding="utf-8")
            config = load_config(ROOT, Path("config/defaults.yaml"), path)
        self.assertTrue(config["hybrid_cloud"]["enabled"])
        self.assertEqual(config["energy"]["grid_expansion_limit_mw"], 0.0)
        self.assertFalse(config["energy"]["battery_investment_enabled"])
        self.assertEqual(config["hybrid_cloud"]["maximum_cloud_service_share"], 1.0)


if __name__ == "__main__":
    unittest.main()
