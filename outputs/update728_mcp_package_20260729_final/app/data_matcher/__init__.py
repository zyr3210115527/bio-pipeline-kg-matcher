"""Data-asset matcher backends with one stable result contract."""

from .base import DataMatcher
from .factory import build_data_matcher

__all__ = ["DataMatcher", "build_data_matcher"]
