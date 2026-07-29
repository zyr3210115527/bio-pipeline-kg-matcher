#!/usr/bin/env python3
"""Convert the reviewed 96-question workbook extraction into runtime fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.source.read_text(encoding="utf-8"))
    cases = []
    for index, row in enumerate(payload.get("rows", [])[1:], 1):
        if len(row) < 4 or not row[1] or not row[3]:
            continue
        cases.append({
            "case_id": f"q{index:03d}",
            "query": str(row[1]).strip(),
            "expected_data": [
                value.strip()
                for value in str(row[2] or "").splitlines()
                if value.strip()
            ],
            "expected_pipeline_id": str(row[3]).strip(),
        })

    output = {
        "schema_version": "question-tool-data-benchmark/v1",
        "source": "96例问题-数据-工具对应表(1).xlsx!Sheet1:B2:D97",
        "case_count": len(cases),
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
