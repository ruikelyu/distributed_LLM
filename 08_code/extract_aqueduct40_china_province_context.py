#!/usr/bin/env python3
"""Extract the approved China province Aqueduct 4.0 baseline context.

Purpose: Reproduce a 31-province, industrial-demand-weighted baseline water
stress screen from the checksum-frozen WRI country-rankings archive.
Workflow status: Active deterministic source-to-processed-data transformation.
Scientific boundary: Context only; never multiply scores by site-water volume.
Inputs: YAML selection contract and checksum-frozen WRI rankings ZIP workbook.
Outputs: China province baseline context CSV and JSON extraction lineage.
Key assumptions: GADM 3.6 admin-1 names map one-to-one to the project's 31
province identifiers; industrial gross withdrawal is the approved main weight.
Explicit exclusions: 2030 BAU main-case use, local site validation, real-time
stress, water inventory construction, LCIA, optimization, and manuscript edits.
Validation/tests: Source SHA-256, archive member and sheet, required columns,
exact province coverage, unique identifiers, score/category ranges, deterministic
reproduction, and separate total-withdrawal diagnostic extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.testing import assert_frame_equal
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config/scenarios/aqueduct40_province_water_stress_v1.yaml"


def project_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_sheet(archive: Path, member: str, sheet: str) -> pd.DataFrame:
    with zipfile.ZipFile(archive) as bundle:
        if member not in bundle.namelist():
            raise ValueError(f"registered workbook member is absent: {member}")
        workbook = io.BytesIO(bundle.read(member))
    return pd.read_excel(workbook, sheet_name=sheet)


def select_rows(frame: pd.DataFrame, selection: dict[str, Any], weight: str) -> pd.DataFrame:
    required = {"gid_0", "gid_1", "name_0", "name_1", "indicator_name", "weight", "score", "cat", "label"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"official province sheet lacks required columns: {sorted(missing)}")
    selected = frame[
        frame[selection["country_field"]].eq(selection["country_value"])
        & frame[selection["indicator_field"]].eq(selection["indicator_value"])
        & frame[selection["weight_field"]].eq(weight)
    ].copy()
    if len(selected) != int(selection["expected_provinces"]):
        raise ValueError(f"expected {selection['expected_provinces']} rows for weight {weight}, found {len(selected)}")
    if selected["gid_1"].duplicated().any() or selected["name_1"].duplicated().any():
        raise ValueError(f"duplicate China province rows for weight {weight}")
    selected["score"] = pd.to_numeric(selected["score"], errors="raise")
    selected["cat"] = pd.to_numeric(selected["cat"], errors="raise").astype(int)
    if not selected["score"].between(0, 5, inclusive="both").all():
        raise ValueError(f"Aqueduct score outside [0, 5] for weight {weight}")
    if not selected["cat"].between(0, 4, inclusive="both").all() or selected["label"].isna().any():
        raise ValueError(f"Aqueduct category or label invalid for weight {weight}")
    return selected


def extract(settings: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    archive = project_path(settings["file"]["destination"])
    if not archive.is_file():
        raise FileNotFoundError(f"official archive missing: {archive}; run refresh-aqueduct40-source")
    observed_sha256 = sha256(archive)
    if observed_sha256 != settings["file"]["official_sha256"]:
        raise ValueError("official Aqueduct archive SHA-256 does not match the YAML contract")
    selection = settings["selection"]
    frame = read_sheet(archive, settings["file"]["archive_member"], selection["sheet"])
    main = select_rows(frame, selection, selection["main_weight_value"])
    diagnostic = select_rows(frame, selection, selection["diagnostic_weight_value"])

    source_map = selection["source_name_to_project_province"]
    main["province"] = main["name_1"].map(source_map)
    unmapped = sorted(main.loc[main["province"].isna(), "name_1"].astype(str).unique())
    if unmapped or main["province"].nunique() != int(selection["expected_provinces"]):
        raise ValueError(f"China province mapping is incomplete: {unmapped}")
    diagnostic_by_gid = diagnostic.set_index("gid_1")["score"]
    if set(main["gid_1"]) != set(diagnostic_by_gid.index):
        raise ValueError("industrial- and total-weighted province sets differ")

    output = pd.DataFrame(
        {
            "province": main["province"],
            "aqueduct40_gid_1": main["gid_1"],
            "source_province_name": main["name_1"],
            "baseline_water_stress_score": main["score"].astype(float),
            "baseline_water_stress_category": main["cat"].astype(int),
            "baseline_water_stress_label": main["label"].astype(str),
            "aggregation_weight": selection["main_weight_interpretation"],
            "total_weighted_score_diagnostic": main["gid_1"].map(diagnostic_by_gid).astype(float),
            "context_only_not_multiplied_by_site_water": True,
        }
    ).sort_values("province").reset_index(drop=True)
    lineage = {
        "status": "official_source_extracted_and_validated",
        "source_id": settings["source_id"],
        "source_path": str(archive.relative_to(PROJECT_ROOT)),
        "source_sha256": observed_sha256,
        "source_page": settings["dataset"]["source_page"],
        "data_dictionary": settings["dataset"]["data_dictionary"],
        "technical_note_doi": settings["dataset"]["technical_note_doi"],
        "archive_member": settings["file"]["archive_member"],
        "sheet": selection["sheet"],
        "filters": {
            selection["country_field"]: selection["country_value"],
            selection["indicator_field"]: selection["indicator_value"],
            selection["weight_field"]: selection["main_weight_value"],
        },
        "rows": len(output),
        "province_count": output["province"].nunique(),
        "score_range": [float(output["baseline_water_stress_score"].min()), float(output["baseline_water_stress_score"].max())],
        "main_weight_interpretation": selection["main_weight_interpretation"],
        "diagnostic_weight": selection["diagnostic_weight_value"],
        "diagnostic_weight_interpretation": selection["diagnostic_weight_interpretation"],
        "boundary": settings["claim_boundaries"],
    }
    return output, lineage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = yaml.safe_load(project_path(args.config).read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("Aqueduct extraction schema_version must equal 1")
    output, lineage = extract(settings)
    output_path = project_path(settings["selection"]["output"])
    lineage_path = project_path(settings["selection"]["lineage"])
    if args.check_only:
        if not output_path.is_file() or not lineage_path.is_file():
            raise FileNotFoundError("processed Aqueduct context table or lineage is missing")
        frozen = pd.read_csv(output_path, encoding="utf-8-sig")
        try:
            assert_frame_equal(frozen, output, check_exact=False, rtol=0.0, atol=1.0e-12)
        except AssertionError as error:
            raise ValueError("processed Aqueduct context table does not reproduce") from error
        if json.loads(lineage_path.read_text(encoding="utf-8")) != lineage:
            raise ValueError("processed Aqueduct lineage does not reproduce")
        print("Aqueduct 4.0 China province context extraction check passed")
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False, encoding="utf-8-sig")
    lineage_path.write_text(json.dumps(lineage, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path.relative_to(PROJECT_ROOT)}")
    print(f"Wrote {lineage_path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
