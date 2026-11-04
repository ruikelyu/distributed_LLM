from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from run_national_cloud_center import apply_ldc_model_state_boundary


class RQ3LDCBoundaryTests(unittest.TestCase):
    def test_ldc_registry_disables_inherited_lifecycle_floor(self) -> None:
        source = {"model_state": {"enabled": True, "parameter_case": "base"}}
        registry = yaml.safe_load(
            (ROOT / "config/sensitivity/national_cloud_center_v1.yaml").read_text(
                encoding="utf-8"
            )
        )

        resolved = apply_ldc_model_state_boundary(source, registry)

        self.assertIs(resolved["model_state"]["enabled"], False)
        self.assertIs(source["model_state"]["enabled"], True)
        self.assertEqual(resolved["model_state"]["parameter_case"], "base")

    def test_missing_or_enabled_ldc_boundary_is_rejected(self) -> None:
        source = {"model_state": {"enabled": True}}
        for registry in ({}, {"model_state": {"enabled": True}}):
            with self.subTest(registry=registry):
                with self.assertRaisesRegex(ValueError, "explicitly disable"):
                    apply_ldc_model_state_boundary(source, registry)


if __name__ == "__main__":
    unittest.main()
