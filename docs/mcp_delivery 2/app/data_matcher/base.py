"""Shared matcher interface."""

from __future__ import annotations

from typing import Any, Dict, Protocol, Sequence, runtime_checkable


@runtime_checkable
class DataMatcher(Protocol):
    def match(
        self,
        intent: Dict[str, Any],
        pipelines: Sequence[Dict[str, Any]],
        limit: int = 10,
    ) -> Dict[str, Any]: ...

    def match_custom_roles(
        self,
        intent: Dict[str, Any],
        required_roles: Sequence[str],
        limit: int = 10,
    ) -> Dict[str, Any]: ...
