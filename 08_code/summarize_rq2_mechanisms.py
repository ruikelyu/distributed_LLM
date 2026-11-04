#!/usr/bin/env python3
"""Standardize three RQ2 paired diagnostics within two mechanism families.

Purpose: Present two within-site temporal-alignment diagnostics and one cross-site
spatial-coordination diagnostic through one machine-readable result interface.
Workflow status: Active infrastructure-first RQ2 postprocessor.
Scientific boundary: Every effect is control minus mechanism-enabled within its
own strict pair. Diagnostics and mechanism families are not additive.
Inputs: YAML-selected defaults, validated national group-core tables, and the
validated SHG no-shift paired table.
Outputs: One long-form CSV with industry and national-sum rows plus a validation
marker recording source hashes, pair definitions, and claim boundaries.
Key assumptions: Industry-equivalent capacity is the common reporting scale;
national rows sum industry capacities and recompute ratios from those sums.
Explicit exclusions: No architecture-level difference is relabeled as a pure
mechanism, no cross-diagnostic total is produced, and no empirical causal or
grid-investment claim is inferred.
Validation/tests: YAML-derived version agreement, validated source markers,
complete 31-industry pairs, equal service, finite values, source-effect
reconciliation, and national sum identities.
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
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/rq2_mechanism_summary_v1.yaml"
SEMVER = re.compile(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")
OUTPUT_COLUMNS = [
    "model_version",
    "analysis_version",
    "observation_level",
    "industry",
    "mechanism_family",
    "paired_diagnostic",
    "diagnostic_role",
    "architecture",
    "control_case",
    "mechanism_enabled_case",
    "effect_definition",
    "control_incremental_grid_capacity_mw",
    "mechanism_enabled_incremental_grid_capacity_mw",
    "avoided_incremental_grid_capacity_mw",
    "effect_fraction_of_control",
    "weekly_service_units",
    "production_load_mode",
    "production_load_boundary_id",
    "positive_value_interpretation",
    "pairing_boundary",
    "paired_diagnostics_are_additive",
    "mechanism_families_are_additive",
    "evidence_status",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--done-output", type=Path)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run all validation and print national summaries without writing files.",
    )
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


def require_columns(frame: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")


def close(
    left: pd.Series | np.ndarray,
    right: pd.Series | np.ndarray,
    absolute_tolerance: float,
    relative_tolerance: float,
) -> bool:
    return bool(
        np.allclose(
            np.asarray(left, dtype=float),
            np.asarray(right, dtype=float),
            atol=absolute_tolerance,
            rtol=relative_tolerance,
            equal_nan=False,
        )
    )


def standardized_rows(
    source: pd.DataFrame,
    paired_diagnostic: str,
    settings: dict[str, Any],
    model_version: str,
    analysis_version: str,
    control_column: str,
    enabled_column: str,
    effect_column: str,
    service_column: str,
) -> pd.DataFrame:
    contract = settings["paired_diagnostics"][paired_diagnostic]
    result = pd.DataFrame(
        {
            "model_version": model_version,
            "analysis_version": analysis_version,
            "observation_level": "industry",
            "industry": source["industry"].astype(str),
            "mechanism_family": contract["mechanism_family"],
            "paired_diagnostic": paired_diagnostic,
            "diagnostic_role": contract["diagnostic_role"],
            "architecture": contract["architecture"],
            "control_case": contract["control_case"],
            "mechanism_enabled_case": contract["mechanism_enabled_case"],
            "effect_definition": settings["effect_definition"],
            "control_incremental_grid_capacity_mw": source[control_column].astype(float),
            "mechanism_enabled_incremental_grid_capacity_mw": source[enabled_column].astype(float),
            "avoided_incremental_grid_capacity_mw": source[effect_column].astype(float),
            "weekly_service_units": source[service_column].astype(float),
            "production_load_mode": source["production_load_mode"].astype(str),
            "production_load_boundary_id": source["production_load_boundary_id"].astype(str),
            "positive_value_interpretation": contract["positive_value_interpretation"],
            "pairing_boundary": contract["pairing_boundary"],
            "paired_diagnostics_are_additive": bool(
                settings["paired_diagnostics_are_additive"]
            ),
            "mechanism_families_are_additive": bool(
                settings["mechanism_families_are_additive"]
            ),
            "evidence_status": settings["evidence_status"],
        }
    )
    result["effect_fraction_of_control"] = np.where(
        result["control_incremental_grid_capacity_mw"].ne(0.0),
        result["avoided_incremental_grid_capacity_mw"]
        / result["control_incremental_grid_capacity_mw"],
        np.nan,
    )
    return result[OUTPUT_COLUMNS]


def load_and_validate(settings: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    if not SEMVER.fullmatch(model_version):
        raise ValueError("defaults_config model_version must use vMAJOR.MINOR.PATCH")
    analysis_version = str(settings["analysis_version"])
    industries = [str(value) for value in defaults["selected_industries"]]
    expected_count = int(settings["validation"]["expected_industry_count"])
    if len(industries) != expected_count or len(set(industries)) != expected_count:
        raise ValueError("defaults_config does not contain the expected unique industries")
    if settings["effect_definition"] != "control_minus_mechanism_enabled":
        raise ValueError("The registered RQ2 effect definition has changed")
    if settings["paired_diagnostics_are_additive"] is not False:
        raise ValueError("RQ2 paired diagnostics must remain explicitly non-additive")
    if settings["mechanism_families_are_additive"] is not False:
        raise ValueError("RQ2 mechanism families must remain explicitly non-additive")
    families = settings["mechanism_families"]
    diagnostics = settings["paired_diagnostics"]
    if set(families) != {
        "within_site_production_compute_temporal_alignment",
        "cross_site_spatial_coordination",
    }:
        raise ValueError("RQ2 must retain the two author-approved mechanism families")
    registered_members = {
        diagnostic
        for family in families.values()
        for diagnostic in family["paired_diagnostics"]
    }
    if registered_members != set(diagnostics):
        raise ValueError("Mechanism-family membership does not match paired diagnostics")
    for diagnostic, contract in diagnostics.items():
        family = contract["mechanism_family"]
        if family not in families or diagnostic not in families[family]["paired_diagnostics"]:
            raise ValueError(f"{diagnostic}: invalid mechanism-family membership")

    results_root = project_path(defaults["paths"]["results_root"])
    core_root = results_root / model_version / settings["sources"]["core_national_subdirectory"]
    temporal_root = (
        results_root
        / "sensitivity"
        / model_version
        / settings["sources"]["temporal_pair_subdirectory"]
    )
    source_paths = {
        "core_scenarios": core_root / "core_scenarios.csv",
        "shg_load_alignment": core_root / "shg_load_alignment.csv",
        "msg_coordination_value": core_root / "msg_coordination_value.csv",
        "core_validation": core_root / "validated.done.json",
        "temporal_shifting_value": temporal_root / "temporal_shifting_value.csv",
        "temporal_validation": temporal_root / "temporal_shifting.validated.done.json",
    }
    missing = [str(path) for path in source_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing RQ2 source files: " + ", ".join(missing))

    core_marker = json.loads(source_paths["core_validation"].read_text(encoding="utf-8"))
    temporal_marker = json.loads(
        source_paths["temporal_validation"].read_text(encoding="utf-8")
    )
    for label, marker in [("core", core_marker), ("temporal", temporal_marker)]:
        if marker.get("status") != "validated" or marker.get("model_version") != model_version:
            raise ValueError(f"{label} source is not validated for YAML model_version")
    if core_marker.get("evidence_status") != settings["evidence_status"]:
        raise ValueError("Core evidence status differs from the RQ2 summary contract")
    if temporal_marker.get("evidence_status") != settings["evidence_status"]:
        raise ValueError("Temporal evidence status differs from the RQ2 summary contract")

    core = pd.read_csv(source_paths["core_scenarios"], encoding="utf-8-sig")
    alignment = pd.read_csv(source_paths["shg_load_alignment"], encoding="utf-8-sig")
    coordination = pd.read_csv(
        source_paths["msg_coordination_value"], encoding="utf-8-sig"
    )
    temporal = pd.read_csv(source_paths["temporal_shifting_value"], encoding="utf-8-sig")
    require_columns(
        core,
        [
            "industry",
            "architecture",
            "base_load_case",
            "model_version",
            "industry_equivalent_sum_incremental_grid_peak_mw",
            "industry_equivalent_weekly_service_units",
            "production_load_mode",
            "production_load_boundary_id",
        ],
        "core_scenarios",
    )
    require_columns(
        alignment,
        ["industry", "architecture", "definition", "industry_equivalent_avoided_incremental_grid_peak_mw"],
        "shg_load_alignment",
    )
    require_columns(
        coordination,
        [
            "industry",
            "model_version",
            "effect_definition",
            "industry_equivalent_msg_no_routing_sum_incremental_grid_peak_mw",
            "industry_equivalent_msg_coordinated_sum_incremental_grid_peak_mw",
            "industry_equivalent_coordination_effect_sum_incremental_grid_peak_mw",
        ],
        "msg_coordination_value",
    )
    require_columns(
        temporal,
        [
            "model_version",
            "observation_level",
            "industry",
            "architecture",
            "base_load_case",
            "effect_definition",
            "flexible_incremental_grid_capacity_mw",
            "no_shift_incremental_grid_capacity_mw",
            "temporal_shifting_effect_incremental_grid_capacity_mw",
            "weekly_service_units",
        ],
        "temporal_shifting_value",
    )
    if set(core["model_version"].astype(str)) != {model_version}:
        raise ValueError("core_scenarios model_version differs from YAML")
    if set(coordination["model_version"].astype(str)) != {model_version}:
        raise ValueError("msg_coordination_value model_version differs from YAML")
    if set(temporal["model_version"].astype(str)) != {model_version}:
        raise ValueError("temporal_shifting_value model_version differs from YAML")

    shg = core.loc[
        core["architecture"].eq("SHG") & core["base_load_case"].eq("actual_load")
    ].copy()
    msg = core.loc[
        core["architecture"].eq("MSG") & core["base_load_case"].eq("actual_load")
    ].copy()
    temporal_industry = temporal.loc[temporal["observation_level"].eq("industry")].copy()
    frames = {
        "SHG core": shg,
        "MSG core": msg,
        "production-load pair": alignment,
        "MSG pair": coordination,
        "temporal pair": temporal_industry,
    }
    expected_industries = set(industries)
    for label, frame in frames.items():
        observed = set(frame["industry"].astype(str))
        if len(frame) != expected_count or observed != expected_industries:
            raise ValueError(f"{label} lacks exact {expected_count}-industry coverage")
        if frame["industry"].duplicated().any():
            raise ValueError(f"{label} contains duplicate industries")

    contracts = settings["paired_diagnostics"]
    if set(alignment["architecture"].astype(str)) != {contracts["production_load_context"]["architecture"]}:
        raise ValueError("Production-load source architecture differs from contract")
    if set(alignment["definition"].astype(str)) != {contracts["production_load_context"]["source_effect_definition"]}:
        raise ValueError("Production-load source effect definition differs from contract")
    if set(temporal_industry["architecture"].astype(str)) != {contracts["task_temporal_flexibility"]["architecture"]}:
        raise ValueError("Temporal source architecture differs from contract")
    if set(temporal_industry["base_load_case"].astype(str)) != {"actual_load"}:
        raise ValueError("Temporal pair must use actual production load")
    if set(temporal_industry["effect_definition"].astype(str)) != {contracts["task_temporal_flexibility"]["source_effect_definition"]}:
        raise ValueError("Temporal source effect definition differs from contract")
    if set(coordination["effect_definition"].astype(str)) != {contracts["cross_site_routing"]["source_effect_definition"]}:
        raise ValueError("MSG source effect definition differs from contract")

    shg = shg.set_index("industry").loc[industries].reset_index()
    msg = msg.set_index("industry").loc[industries].reset_index()
    alignment = alignment.set_index("industry").loc[industries].reset_index()
    coordination = coordination.set_index("industry").loc[industries].reset_index()
    temporal_industry = temporal_industry.set_index("industry").loc[industries].reset_index()
    absolute_tolerance = float(settings["validation"]["absolute_tolerance_mw"])
    relative_tolerance = float(settings["validation"]["relative_tolerance"])

    production = shg[
        [
            "industry",
            "industry_equivalent_sum_incremental_grid_peak_mw",
            "industry_equivalent_weekly_service_units",
            "production_load_mode",
            "production_load_boundary_id",
        ]
    ].copy()
    production = production.rename(
        columns={
            "industry_equivalent_sum_incremental_grid_peak_mw": "enabled",
            "industry_equivalent_weekly_service_units": "service",
        }
    )
    production["effect"] = alignment[
        "industry_equivalent_avoided_incremental_grid_peak_mw"
    ].astype(float)
    production["control"] = production["enabled"] + production["effect"]

    temporal_source = temporal_industry.copy()
    temporal_source["production_load_mode"] = shg["production_load_mode"]
    temporal_source["production_load_boundary_id"] = shg["production_load_boundary_id"]

    coordination_source = coordination.copy()
    coordination_source["weekly_service_units"] = msg[
        "industry_equivalent_weekly_service_units"
    ]
    coordination_source["production_load_mode"] = msg["production_load_mode"]
    coordination_source["production_load_boundary_id"] = msg[
        "production_load_boundary_id"
    ]

    rows = [
        standardized_rows(
            production,
            "production_load_context",
            settings,
            model_version,
            analysis_version,
            "control",
            "enabled",
            "effect",
            "service",
        ),
        standardized_rows(
            temporal_source,
            "task_temporal_flexibility",
            settings,
            model_version,
            analysis_version,
            "no_shift_incremental_grid_capacity_mw",
            "flexible_incremental_grid_capacity_mw",
            "temporal_shifting_effect_incremental_grid_capacity_mw",
            "weekly_service_units",
        ),
        standardized_rows(
            coordination_source,
            "cross_site_routing",
            settings,
            model_version,
            analysis_version,
            "industry_equivalent_msg_no_routing_sum_incremental_grid_peak_mw",
            "industry_equivalent_msg_coordinated_sum_incremental_grid_peak_mw",
            "industry_equivalent_coordination_effect_sum_incremental_grid_peak_mw",
            "weekly_service_units",
        ),
    ]
    result = pd.concat(rows, ignore_index=True)
    expected_effect = (
        result["control_incremental_grid_capacity_mw"]
        - result["mechanism_enabled_incremental_grid_capacity_mw"]
    )
    if not close(
        result["avoided_incremental_grid_capacity_mw"],
        expected_effect,
        absolute_tolerance,
        relative_tolerance,
    ):
        raise ValueError("At least one standardized effect does not equal control minus enabled")
    numeric = result[
        [
            "control_incremental_grid_capacity_mw",
            "mechanism_enabled_incremental_grid_capacity_mw",
            "avoided_incremental_grid_capacity_mw",
            "effect_fraction_of_control",
            "weekly_service_units",
        ]
    ]
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Standardized RQ2 values must be finite")
    service = result.pivot(
        index="industry", columns="paired_diagnostic", values="weekly_service_units"
    )
    if not close(
        service.to_numpy(),
        np.repeat(service.iloc[:, [0]].to_numpy(), service.shape[1], axis=1),
        absolute_tolerance,
        relative_tolerance,
    ):
        raise ValueError("The three paired diagnostics do not report equal service by industry")

    temporal_national = temporal.loc[temporal["observation_level"].eq("national_sum")]
    if len(temporal_national) != 1:
        raise ValueError("Temporal source must contain exactly one national_sum row")
    for column in [
        "flexible_incremental_grid_capacity_mw",
        "no_shift_incremental_grid_capacity_mw",
        "temporal_shifting_effect_incremental_grid_capacity_mw",
        "weekly_service_units",
    ]:
        if not close(
            [temporal_industry[column].sum()],
            temporal_national[column],
            absolute_tolerance,
            relative_tolerance,
        ):
            raise ValueError(f"Temporal national source row does not sum for {column}")

    national_rows: list[dict[str, Any]] = []
    for paired_diagnostic, group in result.groupby("paired_diagnostic", sort=False):
        control = float(group["control_incremental_grid_capacity_mw"].sum())
        enabled = float(group["mechanism_enabled_incremental_grid_capacity_mw"].sum())
        effect = float(group["avoided_incremental_grid_capacity_mw"].sum())
        template = group.iloc[0].to_dict()
        template.update(
            {
                "observation_level": "national_sum",
                "industry": "NATIONAL_SUM",
                "control_incremental_grid_capacity_mw": control,
                "mechanism_enabled_incremental_grid_capacity_mw": enabled,
                "avoided_incremental_grid_capacity_mw": effect,
                "effect_fraction_of_control": effect / control if control != 0 else np.nan,
                "weekly_service_units": float(group["weekly_service_units"].sum()),
                "production_load_mode": "mixed_30_compatibility_1_calibrated",
                "production_load_boundary_id": "mixed_registered_national_boundary",
            }
        )
        national_rows.append(template)
    result = pd.concat([result, pd.DataFrame(national_rows)], ignore_index=True)[OUTPUT_COLUMNS]
    if len(result) != expected_count * 3 + 3:
        raise ValueError("Standardized output must contain 31 industries and one national row per paired diagnostic")
    if (result["paired_diagnostics_are_additive"] != False).any():  # noqa: E712
        raise ValueError("The diagnostic non-additivity boundary was not propagated")
    if (result["mechanism_families_are_additive"] != False).any():  # noqa: E712
        raise ValueError("The mechanism-family non-additivity boundary was not propagated")

    marker = {
        "status": "validated",
        "model_version": model_version,
        "analysis_version": analysis_version,
        "effect_definition": settings["effect_definition"],
        "industry_count": expected_count,
        "mechanism_family_count": 2,
        "paired_diagnostic_count": 3,
        "industry_rows": expected_count * 3,
        "national_rows": 3,
        "paired_diagnostics_are_additive": False,
        "mechanism_families_are_additive": False,
        "non_additivity_reason": "different_paired_controls_and_counterfactual_boundaries;_the_two_within_site_diagnostics_share_one_enabled_endpoint",
        "mechanism_families": families,
        "paired_diagnostic_definitions": {
            name: {
                "architecture": contract["architecture"],
                "control_case": contract["control_case"],
                "mechanism_enabled_case": contract["mechanism_enabled_case"],
                "pairing_boundary": contract["pairing_boundary"],
            }
            for name, contract in contracts.items()
        },
        "national_summary": {
            row["paired_diagnostic"]: {
                "control_incremental_grid_capacity_mw": row[
                    "control_incremental_grid_capacity_mw"
                ],
                "mechanism_enabled_incremental_grid_capacity_mw": row[
                    "mechanism_enabled_incremental_grid_capacity_mw"
                ],
                "avoided_incremental_grid_capacity_mw": row[
                    "avoided_incremental_grid_capacity_mw"
                ],
                "effect_fraction_of_control": row["effect_fraction_of_control"],
                "positive_industry_count": int(
                    (
                        result.loc[
                            result["paired_diagnostic"].eq(row["paired_diagnostic"])
                            & result["observation_level"].eq("industry"),
                            "avoided_incremental_grid_capacity_mw",
                        ]
                        > 0
                    ).sum()
                ),
            }
            for row in national_rows
        },
        "source_files": {
            label: {"path": display_path(path), "sha256": sha256(path)}
            for label, path in source_paths.items()
        },
        "claim_boundary": settings["claim_boundary"],
        "production_load_boundary_status": core_marker[
            "production_load_boundary_status"
        ],
        "evidence_status": settings["evidence_status"],
    }
    return result, marker


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    result, marker = load_and_validate(settings)
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    marker["configuration_files"] = {
        "analysis": {"path": display_path(config_path), "sha256": sha256(config_path)},
        "defaults": {"path": display_path(defaults_path), "sha256": sha256(defaults_path)},
    }
    model_version = str(defaults["model_version"])
    results_root = project_path(defaults["paths"]["results_root"])
    output_root = results_root / model_version / settings["output_subdirectory"]
    output = args.output.resolve() if args.output else output_root / "rq2_mechanism_effects.csv"
    done_output = (
        args.done_output.resolve()
        if args.done_output
        else output_root / "rq2_mechanism_effects.validated.done.json"
    )
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "checks_passed_no_files_written",
                    "model_version": model_version,
                    "rows": len(result),
                    "national_summary": marker["national_summary"],
                    "mechanism_family_count": 2,
                    "paired_diagnostic_count": 3,
                    "paired_diagnostics_are_additive": False,
                    "mechanism_families_are_additive": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    done_output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, encoding="utf-8-sig", float_format="%.15g")
    marker["output"] = {
        "filename": output.name,
        "rows": len(result),
        "sha256": sha256(output),
    }
    done_output.write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "validated",
                "model_version": model_version,
                "output": str(output),
                "done_output": str(done_output),
                "rows": len(result),
                "mechanism_family_count": 2,
                "paired_diagnostic_count": 3,
                "paired_diagnostics_are_additive": False,
                "mechanism_families_are_additive": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
