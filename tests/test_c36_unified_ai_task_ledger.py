from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


class C36UnifiedTaskLedgerTest(unittest.TestCase):
    def test_shared_ledger_reconciles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ledger"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "08_code/build_c36_unified_ai_task_ledger.py"),
                    "--output-dir",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
            )
            task = pd.read_csv(output / "task_ledger.csv")
            lifecycle = pd.read_csv(output / "lifecycle_ledger.csv")
            attribution = pd.read_csv(output / "task_attribution_summary.csv")
            self.assertEqual(set(task.parameter_case), {"low", "base", "high"})
            self.assertEqual(
                set(task.task_id),
                {"office", "agent", "vision", "maintenance", "scheduling", "simulation"},
            )
            self.assertEqual(len(task), 18)
            reconstructed = (
                task.managed_model_service_units_day
                + task.residual_cpu_gpu_service_units_day
            )
            self.assertTrue(
                (reconstructed - task.effective_service_units_day).abs().max() < 1e-6
            )
            self.assertTrue((task.model_calls_day > 0).all())
            base = task[task.parameter_case == "base"].set_index("task_id")
            self.assertEqual(base.loc["office", "managed_model_share"], 1.0)
            self.assertEqual(base.loc["agent", "managed_model_share"], 1.0)
            self.assertEqual(base.loc["simulation", "managed_model_share"], 0.25)
            self.assertEqual(len(attribution), 3)
            base_attribution = attribution[attribution.parameter_case == "base"].iloc[0]
            self.assertGreater(base_attribution.foundation_model_service_share, 0.5)
            self.assertLess(base_attribution.strict_llm_service_share, 0.5)
            self.assertEqual(
                set(lifecycle.component),
                {
                    "rag_knowledge_base",
                    "agent_tool_calls",
                    "agent_runtime",
                    "qlora_sft_training",
                },
            )
            qlora = lifecycle[lifecycle.component == "qlora_sft_training"]
            self.assertTrue((qlora.annual_tokens > 0).all())
            self.assertTrue(
                qlora.sort_values("parameter_case").annual_tokens.nunique() == 3
            )


if __name__ == "__main__":
    unittest.main()
