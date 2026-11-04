#!/usr/bin/env python3
"""Freeze and verify the official WRI Aqueduct 4.0 rankings archive.

Purpose: Download or validate the exact official archive before province-level
water-stress extraction.
Workflow status: Explicit source-refresh utility for the active Figure 5 chain.
Scientific boundary: Establishes source identity only; it does not calculate
water stress, site water, exposure, or lifecycle impact.
Inputs: YAML source contract and its registered WRI download URL or local copy.
Outputs: Checksum-frozen ZIP archive and JSON source receipt.
Key assumptions: The registered byte size and SHA-256 identify the approved
2023-07-05 rankings package.
Explicit exclusions: Workbook extraction, province mapping, Figure 5, model
optimization, and manuscript editing.
Validation/tests: YAML schema, nonempty file, exact byte size, exact SHA-256,
temporary download validation, and atomic replacement.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

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


def validate(path: Path, file_contract: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError(f"official archive is absent or empty: {path}")
    observed_sha256 = sha256(path)
    if observed_sha256 != file_contract["official_sha256"]:
        raise ValueError(
            f"official SHA-256 mismatch: expected {file_contract['official_sha256']}, observed {observed_sha256}"
        )
    if path.stat().st_size != int(file_contract["bytes"]):
        raise ValueError(f"official byte-size mismatch: expected {file_contract['bytes']}, observed {path.stat().st_size}")
    return {"bytes": path.stat().st_size, "sha256": observed_sha256}


def download(settings: dict[str, Any], destination: Path) -> str:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    request = urllib.request.Request(
        settings["file"]["download_url"], headers={"User-Agent": "distributed-LLM-source-freezer/1.0"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary_path.open("wb") as output:
            while block := response.read(1024 * 1024):
                output.write(block)
        validate(temporary_path, settings["file"])
        temporary_path.replace(destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return settings["file"]["download_url"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = project_path(args.config)
    settings = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if settings.get("schema_version") != 1:
        raise ValueError("Aqueduct source schema_version must equal 1")
    destination = project_path(settings["file"]["destination"])
    if destination.is_file():
        source_url = "preexisting_official_copy"
    elif args.check_only:
        raise FileNotFoundError(f"official archive not yet frozen: {destination}")
    else:
        source_url = download(settings, destination)
    checks = validate(destination, settings["file"])
    receipt = {
        "status": "official_source_frozen_and_checksum_verified",
        "source_id": settings["source_id"],
        "source_url_used": source_url,
        "source_page": settings["dataset"]["source_page"],
        "technical_note_doi": settings["dataset"]["technical_note_doi"],
        "access_date": str(date.today()),
        "path": str(destination.relative_to(PROJECT_ROOT)),
        **checks,
    }
    receipt_path = destination.with_suffix(".source.json")
    if not args.check_only:
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif not receipt_path.is_file():
        raise FileNotFoundError(f"source receipt is missing: {receipt_path}")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
