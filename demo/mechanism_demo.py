"""Toy version of the paper's sizing and scheduling model, eq. (1a)-(1i).

Stylized numbers only: one corporate group with three factories over 24 cyclic hours.
AI demand is given directly in MW of server power at full load, so there is one
hardware type with capacity G = 1 MW and no service-unit conversion. Everything else
follows the paper:

    (1a) min  C z + C_d sum_n delta_n + Y sum_{n,t} Pi_t p_{n,t}
    (1b) sum_n y_{n,t} = R_t                         firm demand served on arrival
    (1c) sum_n sum_{t in T_j} x_{j,n,t} = D_j       flexible job j served before its deadline
    (1d) y_{n,t} = Omega_n R_t, sum_t x_{j,n,t} = Omega_n D_j   fixed shares (no routing)
    (1e) u_{n,t} = y_{n,t} + sum_j x_{j,n,t}        compute demand
    (1f) u_{n,t} <= v_{n,t} <= z_n                  online and installed servers
    (1g) p_{n,t} = M [B z_n + (I - B) v_{n,t} + (1 - I) u_{n,t}]   AI load (facility power)
    (1h) L_{n,t} + p_{n,t} <= K_n + delta_n, K_n = max_t L_{n,t}
    (1i) z_n >= (1 + r) sum_t u_{n,t} / |T|         planning margin

Solved with Linopy and the open-source HiGHS solver in about a second.
Run `python demo/mechanism_demo.py` for the results table.
"""

from __future__ import annotations

from dataclasses import dataclass

import linopy
import numpy as np
import pandas as pd
import xarray as xr

HOURS = np.arange(24)
FACTORIES = ["A", "B", "C"]


def _daily_wave(peak_hour: float, mean: float, amplitude: float) -> np.ndarray:
    """A smooth daily profile with its maximum at peak_hour."""
    return mean + amplitude * np.cos(2 * np.pi * (HOURS - peak_hour) / 24)


def _production_peak(peak_hour: float, base: float, height: float, width_h: float = 2.5) -> np.ndarray:
    """Production load with a few-hour peak on top of a base level (cyclic over the day)."""
    distance = np.minimum(abs(HOURS - peak_hour), 24 - abs(HOURS - peak_hour))
    return base + height * np.exp(-(distance / width_h) ** 2)


# Production load L (MW) of the three factories: same size, peaks eight hours apart.
PRODUCTION_LOAD = pd.DataFrame({
    "A": _production_peak(10, 6.0, 5.0),   # day shift, peak at 10:00
    "B": _production_peak(18, 6.0, 5.0),   # evening shift, peak at 18:00
    "C": _production_peak(2, 6.0, 5.0),    # night process, peak at 02:00
}, index=HOURS)

# AI demand of the whole group, in MW of server power at full load, peaking at 14:00.
# One third is firm (served in its arrival hour); two thirds are flexible (may be delayed up to 12 h).
FIRM_DEMAND = pd.Series(_daily_wave(14, 2 / 3, 0.6), index=HOURS)
FLEX_ARRIVALS = pd.Series(_daily_wave(14, 4 / 3, 1.2), index=HOURS)
MAX_DELAY_H = 12
# Flexible demand arriving in the same hour forms one job j (release hour A_j, volume D_j).
FLEX_JOBS = pd.DataFrame({
    "release_hour": HOURS,
    "max_delay_h": MAX_DELAY_H,
    "energy_mwh": FLEX_ARRIVALS.values,
})


@dataclass(frozen=True)
class Parameters:
    server_cost: float = 35_000_000.0  # C, CNY per MW of installed server power per year (about 2 L20 servers per 3 kW)
    demand_charge: float = 433_200.0   # C_d, CNY per MW of additional capacity per year
    mean_price: float = 550.0          # Pi_t, CNY per MWh, daily mean
    price_swing: float = 150.0         # Pi_t, highest at 14:00 and lowest at 02:00
    days_per_year: float = 365.0       # Y, the 24-h day repeated over the year
    facility_multiplier: float = 1.3   # M
    standby_share: float = 0.02        # B, standby power as a share of full-load power
    idle_share: float = 0.25           # I, online idle power as a share of full-load power
    planning_margin: float = 0.15      # r


@dataclass(frozen=True)
class Case:
    name: str
    nodes: tuple[str, ...]            # factories that host servers
    shifting: bool = True             # False: all demand is firm (F_j = 0)
    routing: bool = True              # False: fixed equal shares Omega_n (1d)
    production_load: bool = True      # False: new data center, L = 0 and K = 0


CASES = [
    # Mechanism 1: siting (new data center vs host factory) x task shifting (no vs yes), as in Section IV-B of the paper.
    Case("1  New data center, no shifting", ("A",), shifting=False, production_load=False),
    Case("2  New data center, with shifting", ("A",), production_load=False),
    Case("3  Host factory, no shifting", ("A",), shifting=False),
    Case("4  Host factory, with shifting", ("A",)),
    # Mechanism 2: several host factories with and without routing.
    Case("5  Three sites, fixed shares", tuple(FACTORIES), routing=False),
    Case("6  Three sites, with routing", tuple(FACTORIES)),
]


def energy_price(par: Parameters) -> xr.DataArray:
    """Hourly energy price Pi_t, highest in the afternoon and lowest at night."""
    price = _daily_wave(14, par.mean_price, par.price_swing)
    return xr.DataArray(price, coords=[pd.Index(HOURS, name="hour")])


def solve(case: Case, par: Parameters = Parameters()) -> dict:
    """Build and solve eq. (1a)-(1i) for one case; return capacities and hourly results."""
    nodes = pd.Index(list(case.nodes), name="node")
    hours = pd.Index(HOURS, name="hour")
    jobs = pd.Index(FLEX_JOBS.index, name="job")
    load = PRODUCTION_LOAD[list(case.nodes)] if case.production_load else PRODUCTION_LOAD[list(case.nodes)] * 0.0
    load = load.rename_axis(index="hour", columns="node")
    capacity = load.max()                                            # K_n

    # Without shifting, flexible energy is served at its release hour like firm demand.
    firm = FIRM_DEMAND.copy()
    if not case.shifting:
        for job in FLEX_JOBS.itertuples():
            firm.iloc[job.release_hour] += job.energy_mwh
    window = np.zeros((len(jobs), 24))                               # 1 for t in T_j
    for j, job in enumerate(FLEX_JOBS.itertuples()):
        window[j, [(job.release_hour + k) % 24 for k in range(job.max_delay_h + 1)]] = 1.0

    m = linopy.Model()
    z = m.add_variables(lower=0, coords=[nodes], name="z")
    v = m.add_variables(lower=0, coords=[nodes, hours], name="v")
    u = m.add_variables(lower=0, coords=[nodes, hours], name="u")
    y = m.add_variables(lower=0, coords=[nodes, hours], name="y")
    x = m.add_variables(lower=0, coords=[jobs, nodes, hours], name="x")
    p = m.add_variables(lower=0, coords=[nodes, hours], name="p")
    delta = m.add_variables(lower=0, coords=[nodes], name="delta")

    T = xr.DataArray(window, coords=[jobs, hours])
    R = xr.DataArray(firm.values, coords=[hours])
    D = xr.DataArray(FLEX_JOBS["energy_mwh"].values if case.shifting else np.zeros(len(jobs)), coords=[jobs])

    m.add_constraints(y.sum("node") == R, name="firm_1b")
    m.add_constraints((x * T).sum(["node", "hour"]) == D, name="flex_1c")
    m.add_constraints(x * (1 - T) == 0, name="window")
    if not case.routing and len(nodes) > 1:
        share = 1.0 / len(nodes)                                     # Omega_n
        m.add_constraints(y == share * R, name="fixed_firm_1d")
        m.add_constraints((x * T).sum("hour") == share * D, name="fixed_flex_1d")
    m.add_constraints(u == y + x.sum("job"), name="compute_1e")
    m.add_constraints(u <= v, name="online_1f")
    m.add_constraints(v <= z, name="installed_1f")
    M, B, I = par.facility_multiplier, par.standby_share, par.idle_share
    m.add_constraints(p == M * (B * z + (I - B) * v + (1 - I) * u), name="power_1g")
    L = xr.DataArray(load.values, coords=[hours, nodes])
    K = xr.DataArray(capacity.values, coords=[nodes])
    m.add_constraints(L + p <= K + delta, name="connection_1h")
    m.add_constraints(z >= (1 + par.planning_margin) * u.sum("hour") / 24, name="margin_1i")

    m.add_objective(par.server_cost * z.sum() + par.demand_charge * delta.sum()
                    + par.days_per_year * (energy_price(par) * p).sum())
    status, _ = m.solve(solver_name="highs", output_flag=False)
    if status != "ok":
        raise RuntimeError(f"{case.name}: solver status {status}")

    ai_load = p.solution.to_pandas().T                               # hour x node
    return {
        "case": case.name,
        "additional_capacity_mw": float(delta.solution.sum()),
        "installed_servers_mw": float(z.solution.sum()),
        "served_mwh": float(u.solution.sum()),
        "annual_cost_million_cny": float(m.objective.value) / 1e6,
        "production_load": load,
        "ai_load": ai_load,
        "capacity": capacity,
    }


def battery(result: dict, roundtrip_efficiency: float = 0.90) -> dict:
    """Size a battery that keeps every host at its pre-AI peak (Supplementary Methods 5)."""
    eta = np.sqrt(roundtrip_efficiency)
    excess = (result["production_load"] + result["ai_load"] - result["capacity"]).clip(lower=0)
    return {
        "power_mw": float(excess.max().sum()),
        "energy_mwh": float((excess.sum() / eta).sum()),
        "excess": excess,
    }


def run_all() -> tuple[pd.DataFrame, list[dict]]:
    results = [solve(case) for case in CASES]
    table = pd.DataFrame([{k: r[k] for k in ("case", "additional_capacity_mw", "installed_servers_mw",
                                             "annual_cost_million_cny")} for r in results])
    return table, results


if __name__ == "__main__":
    table, results = run_all()
    print(table.round(2).to_string(index=False))
    b = battery(results[3])
    print(f"7  Battery at the host of case 4: {b['power_mw']:.2f} MW, {b['energy_mwh']:.2f} MWh")
