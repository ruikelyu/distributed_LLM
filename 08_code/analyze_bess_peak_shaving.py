#!/usr/bin/env python3
"""Size behind-the-meter batteries that keep each AI host site at its pre-AI peak.

Purpose: Estimate the battery power, energy, and investment that would let every
factory-site AI deployment node avoid additional grid-interconnection capacity.
Workflow status: Active post-processor of the validated 31-industry core results.
Scientific boundary: Batteries are sized on the optimized core schedules, which
were solved without storage. Tasks are not re-optimized with the battery, so the
sizes are an upper bound for the same service.
Inputs: Group-architecture hourly results, weighted node table, and CNESA
2-h/4-h winning-bid battery prices.
Outputs: Site-level battery sizes and costs, national totals by architecture,
the fitted power and energy cost components, and a validation marker.
Key assumptions: One battery per AI host site (each factory under PF, the host
under SHG, each node under MSG) that only shaves that site's peak. For site n
with hourly excess e_{n,t} = max(0, L_{n,t} + p_{n,t} - K_n), K_n = max_t L_{n,t},
power P_n = max_t e_{n,t} and energy E_n = max_d sum_{t in day d} e_{n,t} / eta_dis,
i.e., the battery covers the largest daily excess and recharges once per day.
Cost per site is c_P P_n + c_E E_n, with c_P and c_E fitted to the 2-h and 4-h
CNESA prices through price(h) = c_E + c_P / h.
Explicit exclusions: No storage co-optimization, sub-hourly peaks, depth-of-
discharge limits, degradation, replacement, or arbitrage revenue.
Validation/tests: Battery power reconciles with the national additional
capacity of every architecture; an hourly simulation checks whether each site
can recharge its daily energy within its existing connection capacity.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT = PROJECT_ROOT / "05_results/v1.0.0/result"
ARCHITECTURES = ("PF", "SHG", "MSG")
HOURS_PER_DAY = 24


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--group-core-root", type=Path, default=RESULT / "group_architecture_core")
    parser.add_argument("--nodes", type=Path, default=RESULT / "node_interconnection_distribution/node_interconnection_distribution.csv")
    parser.add_argument("--prices", type=Path, default=PROJECT_ROOT / "02_data/raw/curated/cnesa_bess_bid_prices_2026_09.csv")
    parser.add_argument("--output-root", type=Path, default=RESULT / "bess_peak_shaving")
    parser.add_argument("--roundtrip-efficiency", type=float, default=0.90)
    return parser.parse_args()


def fit_cost_components(prices: pd.DataFrame) -> pd.DataFrame:
    """Solve price(h) = c_E + c_P / h from the 2-h and 4-h prices of each scope."""
    rows = []
    for scope, group in prices.groupby("scope"):
        by_h = group.set_index("duration_h")["price_cny_per_kwh"]
        if set(by_h.index) != {2, 4}:
            raise ValueError(f"Expected 2-h and 4-h prices for scope {scope}")
        c_p = (by_h[2] - by_h[4]) / (1 / 2 - 1 / 4)
        c_e = by_h[2] - c_p / 2
        rows.append({"scope": scope, "power_cost_cny_per_kw": c_p, "energy_cost_cny_per_kwh": c_e})
    return pd.DataFrame(rows)


def daily_recharge_shortfall_mwh(excess: np.ndarray, headroom: np.ndarray, power: float, energy: float, eta: float) -> float:
    """Simulate the sized battery over three repeated weeks and return unmet excess in the last week."""
    soc = energy
    unmet = 0.0
    weeks = 3
    for week in range(weeks):
        for e_t, h_t in zip(excess, headroom):
            if e_t > 0:
                discharge = min(e_t, power, soc * eta)
                soc -= discharge / eta
                if week == weeks - 1:
                    unmet += e_t - discharge
            else:
                soc += min(h_t, power, (energy - soc) / eta) * eta
    return unmet


def size_sites(group_core_root: Path, eta: float) -> pd.DataFrame:
    rows = []
    for path in sorted(group_core_root.glob("C*/hourly.csv")):
        industry = path.parent.name
        hourly = pd.read_csv(path, encoding="utf-8-sig")
        hourly = hourly[(hourly["base_load_case"] == "actual_load") & hourly["architecture"].isin(ARCHITECTURES)]
        for (architecture, factory), site in hourly.groupby(["architecture", "factory_id"]):
            site = site.sort_values("hour")
            # PF rows aggregate identical factories; convert to one physical site.
            count = site["represented_factory_count"].to_numpy(dtype=float)
            load = site["base_load_mw"].to_numpy(dtype=float) / count
            ai = site["ai_facility_power_mw"].to_numpy(dtype=float) / count
            if len(load) % HOURS_PER_DAY:
                raise ValueError(f"{industry}/{factory}: horizon is not whole days")
            existing = load.max()
            net = load + ai - existing
            excess = np.maximum(net, 0.0)
            headroom = np.maximum(-net, 0.0)
            power = excess.max()
            daily = excess.reshape(-1, HOURS_PER_DAY).sum(axis=1) / eta
            energy = daily.max()
            shortfall = daily_recharge_shortfall_mwh(excess, headroom, power, energy, eta) if power > 0 else 0.0
            rows.append({
                "architecture": architecture,
                "industry": industry,
                "node_id": f"{industry}/{factory}",
                "existing_capacity_mw": existing,
                "battery_power_mw": power,
                "battery_energy_mwh": energy,
                "battery_duration_h": energy / power if power > 0 else 0.0,
                "hours_above_existing_capacity": int((excess > 0).sum()),
                # Rounding makes the tie-break independent of floating-point noise.
                "largest_excess_day": int(np.round(daily, 9).argmax()) if power > 0 else -1,
                "daily_recharge_shortfall_mwh_per_week": shortfall,
                "daily_recharge_feasible": shortfall <= 1e-6,
            })
    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()
    eta = float(np.sqrt(args.roundtrip_efficiency))
    components = fit_cost_components(pd.read_csv(args.prices))
    sites = size_sites(args.group_core_root, eta)

    nodes = pd.read_csv(args.nodes, encoding="utf-8-sig")
    nodes = nodes[nodes["population_kind"] == "weighted_modeled_deployment_nodes"]
    weights = nodes[["architecture", "node_id", "observation_weight", "incremental_interconnection_capacity_mw"]]
    sites = sites.merge(weights, on=["architecture", "node_id"], how="left", validate="one_to_one")
    if sites["observation_weight"].isna().any():
        raise ValueError("Every site must have a national weight")
    if not np.allclose(sites["battery_power_mw"], sites["incremental_interconnection_capacity_mw"], atol=1e-6):
        raise ValueError("Battery power must equal each site's additional interconnection capacity")

    for _, c in components.iterrows():
        sites[f"battery_cost_{c.scope}_cny"] = (
            c.power_cost_cny_per_kw * sites["battery_power_mw"] * 1e3
            + c.energy_cost_cny_per_kwh * sites["battery_energy_mwh"] * 1e3
        )

    w = sites["observation_weight"]
    national = (
        sites.assign(
            sites_weighted=w,
            sites_with_battery=w * (sites["battery_power_mw"] > 0),
            sites_daily_recharge_infeasible=w * ~sites["daily_recharge_feasible"],
            power_mw=w * sites["battery_power_mw"],
            energy_mwh=w * sites["battery_energy_mwh"],
            cost_system_bn_cny=w * sites["battery_cost_system_cny"] / 1e9,
            cost_epc_bn_cny=w * sites["battery_cost_epc_cny"] / 1e9,
        )
        .groupby("architecture")[[
            "sites_weighted", "sites_with_battery", "sites_daily_recharge_infeasible",
            "power_mw", "energy_mwh", "cost_system_bn_cny", "cost_epc_bn_cny",
        ]]
        .sum()
        .reindex(ARCHITECTURES)
        .reset_index()
    )
    national["average_duration_h"] = national["energy_mwh"] / national["power_mw"]

    args.output_root.mkdir(parents=True, exist_ok=True)
    sites.to_csv(args.output_root / "bess_peak_shaving_sites.csv", index=False, encoding="utf-8-sig")
    national.to_csv(args.output_root / "bess_peak_shaving_national.csv", index=False, encoding="utf-8-sig")
    components.to_csv(args.output_root / "bess_cost_components.csv", index=False, encoding="utf-8-sig")
    (args.output_root / "bess_peak_shaving.validated.done.json").write_text(json.dumps({
        "status": "validated",
        "roundtrip_efficiency": args.roundtrip_efficiency,
        "sizing_rule": "P_n = max_t e_nt; E_n = max_d sum_{t in d} e_nt / eta_dis",
        "power_reconciles_with_additional_capacity": True,
        "national_power_mw": national.set_index("architecture")["power_mw"].round(3).to_dict(),
        "national_energy_mwh": national.set_index("architecture")["energy_mwh"].round(3).to_dict(),
    }, indent=2) + "\n", encoding="utf-8")
    print(national.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
