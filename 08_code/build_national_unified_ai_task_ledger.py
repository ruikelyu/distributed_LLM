#!/usr/bin/env python3
"""Build the national shared-demand ledger used by local and cloud accounting.

Purpose:
    Invoke the validated C36 ledger builder once for each mainland
    manufacturing industry and combine the results into one auditable
    31-industry demand and lifecycle package.
Workflow status:
    Active v1.0.0 national-demand input builder. The output is consumed by
    both the national physical/local route and the complete cloud-payment
    route; it does not optimize hardware or prices.
Scientific boundary:
    Preserve the configured low/base/high effective-service scenarios and six
    tasks while separating service demand from its later delivery route.
    Managed-model service, strict-LLM service, and residual CPU/GPU service
    remain attribution fields rather than observed hardware or electricity
    shares. The ledger is intentionally unscaled and is not anchored to an
    external national electricity total.
Inputs:
    ``config/demand_cases/national_local_cloud_core_v1.yaml`` and its base
    scenario, the validated C36 builder and its upstream service parameters,
    and the ordered C13--C43 industry set.
Outputs:
    ``task_ledger.csv``, ``lifecycle_ledger.csv``,
    ``service_reconciliation.csv``, ``task_attribution_summary.csv``, and
    ``validated.done.json`` in the configured ``ledger`` directory.
Key assumptions:
    National coverage is exactly 31 industries × 3 parameter cases × 6
    tasks. Each industry is built with the same ledger logic and its original
    task total is preserved through managed and residual-service fields.
Explicit exclusions:
    This script does not infer observed task shares, choose CPU/GPU hardware,
    calculate cloud prices, or calibrate demand to an external TWh anchor.
    QLoRA/SFT lifecycle quantities are recorded explicitly and must not be
    silently added to existing service demand downstream.
Validation/tests:
    Row coverage, task attribution reconciliation, and lifecycle coverage are
    checked during execution and recorded in ``validated.done.json``. These
    checks establish ledger closure and coverage, not external validation of
    the demand assumptions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/demand_cases/national_local_cloud_core_v1.yaml"),
    )
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wrapper = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    base_path = ROOT / str(wrapper["base_scenario_config"])
    base = yaml.safe_load(base_path.read_text(encoding="utf-8"))
    industries = [str(value) for value in wrapper["industry_codes"]]
    if industries != [f"C{value}" for value in range(13, 44)]:
        raise ValueError("National ledger must use the ordered C13-C43 industry set")
    output = ROOT / (args.output_dir or Path(str(wrapper["output_root"])) / "ledger")

    task_frames: list[pd.DataFrame] = []
    lifecycle_frames: list[pd.DataFrame] = []
    reconciliation_frames: list[pd.DataFrame] = []
    with tempfile.TemporaryDirectory(prefix="national-ledger-") as directory:
        temporary = Path(directory)
        for industry in industries:
            industry_config = dict(base)
            industry_config["industry_code"] = industry
            config_path = temporary / f"{industry}.yaml"
            config_path.write_text(
                yaml.safe_dump(industry_config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            industry_output = temporary / industry
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "08_code/build_c36_unified_ai_task_ledger.py"),
                    "--scenario-config",
                    str(config_path),
                    "--output-dir",
                    str(industry_output),
                ],
                cwd=ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            task_frames.append(pd.read_csv(industry_output / "task_ledger.csv"))
            lifecycle_frames.append(pd.read_csv(industry_output / "lifecycle_ledger.csv"))
            reconciliation_frames.append(
                pd.read_csv(industry_output / "service_reconciliation.csv")
            )

    tasks = pd.concat(task_frames, ignore_index=True)
    lifecycle = pd.concat(lifecycle_frames, ignore_index=True)
    reconciliation = pd.concat(reconciliation_frames, ignore_index=True)
    tasks["national_scenario_version"] = str(wrapper["scenario_version"])
    lifecycle["national_scenario_version"] = str(wrapper["scenario_version"])
    reconciliation["national_scenario_version"] = str(wrapper["scenario_version"])
    if len(tasks) != 31 * 3 * 6 or len(lifecycle) != 31 * 3 * 4:
        raise AssertionError("National ledger row coverage is incomplete")
    if reconciliation.reconciliation_error.abs().max() > 1e-6:
        raise AssertionError("National managed and residual service do not reconcile")

    attribution = (
        tasks.groupby("parameter_case", as_index=False)
        .agg(
            effective_service_units_day=("effective_service_units_day", "sum"),
            foundation_model_service_units_day=("managed_model_service_units_day", "sum"),
            strict_llm_service_units_day=("strict_llm_service_units_day", "sum"),
        )
        .assign(
            foundation_model_service_share=lambda frame: (
                frame.foundation_model_service_units_day
                / frame.effective_service_units_day
            ),
            strict_llm_service_share=lambda frame: (
                frame.strict_llm_service_units_day
                / frame.effective_service_units_day
            ),
            evidence_status="scenario_attribution_not_observed_national_mean",
        )
    )
    output.mkdir(parents=True, exist_ok=True)
    tasks.to_csv(output / "task_ledger.csv", index=False, encoding="utf-8-sig")
    lifecycle.to_csv(
        output / "lifecycle_ledger.csv", index=False, encoding="utf-8-sig"
    )
    reconciliation.to_csv(
        output / "service_reconciliation.csv", index=False, encoding="utf-8-sig"
    )
    attribution.to_csv(
        output / "task_attribution_summary.csv", index=False, encoding="utf-8-sig"
    )
    payload = {
        "status": "validated_national_shared_demand_ledger_screening_parameters",
        "scenario_version": wrapper["scenario_version"],
        "base_scenario_version": base["scenario_version"],
        "industry_count": len(industries),
        "task_rows": len(tasks),
        "lifecycle_rows": len(lifecycle),
        "maximum_service_reconciliation_error": float(
            reconciliation.reconciliation_error.abs().max()
        ),
        "same_ledger_required_for_local_and_cloud": True,
        "manuscript_outputs_modified": False,
    }
    (output / "validated.done.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
