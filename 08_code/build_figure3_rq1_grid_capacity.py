#!/usr/bin/env python3
"""Build the author-approved RQ1 grid-capacity Figure 3.

Purpose: Render national equal-service additional-interconnection requirements
and separately bounded node-scale capacity distributions.
Workflow status: Active YAML-versioned Figure 3 postprocessor.
Scientific boundary: The LDC aggregate is a logical national capacity portfolio,
not one site; Epoch records are an international facility/campus scale reference,
not a China-specific or equal-service LDC distribution.
Inputs: Author-approved RQ1 aggregate and node summaries plus their approval marker.
Outputs: Figure-data CSV, SVG, PNG, PDF, and a hashed validation marker.
Key assumptions: Modeled-node proportions use registered representative weights;
all node panels use the same coarse capacity bins.
Explicit exclusions: Grid equipment, investment, projects, schedules, maximum-node,
percentile, Top-k, HHI, effective-node-count, water, floor, and land claims.
Validation/tests: YAML-derived version and paths, approval status, input hashes,
architecture and bin coverage, probability sums, and rendered-output hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

os.environ["MPLCONFIGDIR"] = str(Path(tempfile.gettempdir()) / "dllm_matplotlib")
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "dllm_cache"))

import matplotlib.pyplot as plt
from matplotlib import patches
import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/figure3_rq1_grid_capacity_v2.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_inputs(
    config_path: Path,
) -> tuple[dict[str, Any], str, Path, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("Figure 3 schema_version must equal 1")
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    results_root = project_path(defaults["paths"]["results_root"])
    rq1_config_path = project_path(settings["rq1_interpretation_config"])
    rq1 = yaml.safe_load(rq1_config_path.read_text(encoding="utf-8"))
    rq1_root = results_root / model_version / rq1["outputs"]["subdirectory"]
    aggregate_path = rq1_root / rq1["outputs"]["aggregate_summary"]
    node_path = rq1_root / rq1["outputs"]["node_scale_summary"]
    approval_path = rq1_root / rq1["outputs"]["validation"]
    missing = [
        str(path)
        for path in [aggregate_path, node_path, approval_path]
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError("missing approved RQ1 figure input: " + ", ".join(missing))
    marker = json.loads(approval_path.read_text(encoding="utf-8"))
    if marker.get("status") != settings["required_interpretation_status"]:
        raise ValueError("RQ1 interpretation has not been approved for Figure 3")
    if marker.get("author_approval", {}).get("status") != "approved":
        raise ValueError("RQ1 author-approval metadata is missing")
    if marker.get("model_version") != model_version:
        raise ValueError("RQ1 approval marker model_version differs from defaults YAML")
    marker_outputs = marker.get("outputs", {})
    if marker_outputs.get("aggregate_summary", {}).get("sha256") != sha256(aggregate_path):
        raise ValueError("RQ1 aggregate summary hash differs from approval marker")
    if marker_outputs.get("node_scale_summary", {}).get("sha256") != sha256(node_path):
        raise ValueError("RQ1 node-scale summary hash differs from approval marker")
    aggregate = pd.read_csv(aggregate_path, encoding="utf-8-sig")
    nodes = pd.read_csv(node_path, encoding="utf-8-sig")
    paths = {
        "configuration": config_path,
        "defaults": defaults_path,
        "rq1_configuration": rq1_config_path,
        "aggregate_summary": aggregate_path,
        "node_scale_summary": node_path,
        "approval_marker": approval_path,
    }
    return settings, model_version, results_root, aggregate, nodes, {"paths": paths, "marker": marker}


def validate_and_prepare(
    settings: dict[str, Any], model_version: str, aggregate: pd.DataFrame, nodes: pd.DataFrame
) -> pd.DataFrame:
    formal = ["PF", "SHG", "MSG"]
    if len(aggregate) != 3 or set(aggregate["scenario"].astype(str)) != set(formal):
        raise ValueError("Figure 3 aggregate input requires exact PF/SHG/MSG coverage")
    if set(aggregate["model_version"].astype(str)) != {model_version}:
        raise ValueError("Figure 3 aggregate model_version is invalid")
    if not aggregate["equal_service_verified"].astype(bool).all():
        raise ValueError("Figure 3 aggregate comparison is not equal-service")
    if aggregate["centralized_capacity_is_one_physical_site"].astype(bool).any():
        raise ValueError("Figure 3 input permits a one-site LDC interpretation")
    ldc_values = aggregate["ldc_aggregate_incremental_grid_expansion_mw"].unique()
    if len(ldc_values) != 1 or float(ldc_values[0]) <= 0:
        raise ValueError("Figure 3 requires one positive LDC aggregate comparator")

    node_order = [str(value) for value in settings["node_panels"]["order"]]
    expected_bins = list(range(7))
    grouped = nodes.groupby("architecture", sort=False)
    if set(grouped.groups) != set(node_order):
        raise ValueError("Figure 3 node input lacks an expected distribution")
    for architecture, group in grouped:
        if sorted(group["bin_order"].astype(int).tolist()) != expected_bins:
            raise ValueError(f"{architecture}: Figure 3 requires seven ordered bins")
        if not np.isclose(group["node_proportion"].sum(), 1.0, rtol=0, atol=1e-12):
            raise ValueError(f"{architecture}: node proportions do not sum to one")
    bin_labels = (
        nodes[["bin_order", "coarse_bin_label"]]
        .drop_duplicates()
        .sort_values("bin_order")
    )
    if len(bin_labels) != 7 or bin_labels["bin_order"].tolist() != expected_bins:
        raise ValueError("Figure 3 distributions do not share seven common bins")

    aggregate_rows: list[dict[str, Any]] = []
    indexed = aggregate.set_index("scenario")
    ldc = float(ldc_values[0])
    for order, architecture in enumerate(settings["aggregate_panel"]["order"]):
        if architecture == "LDC_AGGREGATE":
            value = ldc
            difference = 0.0
            fraction = 0.0
        else:
            row = indexed.loc[architecture]
            value = float(row["architecture_national_incremental_grid_expansion_mw"])
            difference = float(row["capacity_difference_vs_ldc_aggregate_mw"])
            fraction = float(row["capacity_difference_vs_ldc_aggregate_fraction"])
        aggregate_rows.append(
            {
                "model_version": model_version,
                "panel": "aggregate_capacity",
                "series": architecture,
                "series_label": settings["aggregate_panel"]["labels"][architecture],
                "category_order": order,
                "category_id": architecture,
                "category_label": settings["aggregate_panel"]["labels"][architecture],
                "value": value,
                "unit": "MW",
                "reference_value": ldc,
                "difference_vs_reference_mw": difference,
                "difference_vs_reference_fraction": fraction,
                "population_kind": "national_equal_service_architecture",
                "statistical_unit": "logical_national_capacity_portfolio",
                "claim_boundary": "aggregate_equal_service_screen_not_one_physical_LDC_site",
            }
        )
    node_rows = nodes.copy()
    node_rows["panel"] = "node_scale_distribution"
    node_rows["series"] = node_rows["architecture"]
    node_rows["series_label"] = node_rows["architecture"].map(
        settings["node_panels"]["labels"]
    )
    node_rows["category_order"] = node_rows["bin_order"]
    node_rows["category_id"] = node_rows["coarse_bin_id"]
    node_rows["category_label"] = node_rows["coarse_bin_label"]
    node_rows["value"] = node_rows["node_proportion"]
    node_rows["unit"] = "node_proportion"
    node_rows["reference_value"] = np.nan
    node_rows["difference_vs_reference_mw"] = np.nan
    node_rows["difference_vs_reference_fraction"] = np.nan
    columns = list(pd.DataFrame(aggregate_rows).columns)
    return pd.concat(
        [pd.DataFrame(aggregate_rows)[columns], node_rows[columns]], ignore_index=True
    )


def _factory_glyph(
    ax: plt.Axes,
    x: float,
    y: float,
    color: str,
    server: bool,
    server_scale: float = 1.0,
) -> None:
    ax.add_patch(
        patches.Rectangle(
            (x, y), 0.14, 0.20, transform=ax.transAxes,
            facecolor="#F7F8F9", edgecolor="#606970", linewidth=0.9,
        )
    )
    roof = patches.Polygon(
        [
            [x, y + 0.20],
            [x + 0.045, y + 0.27],
            [x + 0.09, y + 0.20],
            [x + 0.135, y + 0.27],
            [x + 0.14, y + 0.20],
        ],
        closed=False,
        transform=ax.transAxes,
        color="#606970",
        linewidth=0.9,
    )
    ax.add_patch(roof)
    ax.add_patch(
        patches.Rectangle(
            (x + 0.105, y + 0.20), 0.018, 0.105,
            transform=ax.transAxes, facecolor="#DDE1E4",
            edgecolor="#606970", linewidth=0.7,
        )
    )
    if not server:
        return
    server_width = 0.050 * server_scale
    server_height = 0.105 * server_scale
    server_x = x + 0.070 - server_width / 2
    server_y = y + 0.045 - (server_height - 0.105) / 2
    ax.add_patch(
        patches.FancyBboxPatch(
            (server_x, server_y),
            server_width,
            server_height,
            boxstyle="round,pad=0.003,rounding_size=0.005",
            transform=ax.transAxes,
            facecolor=color,
            edgecolor="white",
            linewidth=0.6,
        )
    )
    for fraction in [0.27, 0.55, 0.81]:
        ax.plot(
            [server_x + server_width * 0.15, server_x + server_width * 0.85],
            [server_y + server_height * fraction] * 2,
            transform=ax.transAxes,
            color="white",
            linewidth=0.55,
        )


def _data_center_glyph(ax: plt.Axes, x: float, y: float, color: str) -> None:
    ax.add_patch(
        patches.FancyBboxPatch(
            (x, y), 0.25, 0.26,
            boxstyle="round,pad=0.012,rounding_size=0.015",
            transform=ax.transAxes,
            facecolor="#F4F5F6",
            edgecolor="#606970",
            linewidth=0.9,
        )
    )
    for index in range(3):
        rack_x = x + 0.035 + index * 0.065
        ax.add_patch(
            patches.Rectangle(
                (rack_x, y + 0.045), 0.045, 0.17,
                transform=ax.transAxes, facecolor=color,
                edgecolor="white", linewidth=0.5,
            )
        )
        for row in range(4):
            ax.plot(
                [rack_x + 0.007, rack_x + 0.038],
                [y + 0.072 + row * 0.034] * 2,
                transform=ax.transAxes,
                color="white",
                linewidth=0.45,
            )


def _architecture_card(
    ax: plt.Axes,
    key: str,
    title: str,
    mode: str,
    color: str,
) -> None:
    ax.set_axis_off()
    ax.add_patch(
        patches.FancyBboxPatch(
            (0.01, 0.03), 0.98, 0.91,
            boxstyle="round,pad=0.014,rounding_size=0.025",
            transform=ax.transAxes,
            facecolor="white",
            edgecolor="#D7DCE0",
            linewidth=0.8,
        )
    )
    ax.add_patch(
        patches.Rectangle(
            (0.01, 0.88), 0.98, 0.07,
            transform=ax.transAxes, facecolor=color, edgecolor="none",
        )
    )
    display_title = title
    title_size = 14.5 if key == "LDC_AGGREGATE" else 15.5
    ax.text(
        0.05, 0.78, display_title,
        transform=ax.transAxes, fontweight="bold", fontsize=title_size,
        color="#20262A", va="top",
    )
    if mode == "ldc":
        _data_center_glyph(ax, 0.37, 0.20, color)
        return
    x_positions = [0.18, 0.43, 0.68]
    if mode in {"shg", "msg"}:
        ax.plot(
            [0.25, 0.75], [0.18, 0.18],
            transform=ax.transAxes, color="#9FA7AC", linewidth=1.0, zorder=0,
        )
    for index, x_position in enumerate(x_positions):
        has_server = mode in {"pf", "msg"} or (mode == "shg" and index == 1)
        server_scale = 1.38 if mode == "shg" and index == 1 else 1.0
        _factory_glyph(ax, x_position, 0.18, color, has_server, server_scale)
    if mode == "shg":
        for start in [0.25, 0.75]:
            ax.annotate(
                "", xy=(0.50, 0.20), xytext=(start, 0.20),
                xycoords=ax.transAxes,
                arrowprops={"arrowstyle": "->", "color": color, "lw": 1.0},
            )
        ax.text(
            0.50, 0.085, "AI service assignment",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=11.5, color="#5A6369",
        )
    elif mode == "msg":
        for start, end in [(0.25, 0.50), (0.50, 0.75), (0.75, 0.25)]:
            ax.annotate(
                "", xy=(end, 0.20), xytext=(start, 0.20),
                xycoords=ax.transAxes,
                arrowprops={
                    "arrowstyle": "->",
                    "color": color,
                    "lw": 0.85,
                    "connectionstyle": "arc3,rad=0.12",
                },
            )
        ax.text(
            0.50, 0.085, "Cross-site AI service routing",
            transform=ax.transAxes, ha="center", va="center",
            fontsize=11.5, color="#5A6369",
        )


def plot(settings: dict[str, Any], data: pd.DataFrame, outputs: dict[str, Path]) -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 15,
            "axes.titlesize": 18,
            "axes.labelsize": 15,
            "axes.linewidth": 0.8,
            "xtick.labelsize": 13,
            "ytick.labelsize": 13.5,
        }
    )
    fig = plt.figure(
        figsize=(
            float(settings["figure"]["width_inches"]),
            float(settings["figure"]["height_inches"]),
        )
    )
    grid = fig.add_gridspec(
        2, 2,
        height_ratios=[0.80, 2.25],
        width_ratios=[1.28, 1.0],
        hspace=0.25,
        wspace=0.26,
    )
    architecture_grid = grid[0, :].subgridspec(1, 4, wspace=0.12)
    modes = {
        "LDC_AGGREGATE": "ldc",
        "PF": "pf",
        "SHG": "shg",
        "MSG": "msg",
    }
    for index, architecture in enumerate(settings["architecture_panel"]["order"]):
        _architecture_card(
            fig.add_subplot(architecture_grid[0, index]),
            architecture,
            settings["architecture_panel"]["labels"][architecture],
            modes[architecture],
            settings["aggregate_panel"]["colors"][architecture],
        )
    fig.text(0.055, 0.955, "a", fontsize=21, fontweight="bold", va="top")
    fig.text(
        0.077, 0.955, "Deployment architectures",
        fontsize=19, fontweight="bold", va="top",
    )

    aggregate_ax = fig.add_subplot(grid[1, 0])
    aggregate = data[data["panel"].eq("aggregate_capacity")].sort_values("category_order")
    colors = [settings["aggregate_panel"]["colors"][item] for item in aggregate["series"]]
    y = np.arange(len(aggregate))
    bars = aggregate_ax.barh(
        y, aggregate["value"], color=colors, height=0.58,
        edgecolor="none", zorder=3,
    )
    aggregate_ax.set_yticks(y, aggregate["series_label"])
    for tick, color in zip(aggregate_ax.get_yticklabels(), colors):
        tick.set_color(color)
        tick.set_fontweight("bold")
    aggregate_ax.invert_yaxis()
    aggregate_ax.set_xlabel("National total (MW)")
    aggregate_ax.set_title(
        "b  Additional grid-interconnection capacity",
        loc="left", fontweight="bold", pad=12,
    )
    aggregate_ax.grid(axis="x", color="#DCE1E4", linewidth=0.8, zorder=0)
    aggregate_ax.set_axisbelow(True)
    aggregate_ax.spines[["top", "right", "left"]].set_visible(False)
    aggregate_ax.tick_params(axis="y", length=0, pad=8)
    maximum = float(aggregate["value"].max())
    aggregate_ax.set_xlim(0, 1780)
    aggregate_ax.set_xticks(np.arange(0, 1751, 250))
    for bar, row in zip(bars, aggregate.itertuples(index=False)):
        label = f"{row.value:,.0f} MW"
        if row.series != "LDC_AGGREGATE":
            label += f"   (-{100 * row.difference_vs_reference_fraction:.0f}% vs LDC)"
        aggregate_ax.text(
            row.value + 30,
            bar.get_y() + bar.get_height() / 2,
            label,
            va="center",
            ha="left",
            fontsize=14,
            fontweight="bold",
            color="#2B3338",
        )

    node_ax = fig.add_subplot(grid[1, 1])
    node_data = data[data["panel"].eq("node_scale_distribution")]
    bin_order = [
        ("exact_zero", "0 MW"),
        ("positive_below_0p1_mw", "<0.1"),
        ("0p1_to_1_mw", "0.1-1"),
        ("1_to_10_mw", "1-10"),
        ("10_to_100_mw", "10-100"),
        ("100_to_1000_mw", "100-1,000"),
        ("1000_to_10000_mw", "1,000-10,000"),
    ]
    x = np.arange(len(bin_order))
    bar_width = 0.19
    offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * bar_width
    for offset, series in zip(offsets, settings["node_panels"]["order"]):
        values = np.array(
            [
                float(
                    node_data[
                        node_data["series"].eq(series)
                        & node_data["category_id"].eq(bin_id)
                    ]["value"].iloc[0]
                )
                * 100
                for bin_id, _ in bin_order
            ]
        )
        nonzero = values > 0
        bars = node_ax.bar(
            (x + offset)[nonzero],
            values[nonzero],
            width=bar_width,
            color=settings["node_panels"]["colors"][series],
            edgecolor="white",
            linewidth=0.6,
            label=settings["node_panels"]["labels"][series],
            zorder=3,
        )
        for bar, value in zip(bars, values[nonzero]):
            node_ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 1.0,
                f"{value:.1f}",
                ha="center",
                va="bottom",
                fontsize=10,
                color="#3E474C",
                rotation=90,
                zorder=5,
            )
    node_ax.set_xlim(-0.55, len(bin_order) - 0.45)
    node_ax.set_ylim(0, float(settings["figure"]["node_y_max"]) * 100)
    node_ax.set_xticks(
        x, [label for _, label in bin_order], rotation=26, ha="right"
    )
    node_ax.set_yticks([0, 20, 40, 60, 80], ["0%", "20%", "40%", "60%", "80%"])
    node_ax.spines[["top", "right"]].set_visible(False)
    node_ax.grid(axis="y", color="#E1E5E7", linewidth=0.7, zorder=0)
    node_ax.set_axisbelow(True)
    node_ax.set_xlabel("Capacity bin (MW)")
    node_ax.set_ylabel("Share (%)")
    node_ax.set_title(
        "c  Distribution of site-level capacity",
        loc="left", fontweight="bold", pad=12,
    )
    node_ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, 1.0), ncol=2,
        frameon=False, fontsize=10.5, handlelength=1.25, columnspacing=0.8,
    )

    fig.subplots_adjust(left=0.07, right=0.975, top=0.91, bottom=0.09)
    for key in ["svg", "png", "pdf"]:
        outputs[key].parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outputs["svg"], bbox_inches="tight")
    fig.savefig(outputs["png"], dpi=int(settings["figure"]["png_dpi"]), bbox_inches="tight")
    fig.savefig(outputs["pdf"], bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings, model_version, results_root, aggregate, nodes, provenance = load_inputs(
        config_path
    )
    data = validate_and_prepare(settings, model_version, aggregate, nodes)
    outputs_config = settings["outputs"]
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else results_root / model_version / outputs_config["subdirectory"]
    )
    outputs = {
        key: output_root / outputs_config[key]
        for key in ["data", "svg", "png", "pdf", "validation"]
    }
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "ready_to_render",
                    "model_version": model_version,
                    "figure_version": settings["figure_version"],
                    "aggregate_rows": int(data["panel"].eq("aggregate_capacity").sum()),
                    "node_scale_rows": int(data["panel"].eq("node_scale_distribution").sum()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    output_root.mkdir(parents=True, exist_ok=True)
    data.to_csv(outputs["data"], index=False, encoding="utf-8-sig")
    plot(settings, data, outputs)
    marker = {
        "status": "validated_author_approved_RQ1_figure",
        "model_version": model_version,
        "figure_version": settings["figure_version"],
        "interpretation_status": provenance["marker"]["status"],
        "author_approval": provenance["marker"].get("author_approval"),
        "inputs": {
            key: {"path": display_path(path), "sha256": sha256(path)}
            for key, path in provenance["paths"].items()
        },
        "outputs": {
            key: {"path": display_path(path), "sha256": sha256(path)}
            for key, path in outputs.items()
            if key != "validation"
        },
        "panels": {
            "aggregate_capacity": 4,
            "node_scale_distributions": 4,
            "common_bins_per_distribution": 7,
        },
        "claim_boundaries": settings["claim_boundaries"],
        "main_manuscript_updated": False,
    }
    outputs["validation"].write_text(
        json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": marker["status"],
                "model_version": model_version,
                "png": str(outputs["png"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
