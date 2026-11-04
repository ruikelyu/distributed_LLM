#!/usr/bin/env python3
"""Validate and summarize the national temporal-shifting paired counterfactual.

Purpose: Compare the formal flexible SHG core with the SHG no-shift control and
quantify the paired change in additional grid-interconnection capacity.
Workflow status: Active infrastructure-first RQ2 mechanism postprocessor.
Scientific boundary: The estimand is no-shift minus flexible SHG under an
otherwise identical resolved configuration; it is not an architecture contrast.
Inputs: Defaults and paired-case YAML, validated baseline and no-shift national
summaries, and their validation markers.
Outputs: Industry and national paired-effect rows plus a validation marker.
Key assumptions: Positive effects mean modeled grid capacity avoided by allowing
registered task deadlines; all other resolved configuration leaves are fixed.
Explicit exclusions: No empirical causal claim, LDC comparison, cost-first
interpretation, or inference beyond the registered K_choice task boundary.
Validation/tests: YAML-derived version, exact one-path configuration difference,
31-industry pairing, equal service, constant model fields, active-energy
conservation, and zero shiftable energy in the no-shift control.
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

from core.config import load_config


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
PAIR_FACTOR = "PHY03"
PAIR_CASE = "no_shift"
PAIR_ARCHITECTURE = "SHG"
PAIR_BASE_LOAD = "actual_load"
CAPACITY_COLUMN = "industry_equivalent_sum_incremental_grid_peak_mw"
CONSTANT_FIELDS = [
    "model_version",
    "architecture",
    "base_load_case",
    "physical_factory_count",
    "production_load_site_count",
    "ai_deployment_node_count",
    "modeled_routing_node_count",
    "installed_server_groups_integer",
    "online_server_groups_integer",
    "n_plus_spare_server_groups",
    "model_state_minimum_groups_enabled",
    "planning_reserve_fraction",
    "routing_policy",
    "common_it_effective_efficiency_case",
    "common_it_effective_efficiency_multiplier",
    "baseline_reference_workload_per_service_unit",
    "reference_compute_h_per_service_unit",
    "reference_server_group",
    "production_load_mode",
    "production_load_boundary_id",
    "production_activity_share",
    "load_site_count",
    "group_activity_share",
    "adopter_activity_share",
    "ai_service_group_share",
    "industry_equivalent_multiplier",
    "representative_group_adoption_status",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--defaults", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--case-config", type=Path, required=True)
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--baseline-validation", type=Path, required=True)
    parser.add_argument("--no-shift-summary", type=Path, required=True)
    parser.add_argument("--no-shift-validation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--done-output", type=Path, required=True)
    return parser.parse_args()


def project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def relative_to_project(path: Path) -> Path:
    resolved = project_path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise ValueError(f"Configuration must be inside the project: {resolved}") from error


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def comparable_leaf_values(mapping: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    ignored_roots = {"run_config_path", "sensitivity_metadata"}
    values: dict[str, Any] = {}
    for key, value in mapping.items():
        if not prefix and (str(key).startswith("_") or key in ignored_roots):
            continue
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            values.update(comparable_leaf_values(value, path))
        else:
            values[path] = value
    return values


def changed_leaf_paths(left: dict[str, Any], right: dict[str, Any]) -> set[str]:
    left_values = comparable_leaf_values(left)
    right_values = comparable_leaf_values(right)
    keys = set(left_values) | set(right_values)
    return {key for key in keys if left_values.get(key) != right_values.get(key)}


def load_marker(path: Path, model_version: str, label: str) -> dict[str, Any]:
    marker = json.loads(path.read_text(encoding="utf-8"))
    if marker.get("status") != "validated":
        raise ValueError(f"{label} validation marker is not validated")
    if str(marker.get("model_version")) != model_version:
        raise ValueError(f"{label} validation marker has a different model_version")
    return marker


def scalar_equal(left: Any, right: Any) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if isinstance(left, (int, float, np.integer, np.floating)) and isinstance(
        right, (int, float, np.integer, np.floating)
    ):
        return bool(np.isclose(float(left), float(right), rtol=1e-9, atol=1e-10))
    return str(left) == str(right)


def selected_shg(frame: pd.DataFrame, label: str) -> pd.DataFrame:
    required = {
        "industry",
        CAPACITY_COLUMN,
        "weekly_service_units",
        "industry_equivalent_weekly_service_units",
        "annual_unshiftable_ai_active_energy_twh",
        "annual_shiftable_ai_active_energy_twh",
        *CONSTANT_FIELDS,
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{label} summary is missing columns: {missing}")
    selected = frame.loc[
        frame["architecture"].eq(PAIR_ARCHITECTURE)
        & frame["base_load_case"].eq(PAIR_BASE_LOAD)
    ].copy()
    if len(selected) != 31 or selected["industry"].nunique() != 31:
        raise ValueError(f"{label} summary must contain 31 unique SHG actual-load rows")
    return selected.sort_values("industry", kind="stable").reset_index(drop=True)


def main() -> int:
    args = parse_args()
    defaults_path = project_path(args.defaults)
    registry_path = project_path(args.registry)
    case_config_path = project_path(args.case_config)
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    if not SEMVER.fullmatch(model_version):
        raise ValueError("defaults model_version must use vMAJOR.MINOR.PATCH")
    if registry.get("defaults_config") != str(relative_to_project(defaults_path)):
        raise ValueError("Sensitivity registry does not point to the selected defaults YAML")

    factor = registry["factors"][PAIR_FACTOR]
    paired = factor["paired_counterfactual"]
    if paired.get("architecture") != PAIR_ARCHITECTURE:
        raise ValueError("Temporal pair must use SHG")
    if paired.get("base_load_case") != PAIR_BASE_LOAD:
        raise ValueError("Temporal pair must use the actual production-load case")
    if paired.get("control_case") != PAIR_CASE:
        raise ValueError("Temporal pair control must be no_shift")
    expected_changes = set(map(str, paired.get("changed_paths", [])))
    if expected_changes != {"demand.flexibility_scenario"}:
        raise ValueError("Temporal pair may change only demand.flexibility_scenario")

    baseline_config = relative_to_project(Path(paired["baseline_config"]))
    resolved_baseline = load_config(
        PROJECT_ROOT, relative_to_project(defaults_path), baseline_config
    )
    resolved_control = load_config(
        PROJECT_ROOT, relative_to_project(defaults_path), relative_to_project(case_config_path)
    )
    observed_changes = changed_leaf_paths(resolved_baseline, resolved_control)
    if observed_changes != expected_changes:
        raise ValueError(
            "Resolved temporal pair differs outside its registered path: "
            f"observed={sorted(observed_changes)}, expected={sorted(expected_changes)}"
        )
    baseline_scenario = str(resolved_baseline["demand"]["flexibility_scenario"])
    control_scenario = str(resolved_control["demand"]["flexibility_scenario"])
    if baseline_scenario != str(paired["treatment_case"]) or control_scenario != PAIR_CASE:
        raise ValueError("Resolved flexibility scenarios do not match the paired contract")

    baseline_marker = load_marker(
        project_path(args.baseline_validation), model_version, "baseline"
    )
    control_marker = load_marker(
        project_path(args.no_shift_validation), model_version, "no-shift"
    )
    if PAIR_ARCHITECTURE not in baseline_marker.get("actual_load_architectures", []):
        raise ValueError("Baseline validation does not contain SHG")
    if control_marker.get("actual_load_architectures") != [PAIR_ARCHITECTURE]:
        raise ValueError("No-shift validation must contain only SHG")

    baseline = selected_shg(
        pd.read_csv(project_path(args.baseline_summary), encoding="utf-8-sig"),
        "baseline",
    )
    control = selected_shg(
        pd.read_csv(project_path(args.no_shift_summary), encoding="utf-8-sig"),
        "no-shift",
    )
    expected_industries = [str(value) for value in defaults["selected_industries"]]
    if sorted(baseline["industry"].astype(str)) != sorted(expected_industries):
        raise ValueError("Baseline industries differ from defaults YAML")
    if baseline["industry"].tolist() != control["industry"].tolist():
        raise ValueError("Baseline and no-shift industries do not pair one-to-one")

    for index, industry in enumerate(baseline["industry"]):
        for field in CONSTANT_FIELDS:
            if not scalar_equal(baseline.at[index, field], control.at[index, field]):
                raise ValueError(f"{industry}: temporal pair differs on held field {field}")
        service_left = float(baseline.at[index, "weekly_service_units"])
        service_right = float(control.at[index, "weekly_service_units"])
        service_tolerance = max(abs(service_left), 1.0) * 1e-8
        if abs(service_left - service_right) > service_tolerance:
            raise ValueError(f"{industry}: temporal pair does not conserve service")
        if float(baseline.at[index, "annual_shiftable_ai_active_energy_twh"]) <= 0:
            raise ValueError(f"{industry}: baseline does not contain shiftable active energy")
        if abs(float(control.at[index, "annual_shiftable_ai_active_energy_twh"])) > 1e-12:
            raise ValueError(f"{industry}: no-shift control retains shiftable active energy")
        baseline_active = float(
            baseline.at[index, "annual_unshiftable_ai_active_energy_twh"]
            + baseline.at[index, "annual_shiftable_ai_active_energy_twh"]
        )
        control_active = float(
            control.at[index, "annual_unshiftable_ai_active_energy_twh"]
            + control.at[index, "annual_shiftable_ai_active_energy_twh"]
        )
        if not np.isclose(baseline_active, control_active, rtol=1e-8, atol=1e-12):
            raise ValueError(f"{industry}: temporal pair changes total active compute energy")

    output_rows = pd.DataFrame(
        {
            "model_version": model_version,
            "sensitivity_version": registry["sensitivity_version"],
            "observation_level": "industry",
            "industry": baseline["industry"].astype(str),
            "architecture": PAIR_ARCHITECTURE,
            "base_load_case": PAIR_BASE_LOAD,
            "baseline_flexibility_scenario": baseline_scenario,
            "control_flexibility_scenario": control_scenario,
            "effect_definition": paired["effect_definition"],
            "positive_effect_interpretation": paired[
                "positive_effect_interpretation"
            ],
            "flexible_incremental_grid_capacity_mw": baseline[CAPACITY_COLUMN].astype(float),
            "no_shift_incremental_grid_capacity_mw": control[CAPACITY_COLUMN].astype(float),
            "temporal_shifting_effect_incremental_grid_capacity_mw": (
                control[CAPACITY_COLUMN].astype(float)
                - baseline[CAPACITY_COLUMN].astype(float)
            ),
            "weekly_service_units": baseline["industry_equivalent_weekly_service_units"].astype(float),
            "evidence_status": "outputs_validated_not_interpreted",
        }
    )
    national = {
        "model_version": model_version,
        "sensitivity_version": registry["sensitivity_version"],
        "observation_level": "national_sum",
        "industry": "NATIONAL",
        "architecture": PAIR_ARCHITECTURE,
        "base_load_case": PAIR_BASE_LOAD,
        "baseline_flexibility_scenario": baseline_scenario,
        "control_flexibility_scenario": control_scenario,
        "effect_definition": paired["effect_definition"],
        "positive_effect_interpretation": paired["positive_effect_interpretation"],
        "flexible_incremental_grid_capacity_mw": float(
            output_rows["flexible_incremental_grid_capacity_mw"].sum()
        ),
        "no_shift_incremental_grid_capacity_mw": float(
            output_rows["no_shift_incremental_grid_capacity_mw"].sum()
        ),
        "temporal_shifting_effect_incremental_grid_capacity_mw": float(
            output_rows[
                "temporal_shifting_effect_incremental_grid_capacity_mw"
            ].sum()
        ),
        "weekly_service_units": float(output_rows["weekly_service_units"].sum()),
        "evidence_status": "outputs_validated_not_interpreted",
    }
    output_rows = pd.concat(
        [output_rows, pd.DataFrame([national])], ignore_index=True
    )
    output_path = project_path(args.output)
    done_path = project_path(args.done_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_rows.to_csv(output_path, index=False, encoding="utf-8-sig")
    payload = {
        "status": "validated",
        "model_version": model_version,
        "sensitivity_version": registry["sensitivity_version"],
        "pair": {
            "architecture": PAIR_ARCHITECTURE,
            "base_load_case": PAIR_BASE_LOAD,
            "baseline_flexibility_scenario": baseline_scenario,
            "control_flexibility_scenario": control_scenario,
            "effect_definition": paired["effect_definition"],
            "positive_effect_interpretation": paired[
                "positive_effect_interpretation"
            ],
            "resolved_changed_paths": sorted(observed_changes),
            "all_other_resolved_configuration_leaves_held_constant": True,
        },
        "industry_count": 31,
        "equal_effective_service": True,
        "no_shift_has_zero_shiftable_active_energy": True,
        "active_compute_energy_conserved": True,
        "held_constant_result_fields": CONSTANT_FIELDS,
        "national_summary": {
            "flexible_incremental_grid_capacity_mw": national[
                "flexible_incremental_grid_capacity_mw"
            ],
            "no_shift_incremental_grid_capacity_mw": national[
                "no_shift_incremental_grid_capacity_mw"
            ],
            "temporal_shifting_effect_incremental_grid_capacity_mw": national[
                "temporal_shifting_effect_incremental_grid_capacity_mw"
            ],
        },
        "output": {
            "filename": output_path.name,
            "rows": len(output_rows),
            "sha256": sha256(output_path),
        },
        "claim_boundary": (
            "model_based_SHG_no_shift_minus_flexible_effect_under_registered_"
            "K_choice_and_mixed_production_load_boundaries"
        ),
        "evidence_status": "outputs_validated_not_interpreted",
    }
    done_path.parent.mkdir(parents=True, exist_ok=True)
    done_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "model_version": model_version,
                "industry_count": payload["industry_count"],
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
