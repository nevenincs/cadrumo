"""Generic adapter for registry-projected IVA component rows.

Concrete category/kind rows, legal references, labels, and ordering belong to
the canonical registry. This private module retains only the mechanical
conversion boundary used by callers that already queried that registry.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .components import IvaCategoryComponents, IvaComponentVocabulary, IvaCuotaSettlement


def component_row_from_registry(
    payload: Mapping[str, Any],
    *,
    cuota_settlement_no_token: IvaCuotaSettlement | None = None,
    component_vocabulary: IvaComponentVocabulary | None = None,
) -> IvaCategoryComponents:
    """Validate one registry-projected component row as the typed model."""
    context = None
    if cuota_settlement_no_token is not None or component_vocabulary is not None:
        context = {}
        if cuota_settlement_no_token is not None:
            context["cuota_settlement_no_token"] = cuota_settlement_no_token
        if component_vocabulary is not None:
            context["component_vocabulary"] = component_vocabulary
    return IvaCategoryComponents.model_validate(dict(payload), context=context)


__all__ = ["component_row_from_registry"]
