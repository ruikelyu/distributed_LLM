#!/usr/bin/env python3
"""Download third-party input data that is too large to keep in the repository.

Only needed to rerun the full workflow (`snakemake paper`). The solver-free
rebuild (`08_code/reproduce_paper_results.py`) works without it.

Each file is downloaded from its archived source and checked against the MD5
checksum published by the repository host before it is moved into place.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATASETS = [
    {
        "name": "EWELD: Electricity consumption of enterprises in China (Liu et al.)",
        "doi": "https://doi.org/10.6084/m9.figshare.21893808.v3",
        "license": "CC BY 4.0",
        "url": "https://ndownloader.figshare.com/files/38873490",
        "md5": "eea1455aff6518aae1fbfc397b178111",
        "bytes": 258_090_540,
        "destination": "02_data/raw_load_profiles/eweld/EWELD.zip",
    },
]


def md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(dataset: dict, force: bool) -> None:
    destination = ROOT / dataset["destination"]
    if destination.exists() and not force:
        if md5(destination) == dataset["md5"]:
            print(f"ok       {dataset['destination']}")
            return
        raise ValueError(f"{destination} exists but its MD5 does not match; rerun with --force")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    print(f"download {dataset['destination']} ({dataset['bytes'] / 1e6:.0f} MB) from {dataset['doi']}")
    request = urllib.request.Request(dataset["url"], headers={"User-Agent": "distributed-llm-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as output:
        while block := response.read(1 << 20):
            output.write(block)
    checksum = md5(partial)
    if checksum != dataset["md5"]:
        partial.unlink()
        raise ValueError(f"MD5 mismatch for {dataset['destination']}: {checksum}")
    partial.replace(destination)
    print(f"ok       {dataset['destination']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Download again even if the file exists.")
    args = parser.parse_args()
    for dataset in DATASETS:
        fetch(dataset, args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
