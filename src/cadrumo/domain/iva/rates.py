"""Read-only IVA rate projections from the published registry authority.

:func:`load_iva_rate_table` projects the signed ``iva-rate-schedule`` fact
into mappings from :class:`EUMemberState` to dated :class:`IvaRateRecord`
windows partitioned by :class:`IvaRateKind`.  It does not read authoring TOML.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING

from ..calculations.registry.facts.resolution import ResolvedMappingFact
from ..calculations.registry.facts.schema import MappingFactPayload
from ..calculations.registry.iva_rate_kind_catalogue import require_iva_rate_kind
from .errors import IvaCatalogueError
from .schema import EUMemberState, IvaRateRecord, require_eu_member_state

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.governed_fact_scope import GovernedFactSource

IVA_RATE_FACT_ID = "iva-rate-schedule"
"""Jurisdictions that must carry rate rows.

``XI`` is a Northern Ireland IVA prefix for goods, not a state with its own IVA
rate table, so it is intentionally excluded from the rate-registry completeness
gate.
"""


def load_iva_rate_table(
    *,
    operation: PinnedAuthorityOperation,
) -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
    """Return IVA rates projected from the installed authority artifact.

    Rate TOML is authoring input.  A caller cannot redirect the shipped runtime
    at an arbitrary source tree: publication is the only route to changed rates.
    """
    fact = operation.governed_fact(IVA_RATE_FACT_ID)
    table: dict[EUMemberState, list[IvaRateRecord]] = {}
    for variant in fact.variants:
        if not isinstance(variant.payload, MappingFactPayload):
            raise IvaCatalogueError("IVA rate fact contains a non-mapping variant")
        selectors = {selector.name: selector.value for selector in variant.selectors}
        if "member_state" not in selectors or "kind" not in selectors:
            continue
        if variant.valid_from is None:
            raise IvaCatalogueError("IVA rate variant has no effective start date")
        member_state = require_eu_member_state(
            str(selectors["member_state"]),
            effective_date=variant.valid_from,
            authority=operation,
        )
        payload = {str(entry.key): entry.value for entry in variant.payload.entries}
        table.setdefault(member_state, []).append(
            IvaRateRecord(
                member_state=member_state,
                kind=require_iva_rate_kind(
                    str(selectors["kind"]),
                    effective_date=variant.valid_from,
                    authority=operation,
                ),
                pct=Decimal(str(payload["pct"])),
                effective_from=variant.valid_from,
                effective_until=variant.valid_to,
                legal_refs=variant.legal_refs,
                source_refs=variant.source_refs,
                supersedes_tier_default=bool(payload["supersedes_tier_default"]),
            )
        )
    return MappingProxyType({state: tuple(records) for state, records in table.items()})


def rate_record_from_fact(
    resolved: ResolvedMappingFact,
    *,
    authority: GovernedFactSource,
) -> IvaRateRecord:
    """Project an authority result onto the retained public record."""
    selectors = {selector.name: selector.value for selector in resolved.matched_selectors}
    payload = {str(entry.key): entry.value for entry in resolved.payload.entries}
    return IvaRateRecord(
        member_state=require_eu_member_state(
            str(selectors["member_state"]),
            effective_date=resolved.effective_date,
            authority=authority,
        ),
        kind=require_iva_rate_kind(
            str(selectors["kind"]),
            effective_date=resolved.effective_date,
            authority=authority,
        ),
        pct=Decimal(str(payload["pct"])),
        effective_from=resolved.valid_from,
        effective_until=resolved.valid_to,
        legal_refs=resolved.legal_refs,
        source_refs=resolved.source_refs,
        supersedes_tier_default=bool(payload["supersedes_tier_default"]),
    )


__all__ = [
    "IVA_RATE_FACT_ID",
    "load_iva_rate_table",
    "rate_record_from_fact",
]
