#!/usr/bin/env python3
"""Rebuild every figure, table input, and headline number from saved model results.

The repository ships the outputs of the optimization runs (which need Gurobi and
a non-redistributable hourly price series). This script reruns every
downstream step without a solver, in the same order and with the same
arguments as the Snakemake workflow (`snakemake paper`), and then checks
that each regenerated CSV matches the shipped version.

Usage::

    python 08_code/reproduce_paper_results.py            # rebuild and compare
    python 08_code/reproduce_paper_results.py --list     # show the steps only
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v1.0.0"
RESULT = f"05_results/{VERSION}/result"
SENSITIVITY = f"05_results/sensitivity/{VERSION}"
NO_SHIFT = f"{SENSITIVITY}/national_oat_group_architecture"
INDUSTRIES = [f"C{code}" for code in range(13, 44)]
MAP_FILE = ROOT / "02_data/raw/province_shapes/CHN_full_adm/CHN_full_adm.shp"
COMPARED_ROOTS = ["05_results", "02_data/processed/us_demand"]
EPOCH_DIR = "02_data/raw/epoch_ai/ai_data_centers/2026-09-10"
# Third-party originals that are not redistributed. A step that reads one of them is skipped
# when the file is absent; its outputs stay as shipped. See DATA_SOURCES.md for where to get them.
REQUIRED_RAW_INPUTS = {
    "U.S. manufacturing AI demand": [
        "02_data/raw/curated/us_manufacturing_activity_naics3_2022.csv",
        "02_data/raw/curated/us_manufacturing_mecs_2022.csv",
        "02_data/raw/curated/us_manufacturing_berd_2023.csv"],
    "Interconnection node distribution": [
        f"{EPOCH_DIR}/data_centers.csv", f"{EPOCH_DIR}/data_center_timelines.csv"],
    "Spatial water audit": [
        "02_data/raw/resource_footprint/water_stress_sources/aqueduct40/aqueduct-4-0-country-rankings.zip"],
}


def steps() -> list[tuple[str, list[str], str | None]]:
    """(name, arguments after `python`, optional stdout log path) in execution order."""
    us_demand = f"{RESULT}/us_demand"
    ledger = f"{RESULT}/national_local_cloud_cost_v1/ledger"
    core = f"{RESULT}/group_architecture_core"
    us_cost = f"{RESULT}/cost_benchmark/heterogeneous_hardware_v1/us_naics3"
    no_shift_result = f"{NO_SHIFT}/result/PHY03__no_shift"
    figure5 = ["--data-only"] if not MAP_FILE.exists() else []
    return [
        ("U.S. manufacturing AI demand", [
            "08_code/build_us_manufacturing_ai_demand.py",
            "--config", "config/demand_cases/us_manufacturing_ai_demand_v0.1.yaml",
            "--output-dir", us_demand], None),
        ("China national task ledger", [
            "08_code/build_national_unified_ai_task_ledger.py",
            "--config", "config/demand_cases/national_local_cloud_core_v1.yaml",
            "--output-dir", ledger], None),
        ("Validate U.S. demand", [
            "08_code/validate_us_manufacturing_ai_demand.py",
            "--config", "config/demand_cases/us_manufacturing_ai_demand_v0.1.yaml",
            "--service", "02_data/processed/us_demand/us_manufacturing_ai_effective_service_2030.csv",
            "--task-summary", f"{us_demand}/us_national_task_summary.csv",
            "--validation", f"{us_demand}/us_demand_validation.csv",
            "--done-output", f"{us_demand}/validated.done.json"], None),
        ("Combine no-shift sensitivity industries", [
            "08_code/summarize_group_multisite_core.py",
            "--root", f"{NO_SHIFT}/model/PHY03__no_shift",
            "--industries", *INDUSTRIES,
            "--architectures", "SHG", "--no-enforce-core-capacity-boundary",
            "--summary-output", f"{no_shift_result}/core_scenarios.csv",
            "--alignment-output", f"{no_shift_result}/shg_load_alignment.csv",
            "--coordination-output", f"{no_shift_result}/msg_coordination_value.csv",
            "--lineage-output", f"{no_shift_result}/curve_lineage.csv",
            "--done-output", f"{no_shift_result}/validated.done.json"], None),
        ("Combine core architecture industries", [
            "08_code/summarize_group_multisite_core.py",
            "--root", core,
            "--industries", *INDUSTRIES,
            "--summary-output", f"{core}/national/core_scenarios.csv",
            "--alignment-output", f"{core}/national/shg_load_alignment.csv",
            "--coordination-output", f"{core}/national/msg_coordination_value.csv",
            "--lineage-output", f"{core}/national/curve_lineage.csv",
            "--done-output", f"{core}/national/validated.done.json"], None),
        ("U.S. enterprise payments", [
            "08_code/analyze_us_industry_heterogeneous_hardware.py",
            "--demand", "02_data/processed/us_demand/us_manufacturing_ai_effective_service_2030.csv",
            "--national-task-summary", f"{us_demand}/us_national_task_summary.csv",
            "--defaults", "config/defaults.yaml",
            "--demand-config", "config/demand_cases/us_manufacturing_ai_demand_v0.1.yaml",
            "--routing-config", "config/compute_hardware/cpu_gpu_routing_v1.yaml",
            "--cloud-routing-config", "config/compute_hardware/cpu_gpu_routing_v2.yaml",
            "--cloud-delivery-config", "config/demand_cases/c36_local_cloud_core_v2.yaml",
            "--us-cost-config", "config/cost_cases/us_heterogeneous_cpu_v1.yaml",
            "--us-parameters", "02_data/processed/cost_benchmark/us_core_cost_parameters_v1.csv",
            "--us-api-prices", "02_data/processed/cost_benchmark/us_api_token_prices_v1.csv",
            "--compute-efficiency", "02_data/processed/compute_efficiency/common_it_effective_efficiency_scenarios.csv",
            "--output-dir", us_cost], f"{us_cost}/workflow.log"),
        ("National grid-capacity comparison", [
            "08_code/summarize_national_grid_capacity_comparison.py",
            "--national-summary", f"{core}/national/core_scenarios.csv",
            "--national-validation", f"{core}/national/validated.done.json",
            "--cloud-summary", f"{SENSITIVITY}/national_cloud_center_v1/summary.csv",
            "--output", f"{SENSITIVITY}/national_grid_capacity_comparison.csv",
            "--done-output", f"{SENSITIVITY}/national_grid_capacity_comparison.validated.done.json"], None),
        ("China enterprise payments", [
            "08_code/run_national_local_vs_cloud_cost_v1.py",
            "--config", "config/demand_cases/national_local_cloud_core_v1.yaml",
            "--defaults", "config/defaults.yaml",
            "--run-config", "config/runs/all_industries_core.yaml",
            "--task-ledger", f"{ledger}/task_ledger.csv",
            "--lifecycle-ledger", f"{ledger}/lifecycle_ledger.csv",
            "--local-summary", f"{core}/national/core_scenarios.csv",
            "--output-dir", f"{RESULT}/national_local_cloud_cost_v1/cost"], None),
        ("Temporal-shifting pair", [
            "08_code/summarize_temporal_shifting_pair.py",
            "--defaults", "config/defaults.yaml",
            "--registry", "config/sensitivity/national_oat_extension_v1.yaml",
            "--case-config", f"{NO_SHIFT}/configs/PHY03__no_shift.yaml",
            "--baseline-summary", f"{core}/national/core_scenarios.csv",
            "--baseline-validation", f"{core}/national/validated.done.json",
            "--no-shift-summary", f"{no_shift_result}/core_scenarios.csv",
            "--no-shift-validation", f"{no_shift_result}/validated.done.json",
            "--output", f"{no_shift_result}/temporal_shifting_value.csv",
            "--done-output", f"{no_shift_result}/temporal_shifting.validated.done.json"], None),
        ("Manufacturing-AI demand figure", [
            "08_code/build_figure1_manufacturing_ai_demand.py",
            "--adoption-input", "02_data/china_manufacturing_ai_31sector_proxy_parameters.csv",
            "--service-input", "02_data/processed/effective_service/manufacturing_ai_effective_service_2030.csv",
            "--attribution-input", "02_data/manufacturing_foundation_model_task_attribution_parameters_v0.1.csv",
            "--data-output", f"{RESULT}/manuscript_figures/figure1_manufacturing_ai_demand_data.csv",
            "--png-output", f"{RESULT}/manuscript_figures/figure1_manufacturing_ai_demand.png",
            "--pdf-output", f"{RESULT}/manuscript_figures/figure1_manufacturing_ai_demand.pdf",
            "--svg-output", f"{RESULT}/manuscript_figures/figure1_manufacturing_ai_demand.svg",
            "--metadata-output", f"{RESULT}/manuscript_figures/figure1_manufacturing_ai_demand.metadata.json"], None),
        ("Load-coordination figure", [
            "08_code/build_figure3_load_coordination_redesign.py",
            "--output-stem", f"{RESULT}/manuscript_figures/figure3_load_coordination"], None),
        ("Interconnection node distribution", [
            "08_code/build_node_interconnection_distribution.py",
            "--config", "config/scenarios/node_interconnection_distribution_v1.yaml"], None),
        ("Battery peak-shaving alternative", [
            "08_code/analyze_bess_peak_shaving.py"], None),
        ("Grid-capacity summary", [
            "08_code/build_rq1_infrastructure_interpretation.py",
            "--config", "config/scenarios/rq1_infrastructure_summary_v1.yaml"], None),
        ("Resource-footprint summary", [
            "08_code/build_rq1_resource_footprint_summary.py",
            "--config", "config/scenarios/rq1_resource_footprint_summary_v1.yaml", "--replay-check"], None),
        ("Mechanism decomposition", [
            "08_code/summarize_rq2_mechanisms.py",
            "--config", "config/scenarios/rq2_mechanism_summary_v1.yaml",
            "--output", f"{RESULT}/rq2_mechanisms/rq2_mechanism_effects.csv",
            "--done-output", f"{RESULT}/rq2_mechanisms/rq2_mechanism_effects.validated.done.json"], None),
        ("Grid-capacity figure and data", [
            "08_code/build_figure3_rq1_grid_capacity.py",
            "--config", "config/scenarios/figure3_rq1_grid_capacity_v2.yaml"], None),
        ("GM figures: architectures and site distribution", [
            "08_code/build_gm_figures.py",
            "--output-dir", f"{RESULT}/manuscript_figures"], None),
        ("Spatial water audit", [
            "08_code/audit_rq1_spatial_water.py",
            "--config", "config/scenarios/rq1_spatial_water_audit_v1.yaml"], None),
        ("Resource-footprint panel data", [
            "08_code/build_figure4_rq1_resource_footprint.py",
            "--config", "config/scenarios/figure4_rq1_resource_footprint_v1.yaml"], None),
        ("Provincial water allocation", [
            "08_code/build_figure5_rq1_spatial_water.py",
            "--config", "config/scenarios/figure5_rq1_spatial_water_v1.yaml", *figure5], None),
        ("Resource and payment figure", [
            "08_code/build_figure4_resource_and_enterprise_cost.py", "--main-manuscript-updated"], None),
        ("Water table", [
            "08_code/build_rq1_spatial_water_interpretation.py",
            "--config", "config/scenarios/rq1_spatial_water_interpretation_v1.yaml"], None),
    ]


def snapshot(destination: Path) -> list[Path]:
    saved = []
    for root in COMPARED_ROOTS:
        for path in sorted((ROOT / root).rglob("*.csv")):
            relative = path.relative_to(ROOT)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            saved.append(relative)
    return saved


def _json_numbers_close(x, y, rtol: float, atol: float) -> bool:
    """Compare two parsed JSON values; numbers within tolerance, everything else exactly."""
    if isinstance(x, dict) and isinstance(y, dict):
        return x.keys() == y.keys() and all(_json_numbers_close(x[k], y[k], rtol, atol) for k in x)
    if isinstance(x, list) and isinstance(y, list):
        return len(x) == len(y) and all(_json_numbers_close(p, q, rtol, atol) for p, q in zip(x, y))
    if isinstance(x, (int, float)) and isinstance(y, (int, float)) \
            and not isinstance(x, bool) and not isinstance(y, bool):
        return bool(np.isclose(x, y, rtol=rtol, atol=atol))
    return x == y


def _json_equal(a: pd.Series, b: pd.Series, rtol: float, atol: float) -> bool:
    """True when both text columns hold JSON objects or arrays that agree within tolerance."""
    for left, right in zip(a, b):
        if left == right:
            continue
        try:
            parsed = (json.loads(left), json.loads(right))
        except ValueError:
            return False
        if not _json_numbers_close(*parsed, rtol, atol):
            return False
    return True


def compare(reference: Path, current: Path, rtol: float, atol: float) -> str | None:
    """Return a description of the first difference, or None when equal."""
    if not current.exists():
        return "missing after rebuild"
    try:
        left = pd.read_csv(reference, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        right = pd.read_csv(current, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except pd.errors.EmptyDataError:
        return None if reference.read_bytes() == current.read_bytes() else "empty file differs"
    if list(left.columns) != list(right.columns):
        return "columns differ"
    if left.shape != right.shape:
        return f"shape {left.shape} -> {right.shape}"
    for column in left.columns:
        a, b = left[column], right[column]
        if a.equals(b):
            continue
        if _json_equal(a, b, rtol, atol):
            continue
        x = pd.to_numeric(a, errors="coerce")
        y = pd.to_numeric(b, errors="coerce")
        numeric = x.notna() | y.notna()
        if (a[~numeric] != b[~numeric]).any():
            row = int(np.flatnonzero((a != b).to_numpy())[0])
            return f"column {column!r} row {row}: {a.iloc[row]!r} -> {b.iloc[row]!r}"
        if not np.allclose(x[numeric], y[numeric], rtol=rtol, atol=atol, equal_nan=True):
            delta = float(np.nanmax(np.abs(x[numeric] - y[numeric])))
            return f"column {column!r}: max abs difference {delta:.3g}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="Print the steps without running them.")
    parser.add_argument("--rtol", type=float, default=1e-9)
    parser.add_argument("--atol", type=float, default=1e-9)
    parser.add_argument("--skip-compare", action="store_true",
                        help="Rebuild without comparing to the previous outputs (e.g. after re-solving).")
    args = parser.parse_args()

    plan = steps()
    if args.list:
        for number, (name, command, log) in enumerate(plan, start=1):
            redirect = f" > {log}" if log else ""
            print(f"{number:2d}. {name}\n    python {' '.join(command)}{redirect}")
        return 0

    with tempfile.TemporaryDirectory(prefix="paper_reference_") as temporary:
        reference = Path(temporary)
        saved = snapshot(reference)
        for number, (name, command, log) in enumerate(plan, start=1):
            missing = [path for path in REQUIRED_RAW_INPUTS.get(name, []) if not (ROOT / path).exists()]
            if missing:
                print(f"[{number}/{len(plan)}] {name}: SKIPPED, raw input not found "
                      f"({', '.join(missing)}); shipped outputs kept. See DATA_SOURCES.md.", flush=True)
                continue
            print(f"[{number}/{len(plan)}] {name}", flush=True)
            stdout = (ROOT / log).open("w") if log else subprocess.DEVNULL
            try:
                subprocess.run([sys.executable, *command], cwd=ROOT, check=True,
                               stdout=stdout, stderr=subprocess.STDOUT if log else None)
            finally:
                if log:
                    stdout.close()

        if args.skip_compare:
            print("\nRebuilt all steps; comparison skipped.")
            return 0
        differences = []
        for relative in saved:
            problem = compare(reference / relative, ROOT / relative, args.rtol, args.atol)
            if problem:
                differences.append(f"{relative}: {problem}")
    print(f"\nCompared {len(saved)} CSV files with the shipped results.")
    if differences:
        print(f"{len(differences)} differ:")
        for line in differences:
            print("  ", line)
        return 1
    print("All regenerated CSV files match the shipped results.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
