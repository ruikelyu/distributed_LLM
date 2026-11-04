#!/usr/bin/env python3
"""Materialize one bounded OAT case as a normal core-model run config.

Purpose: Apply one whitelisted sensitivity override to a base configuration and write an auditable run configuration.
Workflow status: Active sensitivity orchestration helper.
Scientific boundary: Change only registered one-at-a-time parameters while retaining the core model and matched-baseline structure.
Inputs: Base config, sensitivity registry, selected factor/case, and output path.
Outputs: Materialized YAML configuration and lineage metadata.
Key assumptions: Only explicit allowed override paths can be changed; the selected industry and model version remain traceable.
Explicit exclusions: No arbitrary configuration mutation, result reuse across incompatible cases, or sensitivity interpretation is performed.
Validation/tests: Override-path whitelist, leaf-path resolution, and registry case coverage are checked before writing.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import yaml


ALLOWED_OVERRIDE_PATHS = {
    "paths.hourly_industry_profiles",
    "demand.flexibility_scenario",
    "demand.effective_service.parameter_case",
    "demand.effective_service.common_it_effective_efficiency_case",
    "server.installed_reserve_fraction",
    "server.n_plus_spare_server_groups",
    "server.maximum_wall_power_kw",
    "server.online_idle_wall_power_kw",
    "server.marginal_facility_multiplier",
    "compute_hardware.cpu_server_overrides.marginal_facility_multiplier",
    "compute_hardware.cpu_server_overrides.installed_reserve_fraction",
    "compute_hardware.routing_case",
    "compute_hardware.cpu_time_multiplier_factor",
    "model.server_groups_integer",
    "energy.maximum_demand_rmb_per_kw_month",
    "energy.battery_investment_enabled",
    "energy.pv_capacity_mode",
    "energy.grid_expansion_limit_mw",
    "energy.grid_expansion_objective_penalty_rmb_per_mw_year",
    "hybrid_cloud.enabled",
    "hybrid_cloud.maximum_cloud_service_share",
}
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def leaf_paths(mapping: dict[str, Any], prefix: str = "") -> set[str]:
    paths: set[str] = set()
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            paths |= leaf_paths(value, path)
        else:
            paths.add(path)
    return paths


def comparable_leaf_values(mapping: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten resolved raw configuration while excluding run bookkeeping."""
    ignored_roots = {"run_config_path", "sensitivity_metadata"}
    values: dict[str, Any] = {}
    for key, value in mapping.items():
        if not prefix and (key in ignored_roots or str(key).startswith("_")):
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


def resolve_project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--defaults", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate version and paired-counterfactual scope without writing YAML.",
    )
    args = parser.parse_args()

    registry = yaml.safe_load(args.registry.read_text(encoding="utf-8"))
    defaults_reference = args.defaults or Path(
        registry.get("defaults_config", "config/defaults.yaml")
    )
    defaults = yaml.safe_load(
        resolve_project_path(defaults_reference).read_text(encoding="utf-8")
    )
    model_version = str(defaults["model_version"])
    registered_version = registry.get("model_version")
    if registered_version is not None and str(registered_version) != model_version:
        raise ValueError(
            f"Sensitivity registry model_version {registered_version} differs from "
            f"defaults {model_version}"
        )
    if args.case_id == registry["reference_case"]["case_id"]:
        factor_id, case_name = "REF", "baseline"
        factor = {
            # Chinese label ("same-version baseline") is written to the factor_label_cn CSV column; keep unchanged.
            "label_cn": "同版本基准",
            "baseline_value": registry["reference_case"]["display_value"],
            "primary_claims": ["C2"],
        }
        case = registry["reference_case"]
    else:
        factor_id, case_name = args.case_id.split("__", 1)
        factor = registry["factors"][factor_id]
        case = factor["cases"][case_name]
    overrides = case.get("overrides", {})
    unknown = leaf_paths(overrides) - ALLOWED_OVERRIDE_PATHS
    if unknown:
        raise ValueError(f"Unsupported smoke-test overrides: {sorted(unknown)}")

    output_label = args.output.as_posix() if args.output else "check_only"
    payload: dict[str, Any] = {
        "run_config_path": output_label,
        "model_version": model_version,
        "selected_industries": registry.get("selected_industries", [registry["industry"]]),
        "selected_scenarios": registry["architectures"],
        "industry_parameter_case": "base",
        "sensitivity_metadata": {
            "sensitivity_version": registry["sensitivity_version"],
            "factor_id": factor_id,
            "factor_label_cn": factor["label_cn"],
            "case_name": case_name,
            "display_value": case["display_value"],
            "baseline_value": factor["baseline_value"],
            "primary_claims": factor["primary_claims"],
            "baseline_invariant": bool(registry.get("baseline_invariant", False)),
            "version_source": str(defaults_reference),
        },
    }
    paired = factor.get("paired_counterfactual")
    if paired:
        expected_changes = set(map(str, paired.get("changed_paths", [])))
        observed_overrides = leaf_paths(overrides)
        if not expected_changes or observed_overrides != expected_changes:
            raise ValueError(
                "Paired counterfactual overrides differ from registered changed_paths: "
                f"observed={sorted(observed_overrides)}, expected={sorted(expected_changes)}"
            )
        if str(case_name) != str(paired.get("control_case")):
            raise ValueError("Paired counterfactual control_case differs from selected case")
        payload["sensitivity_metadata"]["paired_counterfactual"] = paired
    common_overrides = registry.get("common_overrides", {})
    unknown_common = leaf_paths(common_overrides) - ALLOWED_OVERRIDE_PATHS
    if unknown_common:
        raise ValueError(f"Unsupported common smoke-test overrides: {sorted(unknown_common)}")
    payload = deep_merge(payload, common_overrides)
    payload = deep_merge(payload, overrides)
    if paired:
        baseline_path = resolve_project_path(paired["baseline_config"])
        baseline_run = yaml.safe_load(baseline_path.read_text(encoding="utf-8"))
        baseline_resolved = deep_merge(defaults, baseline_run)
        control_resolved = deep_merge(defaults, payload)
        observed_changes = changed_leaf_paths(baseline_resolved, control_resolved)
        expected_changes = set(map(str, paired["changed_paths"]))
        if observed_changes != expected_changes:
            raise ValueError(
                "Resolved paired configurations differ outside the registered scope: "
                f"observed={sorted(observed_changes)}, expected={sorted(expected_changes)}"
            )
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "validated_check_only",
                    "model_version": model_version,
                    "case_id": args.case_id,
                    "changed_paths": sorted(leaf_paths(overrides)),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.output is None:
        raise ValueError("--output is required unless --check-only is used")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
