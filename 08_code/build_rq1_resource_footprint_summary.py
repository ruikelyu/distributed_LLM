#!/usr/bin/env python3
"""Build the boundary-corrected RQ1 resource-footprint summary.

Purpose: Convert validated v1.0 PF and equal-service LDC aggregate outputs into
standard water, facility-floor, and off-site-land comparison tables.
Workflow status: Active solver-free, author-approved resource summary.
Scientific boundary: The calculations compare registered scenarios rather than
estimating an architecture-only causal effect or empirical national footprint.
Inputs: YAML contracts plus validated PF/LDC outputs and registered resource
parameters checked by the RQ1 resource pre-rebuild audit.
Outputs: A long-form result table, field-status table, bounded interpretation,
and a hash-bearing approval marker under the YAML-selected model version.
Key assumptions: PF uses an existing-factory-site boundary; LDC_AGGREGATE uses
a logical equal-service greenfield portfolio and project-screening intensities.
Explicit exclusions: SHG/MSG averages, PF new-building estimates, construction
materials, grid-capacity panels, withdrawal/consumption separation, and PUE changes.
Validation/tests: Version and source-marker checks, exact architecture/metric
coverage, energy consistency, selected central-floor case, field semantics, hashes,
deterministic replay, and manuscript-authorization checks.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from audit_rq1_resource_footprint import audit, load_contract, project_path, sha256


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/rq1_resource_footprint_summary_v1.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--replay-check", action="store_true")
    return parser.parse_args()


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_summary_contract(
    config_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], str, Path, dict[str, Path], dict[str, Any]]:
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("RQ1 resource summary schema_version must equal 1")
    if settings.get("figure_authorization") is not True:
        raise ValueError("resource summary lacks author approval for figure use")
    if settings.get("automatic_manuscript_edit") is not False:
        raise ValueError("resource summary cannot authorize automatic manuscript edits")
    if settings.get("author_approval", {}).get("status") != "approved":
        raise ValueError("resource summary lacks author-approval metadata")
    audit_config_path = project_path(settings["audit_config"])
    audit_settings, model_version, results_root, paths = load_contract(audit_config_path)
    audit_report = audit(audit_settings, model_version, paths)
    if audit_report["status"] != "READY_FOR_BOUNDARY_CORRECTED_POSTPROCESSOR_REBUILD":
        raise ValueError("RQ1 resource pre-rebuild audit is not ready")
    if audit_report.get("manuscript_authorization") is not False:
        raise ValueError("pre-rebuild audit improperly authorizes manuscript use")
    return settings, audit_settings, model_version, results_root, paths, audit_report


def direction(pf_value: float, ldc_value: float, tolerance: float) -> str:
    if np.isclose(pf_value, ldc_value, rtol=tolerance, atol=0.0):
        return "NO_MATERIAL_DIFFERENCE_AT_TOLERANCE"
    return "PF_LOWER" if pf_value < ldc_value else "PF_HIGHER"


def build_tables(
    settings: dict[str, Any], model_version: str, report: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    preview = report["diagnostic_preview_not_authorized_for_manuscript"]
    pf = preview["PF"]
    ldc = preview["LDC_AGGREGATE"]
    tolerance = float(settings["validation"]["relative_tolerance"])
    rows: list[dict[str, Any]] = []

    def add_pair(
        metric_id: str,
        sensitivity_case: str,
        unit: str,
        pf_value: float,
        ldc_value: float,
        pf_parameter_case: str,
        ldc_parameter_case: str,
        pf_boundary: str,
        ldc_boundary: str,
        comparison_status: str,
    ) -> None:
        pair_direction = direction(pf_value, ldc_value, tolerance)
        common = {
            "model_version": model_version,
            "analysis_version": settings["analysis_version"],
            "metric_id": metric_id,
            "sensitivity_case": sensitivity_case,
            "unit": unit,
            "comparison_direction": pair_direction,
            "comparison_status": comparison_status,
            "equal_effective_service_verified": True,
            "author_approved_for_later_manuscript_migration": True,
            "automatic_manuscript_edit": False,
        }
        rows.extend(
            [
                {
                    **common,
                    "architecture": "PF",
                    "value": pf_value,
                    "parameter_case": pf_parameter_case,
                    "value_status": "scenario_calculation",
                    "boundary": pf_boundary,
                },
                {
                    **common,
                    "architecture": "LDC_AGGREGATE",
                    "value": ldc_value,
                    "parameter_case": ldc_parameter_case,
                    "value_status": "screening_project_proxy",
                    "boundary": ldc_boundary,
                },
            ]
        )

    add_pair(
        "onsite_cooling_humidification_water",
        "registered_main",
        "m3_per_year",
        float(pf["onsite_cooling_humidification_water_m3"]),
        float(ldc["onsite_cooling_humidification_water_m3"]),
        "small_factory_site",
        "china_hyperscaler_harmonized_baseline",
        settings["claim_boundaries"]["water"],
        settings["claim_boundaries"]["water"],
        "conditional_on_distinct_registered_WUE_cases",
    )
    floor_case = str(settings["validation"]["selected_floor_case"])
    add_pair(
        "total_facility_floor_requirement",
        floor_case,
        "m2",
        float(pf["facility_floor_m2"][floor_case]),
        float(ldc["facility_floor_m2"]),
        f"PF_{floor_case}_rack_and_space_case",
        "CN_LARGE_GREENFIELD",
        settings["claim_boundaries"]["pf_floor"],
        settings["claim_boundaries"]["ldc_floor"],
        "author_selected_central_scenario_comparison",
    )
    add_pair(
        "offsite_land_conversion",
        "registered_boundary",
        "m2",
        float(pf["offsite_land_conversion_m2"]),
        float(ldc["offsite_land_conversion_m2"]),
        "SMALL_FACTORY_REUSE",
        "CN_LARGE_GREENFIELD",
        settings["claim_boundaries"]["pf_land"],
        settings["claim_boundaries"]["ldc_land"],
        "boundary_contrast_not_empirical_architecture_effect",
    )
    summary = pd.DataFrame(rows)
    field_status = pd.DataFrame(
        [
            {
                "model_version": model_version,
                "analysis_version": settings["analysis_version"],
                "architecture": "PF",
                "field_id": "new_building_area",
                "value": np.nan,
                "unit": "m2",
                "value_status": "unquantified",
                "boundary": settings["claim_boundaries"]["pf_floor"],
                "author_approved_for_later_manuscript_migration": True,
                "automatic_manuscript_edit": False,
            },
            {
                "model_version": model_version,
                "analysis_version": settings["analysis_version"],
                "architecture": "LDC_AGGREGATE",
                "field_id": "new_building_area",
                "value": float(ldc["new_building_area_m2"]),
                "unit": "m2",
                "value_status": "greenfield_screening_project_proxy",
                "boundary": settings["claim_boundaries"]["ldc_floor"],
                "author_approved_for_later_manuscript_migration": True,
                "automatic_manuscript_edit": False,
            },
        ]
    )
    validate_tables(settings, summary, field_status, pf, ldc)
    return summary, field_status


def validate_tables(
    settings: dict[str, Any],
    summary: pd.DataFrame,
    field_status: pd.DataFrame,
    pf: dict[str, Any],
    ldc: dict[str, Any],
) -> None:
    required_architectures = set(settings["validation"]["required_architectures"])
    if set(summary["architecture"]) != required_architectures:
        raise ValueError("resource summary lacks exact PF/LDC architecture coverage")
    if set(summary["architecture"]) & set(settings["validation"]["forbidden_architectures"]):
        raise ValueError("resource summary contains a forbidden architecture")
    if set(summary["metric_id"]) != set(settings["validation"]["required_metrics"]):
        raise ValueError("resource summary lacks exact required metric coverage")
    if len(summary) != int(settings["validation"]["expected_summary_rows"]):
        raise ValueError("resource summary row count differs from its YAML contract")
    if summary["value"].isna().any():
        raise ValueError("resource summary must contain finite PF/LDC values")
    if (summary["value"] < 0).any() or not np.isfinite(summary["value"]).all():
        raise ValueError("resource summary contains invalid values")
    if not summary["author_approved_for_later_manuscript_migration"].astype(bool).all():
        raise ValueError("resource rows lack author approval")
    if summary["automatic_manuscript_edit"].astype(bool).any():
        raise ValueError("resource rows permit automatic manuscript edits")
    floor = summary[summary["metric_id"].eq("total_facility_floor_requirement")]
    if len(floor) != 2 or set(floor["sensitivity_case"]) != {
        settings["validation"]["selected_floor_case"]
    }:
        raise ValueError("facility-floor summary must use only the selected case")
    if set(floor["comparison_direction"]) != {
        settings["validation"]["expected_floor_direction"]
    }:
        raise ValueError("selected facility-floor direction differs from its contract")
    if len(field_status) != 2 or set(field_status["architecture"]) != required_architectures:
        raise ValueError("new-building field status lacks exact PF/LDC coverage")
    pf_field = field_status[field_status["architecture"].eq("PF")].iloc[0]
    if pf_field["value_status"] != "unquantified" or not pd.isna(pf_field["value"]):
        raise ValueError("PF new-building area must remain unquantified")
    it_tolerance = float(settings["validation"]["it_energy_relative_tolerance"])
    if not np.isclose(
        float(pf["it_energy_twh"]),
        float(ldc["it_energy_twh"]),
        rtol=it_tolerance,
        atol=0.0,
    ):
        raise ValueError("PF and LDC diagnostic IT energy differs beyond tolerance")


def review_markdown(
    settings: dict[str, Any], model_version: str, summary: pd.DataFrame
) -> str:
    def value(metric: str, architecture: str, case: str) -> float:
        row = summary[
            summary["metric_id"].eq(metric)
            & summary["architecture"].eq(architecture)
            & summary["sensitivity_case"].eq(case)
        ]
        return float(row.iloc[0]["value"])

    pf_water = value("onsite_cooling_humidification_water", "PF", "registered_main")
    ldc_water = value(
        "onsite_cooling_humidification_water", "LDC_AGGREGATE", "registered_main"
    )
    central_floor = value(
        "total_facility_floor_requirement", "PF", "central"
    )
    ldc_floor = value("total_facility_floor_requirement", "LDC_AGGREGATE", "central")
    ldc_land = value("offsite_land_conversion", "LDC_AGGREGATE", "registered_boundary")
    return (
        f"# RQ1 resource footprint: controlled interpretation ({model_version})\n\n"
        "**Status: approved by the authors for Figure 4 and later coordinated manuscript migration; the manuscript is not edited automatically.**\n\n"
        "## Standardized results\n\n"
        f"- Onsite cooling and humidification water: PF {pf_water / 1e6:.3f}, LDC aggregate "
        f"{ldc_water / 1e6:.3f} million m3/year. The two use different registered WUE scenarios, "
        "so the difference is not a causal effect of the architecture itself, and withdrawal and consumption are not distinguished.\n"
        f"- Total facility floor-area demand uses the author-specified central scenario: PF "
        f"{central_floor / 1e6:.3f} million m2; the LDC greenfield project proxy is "
        f"{ldc_floor / 1e6:.3f} million m2. This comparison represents only the registered central space scenario "
        "and is not extrapolated into an unconditional conclusion for other rack densities or site conditions.\n"
        f"- Offsite land conversion: the PF value of 0 is defined solely by the existing-site boundary; the LDC greenfield project proxy is "
        f"{ldc_land / 1e6:.3f} million m2. This contrast cannot be interpreted as an empirically observed "
        "architecture land effect.\n\n"
        "## Field boundaries\n\n"
        "- PF new building area remains unquantified; it must not be replaced by 0.\n"
        "- LDC_AGGREGATE is an equal-service logical capacity portfolio, not one physical data center.\n"
        "- Floor-area and land intensities are project screening proxies, not national averages or vendor-weighted estimates.\n"
        "- Cooling scenarios that change PUE are outside this post-processor and require an RQ3 re-solve.\n"
    )


def write_outputs(
    settings: dict[str, Any],
    model_version: str,
    output_root: Path,
    summary: pd.DataFrame,
    field_status: pd.DataFrame,
    source_paths: dict[str, Path],
    review: str,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    outputs = settings["outputs"]
    summary_path = output_root / outputs["summary_table"]
    fields_path = output_root / outputs["field_status_table"]
    review_path = output_root / outputs["interpretation_review"]
    marker_path = output_root / outputs["validation"]
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
    field_status.to_csv(fields_path, index=False, encoding="utf-8-sig")
    review_path.write_text(review, encoding="utf-8")
    marker = {
        "status": "author_approved_for_figure_and_later_manuscript_migration",
        "model_version": model_version,
        "analysis_version": settings["analysis_version"],
        "evidence_status": settings["evidence_status"],
        "interpretation_status": settings["interpretation_status"],
        "figure_authorization": True,
        "automatic_manuscript_edit": False,
        "author_approval": settings["author_approval"],
        "equal_effective_service_verified": True,
        "selected_floor_case": settings["validation"]["selected_floor_case"],
        "selected_floor_direction": settings["validation"]["expected_floor_direction"],
        "pf_new_building_area_status": "unquantified",
        "source_hashes": {
            name: {"path": display_path(path), "sha256": sha256(path)}
            for name, path in source_paths.items()
        },
        "outputs": {
            "summary_table": {
                "path": display_path(summary_path),
                "rows": len(summary),
                "sha256": sha256(summary_path),
            },
            "field_status_table": {
                "path": display_path(fields_path),
                "rows": len(field_status),
                "sha256": sha256(fields_path),
            },
            "interpretation_review": {
                "path": display_path(review_path),
                "sha256": sha256(review_path),
            },
        },
        "claim_boundaries": settings["claim_boundaries"],
    }
    marker_path.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return marker


def replay_check(
    settings: dict[str, Any],
    model_version: str,
    summary: pd.DataFrame,
    field_status: pd.DataFrame,
    source_paths: dict[str, Path],
    review: str,
) -> None:
    with tempfile.TemporaryDirectory(prefix="rq1_resource_replay_") as tmp:
        first = Path(tmp) / "first"
        second = Path(tmp) / "second"
        marker_a = write_outputs(
            settings, model_version, first, summary, field_status, source_paths, review
        )
        marker_b = write_outputs(
            settings, model_version, second, summary, field_status, source_paths, review
        )
        for key in ["summary_table", "field_status_table", "interpretation_review"]:
            if marker_a["outputs"][key]["sha256"] != marker_b["outputs"][key]["sha256"]:
                raise ValueError(f"nondeterministic output: {key}")


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings, _, model_version, results_root, paths, report = load_summary_contract(
        config_path
    )
    summary, field_status = build_tables(settings, model_version, report)
    review = review_markdown(settings, model_version, summary)
    sources = {
        "summary_configuration": config_path,
        "summary_script": PROJECT_ROOT / "08_code/build_rq1_resource_footprint_summary.py",
        "audit_script": PROJECT_ROOT / "08_code/audit_rq1_resource_footprint.py",
        **paths,
    }
    if args.replay_check:
        replay_check(
            settings, model_version, summary, field_status, sources, review
        )
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "READY_TO_WRITE_AUTHOR_APPROVED_SUMMARY",
                    "model_version": model_version,
                    "summary_rows": len(summary),
                    "field_status_rows": len(field_status),
                    "floor_directions": sorted(
                        set(
                            summary.loc[
                                summary["metric_id"].eq(
                                    "total_facility_floor_requirement"
                                ),
                                "comparison_direction",
                            ]
                        )
                    ),
                    "figure_authorization": True,
                    "automatic_manuscript_edit": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else results_root / model_version / settings["outputs"]["subdirectory"]
    )
    marker = write_outputs(
        settings, model_version, output_root, summary, field_status, sources, review
    )
    print(
        json.dumps(
            {
                "status": marker["status"],
                "model_version": model_version,
                "output_root": str(output_root),
                "figure_authorization": True,
                "automatic_manuscript_edit": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
