#!/usr/bin/env python3
"""Compare distributed architectures with an all-industry logical LDC pool.

Purpose: Summarize national grid-capacity and energy comparisons across active distributed and centralized physical cases.
Workflow status: Active grid-capacity post-processing module.
Scientific boundary: Compare emitted architecture summaries and matched baseline increments; LDC_AGGREGATE is a logical new-capacity portfolio, not one physical site.
Inputs: National architecture summaries, cloud-center output, and validation metadata.
Outputs: Comparison table, findings, and completion metadata.
Key assumptions: Incremental grid capacity is a positive net peak increase relative to the paired no-AI baseline, with zero existing capacity for the greenfield LDC portfolio.
Explicit exclusions: Physical LDC siting, grid-upgrade monetary cost, transmission constraints, and provider billing are not inferred from MW comparisons.
Validation/tests: Architecture labels, equal-service and scenario-contract fields, row coverage, baseline pairing, and nonnegative increment checks are enforced.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ARCHITECTURE_LABELS = {
    "PF": "factory_distributed",
    "SHG": "group_single_host",
    "MSG": "group_multisite",
}
GROUP_ARCHITECTURES = {"PF", "SHG", "MSG"}
CONTRACT_FIELDS = [
    "model_version",
    "common_it_effective_efficiency_case",
    "common_it_effective_efficiency_multiplier",
    "baseline_reference_workload_per_service_unit",
    "reference_compute_h_per_service_unit",
    "reference_server_group",
    "planning_reserve_fraction",
    "n_plus_spare_server_groups",
    "model_state_minimum_groups_enabled",
]


def load_national(path: Path) -> pd.DataFrame:
    national = pd.read_csv(path, encoding="utf-8-sig")
    if {"architecture", "base_load_case", "industry"}.issubset(national.columns):
        national = national.loc[national["base_load_case"].eq("actual_load")].copy()
        national["scenario"] = national["architecture"].astype(str)
        national["industry_code"] = national["industry"].astype(str)
        national["industry_equivalent_incremental_grid_expansion_mw"] = national[
            "industry_equivalent_sum_incremental_grid_peak_mw"
        ]
    return national


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--national-summary", type=Path, required=True)
    parser.add_argument("--national-validation", type=Path, required=True)
    parser.add_argument("--cloud-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--done-output", type=Path, required=True)
    args = parser.parse_args()

    national = load_national(args.national_summary)
    validation = json.loads(args.national_validation.read_text(encoding="utf-8"))
    cloud = pd.read_csv(args.cloud_summary, encoding="utf-8-sig")
    present = set(national["scenario"])
    if present not in (GROUP_ARCHITECTURES, {"SHG"}):
        raise AssertionError(
            "national summary must contain SHG or the full PF / SHG / MSG set"
        )
    if validation.get("status") != "validated":
        raise AssertionError("national group-core validation marker is not validated")
    if set(validation.get("actual_load_architectures", [])) != present:
        raise AssertionError("national validation architecture set does not match the summary")
    if national["industry_code"].nunique() != 31:
        raise AssertionError("national summary must contain all 31 industries")
    if len(cloud) != 1 or int(cloud.iloc[0]["industry_count"]) != 31:
        raise AssertionError("LDC reference must be one logical pool serving all 31 industries")

    cloud_row = cloud.iloc[0]
    if cloud_row["architecture"] != "LDC_AGGREGATE":
        raise AssertionError("centralized reference must use LDC_AGGREGATE")
    if cloud_row["architecture_display_label"] != "LDC-aggregate":
        raise AssertionError("centralized display label must be LDC-aggregate")
    if bool(cloud_row["installed_server_groups_integer"]):
        raise AssertionError("LDC aggregate installed capacity must remain continuous")
    if bool(cloud_row["online_server_groups_integer"]):
        raise AssertionError("LDC aggregate online capacity must remain continuous")
    if cloud_row["solver_status"] != "ok" or cloud_row["solver_condition"] != "optimal":
        raise AssertionError("LDC aggregate optimization did not finish optimally")
    if "logical_resource_pool_not_one_physical_site" not in str(cloud_row["interpretation"]):
        raise AssertionError("LDC interpretation must prohibit a one-physical-site inference")
    for field in CONTRACT_FIELDS:
        values = national[field].drop_duplicates()
        if len(values) != 1:
            raise AssertionError(f"national package mixes incompatible {field} values")
        national_value = values.iloc[0]
        cloud_value = cloud_row[field]
        if pd.api.types.is_number(national_value):
            if not np.isclose(float(national_value), float(cloud_value), rtol=0, atol=1e-12):
                raise AssertionError(f"LDC differs from distributed cases on paired field {field}")
        elif str(national_value) != str(cloud_value):
            raise AssertionError(f"LDC differs from distributed cases on paired field {field}")
    service_by_industry = national.groupby("industry_code")[
        "industry_equivalent_weekly_service_units"
    ]
    service_spread = service_by_industry.max() - service_by_industry.min()
    service_scale = service_by_industry.max().abs().clip(lower=1.0)
    if not (service_spread.abs() <= service_scale * 1e-9).all():
        raise AssertionError("distributed architectures do not serve equal industry demand")
    distributed_daily_service = float(service_by_industry.first().sum() / 7.0)
    if not np.isclose(
        distributed_daily_service,
        float(cloud_row["daily_effective_service_units"]),
        rtol=1e-9,
    ):
        raise AssertionError("distributed and LDC cases do not serve equal national demand")
    if not np.isclose(
        float(cloud_row["daily_effective_service_units"]),
        float(cloud_row["reconstructed_daily_effective_service_units"]),
        rtol=1e-9,
    ):
        raise AssertionError("LDC hourly dispatch does not reconstruct its service ledger")

    cloud_mw = float(cloud_row["incremental_grid_expansion_mw"])
    if cloud_mw <= 0 or not np.isclose(
        cloud_mw, float(cloud_row["grid_import_peak_mw"]), rtol=0, atol=1e-5
    ):
        raise AssertionError("greenfield LDC capacity must equal its positive grid-import peak")
    rows = []
    for scenario, group in national.groupby("scenario"):
        architecture_mw = float(group["industry_equivalent_incremental_grid_expansion_mw"].sum())
        difference_mw = cloud_mw - architecture_mw
        rows.append(
            {
                "comparison_basis": "equal_service_new_LDC_aggregate_capacity_portfolio",
                "scenario": scenario,
                "architecture": ARCHITECTURE_LABELS[scenario],
                "architecture_national_incremental_grid_expansion_mw": architecture_mw,
                "ldc_aggregate_incremental_grid_expansion_mw": cloud_mw,
                "capacity_difference_vs_ldc_aggregate_mw": difference_mw,
                "capacity_difference_vs_ldc_aggregate_fraction": difference_mw / cloud_mw,
                "lower_screening_capacity_than_ldc_aggregate": bool(difference_mw > 0),
            }
        )

    result = pd.DataFrame(rows).sort_values("scenario")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    payload = {
        "status": "validated",
        "model_version": str(cloud_row["model_version"]),
        "comparison_basis": "equal-service new LDC aggregate capacity portfolio",
        "distributed_architectures": sorted(present),
        "centralized_architecture": "LDC_AGGREGATE",
        "centralized_capacity_is_one_physical_site": False,
        "equal_service_verified": True,
        "all_distributed_architectures_have_lower_screening_capacity_than_ldc_aggregate": bool(
            result["lower_screening_capacity_than_ldc_aggregate"].all()
        ),
        "evidence_status": "outputs_validated_not_interpreted",
        "claim_boundary": "site_facing_continuous_MW_screen_not_avoided_grid_investment",
    }
    args.done_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
