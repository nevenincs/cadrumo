"""Tax-route primitives for modelo applicability."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from enum import StrEnum

from ...contribuyente.entity_type import (
    EntityType,
    entity_type_attribution_entity_token,
    entity_type_legal_entity_token,
    entity_type_natural_person_token,
    entity_type_tokens,
)

__all__ = ["TAX_ROUTE_FOR_ENTITY_TYPE", "TaxRoute", "tax_route_for_entity_type"]


class TaxRoute(StrEnum):
    """The tax branch a taxpayer profile routes to."""

    IRPF = "irpf"
    IMPUESTO_SOCIEDADES = "impuesto_sociedades"
    ATTRIBUTION_PASS_THROUGH = "attribution_pass_through"  # noqa: S105 - tax route token, not a secret
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


class _TaxRouteByEntityType(Mapping[EntityType, TaxRoute]):
    """Lazy compatibility mapping backed by the typed registry projection."""

    def __getitem__(self, entity_type: EntityType) -> TaxRoute:
        return tax_route_for_entity_type(entity_type)

    def __iter__(self) -> Iterator[EntityType]:
        return iter(entity_type_tokens())

    def __len__(self) -> int:
        return len(entity_type_tokens())


TAX_ROUTE_FOR_ENTITY_TYPE: Mapping[EntityType, TaxRoute] = _TaxRouteByEntityType()
