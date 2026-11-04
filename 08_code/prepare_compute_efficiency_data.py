#!/usr/bin/env python3
"""Prepare the author-confirmed common 2030 IT-effective-efficiency cases.

Purpose: Convert the 2024-normalized 1.5/3.0/5.0 efficiency scenarios into
reference compute-hours required per effective-service unit.
Workflow status: Active parameter-preparation step for the infrastructure-first
core and sensitivity runs.
Scientific boundary: The multiplier is common to PF, SHG, MSG and LDC and to
the modeled CPU/GPU paths. It changes baseline reference workload to reference
compute-hours before sizing and scheduling.
Inputs: Author-confirmed scenario multipliers and their scope labels.
Outputs: A model-ready scenario table and lineage metadata.
Key assumptions: One effective-service unit carries one 2024 baseline reference
workload unit; required reference compute-hours equal workload divided by the
common IT-effective-efficiency multiplier.
Explicit exclusions: PUE, planning headroom, temporal shifting, spatial
coordination and workload rebound are not part of this multiplier. The cases
are not forecasts, confidence intervals, hardware SKUs or rack-density claims.
Validation/tests: Exact case coverage, years, positive values, unique 3.0 main
case, reciprocal conversion and common scope are checked here and downstream.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


EXPECTED_CASES = {
    "it_efficiency_1p5": 1.5,
    "it_efficiency_3p0": 3.0,
    "it_efficiency_5p0": 5.0,
}
EXPECTED_NORMALIZATION_YEAR = 2024
EXPECTED_TARGET_YEAR = 2030
EXPECTED_SCOPE = "all_architectures_and_cpu_gpu_paths"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lineage-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = pd.read_csv(args.input, encoding="utf-8-sig")
    required = {
        "efficiency_case",
        "normalization_year",
        "target_year",
        "baseline_reference_workload_per_service_unit",
        "common_it_effective_efficiency_multiplier",
        "evidence_status",
        "scope",
        "interpretation",
    }
    if set(frame.columns) != required:
        raise ValueError(f"Efficiency input columns must be exactly {sorted(required)}")
    if len(frame) != len(EXPECTED_CASES) or set(frame["efficiency_case"]) != set(EXPECTED_CASES):
        raise ValueError("Efficiency cases must be it_efficiency_1p5, it_efficiency_3p0, and it_efficiency_5p0")
    if frame["efficiency_case"].duplicated().any():
        raise ValueError("Efficiency cases must be unique")
    if set(frame["normalization_year"].astype(int)) != {EXPECTED_NORMALIZATION_YEAR}:
        raise ValueError("All efficiency cases must use the 2024 normalization")
    if set(frame["target_year"].astype(int)) != {EXPECTED_TARGET_YEAR}:
        raise ValueError("All efficiency cases must target 2030")
    if set(frame["scope"].astype(str)) != {EXPECTED_SCOPE}:
        raise ValueError("Efficiency must apply symmetrically to all architectures and CPU/GPU paths")
    workload = frame["baseline_reference_workload_per_service_unit"].astype(float)
    multipliers = frame["common_it_effective_efficiency_multiplier"].astype(float)
    if (workload <= 0).any() or (multipliers <= 0).any():
        raise ValueError("Reference workload and efficiency multipliers must be positive")
    actual = dict(zip(frame["efficiency_case"], multipliers))
    if any(abs(actual[case] - expected) > 1e-12 for case, expected in EXPECTED_CASES.items()):
        raise ValueError("Configured efficiency multipliers must be exactly 1.5, 3.0, and 5.0")
    output = frame.copy()
    output["reference_compute_h_per_service_unit"] = workload / multipliers
    output["is_main_scenario"] = output["efficiency_case"].eq("it_efficiency_3p0")
    output["conversion_rule"] = "baseline_reference_workload_divided_by_common_it_effective_efficiency"
    order = {case: index for index, case in enumerate(EXPECTED_CASES)}
    output = output.sort_values("efficiency_case", key=lambda values: values.map(order))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, encoding="utf-8-sig")
    lineage = {
        "status": "validated",
        "source": str(args.input),
        "output": str(args.output),
        "cases": output["efficiency_case"].tolist(),
        "normalization_year": EXPECTED_NORMALIZATION_YEAR,
        "target_year": EXPECTED_TARGET_YEAR,
        "main_case": "it_efficiency_3p0",
        "common_it_effective_efficiency_multipliers": [1.5, 3.0, 5.0],
        "minimum_reference_compute_h_per_service_unit": float(output["reference_compute_h_per_service_unit"].min()),
        "maximum_reference_compute_h_per_service_unit": float(output["reference_compute_h_per_service_unit"].max()),
        "conversion_rule": "baseline_reference_workload_divided_by_common_it_effective_efficiency",
        "external_energy_calibration_applied": False,
        "excluded_from_multiplier": ["PUE", "planning_headroom", "temporal_shifting", "MSG_spatial_coordination", "workload_rebound"],
        "interpretation": "Author-confirmed common IT-effective-efficiency scenarios; not a forecast, confidence interval, hardware SKU, or rack-density assumption.",
    }
    args.lineage_output.parent.mkdir(parents=True, exist_ok=True)
    args.lineage_output.write_text(json.dumps(lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
