#!/usr/bin/env python3
"""Take a new delivery drop, but don't let it silently delete data.

The 0812 delivery shipped twice in one day. The second drop fixed 351 wrong
tumor/normal labels, and also -- without saying so -- cleared `tissue_type` on
325 samples and removed 22 populated `adjuvant_treatment_*` columns from
`individual.csv`. Her own live instance still had every one of those values,
because she inserted the 49 new T2 nodes incrementally instead of rebuilding
from the new CSVs. So the two artifacts she ships, the CSVs and the database,
disagreed with each other.

One rule decides every cell, so the result is reproducible rather than
hand-picked:

    a value that was non-empty and became empty is restored from the previous
    drop; everything else takes the new drop, including value changes.

Deletions are the only thing treated as suspect. A changed value is her
correcting something and is always accepted -- that is how the 350 `*_Tumor`
samples in HRA016026 got fixed. A dropped column that still had values is the
column-level form of the same rule.

Every restored cell is printed. If the report is ever empty the delivery is
clean and this script can go away.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# 主键，用来把新旧两版的行对上；没列在这里的文件整份取新版。
PRIMARY_KEYS = {
    "entities/individual.csv": "individual_accession",
    "entities/sample.csv": "sample_accession",
    "entities/study.csv": "study_accession",
    "entities/project.csv": "project_accession",
    "entities/T1.csv": "T1_id",
    "entities/T2.csv": "T2_id",
    "entities/tool.csv": "tool_id",
}


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def read_git_csv(ref: str, path: str) -> Tuple[List[str], List[Dict[str, str]]]:
    blob = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, check=True
    ).stdout.decode("utf-8-sig")
    reader = csv.DictReader(blob.splitlines())
    return list(reader.fieldnames or []), list(reader)


def reconcile_file(
    relative: str,
    previous: Tuple[List[str], List[Dict[str, str]]],
    incoming: Tuple[List[str], List[Dict[str, str]]],
) -> Tuple[List[str], List[Dict[str, str]], Dict[str, object]]:
    key = PRIMARY_KEYS.get(relative)
    previous_columns, previous_rows = previous
    incoming_columns, incoming_rows = incoming
    if not key:
        return incoming_columns, incoming_rows, {}

    previous_by_key = {row.get(key, ""): row for row in previous_rows}
    restored_columns = [
        column
        for column in previous_columns
        if column not in incoming_columns
        and any((row.get(column) or "").strip() for row in previous_rows)
    ]
    columns = list(incoming_columns) + restored_columns

    restored_cells: Counter = Counter()
    examples: Dict[str, Tuple[str, str]] = {}
    rows: List[Dict[str, str]] = []
    for row in incoming_rows:
        merged = dict(row)
        earlier = previous_by_key.get(row.get(key, ""))
        if earlier:
            for column in columns:
                if (merged.get(column) or "").strip():
                    continue
                value = (earlier.get(column) or "").strip()
                if not value:
                    continue
                merged[column] = earlier[column]
                restored_cells[column] += 1
                examples.setdefault(column, (row.get(key, ""), value))
        rows.append({column: merged.get(column, "") for column in columns})

    report = {
        "restored_columns": restored_columns,
        "restored_cells": dict(restored_cells),
        "examples": examples,
        "rows_only_in_previous": sorted(set(previous_by_key) - {r.get(key, "") for r in incoming_rows}),
    }
    return columns, rows, report


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--incoming", required=True, help="新一版交付的 import 目录")
    parser.add_argument("--target", default="data/0812", help="仓库里的交付目录，就地更新")
    parser.add_argument(
        "--previous-ref",
        default="HEAD",
        help="拿哪个 git ref 里的 --target 当作上一版（默认 HEAD）",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    incoming_root = Path(args.incoming)
    target_root = Path(args.target)

    reports: Dict[str, Dict[str, object]] = {}
    for source in sorted(incoming_root.rglob("*.csv")):
        relative = source.relative_to(incoming_root).as_posix()
        target = target_root / relative
        incoming = read_csv(source)
        try:
            previous = read_git_csv(args.previous_ref, (target_root / relative).as_posix())
        except subprocess.CalledProcessError:
            previous = ([], [])
        columns, rows, report = reconcile_file(relative, previous, incoming)
        if any(report.get(field) for field in ("restored_columns", "restored_cells", "rows_only_in_previous")):
            reports[relative] = report
        if not args.dry_run:
            write_csv(target, columns, rows)

    if not reports:
        print("新一版没有删除任何已有数据，整份直接采用。")
        return 0

    print("新一版删掉了下面这些已有数据，已从上一版回填：\n")
    for relative, report in reports.items():
        print(f"  {relative}")
        if report["restored_columns"]:
            print(f"    整列删除: {len(report['restored_columns'])} 列 -> {report['restored_columns']}")
        for column, count in sorted(report["restored_cells"].items(), key=lambda x: -x[1]):
            sample_key, value = report["examples"][column]
            print(f"    {column}: 回填 {count:,} 格   例 {sample_key} = {value!r}")
        if report["rows_only_in_previous"]:
            print(f"    上一版有、新版没有的行: {len(report['rows_only_in_previous'])}（未回填，行删除不在本规则内）")
    print("\n以上都应该反馈给数据提供方，本脚本只是不让它们悄悄消失。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
