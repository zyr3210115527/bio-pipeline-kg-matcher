"""Read-only Neo4j health and pipeline evidence queries for the demo."""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence


VERSION_QUERY = "CALL dbms.components() YIELD versions RETURN versions[0] AS version LIMIT 1"
NODE_COUNT_QUERY = "MATCH (n) RETURN count(n) AS node_count"
RELATIONSHIP_COUNT_QUERY = "MATCH ()-[r]->() RETURN count(r) AS relationship_count"
LABEL_COUNT_QUERY = (
    "MATCH (n) UNWIND labels(n) AS label "
    "RETURN label, count(*) AS count ORDER BY count DESC, label"
)
EVIDENCE_QUERY = """
UNWIND $tool_ids AS requested_id
OPTIONAL MATCH (tool {tool_id: requested_id})
WHERE 'Tool' IN labels(tool) OR 'tool_id' IN labels(tool)
OPTIONAL MATCH (tool)-[relationship]-(neighbor)
RETURN requested_id AS tool_id,
       tool IS NOT NULL AS matched,
       properties(tool) AS tool_properties,
       type(relationship) AS relationship_type,
       CASE
         WHEN relationship IS NULL THEN null
         WHEN startNode(relationship) = tool THEN 'outgoing'
         ELSE 'incoming'
       END AS direction,
       labels(neighbor) AS neighbor_labels,
       properties(neighbor) AS neighbor_properties
ORDER BY tool_id, relationship_type
LIMIT 300
""".strip()

TOOL_CATALOG_QUERY = """
MATCH (tool:tool_id)
WHERE tool.catalog_id IS NOT NULL
RETURN properties(tool) AS tool
ORDER BY tool.catalog_id
""".strip()

TOOL_SLOT_QUERY = """
MATCH (tool:tool_id)-[edge:HAS_INPUT_SLOT|HAS_OUTPUT_SLOT]->(slot:io_slot)
WHERE tool.catalog_id IS NOT NULL
OPTIONAL MATCH (slot)-[:REQUIRES|PRODUCES]->(artifact:artifact_type)
OPTIONAL MATCH (slot)-[:ALLOW_FORMAT]->(format:format)
RETURN tool.tool_id AS tool_id,
       tool.catalog_id AS catalog_id,
       type(edge) AS edge_type,
       properties(slot) AS slot,
       collect(DISTINCT artifact.artifact_type) AS artifacts,
       collect(DISTINCT format.format) AS formats
ORDER BY catalog_id, edge_type, slot.slot_id
""".strip()

TOOL_NEXT_QUERY = """
MATCH (source:tool_id)-[edge:NEXT {source:'curated-next-csv'}]->(target:tool_id)
RETURN source.tool_id AS source_tool_id,
       target.tool_id AS target_tool_id,
       source.catalog_id AS source_catalog_id,
       target.catalog_id AS target_catalog_id,
       edge.kind AS kind,
       edge.output AS output,
       edge.input AS input
ORDER BY source.catalog_id, target.catalog_id
""".strip()

PIPELINE_STEP_QUERY = """
MATCH (pipeline:tool_id)-[edge:HAS_STEP]->(method:tool_id)
WHERE pipeline.catalog_id IS NOT NULL AND method.catalog_id IS NOT NULL
RETURN pipeline.tool_id AS pipeline_id,
       method.tool_id AS tool_id,
       edge.step_id AS step_id,
       edge.order AS step_order,
       edge.depends_on AS depends_on,
       edge.locked AS locked,
       edge.source AS source
ORDER BY pipeline_id, step_order, step_id
""".strip()


def _float_env(name: str, default: float) -> float:
    try:
        return max(0.1, float(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


def _record_value(record: Any, key: str, default: Any = None) -> Any:
    if record is None:
        return default
    try:
        return record.get(key, default)
    except AttributeError:
        try:
            return record[key]
        except (KeyError, TypeError):
            return default


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_value(v) for v in value]
    return str(value)


def _safe_error(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    if "auth" in name or "security" in name or "unauthorized" in name:
        return "authentication_failed"
    if "timeout" in name or "serviceunavailable" in name:
        return "connection_timeout"
    if isinstance(exc, (ModuleNotFoundError, ImportError)):
        return "driver_unavailable"
    return "connection_failed"


class Neo4jClient:
    """Lazy, thread-safe read-only client for the runtime Neo4j tool catalog."""

    def __init__(
        self,
        *,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        connect_timeout: Optional[float] = None,
        query_timeout: Optional[float] = None,
        cache_ttl: Optional[float] = None,
        driver_factory: Optional[Callable[..., Any]] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687")
        self.user = user or os.environ.get("NEO4J_USER", "neo4j")
        self.password = password if password is not None else os.environ.get("NEO4J_PASSWORD")
        self.database = database or os.environ.get("NEO4J_DATABASE", "neo4j")
        self.connect_timeout = connect_timeout or _float_env("NEO4J_CONNECT_TIMEOUT", 2.0)
        self.query_timeout = query_timeout or _float_env("NEO4J_QUERY_TIMEOUT", 2.0)
        self.cache_ttl = cache_ttl or _float_env("NEO4J_HEALTH_CACHE_TTL", 30.0)
        self._driver_factory = driver_factory
        self._query_factory: Optional[Callable[..., Any]] = None
        self._read_access: Any = "READ"
        self._driver: Any = None
        self._clock = clock
        self._lock = threading.Lock()
        self._health_cache: Optional[Dict[str, Any]] = None
        self._health_cached_at = 0.0

    def _base_health(self) -> Dict[str, Any]:
        return {
            "connected": False,
            "version": None,
            "database": self.database,
            "latency_ms": None,
            "node_count": None,
            "relationship_count": None,
            "label_counts": {},
            "error": None,
        }

    def _get_driver(self) -> Any:
        if self._driver is not None:
            return self._driver
        with self._lock:
            if self._driver is not None:
                return self._driver
            if not self.password:
                raise RuntimeError("neo4j_password_missing")
            if self._driver_factory is None:
                from neo4j import GraphDatabase, Query, READ_ACCESS

                self._driver_factory = GraphDatabase.driver
                self._query_factory = Query
                self._read_access = READ_ACCESS
            self._driver = self._driver_factory(
                self.uri,
                auth=(self.user, self.password),
                connection_timeout=self.connect_timeout,
                connection_acquisition_timeout=self.connect_timeout,
                max_connection_pool_size=5,
            )
            return self._driver

    def _query(self, text: str) -> Any:
        if self._query_factory is None:
            return text
        return self._query_factory(text, timeout=self.query_timeout)

    def _single(self, session: Any, query: str) -> Any:
        return session.run(self._query(query)).single()

    def health(self, force: bool = False) -> Dict[str, Any]:
        now = self._clock()
        with self._lock:
            if (
                not force
                and self._health_cache is not None
                and now - self._health_cached_at < self.cache_ttl
            ):
                return dict(self._health_cache)

        health = self._base_health()
        started = self._clock()
        if not self.password:
            health["error"] = "not_configured"
            return self._store_health(health, now)
        try:
            driver = self._get_driver()
            driver.verify_connectivity()
            with driver.session(database=self.database, default_access_mode=self._read_access) as session:
                version_record = self._single(session, VERSION_QUERY)
                node_record = self._single(session, NODE_COUNT_QUERY)
                relationship_record = self._single(session, RELATIONSHIP_COUNT_QUERY)
                label_records = list(session.run(self._query(LABEL_COUNT_QUERY)))
            health.update({
                "connected": True,
                "version": _record_value(version_record, "version"),
                "latency_ms": round((self._clock() - started) * 1000, 1),
                "node_count": _record_value(node_record, "node_count", 0),
                "relationship_count": _record_value(
                    relationship_record, "relationship_count", 0
                ),
                "label_counts": {
                    str(_record_value(row, "label")): int(_record_value(row, "count", 0))
                    for row in label_records
                    if _record_value(row, "label")
                },
            })
        except RuntimeError as exc:
            health["error"] = (
                "not_configured" if str(exc) == "neo4j_password_missing" else _safe_error(exc)
            )
        except Exception as exc:
            health["error"] = _safe_error(exc)
        return self._store_health(health, now)

    def _store_health(self, health: Dict[str, Any], timestamp: float) -> Dict[str, Any]:
        with self._lock:
            self._health_cache = dict(health)
            self._health_cached_at = timestamp
        return dict(health)

    def evidence(self, tool_ids: Iterable[str]) -> Dict[str, Any]:
        requested = list(dict.fromkeys(str(item) for item in tool_ids if item))
        result: Dict[str, Any] = {
            "source": "neo4j-runtime",
            "connected": False,
            "matched_tool_ids": [],
            "missing_tool_ids": requested,
            "slot_evidence": [],
            "query_ms": None,
            "error": None,
        }
        health = self.health()
        if not health["connected"]:
            result["error"] = health["error"]
            return result
        if not requested:
            result.update({"connected": True, "missing_tool_ids": [], "query_ms": 0.0})
            return result

        started = self._clock()
        try:
            driver = self._get_driver()
            with driver.session(database=self.database, default_access_mode=self._read_access) as session:
                rows = list(session.run(self._query(EVIDENCE_QUERY), tool_ids=requested))
            matched = []
            evidence: List[Dict[str, Any]] = []
            for row in rows:
                tool_id = str(_record_value(row, "tool_id") or "")
                if _record_value(row, "matched") and tool_id and tool_id not in matched:
                    matched.append(tool_id)
                relationship_type = _record_value(row, "relationship_type")
                neighbor_properties = _record_value(row, "neighbor_properties")
                if relationship_type or neighbor_properties:
                    evidence.append({
                        "tool_id": tool_id,
                        "relationship_type": relationship_type,
                        "direction": _record_value(row, "direction"),
                        "neighbor_labels": _json_value(
                            _record_value(row, "neighbor_labels", []) or []
                        ),
                        "neighbor": _json_value(neighbor_properties or {}),
                    })
            result.update({
                "connected": True,
                "matched_tool_ids": [item for item in requested if item in matched],
                "missing_tool_ids": [item for item in requested if item not in matched],
                "slot_evidence": evidence,
                "query_ms": round((self._clock() - started) * 1000, 1),
            })
        except Exception as exc:
            result["error"] = _safe_error(exc)
        return result

    def tool_catalog(self) -> Dict[str, Any]:
        """Return the Neo4j-backed tool, slot and reviewed NEXT catalog."""
        result: Dict[str, Any] = {
            "source": "neo4j",
            "connected": False,
            "tools": [],
            "next_edges": [],
            "pipeline_steps": [],
            "error": None,
        }
        health = self.health()
        if not health["connected"]:
            result["error"] = health["error"]
            return result
        try:
            driver = self._get_driver()
            with driver.session(
                database=self.database, default_access_mode=self._read_access
            ) as session:
                tool_rows = list(session.run(self._query(TOOL_CATALOG_QUERY)))
                slot_rows = list(session.run(self._query(TOOL_SLOT_QUERY)))
                next_rows = list(session.run(self._query(TOOL_NEXT_QUERY)))
                pipeline_step_rows = list(session.run(self._query(PIPELINE_STEP_QUERY)))
            tools: Dict[str, Dict[str, Any]] = {}
            for row in tool_rows:
                properties = _json_value(_record_value(row, "tool", {}) or {})
                tool_id = str(properties.get("tool_id") or "")
                if not tool_id:
                    continue
                tools[tool_id] = {**properties, "inputs": [], "outputs": []}
            for row in slot_rows:
                tool_id = str(_record_value(row, "tool_id") or "")
                if tool_id not in tools:
                    continue
                slot = _json_value(_record_value(row, "slot", {}) or {})
                slot["artifacts"] = _json_value(
                    _record_value(row, "artifacts", []) or []
                )
                slot["formats"] = _json_value(
                    _record_value(row, "formats", []) or []
                )
                key = (
                    "inputs"
                    if _record_value(row, "edge_type") == "HAS_INPUT_SLOT"
                    else "outputs"
                )
                tools[tool_id][key].append(slot)
            next_edges = [
                {
                    "source_tool_id": _record_value(row, "source_tool_id"),
                    "target_tool_id": _record_value(row, "target_tool_id"),
                    "source_catalog_id": _record_value(row, "source_catalog_id"),
                    "target_catalog_id": _record_value(row, "target_catalog_id"),
                    "kind": _record_value(row, "kind"),
                    "output": _record_value(row, "output"),
                    "input": _record_value(row, "input"),
                }
                for row in next_rows
            ]
            result.update({
                "connected": True,
                "tools": list(tools.values()),
                "next_edges": next_edges,
                "pipeline_steps": [
                    {
                        "pipeline_id": _record_value(row, "pipeline_id"),
                        "tool_id": _record_value(row, "tool_id"),
                        "step_id": _record_value(row, "step_id"),
                        "step_order": _record_value(row, "step_order"),
                        "depends_on": _json_value(
                            _record_value(row, "depends_on", []) or []
                        ),
                        "locked": bool(_record_value(row, "locked")),
                        "source": _record_value(row, "source"),
                    }
                    for row in pipeline_step_rows
                ],
            })
        except Exception as exc:
            result["error"] = _safe_error(exc)
        return result

    def close(self) -> None:
        with self._lock:
            driver, self._driver = self._driver, None
            self._health_cache = None
        if driver is not None:
            driver.close()
