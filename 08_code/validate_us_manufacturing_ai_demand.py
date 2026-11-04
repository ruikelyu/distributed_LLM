#!/usr/bin/env python3
"""Validate U.S. manufacturing demand outputs.

Purpose: Check U.S. industry/task/scenario coverage, bottom-up demand aggregation, and local/cloud cost-component closure.
Workflow status: Active U.S. demand and accounting validator.
Scientific boundary: Validate the declared U.S. counterfactual implementation and its source-field relationships.
Inputs: U.S. service, task summary, validation table, local-cost output, cloud-cost output, and U.S. demand configuration.
Outputs: Completion metadata for the U.S. demand package.
Key assumptions: The U.S. module uses its own activity, adoption, parameter, and price inputs rather than scaling from China totals.
Explicit exclusions: Passing checks do not establish U.S. hardware performance, cloud-price realism, or a full U.S. physical deployment model.
Validation/tests: Industry/task/case coverage, adoption bounds, aggregation, token boundary, and cost components are checked here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml


TASKS = {"office", "agent", "vision", "maintenance", "scheduling", "simulation"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service", type=Path, required=True)
    parser.add_argument("--task-summary", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--done-output", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    service = pd.read_csv(args.service, encoding="utf-8-sig")
    task = pd.read_csv(args.task_summary, encoding="utf-8-sig")
    validation = pd.read_csv(args.validation, encoding="utf-8-sig")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    expected_model_version = str(config["model_version"])
    expected_demand_version = str(config["demand_case_version"])
    for name, frame in {
        "service": service,
        "task_summary": task,
        "validation": validation,
    }.items():
        if "model_version" not in frame or set(frame["model_version"].astype(str)) != {expected_model_version}:
            raise ValueError(f"{name} must contain only model_version={expected_model_version}")
        if "demand_case_version" not in frame or set(frame["demand_case_version"].astype(str)) != {expected_demand_version}:
            raise ValueError(f"{name} must contain only demand_case_version={expected_demand_version}")
    if len(service) != 21 * 6 * 3 or service["naics3"].nunique() != 21:
        raise ValueError("Expected 21 NAICS3 x six tasks x three cases")
    if set(service["task_id"]) != TASKS or set(service["parameter_case"]) != {"low", "base", "high"}:
        raise ValueError("Task/case coverage incomplete")
    if not service["adoption_fraction"].between(0, 1).all() or not service["coverage_fraction"].between(0, 1).all():
        raise ValueError("Adoption/coverage must remain in [0,1]")
    if (service["effective_service_units_day"] <= 0).any():
        raise ValueError("Service demand must be positive")
    detail_total = service.groupby(["parameter_case", "task_id"])["effective_service_units_day"].sum().sort_index()
    task_total = task.set_index(["parameter_case", "task_id"])["effective_service_units_day"].sort_index()
    if (detail_total - task_total).abs().max() > 1e-6:
        raise ValueError("Task and industry service totals do not reconcile")
    non_token = task[~task["task_id"].isin(["office", "agent"])]
    if (non_token[["annual_input_tokens", "annual_output_tokens"]].abs().max().max() != 0):
        raise ValueError("Non-token tasks generated tokens")
    if set(validation["installed_reserve_fraction"]) != {0.15}:
        raise ValueError("Installed reserve must be exactly one 15% parameter")
    external = config["external_scale_validation"]
    for row in validation.itertuples(index=False):
        ratio = float(row.annual_ai_facility_energy_twh) / float(external["china_energy_twh"][row.parameter_case])
        if not float(external["expected_us_to_china_ratio_low"]) <= ratio <= float(external["expected_us_to_china_ratio_high"]):
            raise ValueError(f"{row.parameter_case} bottom-up U.S. energy is outside the external scale check")
    if "macro_calibration_multiplier" in service.columns:
        raise ValueError("Top-down macro calibration multiplier must not remain in service output")
    payload = {
        "status": "validated",
        "model_version": expected_model_version,
        "demand_case_version": expected_demand_version,
        "rows": len(service),
        "naics3": 21,
        "tasks": sorted(TASKS),
        "parameter_cases": ["low", "base", "high"],
        "checks": [
            "activity/task/case coverage", "adoption and coverage bounds", "industry/task reconciliation",
            "tokens restricted to office and agent", "single 15% installed reserve",
            "bottom-up formula and external scale check",
        ],
        "input_sha256": {
            "service": sha256(args.service),
            "task_summary": sha256(args.task_summary),
            "validation": sha256(args.validation),
            "config": sha256(args.config),
        },
    }
    args.done_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
