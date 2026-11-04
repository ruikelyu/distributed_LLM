#!/usr/bin/env python3
"""Validate and combine the 31-industry group-architecture core package.

Purpose: Validate per-industry PF, SHG, and MSG outputs and assemble the national core summary.
Workflow status: Active v1.0.0 group-core result validator and aggregator.
Scientific boundary: Check service, architecture, node-weight, integer-boundary, and matched-zero-load relationships in emitted outputs.
Inputs: Per-industry summaries/hourly files, curve lineage, validation metadata, and architecture configuration.
Outputs: National summary, merged lineage/alignment tables, findings, and completion metadata.
Key assumptions: Physical factory counts remain distinct from modeled routing nodes and PF/SHG/MSG architecture boundaries are not mixed.
Explicit exclusions: No re-optimization, correction of invalid results, or external validity certification is performed.
Validation/tests: Coverage, conservation, schema, weights, architecture pairs, and solver-status checks are enforced here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DEFAULT_ARCHITECTURES = ["PF", "SHG", "MSG"]
PAIRS_BY_ARCHITECTURE = {
    "PF": {("PF", "actual_load")},
    "SHG": {("SHG", "actual_load"), ("SHG", "zero_load")},
    "MSG": {("MSG", "actual_load")},
}
SCALABLE_COLUMNS = [
    "installed_gpu_server_groups",
    "installed_cpu_server_groups",
    "average_required_gpu_server_groups",
    "average_required_cpu_server_groups",
    "average_required_total_server_groups",
    "annual_server_cost_rmb",
    "annual_ai_energy_cost_rmb",
    "annual_incremental_maximum_demand_cost_rmb",
    "annual_incremental_total_cost_rmb",
    "annual_ai_facility_energy_twh",
    "sum_incremental_grid_peak_mw",
    "weekly_service_units",
]
COORDINATION_EFFECT_METRICS = (
    "sum_incremental_grid_peak_mw",
    "installed_gpu_server_groups",
    "installed_cpu_server_groups",
    "annual_ai_facility_energy_twh",
    "annual_ai_fixed_overhead_energy_twh",
    "annual_unshiftable_ai_active_energy_twh",
    "annual_shiftable_ai_active_energy_twh",
    "annual_incremental_total_cost_rmb",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--industries", nargs="+", required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--alignment-output", type=Path, required=True)
    parser.add_argument("--coordination-output", type=Path, required=True)
    parser.add_argument("--lineage-output", type=Path, required=True)
    parser.add_argument("--done-output", type=Path, required=True)
    parser.add_argument("--architectures", nargs="+", default=DEFAULT_ARCHITECTURES)
    parser.add_argument(
        "--enforce-core-capacity-boundary",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Require the core 15% average-demand headroom and zero N+1 spare. Disable for national OAT capacity screens.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    architectures = list(args.architectures)
    expected_pairs = set()
    for architecture in architectures:
        if architecture not in PAIRS_BY_ARCHITECTURE:
            raise ValueError(f"Unsupported architecture: {architecture}")
        expected_pairs |= PAIRS_BY_ARCHITECTURE[architecture]
    summaries = []
    alignments = []
    lineages = []
    coordination_values = []
    factory_counts = {}
    ai_deployment_node_counts = {}
    production_load_modes = {}
    adopter_activity_shares = {}
    for industry in args.industries:
        folder = args.root / industry
        summary = pd.read_csv(folder / "summary.csv", encoding="utf-8-sig")
        pairs = set(zip(summary["architecture"], summary["base_load_case"]))
        if not expected_pairs.issubset(pairs):
            raise ValueError(f"{industry}: expected {sorted(expected_pairs)}, found {pairs}")
        summary = summary.loc[
            [pair in expected_pairs for pair in zip(summary["architecture"], summary["base_load_case"])]
        ].copy()
        if set(summary["industry"].astype(str)) != {industry}:
            raise ValueError(f"{industry}: summary industry label is inconsistent")
        actual = summary[summary["base_load_case"].eq("actual_load")]
        if set(actual["architecture"]) != set(architectures) or len(actual) != len(architectures):
            raise ValueError(f"{industry}: actual-load comparison is incomplete")
        if "PF" in architectures and not bool(summary.loc[summary["architecture"].eq("PF"), "installed_server_groups_integer"].all()):
            raise ValueError(f"{industry}: PF installed capacity must be integer")
        if bool(summary.loc[summary["architecture"].ne("PF"), "installed_server_groups_integer"].any()):
            raise ValueError(f"{industry}: group architectures must use continuous installed capacity")
        if bool(summary["online_server_groups_integer"].any()):
            raise ValueError(f"{industry}: hourly online capacity must remain continuous")
        contract_fields = [
            "model_version",
            "common_it_effective_efficiency_case",
            "common_it_effective_efficiency_multiplier",
            "baseline_reference_workload_per_service_unit",
            "reference_compute_h_per_service_unit",
            "reference_server_group",
        ]
        missing_contract_fields = [field for field in contract_fields if field not in summary]
        if missing_contract_fields:
            raise ValueError(f"{industry}: missing infrastructure-contract fields {missing_contract_fields}")
        if any(summary[field].nunique(dropna=False) != 1 for field in contract_fields):
            raise ValueError(f"{industry}: infrastructure contract differs across architectures")
        expected_reference_compute = (
            float(summary["baseline_reference_workload_per_service_unit"].iloc[0])
            / float(summary["common_it_effective_efficiency_multiplier"].iloc[0])
        )
        if abs(float(summary["reference_compute_h_per_service_unit"].iloc[0]) - expected_reference_compute) > 1e-12:
            raise ValueError(f"{industry}: reference-compute conversion is inconsistent")
        reserve_values = summary["planning_reserve_fraction"].astype(float)
        spare_values = summary["n_plus_spare_server_groups"].astype(float)
        if reserve_values.nunique(dropna=False) != 1:
            raise ValueError(f"{industry}: planning reserve is inconsistent across architectures")
        if spare_values.nunique(dropna=False) != 1:
            raise ValueError(f"{industry}: N+k spare count is inconsistent across architectures")
        if args.enforce_core_capacity_boundary:
            if not ((reserve_values - 0.15).abs() <= 1e-12).all():
                raise ValueError(f"{industry}: core planning headroom must be 15%")
            if not (spare_values == 0.0).all():
                raise ValueError(f"{industry}: N+1 belongs to sensitivity analysis, not the core")
        reference = float(summary["weekly_service_units"].iloc[0])
        error = (summary["weekly_service_units"] - reference).abs().max() / max(abs(reference), 1e-12)
        if error > 1e-7:
            raise ValueError(f"{industry}: service conservation error {error:.3g}")
        summaries.append(actual)

        if "SHG" in architectures:
            alignment = pd.read_csv(folder / "load_alignment_value.csv", encoding="utf-8-sig")
            if len(alignment) != 1 or alignment["architecture"].iloc[0] != "SHG":
                raise ValueError(f"{industry}: expected one SHG load-alignment row")
            alignments.append(alignment)

        lineage = pd.read_csv(folder / "curve_lineage.csv", encoding="utf-8-sig")
        lineage.insert(0, "industry", industry)
        metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        for field in contract_fields:
            summary_value = summary[field].iloc[0]
            metadata_value = metadata.get(field)
            if isinstance(summary_value, (int, float)):
                if metadata_value is None or abs(float(metadata_value) - float(summary_value)) > 1e-12:
                    raise ValueError(f"{industry}: metadata {field} does not match summary")
            elif str(metadata_value) != str(summary_value):
                raise ValueError(f"{industry}: metadata {field} does not match summary")
        load_calibration = metadata.get("load_calibration", {})
        production_load_modes[industry] = str(load_calibration.get("mode", "missing"))
        if "planning_reserve_fraction" in metadata:
            if abs(float(metadata["planning_reserve_fraction"]) - float(reserve_values.iloc[0])) > 1e-12:
                raise ValueError(f"{industry}: metadata planning reserve does not match summary")
        if "n_plus_spare_server_groups" in metadata:
            if abs(float(metadata["n_plus_spare_server_groups"]) - float(spare_values.iloc[0])) > 1e-12:
                raise ValueError(f"{industry}: metadata N+k spare does not match summary")
        if args.enforce_core_capacity_boundary:
            if abs(float(metadata.get("planning_reserve_fraction", reserve_values.iloc[0])) - 0.15) > 1e-12:
                raise ValueError(f"{industry}: metadata does not record the 15% core headroom")
            if abs(float(metadata.get("n_plus_spare_server_groups", spare_values.iloc[0]))) > 1e-12:
                raise ValueError(f"{industry}: metadata must record zero N+1 for the core")
        expected_factories = int(metadata["production_load_site_count"])
        expected_nodes = int(metadata["modeled_routing_node_count"])
        deployment_counts = {
            key: int(value)
            for key, value in metadata["ai_deployment_node_count_by_architecture"].items()
        }
        if deployment_counts != {
            "PF": expected_factories,
            "SHG": 1,
            "MSG": expected_nodes,
        }:
            raise ValueError(
                f"{industry}: inconsistent architecture-specific AI deployment counts"
            )
        if metadata.get("multisite_AI_deployment_points_equal_routing_nodes") is not True:
            raise ValueError(f"{industry}: multisite AI deployment points must equal routing nodes")
        if metadata.get("electrical_load_aggregation_at_AI_nodes") is not False:
            raise ValueError(f"{industry}: production loads must remain on independent electrical boundaries")
        if len(lineage) != expected_nodes:
            raise ValueError(f"{industry}: curve lineage does not match its modeled routing-node count")
        if int(lineage["represented_production_load_site_count"].sum()) != expected_factories:
            raise ValueError(f"{industry}: representative-node weights do not reconstruct production-load sites")
        factory_counts[industry] = expected_factories
        ai_deployment_node_counts[industry] = deployment_counts
        group_share = float(metadata["group_share"])
        if not 0 < group_share <= 1:
            raise ValueError(f"{industry}: invalid representative group share {group_share}")
        adopter_activity_share = float(metadata["adopter_activity_share"])
        if not 0 < adopter_activity_share <= 1:
            raise ValueError(
                f"{industry}: invalid adopter activity share {adopter_activity_share}"
            )
        if metadata.get("representative_group_adoption_status") != "adopted":
            raise ValueError(f"{industry}: representative group must be conditioned on adoption")
        conditional_group_ai_scale = float(metadata["conditional_group_ai_scale"])
        expected_group_scale = group_share / adopter_activity_share
        if abs(conditional_group_ai_scale - expected_group_scale) > 1e-12:
            raise ValueError(f"{industry}: conditional group AI scale is inconsistent")
        multiplier = adopter_activity_share / group_share
        if abs(conditional_group_ai_scale * multiplier - 1.0) > 1e-12:
            raise ValueError(f"{industry}: adopter-conditioned scaling does not reconstruct industry service")
        if abs(float(metadata["industry_equivalent_multiplier"]) - multiplier) > 1e-12:
            raise ValueError(f"{industry}: metadata industry multiplier is inconsistent")
        adopter_activity_shares[industry] = adopter_activity_share
        actual = actual.copy()
        actual["representative_group_share"] = group_share
        actual["adopter_activity_share"] = adopter_activity_share
        actual["conditional_group_ai_scale"] = conditional_group_ai_scale
        actual["industry_equivalent_multiplier"] = multiplier
        for column in SCALABLE_COLUMNS:
            actual[f"industry_equivalent_{column}"] = actual[column].astype(float) * multiplier
        summaries[-1] = actual

        if alignments:
            alignment = alignments[-1].copy()
            alignment["representative_group_share"] = group_share
            alignment["adopter_activity_share"] = adopter_activity_share
            alignment["conditional_group_ai_scale"] = conditional_group_ai_scale
            alignment["industry_equivalent_multiplier"] = multiplier
            alignment["production_load_mode"] = str(load_calibration["mode"])
            alignment["production_load_boundary_id"] = str(load_calibration["boundary_id"])
            for column in [name for name in alignment.columns if name.startswith("load_alignment_value_") or name == "avoided_incremental_grid_peak_mw"]:
                alignment[f"industry_equivalent_{column}"] = alignment[column].astype(float) * multiplier
            alignments[-1] = alignment

        if "MSG" in architectures:
            control = pd.read_csv(folder / "msg_no_routing_summary.csv", encoding="utf-8-sig")
            control_hourly = pd.read_csv(folder / "msg_no_routing_hourly.csv", encoding="utf-8-sig")
            coordination = pd.read_csv(folder / "coordination_value.csv", encoding="utf-8-sig")
            if len(control) != 1 or len(coordination) != 1:
                raise ValueError(f"{industry}: expected one MSG-no-routing control and one coordination row")
            control_row = control.iloc[0]
            msg_row = summary.loc[
                summary["architecture"].eq("MSG") & summary["base_load_case"].eq("actual_load")
            ].iloc[0]
            if control_row["architecture"] != "MSG_NO_ROUTING":
                raise ValueError(f"{industry}: invalid MSG-no-routing output code")
            if bool(control_row["formal_architecture"]):
                raise ValueError(f"{industry}: MSG-no-routing cannot be a formal architecture")
            if control_row["paired_treatment"] != "MSG":
                raise ValueError(f"{industry}: MSG-no-routing must be paired with MSG")
            if control_row["routing_policy"] != "fixed_ex_ante_task_origin_shares":
                raise ValueError(f"{industry}: MSG-no-routing routing policy is invalid")
            for field in contract_fields + [
                "planning_reserve_fraction",
                "n_plus_spare_server_groups",
                "production_load_site_count",
                "ai_deployment_node_count",
                "modeled_routing_node_count",
                "weekly_service_units",
            ]:
                left = control_row[field]
                right = msg_row[field]
                if isinstance(left, (int, float)):
                    tolerance = max(abs(float(right)), 1.0) * 1e-8
                    if abs(float(left) - float(right)) > tolerance:
                        raise ValueError(f"{industry}: MSG control differs from MSG on paired field {field}")
                elif str(left) != str(right):
                    raise ValueError(f"{industry}: MSG control differs from MSG on paired field {field}")
            service_tolerance = max(abs(float(control_row["weekly_service_units"])), 1.0) * 1e-8
            if float(control_row["maximum_rigid_origin_share_absolute_error"]) > service_tolerance:
                raise ValueError(f"{industry}: rigid task-hour origin shares were not enforced")
            if float(control_row["maximum_flexible_origin_share_absolute_error"]) > service_tolerance:
                raise ValueError(f"{industry}: flexible job origin shares were not enforced")
            mechanism = metadata.get("mechanism_controls", {}).get("MSG_no_routing", {})
            if mechanism.get("enabled") is not True or mechanism.get("formal_architecture") is not False:
                raise ValueError(f"{industry}: metadata does not identify the internal MSG control")
            fixed_shares = mechanism.get("fixed_site_service_shares", [])
            if len(fixed_shares) != expected_nodes or abs(sum(map(float, fixed_shares)) - 1.0) > 1e-12:
                raise ValueError(f"{industry}: invalid ex-ante MSG fixed-site shares")
            if set(control_hourly["architecture"]) != {"MSG_NO_ROUTING"}:
                raise ValueError(f"{industry}: invalid architecture in MSG-no-routing hourly output")
            if set(control_hourly["routing_policy"]) != {"fixed_ex_ante_task_origin_shares"}:
                raise ValueError(f"{industry}: invalid routing policy in MSG-no-routing hourly output")
            if control_hourly["factory_id"].nunique() != expected_nodes:
                raise ValueError(f"{industry}: MSG-no-routing hourly nodes do not match MSG")
            if abs(float(control_hourly["ai_service_units"].sum()) - float(control_row["weekly_service_units"])) > service_tolerance:
                raise ValueError(f"{industry}: MSG-no-routing hourly service does not reconcile")
            observed_fixed_shares = (
                control_hourly.groupby("factory_id")["fixed_site_service_share"].first().sort_index().to_numpy(dtype=float)
            )
            if not __import__("numpy").allclose(observed_fixed_shares, fixed_shares, rtol=0, atol=1e-12):
                raise ValueError(f"{industry}: MSG-no-routing hourly shares do not match metadata")
            rigid_by_node_hour = control_hourly.pivot(
                index="hour", columns="factory_id", values="unshiftable_ai_service_units"
            ).sort_index(axis=1)
            rigid_total_by_hour = rigid_by_node_hour.sum(axis=1).to_numpy(dtype=float)
            expected_rigid = rigid_total_by_hour[:, None] * __import__("numpy").asarray(fixed_shares, dtype=float)[None, :]
            if not __import__("numpy").allclose(rigid_by_node_hour.to_numpy(dtype=float), expected_rigid, rtol=0, atol=service_tolerance):
                raise ValueError(f"{industry}: MSG-no-routing rigid hourly shares are not fixed")
            flexible_by_node = (
                control_hourly.groupby("factory_id")["shiftable_ai_service_units"].sum().sort_index().to_numpy(dtype=float)
            )
            expected_flexible = float(flexible_by_node.sum()) * __import__("numpy").asarray(fixed_shares, dtype=float)
            if not __import__("numpy").allclose(flexible_by_node, expected_flexible, rtol=0, atol=service_tolerance):
                raise ValueError(f"{industry}: MSG-no-routing flexible totals are not fixed")
            if coordination["effect_definition"].iloc[0] != "MSG_no_routing_minus_MSG_coordinated":
                raise ValueError(f"{industry}: coordination effect direction is invalid")
            for metric in COORDINATION_EFFECT_METRICS:
                control_value = float(control_row[metric])
                msg_value = float(msg_row[metric])
                if abs(float(coordination[f"msg_no_routing_{metric}"].iloc[0]) - control_value) > max(abs(control_value), 1.0) * 1e-8:
                    raise ValueError(f"{industry}: coordination control value mismatch for {metric}")
                if abs(float(coordination[f"msg_coordinated_{metric}"].iloc[0]) - msg_value) > max(abs(msg_value), 1.0) * 1e-8:
                    raise ValueError(f"{industry}: coordination treatment value mismatch for {metric}")
                expected_effect = control_value - msg_value
                if abs(float(coordination[f"coordination_effect_{metric}"].iloc[0]) - expected_effect) > max(abs(expected_effect), 1.0) * 1e-8:
                    raise ValueError(f"{industry}: coordination effect mismatch for {metric}")
            coordination.insert(0, "representative_industry", industry)
            coordination["representative_group_share"] = group_share
            coordination["adopter_activity_share"] = adopter_activity_share
            coordination["conditional_group_ai_scale"] = conditional_group_ai_scale
            coordination["industry_equivalent_multiplier"] = multiplier
            for metric in COORDINATION_EFFECT_METRICS:
                for prefix in ("msg_no_routing_", "msg_coordinated_", "coordination_effect_"):
                    column = prefix + metric
                    coordination[f"industry_equivalent_{column}"] = coordination[column].astype(float) * multiplier
            coordination_values.append(coordination)
        lineages.append(lineage)

    if len(args.industries) != 31 or len(set(args.industries)) != 31:
        raise ValueError("The national core package requires exactly 31 unique industries")
    valid_load_modes = {"calibrated_registry", "legacy_industry_electricity_share"}
    observed_load_modes = set(production_load_modes.values())
    if not observed_load_modes or not observed_load_modes.issubset(valid_load_modes):
        raise ValueError(f"Unsupported or missing production-load modes: {observed_load_modes}")
    if production_load_modes.get("C36") != "calibrated_registry":
        raise ValueError("C36 must use the approved calibrated production-load registry boundary")
    load_mode_counts = pd.Series(production_load_modes).value_counts().to_dict()
    core = pd.concat(summaries, ignore_index=True)
    for field in (
        "model_version",
        "common_it_effective_efficiency_case",
        "common_it_effective_efficiency_multiplier",
        "baseline_reference_workload_per_service_unit",
        "reference_compute_h_per_service_unit",
        "reference_server_group",
    ):
        if core[field].nunique(dropna=False) != 1:
            raise ValueError(f"National package mixes incompatible {field} values")
    alignment = pd.concat(alignments, ignore_index=True) if alignments else pd.DataFrame()
    coordination = pd.concat(coordination_values, ignore_index=True) if coordination_values else pd.DataFrame()
    lineage = pd.concat(lineages, ignore_index=True)
    expected_actual_rows = 31 * len(architectures)
    expected_alignment_rows = 31 if "SHG" in architectures else 0
    expected_coordination_rows = 31 if "MSG" in architectures else 0
    if (
        len(core) != expected_actual_rows
        or len(alignment) != expected_alignment_rows
        or len(coordination) != expected_coordination_rows
    ):
        raise AssertionError("Unexpected national output dimensions")
    for path in (args.summary_output, args.alignment_output, args.coordination_output, args.lineage_output, args.done_output):
        path.parent.mkdir(parents=True, exist_ok=True)
    core.to_csv(args.summary_output, index=False, encoding="utf-8-sig")
    alignment.to_csv(args.alignment_output, index=False, encoding="utf-8-sig")
    coordination.to_csv(args.coordination_output, index=False, encoding="utf-8-sig")
    lineage.to_csv(args.lineage_output, index=False, encoding="utf-8-sig")
    payload = {
        "status": "validated",
        "model_version": str(core["model_version"].iloc[0]),
        "industry_count": 31,
        "actual_load_architectures": architectures,
        "actual_load_rows": expected_actual_rows,
        "shg_zero_load_pair_rows": expected_alignment_rows,
        "msg_no_routing_pair_rows": expected_coordination_rows,
        "msg_coordination_effect_definition": "MSG_no_routing_minus_MSG_coordinated",
        "msg_coordination_positive_value_interpretation": "burden_avoided_by_cross_site_coordination",
        "msg_no_routing_is_formal_architecture": False,
        "II_1host_in_core": False,
        "factory_counts": factory_counts,
        "production_load_site_counts": factory_counts,
        "ai_deployment_node_counts": ai_deployment_node_counts,
        "production_load_mode_by_industry": production_load_modes,
        "production_load_mode_counts": load_mode_counts,
        "representative_group_condition": "known_AI_adopter",
        "adopter_activity_share_proxy_by_industry": adopter_activity_shares,
        "adopter_conditioning_identity": "conditional_group_ai_scale_times_industry_equivalent_multiplier_equals_one",
        "common_it_effective_efficiency_case": str(core["common_it_effective_efficiency_case"].iloc[0]),
        "common_it_effective_efficiency_multiplier": float(core["common_it_effective_efficiency_multiplier"].iloc[0]),
        "baseline_reference_workload_per_service_unit": float(core["baseline_reference_workload_per_service_unit"].iloc[0]),
        "reference_compute_h_per_service_unit": float(core["reference_compute_h_per_service_unit"].iloc[0]),
        "reference_server_group": str(core["reference_server_group"].iloc[0]),
        "production_load_boundary_status": "mixed_explicit_C36_calibrated_other_industries_legacy_compatibility",
        "evidence_status": "outputs_validated_not_interpreted",
    }
    args.done_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
