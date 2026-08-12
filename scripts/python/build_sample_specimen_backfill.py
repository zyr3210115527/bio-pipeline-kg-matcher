#!/usr/bin/env python3
"""Recover sample-level specimen_types/tissue_type that the 0811 delivery dropped.

0811 `entities/sample.csv` is run-level and only carries `specimen_type` for the
557 healthy rows. The pre-0811 graph had `specimen_types` on every one of its
8,640 sample nodes, and `STUDY_ROLE_RULES` in ``pipeline_router.py`` resolves
tumor/normal roles from exactly that field. Without it, paired WES
tumor/normal matching (and therefore the GATK four-slot binding) cannot work.

This reads the pre-0811 logical backup, keeps only accessions that still exist
in the 0811 sample table, and writes a supplement CSV. The import step only
fills properties that are absent on the 0811 node, so her data always wins.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from pathlib import Path
from typing import Dict, Sequence

FIELDS = ("sample_accession", "specimen_types", "tissue_type")


def load_backup_samples(backup: Path) -> Dict[str, Dict[str, str]]:
    samples: Dict[str, Dict[str, str]] = {}
    with gzip.open(backup, "rt", encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("kind") != "node":
                continue
            value = record["value"]
            if "sample" not in set(value.get("labels") or []):
                continue
            properties = value.get("properties") or {}
            accession = str(properties.get("sample_accession") or "").strip()
            if not accession:
                continue
            samples[accession] = {
                "sample_accession": accession,
                "specimen_types": str(properties.get("specimen_types") or "").strip(),
                "tissue_type": str(properties.get("tissue_type") or "").strip(),
            }
    return samples


def load_current_accessions(sample_csv: Path) -> set[str]:
    with sample_csv.open(encoding="utf-8-sig", newline="") as handle:
        return {
            (row.get("sample_accession") or "").strip()
            for row in csv.DictReader(handle)
            if (row.get("sample_accession") or "").strip()
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", required=True, help="pre-0811 *.jsonl.gz logical backup")
    parser.add_argument("--sample-csv", default="data/0811/entities/sample.csv")
    parser.add_argument("--output", default="data/0811_supplement/sample_specimen_backfill.csv")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    legacy = load_backup_samples(Path(args.backup))
    current = load_current_accessions(Path(args.sample_csv))
    rows = [
        legacy[accession]
        for accession in sorted(current & set(legacy))
        if legacy[accession]["specimen_types"] or legacy[accession]["tissue_type"]
    ]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    print(
        f"legacy_samples={len(legacy)} current_samples={len(current)} "
        f"written={len(rows)} -> {output}"
    )
    print(f"not recoverable (0811-only samples)={len(current - set(legacy))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
