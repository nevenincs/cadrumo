"""Tax-route primitives for modelo applicability."""

from __future__ import annotations

from enum import StrEnum, auto

from ...contribuyente.entity_type import (
    EntityType,
    entity_type_attribution_entity_token,
    entity_type_legal_entity_token,
    entity_type_natural_person_token,
)

__all__ = ["TaxRoute", "tax_route_for_entity_type"]


class TaxRoute(StrEnum):
    """The tax branch a taxpayer profile routes to."""

    IRPF = "irpf"
    IMPUESTO_SOCIEDADES = "impuesto_sociedades"
    ATTRIBUTION_PASS_THROUGH = auto()
    INCOMPLETE = "incomplete"


def tax_route_for_entity_type(entity_type: EntityType) -> TaxRoute:
    """Resolve the tax route against the registry-declared entity tokens."""
    if entity_type == entity_type_natural_person_token():
        return TaxRoute.IRPF
    if entity_type == entity_type_legal_entity_token():
        return TaxRoute.IMPUESTO_SOCIEDADES
    if entity_type == entity_type_attribution_entity_token():
        return TaxRoute.ATTRIBUTION_PASS_THROUGH
    raise ValueError(f"entity type {entity_type!r} has no declared tax route")
