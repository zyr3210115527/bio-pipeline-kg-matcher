"""Neo4j data backend that reuses the CSV matcher's established Python behavior."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping, Optional

from neo4j import GraphDatabase, READ_ACCESS

from pipeline_router import CsvKGDataMatcher


CANONICAL_SNAPSHOT_ID = "dg-b23135d49c950d0846a563bc"


class Neo4jKGDataMatcher(CsvKGDataMatcher):
    """Load normalized matcher tables from datagraph/v1, then reuse all business logic."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        driver: Any = None,
    ):
        self.uri = uri or os.environ.get("NEO4J_URI", "")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password if password is not None else os.environ.get("NEO4J_PASSWORD", "")
        self.database = database or os.environ.get("NEO4J_DATABASE", "")
        self.snapshot_id = snapshot_id or os.environ.get(
            "DATAGRAPH_SNAPSHOT_ID", CANONICAL_SNAPSHOT_ID
        )
        if not self.uri or not self.database or not self.password:
            raise RuntimeError("Neo4j data matcher is not configured")
        self._owns_driver = driver is None
        self._driver = driver or GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
            connection_timeout=float(os.environ.get("NEO4J_CONNECT_TIMEOUT", "2")),
        )
        self.data_schema = "normalized-v2"
        try:
            self._load_graph()
        except Exception:
            self.close()
            raise

    @staticmethod
    def _source_row(properties: Mapping[str, Any]) -> Dict[str, str]:
        raw = properties.get("source_row_json")
        if not raw:
            raise RuntimeError(
                f"managed entity is missing source_row_json: {properties.get('source_table')}"
            )
        parsed = json.loads(str(raw))
        return {str(key): "" if value is None else str(value) for key, value in parsed.items()}

    def _load_source_entities(self, session: Any, label: str) -> List[Dict[str, str]]:
        result = session.run(
            f"MATCH (n:`{label}`) "
            "WHERE n.datagraph_managed = true AND n.snapshot_id = $snapshot_id "
            "RETURN properties(n) AS properties ORDER BY n.source_row_number",
            snapshot_id=self.snapshot_id,
        )
        return [self._source_row(dict(row["properties"])) for row in result]

    def _load_graph(self) -> None:
        with self._driver.session(
            database=self.database,
            default_access_mode=READ_ACCESS,
        ) as session:
            snapshots = [
                dict(row)
                for row in session.run(
                    "MATCH (n) WHERE n.datagraph_managed = true "
                    "RETURN n.snapshot_id AS snapshot_id,count(n) AS count ORDER BY snapshot_id"
                )
            ]
            if snapshots != [{"snapshot_id": self.snapshot_id, "count": 32744}]:
                raise RuntimeError(
                    f"Neo4j data graph snapshot mismatch: expected {self.snapshot_id}/32744, got {snapshots}"
                )
            self.study = self._load_source_entities(session, "study")
            self.project = self._load_source_entities(session, "project")
            self.sample = self._load_source_entities(session, "sample")
            self.individual = self._load_source_entities(session, "individual")
            self.t2 = self._load_source_entities(session, "t2")
            self.sample_specimen_types = {
                row.get("sample_accession"): row.get("specimen_types") or ""
                for row in self.sample
                if row.get("sample_accession")
            }
            self.t1 = []
            result = session.run(
                "MATCH (n:t1) "
                "WHERE n.datagraph_managed = true AND n.snapshot_id = $snapshot_id "
                "RETURN properties(n) AS p ORDER BY n.study_accession,n.run_accession,n.read_pair,n.files",
                snapshot_id=self.snapshot_id,
            )
            for record in result:
                row = dict(record["p"])
                sample_accession = str(row.get("sample_accession") or "")
                self.t1.append(
                    {
                        "study_accession": str(row.get("study_accession") or ""),
                        "sample_accession": sample_accession,
                        "run_accession": str(row.get("run_accession") or ""),
                        "data_type": str(row.get("data_type") or row.get("strategy") or ""),
                        "Read Pair": str(row.get("read_pair") or ""),
                        "files": str(row.get("files") or ""),
                        "format": str(row.get("semantic_format") or ""),
                        "file_path": str(row.get("file_path") or ""),
                        "file_description": str(row.get("file_description") or ""),
                        "Experiment": str(row.get("experiment_accession") or ""),
                        "Platform": str(row.get("platform") or ""),
                        "data_level": str(row.get("data_level") or ""),
                        "strategy": str(row.get("strategy") or ""),
                        "individual_accession": str(row.get("individual_accession") or ""),
                        "individual_name": str(row.get("individual_name") or ""),
                        "sample_name": str(row.get("sample_name") or ""),
                        "specimen_types": self.sample_specimen_types.get(sample_accession, ""),
                        "gender": str(row.get("gender") or ""),
                    }
                )

            self.project_by_study = {}
            for row in self.project:
                studies = str(row.get("study_accession") or "").replace("，", ",").split(",")
                for study in studies:
                    study = study.strip()
                    if study and study not in self.project_by_study:
                        self.project_by_study[study] = row
            projects_by_id = {row.get("project_accession"): row for row in self.project}
            relation_rows = session.run(
                "MATCH (s:study)-[:IN_PROJECT]->(p:project) "
                "WHERE s.datagraph_managed = true AND p.datagraph_managed = true "
                "RETURN s.study_accession AS study_accession,p.project_accession AS project_accession "
                "ORDER BY study_accession,project_accession"
            )
            for relation in relation_rows:
                project = projects_by_id.get(relation["project_accession"])
                if project:
                    self.project_by_study[str(relation["study_accession"])] = project
            self.study_by_id = {
                row.get("study_accession"): row
                for row in self.study
                if row.get("study_accession")
            }

    def close(self) -> None:
        if getattr(self, "_owns_driver", False) and getattr(self, "_driver", None) is not None:
            self._driver.close()
            self._driver = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
