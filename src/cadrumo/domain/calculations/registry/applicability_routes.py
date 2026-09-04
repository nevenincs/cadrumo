"""Tax-route primitives for modelo applicability."""

from __future__ import annotations

from enum import StrEnum

from ...contribuyente.entity_type import EntityType

__all__ = ["TAX_ROUTE_FOR_ENTITY_TYPE", "TaxRoute"]


class TaxRoute(StrEnum):
    """The tax branch a taxpayer profile routes to."""

    IRPF = "irpf"
    IMPUESTO_SOCIEDADES = "impuesto_sociedades"
    ATTRIBUTION_PASS_THROUGH = "attribution_pass_through"  # noqa: S105 - tax route token, not a secret
    INCOMPLETE = "incomplete"


TAX_ROUTE_FOR_ENTITY_TYPE: dict[EntityType, TaxRoute] = {
    EntityType.NATURAL_PERSON: TaxRoute.IRPF,
    EntityType.LEGAL_ENTITY: TaxRoute.IMPUESTO_SOCIEDADES,
    EntityType.ATTRIBUTION_ENTITY: TaxRoute.ATTRIBUTION_PASS_THROUGH,
}
