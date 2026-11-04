"""Shared AI-adoption scenario and adopter-conditioned demand scaling.

The national service ledger is an unconditional industry total: non-adopting
firms contribute zero service and therefore dilute the industry average.  A
representative group that is known to have adopted AI must instead be scaled
by its activity share divided by the adopter activity-coverage share.

The current China source reports firm-count adoption rather than activity-
weighted adoption.  The 2030 firm-count scenario is therefore used only as an
explicit proxy for adopter activity coverage and is labelled accordingly in
all model outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_NATIONAL_ADOPTION_2030 = 0.480046


@dataclass(frozen=True)
class AdopterConditioning:
    industry_code: str
    year: int
    adopter_activity_share: float
    evidence_status: str
    source_measure: str

    def group_service_scale(self, group_activity_share: float) -> float:
        if not 0.0 < group_activity_share <= 1.0:
            raise ValueError("group_activity_share must be in (0, 1]")
        return float(group_activity_share) / self.adopter_activity_share

    def industry_equivalent_multiplier(self, group_activity_share: float) -> float:
        if not 0.0 < group_activity_share <= 1.0:
            raise ValueError("group_activity_share must be in (0, 1]")
        return self.adopter_activity_share / float(group_activity_share)


def odds(value: float) -> float:
    if not 0.0 < value < 1.0:
        raise ValueError("Adoption fraction must be in (0, 1)")
    return value / (1.0 - value)


def inverse_odds(value: float) -> float:
    if value <= 0.0:
        raise ValueError("Odds must be positive")
    return value / (1.0 + value)


def adoption_scenario_2030(
    adoption: pd.DataFrame,
    national_target: float = DEFAULT_NATIONAL_ADOPTION_2030,
) -> pd.DataFrame:
    """Return the industry 2030 adoption scenario used by Figure 1 and core."""
    required = {
        "industry_code",
        "above_size_firms_2023",
        "any_ai_adoption_2023",
        "template_diffusion_speed",
    }
    missing = required - set(adoption.columns)
    if missing:
        raise ValueError(f"Adoption input is missing columns: {sorted(missing)}")
    if len(adoption) != 31 or adoption["industry_code"].nunique() != 31:
        raise ValueError("Adoption input must cover 31 manufacturing industries")
    if not 0.0 < float(national_target) < 1.0:
        raise ValueError("national_target must be in (0, 1)")
    if not adoption["any_ai_adoption_2023"].astype(float).between(0.0, 1.0, inclusive="neither").all():
        raise ValueError("Observed adoption fractions must be in (0, 1)")
    if not (adoption["above_size_firms_2023"].astype(float) > 0.0).all():
        raise ValueError("Firm-count weights must be positive")

    frame = adoption.copy()
    national_2023 = float(
        (
            frame["any_ai_adoption_2023"].astype(float)
            * frame["above_size_firms_2023"].astype(float)
        ).sum()
        / frame["above_size_firms_2023"].astype(float).sum()
    )
    national_odds_multiplier = odds(float(national_target)) / odds(national_2023)
    frame["any_ai_adoption_2030"] = [
        inverse_odds(
            odds(float(row.any_ai_adoption_2023))
            * national_odds_multiplier ** float(row.template_diffusion_speed)
        )
        for row in frame.itertuples(index=False)
    ]
    frame["adopter_activity_share_proxy_2030"] = frame["any_ai_adoption_2030"]
    frame["adopter_activity_share_proxy_status"] = (
        "firm_count_adoption_scenario_used_as_activity_coverage_proxy"
    )
    return frame


def read_adopter_conditioning(
    path: Path,
    industry_code: str,
    *,
    year: int = 2030,
    national_target: float = DEFAULT_NATIONAL_ADOPTION_2030,
) -> AdopterConditioning:
    if year != 2030:
        raise ValueError("The active China adopter-conditioning scenario supports 2030 only")
    frame = adoption_scenario_2030(
        pd.read_csv(path, encoding="utf-8-sig"),
        national_target=national_target,
    )
    selected = frame[frame["industry_code"].astype(str).eq(industry_code)]
    if len(selected) != 1:
        raise ValueError(f"Expected one adoption row for {industry_code}")
    row = selected.iloc[0]
    share = float(row["adopter_activity_share_proxy_2030"])
    if not 0.0 < share <= 1.0:
        raise ValueError(f"Invalid adopter activity share proxy for {industry_code}")
    return AdopterConditioning(
        industry_code=industry_code,
        year=year,
        adopter_activity_share=share,
        evidence_status=str(row["adopter_activity_share_proxy_status"]),
        source_measure="fraction_of_above_size_firms_with_any_AI",
    )


def conditioning_from_config(
    root: Path,
    config: dict,
    industry_code: str,
) -> AdopterConditioning:
    settings = config["demand"]["adopter_conditioning"]
    if settings["mode"] != "conditional_on_adopted_group":
        raise ValueError("Active group investment workflow requires conditional_on_adopted_group")
    return read_adopter_conditioning(
        root / config["paths"]["industry_adoption_parameters"],
        industry_code,
        year=int(settings["year"]),
        national_target=float(settings["national_adoption_target_2030"]),
    )
