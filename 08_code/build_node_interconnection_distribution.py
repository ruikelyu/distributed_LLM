#!/usr/bin/env python3
"""Build the weighted modeled-node and empirical LDC capacity distributions.

Purpose: Produce the RQ1 node-scale interconnection-capacity evidence table and
common-bin histogram without changing or re-solving the physical model.
Workflow status: Active infrastructure-first postprocessor.
Scientific boundary: PF/SHG/MSG are weighted modeled-node distributions. Epoch
records are an international facility/campus scale reference, not a China-specific
or equal-service allocation of the modeled LDC aggregate.
Inputs: Analysis/default YAML files, validated 31-industry core outputs, and the
frozen Epoch current-IT-power snapshot plus lineage manifest.
Outputs: Node-level capacity records, common-bin weighted proportions, and a
validation marker.
Key assumptions: Representative-node weights reconstruct the registered national
population; Epoch current IT power is converted with YAML-registered multipliers.
Explicit exclusions: No node extrema or percentiles, grid-equipment inference,
China-specific LDC allocation, or normalization to modeled national capacity.
Validation/tests: Version/config agreement, source checksums, architecture and
industry coverage, national-capacity reconciliation, shared-bin coverage, and
histogram-proportion identities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/node_interconnection_distribution_v1.yaml"
SEMVER = re.compile(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--output-root",
        type=Path,
        help="Optional audit-only output directory; model_version still comes from YAML.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run every input and reconciliation check without writing result files.",
    )
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_contract(settings: dict[str, Any]) -> tuple[dict[str, Any], str, Path, Path]:
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    if not SEMVER.fullmatch(model_version):
        raise ValueError("defaults_config model_version must use vMAJOR.MINOR.PATCH")
    results_root = project_path(defaults["paths"]["results_root"])
    version_root = results_root / model_version
    return defaults, model_version, results_root, version_root


def validate_snapshot(
    settings: dict[str, Any], model_version: str
) -> tuple[pd.DataFrame, dict[str, Any]]:
    source = settings["source"]
    snapshot_path = project_path(source["processed_snapshot"])
    manifest_path = project_path(source["snapshot_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "validated_source_snapshot":
        raise ValueError("Epoch lineage manifest is not validated")
    if manifest.get("model_version") != model_version:
        raise ValueError("Epoch processed snapshot is bound to a different model_version")
    identity = manifest.get("diagnostics", {})
    if int(identity.get("unresolved_address_collision_group_count", -1)) != 0:
        raise ValueError("Epoch snapshot has unresolved same-address record identities")
    if int(identity.get("same_address_collision_group_count", -1)) != int(
        identity.get("registered_distinct_record_group_count", -2)
    ):
        raise ValueError("Epoch same-address collisions are not fully registered")
    for metadata in manifest["raw_files"].values():
        path = project_path(metadata["path"])
        if sha256(path) != metadata["sha256"]:
            raise ValueError(f"Raw Epoch source checksum mismatch: {path}")
    if sha256(snapshot_path) != manifest["processed_snapshot"]["sha256"]:
        raise ValueError("Processed Epoch snapshot checksum mismatch")
    snapshot = pd.read_csv(snapshot_path, encoding="utf-8-sig")
    if set(snapshot["model_version"].astype(str)) != {model_version}:
        raise ValueError("Processed Epoch snapshot contains an unexpected model_version")
    if snapshot["facility_name"].duplicated().any():
        raise ValueError("Processed Epoch snapshot contains duplicate facility records")
    if not snapshot["current_it_power_mw"].gt(0).all():
        raise ValueError("Processed Epoch snapshot must contain only positive current IT power")
    return snapshot, manifest


def distributed_node_rows(
    defaults: dict[str, Any],
    settings: dict[str, Any],
    model_version: str,
    version_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    contract = settings["distributed_model"]
    architectures = [str(value) for value in contract["architectures"]]
    industries = [str(value) for value in defaults["selected_industries"]]
    if len(industries) != 31 or architectures != ["PF", "SHG", "MSG"]:
        raise ValueError("Node distribution requires the registered 31-industry PF/SHG/MSG core")
    core_root = version_root / "result" / contract["result_subdirectory"]
    national_path = core_root / "national/core_scenarios.csv"
    validation_path = core_root / "national/validated.done.json"
    national = pd.read_csv(national_path, encoding="utf-8-sig")
    marker = json.loads(validation_path.read_text(encoding="utf-8"))
    if marker.get("status") != "validated" or marker.get("model_version") != model_version:
        raise ValueError("National group core is not validated for the active YAML model_version")
    if set(marker.get("actual_load_architectures", [])) != set(architectures):
        raise ValueError("National group-core architectures do not match the distribution contract")
    national = national.loc[
        national["base_load_case"].eq(contract["base_load_case"])
    ].copy()
    if len(national) != 31 * len(architectures):
        raise ValueError("National group core lacks complete industry-architecture coverage")

    negative_tolerance = float(contract["negative_solver_tolerance_mw"])
    rows: list[dict[str, Any]] = []
    reconciliation: dict[str, Any] = {}
    for industry in industries:
        summary = pd.read_csv(core_root / industry / "summary.csv", encoding="utf-8-sig")
        hourly = pd.read_csv(core_root / industry / "hourly.csv", encoding="utf-8-sig")
        if set(summary["model_version"].astype(str)) != {model_version}:
            raise ValueError(f"{industry}: summary model_version differs from YAML")
        actual_summary = summary.loc[
            summary["base_load_case"].eq(contract["base_load_case"])
            & summary["architecture"].isin(architectures)
        ]
        if set(actual_summary["architecture"]) != set(architectures):
            raise ValueError(f"{industry}: incomplete PF/SHG/MSG summary coverage")
        multiplier_values = actual_summary["industry_equivalent_multiplier"].unique()
        if len(multiplier_values) != 1:
            raise ValueError(f"{industry}: architectures use different reconstruction multipliers")
        industry_multiplier = float(multiplier_values[0])
        for architecture in architectures:
            selected = hourly.loc[
                hourly["architecture"].eq(architecture)
                & hourly["base_load_case"].eq(contract["base_load_case"])
            ].copy()
            if selected.empty:
                raise ValueError(f"{industry}/{architecture}: missing hourly records")
            for node_id, node in selected.groupby("factory_id", sort=True):
                represented = node["represented_factory_count"].unique()
                if len(represented) != 1 or float(represented[0]) <= 0:
                    raise ValueError(
                        f"{industry}/{architecture}/{node_id}: invalid representative weight"
                    )
                represented_count = float(represented[0])
                aggregation_factor = represented_count if architecture == "PF" else 1.0
                base_peak = float(node["base_load_mw"].max()) / aggregation_factor
                grid_peak = float(node["grid_import_mw"].max()) / aggregation_factor
                raw_increment = grid_peak - base_peak
                if raw_increment < -negative_tolerance:
                    raise ValueError(
                        f"{industry}/{architecture}/{node_id}: material negative peak increment"
                    )
                increment = max(raw_increment, 0.0)
                within_group_weight = represented_count if architecture == "PF" else 1.0
                observation_weight = within_group_weight * industry_multiplier
                rows.append(
                    {
                        "model_version": model_version,
                        "analysis_version": settings["analysis_version"],
                        "architecture": architecture,
                        "architecture_display_label": architecture,
                        "capacity_case": "modeled_main",
                        "population_kind": "weighted_modeled_deployment_nodes",
                        "statistical_unit": "modeled_physical_AI_deployment_node",
                        "industry": industry,
                        "node_id": f"{industry}/{node_id}",
                        "source_record_name": "",
                        "incremental_interconnection_capacity_mw": increment,
                        "current_it_power_mw": np.nan,
                        "peak_facility_to_it_multiplier": np.nan,
                        "represented_node_weight_within_group": within_group_weight,
                        "industry_equivalent_multiplier": industry_multiplier,
                        "observation_weight": observation_weight,
                        "weighted_capacity_contribution_mw": increment
                        * observation_weight,
                        "is_zero_capacity": bool(increment == 0.0),
                        "equal_service_distribution": True,
                        "china_specific_empirical_distribution": False,
                    }
                )

    nodes = pd.DataFrame(rows)
    national_targets = national.set_index(["industry", "architecture"])[
        "industry_equivalent_sum_incremental_grid_peak_mw"
    ]
    observed = nodes.groupby(["industry", "architecture"])[
        "weighted_capacity_contribution_mw"
    ].sum()
    observed = observed.reindex(national_targets.index)
    differences = observed - national_targets
    tolerance = (
        national_targets.abs()
        * float(contract["reconciliation_relative_tolerance"])
        + float(contract["reconciliation_absolute_tolerance_mw"])
    )
    if observed.isna().any() or not differences.abs().le(tolerance).all():
        failed = differences.loc[differences.abs().gt(tolerance)].to_dict()
        raise ValueError(f"Node distribution does not reconcile to national capacity: {failed}")
    for architecture in architectures:
        selected = nodes.loc[nodes["architecture"].eq(architecture)]
        reconciliation[architecture] = {
            "modeled_record_count": int(len(selected)),
            "weighted_site_count": float(selected["observation_weight"].sum()),
            "zero_record_count": int(selected["is_zero_capacity"].sum()),
            "zero_weighted_site_count": float(
                selected.loc[selected["is_zero_capacity"], "observation_weight"].sum()
            ),
            "weighted_capacity_total_mw": float(
                selected["weighted_capacity_contribution_mw"].sum()
            ),
        }
    return nodes, reconciliation


def ldc_reference_rows(
    snapshot: pd.DataFrame, settings: dict[str, Any], model_version: str
) -> pd.DataFrame:
    contract = settings["ldc_empirical_reference"]
    rows: list[dict[str, Any]] = []
    for case, multiplier_value in contract["cases"].items():
        multiplier = float(multiplier_value)
        if multiplier <= 1.0:
            raise ValueError("Peak facility-to-IT multipliers must exceed one")
        for row in snapshot.itertuples(index=False):
            capacity = float(row.current_it_power_mw) * multiplier
            rows.append(
                {
                    "model_version": model_version,
                    "analysis_version": settings["analysis_version"],
                    "architecture": contract["architecture_code"],
                    "architecture_display_label": "LDC empirical facility/campus reference",
                    "capacity_case": case,
                    "population_kind": "international_empirical_facility_campus_records",
                    "statistical_unit": contract["statistical_unit"],
                    "industry": "",
                    "node_id": f"Epoch/{row.facility_name}",
                    "source_record_name": row.facility_name,
                    "incremental_interconnection_capacity_mw": capacity,
                    "current_it_power_mw": float(row.current_it_power_mw),
                    "peak_facility_to_it_multiplier": multiplier,
                    "represented_node_weight_within_group": 1.0,
                    "industry_equivalent_multiplier": 1.0,
                    "observation_weight": 1.0,
                    "weighted_capacity_contribution_mw": capacity,
                    "is_zero_capacity": False,
                    "equal_service_distribution": bool(contract["equal_service_comparator"]),
                    "china_specific_empirical_distribution": bool(contract["china_specific"]),
                }
            )
    return pd.DataFrame(rows)


def build_histogram(nodes: pd.DataFrame, settings: dict[str, Any]) -> pd.DataFrame:
    histogram = settings["histogram"]
    edges = np.asarray(histogram["positive_bin_edges_mw"], dtype=float)
    if len(edges) < 2 or not np.all(np.isfinite(edges)) or not np.all(np.diff(edges) > 0):
        raise ValueError("positive_bin_edges_mw must be finite and strictly increasing")
    if edges[0] <= 0:
        raise ValueError("Positive histogram bins must exclude the separate zero category")
    positive = nodes.loc[nodes["incremental_interconnection_capacity_mw"].gt(0)]
    if positive["incremental_interconnection_capacity_mw"].min() < edges[0]:
        raise ValueError("A positive capacity falls below the first common histogram edge")
    if positive["incremental_interconnection_capacity_mw"].max() >= edges[-1]:
        raise ValueError("A positive capacity reaches or exceeds the last histogram edge")

    rows: list[dict[str, Any]] = []
    group_columns = [
        "model_version",
        "analysis_version",
        "architecture",
        "architecture_display_label",
        "capacity_case",
        "population_kind",
        "statistical_unit",
    ]
    for keys, group in nodes.groupby(group_columns, sort=False, dropna=False):
        common = dict(zip(group_columns, keys))
        total_weight = float(group["observation_weight"].sum())
        zero = group.loc[group["incremental_interconnection_capacity_mw"].eq(0)]
        rows.append(
            {
                **common,
                "bin_order": 0,
                "bin_label": histogram["zero_bin_label"],
                "bin_lower_mw": 0.0,
                "bin_upper_mw": 0.0,
                "is_zero_bin": True,
                "record_count": int(len(zero)),
                "weighted_site_count": float(zero["observation_weight"].sum()),
                "node_proportion": float(zero["observation_weight"].sum())
                / total_weight,
            }
        )
        for index, (lower, upper) in enumerate(zip(edges[:-1], edges[1:]), start=1):
            selected = group.loc[
                group["incremental_interconnection_capacity_mw"].ge(lower)
                & group["incremental_interconnection_capacity_mw"].lt(upper)
            ]
            weight = float(selected["observation_weight"].sum())
            rows.append(
                {
                    **common,
                    "bin_order": index,
                    "bin_label": f"[{lower:g}, {upper:g}) MW",
                    "bin_lower_mw": lower,
                    "bin_upper_mw": upper,
                    "is_zero_bin": False,
                    "record_count": int(len(selected)),
                    "weighted_site_count": weight,
                    "node_proportion": weight / total_weight,
                }
            )
    result = pd.DataFrame(rows)
    proportions = result.groupby(["architecture", "capacity_case"])[
        "node_proportion"
    ].sum()
    if not np.allclose(proportions.to_numpy(dtype=float), 1.0, rtol=0, atol=1e-12):
        raise ValueError("Histogram proportions do not sum to one")
    return result


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    defaults, model_version, _, version_root = load_contract(settings)
    snapshot, manifest = validate_snapshot(settings, model_version)
    distributed, reconciliation = distributed_node_rows(
        defaults, settings, model_version, version_root
    )
    ldc = ldc_reference_rows(snapshot, settings, model_version)
    nodes = pd.concat([distributed, ldc], ignore_index=True)
    histogram = build_histogram(nodes, settings)

    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "validated_check_only",
                    "model_version": model_version,
                    "distributed_node_records": len(distributed),
                    "epoch_reference_records_per_case": len(snapshot),
                    "histogram_rows": len(histogram),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    output_settings = settings["outputs"]
    output_root = (
        args.output_root.resolve()
        if args.output_root is not None
        else version_root / "result" / output_settings["result_subdirectory"]
    )
    output_root.mkdir(parents=True, exist_ok=True)
    node_path = output_root / output_settings["node_data"]
    histogram_path = output_root / output_settings["histogram_data"]
    validation_path = output_root / output_settings["validation"]
    nodes.to_csv(node_path, index=False, encoding="utf-8-sig")
    histogram.to_csv(histogram_path, index=False, encoding="utf-8-sig")

    ldc_contract = settings["ldc_empirical_reference"]
    payload = {
        "status": "validated",
        "model_version": model_version,
        "analysis_version": settings["analysis_version"],
        "configuration": str(config_path.relative_to(PROJECT_ROOT)),
        "version_resolution": "model_version_and_result_root_read_from_defaults_config",
        "architectures": ["PF", "SHG", "MSG"],
        "distributed_reconciliation": reconciliation,
        "epoch_source": {
            "dataset_updated_date": manifest["dataset_updated_date"],
            "access_date": manifest["access_date"],
            "as_of_date": manifest["as_of_date"],
            "positive_facility_campus_records": int(len(snapshot)),
            "same_address_collision_groups": int(
                manifest["diagnostics"]["same_address_collision_group_count"]
            ),
            "registered_distinct_record_groups": int(
                manifest["diagnostics"]["registered_distinct_record_group_count"]
            ),
            "unresolved_address_collision_groups": int(
                manifest["diagnostics"]["unresolved_address_collision_group_count"]
            ),
            "data_centers_sha256": manifest["raw_files"]["data_centers"]["sha256"],
            "timelines_sha256": manifest["raw_files"]["timelines"]["sha256"],
        },
        "ldc_empirical_reference": {
            "architecture_code": ldc_contract["architecture_code"],
            "main_case": ldc_contract["main_case"],
            "peak_facility_to_it_multiplier_cases": ldc_contract["cases"],
            "statistical_unit": ldc_contract["statistical_unit"],
            "equal_service_comparator": False,
            "china_specific": False,
            "normalized_to_modeled_national_service_or_capacity": False,
        },
        "histogram": {
            "zero_capacity_is_separate_bin": True,
            "common_positive_bin_edges_mw": settings["histogram"][
                "positive_bin_edges_mw"
            ],
            "proportions_sum_to_one": True,
        },
        "forbidden_metrics_not_emitted": [
            "maximum_modeled_node_claim",
            "P50_or_P95_claim",
            "top_k_share",
            "HHI",
            "effective_node_count",
        ],
        "claim_boundary": (
            "weighted_modeled_node_distribution_vs_international_empirical_"
            "facility_campus_scale_reference_not_grid_projects_or_equal_service_LDC_sites"
        ),
        "evidence_status": "outputs_validated_not_interpreted",
        "outputs": {
            "node_data": {
                "filename": node_path.name,
                "sha256": sha256(node_path),
                "rows": len(nodes),
            },
            "histogram_data": {
                "filename": histogram_path.name,
                "sha256": sha256(histogram_path),
                "rows": len(histogram),
            },
        },
    }
    validation_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "model_version": model_version,
                "distributed_node_records": len(distributed),
                "epoch_reference_records_per_case": len(snapshot),
                "output": str(output_root),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
