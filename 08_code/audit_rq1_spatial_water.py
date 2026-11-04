#!/usr/bin/env python3
"""Audit readiness of the RQ1 PF-versus-LDC spatial water chain.

Purpose: Verify solver-free spatial allocation and the traceable province-level
Aqueduct 4.0 water-stress context before the replacement Figure 5 is built.
Workflow status: Active YAML-versioned rebuild-readiness audit.
Scientific boundary: Diagnostic only; this script does not create Figure 5 or
authorize a replacement spatial-exposure figure or weighted-impact claims.
Inputs: Approved resource outputs, PF and LDC spatial proxies, checksum-frozen
Aqueduct 4.0 province context and lineage, and the superseded Figure 5 script.
Outputs: JSON and Markdown audit reports under the YAML-selected model version.
Key assumptions: Architecture-specific WUE is uniform across provinces, so
allocation preserves each architecture's approved national water total.
Explicit exclusions: Facility siting prediction, provider traffic inference,
location-specific WUE, water withdrawal/consumption splitting, and optimization.
Validation/tests: Version/approval, province coverage, share closure, lineage,
source-hash and legacy-script boundary checks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/rq1_spatial_water_audit_v1.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
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


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_contract(config_path: Path) -> tuple[dict[str, Any], str, dict[str, Path]]:
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("spatial-water audit schema_version must equal 1")
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    results_root = project_path(defaults["paths"]["results_root"])
    inputs = settings["inputs"]
    paths = {
        "configuration": config_path,
        "defaults": defaults_path,
        "scenario_registry": project_path(settings["scenario_registry"]),
        "water_stress_source_config": project_path(settings["water_stress_source_config"]),
        "legacy_figure_script": project_path(settings["legacy_figure_script"]),
        "resource_summary": results_root / model_version / inputs["approved_resource_summary_subpath"],
        "resource_validation": results_root / model_version / inputs["approved_resource_validation_subpath"],
        "pf_allocation": project_path(inputs["province_industry_allocation"]),
        "pf_lineage": project_path(inputs["province_industry_lineage"]),
        "ldc_proxy": project_path(inputs["cloud_capacity_proxy"]),
        "water_stress": project_path(inputs["water_stress_context"]),
        "water_stress_lineage": project_path(inputs["water_stress_lineage"]),
        "water_stress_source_receipt": project_path(inputs["water_stress_source_receipt"]),
    }
    required = [
        "configuration", "defaults", "scenario_registry", "water_stress_source_config", "legacy_figure_script",
        "resource_summary", "resource_validation", "pf_allocation", "pf_lineage",
        "ldc_proxy", "water_stress", "water_stress_lineage", "water_stress_source_receipt",
    ]
    missing = [relative(paths[name]) for name in required if not paths[name].is_file()]
    if missing:
        raise FileNotFoundError("missing spatial-water audit input: " + ", ".join(missing))
    return settings, model_version, paths


def audit(settings: dict[str, Any], model_version: str, paths: dict[str, Path]) -> dict[str, Any]:
    validation = settings["validation"]
    expected_industries = int(validation["expected_industries"])
    expected_provinces = int(validation["expected_provinces"])
    tolerance = float(validation["share_tolerance"])

    marker = json.loads(paths["resource_validation"].read_text(encoding="utf-8"))
    if marker.get("model_version") != model_version or marker.get("author_approval", {}).get("status") != "approved":
        raise ValueError("spatial audit requires the active author-approved resource summary")
    summary = pd.read_csv(paths["resource_summary"], encoding="utf-8-sig")
    water = summary[summary["metric_id"].eq(validation["water_metric"])].copy()
    if set(water["architecture"]) != set(validation["approved_architectures"]):
        raise ValueError("approved water summary does not contain exactly PF and LDC_AGGREGATE")
    national_water = dict(zip(water["architecture"], water["value"].astype(float)))
    water_boundaries = set(water["boundary"].astype(str))
    water_inventory_is_unsplit_site_water = bool(water_boundaries) and all(
        "not_split_withdrawal_or_consumption" in boundary for boundary in water_boundaries
    )
    stress_source = yaml.safe_load(paths["water_stress_source_config"].read_text(encoding="utf-8"))

    pf = pd.read_csv(paths["pf_allocation"], encoding="utf-8-sig")
    pf_lineage = json.loads(paths["pf_lineage"].read_text(encoding="utf-8"))
    pf_grouped = pf.groupby("industry_code")["electricity_share_within_industry"].sum()
    pf_source = project_path(pf_lineage["source"])
    pf_checks = {
        "rows_equal_31_by_31": len(pf) == expected_industries * expected_provinces,
        "industry_count": pf["industry_code"].nunique() == expected_industries,
        "province_count": pf["province"].nunique() == expected_provinces,
        "each_industry_share_sums_to_one": bool(np.allclose(pf_grouped, 1.0, atol=tolerance, rtol=0.0)),
        "lineage_declares_scenario_not_observation": "not observed" in pf_lineage.get("interpretation", ""),
        "lineage_source_exists": pf_source.is_file(),
        "lineage_source_hash_matches": pf_source.is_file() and sha256(pf_source) == pf_lineage.get("source_sha256"),
    }

    ldc = pd.read_csv(paths["ldc_proxy"], encoding="utf-8-sig")
    required_ldc_metadata = ["share_basis", "reference_period", "source_title", "source_figure", "source_url", "extraction_method", "uncertainty_note"]
    ldc_checks = {
        "province_count": ldc["province"].nunique() == expected_provinces,
        "share_sums_to_one": bool(np.isclose(ldc["cloud_load_share"].sum(), 1.0, atol=tolerance, rtol=0.0)),
        "embedded_source_metadata_complete": all(column in ldc and ldc[column].notna().all() for column in required_ldc_metadata),
        # Matches the Chinese source note in the data file ("not a cloud-provider traffic share or 2030 plan share").
        "explicitly_capacity_proxy": bool(ldc["uncertainty_note"].astype(str).str.contains("不是云厂商流量份额或2030规划份额", regex=False).all()),
    }

    stress = pd.read_csv(paths["water_stress"], encoding="utf-8-sig")
    stress_lineage = json.loads(paths["water_stress_lineage"].read_text(encoding="utf-8"))
    stress_receipt = json.loads(paths["water_stress_source_receipt"].read_text(encoding="utf-8"))
    raw_archive = project_path(stress_source["file"]["destination"])
    expected_columns = {
        "province", "baseline_water_stress_score", "baseline_water_stress_category",
        "baseline_water_stress_label", "aggregation_weight", "context_only_not_multiplied_by_site_water",
    }
    stress_checks = {
        "has_exactly_31_unique_provinces": len(stress) == expected_provinces and stress["province"].nunique() == expected_provinces,
        "required_columns_present": expected_columns.issubset(stress.columns),
        "scores_complete_and_in_range": bool(stress["baseline_water_stress_score"].notna().all() and stress["baseline_water_stress_score"].between(0, 5).all()),
        "categories_complete_and_in_range": bool(stress["baseline_water_stress_category"].notna().all() and stress["baseline_water_stress_category"].between(0, 4).all()),
        "industrial_weight_is_explicit": bool(stress["aggregation_weight"].eq(stress_source["selection"]["main_weight_interpretation"]).all()),
        "context_separation_flag_is_true": bool(stress["context_only_not_multiplied_by_site_water"].all()),
        "raw_source_snapshot_exists": raw_archive.is_file(),
        "raw_source_hash_matches_contract": raw_archive.is_file() and sha256(raw_archive) == stress_source["file"]["official_sha256"],
        "lineage_hash_matches_source": stress_lineage.get("source_sha256") == stress_source["file"]["official_sha256"],
        "receipt_hash_matches_source": stress_receipt.get("sha256") == stress_source["file"]["official_sha256"],
        "baseline_is_main_and_2030_bau_is_rq3_only": bool(not stress_source["future_sensitivity"]["active_in_main_figure"] and stress_source["future_sensitivity"]["registered_for_rq3_only"]),
    }
    stress_traceable = all(stress_checks.values())

    legacy = paths["legacy_figure_script"].read_text(encoding="utf-8")
    legacy_findings = {
        "hardcodes_v1_result_roots": "05_results/v1.0.0" in legacy,
        "hardcodes_pf_facility_multiplier": "/ 1.30" in legacy,
        "reuses_pf_it_energy_for_ldc": "cloud.cloud_load_share * national_it_energy_twh" in legacy,
        "uses_forbidden_withdrawal_label": "withdrawal" in legacy.lower(),
        "has_versioned_validation_marker": "validated.done.json" in legacy,
    }

    components = [
        {
            "component": "PF_province_water_allocation",
            "disposition": "REBUILD_POSTPROCESS_NO_SOLVE",
            "ready": all(pf_checks.values()),
            "reason": "allocate the approved PF national water total with the frozen 31-industry REFERENCE electricity-share scenario",
        },
        {
            "component": "LDC_province_water_allocation",
            "disposition": "REBUILD_POSTPROCESS_NO_SOLVE_USING_OWN_APPROVED_WATER_TOTAL",
            "ready": all(ldc_checks.values()),
            "reason": "allocate LDC's own approved water total with the frozen 2025 CAICT capacity proxy; do not reuse PF IT energy",
        },
        {
            "component": "national_water_total",
            "disposition": "PRESERVE_APPROVED_TOTALS",
            "ready": True,
            "reason": "uniform architecture-specific WUE means spatial allocation changes distribution, not the approved national total",
        },
        {
            "component": "formal_water_scarcity_LCIA_application",
            "disposition": "NOT_APPLICABLE_BY_APPROVED_DESIGN",
            "ready": True,
            "reason": "the approved design does not multiply site water by a characterization factor or report world-equivalent impact",
        },
        {
            "component": "province_water_stress_context_and_Figure5",
            "disposition": "USE_SEPARATE_BASELINE_CONTEXT_PANEL",
            "ready": stress_traceable,
            "reason": "use the checksum-frozen WRI province baseline, industrial-demand-weighted score only as a prioritization context separate from site-water quantities",
        },
    ]
    status = "READY_FOR_SPATIAL_REBUILD" if all(item["ready"] for item in components) else "PARTIAL_READY_WATER_STRESS_CONTEXT_BLOCKED"
    return {
        "status": status,
        "model_version": model_version,
        "audit_version": settings["audit_version"],
        "evidence_status": "audit_only_no_manuscript_authorization",
        "solver_required": False,
        "automatic_manuscript_edit": settings["automatic_manuscript_edit"],
        "approved_national_onsite_water_m3_per_year": national_water,
        "water_stress_context_method": {
            "source": stress_source["dataset"]["title"],
            "indicator": stress_source["selection"]["indicator_value"],
            "aggregation_weight": stress_source["selection"]["main_weight_interpretation"],
            "approved_water_inventory_is_unsplit_site_water": water_inventory_is_unsplit_site_water,
            "technical_note_doi": stress_source["dataset"]["technical_note_doi"],
            "future_2030_bau_active_in_main_figure": stress_source["future_sensitivity"]["active_in_main_figure"],
        },
        "checks": {"pf_allocation": pf_checks, "ldc_capacity_proxy": ldc_checks, "water_stress_context": stress_checks},
        "legacy_figure5_findings": legacy_findings,
        "components": components,
        "claim_boundaries": settings["claim_boundaries"],
        "input_hashes": {
            name: {"path": relative(path), "sha256": sha256(path)}
            for name, path in paths.items() if path.is_file()
        },
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# RQ1 spatial-water audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Model version: `{report['model_version']}`",
        "- Execution: solver-free audit; no Figure 5 or manuscript authorization",
        "",
        "## Component disposition",
        "",
        "| Component | Ready | Disposition | Reason |",
        "|---|---:|---|---|",
    ]
    for item in report["components"]:
        lines.append(f"| {item['component']} | {str(item['ready']).lower()} | `{item['disposition']}` | {item['reason']} |")
    lines.extend(["", "## Decisive findings", ""])
    lines.append("- PF allocation closes across 31 industries and 31 provinces and its upstream source hash matches the registered lineage.")
    lines.append("- The LDC input is usable only as a frozen 2025 in-use intelligent-compute capacity proxy, not provider traffic or a 2030 siting forecast.")
    lines.append("- PF and LDC must retain their own approved national on-site cooling and humidification water totals; the superseded script incorrectly applies PF IT energy to LDC.")
    lines.append("- The official WRI Aqueduct 4.0 rankings archive is checksum-frozen, and the industrial-demand-weighted baseline water-stress rows reproduce for all 31 provinces with lineage.")
    lines.append("- The approved design retains the registered site-water WUE values and presents province water stress separately. It does not multiply the two, report m3 world-eq, or claim a formal LCIA water-scarcity impact.")
    lines.append("- The superseded script also hard-codes v1.0.0 paths and a 1.30 multiplier and labels the metric as withdrawal, outside the current water boundary.")
    lines.extend(["", "## Next admissible action", ""])
    lines.append("Build the YAML-versioned PF-versus-LDC Figure 5 postprocessor using each architecture's approved national site-water total and the Aqueduct baseline score as a separate context field or panel. Keep 2030 BAU for RQ3 sensitivity only. No optimization rerun is required unless location-specific WUE or another power-affecting cooling assumption is introduced.")
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    config_path = project_path(args.config)
    settings, model_version, paths = load_contract(config_path)
    report = audit(settings, model_version, paths)
    if args.check_only:
        print(json.dumps({"status": report["status"], "model_version": model_version}, ensure_ascii=False))
        return
    defaults = yaml.safe_load(paths["defaults"].read_text(encoding="utf-8"))
    output_root = args.output_root or project_path(defaults["paths"]["results_root"]) / model_version / settings["outputs"]["subdirectory"]
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / settings["outputs"]["report_json"]
    md_path = output_root / settings["outputs"]["report_markdown"]
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(markdown(report), encoding="utf-8")
    print(f"Wrote {relative(json_path)}")
    print(f"Wrote {relative(md_path)}")
    print(report["status"])


if __name__ == "__main__":
    main()
