from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = "config/demand_cases/national_local_cloud_core_v1.yaml"


class NationalLocalVsCloudCostV1Test(unittest.TestCase):
    def test_national_ledger_and_cost_boundaries_reconcile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            ledger = temporary / "ledger"
            cost = temporary / "cost"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "08_code/build_national_unified_ai_task_ledger.py"),
                    "--config",
                    CONFIG,
                    "--output-dir",
                    str(ledger),
                ],
                cwd=ROOT,
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "08_code/run_national_local_vs_cloud_cost_v1.py"),
                    "--config",
                    CONFIG,
                    "--task-ledger",
                    str(ledger / "task_ledger.csv"),
                    "--lifecycle-ledger",
                    str(ledger / "lifecycle_ledger.csv"),
                    "--output-dir",
                    str(cost),
                ],
                cwd=ROOT,
                check=True,
            )

            tasks = pd.read_csv(ledger / "task_ledger.csv")
            comparison = pd.read_csv(cost / "comparison.csv")
            components = pd.read_csv(cost / "cloud_cost_components.csv")
            local = pd.read_csv(cost / "local_cost_components.csv")
            validation = json.loads((cost / "validated.done.json").read_text())

            self.assertEqual(tasks.industry_code.nunique(), 31)
            self.assertEqual(len(tasks), 31 * 3 * 6)
            self.assertEqual(len(comparison), 3 * 4 * 3)
            self.assertEqual(comparison.provider_bundle.nunique(), 4)
            self.assertEqual(
                set(comparison.local_architecture),
                {"PF", "SHG", "MSG"},
            )
            self.assertEqual(set(comparison.cloud_price_case), {"low", "base", "high"})
            self.assertTrue((comparison.local_service_share == 1.0).all())
            self.assertTrue((comparison.cloud_service_share == 1.0).all())
            self.assertTrue(comparison.equal_effectiveness_assumption.all())

            observed = comparison.groupby(
                ["cloud_price_case", "provider_bundle"]
            ).annual_100pct_cloud_cost_rmb.first()
            reconstructed = components.groupby(
                ["price_case", "provider_bundle"]
            ).annual_cost_rmb.sum()
            reconstructed.index.names = observed.index.names
            pd.testing.assert_series_equal(
                observed.sort_index(), reconstructed.sort_index(), check_names=False
            )
            self.assertTrue(
                (local.rag_available_bundled_storage_gb >= local.rag_required_storage_gb).all()
            )
            self.assertTrue(validation["same_service"])
            self.assertTrue(validation["cloud_components_reconcile"])


if __name__ == "__main__":
    unittest.main()
