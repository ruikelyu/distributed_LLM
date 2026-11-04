#!/usr/bin/env python3
"""Build a controlled RQ1 infrastructure interpretation from validated outputs.

Purpose: Join national equal-service additional-interconnection comparisons with
the weighted modeled-node and external facility/campus capacity distributions.
Workflow status: Active RQ1 controlled-interpretation generator.
Scientific boundary: National aggregate capacity relief and node-scale
distributions are separate estimands. LDC_AGGREGATE is not a physical site and
the Epoch reference is not a China-specific equal-service comparator.
Inputs: YAML-selected defaults, validated national capacity comparison, validated
node distribution and histogram, and their completion markers.
Outputs: Aggregate and node-scale CSV summaries, a bounded Markdown review, and
a machine-readable candidate marker.
Key assumptions: All distributed and LDC aggregate cases provide equal effective
service; modeled node proportions use registered representative weights.
Explicit exclusions: Water, floor, land, costs, grid equipment, investment,
projects, schedules, maximum-node, percentile, Top-k, HHI, and effective-node
count claims.
Validation/tests: Version, hashes, status markers, architecture coverage, equal
service, aggregation identities, common capacity bins, and probability sums.
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
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/rq1_infrastructure_summary_v1.yaml"
SEMVER = re.compile(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_contract(
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, Path]:
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("RQ1 interpretation schema_version must equal 1")
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    if not SEMVER.fullmatch(model_version):
        raise ValueError("defaults model_version must use vMAJOR.MINOR.PATCH")
    node_config_path = project_path(settings["node_distribution_config"])
    node_settings = yaml.safe_load(node_config_path.read_text(encoding="utf-8"))
    results_root = project_path(defaults["paths"]["results_root"])
    return settings, defaults, node_settings, model_version, results_root


def source_paths(
    settings: dict[str, Any], model_version: str, results_root: Path
) -> dict[str, Path]:
    sources = settings["sources"]
    aggregate_root = (
        results_root / sources["aggregate_comparison_subdirectory"] / model_version
    )
    node_root = results_root / model_version / sources["node_distribution_subdirectory"]
    return {
        "aggregate_table": aggregate_root / sources["aggregate_comparison_filename"],
        "aggregate_marker": aggregate_root / sources["aggregate_validation_filename"],
        "node_table": node_root / sources["node_data_filename"],
        "node_histogram": node_root / sources["node_histogram_filename"],
        "node_marker": node_root / sources["node_validation_filename"],
    }


def validate_sources(
    settings: dict[str, Any],
    node_settings: dict[str, Any],
    model_version: str,
    paths: dict[str, Path],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing RQ1 evidence: " + ", ".join(missing))
    aggregate_marker = json.loads(paths["aggregate_marker"].read_text(encoding="utf-8"))
    node_marker = json.loads(paths["node_marker"].read_text(encoding="utf-8"))
    if aggregate_marker.get("status") != "validated":
        raise ValueError("aggregate comparison is not validated")
    if node_marker.get("status") != "validated":
        raise ValueError("node distribution is not validated")
    if {
        aggregate_marker.get("model_version"),
        node_marker.get("model_version"),
    } != {model_version}:
        raise ValueError("RQ1 source model_version differs from defaults YAML")
    if aggregate_marker.get("centralized_capacity_is_one_physical_site") is not False:
        raise ValueError("aggregate source permits a one-physical-site LDC interpretation")
    if aggregate_marker.get("equal_service_verified") is not True:
        raise ValueError("aggregate source lacks equal-service validation")
    if node_marker.get("forbidden_metrics_not_emitted") != settings["claim_boundaries"][
        "forbidden_metrics"
    ]:
        raise ValueError("node source forbidden-metric boundary differs from RQ1 contract")
    main_case = str(node_settings["ldc_empirical_reference"]["main_case"])
    marker_reference = node_marker.get("ldc_empirical_reference", {})
    if marker_reference.get("main_case") != main_case:
        raise ValueError("node reference main case differs from its YAML")
    if marker_reference.get("equal_service_comparator") is not False:
        raise ValueError("external facility reference cannot be an equal-service comparator")
    if marker_reference.get("china_specific") is not False:
        raise ValueError("external facility reference cannot be labeled China-specific")

    aggregate = pd.read_csv(paths["aggregate_table"], encoding="utf-8-sig")
    nodes = pd.read_csv(paths["node_table"], encoding="utf-8-sig")
    histogram = pd.read_csv(paths["node_histogram"], encoding="utf-8-sig")
    node_outputs = node_marker.get("outputs", {})
    if node_outputs.get("node_data", {}).get("sha256") != sha256(paths["node_table"]):
        raise ValueError("node table hash differs from validation marker")
    if node_outputs.get("histogram_data", {}).get("sha256") != sha256(
        paths["node_histogram"]
    ):
        raise ValueError("node histogram hash differs from validation marker")
    if len(nodes) != int(node_outputs["node_data"]["rows"]):
        raise ValueError("node table row count differs from validation marker")
    if len(histogram) != int(node_outputs["histogram_data"]["rows"]):
        raise ValueError("node histogram row count differs from validation marker")
    return aggregate, nodes, aggregate_marker, node_marker


def build_aggregate_summary(
    settings: dict[str, Any], model_version: str, aggregate: pd.DataFrame
) -> pd.DataFrame:
    architectures = [str(value) for value in settings["distributed_architectures"]]
    required = {
        "scenario",
        "architecture_national_incremental_grid_expansion_mw",
        "ldc_aggregate_incremental_grid_expansion_mw",
        "capacity_difference_vs_ldc_aggregate_mw",
        "capacity_difference_vs_ldc_aggregate_fraction",
        "lower_screening_capacity_than_ldc_aggregate",
    }
    if not required.issubset(aggregate.columns):
        raise ValueError("aggregate comparison lacks required columns")
    if len(aggregate) != len(architectures) or set(aggregate["scenario"]) != set(
        architectures
    ):
        raise ValueError("aggregate comparison lacks exact PF/SHG/MSG coverage")
    tolerance = float(settings["validation"]["absolute_tolerance_mw"])
    calculated = (
        aggregate["ldc_aggregate_incremental_grid_expansion_mw"]
        - aggregate["architecture_national_incremental_grid_expansion_mw"]
    )
    if not np.allclose(
        calculated,
        aggregate["capacity_difference_vs_ldc_aggregate_mw"],
        rtol=float(settings["validation"]["relative_tolerance"]),
        atol=tolerance,
    ):
        raise ValueError("aggregate capacity differences do not reconcile")
    fractions = calculated / aggregate["ldc_aggregate_incremental_grid_expansion_mw"]
    if not np.allclose(
        fractions,
        aggregate["capacity_difference_vs_ldc_aggregate_fraction"],
        rtol=float(settings["validation"]["relative_tolerance"]),
        atol=1e-10,
    ):
        raise ValueError("aggregate capacity fractions do not reconcile")
    if not aggregate["lower_screening_capacity_than_ldc_aggregate"].astype(bool).all():
        raise ValueError("at least one distributed case is not below LDC_AGGREGATE")
    result = aggregate.copy()
    result.insert(0, "model_version", model_version)
    result.insert(1, "analysis_version", settings["analysis_version"])
    result["centralized_architecture"] = settings["centralized_architecture"]
    result["equal_service_verified"] = True
    result["centralized_capacity_is_one_physical_site"] = False
    result["claim_boundary"] = settings["claim_boundaries"]["aggregate"]
    return result.sort_values(
        "scenario", key=lambda values: values.map({name: i for i, name in enumerate(architectures)})
    ).reset_index(drop=True)


def build_node_scale_summary(
    settings: dict[str, Any],
    node_settings: dict[str, Any],
    model_version: str,
    nodes: pd.DataFrame,
) -> pd.DataFrame:
    architectures = [str(value) for value in settings["distributed_architectures"]]
    reference = str(settings["empirical_reference_architecture"])
    main_case = str(node_settings["ldc_empirical_reference"]["main_case"])
    distributed = nodes.loc[
        nodes["architecture"].isin(architectures)
        & nodes["capacity_case"].eq("modeled_main")
    ].copy()
    empirical = nodes.loc[
        nodes["architecture"].eq(reference)
        & nodes["capacity_case"].eq(main_case)
    ].copy()
    expected_epoch = int(settings["validation"]["expected_epoch_record_count"])
    if set(distributed["architecture"]) != set(architectures):
        raise ValueError("node table lacks PF/SHG/MSG distributions")
    if len(empirical) != expected_epoch:
        raise ValueError("unexpected Epoch facility/campus record count")
    if empirical["equal_service_distribution"].astype(bool).any():
        raise ValueError("Epoch reference cannot be labeled equal-service")
    if empirical["china_specific_empirical_distribution"].astype(bool).any():
        raise ValueError("Epoch reference cannot be labeled China-specific")
    selected = pd.concat([distributed, empirical], ignore_index=True)
    if set(selected["model_version"].astype(str)) != {model_version}:
        raise ValueError("node table model_version differs from defaults YAML")
    if selected["observation_weight"].le(0).any():
        raise ValueError("node distribution contains nonpositive observation weight")
    capacity = selected["incremental_interconnection_capacity_mw"].astype(float)
    if capacity.lt(0).any() or not np.isfinite(capacity).all():
        raise ValueError("node distribution contains invalid capacity")

    bin_contracts = settings["node_scale_bins"]
    rows: list[dict[str, Any]] = []
    for architecture, group in selected.groupby("architecture", sort=False):
        total_weight = float(group["observation_weight"].sum())
        assigned = pd.Series(False, index=group.index)
        for order, contract in enumerate(bin_contracts):
            if contract.get("kind") == "zero":
                mask = group["incremental_interconnection_capacity_mw"].eq(0)
            else:
                lower = float(contract["lower_mw"])
                upper = float(contract["upper_mw"])
                mask = group["incremental_interconnection_capacity_mw"].ge(lower)
                if lower == 0:
                    mask &= group["incremental_interconnection_capacity_mw"].gt(0)
                mask &= group["incremental_interconnection_capacity_mw"].lt(upper)
            if (assigned & mask).any():
                raise ValueError(f"{architecture}: overlapping node-scale bins")
            assigned |= mask
            rows.append(
                {
                    "model_version": model_version,
                    "analysis_version": settings["analysis_version"],
                    "architecture": architecture,
                    "capacity_case": (
                        "modeled_main" if architecture in architectures else main_case
                    ),
                    "population_kind": group["population_kind"].iloc[0],
                    "statistical_unit": group["statistical_unit"].iloc[0],
                    "bin_order": order,
                    "coarse_bin_id": contract["id"],
                    "coarse_bin_label": contract["label"],
                    "record_count": int(mask.sum()),
                    "weighted_node_count": float(group.loc[mask, "observation_weight"].sum()),
                    "node_proportion": float(group.loc[mask, "observation_weight"].sum())
                    / total_weight,
                    "equal_service_distribution": bool(
                        group["equal_service_distribution"].astype(bool).all()
                    ),
                    "china_specific_empirical_distribution": bool(
                        group["china_specific_empirical_distribution"].astype(bool).all()
                    ),
                    "claim_boundary": (
                        settings["claim_boundaries"]["node_distribution"]
                        if architecture in architectures
                        else settings["claim_boundaries"]["empirical_reference"]
                    ),
                }
            )
        if not assigned.all():
            raise ValueError(f"{architecture}: at least one node falls outside coarse bins")
    result = pd.DataFrame(rows)
    sums = result.groupby("architecture")["node_proportion"].sum()
    if not np.allclose(sums, 1.0, rtol=0, atol=1e-12):
        raise ValueError("coarse node-scale proportions do not sum to one")
    return result


def share(summary: pd.DataFrame, architecture: str, bins: list[str]) -> float:
    selected = summary.loc[
        summary["architecture"].eq(architecture)
        & summary["coarse_bin_id"].isin(bins),
        "node_proportion",
    ]
    return float(selected.sum())


def build_markdown(
    settings: dict[str, Any],
    model_version: str,
    aggregate: pd.DataFrame,
    node_summary: pd.DataFrame,
    paths: dict[str, Path],
) -> str:
    approved = settings["interpretation_status"] == (
        "author_approved_for_figure_and_manuscript_migration"
    )
    status_line = (
        "**Status: approved by the authors for the figure and later manuscript migration; the current manuscript is not yet synchronized.**"
        if approved
        else "**Status: candidate interpretation pending author approval; must not be treated as an authorized manuscript claim.**"
    )
    decision_heading = "Migration status" if approved else "Author decision gate"
    results_heading = "Author-approved Results wording for migration" if approved else "Candidate Results wording"
    decision_text = (
        "The aggregate results, node-scale results, and their boundaries above are approved by the authors and may enter the Figure 3 design; "
        "Methods, Results, Discussion, and captions must still be synchronized in the later coordinated manuscript migration."
        if approved
        else "Once approved, the aggregate and node-scale results above may enter the Figure 3 design, with boundaries synchronized in Methods, Results, Discussion, and captions; "
        "until approval they remain a candidate interpretation."
    )
    aggregate_rows = []
    indexed = aggregate.set_index("scenario")
    for architecture in settings["distributed_architectures"]:
        item = indexed.loc[architecture]
        aggregate_rows.append(
            f"| {architecture} | {item.architecture_national_incremental_grid_expansion_mw:.1f} | "
            f"{item.ldc_aggregate_incremental_grid_expansion_mw:.1f} | "
            f"{item.capacity_difference_vs_ldc_aggregate_mw:.1f} | "
            f"{100 * item.capacity_difference_vs_ldc_aggregate_fraction:.1f}% |"
        )
    reference = str(settings["empirical_reference_architecture"])
    node_rows = []
    for architecture in [*settings["distributed_architectures"], reference]:
        node_rows.append(
            "| {} | {:.1f}% | {:.1f}% | {:.1f}% | {:.1f}% | {:.1f}% | {:.1f}% | {:.1f}% |".format(
                architecture,
                100 * share(node_summary, architecture, ["exact_zero"]),
                100 * share(node_summary, architecture, ["positive_below_0p1_mw"]),
                100 * share(node_summary, architecture, ["0p1_to_1_mw"]),
                100 * share(node_summary, architecture, ["1_to_10_mw"]),
                100 * share(node_summary, architecture, ["10_to_100_mw"]),
                100 * share(node_summary, architecture, ["100_to_1000_mw"]),
                100 * share(node_summary, architecture, ["1000_to_10000_mw"]),
            )
        )
    pf = indexed.loc["PF"]
    shg = indexed.loc["SHG"]
    msg = indexed.loc["MSG"]
    return (
        f"# RQ1 grid infrastructure: controlled interpretation review ({model_version})\n\n"
        f"{status_line}\n\n"
        "## 1. Evidence scope\n\n"
        f"National totals come from `{display_path(paths['aggregate_table'])}`; node scale comes from "
        f"`{display_path(paths['node_table'])}` and its common bins. The former compares national incremental "
        "interconnection capacity under the same effective AI service; the latter compares the capacity scale of weighted modeled deployment nodes with internationally published facility/campus records. "
        "The two answer different questions, and the external facility distribution must not be treated as an equal-service LDC node configuration.\n\n"
        "## 2. National incremental interconnection capacity\n\n"
        "| Architecture | Architecture capacity (MW) | LDC aggregate capacity (MW) | Difference vs. LDC (MW) | Ratio vs. LDC |\n"
        "|---|---:|---:|---:|---:|\n"
        + "\n".join(aggregate_rows)
        + "\n\nAll three distributed scenarios provide the same effective AI service as the LDC aggregate counterfactual. The LDC value is a logical portfolio of new capacity, not one physical data center or interconnection point.\n\n"
        "## 3. Node-scale distribution\n\n"
        "| Distribution | 0 MW | (0,0.1) MW | [0.1,1) MW | [1,10) MW | [10,100) MW | [100,1000) MW | [1000,10000) MW |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
        + "\n".join(node_rows)
        + "\n\nPF, SHG, and MSG shares use registered representative-node weights, not an observed sample of national factory interconnection points. "
        "The Epoch primary reference contains 69 internationally published AI facility or campus records, converted with a peak facility power / current IT power factor of 1.20; "
        "these records are not independent grid interconnection points, nor a China-specific or equal-service LDC configuration.\n\n"
        f"## 4. {results_heading}\n\n"
        f"Under the {model_version} main scenario and the same effective-AI-service boundary, the national incremental interconnection capacity required by PF, SHG, and MSG is "
        f"{pf.architecture_national_incremental_grid_expansion_mw:.1f}, "
        f"{shg.architecture_national_incremental_grid_expansion_mw:.1f}, and "
        f"{msg.architecture_national_incremental_grid_expansion_mw:.1f} MW, respectively, all below the LDC aggregate counterfactual's "
        f"{pf.ldc_aggregate_incremental_grid_expansion_mw:.1f} MW; the corresponding differences are "
        f"{pf.capacity_difference_vs_ldc_aggregate_mw:.1f} MW ("
        f"{100 * pf.capacity_difference_vs_ldc_aggregate_fraction:.1f}%), "
        f"{shg.capacity_difference_vs_ldc_aggregate_mw:.1f} MW ("
        f"{100 * shg.capacity_difference_vs_ldc_aggregate_fraction:.1f}%), and "
        f"{msg.capacity_difference_vs_ldc_aggregate_mw:.1f} MW ("
        f"{100 * msg.capacity_difference_vs_ldc_aggregate_fraction:.1f}%). "
        "Beyond the national total, the deployment architecture also changes the node scale at which capacity appears. In the common bins, "
        f"{100 * share(node_summary, 'PF', ['positive_below_0p1_mw']):.1f}% of PF node weight lies below 0.1 MW, "
        f"{100 * share(node_summary, 'SHG', ['0p1_to_1_mw']):.1f}% of SHG node weight lies in 0.1--1 MW, and "
        f"{100 * share(node_summary, 'MSG', ['exact_zero']):.1f}% of MSG node weight requires no new capacity, with a further "
        f"{100 * share(node_summary, 'MSG', ['positive_below_0p1_mw']):.1f}% in 0--0.1 MW. "
        "As a scale reference, all 69 Epoch international facility/campus records lie above 10 MW under the primary conversion, with "
        f"{100 * share(node_summary, reference, ['100_to_1000_mw']):.1f}% in 100--1000 MW. "
        "This external comparison shows that the two distributions occupy different capacity scales, but it is not a China-specific, equal-service, or same-statistical-unit LDC siting comparison.\n\n"
        "## 5. Required accompanying boundaries\n\n"
        "1. Incremental interconnection capacity is a site-side continuous MW screening quantity holding unobserved existing headroom fixed; it is not grid equipment, investment, projects, or construction timing.\n"
        "2. `LDC_AGGREGATE` is a logical new-capacity portfolio carrying the same national service; it does not correspond to one physical facility or interconnection point.\n"
        "3. PF, SHG, and MSG node distributions come from weighted representative nodes, not a probability sample of national factory nodes.\n"
        "4. The statistical unit of the Epoch records is a published facility or campus, not guaranteed to be an independent grid interconnection point; the sample is an international reference, not a China-specific distribution.\n"
        "5. The Epoch distribution is not normalized to this study's national service volume or total capacity and cannot be used to infer the number or spatial configuration of LDC physical sites.\n"
        "6. The largest modeled node, P50/P95, Top-k, HHI, and effective node count are not reported at this stage.\n"
        "7. Water, facility floor area, and offsite land are not yet part of this interpretation.\n\n"
        f"## 6. {decision_heading}\n\n"
        f"{decision_text}\n"
    )


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings, _, node_settings, model_version, results_root = load_contract(config_path)
    paths = source_paths(settings, model_version, results_root)
    aggregate_source, nodes, aggregate_marker, node_marker = validate_sources(
        settings, node_settings, model_version, paths
    )
    aggregate = build_aggregate_summary(settings, model_version, aggregate_source)
    node_summary = build_node_scale_summary(
        settings, node_settings, model_version, nodes
    )
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else results_root / model_version / settings["outputs"]["subdirectory"]
    )
    review = build_markdown(
        settings, model_version, aggregate, node_summary, paths
    )
    payload = {
        "status": settings["interpretation_status"],
        "model_version": model_version,
        "analysis_version": settings["analysis_version"],
        "author_approval": settings.get("author_approval"),
        "configuration": {
            "path": display_path(config_path),
            "sha256": sha256(config_path),
        },
        "source_files": {
            key: {"path": display_path(path), "sha256": sha256(path)}
            for key, path in paths.items()
        },
        "source_status": {
            "aggregate": aggregate_marker["status"],
            "node_distribution": node_marker["status"],
        },
        "equal_service_verified": True,
        "centralized_capacity_is_one_physical_site": False,
        "aggregate_row_count": len(aggregate),
        "node_scale_row_count": len(node_summary),
        "node_scale_group_count": int(node_summary["architecture"].nunique()),
        "node_scale_proportions_sum_to_one": True,
        "claim_boundaries": settings["claim_boundaries"],
        "evidence_status": settings["evidence_status"],
        "aggregate_summary": aggregate.to_dict(orient="records"),
    }
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": payload["status"],
                    "model_version": model_version,
                    "aggregate_summary": payload["aggregate_summary"],
                    "node_scale_row_count": len(node_summary),
                    "node_scale_group_count": payload["node_scale_group_count"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    output_root.mkdir(parents=True, exist_ok=True)
    aggregate_path = output_root / settings["outputs"]["aggregate_summary"]
    node_path = output_root / settings["outputs"]["node_scale_summary"]
    review_path = output_root / settings["outputs"]["interpretation_review"]
    marker_path = output_root / settings["outputs"]["validation"]
    aggregate.to_csv(aggregate_path, index=False, encoding="utf-8-sig")
    node_summary.to_csv(node_path, index=False, encoding="utf-8-sig")
    review_path.write_text(review, encoding="utf-8")
    payload["outputs"] = {
        "aggregate_summary": {
            "path": display_path(aggregate_path),
            "sha256": sha256(aggregate_path),
            "rows": len(aggregate),
        },
        "node_scale_summary": {
            "path": display_path(node_path),
            "sha256": sha256(node_path),
            "rows": len(node_summary),
        },
        "interpretation_review": {
            "path": display_path(review_path),
            "sha256": sha256(review_path),
        },
    }
    marker_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "model_version": model_version,
                "output_root": str(output_root),
                "aggregate_rows": len(aggregate),
                "node_scale_rows": len(node_summary),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
