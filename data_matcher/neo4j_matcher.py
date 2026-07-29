"""Neo4j data backend that reuses the CSV matcher's established Python behavior."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional

from neo4j import GraphDatabase, READ_ACCESS

from pipeline_router import CsvKGDataMatcher
from .expectations import load_expectations


class Neo4jKGDataMatcher(CsvKGDataMatcher):
    """Load normalized matcher tables from datagraph/v1, then reuse all business logic."""

    # The update728 data backend may be imported with either capitalized labels
    # (Project/Study/...) or lowercase labels (project/study/...). Resolve the
    # actual label present in the connected database instead of assuming one case.
    _LEGACY_LABEL_ALIASES = {
        "Project": ("Project", "project"),
        "Study": ("Study", "study"),
        "Sample": ("Sample", "sample"),
        "Individual": ("Individual", "individual"),
        "T1": ("T1", "t1"),
        "T2": ("T2", "t2"),
        "Modal": ("Modal", "modal"),
    }
    _LEGACY_CORE_LABELS = ("Project", "Study", "Sample", "Individual", "T1", "T2")

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
        self.expectations = load_expectations()
        self.snapshot_id = snapshot_id or os.environ.get("DATAGRAPH_SNAPSHOT_ID") or self.expectations["snapshot_id"]
        expected_from_env = os.environ.get("DATAGRAPH_NODE_COUNT")
        self.expected_node_count = int(expected_from_env) if expected_from_env else self.expectations["node_count"]
        self.schema_mode = os.environ.get("DATAGRAPH_SCHEMA_MODE", "auto").strip().lower()
        if self.schema_mode not in {"auto", "managed-v1", "legacy-update728"}:
            raise RuntimeError(
                "unsupported DATAGRAPH_SCHEMA_MODE; expected auto, managed-v1, or legacy-update728"
            )
        if not self.uri or not self.database or not self.password:
            raise RuntimeError("Neo4j data matcher is not configured")
        self.legacy_labels: Dict[str, Optional[str]] = {}
        self.count_drift: Dict[str, Dict[str, int]] = {}
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
            if snapshots and self.schema_mode != "legacy-update728":
                self._load_managed_graph(session, snapshots)
            elif self.schema_mode != "managed-v1":
                self._load_legacy_graph(session)
            else:
                raise RuntimeError("managed datagraph snapshot is missing")
            self._build_common_indexes(session)

    def _load_managed_graph(self, session: Any, snapshots: List[Dict[str, Any]]) -> None:
        expected = [{"snapshot_id": self.snapshot_id, "count": self.expected_node_count}]
        if snapshots != expected:
            raise RuntimeError(
                f"Neo4j data graph snapshot mismatch: expected {expected}, got {snapshots}"
            )
        self.backend_schema = "managed-v1"
        self.data_schema = "normalized-v2"
        self.study = self._load_source_entities(session, "study")
        self.project = self._load_source_entities(session, "project")
        self.sample = self._load_source_entities(session, "sample")
        self.individual = self._load_source_entities(session, "individual")
        self.t2 = self._load_source_entities(session, "t2")
        self.sample_specimen_types = {
            row.get("sample_accession"): row.get("specimen_types") or row.get("specimen_type") or ""
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
            self.t1.append(self._adapt_t1(dict(record["p"])))

    @staticmethod
    def _load_legacy_nodes(session: Any, label: str) -> List[Dict[str, Any]]:
        result = session.run(
            f"MATCH (n:`{label}`) RETURN properties(n) AS p ORDER BY elementId(n)"
        )
        return [dict(record["p"]) for record in result]

    @staticmethod
    def _warn(message: str) -> None:
        # stdout is reserved for the MCP JSON-RPC stream, so diagnostics go to stderr.
        print(f"[neo4j-matcher] {message}", file=sys.stderr)

    def _resolve_legacy_labels(self, session: Any) -> Dict[str, Optional[str]]:
        present = {
            str(record["label"])
            for record in session.run("CALL db.labels() YIELD label RETURN label")
        }
        resolved: Dict[str, Optional[str]] = {}
        for logical, aliases in self._LEGACY_LABEL_ALIASES.items():
            resolved[logical] = next((name for name in aliases if name in present), None)
        return resolved

    def _legacy_label_counts(
        self, session: Any, labels: Mapping[str, Optional[str]]
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for logical in self.expectations["legacy_backend"]["label_counts"]:
            label = labels.get(logical)
            if not label:
                counts[logical] = 0
                continue
            record = session.run(
                f"MATCH (n:`{label}`) RETURN count(n) AS count"
            ).single()
            counts[logical] = int(record["count"] if record else 0)
        return counts

    def _load_legacy_graph(self, session: Any) -> None:
        labels = self._resolve_legacy_labels(session)
        self.legacy_labels = labels
        missing = [name for name in self._LEGACY_CORE_LABELS if not labels.get(name)]
        if missing:
            raise RuntimeError(
                f"legacy update728 graph is missing required labels {missing}; "
                "the connected database does not look like the update728 data backend"
            )
        expected_counts = self.expectations["legacy_backend"]["label_counts"]
        actual_counts = self._legacy_label_counts(session, labels)
        empty = sorted(
            name for name in self._LEGACY_CORE_LABELS if actual_counts.get(name, 0) == 0
        )
        if empty:
            raise RuntimeError(
                f"legacy update728 graph has empty core labels {empty}; actual={actual_counts}"
            )
        # Adapt to whatever the data provider actually imported: a count that differs
        # from the agreed contract is recorded and warned about, not treated as fatal.
        self.count_drift = {
            name: {"expected": expected_counts[name], "actual": actual_counts.get(name, 0)}
            for name in expected_counts
            if actual_counts.get(name, 0) != expected_counts[name]
        }
        if self.count_drift:
            self._warn(
                "legacy label counts differ from the update728 contract; adapting to the "
                "connected graph anyway: "
                + json.dumps(self.count_drift, ensure_ascii=False)
            )
        self.backend_schema = "legacy-update728"
        self.data_schema = "legacy-update728"
        self.project = self._load_legacy_nodes(session, labels["Project"])
        self.study = self._load_legacy_nodes(session, labels["Study"])
        self.sample = self._load_legacy_nodes(session, labels["Sample"])
        self.individual = self._load_legacy_nodes(session, labels["Individual"])
        self.sample_specimen_types = {
            str(row.get("sample_accession") or ""): str(
                row.get("specimen_types") or row.get("specimen_type") or ""
            )
            for row in self.sample
            if row.get("sample_accession")
        }
        self.t2 = []
        for row in self._load_legacy_nodes(session, labels["T2"]):
            t2_id = str(row.get("T2_id") or row.get("t2_id") or "")
            file_name = str(
                row.get("sub_file_name") or row.get("file_name") or t2_id
            )
            self.t2.append({
                **row,
                "t2_id": t2_id,
                "files": file_name,
                "file_name": file_name,
                "file_type": str(row.get("file_name") or row.get("format") or ""),
                "format": str(row.get("semantic_format") or row.get("format") or ""),
                "file_path": str(row.get("file_path") or file_name),
            })

        modal_strategy = {
            "WES": "WES",
            "RNA": "RNA-Seq",
            "sc-RNA": "scRNA-seq",
            "Clinical": "Clinical",
            "Meta": "Meta",
        }
        self.t1 = []
        t1_label = labels["T1"]
        study_label = labels["Study"]
        modal_label = labels.get("Modal") or "Modal"
        result = session.run(
            f"MATCH (n:`{t1_label}`) "
            f"OPTIONAL MATCH (n)-[:IN_STUDY]->(study:`{study_label}`) "
            f"OPTIONAL MATCH (n)-[:IN_MODAL]->(modal:`{modal_label}`) "
            "RETURN properties(n) AS p,coalesce(n.T1_id,n.t1_id,n.files) AS t1_sort,"
            "collect(DISTINCT study.study_accession) AS studies,"
            "collect(DISTINCT modal.modal) AS modals "
            "ORDER BY t1_sort"
        )
        for record in result:
            row = dict(record["p"])
            studies = sorted(str(value) for value in (record["studies"] or []) if value)
            modals = sorted(str(value) for value in (record["modals"] or []) if value)
            strategy = next((modal_strategy[value] for value in modals if value in modal_strategy), "")
            row.update({
                "files": str(row.get("T1_id") or row.get("files") or ""),
                "study_accession": str(row.get("study_accession") or (studies[0] if studies else "")),
                "strategy": str(row.get("strategy") or strategy),
                "data_type": str(row.get("data_type") or strategy),
                "read_pair": str(row.get("read_pair") or self._guess_read_pair(str(row.get("file_name") or ""))),
            })
            self.t1.append(self._adapt_t1(row))

    def _adapt_t1(self, row: Mapping[str, Any]) -> Dict[str, Any]:
        sample_accession = str(row.get("sample_accession") or "")
        file_id = str(row.get("files") or row.get("T1_id") or "")
        file_name = str(row.get("file_name") or file_id)
        return {
            "study_accession": str(row.get("study_accession") or ""),
            "sample_accession": sample_accession,
            "run_accession": str(row.get("run_accession") or ""),
            "data_type": str(row.get("data_type") or row.get("strategy") or ""),
            "Read Pair": str(row.get("read_pair") or self._guess_read_pair(file_name)),
            "file_id": file_id,
            "file_name": file_name,
            "files": file_name,
            "format": str(row.get("semantic_format") or row.get("format") or ""),
            "file_path": str(row.get("file_path") or file_name),
            "file_description": str(row.get("file_description") or row.get("sample_description") or ""),
            "Experiment": str(row.get("experiment_accession") or ""),
            "Platform": str(row.get("platform") or ""),
            "data_level": str(row.get("data_level") or ""),
            "strategy": str(row.get("strategy") or row.get("data_type") or ""),
            "individual_accession": str(row.get("individual_accession") or ""),
            "individual_name": str(row.get("individual_name") or ""),
            "sample_name": str(row.get("sample_name") or ""),
            "specimen_types": self.sample_specimen_types.get(sample_accession, ""),
            "gender": str(row.get("gender") or ""),
        }

    def _build_common_indexes(self, session: Any) -> None:
        self.project_by_study = {}
        for row in self.project:
            studies = str(row.get("study_accession") or "").replace("，", ",").split(",")
            for study in studies:
                study = study.strip()
                if study and study not in self.project_by_study:
                    self.project_by_study[study] = row
        projects_by_id = {row.get("project_accession"): row for row in self.project}
        if self.backend_schema == "managed-v1":
            relation_query = (
                "MATCH (s:study)-[:IN_PROJECT]->(p:project) "
                "WHERE s.datagraph_managed = true AND p.datagraph_managed = true "
                "RETURN s.study_accession AS study_accession,p.project_accession AS project_accession"
            )
        else:
            relation_query = (
                "MATCH (s:Study)-[:IN_PROJECT]->(p:Project) "
                "RETURN s.study_accession AS study_accession,p.project_accession AS project_accession"
            )
        for relation in session.run(relation_query):
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
