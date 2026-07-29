"""Shared runtime configuration for the Web and MCP entry points."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional
from urllib.parse import urlparse


HERE = Path(__file__).resolve().parent
LOCAL_ENV = HERE / ".env.local"

DEFAULTS = {
    "FORCE_RULE": "0",
    "LLM_MODE": "api",
    "LLM_BASE_URL": "https://api.deepseek.com/chat/completions",
    "LLM_MODEL": "deepseek-v4-pro",
    "LLM_TIMEOUT": "180",
    "LLM_REQUIRED": "0",
    "LLM_THINKING": "enabled",
    "LLM_REASONING_EFFORT": "high",
    "LLM_MAX_TOKENS": "16000",
    "NEO4J_URI": "bolt://127.0.0.1:7687",
    "NEO4J_USER": "neo4j",
    "NEO4J_DATABASE": "neo4j",
    "NEO4J_CONNECT_TIMEOUT": "2",
    "NEO4J_QUERY_TIMEOUT": "2",
    "NEO4J_HEALTH_CACHE_TTL": "30",
    "DATA_MATCHER_MODE": "csv",
    "DATAGRAPH_SNAPSHOT_ID": "dg-b23135d49c950d0846a563bc",
    "DATA_MATCHER_DIFF_PATH": "docs/data_matcher_compare_runtime.jsonl",
}

_status_lock = threading.Lock()
_llm_last_status = "not_called"


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_local_env(
    path: Path = LOCAL_ENV,
    environ: Optional[MutableMapping[str, str]] = None,
) -> Dict[str, str]:
    """Load KEY=VALUE lines without replacing explicit process variables."""
    target = environ if environ is not None else os.environ
    loaded: Dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, OSError):
        return loaded
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not key.replace("_", "a").isalnum():
            continue
        if key not in target:
            target[key] = _unquote(value)
            loaded[key] = target[key]
    return loaded


def initialize_runtime(
    path: Path = LOCAL_ENV,
    environ: Optional[MutableMapping[str, str]] = None,
) -> Mapping[str, str]:
    target = environ if environ is not None else os.environ
    load_local_env(path=path, environ=target)
    for key, value in DEFAULTS.items():
        target.setdefault(key, value)
    return target


def env_flag(name: str, default: bool = False) -> bool:
    fallback = "1" if default else "0"
    return (os.environ.get(name, fallback) or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def endpoint_host(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    parsed = urlparse(value)
    return parsed.hostname or None


def set_llm_last_status(status: str) -> None:
    global _llm_last_status
    with _status_lock:
        _llm_last_status = str(status or "unknown")


def get_llm_health(environ: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    env = environ if environ is not None else os.environ
    configured = bool(env.get("LLM_API_KEY") and env.get("LLM_BASE_URL") and env.get("LLM_MODEL"))
    with _status_lock:
        status = _llm_last_status
    force_rule = (env.get("FORCE_RULE", "0") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if force_rule:
        status = "force_rule"
    elif not configured and status == "not_called":
        status = "not_configured"
    return {
        "configured": configured,
        "model": env.get("LLM_MODEL"),
        "endpoint_host": endpoint_host(env.get("LLM_BASE_URL")),
        "last_status": status,
    }


initialize_runtime()
