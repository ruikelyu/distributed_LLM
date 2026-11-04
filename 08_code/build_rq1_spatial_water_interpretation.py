#!/usr/bin/env python3
"""Build a bounded, solver-free interpretation of validated Figure 5 data.

Purpose: Convert the approved PF/LDC province allocation figure data into
auditable descriptive summaries and author-approved wording for later migration.
Workflow status: Active approved-interpretation generator; no manuscript edit.
Scientific boundary: Water quantity and Aqueduct stress remain independent.
Inputs: YAML-selected defaults, Figure 5 configuration, data, and validation marker.
Outputs: Architecture, Top-7, and stress-category CSVs; a Markdown review memo;
and a machine-readable approval marker.
Key assumptions: Province allocation shares distribute each architecture's own
registered national on-site cooling and humidification water total.
Explicit exclusions: No score-volume product, LCIA, causal architecture effect,
observed siting, physical site concentration, or local water-impact claim.
Validation/tests: Version and hashes, exact dimensions, allocation closure,
province-context identity, category mapping, and prohibited-product absence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = (
    PROJECT_ROOT / "config/scenarios/rq1_spatial_water_interpretation_v1.yaml"
)
SEMVER = re.compile(r"v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)")


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


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series
    normalized = series.astype(str).str.strip().str.lower()
    if not normalized.isin({"true", "false"}).all():
        raise ValueError(f"{series.name} contains values other than true/false")
    return normalized.eq("true")


def load_and_validate(
    settings: dict[str, Any], config_path: Path
) -> tuple[pd.DataFrame, dict[str, Any], Path, Path, Path, str]:
    defaults_path = project_path(settings["defaults_config"])
    figure_config_path = project_path(settings["figure5_config"])
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    figure_config = yaml.safe_load(figure_config_path.read_text(encoding="utf-8"))
    model_version = str(defaults["model_version"])
    if not SEMVER.fullmatch(model_version):
        raise ValueError("defaults_config model_version must use vMAJOR.MINOR.PATCH")

    results_root = project_path(defaults["paths"]["results_root"])
    figure_root = (
        results_root / model_version / figure_config["outputs"]["subdirectory"]
    )
    data_path = figure_root / figure_config["outputs"]["data"]
    marker_path = figure_root / figure_config["outputs"]["validation"]
    if not data_path.exists() or not marker_path.exists():
        raise FileNotFoundError("Validated Figure 5 data and marker are required")

    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("status") != settings["required_figure_status"]:
        raise ValueError("Figure 5 marker does not have the required status")
    if marker.get("model_version") != model_version:
        raise ValueError("Figure 5 marker model_version differs from defaults YAML")
    if marker.get("figure_version") != figure_config["figure_version"]:
        raise ValueError("Figure 5 marker figure_version differs from figure YAML")
    if marker.get("automatic_manuscript_edit") is not False:
        raise ValueError("Figure 5 marker permits an automatic manuscript edit")
    if marker.get("main_manuscript_updated") is not False:
        raise ValueError("Figure 5 marker unexpectedly records a manuscript update")
    if marker.get("outputs", {}).get("data", {}).get("sha256") != sha256(data_path):
        raise ValueError("Figure 5 data hash differs from its validation marker")
    if marker.get("inputs", {}).get("configuration", {}).get("sha256") != sha256(
        figure_config_path
    ):
        raise ValueError("Figure 5 configuration changed after figure validation")

    table = pd.read_csv(data_path, encoding="utf-8-sig")
    validation = settings["validation"]
    required_columns = {
        "model_version",
        "figure_version",
        "architecture",
        "province",
        "allocation_share",
        "national_onsite_cooling_humidification_water_m3_per_year",
        "province_onsite_cooling_humidification_water_m3_per_year",
        "allocation_proxy",
        "aqueduct40_baseline_water_stress_score",
        "aqueduct40_baseline_water_stress_category",
        "aqueduct40_baseline_water_stress_label",
        "aqueduct40_aggregation_weight",
        "site_water_times_stress_score",
        "context_only_not_multiplied",
        "automatic_manuscript_edit",
    }
    missing = required_columns.difference(table.columns)
    if missing:
        raise ValueError(f"Figure 5 data are missing columns: {sorted(missing)}")
    if len(table) != int(validation["expected_rows"]):
        raise ValueError("Unexpected Figure 5 row count")
    if set(table["architecture"].astype(str)) != set(
        validation["expected_architectures"]
    ):
        raise ValueError("Unexpected Figure 5 architecture set")
    if set(table["model_version"].astype(str)) != {model_version}:
        raise ValueError("Figure 5 table model_version differs from defaults YAML")
    if set(table["figure_version"].astype(str)) != {figure_config["figure_version"]}:
        raise ValueError("Figure 5 table figure_version differs from figure YAML")
    if table.duplicated(["architecture", "province"]).any():
        raise ValueError("Figure 5 contains duplicate architecture-province rows")

    expected_provinces = int(validation["expected_provinces"])
    province_sets = {
        architecture: set(group["province"].astype(str))
        for architecture, group in table.groupby("architecture", sort=False)
    }
    if any(len(values) != expected_provinces for values in province_sets.values()):
        raise ValueError("At least one architecture lacks exact province coverage")
    if len({frozenset(values) for values in province_sets.values()}) != 1:
        raise ValueError("PF and LDC do not cover the same province set")

    share_tolerance = float(validation["share_tolerance"])
    share_sums = table.groupby("architecture")["allocation_share"].sum()
    if not np.allclose(share_sums.to_numpy(), 1.0, atol=share_tolerance, rtol=0):
        raise ValueError("Architecture allocation shares do not sum to one")
    national_counts = table.groupby("architecture")[
        "national_onsite_cooling_humidification_water_m3_per_year"
    ].nunique()
    if not national_counts.eq(1).all():
        raise ValueError("National site-water total varies within an architecture")
    expected_water = (
        table["allocation_share"]
        * table["national_onsite_cooling_humidification_water_m3_per_year"]
    )
    if not np.allclose(
        expected_water,
        table["province_onsite_cooling_humidification_water_m3_per_year"],
        atol=float(validation["water_tolerance_m3_per_year"]),
        rtol=1e-12,
    ):
        raise ValueError("Provincial water does not equal share times national total")

    if validation["require_score_volume_product_missing"] and not table[
        "site_water_times_stress_score"
    ].isna().all():
        raise ValueError("A prohibited site-water-times-stress product is populated")
    context_flag = bool_series(table["context_only_not_multiplied"])
    if bool(validation["required_context_flag"]) and not context_flag.all():
        raise ValueError("Not every row preserves stress as independent context")
    automatic_edit = bool_series(table["automatic_manuscript_edit"])
    if validation["required_automatic_manuscript_edit"] is False and automatic_edit.any():
        raise ValueError("Figure 5 data permit automatic manuscript editing")

    category_map = {
        int(key): str(value)
        for key, value in validation["required_stress_categories"].items()
    }
    categories = table["aqueduct40_baseline_water_stress_category"].astype(int)
    if set(categories) != set(category_map):
        raise ValueError("Aqueduct category coverage differs from YAML")
    for category, label in category_map.items():
        observed = set(
            table.loc[categories.eq(category), "aqueduct40_baseline_water_stress_label"]
            .astype(str)
            .unique()
        )
        if observed != {label}:
            raise ValueError(f"Aqueduct category {category} label differs from YAML")

    context_columns = [
        "province",
        "aqueduct40_baseline_water_stress_score",
        "aqueduct40_baseline_water_stress_category",
        "aqueduct40_baseline_water_stress_label",
        "aqueduct40_aggregation_weight",
    ]
    contexts = []
    for _, group in table.groupby("architecture", sort=True):
        contexts.append(group[context_columns].sort_values("province").reset_index(drop=True))
    if not contexts[0].equals(contexts[1]):
        raise ValueError("PF and LDC do not use the same independent province context")

    if any("2030" in str(value) and "BAU" in str(value).upper() for value in table.values.ravel()):
        raise ValueError("2030 BAU water stress entered the main Figure 5 table")

    return table, marker, defaults_path, figure_config_path, data_path, model_version


def build_summaries(
    table: pd.DataFrame, settings: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    top_n = int(settings["summary"]["top_n"])
    high_categories = {
        int(value)
        for value in settings["summary"]["high_or_extremely_high_categories"]
    }
    labels = settings["summary"]["architecture_labels"]
    province_labels = {
        str(key): str(value)
        for key, value in settings["summary"]["province_labels"].items()
    }
    if set(province_labels) != set(table["province"].astype(str)):
        raise ValueError("YAML province labels do not exactly cover Figure 5 provinces")
    architecture_rows: list[dict[str, Any]] = []
    top_frames: list[pd.DataFrame] = []
    category_frames: list[pd.DataFrame] = []

    for architecture in settings["validation"]["expected_architectures"]:
        group = table.loc[table["architecture"].eq(architecture)].copy()
        group = group.sort_values(
            ["allocation_share", "province"], ascending=[False, True]
        ).reset_index(drop=True)
        ranked = group.head(top_n).copy()
        ranked.insert(2, "rank", np.arange(1, len(ranked) + 1))
        ranked.insert(4, "province_label", ranked["province"].map(province_labels))
        top_frames.append(
            ranked[
                [
                    "model_version",
                    "architecture",
                    "rank",
                    "province",
                    "province_label",
                    "allocation_share",
                    "province_onsite_cooling_humidification_water_m3_per_year",
                    "aqueduct40_baseline_water_stress_score",
                    "aqueduct40_baseline_water_stress_category",
                    "aqueduct40_baseline_water_stress_label",
                    "allocation_proxy",
                ]
            ]
        )

        category = (
            group.groupby(
                [
                    "aqueduct40_baseline_water_stress_category",
                    "aqueduct40_baseline_water_stress_label",
                ],
                as_index=False,
                observed=True,
            )
            .agg(
                province_count=("province", "nunique"),
                allocated_site_water_m3_per_year=(
                    "province_onsite_cooling_humidification_water_m3_per_year",
                    "sum",
                ),
                allocation_share=("allocation_share", "sum"),
            )
            .sort_values("aqueduct40_baseline_water_stress_category")
        )
        category.insert(0, "architecture", architecture)
        category.insert(0, "model_version", str(group["model_version"].iloc[0]))
        category_frames.append(category)

        high = group.loc[
            group["aqueduct40_baseline_water_stress_category"].astype(int).isin(
                high_categories
            )
        ]
        extreme = group.loc[
            group["aqueduct40_baseline_water_stress_category"].astype(int).eq(4)
        ]
        architecture_rows.append(
            {
                "model_version": str(group["model_version"].iloc[0]),
                "architecture": architecture,
                "architecture_label": labels[architecture],
                "allocation_proxy": str(group["allocation_proxy"].iloc[0]),
                "national_site_water_m3_per_year": float(
                    group[
                        "national_onsite_cooling_humidification_water_m3_per_year"
                    ].iloc[0]
                ),
                "largest_allocation_province": str(ranked.iloc[0]["province"]),
                "largest_allocation_province_label": str(
                    ranked.iloc[0]["province_label"]
                ),
                "largest_allocation_share": float(ranked.iloc[0]["allocation_share"]),
                "top_n": top_n,
                "top_n_cumulative_allocation_share": float(
                    ranked["allocation_share"].sum()
                ),
                "high_or_extremely_high_allocation_share": float(
                    high["allocation_share"].sum()
                ),
                "high_or_extremely_high_site_water_m3_per_year": float(
                    high[
                        "province_onsite_cooling_humidification_water_m3_per_year"
                    ].sum()
                ),
                "extremely_high_allocation_share": float(
                    extreme["allocation_share"].sum()
                ),
                "extremely_high_site_water_m3_per_year": float(
                    extreme[
                        "province_onsite_cooling_humidification_water_m3_per_year"
                    ].sum()
                ),
            }
        )

    architecture_summary = pd.DataFrame(architecture_rows)
    top_provinces = pd.concat(top_frames, ignore_index=True)
    category_summary = pd.concat(category_frames, ignore_index=True)
    for frame, name in [
        (architecture_summary, "architecture summary"),
        (top_provinces, "Top-N summary"),
        (category_summary, "stress-category summary"),
    ]:
        numeric = frame.select_dtypes(include=[np.number])
        if not np.isfinite(numeric.to_numpy()).all():
            raise ValueError(f"{name} contains non-finite numeric values")

    top_sets = {
        architecture: set(
            top_provinces.loc[
                top_provinces["architecture"].eq(architecture), "province"
            ].astype(str)
        )
        for architecture in settings["validation"]["expected_architectures"]
    }
    pf = architecture_summary.set_index("architecture").loc["PF"]
    ldc = architecture_summary.set_index("architecture").loc["LDC_AGGREGATE"]
    diagnostic = {
        "top_n": top_n,
        "top_n_overlap_count": len(top_sets["PF"] & top_sets["LDC_AGGREGATE"]),
        "top_n_overlap_provinces": sorted(
            top_sets["PF"] & top_sets["LDC_AGGREGATE"]
        ),
        "top_n_overlap_province_labels": [
            province_labels[province]
            for province in sorted(top_sets["PF"] & top_sets["LDC_AGGREGATE"])
        ],
        "high_or_extremely_high_spatial_allocation_share_difference_percentage_points_pf_minus_ldc": 100
        * (
            float(pf["high_or_extremely_high_allocation_share"])
            - float(ldc["high_or_extremely_high_allocation_share"])
        ),
        "interpretation": "descriptive_difference_between_registered_spatial_allocation_inputs_not_architecture_effect",
    }
    return architecture_summary, top_provinces, category_summary, diagnostic


def build_markdown(
    architecture_summary: pd.DataFrame,
    top_provinces: pd.DataFrame,
    category_summary: pd.DataFrame,
    diagnostic: dict[str, Any],
    settings: dict[str, Any],
    data_path: Path,
    marker_path: Path,
) -> str:
    indexed = architecture_summary.set_index("architecture")
    pf = indexed.loc["PF"]
    ldc = indexed.loc["LDC_AGGREGATE"]
    architecture_rows = []
    for row in architecture_summary.to_dict(orient="records"):
        architecture_rows.append(
            "| {architecture_label} | {national:.3f} | {largest} ({largest_pct:.1f}%) | "
            "{top_n_pct:.1f}% | {high_pct:.1f}% | {extreme_pct:.1f}% |".format(
                **row,
                national=row["national_site_water_m3_per_year"] / 1e6,
                # English province name for the review text; the Chinese
                # province_label column is kept unchanged in the CSV outputs.
                largest=str(row["largest_allocation_province"]).title(),
                largest_pct=100 * row["largest_allocation_share"],
                top_n_pct=100 * row["top_n_cumulative_allocation_share"],
                high_pct=100 * row["high_or_extremely_high_allocation_share"],
                extreme_pct=100 * row["extremely_high_allocation_share"],
            )
        )
    top_rows = []
    for row in top_provinces.to_dict(orient="records"):
        top_rows.append(
            "| {architecture} | {rank} | {province_name} | {water:,.0f} | {share:.1f}% | {stress} |".format(
                **row,
                province_name=str(row["province"]).title(),
                water=row[
                    "province_onsite_cooling_humidification_water_m3_per_year"
                ],
                share=100 * row["allocation_share"],
                stress=row["aqueduct40_baseline_water_stress_label"],
            )
        )
    category_rows = []
    for row in category_summary.to_dict(orient="records"):
        category_rows.append(
            "| {architecture} | {category} | {province_count} | {water:,.0f} | {share:.1f}% |".format(
                **row,
                category=row["aqueduct40_baseline_water_stress_label"],
                water=row["allocated_site_water_m3_per_year"],
                share=100 * row["allocation_share"],
            )
        )
    overlap = [str(province).title() for province in diagnostic["top_n_overlap_provinces"]]
    overlap_text = ", ".join(overlap) if overlap else "none"
    candidate = (
        f"In the Figure 5 spatial screen of the {pf.model_version} main scenario, PF's {pf.national_site_water_m3_per_year / 1e6:.3f} million m³/year "
        f"of onsite cooling and humidification water is allocated by the 2030 REFERENCE manufacturing-electricity spatial scenario; the top {int(pf.top_n)} provinces account for "
        f"{100 * pf.top_n_cumulative_allocation_share:.1f}%, and provinces in the Aqueduct baseline High or Extremely High categories account for "
        f"{100 * pf.high_or_extremely_high_allocation_share:.1f}%. LDC aggregate's {ldc.national_site_water_m3_per_year / 1e6:.3f} million m³/year "
        f"is allocated by the 2025 in-service intelligent-computing capacity proxy; the top {int(ldc.top_n)} provinces account for {100 * ldc.top_n_cumulative_allocation_share:.1f}%, "
        f"and High or Extremely High category provinces account for {100 * ldc.high_or_extremely_high_allocation_share:.1f}%. "
        f"The two Top-{int(pf.top_n)} sets share {diagnostic['top_n_overlap_count']} provinces ({overlap_text}). "
        "These shares only describe the overlay of two registered provincial spatial allocations on the same provincial water-stress background; they do not represent actual facility siting, physical site concentration, a causal architecture effect, or a formal water-scarcity impact."
    )
    boundaries = "\n".join(
        f"{index}. `{boundary}`"
        for index, boundary in enumerate(settings["claim_boundaries"], start=1)
    )
    return (
        f"# RQ1 Figure 5 spatial water: controlled interpretation review memo ({pf.model_version})\n\n"
        "**Status: interpretation confirmed by the authors; reserved for later coordinated migration into the manuscript.**\n\n"
        "## 1. Review scope and evidence\n\n"
        f"This memo only interprets the validated data `{display_path(data_path)}` and its marker `{display_path(marker_path)}`. "
        "Statistics are aggregated directly from provincial allocation shares; the PyPSA solver is not run, Figure 5 is not changed, and the manuscript text is not modified.\n\n"
        "## 2. Within-architecture descriptive summary\n\n"
        "| Architecture | National onsite water (million m³/yr) | Largest provincial allocation | Top-7 provincial allocation share | High-or-above share | Extremely High share |\n"
        "|---|---:|---|---:|---:|---:|\n"
        + "\n".join(architecture_rows)
        + "\n\nShares here are provincial spatial-allocation shares of each architecture's own national onsite water total: PF uses the 2030 REFERENCE manufacturing-electricity spatial scenario and LDC uses the 2025 in-service intelligent-computing capacity proxy. PF and LDC use different registered WUE scenarios and different spatial inputs, so differences in national totals or shares cannot be interpreted as a net effect of deployment architecture.\n\n"
        "## 3. Top-7 provincial spatial allocation\n\n"
        "| Architecture | Rank | Province | Onsite water (m³/yr) | Within-architecture share | Aqueduct baseline category |\n"
        "|---|---:|---|---:|---:|---|\n"
        + "\n".join(top_rows)
        + f"\n\nThe two Top-{diagnostic['top_n']} sets share {diagnostic['top_n_overlap_count']} provinces: {overlap_text}. "
        "This only shows that the two registered spatial inputs produce different provincial distributions. Both are referred to as Top-7 provincial spatial allocation; the cumulative share is not a concentration of physical data centers or plant sites.\n\n"
        "## 4. Water-stress category composition\n\n"
        "| Architecture | Aqueduct baseline category | Provinces | Allocated onsite water (m³/yr) | Within-architecture share |\n"
        "|---|---|---:|---:|---:|\n"
        + "\n".join(category_rows)
        + "\n\nThese category totals answer 'what share of each architecture's proxy allocation falls in a given provincial background category'; water volume is not multiplied by the stress score, and this does not constitute m³ world-equivalent, a formal LCIA, or a local water-resource impact.\n\n"
        "## 5. Author-confirmed Results wording pending migration\n\n"
        + candidate
        + "\n\n## 6. Required accompanying claim boundaries\n\n"
        + boundaries
        + "\n\n## 7. Author decision gate\n\n"
        "This confirmation only authorizes these values, names, and boundaries for later coordinated manuscript migration; this script still does not modify the manuscript, and the Figure 5 data and figure status are unchanged.\n"
    )


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("automatic_manuscript_edit") is not False:
        raise ValueError("Interpretation YAML must disable automatic manuscript editing")
    table, figure_marker, defaults_path, figure_config_path, data_path, model_version = (
        load_and_validate(settings, config_path)
    )
    architecture_summary, top_provinces, category_summary, diagnostic = (
        build_summaries(table, settings)
    )
    marker_path = data_path.parent / yaml.safe_load(
        figure_config_path.read_text(encoding="utf-8")
    )["outputs"]["validation"]
    defaults = yaml.safe_load(defaults_path.read_text(encoding="utf-8"))
    output_root = (
        args.output_root.resolve()
        if args.output_root
        else project_path(defaults["paths"]["results_root"])
        / model_version
        / settings["outputs"]["subdirectory"]
    )
    review = build_markdown(
        architecture_summary,
        top_provinces,
        category_summary,
        diagnostic,
        settings,
        data_path,
        marker_path,
    )

    check_summary = {
        "status": "author_approved_for_later_manuscript_migration",
        "model_version": model_version,
        "analysis_version": settings["analysis_version"],
        "solver_required": False,
        "architecture_count": int(architecture_summary.shape[0]),
        "top_n": int(settings["summary"]["top_n"]),
        "stress_category_count": int(
            category_summary["aqueduct40_baseline_water_stress_category"].nunique()
        ),
        "distribution_diagnostic": diagnostic,
        "automatic_manuscript_edit": False,
        "main_manuscript_updated": False,
    }
    if args.check_only:
        print(json.dumps(check_summary, ensure_ascii=False, indent=2))
        return 0

    output_root.mkdir(parents=True, exist_ok=True)
    outputs = settings["outputs"]
    architecture_path = output_root / outputs["architecture_summary"]
    top_path = output_root / outputs["top_provinces"]
    category_path = output_root / outputs["stress_category_composition"]
    review_path = output_root / outputs["interpretation_review"]
    done_path = output_root / outputs["validation"]
    architecture_summary.to_csv(architecture_path, index=False, encoding="utf-8-sig")
    top_provinces.to_csv(top_path, index=False, encoding="utf-8-sig")
    category_summary.to_csv(category_path, index=False, encoding="utf-8-sig")
    review_path.write_text(review, encoding="utf-8")

    provenance = {
        **check_summary,
        "evidence_status": settings["evidence_status"],
        "inputs": {
            "configuration": {
                "path": display_path(config_path),
                "sha256": sha256(config_path),
            },
            "defaults": {
                "path": display_path(defaults_path),
                "sha256": sha256(defaults_path),
            },
            "figure_configuration": {
                "path": display_path(figure_config_path),
                "sha256": sha256(figure_config_path),
            },
            "figure_data": {
                "path": display_path(data_path),
                "sha256": sha256(data_path),
            },
            "figure_validation": {
                "path": display_path(marker_path),
                "sha256": sha256(marker_path),
                "status": figure_marker["status"],
            },
        },
        "outputs": {
            "architecture_summary": {
                "path": display_path(architecture_path),
                "sha256": sha256(architecture_path),
            },
            "top_provinces": {
                "path": display_path(top_path),
                "sha256": sha256(top_path),
            },
            "stress_category_composition": {
                "path": display_path(category_path),
                "sha256": sha256(category_path),
            },
            "interpretation_review": {
                "path": display_path(review_path),
                "sha256": sha256(review_path),
            },
        },
        "checks": {
            "source_rows": int(len(table)),
            "province_count": int(table["province"].nunique()),
            "score_volume_product_all_missing": bool(
                table["site_water_times_stress_score"].isna().all()
            ),
            "water_and_stress_remain_independent": True,
            "future_2030_BAU_excluded": True,
            "interpretation_author_approved": True,
        },
        "claim_boundaries": settings["claim_boundaries"],
    }
    done_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
