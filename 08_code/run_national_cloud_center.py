#!/usr/bin/env python3
"""Optimize all 31 manufacturing-industry AI workloads in one logical LDC pool.

Purpose: Screen the aggregate new large-data-centre capacity portfolio required for the national six-task workload.
Workflow status: Active optional physical post-processing scenario; it is separate from the complete cloud-payment ledger.
Scientific boundary: Pool all configured industry workloads in one logical resource pool and optimize aggregate CPU/GPU capacity, facility power, and grid import; do not infer that the capacity is located at one physical site.
Inputs: Defaults/run configuration, industry service and load inputs, hourly prices, and cloud-center scenario parameters.
Outputs: Centralized physical summary, hourly accounting, and resolved run metadata.
Key assumptions: Workloads share one logical capacity pool and use the configured common-equivalent throughput, reserve, and LDC facility-efficiency rules.
Explicit exclusions: This is not a provider billing model, a physical-site allocation, or evidence that a tightly coupled job fits at any one site; it does not include WAN, latency, regional allocation, or empirical cloud performance.
Validation/tests: Input coverage, service conservation, capacity, and power identities are checked by the corresponding core validators.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.capacity import average_required_server_groups, local_installed_capacity_floor
from core.config import load_config, write_resolved_config
from core.data import FlexibleJob, load_industry_inputs, read_core_grid_energy_prices
from core.io import write_csv
from core.model import optimize_host


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--defaults", type=Path, required=True)
    parser.add_argument("--run-config", type=Path, required=True)
    parser.add_argument("--cloud-config", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--hourly-output", type=Path, required=True)
    parser.add_argument("--resolved-config-output", type=Path, required=True)
    return parser.parse_args()


def apply_ldc_model_state_boundary(config: dict, registry: dict) -> dict:
    """Apply the LDC-only lifecycle boundary declared by its registry."""
    model_state = registry.get("model_state")
    if not isinstance(model_state, dict) or model_state.get("enabled") is not False:
        raise ValueError(
            "LDC cloud config must explicitly disable model-state lifecycle floors"
        )
    resolved = deepcopy(config)
    if not isinstance(resolved.get("model_state"), dict):
        raise ValueError("Resolved run config is missing model_state settings")
    resolved["model_state"]["enabled"] = False
    return resolved


def main() -> None:
    args = parse_args()
    config = load_config(ROOT, args.defaults, args.run_config)
    registry = yaml.safe_load((ROOT / args.cloud_config).read_text(encoding="utf-8"))
    cloud = registry["national_cloud_center"]
    industries = list(registry["selected_industries"])
    if industries != list(config["selected_industries"]):
        raise ValueError("Cloud-center industry list must match its run config")

    horizon = int(config["model"]["horizon_hours"])
    rigid_by_task: dict[str, np.ndarray] = {}
    jobs: list[FlexibleJob] = []
    daily_service = 0.0
    for industry in industries:
        inputs = load_industry_inputs(config, industry)
        daily_service += float(inputs.daily_effective_service_units)
        for task, values in inputs.rigid_service_units_by_task.items():
            rigid_by_task[task] = rigid_by_task.get(task, np.zeros(horizon)) + values
        jobs.extend(inputs.flexible_jobs)
    rigid = sum(rigid_by_task.values(), np.zeros(horizon))

    routing = yaml.safe_load(
        (ROOT / config["compute_hardware"]["routing_config"]).read_text(encoding="utf-8")
    )
    routing_case = str(routing["active_core_routing_case"])
    cpu_fractions = {
        task: float(value) for task, value in routing["routing_cases"][routing_case].items()
    }
    cpu_multipliers = {
        task: float(value)
        for task, value in routing["core_cpu_server_hour_per_reference_compute_hour"].items()
        if task != "rationale"
    }
    cloud_config = apply_ldc_model_state_boundary(config, registry)
    if bool(cloud_config["model_state"]["enabled"]):
        raise ValueError("LDC infrastructure core must disable model-state lifecycle floors")
    cloud_config["energy"]["pv_capacity_mode"] = str(cloud["pv_capacity_mode"])
    cloud_config["energy"]["battery_investment_enabled"] = bool(
        cloud["battery_investment_enabled"]
    )
    cloud_config["server"]["marginal_facility_multiplier"] = float(
        cloud["gpu_facility_multiplier"]
    )
    cloud_config["server"]["installed_reserve_fraction"] = float(
        cloud["installed_reserve_fraction"]
    )
    cloud_config["server"]["n_plus_spare_server_groups"] = int(
        cloud["n_plus_spare_server_groups"]
    )
    cpu_server = deepcopy(routing["cpu_server"])
    cpu_price_case = str(cloud_config["compute_hardware"].get("local_cpu_price_case", "base"))
    cpu_price_cases = cpu_server.get("purchase_cost_cases_rmb", {})
    if cpu_price_case not in cpu_price_cases:
        raise ValueError(f"Unsupported local CPU purchase-price case: {cpu_price_case}")
    cpu_server["purchase_price_case"] = cpu_price_case
    cpu_server["purchase_cost_rmb"] = float(cpu_price_cases[cpu_price_case])
    cpu_server["marginal_facility_multiplier"] = float(cloud["cpu_facility_multiplier"])
    cpu_server["installed_reserve_fraction"] = float(cloud["installed_reserve_fraction"])
    cpu_server.setdefault("normal_dispatch_reserve_fraction", 0.0)

    arrival_by_task = {task: values.copy() for task, values in rigid_by_task.items()}
    for job in jobs:
        arrival_by_task[job.task_id][job.release_hour] += job.amount_service_units
    reference_compute_h = float(cloud_config["demand"]["effective_service"]["reference_compute_h_per_service_unit"])
    gpu_compute = np.zeros(horizon)
    cpu_compute = np.zeros(horizon)
    for task, arrivals in arrival_by_task.items():
        cpu_fraction = float(cpu_fractions.get(task, 0.0))
        gpu_compute += arrivals * reference_compute_h * (1.0 - cpu_fraction)
        cpu_compute += arrivals * reference_compute_h * cpu_fraction * float(cpu_multipliers.get(task, 1.0))
    gpu_required = average_required_server_groups(
        float(gpu_compute.sum()),
        horizon,
        float(cloud_config["server"]["accelerators_per_server"]),
    )
    cpu_required = average_required_server_groups(
        float(cpu_compute.sum()),
        horizon,
        float(cpu_server["service_capacity_cpu_server_h_per_h"]),
    )
    floors = {
        "gpu": local_installed_capacity_floor(
            gpu_required,
            float(cloud["installed_reserve_fraction"]),
            int(cloud["n_plus_spare_server_groups"]),
        ),
        "cpu": local_installed_capacity_floor(
            cpu_required,
            float(cloud["installed_reserve_fraction"]),
            int(cloud["n_plus_spare_server_groups"]),
        ) if cpu_required > 0 else 0.0,
    }
    result = optimize_host(
        cloud_config,
        base_load_mw=np.full(horizon, float(cloud["base_load_mw"])),
        pv_capacity_factor=np.zeros(horizon),
        roof_area_m2=1.0,
        rigid_service_units=rigid,
        flexible_jobs=tuple(jobs),
        grid_energy_price_rmb_per_mwh=read_core_grid_energy_prices(cloud_config),
        existing_grid_capacity_mw=float(cloud["existing_grid_capacity_mw"]),
        rigid_service_units_by_task=rigid_by_task,
        heterogeneous_hardware={
            "routing_case": routing_case,
            "cpu_fraction_by_task": cpu_fractions,
            "cpu_compute_multiplier_by_task": cpu_multipliers,
            "cpu_server": cpu_server,
        },
        minimum_installed_hardware_groups=floors,
    )
    represented_days = float(result.summary["represented_days"])
    row = {
        "scenario_version": registry["scenario_version"],
        "model_version": config["model_version"],
        "architecture": cloud["architecture"],
        "architecture_display_label": cloud["display_architecture"],
        "industry_count": len(industries),
        "active_hardware_routing_case": routing_case,
        "flexibility_scenario": config["demand"]["flexibility_scenario"],
        "common_it_effective_efficiency_case": config["demand"]["effective_service"]["common_it_effective_efficiency_case"],
        "common_it_effective_efficiency_multiplier": config["demand"]["effective_service"]["common_it_effective_efficiency_multiplier"],
        "baseline_reference_workload_per_service_unit": config["demand"]["effective_service"]["baseline_reference_workload_per_service_unit"],
        "reference_compute_h_per_service_unit": reference_compute_h,
        "reference_server_group": config["server"]["configuration"],
        "planning_reserve_fraction": cloud["installed_reserve_fraction"],
        "n_plus_spare_server_groups": cloud["n_plus_spare_server_groups"],
        "model_state_minimum_groups_enabled": False,
        "installed_server_groups_integer": bool(
            cloud_config["model"].get(
                "installed_server_groups_integer",
                cloud_config["model"]["server_groups_integer"],
            )
        ),
        "online_server_groups_integer": bool(
            cloud_config["model"].get(
                "online_server_groups_integer",
                cloud_config["model"]["server_groups_integer"],
            )
        ),
        "solver_name": str(cloud_config["model"]["solver"]["name"]),
        "solver_status": "ok",
        "solver_condition": "optimal",
        "daily_effective_service_units": daily_service,
        "reconstructed_daily_effective_service_units": float(result.hourly["ai_executed_service_units"].sum()) / represented_days,
        "gpu_facility_multiplier": cloud_config["server"]["marginal_facility_multiplier"],
        "cpu_facility_multiplier": cpu_server["marginal_facility_multiplier"],
        "installed_gpu_server_groups": result.summary["installed_gpu_server_groups"],
        "installed_cpu_server_groups": result.summary["installed_cpu_server_groups"],
        "average_required_gpu_server_groups": float(result.hourly["gpu_compute_h"].mean()) / float(cloud_config["server"]["accelerators_per_server"]),
        "average_required_cpu_server_groups": float(result.hourly["cpu_compute_h"].mean()) / float(cpu_server["service_capacity_cpu_server_h_per_h"]),
        "annual_ai_facility_energy_twh": result.summary["annual_ai_facility_energy_twh"],
        "ai_facility_peak_mw": result.summary["ai_facility_peak_mw"],
        "grid_import_peak_mw": result.summary["grid_import_peak_mw"],
        "incremental_grid_expansion_mw": result.summary["grid_expansion_mw"],
        "existing_grid_capacity_mw": result.summary["existing_grid_capacity_mw"],
        "interpretation": cloud["interpretation"],
    }
    average_required_total = row["average_required_gpu_server_groups"] + row["average_required_cpu_server_groups"]
    installed_total = row["installed_gpu_server_groups"] + row["installed_cpu_server_groups"]
    row["installed_total_server_capacity_to_average_demand_ratio"] = installed_total / average_required_total
    row["realized_total_installed_capacity_utilization_fraction"] = average_required_total / installed_total
    row["realized_total_capacity_redundancy_fraction_above_average"] = installed_total / average_required_total - 1.0
    if not np.isclose(
        row["daily_effective_service_units"],
        row["reconstructed_daily_effective_service_units"],
        rtol=1e-9,
    ):
        raise ValueError("National cloud center does not conserve effective service")
    if not np.isclose(row["grid_import_peak_mw"], row["incremental_grid_expansion_mw"], atol=1e-5):
        raise ValueError("Zero-capacity greenfield cloud node must expand to its full grid peak")
    write_csv(pd.DataFrame([row]), args.summary_output)
    write_csv(result.hourly, args.hourly_output)
    resolved = deepcopy(cloud_config)
    resolved["national_cloud_center"] = cloud
    write_resolved_config(resolved, args.resolved_config_output)


if __name__ == "__main__":
    main()
