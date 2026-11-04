#!/usr/bin/env python3
"""Build the validated three-panel resource and enterprise-payment Figure 4.

Panel a combines the three approved PF-versus-LDC resource comparisons in a
radar chart with independently normalized axes and explicit absolute values.
Panels b and c report the validated China and U.S. demand-level payment ranges.
China low/high demand values scale the current v1.0.0 base ledgers by total
effective service; U.S. values use the independently constructed 21-NAICS
demand and cost results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

os.environ["MPLCONFIGDIR"] = str(Path(tempfile.gettempdir()) / "dllm_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "dllm_cache"))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULT_ROOT = ROOT / "05_results/v1.0.0/result"
RESOURCE_DATA = RESULT_ROOT / "manuscript_figures/figure4_resource_footprint_data.csv"
RESOURCE_MARKER = RESULT_ROOT / "manuscript_figures/figure4_resource_footprint.validated.done.json"
COST_DATA = RESULT_ROOT / "national_local_cloud_cost_v1/cost/comparison.csv"
COST_MARKER = RESULT_ROOT / "national_local_cloud_cost_v1/cost/validated.done.json"
CHINA_SERVICE_DATA = ROOT / "02_data/processed/effective_service/manufacturing_ai_effective_service_2030.csv"
US_COST_DATA = RESULT_ROOT / "cost_benchmark/heterogeneous_hardware_v1/us_naics3/us_national_comparison.csv"
US_COST_MARKER = RESULT_ROOT / "cost_benchmark/heterogeneous_hardware_v1/us_naics3/validated.done.json"
US_DEMAND_MARKER = RESULT_ROOT / "us_demand/validated.done.json"
OUTPUT_ROOT = RESULT_ROOT / "manuscript_figures"
STEM = "figure4_resource_and_enterprise_cost"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--manuscript-output-root", type=Path)
    parser.add_argument("--main-manuscript-updated", action="store_true")
    parser.add_argument("--check-only", action="store_true", help="Validate all registered inputs without rewriting outputs")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_and_validate() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict, dict]:
    required = [
        RESOURCE_DATA,
        RESOURCE_MARKER,
        COST_DATA,
        COST_MARKER,
        CHINA_SERVICE_DATA,
        US_COST_DATA,
        US_COST_MARKER,
        US_DEMAND_MARKER,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing validated Figure 4 input: " + ", ".join(missing))

    resource_marker = json.loads(RESOURCE_MARKER.read_text(encoding="utf-8"))
    cost_marker = json.loads(COST_MARKER.read_text(encoding="utf-8"))
    us_cost_marker = json.loads(US_COST_MARKER.read_text(encoding="utf-8"))
    us_demand_marker = json.loads(US_DEMAND_MARKER.read_text(encoding="utf-8"))
    if resource_marker.get("status") != "validated_author_approved_RQ1_resource_figure":
        raise ValueError("Resource figure is not author-approved and validated")
    if resource_marker.get("model_version") != "v1.0.0":
        raise ValueError("Resource figure is not from model version v1.0.0")
    expected_resource_hash = resource_marker["outputs"]["data"]["sha256"]
    if sha256(RESOURCE_DATA) != expected_resource_hash:
        raise ValueError("Resource figure data differ from their validation marker")
    if cost_marker.get("status") != "validated_national_all_local_vs_all_cloud_screening":
        raise ValueError("Enterprise-payment comparison is not validated")
    if cost_marker.get("scenario_version") != "national_local_cloud_core_v1.0.0":
        raise ValueError("Enterprise-payment comparison is not the v1.0.0 scenario")
    if not cost_marker.get("same_service") or not cost_marker.get("cloud_components_reconcile"):
        raise ValueError("Enterprise-payment comparison failed a required validation")

    resource = pd.read_csv(RESOURCE_DATA, encoding="utf-8-sig")
    if len(resource) != 6 or set(resource["architecture"]) != {"PF", "LDC_AGGREGATE"}:
        raise ValueError("Resource panels require exactly six approved plotting rows")
    cost = pd.read_csv(COST_DATA, encoding="utf-8-sig")
    base_cost = cost[cost["cloud_price_case"].eq("base")].copy()
    if len(base_cost) != 12 or base_cost["provider_bundle"].nunique() != 4:
        raise ValueError("China cost lines require three architectures and four base-price cloud bundles")
    if base_cost["local_architecture"].nunique() != 3:
        raise ValueError("China cost lines require PF, SHG, and MSG")
    if not base_cost["same_annual_effective_service_units"].nunique() == 1:
        raise ValueError("China cost lines do not use one common base service quantity")
    if not base_cost["equal_effectiveness_assumption"].astype(bool).all():
        raise ValueError("China cost lines lack the equal-effectiveness assumption")

    china_service = pd.read_csv(CHINA_SERVICE_DATA, encoding="utf-8-sig")
    service_cases = set(china_service["parameter_case"])
    if service_cases != {"low", "base", "high"}:
        raise ValueError("China service data must contain low, base, and high demand cases")

    us_cost = pd.read_csv(US_COST_DATA, encoding="utf-8-sig")
    us_base_price = us_cost[us_cost["cpu_server_price_case"].eq("base")].copy()
    if set(us_base_price["parameter_case"]) != {"low", "base", "high"}:
        raise ValueError("U.S. cost lines must contain low, base, and high demand cases")
    if us_base_price["provider"].nunique() != 3:
        raise ValueError("U.S. cost lines require three cloud providers")
    if us_cost_marker.get("model_version") != "v1.0.0":
        raise ValueError("U.S. enterprise-payment comparison is not from model version v1.0.0")
    if us_cost_marker.get("status") != "complete_validated_us_21_naics_shared_cloud_service_contract":
        raise ValueError("U.S. enterprise-payment comparison is not validated")
    if us_demand_marker.get("status") != "validated" or us_demand_marker.get("model_version") != "v1.0.0":
        raise ValueError("U.S. demand package is not validated for model version v1.0.0")
    return resource, base_cost, china_service, us_base_price, resource_marker, cost_marker, us_cost_marker


def make_plot_data(
    resource: pd.DataFrame,
    china_cost: pd.DataFrame,
    china_service: pd.DataFrame,
    us_cost: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    panel_letters = {
        "onsite_cooling_humidification_water": "a",
        "total_facility_floor_requirement": "b",
        "offsite_land_conversion": "c",
    }
    display_labels = {
        "PF": "Factory deployment",
        "LDC_AGGREGATE": "New large data centers",
    }
    for row in resource.itertuples(index=False):
        rows.append(
            {
                "panel": panel_letters[row.metric_id],
                "metric_id": row.metric_id,
                "comparison_item": display_labels[row.architecture],
                "value_low": float(row.plot_value),
                "value_high": float(row.plot_value),
                "unit": row.plot_unit,
                "scenario_boundary": row.boundary,
            }
        )

    china_totals = china_service.groupby("parameter_case")["effective_service_units_day"].sum()
    china_ratios = china_totals / float(china_totals["base"])
    china_local = china_cost.drop_duplicates("local_architecture")
    china_cloud = china_cost.drop_duplicates("provider_bundle")
    for demand_case in ["low", "base", "high"]:
        ratio = float(china_ratios[demand_case])
        for item in china_local.itertuples(index=False):
            rows.append(
                {
                    "panel": "d",
                    "metric_id": "annual_enterprise_total_payment",
                    "comparison_item": "On-site deployment",
                    "series_id": item.local_architecture,
                    "demand_case": demand_case,
                    "value_low": float(item.annual_100pct_local_cost_rmb) * ratio / 1e9,
                    "value_high": float(item.annual_100pct_local_cost_rmb) * ratio / 1e9,
                    "unit": "billion RMB/year",
                    "scenario_boundary": "current base local ledger scaled by national effective-service demand ratio",
                }
            )
        for item in china_cloud.itertuples(index=False):
            rows.append(
                {
                    "panel": "d",
                    "metric_id": "annual_enterprise_total_payment",
                    "comparison_item": "Cloud procurement",
                    "series_id": item.provider_bundle,
                    "demand_case": demand_case,
                    "value_low": float(item.annual_100pct_cloud_cost_rmb) * ratio / 1e9,
                    "value_high": float(item.annual_100pct_cloud_cost_rmb) * ratio / 1e9,
                    "unit": "billion RMB/year",
                    "scenario_boundary": "current base cloud ledger scaled by national effective-service demand ratio",
                }
            )

    for demand_case in ["low", "base", "high"]:
        selected = us_cost[us_cost["parameter_case"].eq(demand_case)]
        local = float(selected["local_total_annual_cost_usd"].iloc[0]) / 1e9
        rows.append(
            {
                "panel": "e",
                "metric_id": "annual_enterprise_total_payment",
                "comparison_item": "On-site deployment",
                "series_id": "industry-sized",
                "demand_case": demand_case,
                "value_low": local,
                "value_high": local,
                "unit": "billion USD/year",
                "scenario_boundary": "21 NAICS industries sized independently and summed nationally",
            }
        )
        for item in selected.itertuples(index=False):
            rows.append(
                {
                    "panel": "e",
                    "metric_id": "annual_enterprise_total_payment",
                    "comparison_item": "Cloud procurement",
                    "series_id": item.provider,
                    "demand_case": demand_case,
                    "value_low": float(item.cloud_total_annual_cost_usd) / 1e9,
                    "value_high": float(item.cloud_total_annual_cost_usd) / 1e9,
                    "unit": "billion USD/year",
                    "scenario_boundary": "nationally pooled residual cloud capacity after managed/API delivery",
                }
            )
    return pd.DataFrame(rows)


def style_axis(axis: plt.Axes, grid_axis: str = "x") -> None:
    axis.grid(axis=grid_axis, color="#D8DDE1", linewidth=0.8, alpha=0.75)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)


def plot_cost_lines(
    axis: plt.Axes,
    data: pd.DataFrame,
    letter: str,
    country: str,
    unit: str,
    blue: str,
    orange: str,
) -> None:
    order = ["low", "base", "high"]
    x = np.arange(len(order), dtype=float)
    maxima: list[float] = []
    for comparison_item, color, offset in [
        ("On-site deployment", blue, -0.035),
        ("Cloud procurement", orange, 0.035),
    ]:
        selected = data[data["comparison_item"].eq(comparison_item)]
        low = np.array(
            [selected[selected["demand_case"].eq(case)]["value_low"].min() for case in order]
        )
        high = np.array(
            [selected[selected["demand_case"].eq(case)]["value_high"].max() for case in order]
        )
        xx = x + offset
        axis.fill_between(xx, low, high, color=color, alpha=0.18, zorder=1)
        axis.plot(xx, low, color=color, linewidth=2.0, marker="o", markersize=4.5, zorder=3)
        axis.plot(xx, high, color=color, linewidth=2.0, marker="o", markersize=4.5, zorder=3)
        axis.vlines(xx, low, high, color=color, linewidth=3.5, alpha=0.8, zorder=2)
        maxima.extend(high.tolist())
    axis.set_xticks(x, ["Low", "Base", "High"])
    axis.tick_params(axis="both", labelsize=18)
    axis.set_xlabel("AI service demand", fontsize=20, labelpad=8)
    axis.set_ylabel(unit, fontsize=20, labelpad=10)
    axis.set_title(
        f"{letter}  Annual payments: {country}",
        loc="left",
        fontweight="bold",
        fontsize=22,
        pad=18,
    )
    axis.set_ylim(0, max(maxima) * 1.20)
    axis.legend(
        handles=[
            plt.Line2D([0], [0], color=blue, marker="o", linewidth=2, label="Factory-site deployment"),
            plt.Line2D([0], [0], color=orange, marker="o", linewidth=2, label="Cloud procurement"),
        ],
        frameon=False,
        ncol=1,
        fontsize=16,
        loc="upper left",
    )
    style_axis(axis, "y")


def plot_resource_radar(axis: plt.Axes, data: pd.DataFrame, blue: str, gray: str) -> None:
    panels = ["a", "b", "c"]
    factory = np.array(
        [
            float(
                data[
                    data["panel"].eq(panel)
                    & data["comparison_item"].eq("Factory deployment")
                ]["value_low"].iloc[0]
            )
            for panel in panels
        ]
    )
    ldc = np.array(
        [
            float(
                data[
                    data["panel"].eq(panel)
                    & data["comparison_item"].eq("New large data centers")
                ]["value_low"].iloc[0]
            )
            for panel in panels
        ]
    )
    ratios = factory / ldc
    theta = np.linspace(0, 2 * np.pi, len(panels), endpoint=False)
    closed_theta = np.r_[theta, theta[0]]

    axis.set_theta_offset(np.pi / 2)
    axis.set_theta_direction(-1)
    axis.set_ylim(0, 1.10)
    axis.set_xticks(theta)
    axis.set_xticklabels([])
    axis.set_yticks([0.25, 0.50, 0.75, 1.00])
    axis.set_yticklabels([])
    axis.grid(color="#D8DDE1", linewidth=1.0)
    axis.spines["polar"].set_color(gray)
    axis.spines["polar"].set_linewidth(1.5)

    ldc_closed = np.r_[np.ones(3), 1.0]
    pf_closed = np.r_[ratios, ratios[0]]
    axis.fill(closed_theta, ldc_closed, color=gray, alpha=0.08, zorder=1)
    axis.plot(closed_theta, ldc_closed, color=gray, linewidth=2.0, marker="s", markersize=6, markerfacecolor="white", zorder=2)
    axis.fill(closed_theta, pf_closed, color=blue, alpha=0.18, zorder=3)
    axis.plot(closed_theta, pf_closed, color=blue, linewidth=3.0, marker="o", markersize=7, zorder=4)

    ratio_labels = [f"{ratios[0]:.2f}", f"{ratios[1]:.2f}", "0*"]
    offsets = [(0, 14), (-6, -22), (-18, -1)]
    for angle, ratio, label, offset in zip(theta, ratios, ratio_labels, offsets):
        axis.annotate(
            label,
            xy=(angle, ratio),
            xytext=offset,
            textcoords="offset points",
            ha="center",
            va="center",
            color=blue,
            fontsize=19,
            fontweight="bold",
            zorder=5,
        )

    labels = [
        (
            0.50,
            1.165,
            "On-site water",
            f"{factory[0]:.3f} / {ldc[0]:.3f} million m$^3$ yr$^{{-1}}$",
            "center",
        ),
        (
            0.99,
            0.025,
            "Facility floor",
            f"{factory[1]:.3f} / {ldc[1]:.3f}\n(million m$^2$)",
            "right",
        ),
        (
            0.01,
            0.025,
            "Off-site land",
            f"0* / {ldc[2]:.3f}\n(million m$^2$)",
            "left",
        ),
    ]
    for x, y, title, values, alignment in labels:
        axis.text(
            x,
            y,
            title,
            transform=axis.transAxes,
            ha=alignment,
            va="bottom",
            fontsize=19,
            fontweight="bold",
        )
        axis.text(
            x,
            y - 0.050,
            values,
            transform=axis.transAxes,
            ha=alignment,
            va="top",
            fontsize=17.5,
            linespacing=1.15,
        )

    axis.text(-0.17, 1.30, "a", transform=axis.transAxes, fontsize=26, fontweight="bold", ha="left")
    axis.text(-0.07, 1.30, "Relative resource requirements", transform=axis.transAxes, fontsize=22, fontweight="bold", ha="left")
    axis.legend(
        handles=[
            plt.Line2D([0], [0], color=blue, marker="o", linewidth=3, label="Per-factory deployment (PF)"),
            plt.Line2D([0], [0], color=gray, marker="s", markerfacecolor="white", linewidth=2, label="New large data centers (LDC = 1)"),
        ],
        frameon=False,
        fontsize=17,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.19),
        ncol=1,
        handlelength=1.5,
        handletextpad=0.7,
    )


def plot(data: pd.DataFrame, outputs: dict[str, Path]) -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "font.size": 18,
        }
    )
    blue = "#3C78A8"
    gray = "#8D959C"
    orange = "#A65E3F"
    fig = plt.figure(figsize=(13.5, 5.8))
    grid = fig.add_gridspec(1, 3, width_ratios=[1.08, 1.18, 1.18], wspace=0.31)

    plot_resource_radar(fig.add_subplot(grid[0, 0], projection="polar"), data, blue, gray)

    plot_cost_lines(
        fig.add_subplot(grid[0, 1]),
        data[data["panel"].eq("d")],
        "b",
        "China",
        "billion CNY/year",
        blue,
        orange,
    )
    plot_cost_lines(
        fig.add_subplot(grid[0, 2]),
        data[data["panel"].eq("e")],
        "c",
        "United States",
        "billion USD/year",
        blue,
        orange,
    )

    fig.subplots_adjust(left=0.04, right=0.995, top=0.84, bottom=0.18)
    for path in outputs.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outputs["svg"], bbox_inches="tight")
    fig.savefig(outputs["png"], dpi=600, bbox_inches="tight")
    fig.savefig(outputs["pdf"], bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    resource, china_cost, china_service, us_cost, resource_marker, cost_marker, us_cost_marker = load_and_validate()
    data = make_plot_data(resource, china_cost, china_service, us_cost)
    output_root = args.output_root.resolve()
    outputs = {extension: output_root / f"{STEM}.{extension}" for extension in ["svg", "png", "pdf"]}
    data_path = output_root / f"{STEM}_data.csv"
    marker_path = output_root / f"{STEM}.validated.done.json"
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "validated_inputs_ready_for_figure4_resource_and_enterprise_cost_v2_radar",
                    "plot_rows": len(data),
                    "output_root": str(output_root),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    output_root.mkdir(parents=True, exist_ok=True)
    data.to_csv(data_path, index=False, encoding="utf-8-sig")
    plot(data, outputs)

    marker = {
        "status": "validated_v1.0.0_resource_and_enterprise_payment_figure",
        "model_version": "v1.0.0",
        "figure_version": "figure4_resource_and_enterprise_cost_v2_radar",
        "inputs": {
            "resource_data": {"path": relative(RESOURCE_DATA), "sha256": sha256(RESOURCE_DATA)},
            "resource_validation": {"path": relative(RESOURCE_MARKER), "sha256": sha256(RESOURCE_MARKER)},
            "cost_data": {"path": relative(COST_DATA), "sha256": sha256(COST_DATA)},
            "cost_validation": {"path": relative(COST_MARKER), "sha256": sha256(COST_MARKER)},
            "china_service_data": {"path": relative(CHINA_SERVICE_DATA), "sha256": sha256(CHINA_SERVICE_DATA)},
            "us_cost_data": {"path": relative(US_COST_DATA), "sha256": sha256(US_COST_DATA)},
            "us_cost_validation": {"path": relative(US_COST_MARKER), "sha256": sha256(US_COST_MARKER)},
            "us_demand_validation": {"path": relative(US_DEMAND_MARKER), "sha256": sha256(US_DEMAND_MARKER)},
        },
        "outputs": {
            "data": {"path": relative(data_path), "sha256": sha256(data_path)},
            **{key: {"path": relative(path), "sha256": sha256(path)} for key, path in outputs.items()},
        },
        "cost_panels": {
            "panels": ["china_demand_range", "us_demand_range"],
            "parameter_cases": ["low", "base", "high"],
            "china_low_high_method": "current base ledgers scaled by national total effective-service ratios",
            "us_method": us_cost_marker["aggregation_boundary"],
            "boundary": "enterprise payment screening at equal assumed effectiveness; not social cost or procurement advice",
        },
        "layout": {
            "panel_a": "three resource axes independently normalized to the corresponding LDC value of 1; absolute PF/LDC values printed outside the radar",
            "panel_b": "China annual enterprise-payment ranges in RMB with an independent vertical axis",
            "panel_c": "United States annual enterprise-payment ranges in USD with an independent vertical axis",
            "radar_area_is_aggregate_score": False,
            "cost_point_value_annotations": False,
        },
        "resource_interpretation_status": resource_marker["interpretation_status"],
        "cost_scenario_version": cost_marker["scenario_version"],
        "main_manuscript_updated": args.main_manuscript_updated,
    }
    marker_path.write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.manuscript_output_root:
        manuscript_root = args.manuscript_output_root.resolve()
        manuscript_root.mkdir(parents=True, exist_ok=True)
        for extension, source in outputs.items():
            shutil.copy2(source, manuscript_root / f"{STEM}_manuscript.{extension}")

    print(json.dumps({"status": marker["status"], "png": str(outputs["png"]), "marker": str(marker_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
