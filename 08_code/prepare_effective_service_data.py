#!/usr/bin/env python3
"""Build the model-ready unscaled 2030 industry-task service ledger.

Purpose: Build the model-ready unscaled 2030 industry-task service ledger.

The legacy 2030 task table already embeds enterprise adoption and a simple
per-adopter growth path. This transform first reconstructs the corresponding
2023 task baseline, then applies the task-specific total-service growth factors
from the bottom-up research report. The resulting six-task values are the
architecture-invariant demand ledger itself. No national electricity target or
post-hoc scale factor is applied before the deployment architectures are run.

Workflow status: Active demand-preparation step for the v1.0.0 mainline.
Scientific boundary: The output is an architecture-invariant six-task effective-service ledger, not an electricity target.
Inputs: Industry baseline, task templates, task-growth scenarios, and explicit template fallbacks.
Outputs: Industry-task service table, scenario summary, and source-lineage metadata.
Key assumptions: Low/base/high values are evidence-constrained scenarios; adoption and growth are represented in the supplied task quantities.
Explicit exclusions: No hardware route, deployment architecture, cloud price, or post-hoc national TWh calibration is applied.
Validation/tests: Column, coverage, scenario, and reconciliation checks are performed by this script and downstream effective-service validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


TASKS = {"office", "agent", "vision", "maintenance", "scheduling", "simulation"}
CASES = ("low", "base", "high")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_columns(frame: pd.DataFrame, columns: set[str], label: str) -> None:
    missing = columns - set(frame.columns)
    if missing:
        raise ValueError(f"{label} is missing columns: {sorted(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--industry-baseline", type=Path, required=True)
    parser.add_argument("--task-templates", type=Path, required=True)
    parser.add_argument("--growth-scenarios", type=Path, required=True)
    parser.add_argument("--task-scope", type=Path, required=True)
    parser.add_argument("--template-fallbacks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--lineage-output", type=Path, required=True)
    args = parser.parse_args()

    industry = pd.read_csv(args.industry_baseline, encoding="utf-8-sig")
    templates = pd.read_csv(args.task_templates, encoding="utf-8-sig")
    growth = pd.read_csv(args.growth_scenarios, encoding="utf-8-sig")
    task_scope = pd.read_csv(args.task_scope, encoding="utf-8-sig")
    fallbacks = pd.read_csv(args.template_fallbacks, encoding="utf-8-sig")

    require_columns(
        industry,
        {
            "industry_code",
            "industry_name_cn",
            "ai_using_firms_2023",
            "adopting_firms_2030",
            "task_template",
            "sector_l20eq_gpu_h_day_2030",
        },
        "industry baseline",
    )
    require_columns(
        templates,
        {"industry_code", "year", "task_id", "sector_l20eq_gpu_h_day"},
        "task templates",
    )
    require_columns(
        growth,
        {
            "task_id",
            "task_name_cn",
            "legacy_per_adopter_growth_2023_2030",
            "growth_low",
            "growth_base",
            "growth_high",
            "evidence_status",
            "source",
        },
        "growth scenarios",
    )
    require_columns(
        task_scope,
        {
            "task_id",
            "task_name_cn",
            "core_deployment_class",
            "core_included_component",
            "excluded_k_edge_component",
            "excluded_k_pool_component",
            "local_capability_boundary",
            "evidence_basis",
            "evidence_grade",
            "status",
        },
        "task core scope",
    )
    require_columns(
        fallbacks,
        {"requested_template", "resolved_template", "evidence_status"},
        "template fallbacks",
    )
    if len(industry) != 31 or industry["industry_code"].nunique() != 31:
        raise ValueError("industry baseline must contain exactly 31 industries")
    if set(growth["task_id"]) != TASKS or len(growth) != len(TASKS):
        raise ValueError("growth scenarios must contain exactly the six core tasks")
    if set(task_scope["task_id"]) != TASKS or len(task_scope) != len(TASKS):
        raise ValueError("task core scope must contain exactly the six core tasks")
    if set(task_scope["core_deployment_class"].astype(str)) != {"K_choice"}:
        raise ValueError("the active six-task core ledger must be scoped to K_choice")

    template_rows = templates[templates["year"] == 2030].copy()
    fallback_map = dict(
        zip(fallbacks["requested_template"], fallbacks["resolved_template"])
    )
    growth_by_task = growth.set_index("task_id")
    scope_by_task = task_scope.set_index("task_id")
    records: list[dict[str, object]] = []

    for item in industry.itertuples(index=False):
        requested_template = str(item.task_template)
        resolved_template = fallback_map.get(requested_template, requested_template)
        selected = template_rows[template_rows["industry_code"] == resolved_template]
        if set(selected["task_id"]) != TASKS:
            raise ValueError(
                f"template {requested_template}->{resolved_template} does not cover six tasks"
            )
        total_template_service = float(selected["sector_l20eq_gpu_h_day"].sum())
        if total_template_service <= 0:
            raise ValueError(f"template {resolved_template} has non-positive service")
        adoption_growth = float(item.adopting_firms_2030) / float(
            item.ai_using_firms_2023
        )
        if adoption_growth <= 0:
            raise ValueError(f"{item.industry_code} has invalid adoption growth")

        for task in selected.itertuples(index=False):
            task_id = str(task.task_id)
            settings = growth_by_task.loc[task_id]
            scope = scope_by_task.loc[task_id]
            task_share = float(task.sector_l20eq_gpu_h_day) / total_template_service
            legacy_task_2030 = (
                float(item.sector_l20eq_gpu_h_day_2030) * task_share
            )
            legacy_total_growth = adoption_growth * float(
                settings.legacy_per_adopter_growth_2023_2030
            )
            reconstructed_2023 = legacy_task_2030 / legacy_total_growth
            for case in CASES:
                task_growth = float(settings[f"growth_{case}"])
                effective_service = reconstructed_2023 * task_growth
                records.append(
                    {
                        "industry_code": item.industry_code,
                        "industry_name_cn": item.industry_name_cn,
                        "year": 2030,
                        "parameter_case": case,
                        "task_id": task_id,
                        "task_name_cn": scope.task_name_cn,
                        "core_deployment_class": scope.core_deployment_class,
                        "core_included_component": scope.core_included_component,
                        "excluded_k_edge_component": scope.excluded_k_edge_component,
                        "excluded_k_pool_component": scope.excluded_k_pool_component,
                        "local_capability_boundary": scope.local_capability_boundary,
                        "scope_evidence_basis": scope.evidence_basis,
                        "scope_evidence_grade": scope.evidence_grade,
                        "scope_status": scope.status,
                        "effective_service_units_day": effective_service,
                        "structural_service_weight": effective_service,
                        "demand_scaling_factor": 1.0,
                        "demand_scaling_method": "none_bottom_up_six_task_ledger",
                        "reconstructed_2023_service_units_day": reconstructed_2023,
                        "total_service_growth_2023_2030": task_growth,
                        "legacy_2030_task_service_units_day": legacy_task_2030,
                        "legacy_total_growth_2023_2030": legacy_total_growth,
                        "template_task_share": task_share,
                        "requested_task_template": requested_template,
                        "resolved_task_template": resolved_template,
                        "service_unit": "2024_baseline_reference_workload_unit",
                        "evidence_status": settings.evidence_status,
                        "source": settings.source,
                    }
                )

    output = pd.DataFrame.from_records(records).sort_values(
        ["parameter_case", "industry_code", "task_id"]
    )
    expected_rows = 31 * len(TASKS) * len(CASES)
    if len(output) != expected_rows:
        raise ValueError(f"expected {expected_rows} output rows, found {len(output)}")
    if (output["effective_service_units_day"] <= 0).any():
        raise ValueError("effective service must be positive")
    if not output["effective_service_units_day"].equals(
        output["structural_service_weight"]
    ):
        raise AssertionError("model-ready demand must equal the unscaled structural ledger")

    summary = (
        output.groupby(
            ["parameter_case", "industry_code", "industry_name_cn"], as_index=False
        )
        .agg(
            effective_service_units_day=("effective_service_units_day", "sum"),
            reconstructed_2023_service_units_day=(
                "reconstructed_2023_service_units_day",
                "sum",
            ),
            demand_scaling_factor=("demand_scaling_factor", "first"),
            demand_scaling_method=("demand_scaling_method", "first"),
        )
        .sort_values(["parameter_case", "industry_code"])
    )
    summary["aggregate_growth_2023_2030"] = (
        summary["effective_service_units_day"]
        / summary["reconstructed_2023_service_units_day"]
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.lineage_output.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False, encoding="utf-8-sig")
    summary.to_csv(args.summary_output, index=False, encoding="utf-8-sig")
    lineage = {
        "schema_version": 3,
        "output": str(args.output),
        "formula": (
            "structural_weight_2030 = legacy_task_service_2030 / "
            "[(adopting_firms_2030 / ai_using_firms_2023) * "
            "legacy_per_adopter_growth] * task_total_service_growth"
        ),
        "inputs": {
            str(path): {"sha256": sha256(path)}
            for path in (
                args.industry_baseline,
                args.task_templates,
                args.growth_scenarios,
                args.task_scope,
                args.template_fallbacks,
            )
        },
        "rows": len(output),
        "parameter_cases": list(CASES),
        "tasks": sorted(TASKS),
        "notes": [
            "Growth factors are joint research scenarios, not observed forecasts.",
            "Four legacy auto-calibrated templates use documented structural fallbacks.",
            "The six-task values define both industry-task structure and the national service total.",
            "All six core task families are explicitly scoped to K_choice; K_edge and K_pool components are excluded from this ledger.",
            "The scope classification is author-approved but is not an empirical estimate of national K_edge/K_choice/K_pool shares.",
            "No external electricity target or post-hoc national multiplier is applied.",
            "Hardware efficiency and PUE affect reference or architecture electricity, not service demand.",
        ],
    }
    args.lineage_output.write_text(
        json.dumps(lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
