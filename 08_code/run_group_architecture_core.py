#!/usr/bin/env python3
"""Run the active PF, SHG, and MSG group-architecture model.

Purpose:
    Execute the active group-architecture physical core and write one
    auditable package per industry.
Workflow status:
    Active v1.0.0 China physical-core executor and shared mechanism-sensitivity
    executor. The Snakemake core rule calls this file once per industry.
Scientific boundary:
    Reconstruct the same weekly six-task AI service under independent-factory,
    group single-host, and group multisite deployment. The model jointly chooses
    CPU/GPU installation, hourly online capacity, deadline-constrained task
    execution, facility power, grid import, and enterprise operating cost.
Inputs:
    Merged defaults/run configuration, a group-architecture experiment registry,
    processed task-service inputs, production-load calibration, representative
    group parameters, EWELD complete-week load profiles, and
    ``config/compute_hardware/cpu_gpu_routing_v1.yaml``. The v1 routing file is
    the physical-core routing contract: it maps tasks to CPU/GPU service time
    and power/capacity requirements. It is not the v2 cloud-product billing
    route and the two files are not version alternatives for this solver.
Outputs:
    ``summary.csv``, ``hourly.csv``, ``curve_lineage.csv``,
    ``load_alignment_value.csv``, the internal ``MSG-no-routing`` paired-control
    files, and ``metadata.json`` in the selected output directory.
Key assumptions:
    PF installed CPU/GPU groups are integer; SHG and MSG use
    continuous equivalent installation. Online groups are continuous. Installed
    capacity has an average-demand planning floor plus configured headroom and
    optional N+k spare; hourly throughput and deadlines may require more.
Explicit exclusions:
    The active core excludes PV, batteries, network costs, latency penalties,
    and task-level data-residency constraints.
Validation/tests:
    This script checks service conservation, power decomposition, integer
    boundaries, node weights, and architecture/base-load coverage. The national
    package is then checked by ``summarize_group_multisite_core.py`` and the
    solver-option unit tests.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import linopy
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "08_code"))

from core.config import deep_merge, load_config
from core.data import load_industry_inputs, read_core_grid_energy_prices, scale_task_workload
from core.adoption import conditioning_from_config
from core.model import annual_server_cost_per_group
from core.production_load import resolve_site_mean_load_mw
from core.representative_group import read_representative_groups
from prepare_eweld_representative_weeks import complete_weeks


INTEGER_INSTALLED_CAPACITY_BY_ARCHITECTURE = {
    "PF": True,
    "SHG": False,
    "MSG": False,
}

COORDINATION_EFFECT_METRICS = (
    "sum_incremental_grid_peak_mw",
    "installed_gpu_server_groups",
    "installed_cpu_server_groups",
    "annual_ai_facility_energy_twh",
    "annual_ai_fixed_overhead_energy_twh",
    "annual_unshiftable_ai_active_energy_twh",
    "annual_shiftable_ai_active_energy_twh",
    "annual_incremental_total_cost_rmb",
)


def normalized_fixed_site_shares(shares: list[float] | np.ndarray, site_count: int) -> np.ndarray:
    """Validate ex-ante task-origin shares for the MSG no-routing control."""
    values = np.asarray(shares, dtype=float)
    if values.shape != (site_count,):
        raise ValueError("fixed_site_service_shares must contain one value per MSG node")
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("fixed_site_service_shares must be finite and non-negative")
    total = float(values.sum())
    if total <= 0 or abs(total - 1.0) > 1e-12:
        raise ValueError("fixed_site_service_shares must sum to one")
    return values


def build_coordination_effect_row(
    industry: str,
    no_routing: dict,
    coordinated: dict,
) -> dict[str, object]:
    """Return MSG-no-routing minus MSG-coordinated paired mechanism effects."""
    row: dict[str, object] = {
        "industry": industry,
        "model_version": coordinated["model_version"],
        "common_it_effective_efficiency_case": coordinated["common_it_effective_efficiency_case"],
        "common_it_effective_efficiency_multiplier": coordinated["common_it_effective_efficiency_multiplier"],
        "planning_reserve_fraction": coordinated["planning_reserve_fraction"],
        "n_plus_spare_server_groups": coordinated["n_plus_spare_server_groups"],
        "reference_server_group": coordinated["reference_server_group"],
        "control_code": "MSG_NO_ROUTING",
        "control_label": "MSG-no-routing",
        "treatment_code": "MSG",
        "treatment_label": "MSG-coordinated",
        "effect_definition": "MSG_no_routing_minus_MSG_coordinated",
        "positive_value_interpretation": "burden_avoided_by_cross_site_coordination",
    }
    for metric in COORDINATION_EFFECT_METRICS:
        control_value = float(no_routing[metric])
        treatment_value = float(coordinated[metric])
        row[f"msg_no_routing_{metric}"] = control_value
        row[f"msg_coordinated_{metric}"] = treatment_value
        row[f"coordination_effect_{metric}"] = control_value - treatment_value
    return row


def validate_integer_boundary(experiment: dict) -> None:
    """Keep integer server installation exclusive to independent factories."""
    boundary = experiment.get("integer_boundary", {})
    for architecture, expected in INTEGER_INSTALLED_CAPACITY_BY_ARCHITECTURE.items():
        field = f"{architecture}_installed_server_groups_integer"
        configured = boundary.get(field, expected)
        if not isinstance(configured, bool) or configured is not expected:
            raise ValueError(
                f"{field} must be {str(expected).lower()}: only PF uses integer "
                "installed server groups; both group architectures use continuous "
                "equivalent capacity"
            )
    if boundary.get("online_server_groups_integer", False) is not False:
        raise ValueError("online_server_groups_integer must be false for all group-architecture cases")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--defaults", type=Path, default=Path("config/defaults.yaml"))
    parser.add_argument("--config", type=Path, default=Path("config/runs/all_industries_core.yaml"))
    parser.add_argument("--experiment", type=Path, default=Path("config/sensitivity/c36_group_multisite_continuous_v1.yaml"))
    parser.add_argument("--output-dir", type=Path, default=Path("05_results/sensitivity/v1.0.0/group_multisite_continuous/C36"))
    parser.add_argument("--industry", help="Override experiment.industry; used by the 31-industry core workflow.")
    parser.add_argument(
        "--architectures",
        nargs="+",
        help="Override experiment/run-config architectures; used by SHG-only sensitivity screens.",
    )
    parser.add_argument("--describe-only", action="store_true", help="Report continuous variable counts without solving.")
    return parser.parse_args()


def select_factory_weeks(
    archive: Path,
    target: np.ndarray,
    factory_count: int,
    source_isic: int,
    quality: dict | None = None,
) -> tuple[list[dict], np.ndarray]:
    quality = quality or {}
    minimum_monday_ratio = float(
        quality.get("minimum_monday_to_tuesday_friday_mean_ratio", 0.0)
    )
    maximum_weekday_cv = float(quality.get("maximum_weekday_daily_mean_cv", np.inf))
    maximum_peak_to_mean = float(quality.get("maximum_weekly_peak_to_mean_ratio", np.inf))
    pattern = re.compile(rf"^EWELD/Electricity Consumption/C/C{source_isic:02d} .+/(?P<user>U\d+)\.csv$")
    candidates: dict[
        str,
        list[tuple[float, pd.Timestamp, str, np.ndarray, float, float, float, float]],
    ] = defaultdict(list)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            match = pattern.match(member)
            if not match:
                continue
            with zf.open(member) as handle:
                frame = pd.read_csv(handle, usecols=["Time", "Value"])
            for monday, week in complete_weeks(frame):
                raw = week["raw_value"].to_numpy(float)
                days = raw.reshape(7, 24)
                daily_mean = days.mean(axis=1, keepdims=True)
                if (daily_mean <= 0).any():
                    continue
                shapes = days / daily_mean
                typical = np.median(shapes, axis=0)
                rmse = float(np.sqrt(np.mean((typical - target) ** 2)))
                daily_values = daily_mean[:, 0]
                monday_ratio = float(daily_values[0] / daily_values[1:5].mean())
                weekday_cv = float(daily_values[:5].std() / daily_values[:5].mean())
                weekend_ratio = float(daily_values[5:].mean() / daily_values[:5].mean())
                peak_to_mean = float(raw.max() / raw.mean())
                if monday_ratio < minimum_monday_ratio:
                    continue
                if weekday_cv > maximum_weekday_cv:
                    continue
                if peak_to_mean > maximum_peak_to_mean:
                    continue
                candidates[match.group("user")].append(
                    (
                        rmse,
                        monday,
                        member,
                        raw,
                        monday_ratio,
                        weekday_cv,
                        weekend_ratio,
                        peak_to_mean,
                    )
                )
    if not candidates:
        raise ValueError(f"No usable EWELD users for ISIC {source_isic}")
    selected = []
    for user in sorted(candidates, key=lambda value: int(value[1:])):
        candidate = min(candidates[user], key=lambda row: (row[0], row[1]))
        selected.append((user, *candidate))
        if len(selected) == factory_count:
            break
    if len(selected) < factory_count:
        used = {(row[0], row[2]) for row in selected}
        remaining = sorted(
            (
                (user, *candidate)
                for user, weeks in candidates.items()
                for candidate in weeks
                if (user, candidate[1]) not in used
            ),
            key=lambda row: (row[1], row[2], int(row[0][1:])),
        )
        selected.extend(remaining[: factory_count - len(selected)])
    if len(selected) != factory_count:
        raise ValueError(f"Need {factory_count} distinct weeks for ISIC {source_isic}, found {len(selected)}")
    lineage = []
    curves = []
    user_counts = defaultdict(int)
    for (
        user,
        rmse,
        monday,
        member,
        raw,
        monday_ratio,
        weekday_cv,
        weekend_ratio,
        peak_to_mean,
    ) in selected:
        user_counts[user] += 1
        curves.append(raw / float(raw.mean()))
        lineage.append({
            "factory_id": f"F{len(lineage) + 1}",
            "source_user": user,
            "source_member": member,
            "week_start": monday.date().isoformat(),
            "week_end": (monday + pd.Timedelta(days=6)).date().isoformat(),
            "same_user_week_sequence": user_counts[user],
            "curve_role": "distinct_user_factory_proxy" if user_counts[user] == 1 else "same_user_distinct_week_factory_proxy",
            "shape_rmse_to_industry_core": rmse,
            "monday_to_tuesday_friday_mean_ratio": monday_ratio,
            "weekday_daily_mean_cv": weekday_cv,
            "weekend_to_weekday_mean_ratio": weekend_ratio,
            "weekly_peak_to_mean_ratio": peak_to_mean,
            "calendar_interpretation": "weekday_hour_aligned_synthetic_simultaneous_week",
        })
    return lineage, np.asarray(curves, dtype=float)


def hardware_parameters(config: dict) -> tuple[dict, dict, dict, dict]:
    routing = yaml.safe_load((ROOT / config["compute_hardware"]["routing_config"]).read_text(encoding="utf-8"))
    case = str(config["compute_hardware"].get("routing_case", routing["active_core_routing_case"]))
    cpu_fraction = {task: float(value) for task, value in routing["routing_cases"][case].items()}
    cpu_multiplier = {
        task: float(value)
        for task, value in routing["core_cpu_server_hour_per_reference_compute_hour"].items()
        if task != "rationale"
    }
    cpu = deep_merge(dict(routing["cpu_server"]), dict(config["compute_hardware"].get("cpu_server_overrides", {})))
    price_case = str(config["compute_hardware"].get("local_cpu_price_case", "base"))
    cpu["purchase_cost_rmb"] = float(cpu["purchase_cost_cases_rmb"][price_case])
    cpu.setdefault("normal_dispatch_reserve_fraction", 0.0)
    return {"gpu": deepcopy(config["server"]), "cpu": cpu}, cpu_fraction, cpu_multiplier, {"routing_case": case, "cpu_price_case": price_case}


def balanced_factory_weights(physical_factory_count: int, modeled_node_count: int) -> np.ndarray:
    """Assign every physical factory to one representative node with near-equal integer weights."""
    if not 1 <= modeled_node_count <= physical_factory_count:
        raise ValueError("modeled_node_count must be between one and physical_factory_count")
    quotient, remainder = divmod(physical_factory_count, modeled_node_count)
    weights = np.full(modeled_node_count, quotient, dtype=int)
    weights[:remainder] += 1
    if int(weights.sum()) != physical_factory_count or (weights <= 0).any():
        raise AssertionError("Invalid representative factory weights")
    return weights


def resolve_population_count(setting: object, representative_group_count: int, label: str) -> int:
    """Resolve one physical population without coupling it to another population."""
    if setting in {None, "representative_group_case", "registry_or_representative_group_case"}:
        value = int(representative_group_count)
    else:
        value = int(setting)
    if value < 1:
        raise ValueError(f"{label} must be positive")
    return value


def aggregate_site_power_weights(
    site_power_weights: list[float], node_site_counts: np.ndarray
) -> np.ndarray:
    """Aggregate ordered physical-site power shares into representative routing nodes."""
    site_weights = np.asarray(site_power_weights, dtype=float)
    counts = np.asarray(node_site_counts, dtype=int)
    if len(site_weights) != int(counts.sum()):
        raise ValueError("Production-site power weights do not match the registered site count")
    if not np.isfinite(site_weights).all() or (site_weights <= 0).any():
        raise ValueError("Production-site power weights must be finite and positive")
    site_weights = site_weights / site_weights.sum()
    boundaries = np.concatenate(([0], np.cumsum(counts)))
    node_weights = np.asarray(
        [site_weights[boundaries[index]:boundaries[index + 1]].sum() for index in range(len(counts))]
    )
    if not np.isclose(node_weights.sum(), 1.0):
        raise AssertionError("Representative-node power shares must sum to one")
    return node_weights


def build_solver_options(config: dict, solver_name: str) -> dict:
    """Return the frozen solver controls used by every architecture solve."""
    solver = config["model"]["solver"]
    configured_name = str(solver["name"])
    if configured_name != solver_name:
        raise ValueError(
            f"Experiment solver {solver_name} does not match configured solver {configured_name}"
        )
    if solver_name == "gurobi":
        return {
            "Threads": int(solver.get("threads", 1)),
            "MIPGap": float(solver.get("mip_gap", 0.001)),
            # Keep this last so Gurobi records the resource controls before
            # console output is disabled.
            "LogToConsole": int(bool(solver.get("log_to_console", False))),
        }
    if solver_name == "highs":
        return {
            "log_to_console": bool(solver.get("log_to_console", False)),
            "mip_rel_gap": float(solver.get("mip_gap", 0.001)),
            "threads": int(solver.get("threads", 1)),
        }
    raise ValueError(f"Unsupported solver: {solver_name}")


def solve_with_configured_options(model, config: dict, solver_name: str):
    """Solve with options expanded for the linopy ``Model.solve`` API."""
    options = build_solver_options(config, solver_name)
    solve_kwargs = {"solver_name": solver_name, **options}
    if solver_name == "gurobi":
        # Apply the thread ceiling when the Gurobi environment is created as
        # well as on the model. This avoids a large default worker pool during
        # linopy's direct model transfer on high-core-count hosts.
        solve_kwargs["env"] = {"Threads": options["Threads"]}
    return model.solve(**solve_kwargs)


def solve_architecture(
    *,
    architecture: str,
    config: dict,
    base_loads: np.ndarray,
    rigid_by_task: dict[str, np.ndarray],
    jobs: tuple,
    grid_prices: np.ndarray,
    servers: dict,
    cpu_fraction: dict,
    cpu_multiplier: dict,
    solver_name: str,
    installed_integer: bool,
    base_load_case: str,
    fixed_site_service_shares: list[float] | np.ndarray | None = None,
) -> tuple[dict, pd.DataFrame]:
    """Solve one group architecture and return summary plus hourly accounting.

    The solve jointly enforces task deadlines, CPU/GPU capacity, facility
    power, grid import, and the architecture-specific installation boundary.
    ``base_load_case`` records whether the matched actual or zero-load pairing
    is being solved.
    """
    sites = list(range(base_loads.shape[0]))
    hours = range(base_loads.shape[1])
    tasks = sorted(rigid_by_task)
    hardware = ["gpu", "cpu"]
    fixed_shares = (
        normalized_fixed_site_shares(fixed_site_service_shares, len(sites))
        if fixed_site_service_shares is not None
        else None
    )
    annual_periods = float(config["model"]["annualization_days"]) / (len(list(hours)) / 24.0)
    discount = float(config["model"]["discount_rate"])
    demand_rate = float(config["energy"]["maximum_demand_rmb_per_kw_month"]) * 1000.0 * 12.0
    reference_compute_factor = float(config["demand"]["effective_service"]["reference_compute_h_per_service_unit"])
    reserve = float(servers["gpu"]["installed_reserve_fraction"])
    n_plus_spare = int(servers["gpu"].get("n_plus_spare_server_groups", 0))
    if any(int(servers[name].get("n_plus_spare_server_groups", n_plus_spare)) != n_plus_spare for name in hardware):
        raise ValueError("GPU/CPU n_plus_spare_server_groups must match within one solve")
    if any(abs(float(servers[name]["installed_reserve_fraction"]) - reserve) > 1e-12 for name in hardware):
        raise ValueError("GPU/CPU installed_reserve_fraction must match within one solve")

    model = linopy.Model()
    site_index = pd.Index(sites, name="site")
    hardware_index = pd.Index(hardware, name="hardware")
    hour_index = pd.Index(list(hours), name="hour")
    installed = model.add_variables(lower=0.0, integer=installed_integer, coords=[site_index, hardware_index], name="installed")
    online = model.add_variables(lower=0.0, coords=[site_index, hardware_index, hour_index], name="online")
    peak = model.add_variables(lower=0.0, coords=[site_index], name="grid_peak")

    rigid_keys = [(hour, task, site) for hour in hours for task in tasks for site in sites]
    rigid_index = pd.Index(range(len(rigid_keys)), name="rigid_assignment")
    rigid_route = model.add_variables(lower=0.0, coords=[rigid_index], name="rigid_route")
    rigid_lookup: dict[tuple[int, str, int], int] = {key: idx for idx, key in enumerate(rigid_keys)}
    for hour in hours:
        for task in tasks:
            indices = [rigid_lookup[(hour, task, site)] for site in sites]
            if fixed_shares is None:
                model.add_constraints(
                    rigid_route.sel(rigid_assignment=indices).sum() == float(rigid_by_task[task][hour]),
                    name=f"rigid_service_{hour}_{task}",
                )
            else:
                for site, index in zip(sites, indices):
                    model.add_constraints(
                        rigid_route.sel(rigid_assignment=index)
                        == float(rigid_by_task[task][hour]) * float(fixed_shares[site]),
                        name=f"rigid_origin_share_{hour}_{task}_{site}",
                    )

    flexible_keys: list[tuple[int, int, str, int]] = []
    by_job: dict[int, list[int]] = defaultdict(list)
    by_site_hour_task: dict[tuple[int, int, str], list[int]] = defaultdict(list)
    for job_idx, job in enumerate(jobs):
        admissible = sorted({(job.release_hour + offset) % len(list(hours)) for offset in range(job.deadline_hours + 1)})
        for site in sites:
            for hour in admissible:
                idx = len(flexible_keys)
                flexible_keys.append((job_idx, hour, job.task_id, site))
                by_job[job_idx].append(idx)
                by_site_hour_task[(site, hour, job.task_id)].append(idx)
    flexible_index = pd.Index(range(len(flexible_keys)), name="flexible_assignment")
    flexible_route = model.add_variables(lower=0.0, coords=[flexible_index], name="flexible_route")
    for job_idx, job in enumerate(jobs):
        if fixed_shares is None:
            model.add_constraints(
                flexible_route.sel(flexible_assignment=by_job[job_idx]).sum() == float(job.amount_service_units),
                name=f"flexible_service_{job_idx}",
            )
        else:
            for site in sites:
                site_indices = [
                    idx for idx in by_job[job_idx]
                    if flexible_keys[idx][3] == site
                ]
                model.add_constraints(
                    flexible_route.sel(flexible_assignment=site_indices).sum()
                    == float(job.amount_service_units) * float(fixed_shares[site]),
                    name=f"flexible_origin_share_{job_idx}_{site}",
                )

    server_cost = {name: annual_server_cost_per_group(server, discount) for name, server in servers.items()}
    objective = sum(server_cost[name] * installed.sel(hardware=name).sum() for name in hardware)
    objective += demand_rate * peak.sum()
    power_expr: dict[tuple[int, int], object] = {}
    compute_expr: dict[tuple[int, int, str], object] = {}
    for site in sites:
        for hour in hours:
            task_service = {}
            for task in tasks:
                rigid_value = rigid_route.sel(rigid_assignment=rigid_lookup[(hour, task, site)])
                flex_indices = by_site_hour_task.get((site, hour, task), [])
                flexible_value = flexible_route.sel(flexible_assignment=flex_indices).sum() if flex_indices else 0.0
                task_service[task] = rigid_value + flexible_value
            power_terms = []
            for name in hardware:
                compute = 0
                for task, service in task_service.items():
                    cpu_share = float(cpu_fraction.get(task, 0.0))
                    fraction = cpu_share if name == "cpu" else 1.0 - cpu_share
                    multiplier = float(cpu_multiplier.get(task, 1.0)) if name == "cpu" else 1.0
                    compute += service * reference_compute_factor * fraction * multiplier
                compute_expr[(site, hour, name)] = compute
                server = servers[name]
                capacity = float(server["service_capacity_cpu_server_h_per_h"] if name == "cpu" else server["accelerators_per_server"])
                online_value = online.sel(site=site, hardware=name, hour=hour)
                installed_value = installed.sel(site=site, hardware=name)
                model.add_constraints(online_value <= installed_value, name=f"online_installed_{site}_{name}_{hour}")
                model.add_constraints(compute <= capacity * online_value, name=f"online_capacity_{site}_{name}_{hour}")
                pue = float(server["marginal_facility_multiplier"])
                maximum = float(server["maximum_wall_power_kw"])
                idle = float(server["online_idle_wall_power_kw"])
                standby = float(server["cold_spare_standby_power_kw"])
                power_terms.append(pue / 1000.0 * (standby * installed_value + (idle - standby) * online_value + (maximum - idle) / capacity * compute))
            power = sum(power_terms)
            power_expr[(site, hour)] = power
            model.add_constraints(float(base_loads[site, hour]) + power <= peak.sel(site=site), name=f"grid_peak_{site}_{hour}")
            objective += annual_periods * float(grid_prices[hour]) * power
    for site in sites:
        for name in hardware:
            server = servers[name]
            capacity = float(server["service_capacity_cpu_server_h_per_h"] if name == "cpu" else server["accelerators_per_server"])
            average_compute = sum(compute_expr[(site, hour, name)] for hour in hours) / len(list(hours))
            reserve_fraction = float(server["installed_reserve_fraction"])
            spare_groups = int(server.get("n_plus_spare_server_groups", 0))
            if spare_groups < 0:
                raise ValueError("n_plus_spare_server_groups must be non-negative")
            average_required = average_compute / capacity
            model.add_constraints(
                installed.sel(site=site, hardware=name) >= (1.0 + reserve_fraction) * average_required,
                name=f"average_demand_planning_capacity_{site}_{name}",
            )
            if spare_groups:
                model.add_constraints(
                    installed.sel(site=site, hardware=name) >= average_required + spare_groups,
                    name=f"n_plus_spare_capacity_{site}_{name}",
                )
    model.objective = objective
    status, condition = solve_with_configured_options(model, config, solver_name)
    if status != "ok":
        raise RuntimeError(f"{architecture} solve failed: {status}/{condition}")

    installed_values = installed.solution.to_pandas()
    online_values = online.solution.to_series()
    peak_values = peak.solution.to_pandas()
    rigid_values = rigid_route.solution.to_numpy()
    flexible_values = flexible_route.solution.to_numpy()
    maximum_rigid_origin_share_error = 0.0
    maximum_flexible_origin_share_error = 0.0
    if fixed_shares is not None:
        for hour in hours:
            for task in tasks:
                total = float(rigid_by_task[task][hour])
                for site in sites:
                    observed = float(rigid_values[rigid_lookup[(hour, task, site)]])
                    maximum_rigid_origin_share_error = max(
                        maximum_rigid_origin_share_error,
                        abs(observed - total * float(fixed_shares[site])),
                    )
        for job_idx, job in enumerate(jobs):
            for site in sites:
                observed = sum(
                    float(flexible_values[idx])
                    for idx in by_job[job_idx]
                    if flexible_keys[idx][3] == site
                )
                maximum_flexible_origin_share_error = max(
                    maximum_flexible_origin_share_error,
                    abs(observed - float(job.amount_service_units) * float(fixed_shares[site])),
                )
    rows = []
    for site in sites:
        for hour in hours:
            service_by_task = {}
            rigid_service_by_task = {}
            flexible_service_by_task = {}
            for task in tasks:
                rigid_service = float(rigid_values[rigid_lookup[(hour, task, site)]])
                flexible_service = sum(
                    float(flexible_values[idx])
                    for idx in by_site_hour_task.get((site, hour, task), [])
                )
                rigid_service_by_task[task] = rigid_service
                flexible_service_by_task[task] = flexible_service
                service_by_task[task] = rigid_service + flexible_service
            compute_by_hardware = {}
            rigid_compute_by_hardware = {}
            flexible_compute_by_hardware = {}
            facility_power = 0.0
            fixed_overhead_power = 0.0
            unshiftable_active_power = 0.0
            shiftable_active_power = 0.0
            for name in hardware:
                rigid_compute = 0.0
                flexible_compute = 0.0
                for task in tasks:
                    cpu_share = float(cpu_fraction.get(task, 0.0))
                    fraction = cpu_share if name == "cpu" else 1.0 - cpu_share
                    multiplier = float(cpu_multiplier.get(task, 1.0)) if name == "cpu" else 1.0
                    conversion = reference_compute_factor * fraction * multiplier
                    rigid_compute += rigid_service_by_task[task] * conversion
                    flexible_compute += flexible_service_by_task[task] * conversion
                compute = rigid_compute + flexible_compute
                compute_by_hardware[name] = compute
                rigid_compute_by_hardware[name] = rigid_compute
                flexible_compute_by_hardware[name] = flexible_compute
                server = servers[name]
                capacity = float(server["service_capacity_cpu_server_h_per_h"] if name == "cpu" else server["accelerators_per_server"])
                online_count = float(online_values.loc[(site, name, hour)])
                installed_count = float(installed_values.loc[site, name])
                multiplier_pue = float(server["marginal_facility_multiplier"]) / 1000.0
                fixed_overhead_power += multiplier_pue * (
                    float(server["cold_spare_standby_power_kw"]) * installed_count
                    + (float(server["online_idle_wall_power_kw"]) - float(server["cold_spare_standby_power_kw"])) * online_count
                )
                active_coefficient = multiplier_pue * (
                    float(server["maximum_wall_power_kw"])
                    - float(server["online_idle_wall_power_kw"])
                ) / capacity
                unshiftable_active_power += active_coefficient * rigid_compute
                shiftable_active_power += active_coefficient * flexible_compute
            facility_power = fixed_overhead_power + unshiftable_active_power + shiftable_active_power
            rows.append({
                "architecture": architecture,
                "base_load_case": base_load_case,
                "routing_policy": "fixed_ex_ante_task_origin_shares" if fixed_shares is not None else "optimized_across_eligible_nodes",
                "factory_id": f"F{site + 1}",
                "hour": hour,
                "base_load_mw": float(base_loads[site, hour]),
                "ai_service_units": sum(service_by_task.values()),
                "unshiftable_ai_service_units": sum(rigid_service_by_task.values()),
                "shiftable_ai_service_units": sum(flexible_service_by_task.values()),
                "gpu_compute_h": compute_by_hardware["gpu"],
                "cpu_compute_h": compute_by_hardware["cpu"],
                "unshiftable_gpu_compute_h": rigid_compute_by_hardware["gpu"],
                "shiftable_gpu_compute_h": flexible_compute_by_hardware["gpu"],
                "unshiftable_cpu_compute_h": rigid_compute_by_hardware["cpu"],
                "shiftable_cpu_compute_h": flexible_compute_by_hardware["cpu"],
                "ai_fixed_overhead_power_mw": fixed_overhead_power,
                "unshiftable_ai_active_power_mw": unshiftable_active_power,
                "shiftable_ai_active_power_mw": shiftable_active_power,
                "ai_facility_power_mw": facility_power,
                "grid_import_mw": float(base_loads[site, hour]) + facility_power,
            })
    hourly = pd.DataFrame(rows)
    if not np.allclose(
        hourly["ai_facility_power_mw"],
        hourly[
            [
                "ai_fixed_overhead_power_mw",
                "unshiftable_ai_active_power_mw",
                "shiftable_ai_active_power_mw",
            ]
        ].sum(axis=1),
        rtol=0,
        atol=1e-10,
    ):
        raise AssertionError("AI facility-power decomposition does not reconstruct total power")
    if not np.allclose(
        hourly["ai_service_units"],
        hourly[["unshiftable_ai_service_units", "shiftable_ai_service_units"]].sum(axis=1),
        rtol=0,
        atol=1e-10,
    ):
        raise AssertionError("AI service decomposition does not reconstruct total service")
    base_peaks = base_loads.max(axis=1)
    incremental_demand_cost = float(np.sum(np.asarray(peak_values) - base_peaks) * demand_rate)
    annual_energy_cost = float(sum(row["ai_facility_power_mw"] * grid_prices[int(row["hour"])] * annual_periods for row in rows))
    annual_server_cost = float(sum(installed_values.loc[site, name] * server_cost[name] for site in sites for name in hardware))
    average_required_gpu_groups = float(hourly["gpu_compute_h"].sum()) / (len(list(hours)) * float(servers["gpu"]["accelerators_per_server"]))
    average_required_cpu_groups = float(hourly["cpu_compute_h"].sum()) / (len(list(hours)) * float(servers["cpu"]["service_capacity_cpu_server_h_per_h"]))
    average_required_total_groups = average_required_gpu_groups + average_required_cpu_groups
    installed_total_groups = float(installed_values["gpu"].sum() + installed_values["cpu"].sum())
    installed_to_average_ratio = installed_total_groups / average_required_total_groups
    summary = {
        "model_version": config["model_version"],
        "architecture": architecture,
        "base_load_case": base_load_case,
        "routing_policy": "fixed_ex_ante_task_origin_shares" if fixed_shares is not None else "optimized_across_eligible_nodes",
        "mechanism_control_only": fixed_shares is not None,
        "common_it_effective_efficiency_case": config["demand"]["effective_service"]["common_it_effective_efficiency_case"],
        "common_it_effective_efficiency_multiplier": config["demand"]["effective_service"]["common_it_effective_efficiency_multiplier"],
        "baseline_reference_workload_per_service_unit": config["demand"]["effective_service"]["baseline_reference_workload_per_service_unit"],
        "reference_compute_h_per_service_unit": reference_compute_factor,
        "reference_server_group": config["server"]["configuration"],
        "solver_status": status,
        "solver_condition": condition,
        "physical_factory_count": len(sites),
        "installed_server_groups_integer": installed_integer,
        "online_server_groups_integer": False,
        "n_plus_spare_server_groups": n_plus_spare,
        "model_state_minimum_groups_enabled": False,
        "planning_reserve_fraction": reserve,
        "installed_gpu_server_groups": float(installed_values["gpu"].sum()),
        "installed_cpu_server_groups": float(installed_values["cpu"].sum()),
        "average_required_gpu_server_groups": average_required_gpu_groups,
        "average_required_cpu_server_groups": average_required_cpu_groups,
        "average_required_total_server_groups": average_required_total_groups,
        "installed_total_server_capacity_to_average_demand_ratio": installed_to_average_ratio,
        "realized_total_installed_capacity_utilization_fraction": 1.0 / installed_to_average_ratio,
        "realized_total_capacity_redundancy_fraction_above_average": installed_to_average_ratio - 1.0,
        "annual_server_cost_rmb": annual_server_cost,
        "annual_ai_energy_cost_rmb": annual_energy_cost,
        "annual_incremental_maximum_demand_cost_rmb": incremental_demand_cost,
        "annual_incremental_total_cost_rmb": annual_server_cost + annual_energy_cost + incremental_demand_cost,
        "annual_ai_facility_energy_twh": float(hourly["ai_facility_power_mw"].sum() * annual_periods / 1e6),
        "annual_ai_fixed_overhead_energy_twh": float(hourly["ai_fixed_overhead_power_mw"].sum() * annual_periods / 1e6),
        "annual_unshiftable_ai_active_energy_twh": float(hourly["unshiftable_ai_active_power_mw"].sum() * annual_periods / 1e6),
        "annual_shiftable_ai_active_energy_twh": float(hourly["shiftable_ai_active_power_mw"].sum() * annual_periods / 1e6),
        "sum_incremental_grid_peak_mw": float(np.sum(np.maximum(np.asarray(peak_values) - base_peaks, 0.0))),
        "maximum_single_site_ai_facility_power_mw": float(hourly.groupby("factory_id")["ai_facility_power_mw"].max().max()),
        "weekly_service_units": float(hourly["ai_service_units"].sum()),
        "maximum_rigid_origin_share_absolute_error": maximum_rigid_origin_share_error,
        "maximum_flexible_origin_share_absolute_error": maximum_flexible_origin_share_error,
    }
    return summary, hourly


def main() -> None:
    args = parse_args()
    experiment = yaml.safe_load((ROOT / args.experiment).read_text(encoding="utf-8"))
    config = load_config(ROOT, args.defaults, args.config)
    industry = str(args.industry or experiment.get("industry", ""))
    if industry not in config["selected_industries"]:
        raise ValueError(f"Industry {industry!r} is not selected by {args.config}")
    inputs = load_industry_inputs(config, industry)
    task_boundary = experiment.get("task_boundary", {})
    if task_boundary.get("representative_group_condition") != "known_AI_adopter":
        raise ValueError("Group core must represent a group known to have adopted AI")
    if task_boundary.get("group_service_scale") != "group_activity_share_divided_by_adopter_activity_coverage":
        raise ValueError("Group core must use adopter-conditioned service scaling")
    if task_boundary.get("industry_reconstruction") != "adopter_activity_coverage_divided_by_group_activity_share":
        raise ValueError("Group core must preserve the unconditional industry total")
    if task_boundary.get("task_origin_weighting") != "equal_share_proxy_within_adopted_group":
        raise ValueError("Unsupported within-group task-origin weighting")
    group = read_representative_groups(ROOT / config["paths"]["representative_group_report"])[industry]
    representative_group_count = group.factories(config["industry_parameter_case"])
    legacy_load_site_count = resolve_population_count(
        experiment.get(
            "production_load_site_count",
            experiment.get("factory_count", "registry_or_representative_group_case"),
        ),
        representative_group_count,
        "production_load_site_count",
    )
    share = group.share(config["industry_parameter_case"])
    adopter_conditioning = conditioning_from_config(ROOT, config, industry)
    adopter_activity_share = adopter_conditioning.adopter_activity_share
    conditional_group_ai_scale = adopter_conditioning.group_service_scale(share)
    industry_equivalent_multiplier = (
        adopter_conditioning.industry_equivalent_multiplier(share)
    )
    if not np.isclose(
        conditional_group_ai_scale * industry_equivalent_multiplier, 1.0
    ):
        raise AssertionError("Adopter-conditioned group scaling does not reconstruct industry service")
    mean_per_load_site, load_calibration = resolve_site_mean_load_mw(
        root=ROOT,
        config=config,
        industry=industry,
        industry_mean_load_mw=float(inputs.base_load_mw.mean()),
        ai_service_group_share=share,
        legacy_load_site_count=legacy_load_site_count,
    )
    production_load_site_count = int(load_calibration["load_site_count"])
    node_identity_rule = str(
        experiment.get("ai_deployment_node_rule", "same_as_modeled_routing_nodes")
    )
    if node_identity_rule != "same_as_modeled_routing_nodes":
        raise ValueError(
            "ai_deployment_node_rule must be same_as_modeled_routing_nodes"
        )
    requested_node_count = experiment.get("modeled_routing_node_count")
    if requested_node_count is not None:
        modeled_node_count = int(requested_node_count)
        if modeled_node_count < 1 or modeled_node_count > production_load_site_count:
            raise ValueError(
                "modeled_routing_node_count must be between 1 and production_load_site_count"
            )
        node_selection_mode = "explicit"
    else:
        node_cap = int(experiment.get("max_modeled_routing_nodes", production_load_site_count))
        if node_cap < 1:
            raise ValueError("max_modeled_routing_nodes must be positive")
        modeled_node_count = min(production_load_site_count, node_cap)
        node_selection_mode = "capped"
    production_load_site_weights = balanced_factory_weights(
        production_load_site_count, modeled_node_count
    )
    representative_cluster_power_shares = aggregate_site_power_weights(
        load_calibration["load_site_power_weights"], production_load_site_weights
    )
    target = inputs.base_load_mw.reshape(-1, 24)
    target = np.median(target / target.mean(axis=1, keepdims=True), axis=0)
    source_setting = experiment["load_curve_selection"].get("source_isic", "auto_from_core_lineage")
    if source_setting == "auto_from_core_lineage":
        core_lineage = json.loads((ROOT / config["paths"]["hourly_industry_profiles_lineage"]).read_text(encoding="utf-8"))
        source_by_industry = {
            str(row["industry_code"]): int(row["source_isic_division"])
            for row in core_lineage["records"]
        }
        source_isic = source_by_industry[industry]
    else:
        source_isic = int(source_setting)
    lineage, normalized_curves = select_factory_weeks(
        ROOT / config["paths"]["eweld_archive"],
        target,
        modeled_node_count,
        source_isic,
        experiment["load_curve_selection"].get("week_quality_by_industry", {}).get(
            industry, experiment["load_curve_selection"].get("week_quality")
        ),
    )
    for row, weight, power_share in zip(
        lineage, production_load_site_weights, representative_cluster_power_shares
    ):
        row["modeled_routing_node_id"] = row.pop("factory_id").replace("F", "R", 1)
        row["represented_factory_count"] = int(weight)
        row["represented_production_load_site_count"] = int(weight)
        row["PF_representative_site_weight"] = int(weight)
        row["representative_cluster_power_share"] = float(power_share)
        row["electrical_load_aggregation_at_AI_node"] = False
        row["ai_deployment_node_count"] = 1
    print(f"selected {industry} factory weeks from EWELD ISIC {source_isic}", flush=True)
    group_mean_load_mw = float(load_calibration["representative_group_mean_load_mw"])
    if not np.isclose(
        mean_per_load_site * production_load_site_count, group_mean_load_mw
    ):
        raise AssertionError("Production-load site mean does not reconstruct group mean load")
    representative_site_mean_by_node = (
        group_mean_load_mw * representative_cluster_power_shares / production_load_site_weights
    )
    representative_factory_loads = normalized_curves * representative_site_mean_by_node[:, None]
    host_index = int(np.argsort(representative_factory_loads.max(axis=1))[modeled_node_count // 2])
    servers, cpu_fraction, cpu_multiplier, hardware_meta = hardware_parameters(config)
    # Prefer the merged run/case config so PHY07/PHY08 overrides are not wiped by
    # the core experiment pin. Fill only missing hardware fields.
    default_planning_reserve = float(config["server"]["installed_reserve_fraction"])
    default_n_plus = int(config["server"].get("n_plus_spare_server_groups", 0))
    for server in servers.values():
        server.setdefault("installed_reserve_fraction", default_planning_reserve)
        server.setdefault("n_plus_spare_server_groups", default_n_plus)
    planning_reserve = float(servers["gpu"]["installed_reserve_fraction"])
    n_plus_spare = int(servers["gpu"].get("n_plus_spare_server_groups", default_n_plus))
    for server in servers.values():
        if abs(float(server["installed_reserve_fraction"]) - planning_reserve) > 1e-12:
            raise ValueError("GPU/CPU planning reserves must match")
        if int(server.get("n_plus_spare_server_groups", n_plus_spare)) != n_plus_spare:
            raise ValueError("GPU/CPU N+k spare counts must match")
    rigid_group, jobs_group = scale_task_workload(inputs, conditional_group_ai_scale)
    grid_prices = read_core_grid_energy_prices(config)
    horizon_hours = int(config["model"]["horizon_hours"])
    if horizon_hours == 24:
        normalized_day_curves = normalized_curves.reshape(modeled_node_count, 7, 24).mean(axis=1)
        representative_factory_loads = normalized_day_curves * representative_site_mean_by_node[:, None]
    elif horizon_hours != 168:
        raise ValueError("The group-multisite curve selector currently supports 24 or 168 hours")

    admissible_per_site = sum(
        len({(job.release_hour + offset) % horizon_hours for offset in range(job.deadline_hours + 1)})
        for job in jobs_group
    )
    variable_counts = {
        "production_load_site_count": production_load_site_count,
        "multisite_ai_deployment_node_count": modeled_node_count,
        "multisite_task_routing_node_count": modeled_node_count,
        "physical_factory_count": production_load_site_count,
        "modeled_routing_node_count": modeled_node_count,
        "production_load_site_weights": production_load_site_weights.tolist(),
        "PF_representative_site_counts": production_load_site_weights.tolist(),
        "representative_cluster_power_shares": representative_cluster_power_shares.tolist(),
        "electrical_load_aggregation_at_AI_nodes": False,
        "representative_host_site_mean_loads_mw": representative_site_mean_by_node.tolist(),
        "multisite_total_host_site_mean_load_mw": float(representative_site_mean_by_node.sum()),
        "representative_group_all_site_mean_load_mw": group_mean_load_mw,
        "SHG_candidate_node_id": f"R{host_index + 1}",
        "SHG_mean_base_load_mw": float(representative_site_mean_by_node[host_index]),
        "group_activity_share": share,
        "adopter_activity_share": adopter_activity_share,
        "conditional_group_ai_scale": conditional_group_ai_scale,
        "industry_equivalent_multiplier": industry_equivalent_multiplier,
        "ai_service_routing_scope": "full_group_service_across_all_AI_deployment_routing_nodes",
        "routing_node_selection_mode": node_selection_mode,
        "PF_installed_server_integer_variables_solved": modeled_node_count * 2,
        "PF_installed_server_integer_variables_physical_equivalent": production_load_site_count * 2,
        "SHG_installed_server_integer_variables": 0,
        "MSG_installed_server_integer_variables": 0,
        "load_profile_mode": str(config["model"]["load_profile_mode"]),
        "horizon_hours": horizon_hours,
        "online_server_variables": modeled_node_count * 2 * horizon_hours,
        "rigid_route_variables": modeled_node_count * len(rigid_group) * horizon_hours,
        "flexible_time_site_route_variables": modeled_node_count * admissible_per_site,
        "grid_peak_variables": modeled_node_count,
        "primary_continuous_variables_MSG": modeled_node_count * 2 * horizon_hours + modeled_node_count * len(rigid_group) * horizon_hours + modeled_node_count * admissible_per_site + modeled_node_count,
        "integer_variables_PF_solved": modeled_node_count * 2,
    }
    msg_no_routing_config = experiment.get("mechanism_controls", {}).get("MSG_no_routing", {})
    msg_no_routing_enabled = bool(msg_no_routing_config.get("enabled", False))
    if msg_no_routing_enabled:
        if msg_no_routing_config.get("formal_architecture") is not False:
            raise ValueError("MSG-no-routing must remain an internal mechanism control")
        if msg_no_routing_config.get("paired_treatment") != "MSG":
            raise ValueError("MSG-no-routing must be paired only with MSG")
        if msg_no_routing_config.get("fixed_share_source") != "registered_represented_factory_counts":
            raise ValueError("MSG-no-routing shares must come from registered represented-factory counts")
        if msg_no_routing_config.get("rigid_assignment") != "each_task_hour_fixed_to_ex_ante_node_share":
            raise ValueError("MSG-no-routing must fix every rigid task-hour to the ex-ante node shares")
        if msg_no_routing_config.get("flexible_assignment") != "each_job_total_fixed_to_ex_ante_node_share_within_original_deadline":
            raise ValueError("MSG-no-routing must fix every flexible job total while retaining its deadline")
        variable_counts["MSG_no_routing_additional_solve"] = True
        variable_counts["MSG_no_routing_fixed_site_shares"] = (
            production_load_site_weights / production_load_site_weights.sum()
        ).tolist()
    if args.describe_only:
        print(json.dumps(variable_counts, ensure_ascii=False, indent=2))
        return

    selected_architectures = [
        str(name)
        for name in (args.architectures or config.get("selected_scenarios") or experiment.get("architectures") or [])
    ]
    allowed_architectures = {"PF", "SHG", "MSG"}
    if not selected_architectures or set(selected_architectures) - allowed_architectures:
        raise ValueError(f"Unsupported group architectures: {selected_architectures}")
    msg_no_routing_enabled = msg_no_routing_enabled and "MSG" in selected_architectures
    validate_integer_boundary(experiment)
    cases_by_architecture = experiment["base_load_cases_by_architecture"]
    expected_pairs = {
        (architecture, case)
        for architecture in selected_architectures
        for case in cases_by_architecture[architecture]
    }

    final_summaries = []
    final_hourly = []
    msg_coordinated_summary = None
    msg_no_routing_summary = None
    msg_no_routing_hourly = None
    coordination_effect = None
    additive_fields = [
        "installed_gpu_server_groups", "installed_cpu_server_groups", "annual_server_cost_rmb",
        "average_required_gpu_server_groups", "average_required_cpu_server_groups", "average_required_total_server_groups",
        "annual_ai_energy_cost_rmb", "annual_incremental_maximum_demand_cost_rmb",
        "annual_incremental_total_cost_rmb", "annual_ai_facility_energy_twh",
        "annual_ai_fixed_overhead_energy_twh", "annual_unshiftable_ai_active_energy_twh",
        "annual_shiftable_ai_active_energy_twh",
        "sum_incremental_grid_peak_mw", "weekly_service_units",
    ]
    if_site_summaries = []
    if_site_hourly = []
    if "PF" in selected_architectures:
        for site in range(modeled_node_count):
            rigid_site = {task: values / production_load_site_count for task, values in rigid_group.items()}
            jobs_site = tuple(
                job.__class__(job.release_hour, job.deadline_hours, job.amount_service_units / production_load_site_count, job.task_id, job.flexibility_class)
                for job in jobs_group
            )
            summary, hourly = solve_architecture(
                architecture=f"PF_F{site + 1}", config=config, base_loads=representative_factory_loads[[site]],
                rigid_by_task=rigid_site, jobs=jobs_site, grid_prices=grid_prices,
                servers=servers, cpu_fraction=cpu_fraction, cpu_multiplier=cpu_multiplier,
                solver_name=str(experiment["solver"]),
                installed_integer=INTEGER_INSTALLED_CAPACITY_BY_ARCHITECTURE["PF"],
                base_load_case="actual_load",
            )
            weight = int(production_load_site_weights[site])
            for field in additive_fields:
                summary[field] = float(summary[field]) * weight
            summary["representative_factory_weight"] = weight
            if_site_summaries.append(summary)
            for field in [
                "base_load_mw", "ai_service_units", "unshiftable_ai_service_units",
                "shiftable_ai_service_units", "gpu_compute_h", "cpu_compute_h",
                "unshiftable_gpu_compute_h", "shiftable_gpu_compute_h",
                "unshiftable_cpu_compute_h", "shiftable_cpu_compute_h",
                "ai_fixed_overhead_power_mw", "unshiftable_ai_active_power_mw",
                "shiftable_ai_active_power_mw", "ai_facility_power_mw", "grid_import_mw",
            ]:
                hourly[field] = hourly[field].astype(float) * weight
            hourly["factory_id"] = f"R{site + 1}"
            hourly["represented_factory_count"] = weight
            hourly["represented_production_load_site_count"] = weight
            hourly["ai_deployment_node_count"] = 1
            if_site_hourly.append(hourly)
        if_rows = pd.DataFrame(if_site_summaries)
        if_summary = {key: if_rows[key].sum() for key in additive_fields}
        if_summary.update({
            "architecture": "PF", "base_load_case": "actual_load",
            "solver_status": "ok", "solver_condition": "weighted_representative_independent_factory_models",
            "physical_factory_count": production_load_site_count,
            "production_load_site_count": production_load_site_count,
            "ai_deployment_node_count": production_load_site_count,
            "installed_server_groups_integer": True,
            "modeled_routing_node_count": modeled_node_count,
            "active_compute_node_count": modeled_node_count,
            "online_server_groups_integer": False, "n_plus_spare_server_groups": n_plus_spare,
            "model_state_minimum_groups_enabled": False,
            "planning_reserve_fraction": planning_reserve,
            "maximum_single_site_ai_facility_power_mw": float(max(row["maximum_single_site_ai_facility_power_mw"] for row in if_site_summaries)),
        })
        if_ratio = float(if_summary["installed_gpu_server_groups"] + if_summary["installed_cpu_server_groups"]) / float(if_summary["average_required_total_server_groups"])
        if_summary["installed_total_server_capacity_to_average_demand_ratio"] = if_ratio
        if_summary["realized_total_installed_capacity_utilization_fraction"] = 1.0 / if_ratio
        if_summary["realized_total_capacity_redundancy_fraction_above_average"] = if_ratio - 1.0
        final_summaries.append(if_summary)
        final_hourly.append(pd.concat(if_site_hourly, ignore_index=True).assign(architecture="PF"))

    if "SHG" in selected_architectures:
        for base_load_case in cases_by_architecture["SHG"]:
            host_load = (
                representative_factory_loads[[host_index]]
                if base_load_case == "actual_load"
                else np.zeros_like(representative_factory_loads[[host_index]])
            )
            if base_load_case not in {"actual_load", "zero_load"}:
                raise ValueError(f"Unsupported SHG base-load case: {base_load_case}")
            summary, hourly = solve_architecture(
                architecture="SHG", config=config, base_loads=host_load,
                rigid_by_task=rigid_group, jobs=jobs_group, grid_prices=grid_prices,
                servers=servers, cpu_fraction=cpu_fraction, cpu_multiplier=cpu_multiplier,
                solver_name=str(experiment["solver"]),
                installed_integer=INTEGER_INSTALLED_CAPACITY_BY_ARCHITECTURE["SHG"],
                base_load_case=base_load_case,
            )
            summary["physical_factory_count"] = production_load_site_count
            summary["production_load_site_count"] = production_load_site_count
            summary["ai_deployment_node_count"] = 1
            summary["modeled_routing_node_count"] = 1
            summary["active_compute_node_count"] = 1
            hourly["factory_id"] = f"R{host_index + 1}"
            hourly["represented_factory_count"] = 1
            hourly["represented_production_load_site_count"] = 1
            hourly["ai_deployment_node_count"] = 1
            final_summaries.append(summary)
            final_hourly.append(hourly)

    if "MSG" in selected_architectures:
        summary, hourly = solve_architecture(
            architecture="MSG", config=config, base_loads=representative_factory_loads,
            rigid_by_task=rigid_group, jobs=jobs_group, grid_prices=grid_prices,
            servers=servers, cpu_fraction=cpu_fraction, cpu_multiplier=cpu_multiplier,
            solver_name=str(experiment["solver"]),
            installed_integer=INTEGER_INSTALLED_CAPACITY_BY_ARCHITECTURE["MSG"],
            base_load_case="actual_load",
        )
        summary["physical_factory_count"] = production_load_site_count
        summary["production_load_site_count"] = production_load_site_count
        summary["ai_deployment_node_count"] = modeled_node_count
        summary["modeled_routing_node_count"] = modeled_node_count
        summary["active_compute_node_count"] = modeled_node_count
        hourly["factory_id"] = hourly["factory_id"].str.replace("F", "R", n=1, regex=False)
        hourly["represented_factory_count"] = 1
        hourly["represented_production_load_site_count"] = 1
        hourly["ai_deployment_node_count"] = 1
        final_summaries.append(summary)
        final_hourly.append(hourly)
        msg_coordinated_summary = summary

        if msg_no_routing_enabled:
            fixed_site_shares = production_load_site_weights / production_load_site_weights.sum()
            control_summary, control_hourly = solve_architecture(
                architecture="MSG_NO_ROUTING", config=config,
                base_loads=representative_factory_loads,
                rigid_by_task=rigid_group, jobs=jobs_group, grid_prices=grid_prices,
                servers=servers, cpu_fraction=cpu_fraction, cpu_multiplier=cpu_multiplier,
                solver_name=str(experiment["solver"]), installed_integer=False,
                base_load_case="actual_load",
                fixed_site_service_shares=fixed_site_shares,
            )
            control_summary["physical_factory_count"] = production_load_site_count
            control_summary["industry"] = industry
            control_summary["production_load_site_count"] = production_load_site_count
            control_summary["ai_deployment_node_count"] = modeled_node_count
            control_summary["modeled_routing_node_count"] = modeled_node_count
            control_summary["active_compute_node_count"] = modeled_node_count
            control_summary["formal_architecture"] = False
            control_summary["paired_treatment"] = "MSG"
            control_summary["fixed_site_share_source"] = "registered_represented_factory_counts"
            control_hourly["factory_id"] = control_hourly["factory_id"].str.replace("F", "R", n=1, regex=False)
            control_hourly["represented_factory_count"] = production_load_site_weights[
                control_hourly["factory_id"].str.removeprefix("R").astype(int).to_numpy() - 1
            ]
            control_hourly["represented_production_load_site_count"] = control_hourly["represented_factory_count"]
            control_hourly["ai_deployment_node_count"] = 1
            control_hourly["fixed_site_service_share"] = fixed_site_shares[
                control_hourly["factory_id"].str.removeprefix("R").astype(int).to_numpy() - 1
            ]
            if not np.allclose(
                hourly["base_load_mw"].to_numpy(dtype=float),
                control_hourly["base_load_mw"].to_numpy(dtype=float),
                rtol=0,
                atol=1e-12,
            ):
                raise AssertionError("MSG-no-routing and MSG must use identical node-level production loads")
            for paired_field in (
                "model_version",
                "common_it_effective_efficiency_case",
                "common_it_effective_efficiency_multiplier",
                "baseline_reference_workload_per_service_unit",
                "reference_compute_h_per_service_unit",
                "reference_server_group",
                "planning_reserve_fraction",
                "n_plus_spare_server_groups",
                "installed_server_groups_integer",
                "online_server_groups_integer",
            ):
                if control_summary[paired_field] != summary[paired_field]:
                    raise AssertionError(f"MSG-no-routing differs from MSG on {paired_field}")
            service_tolerance = max(float(summary["weekly_service_units"]), 1.0) * 1e-8
            if abs(float(control_summary["weekly_service_units"]) - float(summary["weekly_service_units"])) > service_tolerance:
                raise AssertionError("MSG-no-routing and MSG must conserve the same service")
            if float(control_summary["maximum_rigid_origin_share_absolute_error"]) > service_tolerance:
                raise AssertionError("MSG-no-routing rigid task-hour shares are not fixed as specified")
            if float(control_summary["maximum_flexible_origin_share_absolute_error"]) > service_tolerance:
                raise AssertionError("MSG-no-routing flexible job shares are not fixed as specified")
            objective_tolerance = max(abs(float(summary["annual_incremental_total_cost_rmb"])), 1.0) * 1e-6
            if float(control_summary["annual_incremental_total_cost_rmb"]) + objective_tolerance < float(summary["annual_incremental_total_cost_rmb"]):
                raise AssertionError("The restricted MSG-no-routing feasible set cannot improve the MSG objective")
            msg_no_routing_summary = control_summary
            msg_no_routing_hourly = control_hourly
            coordination_effect = build_coordination_effect_row(
                industry, control_summary, summary
            )

    output = ROOT / args.output_dir
    output.mkdir(parents=True, exist_ok=True)
    summary_frame = pd.DataFrame(final_summaries)
    summary_frame.insert(0, "industry", industry)
    # PF is aggregated from weighted site solves, so stamp release metadata
    # after aggregation just as for the directly solved SHG and MSG rows.
    summary_frame["model_version"] = config["model_version"]
    summary_frame["production_load_mode"] = str(load_calibration["mode"])
    summary_frame["production_load_boundary_id"] = str(load_calibration["boundary_id"])
    summary_frame["production_activity_share"] = float(load_calibration["production_activity_share"])
    summary_frame["load_site_count"] = int(load_calibration["load_site_count"])
    summary_frame["group_activity_share"] = share
    summary_frame["adopter_activity_share"] = adopter_activity_share
    summary_frame["ai_service_group_share"] = conditional_group_ai_scale
    summary_frame["industry_equivalent_multiplier"] = industry_equivalent_multiplier
    summary_frame["representative_group_adoption_status"] = "adopted"
    summary_frame["production_load_site_count"] = production_load_site_count
    summary_frame["common_it_effective_efficiency_case"] = config["demand"]["effective_service"]["common_it_effective_efficiency_case"]
    summary_frame["common_it_effective_efficiency_multiplier"] = config["demand"]["effective_service"]["common_it_effective_efficiency_multiplier"]
    summary_frame["baseline_reference_workload_per_service_unit"] = config["demand"]["effective_service"]["baseline_reference_workload_per_service_unit"]
    summary_frame["reference_compute_h_per_service_unit"] = config["demand"]["effective_service"]["reference_compute_h_per_service_unit"]
    summary_frame["reference_server_group"] = config["server"]["configuration"]
    observed_pairs = set(zip(summary_frame["architecture"], summary_frame["base_load_case"]))
    if observed_pairs != expected_pairs or len(summary_frame) != len(expected_pairs):
        raise ValueError(f"Unexpected architecture/base-load cases: {observed_pairs}")
    reference_architecture = "PF" if "PF" in selected_architectures else selected_architectures[0]
    reference_cost = float(summary_frame.loc[
        summary_frame.architecture.eq(reference_architecture) & summary_frame.base_load_case.eq("actual_load"),
        "annual_incremental_total_cost_rmb",
    ].iloc[0])
    summary_frame["cost_relative_to_PF_actual_load"] = (
        summary_frame["annual_incremental_total_cost_rmb"] / reference_cost
        if reference_architecture == "PF"
        else float("nan")
    )
    summary_frame["cost_relative_to_reference_actual_load"] = summary_frame["annual_incremental_total_cost_rmb"] / reference_cost
    summary_frame.to_csv(output / "summary.csv", index=False, encoding="utf-8-sig")
    pd.concat(final_hourly, ignore_index=True).to_csv(output / "hourly.csv", index=False, encoding="utf-8-sig")
    if msg_no_routing_enabled:
        if msg_no_routing_summary is None or msg_no_routing_hourly is None or coordination_effect is None:
            raise AssertionError("Enabled MSG-no-routing control was not solved")
        pd.DataFrame([msg_no_routing_summary]).to_csv(
            output / "msg_no_routing_summary.csv", index=False, encoding="utf-8-sig"
        )
        msg_no_routing_hourly.to_csv(
            output / "msg_no_routing_hourly.csv", index=False, encoding="utf-8-sig"
        )
        pd.DataFrame([coordination_effect]).to_csv(
            output / "coordination_value.csv", index=False, encoding="utf-8-sig"
        )
    pd.DataFrame(lineage).to_csv(output / "curve_lineage.csv", index=False, encoding="utf-8-sig")
    if "SHG" in selected_architectures:
        paired = summary_frame.set_index(["architecture", "base_load_case"])
        actual = paired.loc[("SHG", "actual_load")]
        zero = paired.loc[("SHG", "zero_load")]
        paired_frame = pd.DataFrame([{
            "industry": industry,
            "architecture": "SHG",
            "load_alignment_value_total_cost_rmb": float(zero.annual_incremental_total_cost_rmb - actual.annual_incremental_total_cost_rmb),
            "load_alignment_value_server_cost_rmb": float(zero.annual_server_cost_rmb - actual.annual_server_cost_rmb),
            "load_alignment_value_energy_cost_rmb": float(zero.annual_ai_energy_cost_rmb - actual.annual_ai_energy_cost_rmb),
            "load_alignment_value_maximum_demand_cost_rmb": float(zero.annual_incremental_maximum_demand_cost_rmb - actual.annual_incremental_maximum_demand_cost_rmb),
            "avoided_incremental_grid_peak_mw": float(zero.sum_incremental_grid_peak_mw - actual.sum_incremental_grid_peak_mw),
            "definition": "SHG_zero_load_reoptimized_minus_actual_load_reoptimized",
        }])
        paired_frame.to_csv(output / "load_alignment_value.csv", index=False, encoding="utf-8-sig")
    else:
        pd.DataFrame(columns=["industry", "architecture"]).to_csv(output / "load_alignment_value.csv", index=False, encoding="utf-8-sig")
    metadata = {
        "model_version": config["model_version"],
        "status": "completed_PF_integer_SHG_MSG_continuous_capacity_mechanism_test",
        "experiment": experiment,
        "industry": industry,
        "source_isic": source_isic,
        "group_share": share,
        "group_activity_share": share,
        "adopter_activity_share": adopter_activity_share,
        "adopter_activity_share_year": adopter_conditioning.year,
        "adopter_activity_share_status": adopter_conditioning.evidence_status,
        "adopter_activity_share_source_measure": adopter_conditioning.source_measure,
        "conditional_group_ai_scale": conditional_group_ai_scale,
        "industry_equivalent_multiplier": industry_equivalent_multiplier,
        "representative_group_adoption_status": "adopted",
        "synthetic_factory_count": production_load_site_count,
        "physical_factory_count": production_load_site_count,
        "production_load_site_count": production_load_site_count,
        "modeled_routing_node_count": modeled_node_count,
        "ai_task_origin_production_site_count": production_load_site_count,
        "within_group_task_origin_rule": "all_registered_production_sites_equal_share_proxy",
        "ai_service_routing_scope": "full_group_service_across_all_AI_deployment_routing_nodes",
        "ai_deployment_node_count_by_architecture": {
            "PF": production_load_site_count,
            "SHG": 1,
            "MSG": modeled_node_count,
        },
        "multisite_AI_deployment_points_equal_routing_nodes": True,
        "electrical_load_aggregation_at_AI_nodes": False,
        "routing_node_selection_mode": node_selection_mode,
        "representative_factory_weights": production_load_site_weights.tolist(),
        "production_load_site_weights": production_load_site_weights.tolist(),
        "PF_representative_site_counts": production_load_site_weights.tolist(),
        "representative_cluster_power_shares": representative_cluster_power_shares.tolist(),
        "load_calibration": load_calibration,
        "SHG_factory_id": f"R{host_index + 1}",
        "hardware": hardware_meta,
        "common_it_effective_efficiency_case": config["demand"]["effective_service"]["common_it_effective_efficiency_case"],
        "common_it_effective_efficiency_multiplier": config["demand"]["effective_service"]["common_it_effective_efficiency_multiplier"],
        "baseline_reference_workload_per_service_unit": config["demand"]["effective_service"]["baseline_reference_workload_per_service_unit"],
        "reference_compute_h_per_service_unit": config["demand"]["effective_service"]["reference_compute_h_per_service_unit"],
        "reference_server_group": config["server"]["configuration"],
        "variable_counts": variable_counts,
        "selected_architectures": selected_architectures,
        "architectures": selected_architectures,
        "mechanism_controls": {
            "MSG_no_routing": {
                "enabled": msg_no_routing_enabled,
                "formal_architecture": False,
                "paired_treatment": "MSG",
                "fixed_share_source": "registered_represented_factory_counts",
                "fixed_site_service_shares": (
                    production_load_site_weights / production_load_site_weights.sum()
                ).tolist() if msg_no_routing_enabled else None,
                "effect_definition": "MSG_no_routing_minus_MSG_coordinated",
                "positive_effect_interpretation": "burden_avoided_by_cross_site_coordination",
                "maximum_rigid_origin_share_absolute_error": (
                    float(msg_no_routing_summary["maximum_rigid_origin_share_absolute_error"])
                    if msg_no_routing_summary is not None else None
                ),
                "maximum_flexible_origin_share_absolute_error": (
                    float(msg_no_routing_summary["maximum_flexible_origin_share_absolute_error"])
                    if msg_no_routing_summary is not None else None
                ),
            }
        },
        "planning_reserve_fraction": planning_reserve,
        "n_plus_spare_server_groups": n_plus_spare,
        "base_load_cases_by_architecture": {
            architecture: cases_by_architecture[architecture]
            for architecture in selected_architectures
        },
        "load_profile_mode": str(config["model"]["load_profile_mode"]),
        "solver": {
            "name": str(experiment["solver"]),
            "options": build_solver_options(config, str(experiment["solver"])),
        },
        "validated_architecture_base_load_pairs": sorted(f"{architecture}__{case}" for architecture, case in observed_pairs),
        "service_conservation_relative_error": {
            f"{row['architecture']}__{row['base_load_case']}": abs(float(row["weekly_service_units"]) - float(summary_frame.iloc[0]["weekly_service_units"])) / max(float(summary_frame.iloc[0]["weekly_service_units"]), 1e-12)
            for row in final_summaries
        },
        "limitations": [
            "EWELD users are anonymous same-industry facilities, not observed members of one corporate group",
            "weeks are aligned by weekday and hour, not observed in the same calendar week",
            "all six modeled central AI task classes are allowed to route within the synthetic group",
            "flexible tasks retain their registered intraday and batch deadlines",
            "cross-site network cost, latency, data-residency restrictions, PV and batteries are excluded",
            "only PF installed GPU/CPU server groups are integer; SHG and MSG installed capacity is continuous equivalent",
            "hourly online server groups remain continuous in all three architectures",
            "same-user distinct weeks are factory-shape proxies when an industry has too few distinct EWELD users",
            f"multisite host nodes are selected by {node_selection_mode} mode; each modeled routing node is one AI deployment point on an independent host-factory electrical boundary",
            "PF solves one integer-capacity factory per representative curve and weights its cost and capacity to reconstruct physical-factory fragmentation",
            "PF representative weights are not applied to SHG or MSG production loads",
            "SHG and MSG use the same unaggregated per-host production-load curves for common candidate nodes",
            "production sites without an AI host contribute to group AI-service demand but their electrical loads are not transferred to host nodes",
            "the 2030 firm-count AI-adoption scenario is used as a proxy for adopter activity coverage because activity-weighted adoption is unavailable",
            "the representative group is conditioned on known AI adoption; its service scale is group activity share divided by the adopter activity-coverage proxy",
            "within the adopted group, every registered production site is assigned an equal share of task origins; task-specific site coverage remains a sensitivity",
            "zero_load is a reoptimized AI-only counterfactual, not a factory operating condition",
            "only SHG receives the zero_load paired counterfactual",
            "SHG load-alignment value includes endogenous changes in AI timing and installed capacity permitted by that architecture",
            "MSG-no-routing is an internal paired mechanism control, not a formal deployment architecture",
            "MSG-no-routing fixes every rigid task-hour and each flexible job total to ex-ante represented-factory shares while retaining each job deadline",
            "only MSG-no-routing minus MSG-coordinated may be interpreted as the modeled cross-site coordination effect",
            "model-state minimum server floors remain disabled in this group-architecture formulation",
            "the dual-L20-calibrated reference server group is a common capacity, power and 2U space proxy rather than a 2030 procurement or rack-density forecast",
        ],
    }
    (output / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
