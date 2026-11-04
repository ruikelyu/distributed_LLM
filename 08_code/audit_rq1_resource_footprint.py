#!/usr/bin/env python3
"""Audit the RQ1 water, facility-floor, and off-site-land rebuild boundary.

Purpose: Determine which legacy Figure 4 components can be rebuilt from v1.0
outputs without solving and which components must be removed or rerun.
Workflow status: Active YAML-versioned pre-rebuild audit.
Scientific boundary: This script diagnoses readiness and produces preview
calculations; it does not authorize resource magnitudes or render a manuscript figure.
Inputs: Validated PF core and LDC aggregate outputs, water and space parameters,
hardware routing, the scenario registry, and the superseded Figure 4 script.
Outputs: Machine-readable and Markdown audit reports under the active model version.
Key assumptions: PF uses the registered existing-factory-site boundary and LDC
uses the registered China greenfield screening proxy.
Explicit exclusions: SHG/MSG resource averages, zero-PF-building claims,
construction materials, grid-equipment effects, and PUE-changing cooling cases.
Validation/tests: Version, architecture, source-marker, parameter-case, energy,
server-capacity, and legacy-pattern checks plus explicit solve-dependency routing.
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
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/rq1_resource_footprint_audit_v1.yaml"


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


def local_floor(
    server_groups: float,
    settings: dict[str, float],
    rack_usable_height_u: float,
    server_height_u: float,
) -> float:
    servers_per_rack = (
        rack_usable_height_u / server_height_u * float(settings["rack_fill"])
    )
    return (
        server_groups
        / servers_per_rack
        * (1.0 + float(settings["noncompute_rack_share"]))
        * float(settings["m2_per_rack"])
    )


def load_contract(config_path: Path) -> tuple[dict[str, Any], str, Path, dict[str, Path]]:
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("RQ1 resource audit schema_version must equal 1")
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    results_root = project_path(defaults["paths"]["results_root"])
    inputs = settings["inputs"]
    paths = {
        "configuration": config_path,
        "defaults": defaults_path,
        "scenario_registry": project_path(settings["scenario_registry"]),
        "legacy_figure_script": project_path(settings["legacy_figure_script"]),
        "core_summary": results_root / model_version / inputs["core_summary_subpath"],
        "core_validation": results_root / model_version / inputs["core_validation_subpath"],
        "ldc_summary": results_root
        / inputs["ldc_summary_subpath"].format(model_version=model_version),
        "ldc_comparison_validation": results_root
        / inputs["ldc_comparison_validation_subpath"].format(model_version=model_version),
        "water_parameters": project_path(inputs["water_parameters"]),
        "space_parameters": project_path(inputs["space_parameters"]),
        "hardware_routing": project_path(inputs["hardware_routing"]),
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing RQ1 resource audit input: " + ", ".join(missing))
    return settings, model_version, results_root, paths


def audit(
    settings: dict[str, Any], model_version: str, paths: dict[str, Path]
) -> dict[str, Any]:
    core_marker = json.loads(paths["core_validation"].read_text(encoding="utf-8"))
    ldc_marker = json.loads(
        paths["ldc_comparison_validation"].read_text(encoding="utf-8")
    )
    if core_marker.get("status") != "validated" or core_marker.get("model_version") != model_version:
        raise ValueError("PF core validation marker is not active and validated")
    if ldc_marker.get("status") != "validated" or ldc_marker.get("model_version") != model_version:
        raise ValueError("LDC comparison validation marker is not active and validated")
    if ldc_marker.get("equal_service_verified") is not True:
        raise ValueError("LDC aggregate source lacks equal-service validation")
    if ldc_marker.get("centralized_capacity_is_one_physical_site") is not False:
        raise ValueError("LDC source permits a one-site interpretation")

    core = pd.read_csv(paths["core_summary"], encoding="utf-8-sig")
    ldc = pd.read_csv(paths["ldc_summary"], encoding="utf-8-sig")
    water = pd.read_csv(paths["water_parameters"], encoding="utf-8-sig")
    space = pd.read_csv(paths["space_parameters"], encoding="utf-8-sig")
    defaults = yaml.safe_load(paths["defaults"].read_text(encoding="utf-8"))
    hardware = yaml.safe_load(paths["hardware_routing"].read_text(encoding="utf-8"))
    selected = settings["selected_cases"]
    pf = core[core["architecture"].eq(selected["distributed_architecture"])]
    if len(pf) != 31 or set(pf["model_version"].astype(str)) != {model_version}:
        raise ValueError("PF resource source must contain 31 active-version rows")
    if len(ldc) != 1 or ldc.iloc[0]["architecture"] != selected["centralized_architecture"]:
        raise ValueError("resource audit requires one LDC_AGGREGATE row")
    if str(ldc.iloc[0]["model_version"]) != model_version:
        raise ValueError("LDC summary model_version differs from defaults")

    water_index = water.set_index("comparison_mode")
    for mode in [selected["local_water_mode"], selected["ldc_water_mode"]]:
        if mode not in water_index.index:
            raise ValueError(f"missing selected water mode: {mode}")
    space_index = space.set_index("space_case_id")
    for case in [selected["pf_space_boundary"], selected["ldc_space_boundary"]]:
        if case not in space_index.index:
            raise ValueError(f"missing selected space boundary: {case}")
    pf_space = space_index.loc[selected["pf_space_boundary"]]
    ldc_space = space_index.loc[selected["ldc_space_boundary"]]
    if pf_space["capacity_source_scenario"] != selected["distributed_architecture"]:
        raise ValueError("PF space boundary retains a legacy architecture mapping")
    if ldc_space["capacity_source_scenario"] != selected["centralized_architecture"]:
        raise ValueError("LDC space boundary retains a legacy architecture mapping")
    if not pd.isna(pf_space["new_build_fraction"]):
        raise ValueError("PF new-building fraction must remain unquantified")
    if float(pf_space["new_land_conversion_fraction"]) != 0.0:
        raise ValueError("PF existing-site boundary must encode zero off-site conversion")
    if (
        ldc_space["capacity_realization"] != "greenfield"
        or float(ldc_space["new_build_fraction"]) != 1.0
        or float(ldc_space["new_land_conversion_fraction"]) != 1.0
    ):
        raise ValueError("LDC selected space boundary must be the greenfield proxy")

    local_multiplier = float(defaults["server"]["marginal_facility_multiplier"])
    cpu_multiplier = float(hardware["cpu_server"]["marginal_facility_multiplier"])
    if not np.isclose(local_multiplier, cpu_multiplier):
        raise ValueError("GPU and CPU local facility multipliers differ")
    ldc_row = ldc.iloc[0]
    ldc_multipliers = {
        float(ldc_row["gpu_facility_multiplier"]),
        float(ldc_row["cpu_facility_multiplier"]),
    }
    if len(ldc_multipliers) != 1:
        raise ValueError("LDC GPU and CPU facility multipliers differ")
    ldc_multiplier = ldc_multipliers.pop()

    pf_facility_energy = float(pf["industry_equivalent_annual_ai_facility_energy_twh"].sum())
    ldc_facility_energy = float(ldc_row["annual_ai_facility_energy_twh"])
    pf_it_energy = pf_facility_energy / local_multiplier
    ldc_it_energy = ldc_facility_energy / ldc_multiplier
    local_wue = float(
        water_index.loc[selected["local_water_mode"], "site_water_use_l_per_kwh_it"]
    )
    ldc_wue = float(
        water_index.loc[selected["ldc_water_mode"], "site_water_use_l_per_kwh_it"]
    )
    pf_water = pf_it_energy * local_wue * 1e6
    ldc_water = ldc_it_energy * ldc_wue * 1e6

    pf_groups = float(
        pf["industry_equivalent_installed_gpu_server_groups"].sum()
        + pf["industry_equivalent_installed_cpu_server_groups"].sum()
    )
    floor_values = {
        name: local_floor(
            pf_groups,
            values,
            float(selected["rack_usable_height_u"]),
            float(selected["server_height_u"]),
        )
        for name, values in selected["local_floor_scenarios"].items()
    }
    gpu_power = float(defaults["server"]["maximum_wall_power_kw"])
    cpu_power = float(hardware["cpu_server"]["maximum_wall_power_kw"])
    ldc_it_capacity_mw = (
        float(ldc_row["installed_gpu_server_groups"]) * gpu_power
        + float(ldc_row["installed_cpu_server_groups"]) * cpu_power
    ) / 1000.0
    ldc_floor = ldc_it_capacity_mw * float(ldc_space["gfa_intensity_m2_per_mw_it"])
    ldc_land = ldc_it_capacity_mw * float(ldc_space["site_intensity_m2_per_mw_it"])

    legacy = paths["legacy_figure_script"].read_text(encoding="utf-8")
    legacy_findings = {
        "contains_SHG_zero_load_in_resource_figure": '"SHG_zero_load"' in legacy,
        "averages_PF_SHG_MSG_resources": 'data["deployment"].isin(["PF", "SHG", "MSG"])' in legacy,
        "sets_local_new_gfa_to_zero": '"new_gfa_m2": 0.0' in legacy,
        "labels_zero_load_uncoordinated": '"uncoordinated"' in legacy,
        "contains_grid_capacity_panel": "Additional grid-interconnection capacity" in legacy,
        "hardcodes_active_result_version_paths": "05_results/v1.0.0" in legacy,
    }
    if not all(legacy_findings.values()):
        raise ValueError("legacy Figure 4 no longer matches the registered audit signature")

    components = [
        {
            "component": "grid_capacity_panel",
            "disposition": "REMOVE_FROM_RESOURCE_FIGURE",
            "solve_required": False,
            "reason": "author-approved aggregate and node-scale grid evidence now belongs to Figure 3",
        },
        {
            "component": "SHG_zero_load_path",
            "disposition": "REMOVE_FROM_RESOURCE_FIGURE",
            "solve_required": False,
            "reason": "this is one RQ2 production-load-context diagnostic, not an uncoordinated architecture",
        },
        {
            "component": "PF_vs_LDC_onsite_water",
            "disposition": "REBUILD_POSTPROCESS_NO_SOLVE",
            "solve_required": False,
            "reason": "validated facility energy and YAML-derived facility multipliers support IT-energy-times-WUE accounting",
        },
        {
            "component": "PF_vs_LDC_facility_floor",
            "disposition": "REBUILD_POSTPROCESS_NO_SOLVE",
            "solve_required": False,
            "reason": "installed reference groups and registered space intensities are available; PF new building area must remain unquantified",
        },
        {
            "component": "PF_vs_LDC_offsite_land",
            "disposition": "REBUILD_POSTPROCESS_NO_SOLVE",
            "solve_required": False,
            "reason": "PF zero is an existing-factory-site scenario boundary and LDC uses a greenfield screening proxy",
        },
        {
            "component": "PUE_changing_cooling_cases",
            "disposition": "DEFER_TO_RQ3_SOLVE",
            "solve_required": True,
            "reason": "changing facility multipliers alters dispatch power and interconnection capacity",
        },
    ]
    return {
        "status": "READY_FOR_BOUNDARY_CORRECTED_POSTPROCESSOR_REBUILD",
        "model_version": model_version,
        "audit_version": settings["audit_version"],
        "source_hashes": {name: sha256(path) for name, path in paths.items()},
        "legacy_findings": legacy_findings,
        "components": components,
        "diagnostic_preview_not_authorized_for_manuscript": {
            "PF": {
                "facility_energy_twh": pf_facility_energy,
                "it_energy_twh": pf_it_energy,
                "onsite_cooling_humidification_water_m3": pf_water,
                "facility_floor_m2": floor_values,
                "new_building_area_m2": None,
                "offsite_land_conversion_m2": 0.0,
                "offsite_land_zero_is_scenario_boundary": True,
            },
            "LDC_AGGREGATE": {
                "facility_energy_twh": ldc_facility_energy,
                "it_energy_twh": ldc_it_energy,
                "onsite_cooling_humidification_water_m3": ldc_water,
                "installed_it_capacity_mw": ldc_it_capacity_mw,
                "facility_floor_m2": ldc_floor,
                "new_building_area_m2": ldc_floor,
                "offsite_land_conversion_m2": ldc_land,
                "greenfield_screening_proxy": True,
            },
        },
        "claim_boundaries": settings["required_rebuild_boundary"],
        "manuscript_authorization": False,
    }


def markdown(report: dict[str, Any]) -> str:
    preview = report["diagnostic_preview_not_authorized_for_manuscript"]
    pf = preview["PF"]
    ldc = preview["LDC_AGGREGATE"]
    component_lines = [
        f"- `{item['disposition']}` — `{item['component']}`: {item['reason']}"
        for item in report["components"]
    ]
    return (
        f"# RQ1 resource-footprint rebuild audit ({report['model_version']})\n\n"
        "**Status: rebuildable post-processor; the preview values below are not yet authorized for the manuscript.**\n\n"
        "## Disposition\n\n"
        + "\n".join(component_lines)
        + "\n\n## Diagnostic preview\n\n"
        f"- PF onsite cooling and humidification water: {pf['onsite_cooling_humidification_water_m3'] / 1e6:.3f} million m3/year.\n"
        f"- LDC aggregate onsite cooling and humidification water: {ldc['onsite_cooling_humidification_water_m3'] / 1e6:.3f} million m3/year.\n"
        f"- PF facility floor area by reference equipment layout: compact {pf['facility_floor_m2']['compact'] / 1e6:.3f}, "
        f"central {pf['facility_floor_m2']['central'] / 1e6:.3f}, spacious {pf['facility_floor_m2']['spacious'] / 1e6:.3f} million m2.\n"
        f"- LDC greenfield facility floor-area proxy: {ldc['facility_floor_m2'] / 1e6:.3f} million m2.\n"
        f"- LDC greenfield offsite land proxy: {ldc['offsite_land_conversion_m2'] / 1e6:.3f} million m2; "
        "the PF value of 0 is only the existing-site boundary, not an empirical estimate.\n\n"
        "## Required corrections\n\n"
        "1. Remove the grid-capacity panel to avoid duplicating the approved Figure 3.\n"
        "2. Remove the SHG zero-load path and the \"uncoordinated\" label.\n"
        "3. Compare only PF and greenfield LDC; no longer average PF, SHG, and MSG.\n"
        "4. Report total facility floor-area demand for PF; keep PF new building area unquantified.\n"
        "5. Label the water metric as onsite cooling and humidification water; do not claim a withdrawal/consumption split.\n"
        "6. Cooling scenarios that change PUE are deferred to an RQ3 re-solve.\n"
    )


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings, model_version, results_root, paths = load_contract(config_path)
    report = audit(settings, model_version, paths)
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "model_version": model_version,
                    "components": report["components"],
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
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / settings["outputs"]["report_json"]
    markdown_path = output_root / settings["outputs"]["report_markdown"]
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(markdown(report), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "model_version": model_version,
                "report": str(markdown_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
