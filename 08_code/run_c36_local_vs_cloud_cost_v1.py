#!/usr/bin/env python3
"""Compare 100% owned and 100% cloud delivery for the same C36 ledger.

This is a single-industry screening model. It reads existing jointly solved
local physical costs, re-optimizes residual cloud CPU/GPU capacity by task and
deadline, and adds explicit managed-model, RAG, agent and symmetric QLoRA costs.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.config import load_config  # noqa: E402
from core.data import load_industry_inputs  # noqa: E402
from run_single_industry_heterogeneous_hardware_screen import (  # noqa: E402
    annual_hardware_cost,
    minimize_peak,
)


TASKS = {"office", "agent", "vision", "maintenance", "scheduling", "simulation"}
LOCAL_ARCHITECTURES = ("PF", "SHG", "MSG")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--defaults", type=Path, default=Path("config/defaults.yaml"))
    parser.add_argument("--run-config", type=Path, default=Path("config/runs/single_industry_core.yaml"))
    parser.add_argument("--routing-config", type=Path, default=Path("config/compute_hardware/cpu_gpu_routing_v1.yaml"))
    parser.add_argument("--scenario-config", type=Path, default=Path("config/demand_cases/c36_local_cloud_core_v1.yaml"))
    parser.add_argument("--task-ledger", type=Path, default=Path("02_data/interim/c36_local_cloud_core_v1/task_ledger.csv"))
    parser.add_argument("--lifecycle-ledger", type=Path, default=Path("02_data/interim/c36_local_cloud_core_v1/lifecycle_ledger.csv"))
    parser.add_argument("--local-summary", type=Path)
    parser.add_argument("--api-prices", type=Path, default=Path("02_data/processed/api_token_cost/api_token_prices_v1_1.csv"))
    parser.add_argument(
        "--lifecycle-parameters",
        type=Path,
        default=Path("02_data/enterprise_llm_lifecycle_parameters.csv"),
    )
    parser.add_argument("--parameter-case", choices=("low", "base", "high"), default="base")
    parser.add_argument("--output-dir", type=Path, default=Path("05_results/v1.0.0/result/cost_benchmark/c36_local_vs_cloud_v1"))
    return parser.parse_args()


def bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def selected_text_prices(prices: pd.DataFrame) -> pd.DataFrame:
    active = prices[
        prices.active_for_baseline.map(bool_value)
        & prices.provider.isin(["Alibaba Cloud", "DeepSeek"])
    ].copy()
    alibaba = active[
        (active.provider == "Alibaba Cloud")
        & active.mainstream_representative.map(bool_value)
    ]
    deepseek = active[
        (active.provider == "DeepSeek")
        & active.mainstream_representative.map(bool_value)
    ]
    if len(alibaba) != 1 or len(deepseek) != 1:
        raise ValueError("Expected one active mainstream Alibaba and DeepSeek text model")
    return pd.concat([alibaba, deepseek], ignore_index=True)


def text_api_cost(task: pd.DataFrame, price: pd.Series) -> float:
    text = task[task.task_id != "vision"]
    fx = float(price.fx_to_cny)
    input_column = (
        "annual_generic_model_input_tokens"
        if "annual_generic_model_input_tokens" in text.columns
        else "annual_input_tokens"
    )
    output_column = (
        "annual_generic_model_output_tokens"
        if "annual_generic_model_output_tokens" in text.columns
        else "annual_output_tokens"
    )
    return (
        float(text[input_column].sum()) / 1e6 * float(price.input_per_mtoken)
        + float(text[output_column].sum()) / 1e6 * float(price.output_per_mtoken)
    ) * fx


def adapted_model_api_cost(task: pd.DataFrame, managed_prices: dict) -> float:
    if "annual_adapted_model_input_tokens" not in task.columns:
        return 0.0
    return (
        float(task.annual_adapted_model_input_tokens.sum())
        / 1e6
        * float(managed_prices.get("qlora_inference_input_rmb_per_million_tokens", 0.0))
        + float(task.annual_adapted_model_output_tokens.sum())
        / 1e6
        * float(managed_prices.get("qlora_inference_output_rmb_per_million_tokens", 0.0))
    )


def load_local_cost_rows(
    root: Path,
    scenario: dict,
    industry: str,
    case: str,
    override_path: Path | None,
) -> pd.DataFrame:
    source = scenario["local_cost_sources"][case]
    source_format = str(source["format"])
    source_path = override_path or Path(str(source["path"]))
    local = pd.read_csv(root / source_path, encoding="utf-8-sig")
    if source_format == "national_detail":
        local = local[
            (local.industry_code == industry) & (local.base_load_case == "actual_load")
        ].copy()
        return local
    if source_format != "representative_group_summary":
        raise ValueError(f"Unsupported local cost source format: {source_format}")
    local = local[
        (local.industry == industry) & (local.base_load_case == "actual_load")
    ].copy()
    if len(local) == 0:
        raise ValueError(f"No local {case} rows found for {industry}")
    share = local.ai_service_group_share.astype(float)
    if (share <= 0).any():
        raise ValueError("Representative-group service share must be positive")
    local["industry_daily_effective_service_units"] = (
        local.weekly_service_units.astype(float) / share / 7.0
    )
    for column in (
        "annual_incremental_total_cost_rmb",
        "installed_gpu_server_groups",
        "average_required_gpu_server_groups",
    ):
        local[f"industry_equivalent_{column}"] = local[column].astype(float) / share
    local = local.rename(
        columns={
            "industry_equivalent_annual_incremental_total_cost_rmb":
                "industry_equivalent_incremental_total_cost_rmb"
        }
    )
    return local


def main() -> None:
    args = parse_args()
    defaults = load_config(ROOT, args.defaults, args.run_config)
    routing = yaml.safe_load((ROOT / args.routing_config).read_text(encoding="utf-8"))
    scenario = yaml.safe_load((ROOT / args.scenario_config).read_text(encoding="utf-8"))
    industry = str(scenario["industry_code"])
    case = args.parameter_case
    task = pd.read_csv(ROOT / args.task_ledger, encoding="utf-8-sig")
    task = task[(task.industry_code == industry) & (task.parameter_case == case)].copy()
    lifecycle = pd.read_csv(ROOT / args.lifecycle_ledger, encoding="utf-8-sig")
    lifecycle = lifecycle[(lifecycle.industry_code == industry) & (lifecycle.parameter_case == case)].copy()
    if set(task.task_id) != TASKS or len(task) != 6:
        raise ValueError("C36 task ledger must contain the six base-case tasks")
    if (
        task.managed_model_service_units_day
        + task.residual_cpu_gpu_service_units_day
        - task.effective_service_units_day
    ).abs().max() > 1e-6:
        raise AssertionError("Task service does not reconcile before costing")

    inputs = load_industry_inputs(defaults, industry)
    route_case = str(routing["active_core_routing_case"])
    cpu_share = {task_id: float(routing["routing_cases"][route_case].get(task_id, 0.0)) for task_id in TASKS}
    residual_share = task.set_index("task_id").residual_cpu_gpu_service_units_day.div(
        task.set_index("task_id").effective_service_units_day
    ).to_dict()
    cloud_cpu_fraction = {task_id: residual_share[task_id] * cpu_share[task_id] for task_id in TASKS}
    cloud_gpu_fraction = {task_id: residual_share[task_id] * (1.0 - cpu_share[task_id]) for task_id in TASKS}
    reference_compute_per_service = float(inputs.reference_compute_h_per_service_unit)
    multipliers = routing["core_cpu_server_hour_per_reference_compute_hour"]
    gpu_compute_factor = {task_id: reference_compute_per_service for task_id in TASKS}
    cpu_compute_factor = {
        task_id: reference_compute_per_service * float(multipliers.get(task_id, 1.0))
        for task_id in TASKS
    }
    _, cloud_gpu_peak, _ = minimize_peak(inputs, cloud_gpu_fraction, 1.0, gpu_compute_factor)

    gpu_group_capacity = float(defaults["server"]["accelerators_per_server"])
    cloud_gpu_groups = math.ceil(cloud_gpu_peak / gpu_group_capacity)
    gpu_case = str(defaults["full_cloud_cost"]["main_gpu_price_case"])
    cpu_case = str(defaults["full_cloud_cost"]["main_cpu_price_case"])
    price_column = {"low": "low_value", "base": "base_value", "high": "high_value"}[gpu_case]
    cost_parameters = pd.read_csv(
        ROOT / defaults["paths"]["enterprise_ai_cost_parameters"], encoding="utf-8-sig"
    )
    gpu_unit_price = float(
        cost_parameters.loc[cost_parameters.parameter_id == "C19", price_column].iloc[0]
    )
    gpu_capacity_cost = cloud_gpu_groups * gpu_unit_price

    if "cloud_cpu_products" in routing:
        cpu_products = routing["cloud_cpu_products"]
        product_by_task = routing["cloud_cpu_product_by_task"]
    else:
        cpu_products = {"ecs_reserved": routing["cloud_cpu"]}
        product_by_task = {task_id: "ecs_reserved" for task_id in TASKS}
    unknown_products = set(product_by_task.values()) - set(cpu_products)
    if unknown_products:
        raise ValueError(f"Unknown cloud CPU products in task routing: {unknown_products}")
    cpu_product_results: dict[str, dict[str, float]] = {}
    for product_name, product_settings in cpu_products.items():
        product_fraction = {
            task_id: (
                cloud_cpu_fraction[task_id]
                if product_by_task.get(task_id) == product_name
                else 0.0
            )
            for task_id in TASKS
        }
        _, product_peak, _ = minimize_peak(
            inputs, product_fraction, 1.0, cpu_compute_factor
        )
        capacity = float(
            product_settings["service_capacity_relative_to_local_cpu_server"]
        )
        price_cases = product_settings.get("annual_price_cases_rmb") or product_settings.get(
            "annual_reserved_price_cases_rmb"
        )
        unit_price = float(price_cases[cpu_case])
        groups = math.ceil(product_peak / capacity) if product_peak > 0 else 0
        cpu_product_results[product_name] = {
            "peak": product_peak,
            "capacity": capacity,
            "groups": groups,
            "unit_price": unit_price,
            "annual_cost": groups * unit_price,
        }
    cloud_cpu_peak = sum(row["peak"] for row in cpu_product_results.values())
    cloud_cpu_groups = int(sum(row["groups"] for row in cpu_product_results.values()))
    cpu_capacity_cost = sum(row["annual_cost"] for row in cpu_product_results.values())

    managed_prices = scenario["cloud_managed_service_prices"]
    rag = lifecycle[lifecycle.component == "rag_knowledge_base"].iloc[0]
    agent_tools = lifecycle[lifecycle.component == "agent_tool_calls"].iloc[0]
    agent_runtime = lifecycle[lifecycle.component == "agent_runtime"].iloc[0]
    qlora = lifecycle[lifecycle.component == "qlora_sft_training"].iloc[0]
    office = task[task.task_id == "office"].iloc[0]
    vision = task[task.task_id == "vision"].iloc[0]
    kb_runtime_cost = (
        float(rag.quantity)
        * float(managed_prices["knowledge_base_runtime_rmb_per_kb_hour"])
        * 8760.0
    )
    embedding_cost = (
        float(rag.annual_tokens)
        / 1e6
        * float(managed_prices["embedding_rmb_per_million_tokens"])
    )
    rerank_cost = (
        float(office.annual_input_tokens)
        / 1e6
        * float(managed_prices["rerank_rmb_per_million_tokens"])
    )
    vlm_api_cost = (
        float(vision.annual_input_tokens)
        / 1e6
        * float(managed_prices["vlm_input_rmb_per_million_tokens"])
        + float(vision.annual_output_tokens)
        / 1e6
        * float(managed_prices["vlm_output_rmb_per_million_tokens"])
    )
    qlora_cloud_training_cost = (
        float(qlora.annual_tokens)
        / 1000.0
        * float(managed_prices["qlora_training_rmb_per_thousand_tokens"])
    )
    qlora_adapted_inference_cost = adapted_model_api_cost(task, managed_prices)

    lifecycle_parameters = pd.read_csv(
        ROOT / args.lifecycle_parameters, encoding="utf-8-sig"
    )
    conversion = scenario["local_lifecycle_conversion"]
    qlora_parameter = lifecycle_parameters[
        lifecycle_parameters.parameter_id
        == str(conversion["qlora_gpu_hours_parameter_id"])
    ]
    if len(qlora_parameter) != 1:
        raise ValueError("Expected one QLoRA GPU-hour lifecycle parameter")
    qlora_gpu_hours_case = str(conversion["qlora_gpu_hours_case"])
    qlora_reference_gpu_h = float(qlora_parameter.iloc[0][qlora_gpu_hours_case])
    qlora_reference_training_tokens = float(
        conversion["qlora_reference_training_tokens"]
    )
    qlora_annual_gpu_h = (
        float(qlora.annual_tokens)
        / qlora_reference_training_tokens
        * qlora_reference_gpu_h
    )
    corpus_tokens = (
        float(rag.quantity)
        * float(scenario["workload_cases"][case]["rag_corpus_tokens_per_knowledge_base"])
    )
    local_rag_required_gb = (
        corpus_tokens
        * float(conversion["rag_storage_bytes_per_corpus_token"])
        * float(conversion["rag_storage_copy_equivalents"])
        / 1e9
    )
    bundled_storage_parameter = lifecycle_parameters[
        lifecycle_parameters.parameter_id
        == str(conversion["bundled_storage_parameter_id"])
    ]
    if len(bundled_storage_parameter) != 1:
        raise ValueError("Expected one bundled-storage lifecycle parameter")
    bundled_storage_gb_per_gpu_group = float(bundled_storage_parameter.iloc[0][case]) * 1000.0

    api_prices = selected_text_prices(pd.read_csv(ROOT / args.api_prices, encoding="utf-8-sig"))
    configured_agent_archetypes = scenario.get("cloud_agent_delivery_archetypes")
    if configured_agent_archetypes:
        agent_archetypes = configured_agent_archetypes
    else:
        agent_archetypes = {
            "": {
                "session_runtime_rmb_per_hour": managed_prices[
                    "agent_runtime_rmb_per_session_hour"
                ],
                "custom_mcp_seconds_per_tool_call": 0.0,
                "custom_mcp_rmb_per_invocation_second": 0.0,
            }
        }
    component_rows: list[dict[str, object]] = []
    provider_totals: dict[str, float] = {}
    bundle_metadata: dict[str, dict[str, str]] = {}
    for price in api_prices.itertuples(index=False):
        price_series = pd.Series(price._asdict())
        text_cost = text_api_cost(task, price_series)
        for archetype_name, archetype in agent_archetypes.items():
            provider_bundle = (
                str(price.provider)
                if not archetype_name
                else f"{price.provider} | {archetype_name}"
            )
            bundle_metadata[provider_bundle] = {
                "model_price_provider": str(price.provider),
                "agent_delivery_archetype": archetype_name
                or "legacy_managed_agent",
            }
            agent_runtime_cost = float(agent_runtime.quantity) * float(
                archetype["session_runtime_rmb_per_hour"]
            )
            mcp_runtime_cost = (
                float(agent_tools.quantity)
                * float(archetype["custom_mcp_seconds_per_tool_call"])
                * float(archetype["custom_mcp_rmb_per_invocation_second"])
            )
            components = {
                "text_llm_api_generic": text_cost,
                "qlora_adapted_model_inference": qlora_adapted_inference_cost,
                "vlm_api": vlm_api_cost,
                "rag_knowledge_base_runtime": kb_runtime_cost,
                "rag_embedding": embedding_cost,
                "rag_rerank": rerank_cost,
                "agent_runtime": agent_runtime_cost,
                "custom_mcp_runtime": mcp_runtime_cost,
                "residual_gpu_reserved_capacity": gpu_capacity_cost,
            }
            for product_name, product in cpu_product_results.items():
                components[f"residual_cpu_{product_name}_capacity"] = product[
                    "annual_cost"
                ]
            components["qlora_sft_training"] = qlora_cloud_training_cost
            total = sum(components.values())
            provider_totals[provider_bundle] = total
            for component, value in components.items():
                if component == "qlora_sft_training":
                    double_counting_rule = (
                        "cloud_training_token_fee_replaces_cloud_training_gpu_capacity"
                    )
                elif component == "qlora_adapted_model_inference":
                    double_counting_rule = (
                        "adapted_tokens_removed_from_generic_API_before_LoRA_price"
                    )
                elif component == "custom_mcp_runtime":
                    double_counting_rule = (
                        "MCP_wrapper_only_external_tool_compute_and_API_fees_excluded"
                    )
                else:
                    double_counting_rule = (
                        "managed_model_service_excluded_from_residual_capacity"
                    )
                component_rows.append(
                    {
                        "scenario_version": scenario["scenario_version"],
                        "industry_code": industry,
                        "parameter_case": case,
                        "provider_bundle": provider_bundle,
                        "model_price_provider": price.provider,
                        "agent_delivery_archetype": archetype_name
                        or "legacy_managed_agent",
                        "component": component,
                        "annual_cost_rmb": value,
                        "included_in_core_total": True,
                        "double_counting_rule": double_counting_rule,
                    }
                )

    local = load_local_cost_rows(
        ROOT, scenario, industry, case, args.local_summary
    )
    expected_architectures = set(LOCAL_ARCHITECTURES) if case == "base" else {"SHG"}
    if set(local.architecture) != expected_architectures:
        raise ValueError(
            f"Local C36 {case} summary must contain {sorted(expected_architectures)}"
        )
    comparison_rows: list[dict[str, object]] = []
    ledger_service = float(task.effective_service_units_day.sum())
    local_lifecycle_rows: list[dict[str, object]] = []
    for local_row in local.itertuples(index=False):
        local_service = float(local_row.industry_daily_effective_service_units)
        if abs(local_service - ledger_service) > 1e-6:
            raise AssertionError(
                f"Local industry-equivalent service {local_service} does not match ledger {ledger_service}"
            )
        local_core_cost = float(local_row.industry_equivalent_incremental_total_cost_rmb)
        installed_gpu_groups = float(
            local_row.industry_equivalent_installed_gpu_server_groups
        )
        average_gpu_groups = float(
            local_row.industry_equivalent_average_required_gpu_server_groups
        )
        spare_gpu_h = max(0.0, installed_gpu_groups - average_gpu_groups) * 2.0 * 8760.0
        uncovered_gpu_h = max(0.0, qlora_annual_gpu_h - spare_gpu_h)
        training_reserve = float(
            conversion["additional_training_capacity_reserve_fraction"]
        )
        additional_gpu_groups = (
            uncovered_gpu_h
            / (2.0 * 8760.0)
            / (1.0 - training_reserve)
        )
        qlora_hardware_cost = annual_hardware_cost(
            defaults["server"], additional_gpu_groups, float(defaults["model"]["discount_rate"])
        )
        qlora_dynamic_kwh_per_gpu_h = (
            float(defaults["server"]["marginal_facility_multiplier"])
            * (
                float(defaults["server"]["maximum_wall_power_kw"])
                - float(defaults["server"]["online_idle_wall_power_kw"])
            )
            / float(defaults["server"]["accelerators_per_server"])
        )
        qlora_energy_kwh = qlora_annual_gpu_h * qlora_dynamic_kwh_per_gpu_h
        qlora_energy_cost = qlora_energy_kwh * float(
            defaults["energy"]["flat_grid_energy_rmb_per_kwh"]
        )
        local_rag_available_gb = installed_gpu_groups * bundled_storage_gb_per_gpu_group
        if local_rag_required_gb > local_rag_available_gb + 1e-6:
            raise ValueError(
                "C36 RAG corpus exceeds bundled local storage; incremental storage price is required"
            )
        local_rag_incremental_storage_cost = 0.0
        local_cost = (
            local_core_cost
            + qlora_hardware_cost
            + qlora_energy_cost
            + local_rag_incremental_storage_cost
        )
        local_lifecycle_rows.append(
            {
                "local_architecture": local_row.architecture,
                "qlora_model_updates_per_year": float(qlora.quantity),
                "qlora_reference_training_tokens": qlora_reference_training_tokens,
                "qlora_reference_gpu_h": qlora_reference_gpu_h,
                "qlora_gpu_hours_case": qlora_gpu_hours_case,
                "qlora_annual_gpu_h": qlora_annual_gpu_h,
                "existing_spare_gpu_h": spare_gpu_h,
                "additional_gpu_groups": additional_gpu_groups,
                "qlora_incremental_energy_kwh": qlora_energy_kwh,
                "qlora_incremental_energy_cost_rmb": qlora_energy_cost,
                "qlora_incremental_hardware_cost_rmb": qlora_hardware_cost,
                "rag_required_storage_gb": local_rag_required_gb,
                "rag_available_bundled_storage_gb": local_rag_available_gb,
                "rag_incremental_storage_cost_rmb": local_rag_incremental_storage_cost,
            }
        )
        for provider, cloud_cost in provider_totals.items():
            metadata = bundle_metadata[provider]
            comparison_rows.append(
                {
                    "scenario_version": scenario["scenario_version"],
                    "industry_code": industry,
                    "parameter_case": case,
                    "local_architecture": local_row.architecture,
                    "provider_bundle": provider,
                    "model_price_provider": metadata["model_price_provider"],
                    "agent_delivery_archetype": metadata[
                        "agent_delivery_archetype"
                    ],
                    "same_effective_service_units_day": ledger_service,
                    "local_service_share": 1.0,
                    "cloud_service_share": 1.0,
                    "annual_100pct_local_cost_rmb": local_cost,
                    "annual_100pct_local_core_cost_before_new_lifecycle_rmb": local_core_cost,
                    "local_qlora_incremental_cost_rmb": qlora_hardware_cost + qlora_energy_cost,
                    "local_rag_incremental_storage_cost_rmb": local_rag_incremental_storage_cost,
                    "annual_100pct_cloud_cost_rmb": cloud_cost,
                    "cloud_to_local_cost_ratio": cloud_cost / local_cost,
                    "local_savings_vs_cloud_fraction": 1.0 - local_cost / cloud_cost,
                    "cloud_gpu_reserved_groups": cloud_gpu_groups,
                    "cloud_cpu_reserved_groups": cloud_cpu_groups,
                    "qlora_cloud_training_cost_included_rmb": qlora_cloud_training_cost,
                    "qlora_adapted_inference_cost_included_rmb": qlora_adapted_inference_cost,
                    "result_status": "single_industry_screening_not_scientific_main_result",
                }
            )

    comparison = pd.DataFrame(comparison_rows)
    components = pd.DataFrame(component_rows)
    included = components[components.included_in_core_total]
    reconstructed = included.groupby("provider_bundle").annual_cost_rmb.sum().to_dict()
    for provider, total in provider_totals.items():
        if abs(reconstructed[provider] - total) > max(1e-3, abs(total) * 1e-12):
            raise AssertionError(f"Cloud components do not reconcile for {provider}")
    if not (task.managed_model_share.between(0, 1).all()):
        raise AssertionError("Managed-model share outside [0,1]")

    output_dir = ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output_dir / "comparison.csv", index=False, encoding="utf-8-sig")
    components.to_csv(output_dir / "cloud_cost_components.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(local_lifecycle_rows).to_csv(
        output_dir / "local_lifecycle_components.csv", index=False, encoding="utf-8-sig"
    )
    routing_rows = [
        {
            "task_id": task_id,
            "managed_model_share": 1.0 - residual_share[task_id],
            "residual_service_share": residual_share[task_id],
            "residual_cpu_share_of_total_task_service": cloud_cpu_fraction[task_id],
            "residual_gpu_share_of_total_task_service": cloud_gpu_fraction[task_id],
            "cloud_cpu_product": product_by_task.get(task_id, "none")
            if cloud_cpu_fraction[task_id] > 0
            else "none",
        }
        for task_id in sorted(TASKS)
    ]
    pd.DataFrame(routing_rows).to_csv(
        output_dir / "cloud_task_routing.csv", index=False, encoding="utf-8-sig"
    )
    cpu_product_rows = [
        {
            "cloud_cpu_product": product_name,
            "cloud_cpu_peak_local_server_equivalents": product["peak"],
            "service_capacity_relative_to_local_server": product["capacity"],
            "cloud_cpu_groups": product["groups"],
            "annual_unit_price_rmb": product["unit_price"],
            "annual_capacity_cost_rmb": product["annual_cost"],
            "routed_tasks": "|".join(
                sorted(
                    task_id
                    for task_id, routed_product in product_by_task.items()
                    if routed_product == product_name
                    and cloud_cpu_fraction.get(task_id, 0.0) > 0
                )
            ),
        }
        for product_name, product in cpu_product_results.items()
    ]
    pd.DataFrame(cpu_product_rows).to_csv(
        output_dir / "cloud_cpu_product_capacity.csv",
        index=False,
        encoding="utf-8-sig",
    )
    cpu_sensitivity_rows: list[dict[str, object]] = []
    for capacity in map(
        float,
        scenario["cloud_cpu_capacity_sensitivity_relative_to_local_64core_server"],
    ):
        sensitivity_product_groups = {
            name: math.ceil(product["peak"] / capacity)
            if product["peak"] > 0
            else 0
            for name, product in cpu_product_results.items()
        }
        cpu_groups = sum(sensitivity_product_groups.values())
        cpu_cost = sum(
            sensitivity_product_groups[name] * product["unit_price"]
            for name, product in cpu_product_results.items()
        )
        for provider, base_total in provider_totals.items():
            cloud_cost = base_total - cpu_capacity_cost + cpu_cost
            for local_row in comparison[
                comparison.provider_bundle == provider
            ].itertuples(index=False):
                cpu_sensitivity_rows.append(
                    {
                        "provider_bundle": provider,
                        "local_architecture": local_row.local_architecture,
                        "cloud_cpu_capacity_relative_to_local_server": capacity,
                        "cloud_cpu_reserved_groups": cpu_groups,
                        "cloud_cpu_groups_by_product": json.dumps(
                            sensitivity_product_groups,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        "cloud_cpu_annual_cost_rmb": cpu_cost,
                        "annual_100pct_cloud_cost_rmb": cloud_cost,
                        "annual_100pct_local_cost_rmb": local_row.annual_100pct_local_cost_rmb,
                        "cloud_to_local_cost_ratio": cloud_cost
                        / local_row.annual_100pct_local_cost_rmb,
                    }
                )
    pd.DataFrame(cpu_sensitivity_rows).to_csv(
        output_dir / "cloud_cpu_capacity_sensitivity.csv",
        index=False,
        encoding="utf-8-sig",
    )
    cpu_break_even_rows: list[dict[str, object]] = []
    cpu_continuous_cost_numerator = sum(
        product["peak"] * product["unit_price"]
        for product in cpu_product_results.values()
    )
    for row in comparison.itertuples(index=False):
        non_cpu_cloud_cost = (
            float(row.annual_100pct_cloud_cost_rmb) - cpu_capacity_cost
        )
        affordable_cpu_cost = (
            float(row.annual_100pct_local_cost_rmb) - non_cpu_cloud_cost
        )
        if affordable_cpu_cost <= 0:
            break_even_capacity = math.nan
            interpretation = "cloud_non_cpu_cost_already_exceeds_local_total"
        else:
            break_even_capacity = cpu_continuous_cost_numerator / affordable_cpu_cost
            interpretation = "cloud_cheaper_at_capacity_above_threshold"
        cpu_break_even_rows.append(
            {
                "provider_bundle": row.provider_bundle,
                "local_architecture": row.local_architecture,
                "cloud_cpu_peak_local_server_equivalents": cloud_cpu_peak,
                "cloud_cpu_annual_unit_price_rmb": math.nan
                if len(cpu_product_results) > 1
                else next(iter(cpu_product_results.values()))["unit_price"],
                "cloud_cpu_products": "|".join(sorted(cpu_product_results)),
                "cloud_cpu_continuous_cost_numerator_rmb": cpu_continuous_cost_numerator,
                "cloud_non_cpu_annual_cost_rmb": non_cpu_cloud_cost,
                "annual_100pct_local_cost_rmb": row.annual_100pct_local_cost_rmb,
                "break_even_cloud_cpu_capacity_relative_to_local_server": break_even_capacity,
                "interpretation": interpretation,
                "rounding_boundary": "continuous_group_approximation_before_integer_ceiling",
            }
        )
    cpu_break_even = pd.DataFrame(cpu_break_even_rows)
    cpu_break_even.to_csv(
        output_dir / "cloud_cpu_capacity_break_even.csv",
        index=False,
        encoding="utf-8-sig",
    )
    payload = {
        "status": f"validated_c36_{case}_screening",
        "scenario_version": scenario["scenario_version"],
        "industry_code": industry,
        "parameter_case": case,
        "same_service": True,
        "local_service_share": 1.0,
        "cloud_service_share": 1.0,
        "cloud_capacity_reoptimized_from_residual_task_peaks": True,
        "cloud_gpu_reserved_groups": cloud_gpu_groups,
        "cloud_cpu_reserved_groups": cloud_cpu_groups,
        "cloud_cpu_groups_by_product": {
            name: int(product["groups"])
            for name, product in cpu_product_results.items()
        },
        "cloud_components_reconcile": True,
        "qlora_included_symmetrically_in_core_comparison": True,
        "qlora_adapted_inference_replaces_generic_api_price": True,
        "qlora_reference_training_tokens": qlora_reference_training_tokens,
        "qlora_reference_gpu_h": qlora_reference_gpu_h,
        "qlora_annual_gpu_h": qlora_annual_gpu_h,
        "mcp_wrapper_runtime_included": any(
            float(row["custom_mcp_rmb_per_invocation_second"]) > 0
            for row in agent_archetypes.values()
        ),
        "external_tool_compute_and_third_party_api_price_excluded": True,
        "local_rag_storage_checked_against_bundled_capacity": True,
        "local_rag_incremental_storage_cost_rmb": 0.0,
        "manuscript_or_national_outputs_modified": False,
    }
    managed_service_share = float(
        task.managed_model_service_units_day.sum()
        / task.effective_service_units_day.sum()
    )
    comparison_table = "\n".join(
        f"| {row.local_architecture} | {row.provider_bundle} | "
        f"{row.annual_100pct_local_cost_rmb/1e9:.3f} | "
        f"{row.annual_100pct_cloud_cost_rmb/1e9:.3f} | "
        f"{row.cloud_to_local_cost_ratio:.2f} | "
        f"{row.local_savings_vs_cloud_fraction:.1%} |"
        for row in comparison.itertuples(index=False)
    )
    component_table = "\n".join(
        f"| {row.provider_bundle} | {row.component} | {row.annual_cost_rmb/1e9:.3f} | "
        f"{'yes' if row.included_in_core_total else 'no'} |"
        for row in components.itertuples(index=False)
    )
    break_even_table = "\n".join(
        f"| {row.local_architecture} | {row.provider_bundle} | "
        f"{row.break_even_cloud_cpu_capacity_relative_to_local_server:.3f} |"
        for row in cpu_break_even.itertuples(index=False)
    )
    local_architecture_text = ", ".join(sorted(local.architecture.unique()))
    findings = f"""# C36 equal-service 100% local vs. 100% cloud cost screen

## Current status

- Uses the same C36 {case} scenario task ledger; industry-equivalent effective service is {ledger_service:,.0f} units/day.
- The service share carried by managed LLM/VLM in this scenario is {managed_service_share:.1%}; this is an evidence-constrained author scenario, not an observed C36 average share.
- Residual tasks under 100% cloud have their capacity re-sized from hourly arrivals, deadlines, and CPU/GPU routing, rather than being allocated pro rata by total service share.
- The local side uses {local_architecture_text} costs restored to the full industry, no longer misusing the 8.5% representative-group cost.

## Preliminary results

| 100% local architecture | 100% cloud model bundle | Local cost CNY bn/yr | Cloud cost CNY bn/yr | Cloud/local | Local below cloud |
|---|---|---:|---:|---:|---:|
{comparison_table}

## Cloud cost breakdown

| Model bundle | Component | CNY bn/yr | Included in current total |
|---|---|---:|---|
{component_table}

## Cloud CPU equivalent-capacity break-even

The table below gives the continuous equivalent-capacity threshold of one 32 vCPU cloud instance relative to a local 64-physical-core server; above the threshold the cloud is cheaper, below it local is cheaper. Rounding to integer instances introduces a small discrete deviation in the actual threshold.

| 100% local architecture | 100% cloud model bundle | Break-even equivalent capacity |
|---|---|---:|
{break_even_table}

## Open boundaries

1. QLoRA/SFT enters both totals at the same training-token volume: local uses the FT006 benchmark of {qlora_reference_gpu_h:.0f} L20-GPU hours per {qlora_reference_training_tokens/1e6:.2f} million tokens and uses existing idle capacity first; cloud uses published training-token prices. Both still need to be replaced by measured benchmarks with matched models, sequence lengths, and quality targets.
2. Agent delivery distinguishes standard agents from Managed Agents per configuration; custom MCP counts only wrapper runtime cost. External optimizers, simulators, and third-party APIs must be costed separately per product and must not be double-counted in MCP cost.
3. Local RAG corpus storage is checked at {float(conversion['rag_storage_bytes_per_corpus_token']):.1f} bytes per token with {float(conversion['rag_storage_copy_equivalents']):.0f} copies; it is currently covered by the servers' included NVMe capacity, so incremental storage investment is zero; database O&M is not yet separated from the existing model O&M item.
4. Cloud CPU is routed by task to {', '.join(sorted(cpu_product_results))}; equivalent capacity remains a specification proxy and must be replaced by matched-task dual-platform benchmarks for maintenance, scheduling, and simulation.
5. Inference tokens after QLoRA adaptation are deducted from general-model API traffic and billed at adapted-model prices; token shares are still proxied by enterprise adoption shares, not observed from production logs.
6. This is only a single-industry screen; it cannot replace the manuscript's 61--64% national conclusion and cannot be used to update Figure 2.
"""
    (output_dir / "findings.md").write_text(findings, encoding="utf-8")
    (output_dir / "validated.done.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
