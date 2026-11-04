#!/usr/bin/env python3
"""Recompute U.S. local and cloud costs under the shared China/U.S. service contract.

Local capacity is sized separately for 21 NAICS3 industries. Cloud capacity is
pooled nationally and serves only the residual CPU/GPU share after managed/API
delivery, matching the active China national cloud-accounting boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))
from build_us_manufacturing_ai_demand import (  # noqa: E402
    allocate_daily_to_shape,
    capital_recovery_factor,
    parameter_value,
    task_shapes,
)
from core.capacity import (  # noqa: E402
    average_required_server_groups,
    local_installed_capacity_floor,
)


TASKS = {"office", "agent", "vision", "maintenance", "scheduling", "simulation"}
CASES = ("low", "base", "high")
PROVIDERS = ("OpenAI", "Anthropic", "Google")
NATIONAL_AGGREGATION_BOUNDARY = (
    "national_pooled_residual_service_capacity_after_managed_api_delivery"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def china_aligned_continuous_capacity(
    hourly_compute_h: np.ndarray,
    service_capacity_per_server_group_h_per_h: float,
    planning_headroom_fraction: float,
    n_plus_spare_server_groups: int,
    normal_dispatch_reserve_fraction: float,
) -> tuple[float, np.ndarray]:
    """Apply the continuous-capacity constraints used by the China core model."""
    compute = np.asarray(hourly_compute_h, dtype=float)
    if compute.ndim != 1 or len(compute) == 0 or not np.isfinite(compute).all():
        raise ValueError("Hourly compute must be a finite, non-empty one-dimensional array")
    if (compute < 0.0).any():
        raise ValueError("Hourly compute must be non-negative")
    capacity = float(service_capacity_per_server_group_h_per_h)
    dispatch_reserve = float(normal_dispatch_reserve_fraction)
    if not np.isfinite(capacity) or capacity <= 0.0:
        raise ValueError("Server-group service capacity must be positive")
    if not 0.0 <= dispatch_reserve < 1.0:
        raise ValueError("Normal dispatch reserve must be in [0, 1)")

    average_required = average_required_server_groups(
        float(compute.sum()), len(compute), capacity
    )
    planning_floor = local_installed_capacity_floor(
        average_required,
        planning_headroom_fraction,
        n_plus_spare_server_groups,
    )
    peak_dispatch_floor = float(compute.max()) * (1.0 + dispatch_reserve) / capacity
    installed = max(planning_floor, peak_dispatch_floor)
    return installed, compute / capacity


def validate_cloud_contract(
    delivery_config: dict,
    cloud_routing_config: dict,
    contract_case: str,
) -> tuple[dict[str, dict], dict[str, str], dict[str, dict]]:
    """Return one complete managed/residual contract shared with China."""
    delivery = delivery_config["task_delivery"][contract_case]
    if set(delivery) != TASKS:
        raise ValueError("Cloud delivery contract must cover all six tasks")
    for task, settings in delivery.items():
        share = float(settings["managed_model_share"])
        if not 0.0 <= share <= 1.0:
            raise ValueError(f"Invalid managed-model share for {task}")
    product_by_task = cloud_routing_config["cloud_cpu_product_by_task"]
    products = cloud_routing_config["cloud_cpu_products"]
    if not TASKS.issubset(product_by_task):
        raise ValueError("Cloud CPU product routing must cover all tasks")
    return delivery, product_by_task, products


def task_profiles(
    frame: pd.DataFrame,
    shapes: dict[str, np.ndarray],
    routing: dict[str, float],
    multipliers: dict[str, float],
    reference_compute_h_per_service: float,
    delivery: dict[str, dict] | None = None,
    product_by_task: dict[str, str] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, np.ndarray]]:
    """Build full local profiles or residual cloud profiles."""
    gpu = np.zeros(24)
    cpu = np.zeros(24)
    cpu_by_product: dict[str, np.ndarray] = {}
    for row in frame.itertuples(index=False):
        task = str(row.task_id)
        profile = allocate_daily_to_shape(
            float(row.effective_service_units_day), shapes[task]
        )
        cpu_share = float(routing.get(task, 0.0))
        residual_share = (
            1.0 - float(delivery[task]["managed_model_share"])
            if delivery is not None
            else 1.0
        )
        gpu += profile * (1.0 - cpu_share) * reference_compute_h_per_service * residual_share
        cpu_task = (
            profile
            * cpu_share
            * float(multipliers.get(task, 1.0))
            * reference_compute_h_per_service
            * residual_share
        )
        cpu += cpu_task
        if product_by_task is not None and cpu_task.any():
            product = str(product_by_task[task])
            cpu_by_product.setdefault(product, np.zeros(24))
            cpu_by_product[product] += cpu_task
    return gpu, cpu, cpu_by_product


def managed_api_tokens(
    frame: pd.DataFrame,
    national_tokens: pd.DataFrame,
    case: str,
    delivery: dict[str, dict],
) -> tuple[float, float]:
    """Combine the U.S. office/agent token ledger with other managed task calls."""
    token_rows = national_tokens[national_tokens.parameter_case == case].set_index("task_id")
    annual_input = 0.0
    annual_output = 0.0
    case_demand = frame[frame.parameter_case == case]
    for task in ("office", "agent"):
        total = float(case_demand[case_demand.task_id == task].effective_service_units_day.sum())
        if total > 0.0 and task in token_rows.index:
            annual_input += float(token_rows.loc[task, "annual_input_tokens"])
            annual_output += float(token_rows.loc[task, "annual_output_tokens"])
    for task in TASKS - {"office", "agent"}:
        settings = delivery[task]
        service_day = float(
            case_demand[case_demand.task_id == task].effective_service_units_day.sum()
        )
        managed_calls_year = (
            service_day
            * float(settings["managed_model_share"])
            * float(settings["calls_per_managed_service_unit"])
            * 365.0
        )
        annual_input += managed_calls_year * float(settings["input_tokens_per_call"])
        annual_output += managed_calls_year * float(settings["output_tokens_per_call"])
    return annual_input, annual_output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demand", type=Path, required=True)
    parser.add_argument("--national-task-summary", type=Path, required=True)
    parser.add_argument("--defaults", type=Path, required=True)
    parser.add_argument("--demand-config", type=Path, required=True)
    parser.add_argument("--routing-config", type=Path, required=True)
    parser.add_argument("--cloud-routing-config", type=Path, required=True)
    parser.add_argument("--cloud-delivery-config", type=Path, required=True)
    parser.add_argument("--us-cost-config", type=Path, required=True)
    parser.add_argument("--us-parameters", type=Path, required=True)
    parser.add_argument("--us-api-prices", type=Path, required=True)
    parser.add_argument("--compute-efficiency", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    demand = pd.read_csv(args.demand, encoding="utf-8-sig")
    national_tokens = pd.read_csv(args.national_task_summary, encoding="utf-8-sig")
    defaults = yaml.safe_load(args.defaults.read_text(encoding="utf-8"))
    demand_config = yaml.safe_load(args.demand_config.read_text(encoding="utf-8"))
    route_config = yaml.safe_load(args.routing_config.read_text(encoding="utf-8"))
    cloud_route_config = yaml.safe_load(args.cloud_routing_config.read_text(encoding="utf-8"))
    delivery_config = yaml.safe_load(args.cloud_delivery_config.read_text(encoding="utf-8"))
    parameters = pd.read_csv(args.us_parameters, encoding="utf-8-sig")
    api_prices = pd.read_csv(args.us_api_prices, encoding="utf-8-sig")
    efficiency = pd.read_csv(args.compute_efficiency, encoding="utf-8-sig")
    us_cost_config = yaml.safe_load(args.us_cost_config.read_text(encoding="utf-8"))
    us = us_cost_config["us_cost_environment"]
    contract_case = str(us["cloud_delivery_contract_case"])
    delivery, product_by_task, cloud_products = validate_cloud_contract(
        delivery_config, cloud_route_config, contract_case
    )

    expected_model_version = str(demand_config["model_version"])
    expected_demand_version = str(demand_config["demand_case_version"])
    if str(defaults["model_version"]) != expected_model_version:
        raise ValueError("U.S. demand config and active defaults must use the same model version")
    for name, frame in {"demand": demand, "national_task_summary": national_tokens}.items():
        if set(frame["model_version"].astype(str)) != {expected_model_version}:
            raise ValueError(f"{name} model version mismatch")
        if set(frame["demand_case_version"].astype(str)) != {expected_demand_version}:
            raise ValueError(f"{name} demand version mismatch")
    if set(demand.task_id) != TASKS or set(demand.parameter_case) != set(CASES):
        raise ValueError("U.S. demand must cover six tasks and low/base/high cases")
    if int(us["local_cpu_physical_cores"]) != 64 or int(us["local_cpu_minimum_memory_gb"]) < 256:
        raise ValueError("U.S. CPU cost case must use the common 64-core, >=256GB local unit")

    api_prices = api_prices[api_prices.provider.isin(us["formal_api_providers"])].copy()
    if set(api_prices.provider) != set(PROVIDERS):
        raise ValueError("Formal U.S. API provider panel is incomplete")
    shapes = task_shapes(ROOT / demand_config["task_shapes"]["profile_file"], demand_config["task_shapes"])
    routing = route_config["routing_cases"][route_config["active_core_routing_case"]]
    multipliers = route_config["core_cpu_server_hour_per_reference_compute_hour"]
    selected_efficiency = efficiency[
        efficiency.efficiency_case == demand_config["compute"]["common_it_effective_efficiency_case"]
    ]
    if len(selected_efficiency) != 1:
        raise ValueError("Configured U.S. compute-efficiency case is missing or duplicated")
    reference_compute_h_per_service = float(selected_efficiency.iloc[0].reference_compute_h_per_service_unit)
    gpu_config = defaults["server"]
    cpu_config = route_config["cpu_server"]
    for server in (gpu_config, cpu_config):
        server.setdefault("installed_reserve_fraction", float(gpu_config["installed_reserve_fraction"]))
        server.setdefault("n_plus_spare_server_groups", int(gpu_config.get("n_plus_spare_server_groups", 0)))
        server.setdefault("normal_dispatch_reserve_fraction", float(gpu_config.get("normal_dispatch_reserve_fraction", 0.0)))
    gpu_capacity = float(gpu_config["accelerators_per_server"])
    cpu_capacity = float(cpu_config["service_capacity_cpu_server_h_per_h"])
    cloud_gpu_capacity = float(defaults["hybrid_cloud"]["gpu_capacity_accelerator_h_per_h"])
    if not np.isclose(cloud_gpu_capacity, gpu_capacity):
        raise ValueError("U.S. and China GPU cloud capacity units must match")
    cloud_cpu_capacity = float(us["cloud_cpu_service_capacity_relative_to_local_cpu_server"])
    for product, settings in cloud_products.items():
        if not np.isclose(float(settings["service_capacity_relative_to_local_cpu_server"]), cloud_cpu_capacity):
            raise ValueError(f"U.S. and China CPU capacity units differ for {product}")

    gpu_purchase = parameter_value(parameters, us["local_gpu_server_parameter_id"], "base")
    cpu_prices = {
        case: parameter_value(parameters, us["local_cpu_server_parameter_id"], case)
        for case in CASES
    }
    electricity = parameter_value(parameters, us["industrial_electricity_parameter_id"], "base")
    cloud_gpu_price = parameter_value(parameters, us["cloud_gpu_reserved_parameter_id"], "base")
    cloud_cpu_price = parameter_value(parameters, us["cloud_cpu_reserved_parameter_id"], "base")
    annual_days = float(demand_config["annualization_days"])
    coefficient = (
        (1.0 + float(us["shared_facility_capex_fraction"]))
        * capital_recovery_factor(float(us["shared_discount_rate"]), float(us["shared_economic_life_years"]))
        + float(us["shared_annual_maintenance_fraction"])
    )

    detail_rows: list[dict[str, object]] = []
    for (case, naics), industry in demand.groupby(["parameter_case", "naics3"]):
        local_gpu, local_cpu, _ = task_profiles(
            industry, shapes, routing, multipliers, reference_compute_h_per_service
        )
        gpu_installed, gpu_online = china_aligned_continuous_capacity(
            local_gpu, gpu_capacity, float(gpu_config["installed_reserve_fraction"]),
            int(gpu_config["n_plus_spare_server_groups"]),
            float(gpu_config["normal_dispatch_reserve_fraction"]),
        )
        cpu_installed, cpu_online = china_aligned_continuous_capacity(
            local_cpu, cpu_capacity, float(cpu_config["installed_reserve_fraction"]),
            int(cpu_config["n_plus_spare_server_groups"]),
            float(cpu_config["normal_dispatch_reserve_fraction"]),
        )
        gpu_kw = float(gpu_config["marginal_facility_multiplier"]) * (
            gpu_installed * float(gpu_config["cold_spare_standby_power_kw"])
            + gpu_online * (float(gpu_config["online_idle_wall_power_kw"]) - float(gpu_config["cold_spare_standby_power_kw"]))
            + local_gpu / gpu_capacity * (float(gpu_config["maximum_wall_power_kw"]) - float(gpu_config["online_idle_wall_power_kw"]))
        )
        cpu_kw = float(cpu_config["marginal_facility_multiplier"]) * (
            cpu_installed * float(cpu_config["cold_spare_standby_power_kw"])
            + cpu_online * (float(cpu_config["online_idle_wall_power_kw"]) - float(cpu_config["cold_spare_standby_power_kw"]))
            + local_cpu / cpu_capacity * (float(cpu_config["maximum_wall_power_kw"]) - float(cpu_config["online_idle_wall_power_kw"]))
        )
        annual_energy_twh = float((gpu_kw.sum() + cpu_kw.sum()) * annual_days / 1e9)
        residual_gpu, _, residual_cpu_products = task_profiles(
            industry, shapes, routing, multipliers, reference_compute_h_per_service,
            delivery, product_by_task,
        )
        diagnostic_gpu = float(residual_gpu.max()) / cloud_gpu_capacity
        diagnostic_cpu = sum(
            float(profile.max()) / (cpu_capacity * cloud_cpu_capacity)
            for profile in residual_cpu_products.values()
        )
        for cpu_case, cpu_purchase in cpu_prices.items():
            local_total = (
                gpu_installed * gpu_purchase * coefficient
                + cpu_installed * cpu_purchase * coefficient
                + annual_energy_twh * 1e9 * electricity
            )
            detail_rows.append({
                "model_version": expected_model_version,
                "demand_case_version": expected_demand_version,
                "parameter_case": case,
                "naics3": int(naics),
                "industry_name": industry.industry_name.iloc[0],
                "routing_case": route_config["active_core_routing_case"],
                "cpu_server_price_case": cpu_case,
                "local_gpu_servers": gpu_installed,
                "local_cpu_servers": cpu_installed,
                "annual_facility_energy_twh": annual_energy_twh,
                "local_total_annual_cost_usd": local_total,
                "diagnostic_unpooled_residual_cloud_gpu_instances": diagnostic_gpu,
                "diagnostic_unpooled_residual_cloud_cpu_instances": diagnostic_cpu,
                "cloud_delivery_contract_case": contract_case,
            })
    detail = pd.DataFrame(detail_rows)
    if detail.naics3.nunique() != 21:
        raise ValueError("Expected 21 U.S. NAICS3 industries")

    local_national = detail.groupby(
        ["parameter_case", "cpu_server_price_case"], as_index=False
    )[["local_gpu_servers", "local_cpu_servers", "annual_facility_energy_twh", "local_total_annual_cost_usd"]].sum()
    national_rows: list[dict[str, object]] = []
    for case in CASES:
        case_demand = demand[demand.parameter_case == case]
        residual_gpu, _, residual_cpu_products = task_profiles(
            case_demand, shapes, routing, multipliers, reference_compute_h_per_service,
            delivery, product_by_task,
        )
        cloud_gpu_instances = float(residual_gpu.max()) / cloud_gpu_capacity
        cpu_instances_by_product = {
            product: float(profile.max()) / (cpu_capacity * cloud_cpu_capacity)
            for product, profile in residual_cpu_products.items()
        }
        cloud_cpu_instances = sum(cpu_instances_by_product.values())
        annual_input_tokens, annual_output_tokens = managed_api_tokens(
            demand, national_tokens, case, delivery
        )
        for local_row in local_national[local_national.parameter_case == case].itertuples(index=False):
            for price in api_prices.itertuples(index=False):
                api_cost = (
                    annual_input_tokens / 1e6 * float(price.input_usd_per_mtoken)
                    + annual_output_tokens / 1e6 * float(price.output_usd_per_mtoken)
                )
                gpu_cost = cloud_gpu_instances * cloud_gpu_price
                cpu_cost = cloud_cpu_instances * cloud_cpu_price
                cloud_total = gpu_cost + cpu_cost + api_cost
                national_rows.append({
                    "parameter_case": case,
                    "cpu_server_price_case": local_row.cpu_server_price_case,
                    "provider": price.provider,
                    "local_gpu_servers": local_row.local_gpu_servers,
                    "local_cpu_servers": local_row.local_cpu_servers,
                    "annual_facility_energy_twh": local_row.annual_facility_energy_twh,
                    "local_total_annual_cost_usd": local_row.local_total_annual_cost_usd,
                    "cloud_gpu_reserved_instances": cloud_gpu_instances,
                    "cloud_cpu_reserved_instances": cloud_cpu_instances,
                    "cloud_cpu_instances_by_product": json.dumps(cpu_instances_by_product, sort_keys=True),
                    "cloud_managed_api_input_tokens": annual_input_tokens,
                    "cloud_managed_api_output_tokens": annual_output_tokens,
                    "cloud_token_api_cost_usd": api_cost,
                    "cloud_gpu_reserved_cost_usd": gpu_cost,
                    "cloud_cpu_reserved_cost_usd": cpu_cost,
                    "cloud_total_annual_cost_usd": cloud_total,
                    "aggregation_boundary": NATIONAL_AGGREGATION_BOUNDARY,
                    "model_version": expected_model_version,
                    "demand_case_version": expected_demand_version,
                    "cloud_delivery_contract_case": contract_case,
                    "cloud_cpu_service_capacity_relative_to_local_server": cloud_cpu_capacity,
                    "cloud_to_local_cost_ratio": cloud_total / float(local_row.local_total_annual_cost_usd),
                    "local_savings_vs_cloud_fraction": 1.0 - float(local_row.local_total_annual_cost_usd) / cloud_total,
                })
    national = pd.DataFrame(national_rows)
    reconstructed = (
        national.cloud_gpu_reserved_cost_usd
        + national.cloud_cpu_reserved_cost_usd
        + national.cloud_token_api_cost_usd
    )
    if not np.allclose(reconstructed, national.cloud_total_annual_cost_usd, rtol=1e-12):
        raise AssertionError("U.S. cloud components do not reconcile")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    detail.to_csv(args.output_dir / "us_naics3_comparison.csv", index=False, encoding="utf-8-sig")
    national.to_csv(args.output_dir / "us_national_comparison.csv", index=False, encoding="utf-8-sig")
    base = national.query("parameter_case == 'base' and cpu_server_price_case == 'base'").sort_values("cloud_total_annual_cost_usd")
    lines = "\n".join(
        f"| {row.provider} | {row.local_total_annual_cost_usd/1e9:.3f} | "
        f"{row.cloud_total_annual_cost_usd/1e9:.3f} | {row.cloud_to_local_cost_ratio:.3f} | "
        f"{row.local_savings_vs_cloud_fraction:.1%} |"
        for row in base.itertuples(index=False)
    )
    findings = (
        "# Local vs. cloud cost for 21 U.S. NAICS manufacturing industries\n\n"
        "The primary local boundary sizes each of the 21 industries separately and then sums them; the cloud side uses "
        "the same service contract as the China national cost ledger: "
        "managed/API services and residual CPU/GPU capacity are mutually exclusive, and residual capacity is pooled nationwide across the U.S. "
        "The U.S. has no formal RAG, agent-runtime, or QLoRA price quotes that correspond exactly to the China ledger, so this table does not present them as observed costs.\n\n"
        "| API provider | Local USD bn/yr | Cloud USD bn/yr | Cloud/local | Local savings |\n"
        "|---|---:|---:|---:|---:|\n" + lines + "\n"
    )
    (args.output_dir / "findings.md").write_text(findings, encoding="utf-8")

    done = {
        "status": "complete_validated_us_21_naics_shared_cloud_service_contract",
        "model_version": expected_model_version,
        "demand_case_version": expected_demand_version,
        "industries": 21,
        "demand_cases": sorted(detail.parameter_case.unique()),
        "cpu_price_cases": sorted(detail.cpu_server_price_case.unique()),
        "providers": sorted(api_prices.provider.unique()),
        "aggregation_boundary": NATIONAL_AGGREGATION_BOUNDARY,
        "cloud_delivery_contract_case": contract_case,
        "cloud_delivery_contract_source": str(args.cloud_delivery_config),
        "cloud_routing_contract_source": str(args.cloud_routing_config),
        "managed_and_residual_service_are_mutually_exclusive": True,
        "cloud_capacity_pooling": "national_21_naics_fixed_profile_pool",
        "installed_capacity_rule": gpu_config["installed_capacity_rule"],
        "planning_reserve_fraction": float(gpu_config["installed_reserve_fraction"]),
        "n_plus_spare_server_groups": int(gpu_config["n_plus_spare_server_groups"]),
        "normal_dispatch_reserve_fraction": float(gpu_config["normal_dispatch_reserve_fraction"]),
        "reference_compute_h_per_service_unit": reference_compute_h_per_service,
        "common_it_effective_efficiency_case": demand_config["compute"]["common_it_effective_efficiency_case"],
        "common_it_effective_efficiency_multiplier": float(selected_efficiency.iloc[0].common_it_effective_efficiency_multiplier),
        "baseline_reference_workload_per_service_unit": float(selected_efficiency.iloc[0].baseline_reference_workload_per_service_unit),
        "excluded_unpriced_managed_components": [
            "RAG_runtime_and_embedding",
            "Agent_session_and_MCP_runtime",
            "QLoRA_SFT_and_adapted_model_lifecycle",
        ],
        "interpretation_boundary": "enterprise_payment_screen_with_public_prices_not_social_cost_or_procurement_recommendation",
        "input_sha256": {
            "demand": sha256(args.demand),
            "national_task_summary": sha256(args.national_task_summary),
            "demand_config": sha256(args.demand_config),
            "routing_config": sha256(args.routing_config),
            "cloud_routing_config": sha256(args.cloud_routing_config),
            "cloud_delivery_config": sha256(args.cloud_delivery_config),
            "us_cost_config": sha256(args.us_cost_config),
            "us_parameters": sha256(args.us_parameters),
            "us_api_prices": sha256(args.us_api_prices),
            "compute_efficiency": sha256(args.compute_efficiency),
        },
    }
    (args.output_dir / "validated.done.json").write_text(
        json.dumps(done, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
