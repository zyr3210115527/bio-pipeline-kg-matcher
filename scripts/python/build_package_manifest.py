#!/usr/bin/env python3
"""Build a deterministic Markdown inventory and SHA-256 manifest for a delivery tree."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def purpose(relative: str) -> str:
    if relative == "neo4j/datagraph-staging.dump":
        return "统一 Neo4j 数据图 + 工具目录 dump"
    if relative.startswith("app/data/csv/"):
        return "CSV 回退/双读基准数据"
    if relative.startswith("app/data_matcher/"):
        return "数据 matcher 实现"
    if relative.startswith("app/config/"):
        return "运行时验证/allowlist 配置"
    if relative.startswith("app/"):
        return "可启动 MCP 应用代码或依赖"
    if relative.startswith("scripts/python/"):
        return "恢复、验证、双读或冒烟脚本"
    if relative.startswith("scripts/"):
        return "对方视角验收脚本"
    if relative.startswith("client_examples/"):
        return "MCP 客户端配置/调用样例"
    if "restore_" in relative:
        return "全新 home 恢复演练证据"
    if relative.endswith(".json"):
        return "机器可读 manifest/验证证据/回放磁带"
    if relative.endswith(".md"):
        return "交付说明或验证报告"
    if relative == ".env.example":
        return "无密钥环境变量模板"
    return "交付文件"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir")
    args = parser.parse_args()
    root = Path(args.package_dir).resolve()
    output = root / "PACKAGE_MANIFEST.md"
    files = [
        path
        for path in root.rglob("*")
        if path.is_file() and path != output and "__pycache__" not in path.parts
    ]
    rows = []
    aggregate = hashlib.sha256()
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        sha = digest(path)
        size = path.stat().st_size
        aggregate.update(f"{relative}\0{sha}\0{size}\n".encode("utf-8"))
        rows.append((relative, size, sha, purpose(relative)))
    lines = [
        "# Package Manifest",
        "",
        f"文件数（不含本 manifest）: {len(rows)}  ",
        f"内容清单 fingerprint: `{aggregate.hexdigest()}`  ",
        "`PACKAGE_MANIFEST.md` 因自引用不能包含自身稳定 hash。",
        "",
        "| Path | Bytes | SHA-256 | Purpose |",
        "|---|---:|---|---|",
    ]
    lines.extend(
        f"| `{relative}` | {size} | `{sha}` | {description} |"
        for relative, size, sha, description in rows
    )
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files={len(rows)} fingerprint={aggregate.hexdigest()} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
