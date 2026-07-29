"""Environment-controlled matcher construction."""

from __future__ import annotations

import os
from typing import Any


def build_data_matcher(mode: str | None = None) -> Any:
    selected = (mode or os.environ.get("DATA_MATCHER_MODE", "csv")).strip().lower()
    if selected == "csv":
        from pipeline_router import CsvKGDataMatcher

        return CsvKGDataMatcher()
    if selected == "neo4j":
        from .neo4j_matcher import Neo4jKGDataMatcher

        return Neo4jKGDataMatcher()
    if selected == "compare":
        from pipeline_router import CsvKGDataMatcher

        from .dual_read import DualReadDataMatcher
        from .neo4j_matcher import Neo4jKGDataMatcher

        return DualReadDataMatcher(CsvKGDataMatcher(), Neo4jKGDataMatcher())
    raise RuntimeError(
        f"unsupported DATA_MATCHER_MODE={selected!r}; expected csv, compare, or neo4j"
    )
