"""Generic adapter for registry-projected IVA component rows.

Concrete category/kind rows, legal references, labels, and ordering belong to
the canonical registry. This private module retains only the mechanical
conversion boundary used by callers that already queried that registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .components import IvaCategoryComponents


def component_row_from_registry(payload: Mapping[str, Any]) -> IvaCategoryComponents:
    """Validate one registry-projected component row as the typed model."""
    return IvaCategoryComponents.model_validate(dict(payload))


__all__ = ["component_row_from_registry"]
