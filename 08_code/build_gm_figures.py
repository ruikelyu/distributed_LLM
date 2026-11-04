#!/usr/bin/env python3
"""Build the architecture schematic and the site-distribution figure of the GM paper.

Purpose: Render Fig. 1 (four deployment architectures as schematic cards) and
Fig. 3 (distribution of sites by additional capacity) of the IEEE PES GM
paper as separate single-column figures.
Workflow status: Active GM-paper figure script; reuses the card drawing of
`build_figure3_rq1_grid_capacity.py`.
Scientific boundary: Fig. 1 is a schematic and carries no data. Fig. 3 shows
the share of modeled sites per capacity bin for the three factory-based
architectures under the same registered site weights as the grid-capacity
figure, next to the Epoch AI records of reported AI data centers as an
international scale reference. The LDC aggregate is not one site.
Inputs: `config/scenarios/figure3_rq1_grid_capacity_v2.yaml` (architecture order,
colors, panel labels) and `figure3_grid_capacity_data.csv` (panel
`node_scale_distribution`), written by `build_figure3_rq1_grid_capacity.py`.
Outputs: `gm_architectures.{pdf,png}` and `gm_site_distribution.{pdf,png}`.
Key assumptions: The paper names the architectures PFD, HFD, MSD and LDC; these
labels replace the data-file labels PF, SHG, MSG and LDC_AGGREGATE in the plots.
Explicit exclusions: National capacity totals (reported in a table in the paper).
Validation/tests: Every architecture and capacity bin must be present in the
figure data, and the site shares of each architecture must sum to one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "08_code"))

import build_figure3_rq1_grid_capacity as grid_figure  # noqa: E402

DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/figure3_rq1_grid_capacity_v2.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "05_results/v1.0.0/result/manuscript_figures"
DATA_FILE = "figure3_grid_capacity_data.csv"

ARCHITECTURE_LABELS = {
    "LDC_AGGREGATE": "Large data center (LDC)",
    "PF": "Per-factory (PFD)",
    "SHG": "Host-factory (HFD)",
    "MSG": "Multi-site (MSD)",
}
SITE_LABELS = {"PF": "PFD", "SHG": "HFD", "MSG": "MSD"}
CARD_MODES = {"LDC_AGGREGATE": "ldc", "PF": "pf", "SHG": "shg", "MSG": "msg"}
CAPACITY_BINS = [
    ("exact_zero", "0"),
    ("positive_below_0p1_mw", "<0.1"),
    ("0p1_to_1_mw", "0.1–1"),
    ("1_to_10_mw", "1–10"),
    ("10_to_100_mw", "10–100"),
    ("100_to_1000_mw", "100–1k"),
    ("1000_to_10000_mw", "1k–10k"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--data", type=Path, help=f"Figure data CSV (default: <output-dir>/{DATA_FILE}).")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def draw_architectures(config: dict, output_dir: Path) -> None:
    """Four architecture cards in a 2 x 2 grid, drawn large and scaled down in LaTeX."""
    panel = config["architecture_panel"]
    colors = config["aggregate_panel"]["colors"]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 3.3))
    for ax, key in zip(axes.flat, panel["order"]):
        grid_figure._architecture_card(ax, key, ARCHITECTURE_LABELS[key], CARD_MODES[key], colors[key])
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01, wspace=0.06, hspace=0.10)
    fig.savefig(output_dir / "gm_architectures.pdf")
    fig.savefig(output_dir / "gm_architectures.png", dpi=200)
    plt.close(fig)


def draw_site_distribution(config: dict, data: pd.DataFrame, output_dir: Path) -> None:
    """Grouped bars of the share of sites per capacity bin for PFD, HFD and MSD."""
    plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7.5,
                         "ytick.labelsize": 7.5, "axes.linewidth": 0.6})
    nodes = data[data["panel"].eq("node_scale_distribution")]
    series = list(config["node_panels"]["order"])
    colors = config["node_panels"]["colors"]
    labels = {**config["node_panels"]["labels"], **SITE_LABELS}
    x = np.arange(len(CAPACITY_BINS))
    width = 0.2
    offsets = np.array([-1.5, -0.5, 0.5, 1.5]) * width
    shares = {}
    for key in series:
        values = []
        for bin_id, _ in CAPACITY_BINS:
            row = nodes[nodes["series"].eq(key) & nodes["category_id"].eq(bin_id)]
            if len(row) != 1:
                raise ValueError(f"Expected one row for series {key}, bin {bin_id}; found {len(row)}")
            values.append(float(row["value"].iloc[0]) * 100)
        shares[key] = np.array(values)
        if not np.isclose(shares[key].sum(), 100.0, atol=1e-6):
            raise ValueError(f"Site shares of {key} sum to {shares[key].sum():.6f} percent, not 100")

    fig, ax = plt.subplots(figsize=(3.5, 1.9))
    for offset, key in zip(offsets, series):
        nonzero = shares[key] > 0
        ax.bar((x + offset)[nonzero], shares[key][nonzero], width=width, color=colors[key],
               label=labels[key], zorder=3, edgecolor="white", linewidth=0.3)
    ax.set_xticks(x, [label for _, label in CAPACITY_BINS])
    ax.set_xlabel("Additional capacity per site (MW)")
    ax.set_ylabel("Share of sites (%)")
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 20, 40, 60, 80])
    ax.grid(axis="y", color="#E1E5E7", linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper center", ncol=2, frameon=False, fontsize=7, handlelength=1.0,
              columnspacing=0.8, bbox_to_anchor=(0.5, 1.02))
    fig.savefig(output_dir / "gm_site_distribution.pdf", bbox_inches="tight")
    fig.savefig(output_dir / "gm_site_distribution.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    data_path = args.data or output_dir / DATA_FILE
    if not data_path.is_absolute():
        data_path = PROJECT_ROOT / data_path
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    data = pd.read_csv(data_path, encoding="utf-8-sig")
    output_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({"font.sans-serif": ["Arial", "DejaVu Sans"], "pdf.fonttype": 42, "svg.fonttype": "none"})
    draw_architectures(config, output_dir)
    draw_site_distribution(config, data, output_dir)
    for name in ("gm_architectures", "gm_site_distribution"):
        print(f"Wrote {output_dir / name}.pdf and .png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
