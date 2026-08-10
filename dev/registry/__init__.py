"""AEAT registry authoring-tree developer tooling (not shipped in the wheel)."""

from ._semantic_map import SemanticMap, SemanticMapAnchor, SemanticMapEntry, SemanticMapRecord
from ._semantic_map_loader import (
    SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION,
    SemanticMapFragment,
    load_semantic_map,
)

__all__ = [
    "SEMANTIC_MAP_FRAGMENT_SCHEMA_VERSION",
    "SemanticMap",
    "SemanticMapAnchor",
    "SemanticMapEntry",
    "SemanticMapFragment",
    "SemanticMapRecord",
    "load_semantic_map",
]
