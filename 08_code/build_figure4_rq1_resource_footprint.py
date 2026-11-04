#!/usr/bin/env python3
"""Build the author-approved RQ1 conditional-resource Figure 4.

Purpose: Render PF and equal-service LDC water, central facility-floor, and
off-site-land scenario calculations from the approved standard result table.
Workflow status: Active YAML-versioned Figure 4 postprocessor.
Scientific boundary: Panels show registered cooling and siting scenarios, not
architecture-only causal effects or observed national resource footprints.
Inputs: Author-approved RQ1 resource summary and its hash-bearing approval marker.
Outputs: Figure-data CSV, SVG, PNG, PDF, and a hashed validation marker.
Key assumptions: The floor panel uses only the author-selected central PF case;
the LDC floor and land values are greenfield project-screening proxies.
Explicit exclusions: PF new-building estimates, compact/spacious display cases,
SHG/MSG, construction materials, withdrawal/consumption separation, and PUE changes.
Validation/tests: YAML-derived version and paths, approval status, input hashes,
exact panel and architecture coverage, units, central-floor selection, zero-land
boundary labelling, rendered-output hashes, and visual inspection.
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
import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/figure4_rq1_resource_footprint_v1.yaml"


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
) -> tuple[dict[str, Any], str, Path, pd.DataFrame, dict[str, Any], dict[str, Path]]:
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("Figure 4 schema_version must equal 1")
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    results_root = project_path(defaults["paths"]["results_root"])
    summary_config_path = project_path(settings["resource_summary_config"])
    summary_settings = yaml.safe_load(summary_config_path.read_text(encoding="utf-8"))
    summary_root = results_root / model_version / summary_settings["outputs"]["subdirectory"]
    summary_path = summary_root / summary_settings["outputs"]["summary_table"]
    field_status_path = summary_root / summary_settings["outputs"]["field_status_table"]
    approval_path = summary_root / summary_settings["outputs"]["validation"]
    paths = {
        "configuration": config_path,
        "figure_script": PROJECT_ROOT / "08_code/build_figure4_rq1_resource_footprint.py",
        "defaults": defaults_path,
        "resource_summary_configuration": summary_config_path,
        "resource_summary": summary_path,
        "field_status": field_status_path,
        "approval_marker": approval_path,
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing approved Figure 4 input: " + ", ".join(missing))
    marker = json.loads(approval_path.read_text(encoding="utf-8"))
    if marker.get("status") != settings["required_interpretation_status"]:
        raise ValueError("RQ1 resource interpretation is not approved for Figure 4")
    if marker.get("author_approval", {}).get("status") != "approved":
        raise ValueError("RQ1 resource approval metadata is missing")
    if marker.get("figure_authorization") is not True:
        raise ValueError("RQ1 resource marker does not authorize a figure")
    if marker.get("automatic_manuscript_edit") is not False:
        raise ValueError("RQ1 resource marker permits automatic manuscript edits")
    if marker.get("model_version") != model_version:
        raise ValueError("RQ1 resource marker model_version differs from defaults YAML")
    marker_outputs = marker.get("outputs", {})
    if marker_outputs.get("summary_table", {}).get("sha256") != sha256(summary_path):
        raise ValueError("resource summary hash differs from its approval marker")
    if marker_outputs.get("field_status_table", {}).get("sha256") != sha256(
        field_status_path
    ):
        raise ValueError("resource field-status hash differs from its approval marker")
    return (
        settings,
        model_version,
        results_root,
        pd.read_csv(summary_path, encoding="utf-8-sig"),
        marker,
        paths,
    )


def validate_and_prepare(
    settings: dict[str, Any], model_version: str, summary: pd.DataFrame
) -> pd.DataFrame:
    architectures = [str(value) for value in settings["architectures"]]
    rows: list[pd.DataFrame] = []
    for order, panel in enumerate(settings["panels"]):
        selected = summary[
            summary["metric_id"].eq(panel["id"])
            & summary["sensitivity_case"].eq(panel["sensitivity_case"])
        ].copy()
        if len(selected) != 2 or set(selected["architecture"]) != set(architectures):
            raise ValueError(f"{panel['id']}: Figure 4 lacks exact PF/LDC coverage")
        if set(selected["model_version"].astype(str)) != {model_version}:
            raise ValueError(f"{panel['id']}: model_version differs from defaults")
        if not selected["equal_effective_service_verified"].astype(bool).all():
            raise ValueError(f"{panel['id']}: equal-service status is missing")
        if not selected["author_approved_for_later_manuscript_migration"].astype(bool).all():
            raise ValueError(f"{panel['id']}: author approval is missing")
        if selected["automatic_manuscript_edit"].astype(bool).any():
            raise ValueError(f"{panel['id']}: automatic manuscript edit is enabled")
        selected["panel_order"] = order
        selected["panel_title"] = panel["title"]
        selected["plot_value"] = selected["value"] * float(panel["unit_scale"])
        selected["plot_unit"] = panel["axis_label"]
        selected["row_label"] = selected["architecture"].map(panel["row_labels"])
        selected["architecture_order"] = selected["architecture"].map(
            {name: i for i, name in enumerate(architectures)}
        )
        rows.append(selected)
    data = pd.concat(rows, ignore_index=True)
    if len(data) != 6 or data["plot_value"].isna().any():
        raise ValueError("Figure 4 requires six finite plotting rows")
    if (data["plot_value"] < 0).any() or not np.isfinite(data["plot_value"]).all():
        raise ValueError("Figure 4 contains invalid plotting values")
    floor = data[data["metric_id"].eq("total_facility_floor_requirement")]
    if set(floor["sensitivity_case"]) != {"central"}:
        raise ValueError("Figure 4 facility floor must use only the central case")
    land_pf = data[
        data["metric_id"].eq("offsite_land_conversion")
        & data["architecture"].eq("PF")
    ].iloc[0]
    if float(land_pf["value"]) != 0.0 or "boundary" not in str(land_pf["boundary"]):
        raise ValueError("PF zero land must remain explicitly boundary-defined")
    return data.sort_values(["panel_order", "architecture_order"]).reset_index(drop=True)


def plot(settings: dict[str, Any], data: pd.DataFrame, outputs: dict[str, Path]) -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "font.size": 10.5,
        }
    )
    fig, axes = plt.subplots(
        1,
        3,
        figsize=(
            float(settings["figure"]["width_inches"]),
            float(settings["figure"]["height_inches"]),
        ),
    )
    architectures = [str(value) for value in settings["architectures"]]
    for axis, panel in zip(axes, settings["panels"]):
        subset = data[data["metric_id"].eq(panel["id"])].sort_values(
            "architecture_order"
        )
        y = np.arange(len(subset))
        colors = [settings["colors"][name] for name in subset["architecture"]]
        bars = axis.barh(y, subset["plot_value"], color=colors, height=0.58)
        axis.set_yticks(y, subset["row_label"])
        axis.invert_yaxis()
        axis.set_xlabel(panel["axis_label"])
        axis.set_title(
            panel["title"], loc="left", fontweight="bold", fontsize=11, pad=24
        )
        axis.text(
            0,
            1.015,
            panel["subtitle"],
            transform=axis.transAxes,
            ha="left",
            va="bottom",
            fontsize=8.8,
            color="#555555",
        )
        axis.grid(axis="x", color="#D8DDE1", linewidth=0.8, alpha=0.75)
        axis.set_axisbelow(True)
        maximum = max(float(subset["plot_value"].max()), 0.01)
        axis.set_xlim(0, maximum * 1.30)
        for bar, row in zip(bars, subset.itertuples(index=False)):
            label = f"{row.plot_value:.3f}"
            if panel["id"] == "offsite_land_conversion" and row.architecture == "PF":
                label = "0 · boundary"
            axis.text(
                row.plot_value + maximum * 0.035,
                bar.get_y() + bar.get_height() / 2,
                label,
                va="center",
                fontsize=9.5,
                color="#303030",
            )
        for side in ["top", "right"]:
            axis.spines[side].set_visible(False)
        if list(subset["architecture"]) != architectures:
            raise ValueError("Figure 4 architecture order changed unexpectedly")
    fig.text(
        0.5,
        0.02,
        "Registered scenarios, not architecture-only effects. PF land = 0 is an existing-site boundary; LDC floor and land are greenfield project proxies.",
        ha="center",
        fontsize=9.2,
        color="#555555",
    )
    fig.subplots_adjust(left=0.09, right=0.99, top=0.82, bottom=0.20, wspace=0.34)
    for key in ["svg", "png", "pdf"]:
        outputs[key].parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outputs["svg"], bbox_inches="tight")
    fig.savefig(outputs["png"], dpi=int(settings["figure"]["png_dpi"]), bbox_inches="tight")
    fig.savefig(outputs["pdf"], bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings, model_version, results_root, summary, approval, paths = load_inputs(
        config_path
    )
    data = validate_and_prepare(settings, model_version, summary)
    output_config = settings["outputs"]
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else results_root / model_version / output_config["subdirectory"]
    )
    outputs = {
        key: output_root / output_config[key]
        for key in ["data", "svg", "png", "pdf", "validation"]
    }
    if args.check_only:
        print(
            json.dumps(
                {
                    "status": "ready_to_render",
                    "model_version": model_version,
                    "figure_version": settings["figure_version"],
                    "rows": len(data),
                    "floor_case": "central",
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
        "status": "validated_author_approved_RQ1_resource_figure",
        "model_version": model_version,
        "figure_version": settings["figure_version"],
        "interpretation_status": approval["status"],
        "author_approval": approval["author_approval"],
        "selected_floor_case": approval["selected_floor_case"],
        "inputs": {
            key: {"path": display_path(path), "sha256": sha256(path)}
            for key, path in paths.items()
        },
        "outputs": {
            key: {"path": display_path(path), "sha256": sha256(path)}
            for key, path in outputs.items()
            if key != "validation"
        },
        "panels": [panel["id"] for panel in settings["panels"]],
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
