#!/usr/bin/env python3
"""Validate the unscaled six-task ledger with the reference-energy logic.

Purpose: Verify national service-ledger coverage, scenario ordering, task closure, and reference-energy derivation.
Workflow status: Active demand-input validator.
Scientific boundary: Confirm internal ledger arithmetic without treating external energy references as calibration targets.
Inputs: Model-ready service table, summary/lineage inputs, defaults, and the selected core configuration.
Outputs: Validation findings and completion metadata for the effective-service package.
Key assumptions: Low/base/high cases and all six tasks are explicit, unscaled, and architecture-invariant.
Explicit exclusions: No hardware sizing, cloud billing, or empirical validation of service intensity is performed.
Validation/tests: Industry/task/case coverage and reference-energy relationships are checked before downstream modeling.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

import pandas as pd

from core.config import load_config
from core.data import load_industry_inputs


CASES = ("low", "base", "high")
CASE_ORDER = {case: index for index, case in enumerate(CASES)}
TARGET_ATTRIBUTE = {
    "low": "external_energy_low_twh",
    "base": "external_energy_central_twh",
    "high": "external_energy_high_twh",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-input", type=Path, required=True)
    parser.add_argument("--defaults", type=Path, required=True)
    parser.add_argument("--run-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--findings-output", type=Path, required=True)
    parser.add_argument("--done-output", type=Path, required=True)
    args = parser.parse_args()

    root = Path.cwd()
    config = load_config(root, args.defaults, args.run_config)
    configured_service = root / config["paths"]["model_ready_task_service"]
    if configured_service.resolve() != args.service_input.resolve():
        raise ValueError("validation input must be the configured model-ready service table")
    frame = pd.read_csv(args.service_input, encoding="utf-8-sig")
    if len(frame) != 31 * 6 * 3:
        raise ValueError("model-ready service must contain 31 industries x 6 tasks x 3 cases")
    required = {
        "effective_service_units_day",
        "structural_service_weight",
        "demand_scaling_factor",
        "demand_scaling_method",
        "core_deployment_class",
        "core_included_component",
        "excluded_k_edge_component",
        "excluded_k_pool_component",
        "local_capability_boundary",
        "scope_evidence_grade",
        "scope_status",
        "service_unit",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"unscaled service ledger is missing columns: {sorted(missing)}")
    if not (frame["demand_scaling_factor"].astype(float) == 1.0).all():
        raise ValueError("the model-ready service ledger must not contain demand scaling")
    if set(frame["demand_scaling_method"].astype(str)) != {
        "none_bottom_up_six_task_ledger"
    }:
        raise ValueError("the demand-scaling method must explicitly record no scaling")
    if not frame["effective_service_units_day"].astype(float).equals(
        frame["structural_service_weight"].astype(float)
    ):
        raise ValueError("effective service must equal the unscaled structural ledger")
    configured_scope = str(config["demand"]["effective_service"]["deployment_scope"])
    if configured_scope != "K_choice":
        raise ValueError("the active core deployment scope must be K_choice")
    if set(frame["core_deployment_class"].astype(str)) != {configured_scope}:
        raise ValueError("model-ready task rows do not match the configured deployment scope")
    scope_columns = [
        "core_included_component",
        "excluded_k_edge_component",
        "excluded_k_pool_component",
        "local_capability_boundary",
        "scope_evidence_grade",
        "scope_status",
    ]
    if frame[scope_columns].isna().any().any():
        raise ValueError("model-ready task scope fields must be complete")
    if set(frame["service_unit"].astype(str)) != {"2024_baseline_reference_workload_unit"}:
        raise ValueError("service ledger must use the 2024 baseline-reference-workload unit")

    rows: list[dict[str, object]] = []
    for case in CASES:
        case_config = deepcopy(config)
        case_config["demand"]["effective_service"]["parameter_case"] = case
        for industry_code in config["selected_industries"]:
            inputs = load_industry_inputs(
                case_config,
                industry_code,
                enforce_external_alignment=False,
            )
            alignment = case_config["demand"]["external_energy_alignment"]
            target_energy = float(getattr(inputs, TARGET_ATTRIBUTE[case]))
            target_ratio = inputs.derived_reference_energy_twh / target_energy
            inside = (
                float(alignment["warning_ratio_low"])
                <= target_ratio
                <= float(alignment["warning_ratio_high"])
            )
            rows.append(
                {
                    "parameter_case": case,
                    "industry_code": industry_code,
                    "industry_name_cn": inputs.industry_name,
                    "effective_service_units_day": inputs.daily_effective_service_units,
                    "derived_reference_energy_twh": inputs.derived_reference_energy_twh,
                    "external_energy_low_twh": inputs.external_energy_low_twh,
                    "external_energy_central_twh": inputs.external_energy_central_twh,
                    "external_energy_high_twh": inputs.external_energy_high_twh,
                    "scenario_target_energy_twh": target_energy,
                    "scenario_target_alignment_ratio": target_ratio,
                    "central_alignment_ratio": inputs.external_energy_alignment_ratio,
                    "inside_industry_warning_band": inside,
                    "reference_energy_server_groups": inputs.reference_energy_server_groups,
                }
            )

    validation = pd.DataFrame.from_records(rows)
    validation["_case_order"] = validation["parameter_case"].map(CASE_ORDER)
    validation = validation.sort_values(["_case_order", "industry_code"]).drop(
        columns="_case_order"
    )
    national = (
        validation.groupby("parameter_case", as_index=False)
        .agg(
            effective_service_units_day=("effective_service_units_day", "sum"),
            derived_reference_energy_twh=("derived_reference_energy_twh", "sum"),
            external_energy_low_twh=("external_energy_low_twh", "sum"),
            external_energy_central_twh=("external_energy_central_twh", "sum"),
            external_energy_high_twh=("external_energy_high_twh", "sum"),
            industries_inside_warning_band=("inside_industry_warning_band", "sum"),
        )
    )
    national["_case_order"] = national["parameter_case"].map(CASE_ORDER)
    national = national.sort_values("_case_order").drop(columns="_case_order")
    national_energy = national.set_index("parameter_case")[
        "derived_reference_energy_twh"
    ].astype(float)
    if not (
        0.0
        < national_energy["low"]
        < national_energy["base"]
        < national_energy["high"]
    ):
        raise ValueError("unscaled low/base/high reference energy must be positive and increasing")
    selected_case = config["demand"]["effective_service"]["parameter_case"]
    selected = national[national["parameter_case"] == selected_case]
    if len(selected) != 1:
        raise ValueError(f"missing selected parameter case: {selected_case}")
    selected_row = selected.iloc[0]
    energy = float(selected_row["derived_reference_energy_twh"])
    lower = float(selected_row["external_energy_low_twh"])
    central = float(selected_row["external_energy_central_twh"])
    upper = float(selected_row["external_energy_high_twh"])
    industries_valid = int(selected_row["industries_inside_warning_band"])
    industry_check_mode = config["demand"]["external_energy_alignment"].get(
        "per_industry_check", "hard"
    )
    if industry_check_mode == "hard" and industries_valid != 31:
        invalid = validation[
            (validation["parameter_case"] == selected_case)
            & (~validation["inside_industry_warning_band"])
        ]["industry_code"].tolist()
        raise ValueError(f"industry alignment check failed for: {invalid}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.findings_output.parent.mkdir(parents=True, exist_ok=True)
    args.done_output.parent.mkdir(parents=True, exist_ok=True)
    validation.to_csv(args.output, index=False, encoding="utf-8-sig")
    case_lines = [
        f"- {row.parameter_case}: {row.derived_reference_energy_twh:.3f} TWh/yr; "
        f"the external allocation scenario is for comparison only; industries inside the diagnostic band: {int(row.industries_inside_warning_band)}/31."
        for row in national.itertuples(index=False)
    ]
    args.findings_output.write_text(
        "\n".join(
            [
                "# Task-level effective service recomputation and external consistency check",
                "",
                "This check directly calls the core model's task hourly shapes, server peak capacity, and idle-power logic.",
                "The 2023 task baseline and task-level joint growth scenarios directly determine the 31-industry x 6-task demand structure and national total.",
                "The model no longer scales demand to 8, 14, or 28 TWh targets; the fixed reference system only converts the service ledger into comparable reference electricity.",
                "The same unscaled service ledger is held fixed across all deployment architectures; common IT effective-efficiency and PUE sensitivities do not rewrite service volume.",
                f"The active 2030 common IT effective efficiency is {config['demand']['effective_service']['common_it_effective_efficiency_multiplier']:.1f}x (relative to 2024); this multiplier converts the baseline reference workload into reference compute hours.",
                "All six core tasks are explicitly restricted to the K_choice deployment scope; K_edge and K_pool portions are not in this service ledger.",
                "This classification is an author-confirmed engineering scope, not an empirical estimate of national three-category task shares.",
                "",
                *case_lines,
                "",
                f"Selected case: {selected_case}. Reference electricity {energy:.3f} TWh/yr;",
                f"this is a derived result of the task ledger, not a calibration target; the per-industry external allocation comparison is in {industry_check_mode} mode, {industries_valid}/31 inside the band.",
                "",
                "Interpretation boundary: demand Base is a joint task-intensity scenario, not a literature point forecast;",
                "task-template fallbacks, event frequencies, and per-event compute still need to be replaced with enterprise logs.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    args.done_output.write_text(
        json.dumps(
            {
                "status": "passed",
                "validation_method": "core_hourly_shapes_and_server_capacity_logic",
                "demand_method": "unscaled_bottom_up_six_task_ledger",
                "demand_scaling_factor": 1.0,
                "core_deployment_scope": configured_scope,
                "scope_share_interpretation": "author_approved_boundary_not_empirical_national_share",
                "selected_parameter_case": selected_case,
                "service_unit": "2024_baseline_reference_workload_unit",
                "common_it_effective_efficiency_case": config["demand"]["effective_service"]["common_it_effective_efficiency_case"],
                "common_it_effective_efficiency_multiplier": config["demand"]["effective_service"]["common_it_effective_efficiency_multiplier"],
                "reference_compute_h_per_service_unit": config["demand"]["effective_service"]["reference_compute_h_per_service_unit"],
                "derived_reference_energy_twh": energy,
                "external_range_twh": [lower, central, upper],
                "derived_reference_energy_twh_by_parameter_case": {
                    row.parameter_case: float(row.derived_reference_energy_twh)
                    for row in national.itertuples(index=False)
                },
                "external_values_used_as_model_inputs": False,
                "industries_inside_warning_band": industries_valid,
                "per_industry_check": industry_check_mode,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
