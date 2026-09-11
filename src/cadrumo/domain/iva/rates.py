"""Read-only IVA rate projections from the published registry authority.

:func:`load_iva_rate_table` projects the signed ``iva-rate-schedule`` fact
into mappings from :class:`EUMemberState` to dated :class:`IvaRateRecord`
windows partitioned by :class:`IvaRateKind`.  It does not read authoring TOML.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from types import MappingProxyType

from ..calculations.registry.facts.resolution import ResolvedMappingFact
from ..calculations.registry.facts.schema import MappingFactPayload
from .errors import IvaCatalogueError
from .schema import EUMemberState, IvaRateKind, IvaRateRecord

IVA_RATE_FACT_ID = "iva-rate-schedule"
"""Jurisdictions that must carry rate rows.

``XI`` is a Northern Ireland IVA prefix for goods, not a state with its own IVA
rate table, so it is intentionally excluded from the rate-registry completeness
gate.
"""


def load_iva_rate_table() -> Mapping[EUMemberState, tuple[IvaRateRecord, ...]]:
    """Return IVA rates projected from the installed authority artifact.

    Rate TOML is authoring input.  A caller cannot redirect the shipped runtime
    at an arbitrary source tree: publication is the only route to changed rates.
    """
    from ..calculations.registry.authority import bundled_authority

    fact = bundled_authority().catalogues.facts.facts.get(IVA_RATE_FACT_ID)
    if fact is None:
        raise IvaCatalogueError("installed authority has no IVA rate facts")
    table: dict[EUMemberState, list[IvaRateRecord]] = {}
    for variant in fact.variants:
        if not isinstance(variant.payload, MappingFactPayload):
            raise IvaCatalogueError("IVA rate fact contains a non-mapping variant")
        selectors = {selector.name: selector.value for selector in variant.selectors}
        member_state = EUMemberState(str(selectors["member_state"]))
        payload = {str(entry.key): entry.value for entry in variant.payload.entries}
        table.setdefault(member_state, []).append(
            IvaRateRecord(
                member_state=member_state,
                kind=IvaRateKind(str(selectors["kind"])),
                pct=Decimal(str(payload["pct"])),
                effective_from=variant.valid_from,
                effective_until=variant.valid_to,
                legal_refs=variant.legal_refs,
                source_refs=variant.source_refs,
                supersedes_tier_default=bool(payload["supersedes_tier_default"]),
            )
        )
    return MappingProxyType({state: tuple(records) for state, records in table.items()})


def iva_rate_record_from_fact(resolved: ResolvedMappingFact) -> IvaRateRecord:
    """Project an authority result onto the retained public record."""
    selectors = {selector.name: selector.value for selector in resolved.matched_selectors}
    payload = {str(entry.key): entry.value for entry in resolved.payload.entries}
    return IvaRateRecord(
        member_state=EUMemberState(str(selectors["member_state"])),
        kind=IvaRateKind(str(selectors["kind"])),
        pct=Decimal(str(payload["pct"])),
        effective_from=resolved.valid_from,
        effective_until=resolved.valid_to,
        legal_refs=resolved.legal_refs,
        source_refs=resolved.source_refs,
        supersedes_tier_default=bool(payload["supersedes_tier_default"]),
    )


__all__ = [
    "IVA_RATE_FACT_ID",
    "iva_rate_record_from_fact",
    "load_iva_rate_table",
]
