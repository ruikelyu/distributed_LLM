#!/usr/bin/env python3
"""Compare 100% local and 100% cloud delivery for the national shared ledger.

Purpose:
    Produce the China national local-versus-cloud payment comparison used by
    the manuscript cost results, while keeping one validated service ledger
    for both delivery routes.
Workflow status:
    Active v1.0.0 national accounting and post-processing module. It is not a
    replacement for the hourly physical core optimization.
Scientific boundary:
    Compare three locally optimized physical architectures with four complete
    cloud-delivery bundles at the same six-task effective-service demand. The
    cloud account includes managed/API services, RAG, agent/MCP, QLoRA/SFT,
    adapted inference, and residual CPU/GPU capacity where configured.
Inputs:
    National demand wrapper and merged defaults, the 31-industry task and
    lifecycle ledgers, validated local physical summaries,
    ``config/compute_hardware/cpu_gpu_routing_v2.yaml`` cloud-product routing
    and price settings, and model-version metadata. The v2 file is the
    enterprise cloud-billing contract: it assigns residual CPU work to
    product-specific ECS/EAS pools and keeps cloud capacity pooling and
    billing separate from the v1 physical-core routing used to generate local
    facility results. This module does not replace or rerun the v1 physical
    optimization.
Outputs:
    ``comparison.csv``, ``cloud_cost_components.csv``,
    ``local_cost_components.csv``, ``local_lifecycle_industry.csv``,
    ``cloud_capacity_and_price.csv``, ``cloud_task_routing.csv``, and
    ``validated.done.json`` in the configured cost directory.
Key assumptions:
    Local costs are inherited from the validated physical results. Cloud CPU
    and GPU workloads are pooled by product and rounded up separately; cloud
    capacity is represented by configured local-equivalent throughput. Price
    cases and provider bundles are scenario inputs, not observed contracts.
Explicit exclusions:
    This module does not measure cloud performance or network latency and does
    not model WAN, governance, contract discounts, or other omitted provider
    charges beyond the configured billing components. It is an enterprise
    payment comparison, not a social-cost or full infrastructure assessment.
Validation/tests:
    Coverage, service reconciliation, cost-component reconstruction, and
    route-specific integer pooling are checked by
    ``tests/test_national_local_vs_cloud_cost_v1.py`` and the generated
    ``validated.done.json``. Passing these checks establishes internal
    consistency, not real-world validity of the throughput or prices.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.config import load_config  # noqa: E402
from core.data import load_industry_inputs  # noqa: E402
from run_c36_local_vs_cloud_cost_v1 import (  # noqa: E402
    adapted_model_api_cost,
    selected_text_prices,
    text_api_cost,
)
from run_single_industry_heterogeneous_hardware_screen import (  # noqa: E402
    _waterfill,
    annual_hardware_cost,
    task_jobs,
)


TASKS = {"office", "agent", "vision", "maintenance", "scheduling", "simulation"}
ARCHITECTURES = ("PF", "SHG", "MSG")
PRICE_COLUMNS = {"low": "low_value", "base": "base_value", "high": "high_value"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/demand_cases/national_local_cloud_core_v1.yaml"),
    )
    parser.add_argument("--defaults", type=Path, default=Path("config/defaults.yaml"))
    parser.add_argument(
        "--run-config", type=Path, default=Path("config/runs/all_industries_core.yaml")
    )
    parser.add_argument("--task-ledger", type=Path)
    parser.add_argument("--lifecycle-ledger", type=Path)
    parser.add_argument("--local-summary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def pooled_minimize_peak(
    inputs_by_industry: dict[str, object],
    task_fractions: dict[str, float],
    compute_per_service: dict[str, float],
) -> tuple[np.ndarray, float, float]:
    """Apply the registered water-filling heuristic to the pooled national jobs."""
    first = next(iter(inputs_by_industry.values()))
    horizon = first.rigid_service_units.size
    compute = np.zeros(horizon)
    jobs: list[tuple[object, float, float, str]] = []
    for industry, inputs in inputs_by_industry.items():
        if inputs.rigid_service_units.size != horizon:
            raise ValueError("Industry horizons differ in national pooling")
        for task, fraction in task_fractions.items():
            if fraction <= 0:
                continue
            rigid, task_job_list = task_jobs(inputs, task, 1.0)
            factor = float(compute_per_service[task])
            compute += rigid * fraction * factor
            jobs.extend((job, fraction, factor, industry) for job in task_job_list)
    for job, fraction, factor, industry in sorted(
        jobs,
        key=lambda item: (
            item[0].deadline_hours,
            item[0].release_hour,
            item[0].task_id,
            item[3],
        ),
    ):
        hours = sorted(
            {
                (job.release_hour + offset) % horizon
                for offset in range(job.deadline_hours + 1)
            }
        )
        _waterfill(compute, hours, job.amount_service_units * fraction * factor)
    return compute, float(compute.max()), float(compute.sum())


def lifecycle_row(frame: pd.DataFrame, component: str) -> pd.Series:
    selected = frame[frame.component == component]
    if selected.empty:
        raise ValueError(f"Missing lifecycle component {component}")
    return selected.sum(numeric_only=True)


def main() -> None:
    args = parse_args()
    wrapper = yaml.safe_load((ROOT / args.config).read_text(encoding="utf-8"))
    scenario = yaml.safe_load(
        (ROOT / str(wrapper["base_scenario_config"])).read_text(encoding="utf-8")
    )
    routing = yaml.safe_load(
        (ROOT / str(wrapper["routing_config"])).read_text(encoding="utf-8")
    )
    defaults = load_config(ROOT, args.defaults, args.run_config)
    case = str(wrapper["parameter_case"])
    industries = [str(value) for value in wrapper["industry_codes"]]
    output = ROOT / (args.output_dir or Path(str(wrapper["output_root"])) / "cost")
    ledger_root = ROOT / Path(str(wrapper["output_root"])) / "ledger"
    task_path = ROOT / (args.task_ledger or ledger_root / "task_ledger.csv")
    lifecycle_path = ROOT / (
        args.lifecycle_ledger or ledger_root / "lifecycle_ledger.csv"
    )
    local_path = ROOT / (args.local_summary or Path(str(wrapper["local_summary"])))

    tasks = pd.read_csv(task_path, encoding="utf-8-sig")
    tasks = tasks[tasks.parameter_case == case].copy()
    lifecycle = pd.read_csv(lifecycle_path, encoding="utf-8-sig")
    lifecycle = lifecycle[lifecycle.parameter_case == case].copy()
    local = pd.read_csv(local_path, encoding="utf-8-sig")
    local = local[local.base_load_case == "actual_load"].copy()
    if (
        tasks.industry_code.nunique() != 31
        or len(tasks) != 31 * 6
        or set(tasks.task_id) != TASKS
    ):
        raise ValueError("National task ledger must contain 31 industries and six tasks")
    if lifecycle.industry_code.nunique() != 31 or len(lifecycle) != 31 * 4:
        raise ValueError("National lifecycle ledger coverage is incomplete")
    if len(local) != 31 * 3 or set(local.architecture) != set(ARCHITECTURES):
        raise ValueError("Local summary must contain 31 industries and three architectures")
    if set(local.solver_status) != {"ok"}:
        raise ValueError("Local physical results include a non-ok solve")
    service_error = (
        tasks.managed_model_service_units_day
        + tasks.residual_cpu_gpu_service_units_day
        - tasks.effective_service_units_day
    ).abs()
    if service_error.max() > 1e-6:
        raise AssertionError("Managed and residual national service do not reconcile")

    managed_share = tasks.groupby("task_id").managed_model_share.nunique()
    if not (managed_share == 1).all():
        raise ValueError("Managed delivery share must be common across industries")
    residual_share = (
        tasks.groupby("task_id").residual_cpu_gpu_service_units_day.sum()
        / tasks.groupby("task_id").effective_service_units_day.sum()
    ).to_dict()
    route_case = str(routing["active_core_routing_case"])
    cpu_route = {
        task: float(routing["routing_cases"][route_case].get(task, 0.0))
        for task in TASKS
    }
    cloud_cpu_fraction = {
        task: residual_share[task] * cpu_route[task] for task in TASKS
    }
    cloud_gpu_fraction = {
        task: residual_share[task] * (1.0 - cpu_route[task]) for task in TASKS
    }

    inputs = {industry: load_industry_inputs(defaults, industry) for industry in industries}
    reference_compute_factors = {value.reference_compute_h_per_service_unit for value in inputs.values()}
    if len(reference_compute_factors) != 1:
        raise ValueError("Industry reference-compute factors are not common")
    reference_compute_per_service = float(next(iter(reference_compute_factors)))
    multipliers = routing["core_cpu_server_hour_per_reference_compute_hour"]
    gpu_factors = {task: reference_compute_per_service for task in TASKS}
    cpu_factors = {
        task: reference_compute_per_service * float(multipliers.get(task, 1.0))
        for task in TASKS
    }
    gpu_profile, gpu_peak, gpu_total_week = pooled_minimize_peak(
        inputs, cloud_gpu_fraction, gpu_factors
    )
    gpu_groups = math.ceil(
        gpu_peak / float(defaults["server"]["accelerators_per_server"])
    )

    product_by_task = routing["cloud_cpu_product_by_task"]
    cpu_products = routing["cloud_cpu_products"]
    cpu_capacity: dict[str, dict[str, float]] = {}
    for product_name, settings in cpu_products.items():
        fractions = {
            task: cloud_cpu_fraction[task]
            if product_by_task.get(task) == product_name
            else 0.0
            for task in TASKS
        }
        profile, peak, total_week = pooled_minimize_peak(inputs, fractions, cpu_factors)
        capacity = float(settings["service_capacity_relative_to_local_cpu_server"])
        cpu_capacity[product_name] = {
            "peak": peak,
            "total_week": total_week,
            "groups": math.ceil(peak / capacity) if peak > 0 else 0,
            "capacity": capacity,
            "profile_peak_check": float(profile.max(initial=0.0)),
        }

    lifecycle_parameters = pd.read_csv(
        ROOT / "02_data/enterprise_llm_lifecycle_parameters.csv", encoding="utf-8-sig"
    )
    conversion = scenario["local_lifecycle_conversion"]
    qlora_parameter = lifecycle_parameters[
        lifecycle_parameters.parameter_id
        == str(conversion["qlora_gpu_hours_parameter_id"])
    ].iloc[0]
    qlora_reference_gpu_h = float(qlora_parameter[conversion["qlora_gpu_hours_case"]])
    qlora_reference_tokens = float(conversion["qlora_reference_training_tokens"])
    bundled = lifecycle_parameters[
        lifecycle_parameters.parameter_id
        == str(conversion["bundled_storage_parameter_id"])
    ].iloc[0]
    storage_per_gpu_group = float(bundled[case]) * 1000.0
    local_rows: list[dict[str, object]] = []
    local_industry_rows: list[dict[str, object]] = []
    for architecture in ARCHITECTURES:
        core_total = 0.0
        qlora_hardware_total = 0.0
        qlora_energy_total = 0.0
        required_storage_total = 0.0
        available_storage_total = 0.0
        for industry in industries:
            physical = local[
                (local.industry == industry) & (local.architecture == architecture)
            ].iloc[0]
            life = lifecycle[lifecycle.industry_code == industry]
            qlora = life[life.component == "qlora_sft_training"].iloc[0]
            rag = life[life.component == "rag_knowledge_base"].iloc[0]
            annual_gpu_h = (
                float(qlora.annual_tokens)
                / qlora_reference_tokens
                * qlora_reference_gpu_h
            )
            installed = float(physical.industry_equivalent_installed_gpu_server_groups)
            average = float(
                physical.industry_equivalent_average_required_gpu_server_groups
            )
            spare_gpu_h = max(0.0, installed - average) * 2.0 * 8760.0
            uncovered_gpu_h = max(0.0, annual_gpu_h - spare_gpu_h)
            additional_groups = uncovered_gpu_h / (2.0 * 8760.0) / (
                1.0 - float(conversion["additional_training_capacity_reserve_fraction"])
            )
            hardware_cost = annual_hardware_cost(
                defaults["server"], additional_groups, float(defaults["model"]["discount_rate"])
            )
            dynamic_kwh_per_gpu_h = float(
                defaults["server"]["marginal_facility_multiplier"]
            ) * (
                float(defaults["server"]["maximum_wall_power_kw"])
                - float(defaults["server"]["online_idle_wall_power_kw"])
            ) / float(defaults["server"]["accelerators_per_server"])
            energy_cost = (
                annual_gpu_h
                * dynamic_kwh_per_gpu_h
                * float(defaults["energy"]["flat_grid_energy_rmb_per_kwh"])
            )
            corpus_tokens = float(rag.quantity) * float(
                scenario["workload_cases"][case]["rag_corpus_tokens_per_knowledge_base"]
            )
            required_storage = (
                corpus_tokens
                * float(conversion["rag_storage_bytes_per_corpus_token"])
                * float(conversion["rag_storage_copy_equivalents"])
                / 1e9
            )
            available_storage = installed * storage_per_gpu_group
            if required_storage > available_storage + 1e-6:
                raise ValueError(f"Local bundled RAG storage is insufficient for {industry}/{architecture}")
            core_cost = float(physical.industry_equivalent_annual_incremental_total_cost_rmb)
            core_total += core_cost
            qlora_hardware_total += hardware_cost
            qlora_energy_total += energy_cost
            required_storage_total += required_storage
            available_storage_total += available_storage
            local_industry_rows.append(
                {
                    "industry_code": industry,
                    "architecture": architecture,
                    "annual_core_cost_rmb": core_cost,
                    "qlora_annual_gpu_h": annual_gpu_h,
                    "qlora_spare_gpu_h": spare_gpu_h,
                    "qlora_additional_gpu_groups": additional_groups,
                    "qlora_incremental_hardware_cost_rmb": hardware_cost,
                    "qlora_incremental_energy_cost_rmb": energy_cost,
                    "rag_required_storage_gb": required_storage,
                    "rag_available_bundled_storage_gb": available_storage,
                }
            )
        local_rows.append(
            {
                "architecture": architecture,
                "annual_core_cost_rmb": core_total,
                "annual_qlora_hardware_cost_rmb": qlora_hardware_total,
                "annual_qlora_energy_cost_rmb": qlora_energy_total,
                "annual_rag_incremental_storage_cost_rmb": 0.0,
                "annual_100pct_local_cost_rmb": core_total
                + qlora_hardware_total
                + qlora_energy_total,
                "rag_required_storage_gb": required_storage_total,
                "rag_available_bundled_storage_gb": available_storage_total,
            }
        )
    local_costs = pd.DataFrame(local_rows).set_index("architecture")

    managed = scenario["cloud_managed_service_prices"]
    api_prices = selected_text_prices(
        pd.read_csv(
            ROOT / "02_data/processed/api_token_cost/api_token_prices_v1_1.csv",
            encoding="utf-8-sig",
        )
    )
    rag = lifecycle_row(lifecycle, "rag_knowledge_base")
    agent_tools = lifecycle_row(lifecycle, "agent_tool_calls")
    agent_runtime = lifecycle_row(lifecycle, "agent_runtime")
    qlora = lifecycle_row(lifecycle, "qlora_sft_training")
    office = tasks[tasks.task_id == "office"]
    vision = tasks[tasks.task_id == "vision"]
    common_components = {
        "qlora_adapted_model_inference": adapted_model_api_cost(tasks, managed),
        "vlm_api": float(vision.annual_input_tokens.sum()) / 1e6 * float(managed["vlm_input_rmb_per_million_tokens"])
        + float(vision.annual_output_tokens.sum()) / 1e6 * float(managed["vlm_output_rmb_per_million_tokens"]),
        "rag_knowledge_base_runtime": float(rag["quantity"]) * float(managed["knowledge_base_runtime_rmb_per_kb_hour"]) * 8760.0,
        "rag_embedding": float(rag["annual_tokens"]) / 1e6 * float(managed["embedding_rmb_per_million_tokens"]),
        "rag_rerank": float(office.annual_input_tokens.sum()) / 1e6 * float(managed["rerank_rmb_per_million_tokens"]),
        "qlora_sft_training": float(qlora["annual_tokens"]) / 1000.0 * float(managed["qlora_training_rmb_per_thousand_tokens"]),
    }
    agent_archetypes = scenario["cloud_agent_delivery_archetypes"]
    cost_parameters = pd.read_csv(
        ROOT / str(defaults["paths"]["enterprise_ai_cost_parameters"]),
        encoding="utf-8-sig",
    )
    gpu_price_row = cost_parameters[cost_parameters.parameter_id == "C19"].iloc[0]
    comparison_rows: list[dict[str, object]] = []
    component_rows: list[dict[str, object]] = []
    capacity_rows: list[dict[str, object]] = []
    annual_days = float(defaults["model"]["annualization_days"])
    annual_service = float(tasks.effective_service_units_day.sum()) * annual_days
    for price_case in wrapper["comparison_boundary"]["cloud_price_cases"]:
        gpu_unit_price = float(gpu_price_row[PRICE_COLUMNS[price_case]])
        gpu_capacity_cost = gpu_groups * gpu_unit_price
        cpu_costs: dict[str, float] = {}
        for product_name, result in cpu_capacity.items():
            settings = cpu_products[product_name]
            prices = settings.get("annual_price_cases_rmb") or settings.get(
                "annual_reserved_price_cases_rmb"
            )
            cpu_costs[product_name] = result["groups"] * float(prices[price_case])
        capacity_rows.append(
            {
                "price_case": price_case,
                "cloud_gpu_peak_reference_compute_h_per_h": gpu_peak,
                "cloud_gpu_groups": gpu_groups,
                "cloud_gpu_annual_unit_price_rmb": gpu_unit_price,
                "cloud_gpu_annual_capacity_cost_rmb": gpu_capacity_cost,
                "cloud_cpu_groups": sum(value["groups"] for value in cpu_capacity.values()),
                "cloud_cpu_annual_capacity_cost_rmb": sum(cpu_costs.values()),
                "cloud_cpu_groups_by_product": json.dumps(
                    {name: value["groups"] for name, value in cpu_capacity.items()},
                    sort_keys=True,
                ),
            }
        )
        for price in api_prices.itertuples(index=False):
            generic_text = text_api_cost(tasks, pd.Series(price._asdict()))
            for archetype_name, archetype in agent_archetypes.items():
                provider_bundle = f"{price.provider} | {archetype_name}"
                components = dict(common_components)
                components["text_llm_api_generic"] = generic_text
                components["agent_runtime"] = float(agent_runtime["quantity"]) * float(
                    archetype["session_runtime_rmb_per_hour"]
                )
                components["custom_mcp_runtime"] = (
                    float(agent_tools["quantity"])
                    * float(archetype["custom_mcp_seconds_per_tool_call"])
                    * float(archetype["custom_mcp_rmb_per_invocation_second"])
                )
                components["residual_gpu_reserved_capacity"] = gpu_capacity_cost
                for product_name, value in cpu_costs.items():
                    components[f"residual_cpu_{product_name}_capacity"] = value
                cloud_total = sum(components.values())
                for component, value in components.items():
                    component_rows.append(
                        {
                            "scenario_version": wrapper["scenario_version"],
                            "price_case": price_case,
                            "provider_bundle": provider_bundle,
                            "component": component,
                            "annual_cost_rmb": value,
                            "included_in_total": True,
                        }
                    )
                for architecture in ARCHITECTURES:
                    local_total = float(
                        local_costs.loc[architecture, "annual_100pct_local_cost_rmb"]
                    )
                    comparison_rows.append(
                        {
                            "scenario_version": wrapper["scenario_version"],
                            "parameter_case": case,
                            "cloud_price_case": price_case,
                            "local_architecture": architecture,
                            "provider_bundle": provider_bundle,
                            "same_annual_effective_service_units": annual_service,
                            "local_service_share": 1.0,
                            "cloud_service_share": 1.0,
                            "annual_100pct_local_cost_rmb": local_total,
                            "annual_100pct_cloud_cost_rmb": cloud_total,
                            "cloud_to_local_cost_ratio": cloud_total / local_total,
                            "local_savings_vs_cloud_fraction": 1.0 - local_total / cloud_total,
                            "equal_effectiveness_assumption": True,
                            "result_status": wrapper["comparison_boundary"]["result_status"],
                        }
                    )

    comparison = pd.DataFrame(comparison_rows)
    components = pd.DataFrame(component_rows)
    observed = comparison.groupby(
        ["cloud_price_case", "provider_bundle"]
    ).annual_100pct_cloud_cost_rmb.first()
    reconstructed = components.groupby(
        ["price_case", "provider_bundle"]
    ).annual_cost_rmb.sum()
    reconstructed.index.names = observed.index.names
    if not np.allclose(observed.sort_index(), reconstructed.sort_index(), rtol=1e-12):
        raise AssertionError("Cloud component totals do not reconcile")
    if comparison.same_annual_effective_service_units.nunique() != 1:
        raise AssertionError("Comparison service boundary is not common")

    output.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output / "comparison.csv", index=False, encoding="utf-8-sig")
    components.to_csv(
        output / "cloud_cost_components.csv", index=False, encoding="utf-8-sig"
    )
    local_costs.reset_index().to_csv(
        output / "local_cost_components.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(local_industry_rows).to_csv(
        output / "local_lifecycle_industry.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(capacity_rows).to_csv(
        output / "cloud_capacity_and_price.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(
        [
            {
                "task_id": task,
                "managed_model_share": 1.0 - residual_share[task],
                "residual_service_share": residual_share[task],
                "residual_cpu_share_of_total_service": cloud_cpu_fraction[task],
                "residual_gpu_share_of_total_service": cloud_gpu_fraction[task],
                "cloud_cpu_product": product_by_task.get(task, "none")
                if cloud_cpu_fraction[task] > 0
                else "none",
            }
            for task in sorted(TASKS)
        ]
    ).to_csv(output / "cloud_task_routing.csv", index=False, encoding="utf-8-sig")
    base_rows = comparison[comparison.cloud_price_case == "base"]
    payload = {
        "status": "validated_national_all_local_vs_all_cloud_screening",
        "scenario_version": wrapper["scenario_version"],
        "industry_count": 31,
        "same_service": True,
        "equal_effectiveness_assumption": True,
        "cloud_performance_benchmark_required": False,
        "local_architectures": list(ARCHITECTURES),
        "cloud_provider_bundles": sorted(comparison.provider_bundle.unique()),
        "cloud_price_cases": sorted(comparison.cloud_price_case.unique()),
        "annual_effective_service_units": annual_service,
        "cloud_gpu_groups": gpu_groups,
        "cloud_cpu_groups_by_product": {
            name: value["groups"] for name, value in cpu_capacity.items()
        },
        "maximum_service_reconciliation_error": float(service_error.max()),
        "cloud_components_reconcile": True,
        "base_cloud_to_local_ratio_range": [
            float(base_rows.cloud_to_local_cost_ratio.min()),
            float(base_rows.cloud_to_local_cost_ratio.max()),
        ],
        "limitations": [
            "managed-service and workload quantities are evidence-bounded scenarios rather than enterprise traces",
            "cloud CPU capacity ratios are specification conversions rather than measured performance",
            "public cloud prices exclude negotiated discounts, WAN, migration, support, tax, and integration",
            "national pooled capacity uses the registered deadline-feasible water-filling upper-bound heuristic",
            "local physical input retains the mixed production-load boundary: C36 calibrated and 30 industries legacy",
        ],
    }
    (output / "validated.done.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
