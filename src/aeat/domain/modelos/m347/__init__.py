"""Modelo 347 typed record schema and per-year manifests."""

from __future__ import annotations

from ._records import ClaveOperacion, Modelo347RecordLine, Modelo347SchemaManifest
from ._rules_2024 import MANIFEST_2024
from ._rules_2025 import MANIFEST_2025
from ._rules_2026 import MANIFEST_2026

__all__ = [
    "MANIFEST_2024",
    "MANIFEST_2025",
    "MANIFEST_2026",
    "ClaveOperacion",
    "Modelo347RecordLine",
    "Modelo347SchemaManifest",
]
