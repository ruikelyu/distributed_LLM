#!/usr/bin/env python3
"""Build Figure 1 for manufacturing-AI demand scale and composition.

The main figure treats demand as context for the later architecture comparison.
It emphasizes the 2030 low/base/high demand scenarios, end-use task composition,
and major industries. Adoption detail, foundation-model attribution, reference-
system conversion, reconstructed early demand, and external top-down electricity
ranges are retained in the accompanying text or data rather than annotated in
the main figure.

Run without arguments from anywhere:

    python3 08_code/build_figure1_manufacturing_ai_demand.py

"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault(
    "MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "distributed_llm_matplotlib")
)

try:
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
except ModuleNotFoundError:
    analysis_python = Path("/opt/anaconda3/bin/python")
    if analysis_python.exists() and os.environ.get("FIGURE1_PYTHON_REEXEC") != "1":
        os.environ["FIGURE1_PYTHON_REEXEC"] = "1"
        os.execv(str(analysis_python), [str(analysis_python), *sys.argv])
    raise


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIGURE_ROOT = PROJECT_ROOT / "05_results/v1.0.0/result/manuscript_figures"
sys.path.insert(0, str(PROJECT_ROOT / "08_code"))

from core.adoption import (  # noqa: E402
    DEFAULT_NATIONAL_ADOPTION_2030,
    adoption_scenario_2030,
)


TASK_ORDER = [
    "office",
    "agent",
    "vision",
    "maintenance",
    "scheduling",
    "simulation",
]
TASK_LABELS = {
    "office": "Office services",
    "agent": "Business agents",
    "vision": "Vision QA",
    "maintenance": "Maintenance",
    "scheduling": "Scheduling",
    "simulation": "R&D simulation",
}
TASK_COLORS = {
    "office": "#8BA6B4",
    "agent": "#E7A84B",
    "vision": "#D66B5D",
    "maintenance": "#9A78B5",
    "scheduling": "#54A69A",
    "simulation": "#356F9F",
}
SHORT_INDUSTRY_NAMES = {
    "C13": "Agri-food processing",
    "C14": "Food",
    "C15": "Beverages and tea",
    "C16": "Tobacco",
    "C17": "Textiles",
    "C18": "Apparel",
    "C19": "Leather and footwear",
    "C20": "Wood products",
    "C21": "Furniture",
    "C22": "Paper",
    "C23": "Printing",
    "C24": "Cultural and sports goods",
    "C25": "Petroleum and coal processing",
    "C26": "Chemicals",
    "C27": "Pharmaceuticals",
    "C28": "Chemical fibers",
    "C29": "Rubber and plastics",
    "C30": "Non-metallic minerals",
    "C31": "Ferrous metals",
    "C32": "Non-ferrous metals",
    "C33": "Fabricated metals",
    "C34": "General machinery",
    "C35": "Special-purpose machinery",
    "C36": "Motor vehicles",
    "C37": "Transport equipment",
    "C38": "Electrical machinery",
    "C39": "Electronic equipment",
    "C40": "Instruments",
    "C41": "Other manufacturing",
    "C42": "Resource recovery",
    "C43": "Equipment repair",
}
INDUSTRY_PLOT_LABELS = {
    "C39": "Electronics",
    "C34": "General machinery",
    "C38": "Electrical machinery",
    "C26": "Chemicals",
    "C35": "Special-purpose equip.",
    "C30": "Non-metallic products",
    "C36": "Motor vehicles",
    "C33": "Fabricated metals",
}
MODEL_VERSION = "v1.0.0"
NATIONAL_ADOPTION_2030_SCENARIO = DEFAULT_NATIONAL_ADOPTION_2030


def _base_row(**kwargs: object) -> dict[str, object]:
    row: dict[str, object] = {
        "model_version": MODEL_VERSION,
        "panel": "",
        "category": "",
        "label": "",
        "series": "",
        "value": np.nan,
        "weight": np.nan,
        "unit": "",
        "status": "",
    }
    row.update(kwargs)
    return row


def prepare_data(
    adoption_path: Path,
    service_path: Path,
    attribution_path: Path,
) -> tuple[pd.DataFrame, dict[str, float]]:
    adoption = pd.read_csv(adoption_path, encoding="utf-8-sig")
    service = pd.read_csv(service_path, encoding="utf-8-sig")
    attribution = pd.read_csv(attribution_path, encoding="utf-8-sig")

    if len(adoption) != 31 or adoption["industry_code"].nunique() != 31:
        raise ValueError("Adoption input must cover 31 manufacturing industries")
    if set(service["parameter_case"]) != {"low", "base", "high"}:
        raise ValueError("Effective-service input must contain low/base/high scenarios")
    if set(attribution["scope"]) != {"foundation", "strict_llm"}:
        raise ValueError("Attribution input must contain foundation and strict_llm scopes")

    adoption_2030 = adoption_scenario_2030(
        adoption, national_target=NATIONAL_ADOPTION_2030_SCENARIO
    )
    national_2023 = float(
        (adoption["any_ai_adoption_2023"] * adoption["above_size_firms_2023"]).sum()
        / adoption["above_size_firms_2023"].sum()
    )
    national_2030 = float(
        (
            adoption_2030["any_ai_adoption_2030"]
            * adoption_2030["above_size_firms_2023"]
        ).sum()
        / adoption_2030["above_size_firms_2023"].sum()
    )

    rows: list[dict[str, object]] = []
    for item in service.itertuples(index=False):
        rows.append(
            _base_row(
                panel="a",
                category=f"2030_{item.parameter_case}",
                label=item.task_name_cn,
                series=item.task_id,
                value=float(item.effective_service_units_day),
                unit="effective_service_units/day",
                status="bottom_up_scenario",
            )
        )
        if item.parameter_case == "base":
            rows.append(
                _base_row(
                    panel="b",
                    category=item.industry_code,
                    label=item.industry_name_cn,
                    series=item.task_id,
                    value=float(item.effective_service_units_day),
                    unit="effective_service_units/day",
                    status="bottom_up_base_scenario",
                )
            )

    base_task_totals = (
        service[service["parameter_case"].eq("base")]
        .groupby("task_id")["effective_service_units_day"]
        .sum()
    )
    foundation = attribution[attribution["scope"].eq("foundation")].set_index("task_id")
    strict_llm = attribution[attribution["scope"].eq("strict_llm")].set_index("task_id")
    base_total = float(base_task_totals.sum())
    foundation_share = float(
        sum(
            float(base_task_totals[task]) * float(foundation.loc[task, "base"])
            for task in TASK_ORDER
        )
        / base_total
    )
    strict_llm_share = float(
        sum(
            float(base_task_totals[task]) * float(strict_llm.loc[task, "base"])
            for task in TASK_ORDER
        )
        / base_total
    )

    context_rows = [
        ("adoption_2023", "National enterprise adoption", national_2023, "fraction", "observed"),
        ("adoption_2025", "National enterprise adoption", np.nan, "fraction", "reported_above_30_percent"),
        ("adoption_2030", "National enterprise adoption", national_2030, "fraction", "scenario"),
        ("foundation_share_base", "Foundation-model involved", foundation_share, "fraction", "service_attribution_scenario"),
        ("strict_llm_share_base", "Strict LLM-primary subset", strict_llm_share, "fraction", "service_attribution_scenario"),
    ]
    for category, label, value, unit, status in context_rows:
        rows.append(
            _base_row(
                panel="context",
                category=category,
                label=label,
                series=category,
                value=value,
                unit=unit,
                status=status,
            )
        )

    context = {
        "national_adoption_2023": national_2023,
        "national_adoption_2030": national_2030,
        "foundation_share_base": foundation_share,
        "strict_llm_share_base": strict_llm_share,
    }
    return pd.DataFrame(rows), context


def _style_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="x", color="#D9DEE2", linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def plot(
    data: pd.DataFrame,
    outputs: list[Path],
) -> None:
    plt.rcParams.update(
        {
            "font.sans-serif": [
                "Arial Unicode MS",
                "PingFang SC",
                "Noto Sans CJK SC",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 14,
        }
    )

    fig, (ax_a, ax_b) = plt.subplots(
        1,
        2,
        figsize=(12.0, 6.0),
        gridspec_kw={"width_ratios": [1.0, 1.12], "wspace": 0.50},
    )

    demand = data[data["panel"].eq("a")]
    cases = ["2030_low", "2030_base", "2030_high"]
    scenario_labels = ["Low", "Base", "High"]
    x = np.arange(len(cases))
    bottoms = np.zeros(len(cases))
    task_values_by_case: dict[str, np.ndarray] = {}
    for task in TASK_ORDER:
        values = np.array(
            [
                demand[demand["category"].eq(case) & demand["series"].eq(task)]["value"].sum()
                / 1e6
                for case in cases
            ]
        )
        task_values_by_case[task] = values
        for i, value in enumerate(values):
            ax_a.bar(
                x[i],
                value,
                bottom=bottoms[i],
                width=0.62,
                color=TASK_COLORS[task],
                alpha=0.90,
                label=TASK_LABELS[task] if i == 0 else None,
            )
        bottoms += values
    for i, total in enumerate(bottoms):
        label = f"{total:.1f}"
        ax_a.text(
            x[i],
            total + max(bottoms) * 0.025,
            label,
            ha="center",
            va="bottom",
            fontsize=13,
            color="#1F2F3A",
        )

    ax_a.set_xticks(x, scenario_labels)
    ax_a.set_ylabel("Effective service (million units/day)")
    ax_a.set_title(
        "a  National demand in 2030",
        loc="left",
        fontweight="bold",
        fontsize=15,
    )
    ax_a.set_ylim(0, max(bottoms) * 1.12)
    _style_axis(ax_a)
    ax_a.grid(axis="x", visible=False)

    industry = data[data["panel"].eq("b")]
    totals = industry.groupby("category")["value"].sum().sort_values(ascending=False)
    top_codes = totals.head(8).index.tolist()
    y = np.arange(len(top_codes))
    left = np.zeros(len(top_codes))
    for task in TASK_ORDER:
        values = np.array(
            [
                industry[
                    industry["category"].eq(code) & industry["series"].eq(task)
                ]["value"].sum()
                / 1e6
                for code in top_codes
            ]
        )
        ax_b.barh(y, values, left=left, color=TASK_COLORS[task], height=0.69)
        left += values
    ax_b.set_yticks(
        y,
        [INDUSTRY_PLOT_LABELS[code] for code in top_codes],
        fontsize=12.5,
    )
    ax_b.invert_yaxis()
    ax_b.set_xlabel("Base-demand effective service (million units/day)")
    ax_b.set_title(
        "b  Major industries in the base-demand scenario",
        loc="left",
        fontweight="bold",
        fontsize=15,
    )
    _style_axis(ax_b)

    handles, labels = ax_a.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=3,
        frameon=False,
        fontsize=12.0,
    )
    fig.subplots_adjust(left=0.075, right=0.985, top=0.93, bottom=0.23)
    for output in outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output, bbox_inches="tight", dpi=300)
    plt.close(fig)


def _relative(path: Path) -> str:
    """Path relative to the project root, so metadata does not depend on the checkout location."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the streamlined Figure 1 manufacturing-AI demand figure."
    )
    parser.add_argument(
        "--adoption-input",
        type=Path,
        default=PROJECT_ROOT / "02_data/china_manufacturing_ai_31sector_proxy_parameters.csv",
    )
    parser.add_argument(
        "--service-input",
        type=Path,
        default=PROJECT_ROOT
        / "02_data/processed/effective_service/manufacturing_ai_effective_service_2030.csv",
    )
    parser.add_argument(
        "--attribution-input",
        type=Path,
        default=PROJECT_ROOT
        / "02_data/manufacturing_foundation_model_task_attribution_parameters_v0.1.csv",
    )
    parser.add_argument(
        "--data-output",
        type=Path,
        default=FIGURE_ROOT / "figure1_manufacturing_ai_demand_data.csv",
    )
    parser.add_argument(
        "--png-output",
        type=Path,
        default=FIGURE_ROOT / "figure1_manufacturing_ai_demand.png",
    )
    parser.add_argument(
        "--pdf-output",
        type=Path,
        default=FIGURE_ROOT / "figure1_manufacturing_ai_demand.pdf",
    )
    parser.add_argument(
        "--svg-output",
        type=Path,
        default=FIGURE_ROOT / "figure1_manufacturing_ai_demand.svg",
    )
    parser.add_argument(
        "--metadata-output",
        type=Path,
        default=FIGURE_ROOT / "figure1_manufacturing_ai_demand.metadata.json",
    )
    args = parser.parse_args()

    data, context = prepare_data(
        args.adoption_input,
        args.service_input,
        args.attribution_input,
    )
    args.data_output.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(args.data_output, index=False, encoding="utf-8-sig")
    plot(data, [args.png_output, args.pdf_output, args.svg_output])

    metadata = {
        "artifact_id": "figure1-manufacturing-ai-demand-v100",
        "status": "author_approved_for_active_manuscript",
        "model_version": MODEL_VERSION,
        "displayed_panels": [
            "2030_low_base_high_demand_and_task_composition",
            "top_eight_industries_in_base_demand_scenario",
        ],
        "context_strip": None,
        "main_figure_exclusions": [
            "full_31_industry_adoption_ranking",
            "reconstructed_2023_and_intermediate_2025_demand",
            "external_top_down_national_electricity_range",
            "deployment_architecture_schematic",
            "foundation_model_and_strict_llm_attribution",
            "fixed_reference_system_conversion",
            "explanatory_percentage_callouts",
        ],
        "service_input": _relative(args.service_input),
        "attribution_input": _relative(args.attribution_input),
        "outputs": {
            "data": _relative(args.data_output),
            "png": _relative(args.png_output),
            "pdf": _relative(args.pdf_output),
            "svg": _relative(args.svg_output),
        },
    }
    args.metadata_output.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Figure written to {args.png_output}")


if __name__ == "__main__":
    main()
