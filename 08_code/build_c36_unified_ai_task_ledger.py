#!/usr/bin/env python3
"""Build one auditable C36 task ledger shared by 100% local and 100% cloud.

The ledger separates existing effective service from its delivery route. Managed
model service plus residual CPU/GPU service always reconciles to the original
task total. RAG/agent activity and QLoRA lifecycle quantities are kept explicit
so downstream cost models cannot silently invent different demand by deployment.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
TASKS = {"office", "agent", "vision", "maintenance", "scheduling", "simulation"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario-config",
        type=Path,
        default=Path("config/demand_cases/c36_local_cloud_core_v1.yaml"),
    )
    parser.add_argument(
        "--service-input",
        type=Path,
        default=Path("02_data/processed/effective_service/manufacturing_ai_effective_service_2030.csv"),
    )
    parser.add_argument(
        "--workload-input",
        type=Path,
        default=Path("02_data/raw/curated/china_manufacturing_ai_workload_parameters.csv"),
    )
    parser.add_argument(
        "--industry-baseline",
        type=Path,
        default=Path("02_data/china_manufacturing_sector_baseline.csv"),
    )
    parser.add_argument(
        "--attribution-parameters",
        type=Path,
        default=Path(
            "02_data/manufacturing_foundation_model_task_attribution_parameters_v0.1.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("02_data/interim/c36_local_cloud_core_v1"),
    )
    return parser.parse_args()


def weighted_adoption_and_active_share(
    workload: pd.DataFrame,
    industry: str,
    task_type: str,
    case: str,
    size_weights: dict[str, float],
) -> float:
    selected = workload[
        (workload["industry_code"] == industry)
        & (workload["task_type"] == task_type)
        & (workload["scenario_year"].astype(str) == "2030")
        & (workload["scenario_level"] == case)
    ]
    by_size = {str(row.enterprise_size_class): row for row in selected.itertuples()}
    if set(by_size) != set(size_weights):
        raise ValueError(f"Missing enterprise-size rows for {industry}/{task_type}/{case}")
    return sum(
        float(size_weights[size])
        * float(by_size[size].ai_adoption_rate)
        * float(by_size[size].active_user_or_equipment_share)
        for size in size_weights
    )


def validate_config(config: dict) -> None:
    cases = set(config["workload_cases"])
    if cases != {"low", "base", "high"} or set(config["task_delivery"]) != cases:
        raise ValueError("Scenario config must contain low/base/high workload and delivery cases")
    weights = config["enterprise_size_weight"]
    if set(weights) != {"large", "sme"} or abs(sum(map(float, weights.values())) - 1.0) > 1e-9:
        raise ValueError("Enterprise-size weights must contain large/sme and sum to one")
    for case, task_map in config["task_delivery"].items():
        if set(task_map) != TASKS:
            raise ValueError(f"Delivery case {case} does not cover the six tasks")
        for task, settings in task_map.items():
            share = float(settings["managed_model_share"])
            if not 0.0 <= share <= 1.0:
                raise ValueError(f"Invalid managed-model share for {case}/{task}")
        adapted_share = float(
            config["workload_cases"][case].get(
                "qlora_adapted_inference_share_of_text_tokens", 0.0
            )
        )
        if not 0.0 <= adapted_share <= 1.0:
            raise ValueError(f"Invalid adapted-model token share for {case}")


def main() -> None:
    args = parse_args()
    config = yaml.safe_load((ROOT / args.scenario_config).read_text(encoding="utf-8"))
    validate_config(config)
    industry = str(config["industry_code"])
    year = int(config["year"])
    annual_days = 365.0

    service = pd.read_csv(ROOT / args.service_input, encoding="utf-8-sig")
    service = service[(service.industry_code == industry) & (service.year == year)]
    workload = pd.read_csv(ROOT / args.workload_input, encoding="utf-8-sig")
    baseline = pd.read_csv(ROOT / args.industry_baseline, encoding="utf-8-sig")
    attribution = pd.read_csv(
        ROOT / args.attribution_parameters, encoding="utf-8-sig"
    )
    attribution_by_scope = {
        scope: frame.set_index("task_id")
        for scope, frame in attribution.groupby("scope")
    }
    if set(attribution_by_scope) != {"foundation", "strict_llm"}:
        raise ValueError("Attribution parameters must contain foundation and strict_llm")
    for scope, frame in attribution_by_scope.items():
        if set(frame.index) != TASKS:
            raise ValueError(f"Attribution scope {scope} does not cover the six tasks")
    industry_rows = baseline[baseline.industry_code == industry]
    if len(industry_rows) != 1:
        raise ValueError(f"Expected one industry baseline row for {industry}")
    industry_row = industry_rows.iloc[0]
    employment = float(industry_row.employment_2023_10k_person) * 10_000.0
    enterprises = float(industry_row.enterprise_units_2023_10k) * 10_000.0
    weights = {key: float(value) for key, value in config["enterprise_size_weight"].items()}

    task_rows: list[dict[str, object]] = []
    lifecycle_rows: list[dict[str, object]] = []
    for case in ("low", "base", "high"):
        case_service = service[service.parameter_case == case].copy()
        if set(case_service.task_id) != TASKS:
            raise ValueError(f"Service case {case} does not cover the six tasks")
        values = config["workload_cases"][case]
        delivery = config["task_delivery"][case]
        adapted_text_share = float(
            values.get("qlora_adapted_inference_share_of_text_tokens", 0.0)
        )

        office_active = weighted_adoption_and_active_share(
            workload, industry, "office_rag_copilot", case, weights
        )
        agent_active = weighted_adoption_and_active_share(
            workload, industry, "business_agent", case, weights
        )
        rag_tasks_day = employment * office_active * float(values["rag_tasks_per_active_user_day"])
        rag_calls_day = rag_tasks_day
        rag_input_day = rag_calls_day * float(values["rag_input_tokens_per_call"])
        rag_output_day = rag_calls_day * float(values["rag_output_tokens_per_call"])
        agent_workflows_day = employment * agent_active * float(values["agent_workflows_per_active_user_day"])
        agent_steps_day = (
            agent_workflows_day
            * float(values["agent_model_steps_per_workflow"])
            * (1.0 + float(values["agent_retry_fraction"]))
        )
        agent_input_day = agent_steps_day * float(values["agent_input_tokens_per_step"])
        agent_output_day = agent_steps_day * float(values["agent_output_tokens_per_step"])

        for row in case_service.itertuples(index=False):
            task = str(row.task_id)
            total_service = float(row.effective_service_units_day)
            managed_share = float(delivery[task]["managed_model_share"])
            registered_foundation_share = float(
                attribution_by_scope["foundation"].loc[task, case]
            )
            if abs(managed_share - registered_foundation_share) > 1e-12:
                raise ValueError(
                    f"Delivery share for {case}/{task} does not match registered foundation attribution"
                )
            strict_llm_share = float(
                attribution_by_scope["strict_llm"].loc[task, case]
            )
            managed_service = total_service * managed_share
            strict_llm_service = total_service * strict_llm_share
            residual_service = total_service - managed_service
            if task == "office":
                calls_day, input_day, output_day = rag_calls_day, rag_input_day, rag_output_day
            elif task == "agent":
                calls_day, input_day, output_day = agent_steps_day, agent_input_day, agent_output_day
            else:
                calls_day = managed_service * float(delivery[task]["calls_per_managed_service_unit"])
                input_day = calls_day * float(delivery[task]["input_tokens_per_call"])
                output_day = calls_day * float(delivery[task]["output_tokens_per_call"])
            task_adapted_share = 0.0 if task == "vision" else adapted_text_share
            adapted_input_day = input_day * task_adapted_share
            adapted_output_day = output_day * task_adapted_share
            task_rows.append(
                {
                    "scenario_version": config["scenario_version"],
                    "industry_code": industry,
                    "industry_name_cn": industry_row.industry_name_cn,
                    "year": year,
                    "parameter_case": case,
                    "task_id": task,
                    "task_name_cn": row.task_name_cn,
                    "effective_service_units_day": total_service,
                    "managed_model_share": managed_share,
                    "managed_model_service_units_day": managed_service,
                    "strict_llm_share": strict_llm_share,
                    "strict_llm_service_units_day": strict_llm_service,
                    "residual_cpu_gpu_service_units_day": residual_service,
                    "model_calls_day": calls_day,
                    "input_tokens_day": input_day,
                    "output_tokens_day": output_day,
                    "annual_input_tokens": input_day * annual_days,
                    "annual_output_tokens": output_day * annual_days,
                    "adapted_model_token_share": task_adapted_share,
                    "annual_adapted_model_input_tokens": adapted_input_day
                    * annual_days,
                    "annual_adapted_model_output_tokens": adapted_output_day
                    * annual_days,
                    "annual_generic_model_input_tokens": (
                        input_day - adapted_input_day
                    )
                    * annual_days,
                    "annual_generic_model_output_tokens": (
                        output_day - adapted_output_day
                    )
                    * annual_days,
                    "strict_llm_or_vlm_service": task in {"office", "agent", "vision"},
                    "evidence_status": "evidence_bounded_scenario_not_observed_c36_mean",
                }
            )

        adopting_llm_enterprises = enterprises * office_active
        knowledge_bases = (
            adopting_llm_enterprises
            * float(values["rag_knowledge_bases_per_adopting_enterprise"])
        )
        corpus_tokens = knowledge_bases * float(values["rag_corpus_tokens_per_knowledge_base"])
        annual_refresh_tokens = (
            corpus_tokens * float(values["rag_monthly_refresh_fraction"]) * 12.0
        )
        qlora_adopters = (
            adopting_llm_enterprises
            * float(values["qlora_adoption_fraction_of_llm_enterprises"])
        )
        qlora_training_tokens = (
            qlora_adopters
            * float(values["qlora_models_per_adopter"])
            * float(values["qlora_updates_per_model_year"])
            * float(values["qlora_dataset_tokens_per_update"])
            * float(values["qlora_epochs"])
        )
        lifecycle_rows.extend(
            [
                {
                    "scenario_version": config["scenario_version"],
                    "industry_code": industry,
                    "parameter_case": case,
                    "component": "rag_knowledge_base",
                    "adopting_enterprises": adopting_llm_enterprises,
                    "quantity": knowledge_bases,
                    "unit": "knowledge_bases",
                    "annual_tokens": corpus_tokens + annual_refresh_tokens,
                    "cost_inclusion_status": "ready_for_cloud_kb_embedding_cost_not_yet_local_storage_sized",
                },
                {
                    "scenario_version": config["scenario_version"],
                    "industry_code": industry,
                    "parameter_case": case,
                    "component": "agent_tool_calls",
                    "adopting_enterprises": enterprises * agent_active,
                    "quantity": agent_workflows_day
                    * float(values["agent_tool_calls_per_workflow"])
                    * annual_days,
                    "unit": "tool_calls_per_year",
                    "annual_tokens": 0.0,
                    "cost_inclusion_status": "ready_for_tool_price_sensitivity",
                },
                {
                    "scenario_version": config["scenario_version"],
                    "industry_code": industry,
                    "parameter_case": case,
                    "component": "agent_runtime",
                    "adopting_enterprises": enterprises * agent_active,
                    "quantity": agent_workflows_day
                    * float(values["agent_session_minutes_per_workflow"])
                    / 60.0
                    * annual_days,
                    "unit": "session_hours_per_year",
                    "annual_tokens": 0.0,
                    "cost_inclusion_status": "ready_for_managed_agent_runtime_cost",
                },
                {
                    "scenario_version": config["scenario_version"],
                    "industry_code": industry,
                    "parameter_case": case,
                    "component": "qlora_sft_training",
                    "adopting_enterprises": qlora_adopters,
                    "quantity": qlora_adopters
                    * float(values["qlora_models_per_adopter"])
                    * float(values["qlora_updates_per_model_year"]),
                    "unit": "model_updates_per_year",
                    "annual_tokens": qlora_training_tokens,
                    "cost_inclusion_status": "ready_for_symmetric_local_gpu_hour_and_cloud_token_cost",
                },
            ]
        )

    task_frame = pd.DataFrame(task_rows)
    lifecycle_frame = pd.DataFrame(lifecycle_rows)
    attribution_summary = (
        task_frame.groupby("parameter_case", as_index=False)
        .agg(
            effective_service_units_day=("effective_service_units_day", "sum"),
            foundation_model_service_units_day=("managed_model_service_units_day", "sum"),
            strict_llm_service_units_day=("strict_llm_service_units_day", "sum"),
        )
        .assign(
            foundation_model_service_share=lambda x: (
                x.foundation_model_service_units_day / x.effective_service_units_day
            ),
            strict_llm_service_share=lambda x: (
                x.strict_llm_service_units_day / x.effective_service_units_day
            ),
            evidence_status="exploratory_attribution_scenario_not_observed_C36_mean",
        )
    )
    reconciliation = task_frame.assign(
        reconstructed_service_units_day=(
            task_frame.managed_model_service_units_day
            + task_frame.residual_cpu_gpu_service_units_day
        ),
        reconciliation_error=lambda x: (
            x.reconstructed_service_units_day - x.effective_service_units_day
        ),
    )
    if reconciliation.reconciliation_error.abs().max() > 1e-6:
        raise AssertionError("Managed and residual service do not reconcile")
    if (task_frame[["model_calls_day", "input_tokens_day", "output_tokens_day"]] < 0).any().any():
        raise AssertionError("Negative workload quantity")
    for direction in ("input", "output"):
        error = (
            task_frame[f"annual_generic_model_{direction}_tokens"]
            + task_frame[f"annual_adapted_model_{direction}_tokens"]
            - task_frame[f"annual_{direction}_tokens"]
        ).abs()
        scale = task_frame[f"annual_{direction}_tokens"].abs().clip(lower=1.0)
        if (error / scale).max() > 1e-12:
            raise AssertionError(f"Generic and adapted {direction} tokens do not reconcile")

    args.output_dir = ROOT / args.output_dir
    args.output_dir.mkdir(parents=True, exist_ok=True)
    task_frame.to_csv(args.output_dir / "task_ledger.csv", index=False, encoding="utf-8-sig")
    lifecycle_frame.to_csv(args.output_dir / "lifecycle_ledger.csv", index=False, encoding="utf-8-sig")
    attribution_summary.to_csv(
        args.output_dir / "task_attribution_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )
    reconciliation.to_csv(args.output_dir / "service_reconciliation.csv", index=False, encoding="utf-8-sig")
    payload = {
        "status": "validated_shared_demand_ledger_screening_parameters",
        "scenario_version": config["scenario_version"],
        "industry_code": industry,
        "task_rows": len(task_frame),
        "lifecycle_rows": len(lifecycle_frame),
        "parameter_cases": sorted(task_frame.parameter_case.unique()),
        "maximum_service_reconciliation_error": float(
            reconciliation.reconciliation_error.abs().max()
        ),
        "same_ledger_required_for_local_and_cloud": True,
        "manuscript_or_national_outputs_modified": False,
        "lifecycle_boundary": "QLoRA training and adapted-model inference tokens are quantified here; the cost runner applies symmetric local GPU-hour and cloud training-price conversions and replaces generic API pricing for adapted tokens",
    }
    (args.output_dir / "validated.done.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
