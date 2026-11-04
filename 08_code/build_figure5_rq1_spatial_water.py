#!/usr/bin/env python3
"""Build the approved-design RQ1 PF-versus-LDC spatial-water Figure 5.

Purpose: Allocate each architecture's approved national on-site cooling and
humidification water total across 31 provinces and encode Aqueduct 4.0 baseline
water stress independently by color.
Workflow status: Active YAML-versioned solver-free Figure 5 postprocessor.
Scientific boundary: Spatial scenario and prioritization context, not observed
facility siting, real-time stress, or formal water-scarcity LCIA.
Inputs: Approved resource summary, validated PF industry energy, PF and LDC
province proxies, Aqueduct context, lineage, and spatial-readiness audit.
Outputs: Long-form figure data, SVG, PNG, PDF, and hashed validation marker.
Key assumptions: Architecture-specific WUE is uniform across provinces; PF
industry facility-energy shares therefore equal PF industry site-water shares.
Explicit exclusions: Site-specific WUE, provider traffic, 2030 LDC siting,
withdrawal/consumption splitting, score-volume multiplication, and optimization.
Validation/tests: YAML-derived version, upstream approval and hashes, exact
31-province coverage, share and national-total closure, context separation,
output hashes, replay-ready data, and visual inspection.
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
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/figure5_rq1_spatial_water_v1.yaml"

TILES = {
    "xinjiang": (0, 2), "gansu": (1, 2), "inner mongolia": (2, 1), "heilongjiang": (5, 0),
    "jilin": (5, 1), "liaoning": (5, 2), "beijing": (4, 2), "tianjin": (5, 3),
    "hebei": (4, 3), "shanxi": (3, 3), "shaanxi": (2, 3), "ningxia": (1, 3),
    "qinghai": (1, 4), "tibet": (0, 5), "sichuan": (2, 5), "chongqing": (3, 5),
    "henan": (4, 4), "shandong": (5, 4), "jiangsu": (6, 5), "anhui": (5, 5),
    "hubei": (4, 5), "zhejiang": (6, 6), "shanghai": (7, 5), "jiangxi": (5, 6),
    "hunan": (4, 6), "fujian": (6, 7), "guangdong": (5, 7), "guangxi": (4, 7),
    "guizhou": (3, 6), "yunnan": (2, 7), "hainan": (5, 8),
}

ABBREVIATIONS = {
    "anhui": "AH", "beijing": "BJ", "chongqing": "CQ", "fujian": "FJ", "gansu": "GS",
    "guangdong": "GD", "guangxi": "GX", "guizhou": "GZ", "hainan": "HI", "hebei": "HE",
    "heilongjiang": "HL", "henan": "HA", "hubei": "HB", "hunan": "HN", "jiangsu": "JS",
    "jiangxi": "JX", "jilin": "JL", "liaoning": "LN", "inner mongolia": "NM", "ningxia": "NX",
    "qinghai": "QH", "shaanxi": "SN", "shandong": "SD", "shanghai": "SH", "shanxi": "SX",
    "sichuan": "SC", "tianjin": "TJ", "xinjiang": "XJ", "tibet": "XZ", "yunnan": "YN",
    "zhejiang": "ZJ",
}

ADCODE_TO_PROVINCE = {
    110000: "beijing", 120000: "tianjin", 130000: "hebei", 140000: "shanxi",
    150000: "inner mongolia", 210000: "liaoning", 220000: "jilin", 230000: "heilongjiang",
    310000: "shanghai", 320000: "jiangsu", 330000: "zhejiang", 340000: "anhui",
    350000: "fujian", 360000: "jiangxi", 370000: "shandong", 410000: "henan",
    420000: "hubei", 430000: "hunan", 440000: "guangdong", 450000: "guangxi",
    460000: "hainan", 500000: "chongqing", 510000: "sichuan", 520000: "guizhou",
    530000: "yunnan", 540000: "tibet", 610000: "shaanxi", 620000: "gansu",
    630000: "qinghai", 640000: "ningxia", 650000: "xinjiang",
}

PROVINCE_LABELS = {name: name.title() for name in TILES}
PROVINCE_LABELS["inner mongolia"] = "Inner Mongolia"

LABEL_OFFSETS = {
    "gansu": (-28, 8), "ningxia": (5, -15), "inner mongolia": (5, 6),
    "tianjin": (5, 6), "anhui": (5, -13), "guangdong": (5, -12),
    "guizhou": (5, -12), "jiangsu": (5, 6), "zhejiang": (5, -12),
    "shandong": (5, 6), "hubei": (-29, 5), "fujian": (5, -11),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Write the province data table and validation marker without rendering the map "
        "(no province boundary file required).",
    )
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


def load_inputs(config_path: Path, require_map: bool = True) -> tuple[dict[str, Any], str, Path, dict[str, Path], dict[str, Any]]:
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("Figure 5 schema_version must equal 1")
    defaults_path = project_path(settings["defaults_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    results_root = project_path(defaults["paths"]["results_root"])

    resource_config_path = project_path(settings["resource_summary_config"])
    resource_config = yaml.safe_load(resource_config_path.read_text(encoding="utf-8"))
    resource_root = results_root / model_version / resource_config["outputs"]["subdirectory"]
    spatial_config_path = project_path(settings["spatial_audit_config"])
    spatial_config = yaml.safe_load(spatial_config_path.read_text(encoding="utf-8"))
    spatial_root = results_root / model_version / spatial_config["outputs"]["subdirectory"]
    inputs = settings["inputs"]
    paths = {
        "configuration": config_path,
        "figure_script": PROJECT_ROOT / "08_code/build_figure5_rq1_spatial_water.py",
        "defaults": defaults_path,
        "resource_summary_configuration": resource_config_path,
        "resource_summary": resource_root / resource_config["outputs"]["summary_table"],
        "resource_approval": resource_root / resource_config["outputs"]["validation"],
        "spatial_audit_configuration": spatial_config_path,
        "spatial_audit": spatial_root / spatial_config["outputs"]["report_json"],
        "water_stress_source_configuration": project_path(settings["water_stress_source_config"]),
        "core_summary": results_root / model_version / inputs["core_summary_subpath"],
        "core_validation": results_root / model_version / inputs["core_validation_subpath"],
        "pf_allocation": project_path(inputs["pf_allocation"]),
        "pf_allocation_lineage": project_path(inputs["pf_allocation_lineage"]),
        "ldc_capacity_proxy": project_path(inputs["ldc_capacity_proxy"]),
        "water_stress_context": project_path(inputs["water_stress_context"]),
        "water_stress_lineage": project_path(inputs["water_stress_lineage"]),
        "china_map": project_path(inputs["china_map"]),
    }
    if not require_map:
        paths.pop("china_map")
    missing = [display_path(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("missing Figure 5 input: " + ", ".join(missing))

    resource_approval = json.loads(paths["resource_approval"].read_text(encoding="utf-8"))
    if resource_approval.get("status") != settings["validation"]["required_resource_interpretation_status"]:
        raise ValueError("resource summary is not approved for Figure 5")
    if resource_approval.get("model_version") != model_version:
        raise ValueError("resource approval model_version differs from defaults")
    if resource_approval.get("outputs", {}).get("summary_table", {}).get("sha256") != sha256(paths["resource_summary"]):
        raise ValueError("resource summary hash differs from approval marker")
    core_validation = json.loads(paths["core_validation"].read_text(encoding="utf-8"))
    if core_validation.get("status") != "validated" or core_validation.get("model_version") != model_version:
        raise ValueError("core summary is not validated for the active model version")
    spatial_audit = json.loads(paths["spatial_audit"].read_text(encoding="utf-8"))
    if spatial_audit.get("status") != settings["required_spatial_audit_status"]:
        raise ValueError("spatial-water audit has not authorized rebuild readiness")
    if spatial_audit.get("model_version") != model_version:
        raise ValueError("spatial-water audit model_version differs from defaults")
    for key in ["pf_allocation", "pf_allocation_lineage", "ldc_capacity_proxy", "water_stress_context", "water_stress_lineage"]:
        audit_key = {
            "pf_allocation_lineage": "pf_lineage",
            "ldc_capacity_proxy": "ldc_proxy",
            "water_stress_context": "water_stress",
        }.get(key, key)
        recorded = spatial_audit.get("input_hashes", {}).get(audit_key, {}).get("sha256")
        if recorded != sha256(paths[key]):
            raise ValueError(f"{key} differs from the READY spatial-water audit")
    return settings, model_version, results_root, paths, spatial_audit


def build_data(settings: dict[str, Any], model_version: str, paths: dict[str, Path]) -> pd.DataFrame:
    validation = settings["validation"]
    expected_provinces = int(validation["expected_provinces"])
    expected_industries = int(validation["expected_industries"])
    tolerance = float(validation["share_tolerance"])

    summary = pd.read_csv(paths["resource_summary"], encoding="utf-8-sig")
    water = summary[
        summary["metric_id"].eq(validation["water_metric"])
        & summary["sensitivity_case"].eq(validation["water_sensitivity_case"])
    ].copy()
    if len(water) != 2 or set(water["architecture"]) != set(validation["approved_architectures"]):
        raise ValueError("Figure 5 requires exactly the approved PF and LDC water totals")
    national_water = water.set_index("architecture")["value"].astype(float).to_dict()

    core = pd.read_csv(paths["core_summary"], encoding="utf-8-sig")
    pf_core = core[core["architecture"].eq("PF")].copy()
    if len(pf_core) != expected_industries or pf_core["industry"].nunique() != expected_industries:
        raise ValueError("Figure 5 requires 31 validated PF industry rows")
    if set(pf_core["model_version"].astype(str)) != {model_version}:
        raise ValueError("PF core model_version differs from defaults")
    industry_energy = pf_core.set_index("industry")["industry_equivalent_annual_ai_facility_energy_twh"].astype(float)
    if not industry_energy.gt(0).all():
        raise ValueError("PF industry-equivalent facility energy must be positive")

    allocation = pd.read_csv(paths["pf_allocation"], encoding="utf-8-sig")
    if len(allocation) != expected_industries * expected_provinces:
        raise ValueError("PF allocation must contain 31 industries by 31 provinces")
    allocation["industry_energy_twh"] = allocation["industry_code"].map(industry_energy)
    if allocation["industry_energy_twh"].isna().any():
        raise ValueError("PF allocation contains an industry absent from validated core results")
    allocation["province_energy_weight"] = allocation["industry_energy_twh"] * allocation["electricity_share_within_industry"]
    pf_share = allocation.groupby("province")["province_energy_weight"].sum()
    pf_share = pf_share / pf_share.sum()

    ldc = pd.read_csv(paths["ldc_capacity_proxy"], encoding="utf-8-sig")
    ldc_share = ldc.set_index("province")["cloud_load_share"].astype(float)
    stress = pd.read_csv(paths["water_stress_context"], encoding="utf-8-sig").set_index("province")
    province_sets = [set(pf_share.index), set(ldc_share.index), set(stress.index), set(TILES)]
    if any(len(values) != expected_provinces for values in province_sets) or not all(values == province_sets[0] for values in province_sets[1:]):
        raise ValueError("PF, LDC, Aqueduct and tile-grid province sets must match exactly")
    if not np.isclose(float(pf_share.sum()), 1.0, atol=tolerance, rtol=0.0):
        raise ValueError("PF province shares do not sum to one")
    if not np.isclose(float(ldc_share.sum()), 1.0, atol=tolerance, rtol=0.0):
        raise ValueError("LDC province shares do not sum to one")

    rows: list[dict[str, Any]] = []
    for architecture, shares, proxy in [
        ("PF", pf_share, "2030_REFERENCE_manufacturing_electricity_spatial_scenario"),
        ("LDC_AGGREGATE", ldc_share, "2025_CAict_in_use_intelligent_compute_capacity_proxy"),
    ]:
        for province in sorted(shares.index):
            stress_row = stress.loc[province]
            rows.append(
                {
                    "model_version": model_version,
                    "figure_version": settings["figure_version"],
                    "architecture": architecture,
                    "province": province,
                    "allocation_share": float(shares.loc[province]),
                    "national_onsite_cooling_humidification_water_m3_per_year": national_water[architecture],
                    "province_onsite_cooling_humidification_water_m3_per_year": national_water[architecture] * float(shares.loc[province]),
                    "allocation_proxy": proxy,
                    "aqueduct40_baseline_water_stress_score": float(stress_row["baseline_water_stress_score"]),
                    "aqueduct40_baseline_water_stress_category": int(stress_row["baseline_water_stress_category"]),
                    "aqueduct40_baseline_water_stress_label": str(stress_row["baseline_water_stress_label"]),
                    "aqueduct40_aggregation_weight": str(stress_row["aggregation_weight"]),
                    "site_water_times_stress_score": np.nan,
                    "context_only_not_multiplied": True,
                    "automatic_manuscript_edit": False,
                }
            )
    data = pd.DataFrame(rows)
    if len(data) != 2 * expected_provinces:
        raise ValueError("Figure 5 data must contain 62 architecture-province rows")
    for architecture in validation["approved_architectures"]:
        subset = data[data["architecture"].eq(architecture)]
        if not np.isclose(subset["allocation_share"].sum(), 1.0, atol=tolerance, rtol=0.0):
            raise ValueError(f"{architecture} allocation shares do not close")
        if not np.isclose(subset["province_onsite_cooling_humidification_water_m3_per_year"].sum(), national_water[architecture], atol=1e-6, rtol=tolerance):
            raise ValueError(f"{architecture} provincial water does not preserve the approved national total")
    if data["site_water_times_stress_score"].notna().any() or not data["context_only_not_multiplied"].all():
        raise ValueError("Figure 5 must not calculate a score-volume product")
    return data.sort_values(["architecture", "province"]).reset_index(drop=True)


def load_map(path: Path) -> gpd.GeoDataFrame:
    import geopandas as gpd  # Only needed when rendering the map.

    china = gpd.read_file(path)
    if "adcode" not in china.columns:
        raise ValueError("Figure 5 map must contain the adcode field")
    china["adcode"] = pd.to_numeric(china["adcode"], errors="coerce").astype("Int64")
    china["province"] = china["adcode"].map(ADCODE_TO_PROVINCE)
    return china.to_crs("+proj=aea +lat_1=25 +lat_2=47 +lat_0=0 +lon_0=105 +datum=WGS84 +units=m +no_defs")


def projected_extent(china: gpd.GeoDataFrame, lon_min: float, lat_min: float, lon_max: float, lat_max: float) -> tuple[float, float, float, float]:
    import geopandas as gpd

    corners = gpd.GeoSeries.from_xy([lon_min, lon_max], [lat_min, lat_max], crs="EPSG:4326").to_crs(china.crs)
    return corners.x.iloc[0], corners.x.iloc[1], corners.y.iloc[0], corners.y.iloc[1]


def stress_palette() -> tuple[ListedColormap, BoundaryNorm, list[str]]:
    colors = ["#D9F0D3", "#ADDD8E", "#FEE08B", "#FDAE61", "#D73027"]
    return ListedColormap(colors), BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5, 4.5], len(colors)), ["Low", "Low-medium", "Medium-high", "High", "Extremely high"]


def draw_map(axis: plt.Axes, china: gpd.GeoDataFrame, subset: pd.DataFrame, shared_max: float, settings: dict[str, Any], panel: dict[str, Any]) -> None:
    cmap, norm, _ = stress_palette()
    china.plot(ax=axis, color="#F0F1F2", edgecolor="white", linewidth=0.55)
    locations = china[china["province"].notna()][["province", "geometry"]].copy()
    locations["point"] = locations.geometry.representative_point()
    mapped = subset.merge(locations[["province", "point"]], on="province", how="left", validate="one_to_one")
    if mapped["point"].isna().any():
        raise ValueError("Figure 5 map is missing a modeled province geometry")
    top = set(mapped.nlargest(int(settings["figure"]["top_value_labels"]), "province_onsite_cooling_humidification_water_m3_per_year")["province"])
    for record in mapped.sort_values("province_onsite_cooling_humidification_water_m3_per_year").itertuples(index=False):
        x, y = record.point.x, record.point.y
        value = float(record.province_onsite_cooling_humidification_water_m3_per_year)
        area = float(settings["figure"]["maximum_bubble_area_points2"]) * value / shared_max
        axis.scatter(x, y, s=max(area, 8), color=cmap(norm(int(record.aqueduct40_baseline_water_stress_category))), edgecolor="#555555", linewidth=0.55, zorder=3)
        if record.province in top:
            offset = LABEL_OFFSETS.get(record.province, (4, 5))
            axis.annotate(
                PROVINCE_LABELS[record.province],
                (x, y),
                xytext=offset,
                textcoords="offset points",
                fontsize=15.5,
                color="#222222",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 0.8},
                zorder=4,
            )
    x0, x1, y0, y1 = projected_extent(china, 72.5, 16.5, 136.0, 54.5)
    axis.set_xlim(x0, x1); axis.set_ylim(y0, y1); axis.set_axis_off(); axis.set_aspect("equal")
    inset = axis.inset_axes([0.02, 0.07, 0.14, 0.24])
    china.plot(ax=inset, color="#F0F1F2", edgecolor="#999999", linewidth=0.35)
    ix0, ix1, iy0, iy1 = projected_extent(china, 105.0, 2.5, 125.0, 25.0)
    inset.set_xlim(ix0, ix1); inset.set_ylim(iy0, iy1); inset.set_axis_off(); inset.set_aspect("equal")
    axis.set_title(panel["title"], loc="left", fontweight="bold", fontsize=22, pad=12)


def draw_top_bars(axis: plt.Axes, subset: pd.DataFrame, shared_bar_max: float, panel: dict[str, Any]) -> None:
    cmap, norm, _ = stress_palette()
    top = subset.nlargest(7, "province_onsite_cooling_humidification_water_m3_per_year").sort_values("province_onsite_cooling_humidification_water_m3_per_year")
    values = top["province_onsite_cooling_humidification_water_m3_per_year"] / 1e3
    colors = [cmap(norm(int(value))) for value in top["aqueduct40_baseline_water_stress_category"]]
    axis.barh([PROVINCE_LABELS[name] for name in top["province"]], values, color=colors, height=0.62)
    axis.set_xlim(0, shared_bar_max * 1.15)
    axis.set_xlabel("On-site cooling and humidification water (thousand m³/year)", fontsize=17)
    axis.grid(axis="x", color="#D8DDE1", linewidth=0.8, alpha=0.75); axis.set_axisbelow(True)
    axis.set_title(panel["title"], loc="left", fontweight="bold", fontsize=22, pad=12)
    axis.tick_params(axis="both", labelsize=16)
    for y, record in enumerate(top.itertuples(index=False)):
        value = float(record.province_onsite_cooling_humidification_water_m3_per_year) / 1e3
        axis.text(
            value + shared_bar_max * 0.018,
            y,
            f"{record.allocation_share:.1%}",
            va="center",
            fontsize=16,
            color="#333333",
        )
    for side in ["top", "right"]:
        axis.spines[side].set_visible(False)


def plot(settings: dict[str, Any], data: pd.DataFrame, map_path: Path, outputs: dict[str, Path]) -> None:
    plt.rcParams.update({"font.sans-serif": ["Arial", "DejaVu Sans"], "axes.unicode_minus": False, "svg.fonttype": "none", "font.size": 17})
    china = load_map(map_path)
    fig, axes = plt.subplots(2, 2, figsize=(float(settings["figure"]["width_inches"]), float(settings["figure"]["height_inches"])), gridspec_kw={"hspace": 0.34, "wspace": 0.24})
    shared_max = float(data["province_onsite_cooling_humidification_water_m3_per_year"].max())
    shared_bar_max = shared_max / 1e3
    pf = data[data["architecture"].eq("PF")]
    ldc = data[data["architecture"].eq("LDC_AGGREGATE")]
    draw_map(axes[0, 0], china, pf, shared_max, settings, settings["panels"][0])
    draw_top_bars(axes[0, 1], pf, shared_bar_max, settings["panels"][1])
    draw_map(axes[1, 0], china, ldc, shared_max, settings, settings["panels"][2])
    draw_top_bars(axes[1, 1], ldc, shared_bar_max, settings["panels"][3])
    cmap, _, stress_labels = stress_palette()
    legend_handles = [
        Patch(facecolor=cmap(index), edgecolor="none", label=label)
        for index, label in enumerate(stress_labels)
    ]
    fig.legend(
        handles=legend_handles,
        title="Baseline water stress",
        loc="lower center",
        bbox_to_anchor=(0.5, 0.01),
        ncol=5,
        frameon=False,
        fontsize=16,
        title_fontsize=17,
        handlelength=1.5,
        columnspacing=1.6,
    )
    fig.subplots_adjust(left=0.055, right=0.985, top=0.94, bottom=0.105)
    for key in ["svg", "png", "pdf"]:
        outputs[key].parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outputs["svg"], bbox_inches="tight")
    fig.savefig(outputs["png"], dpi=int(settings["figure"]["png_dpi"]), bbox_inches="tight")
    fig.savefig(outputs["pdf"], bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    args = parse_args()
    config_path = project_path(args.config).resolve()
    settings, model_version, results_root, paths, spatial_audit = load_inputs(
        config_path, require_map=not args.data_only
    )
    data = build_data(settings, model_version, paths)
    output_root = args.output_root.resolve() if args.output_root else results_root / model_version / settings["outputs"]["subdirectory"]
    figure_keys = [] if args.data_only else ["svg", "png", "pdf"]
    outputs = {key: output_root / settings["outputs"][key] for key in ["data", *figure_keys, "validation"]}
    if args.check_only:
        print(json.dumps({"status": "ready_to_render", "model_version": model_version, "figure_version": settings["figure_version"], "rows": len(data), "spatial_audit_status": spatial_audit["status"], "solver_required": False}, ensure_ascii=False, indent=2))
        return 0
    output_root.mkdir(parents=True, exist_ok=True)
    data.to_csv(outputs["data"], index=False, encoding="utf-8-sig")
    if not args.data_only:
        plot(settings, data, paths["china_map"], outputs)
    marker = {
        "status": "validated_approved_design_RQ1_spatial_water_figure",
        "model_version": model_version,
        "figure_version": settings["figure_version"],
        "solver_required": False,
        "map_rendered": not args.data_only,
        "spatial_audit_status": spatial_audit["status"],
        "inputs": {key: {"path": display_path(path), "sha256": sha256(path)} for key, path in paths.items()},
        "outputs": {key: {"path": display_path(path), "sha256": sha256(path)} for key, path in outputs.items() if key != "validation"},
        "checks": {
            "rows": len(data),
            "province_count": data["province"].nunique(),
            "architectures": sorted(data["architecture"].unique()),
            "share_sums": data.groupby("architecture")["allocation_share"].sum().to_dict(),
            "provincial_water_sums_m3_per_year": data.groupby("architecture")["province_onsite_cooling_humidification_water_m3_per_year"].sum().to_dict(),
            "score_volume_product_all_missing": bool(data["site_water_times_stress_score"].isna().all()),
            "future_2030_BAU_excluded": True,
        },
        "claim_boundaries": settings["claim_boundaries"],
        "automatic_manuscript_edit": settings["automatic_manuscript_edit"],
        "main_manuscript_updated": False,
    }
    outputs["validation"].write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": marker["status"], "model_version": model_version, "data": display_path(outputs["data"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
