#!/usr/bin/env python3
"""Draft redesign of the manuscript's illustrative load-coordination figure.

The draft deliberately leaves the national capacity results to Figure 2.  It
uses the validated C36 hourly outputs only to make the physical mechanism more
visible: AI load fits into time-varying production headroom within a site and
is redistributed toward headroom across sites.
"""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

os.environ["MPLCONFIGDIR"] = str(Path(tempfile.gettempdir()) / "distributed_llm_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "distributed_llm_cache"))

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "05_results/v1.0.0/result/group_architecture_core/C36"
DEFAULT_OUT_STEM = ROOT / "05_results/v1.0.0/result/manuscript_figures/figure3_load_coordination"

DAY_CENTERS = np.array([12, 36, 60, 84, 108, 132, 156])
DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_BOUNDARIES = np.array([24, 48, 72, 96, 120, 144]) - 0.5

PRODUCTION = "#AEB8BF"
PRODUCTION_EDGE = "#5D6B73"
AI = "#D96B25"
AI_DARK = "#A84612"
HEADROOM = "#CFE6EE"
ENVELOPE = "#2B6F84"
OVERFLOW = "#B23A2B"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hourly = pd.read_csv(DATA_ROOT / "hourly.csv")
    shg = hourly[
        hourly.architecture.eq("SHG") & hourly.base_load_case.eq("actual_load")
    ].sort_values("hour").copy()
    shg_zero = hourly[
        hourly.architecture.eq("SHG") & hourly.base_load_case.eq("zero_load")
    ].sort_values("hour").copy()
    msg = hourly[
        hourly.architecture.eq("MSG") & hourly.base_load_case.eq("actual_load")
    ].sort_values(["factory_id", "hour"]).copy()
    msg_no_routing = pd.read_csv(DATA_ROOT / "msg_no_routing_hourly.csv").sort_values(
        ["factory_id", "hour"]
    )

    if len(shg) != 168 or len(shg_zero) != 168:
        raise ValueError("SHG actual- and zero-production-load series must each contain 168 hours")
    if msg.groupby("factory_id").hour.nunique().ne(168).any():
        raise ValueError("MSG coordinated output has incomplete node-hour coverage")
    if msg_no_routing.groupby("factory_id").hour.nunique().ne(168).any():
        raise ValueError("MSG no-routing output has incomplete node-hour coverage")
    return shg, shg_zero, msg, msg_no_routing


def style_time_axis(ax: plt.Axes, *, labels: bool = True) -> None:
    ax.set_xlim(-0.5, 167.5)
    ax.set_xticks(DAY_CENTERS, DAY_LABELS if labels else [])
    for boundary in DAY_BOUNDARIES:
        ax.axvline(boundary, color="white", lw=1.0, alpha=0.9, zorder=0)
    ax.grid(axis="y", color="#D8DDE1", lw=0.7, alpha=0.65)


def draw_site_envelope(
    ax: plt.Axes,
    hours: np.ndarray,
    production: np.ndarray,
    ai_power: np.ndarray,
    baseline_peak: float,
    *,
    counterfactual_total: np.ndarray | None = None,
) -> None:
    combined = production + ai_power
    ax.fill_between(hours, 0, production, color=PRODUCTION, alpha=0.78, zorder=1)
    ax.plot(hours, production, color=PRODUCTION_EDGE, lw=1.0, zorder=3)
    ax.fill_between(hours, production, combined, color=AI, alpha=0.88, zorder=2)
    ax.plot(hours, combined, color=AI_DARK, lw=1.25, zorder=4)
    ax.fill_between(
        hours,
        combined,
        baseline_peak,
        where=combined <= baseline_peak,
        interpolate=True,
        color=HEADROOM,
        alpha=0.78,
        zorder=0,
    )
    ax.fill_between(
        hours,
        baseline_peak,
        combined,
        where=combined > baseline_peak,
        interpolate=True,
        color=OVERFLOW,
        alpha=0.85,
        zorder=5,
    )
    ax.axhline(baseline_peak, color=ENVELOPE, lw=1.5, ls=(0, (5, 3)), zorder=6)
    if counterfactual_total is not None:
        ax.plot(
            hours,
            counterfactual_total,
            color="#6E4B7E",
            lw=1.45,
            ls=(0, (3, 2)),
            zorder=7,
        )


def choose_snapshot_hour(
    coordinated: pd.DataFrame, no_routing: pd.DataFrame
) -> tuple[int, pd.Series]:
    peaks = coordinated.groupby("factory_id").base_load_mw.max()

    def overflow_by_hour(frame: pd.DataFrame) -> pd.Series:
        work = frame.copy()
        work["baseline_peak"] = work.factory_id.map(peaks)
        work["overflow"] = (
            work.base_load_mw + work.ai_facility_power_mw - work.baseline_peak
        ).clip(lower=0)
        return work.groupby("hour").overflow.sum()

    avoided = overflow_by_hour(no_routing) - overflow_by_hour(coordinated)
    return int(avoided.idxmax()), avoided


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-stem",
        type=Path,
        default=DEFAULT_OUT_STEM,
        help="Output path without suffix; PNG, PDF, and SVG files are written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_stem = args.output_stem if args.output_stem.is_absolute() else ROOT / args.output_stem
    shg, shg_zero, msg, msg_no_routing = load_data()

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Arial Unicode MS", "DejaVu Sans"],
            "font.size": 16,
            "axes.titleweight": "bold",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
        }
    )

    fig = plt.figure(figsize=(15.2, 8.2), facecolor="white")
    grid = fig.add_gridspec(
        2,
        2,
        width_ratios=[1.18, 1.0],
        height_ratios=[1.05, 0.95],
        wspace=0.22,
        hspace=0.38,
    )
    ax_week = fig.add_subplot(grid[0, 0])
    ax_zoom = fig.add_subplot(grid[1, 0])
    ax_space = fig.add_subplot(grid[0, 1])
    ax_snapshot = fig.add_subplot(grid[1, 1])

    hours = shg.hour.to_numpy(dtype=int)
    production = shg.base_load_mw.to_numpy(dtype=float)
    ai_power = shg.ai_facility_power_mw.to_numpy(dtype=float)
    baseline_peak = float(production.max())

    # a: full-week capacity envelope.
    draw_site_envelope(ax_week, hours, production, ai_power, baseline_peak)
    style_time_axis(ax_week)
    ax_week.set_ylim(0, max((production + ai_power).max(), baseline_peak) * 1.11)
    ax_week.set_ylabel("Site load (MW)")
    ax_week.set_title(
        "a  Production and AI load at one factory",
        loc="left",
        fontsize=19,
    )

    # b: a 48-hour zoom around the weekly production peak.
    zoom_start, zoom_end = 66, 114
    mask = (hours >= zoom_start) & (hours <= zoom_end)
    zero_ai = shg_zero.ai_facility_power_mw.to_numpy(dtype=float)
    counterfactual_total = production + zero_ai
    draw_site_envelope(
        ax_zoom,
        hours[mask],
        production[mask],
        ai_power[mask],
        baseline_peak,
        counterfactual_total=counterfactual_total[mask],
    )
    ax_zoom.set_xlim(zoom_start - 0.5, zoom_end + 0.5)
    ticks = np.arange(72, 115, 6)
    day_names = {72: "Thu 00", 96: "Fri 00"}
    labels = [day_names.get(int(t), f"{int(t % 24):02d}:00") for t in ticks]
    ax_zoom.set_xticks(ticks, labels)
    ax_zoom.grid(axis="y", color="#D8DDE1", lw=0.7, alpha=0.65)
    ax_zoom.axvline(95.5, color="#D3D8DC", lw=0.8)
    ax_zoom.set_ylim(0, max(counterfactual_total[mask].max(), (production + ai_power)[mask].max()) * 1.08)
    ax_zoom.set_ylabel("Site load (MW)")
    ax_zoom.set_xlabel("Illustrative 48-hour window")
    ax_zoom.set_title(
        "b  AI load is reduced during the production peak",
        loc="left",
        fontsize=19,
    )
    ax_zoom.legend(
        handles=[
            Line2D([0], [0], color=AI_DARK, lw=1.4, label="Production-aware schedule"),
            Line2D(
                [0],
                [0],
                color="#6E4B7E",
                lw=1.4,
                ls=(0, (3, 2)),
                label="Schedule optimized without production load",
            ),
        ],
        loc="lower left",
        frameon=False,
        fontsize=12.8,
    )

    # c: direct paired comparison of node-level incremental peaks.
    nodes = sorted(msg.factory_id.unique())
    base_peaks = msg.groupby("factory_id").base_load_mw.max().loc[nodes]
    fixed_peaks = msg_no_routing.groupby("factory_id").grid_import_mw.max().loc[nodes]
    coordinated_peaks = msg.groupby("factory_id").grid_import_mw.max().loc[nodes]
    fixed_increment = (fixed_peaks - base_peaks).clip(lower=0)
    coordinated_increment = (coordinated_peaks - base_peaks).clip(lower=0)
    y = np.arange(len(nodes), dtype=float)
    for ypos, fixed, coordinated in zip(y, fixed_increment, coordinated_increment):
        ax_space.annotate(
            "",
            xy=(coordinated, ypos),
            xytext=(fixed, ypos),
            arrowprops={
                "arrowstyle": "-|>",
                "color": "#7A858B",
                "lw": 1.5,
                "mutation_scale": 10,
                "shrinkA": 5,
                "shrinkB": 5,
            },
            zorder=1,
        )
    ax_space.scatter(
        fixed_increment,
        y,
        s=78,
        color="#F1B78E",
        edgecolor=AI_DARK,
        linewidth=0.8,
        label="Before routing",
        zorder=3,
    )
    ax_space.scatter(
        coordinated_increment,
        y,
        s=78,
        color=AI,
        edgecolor="white",
        linewidth=0.8,
        label="After routing",
        zorder=4,
    )
    ax_space.set_yticks(y, nodes)
    ax_space.invert_yaxis()
    ax_space.set_ylabel("Multi-site node")
    ax_space.set_xlabel("Additional capacity (MW)")
    ax_space.set_xlim(-0.08, max(fixed_increment) * 1.18)
    ax_space.grid(axis="x", color="#D8DDE1", lw=0.7, alpha=0.75)
    ax_space.set_title(
        "c  Routing reduces the added peak at every node",
        loc="left",
        fontsize=19,
    )
    ax_space.legend(
        loc="lower right",
        ncol=2,
        frameon=False,
        fontsize=12.8,
        columnspacing=1.1,
    )

    # d: one objectively selected hour, comparing fixed allocation and coordination.
    snapshot_hour, avoided = choose_snapshot_hour(msg, msg_no_routing)
    coordinated_hour = msg[msg.hour.eq(snapshot_hour)].set_index("factory_id").loc[nodes]
    no_routing_hour = msg_no_routing[msg_no_routing.hour.eq(snapshot_hour)].set_index("factory_id").loc[nodes]
    peaks = msg.groupby("factory_id").base_load_mw.max().loc[nodes]
    production_fraction = coordinated_hour.base_load_mw.to_numpy() / peaks.to_numpy()
    no_ai_fraction = no_routing_hour.ai_facility_power_mw.to_numpy() / peaks.to_numpy()
    co_ai_fraction = coordinated_hour.ai_facility_power_mw.to_numpy() / peaks.to_numpy()
    x = np.arange(len(nodes), dtype=float)
    width = 0.27
    pair_offset = 0.18
    ax_snapshot.bar(x - pair_offset, production_fraction * 100, width, color=PRODUCTION, edgecolor="white", lw=0.5)
    ax_snapshot.bar(
        x - pair_offset,
        no_ai_fraction * 100,
        width,
        bottom=production_fraction * 100,
        color="#F1B78E",
        edgecolor="white",
        lw=0.5,
        label="AI: fixed node allocation",
    )
    ax_snapshot.bar(x + pair_offset, production_fraction * 100, width, color=PRODUCTION, edgecolor="white", lw=0.5)
    ax_snapshot.bar(
        x + pair_offset,
        co_ai_fraction * 100,
        width,
        bottom=production_fraction * 100,
        color=AI,
        edgecolor="white",
        lw=0.5,
        label="AI: coordinated routing",
    )
    for xpos, prod, ai in zip(x - pair_offset, production_fraction, no_ai_fraction):
        if prod + ai > 1:
            ax_snapshot.bar(
                xpos,
                (prod + ai - 1) * 100,
                width,
                bottom=100,
                color=OVERFLOW,
                edgecolor="none",
                zorder=4,
            )
    for xpos, prod, ai in zip(x + pair_offset, production_fraction, co_ai_fraction):
        if prod + ai > 1:
            ax_snapshot.bar(
                xpos,
                (prod + ai - 1) * 100,
                width,
                bottom=100,
                color=OVERFLOW,
                edgecolor="none",
                zorder=4,
            )
    ax_snapshot.axhline(100, color=ENVELOPE, lw=1.4, ls=(0, (5, 3)))
    ax_snapshot.set_xticks(x, nodes)
    ax_snapshot.set_ylabel("Site load / pre-AI peak (%)")
    ax_snapshot.set_ylim(0, 114)
    ax_snapshot.grid(axis="y", color="#D8DDE1", lw=0.7, alpha=0.65)
    ax_snapshot.set_title(
        "d  AI load before and after routing",
        loc="left",
        fontsize=19,
    )
    ax_snapshot.legend(
        handles=[
            Patch(facecolor=PRODUCTION, label="Production"),
            Patch(facecolor="#F1B78E", label="Before routing (left)"),
            Patch(facecolor=AI, label="After routing (right)"),
            Patch(facecolor=OVERFLOW, label="Above pre-AI peak"),
        ],
        loc="lower left",
        ncol=2,
        frameon=False,
        fontsize=12.8,
        columnspacing=1.0,
    )
    fig.subplots_adjust(left=0.065, right=0.985, top=0.96, bottom=0.08)

    out_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_stem.with_suffix(".png"), dpi=220, bbox_inches="tight")
    fig.savefig(out_stem.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(out_stem.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)
    print(out_stem.with_suffix(".png"))


if __name__ == "__main__":
    main()
