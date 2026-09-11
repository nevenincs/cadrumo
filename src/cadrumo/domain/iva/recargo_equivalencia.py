"""Governed-fact resolution for LIVA art. 161 recargo de equivalencia rates.

The canonical ``iva-recargo-by-applied-rate`` mapping fact resolves the
legally grounded recargo pairing at the rate and operation-date coordinate.
The public lookup answers from the rate a line actually carried and the date
it carried it, returning provenance with the resolved fact when required.

The recargo de equivalencia regime (LIVA arts. 148-163) applies to
comerciantes minoristas (retailers) with limited annual revenue who
buy stock for resale; their suppliers charge them an additional
recargo on top of the regular IVA rate. The four rates align with
the four IVA tiers per LIVA art. 161:

* General (21 % IVA) → 5.2 % recargo (art. 161 1.º).
* Reduced (10 % IVA, art. 91 uno) → 1.4 % recargo (art. 161 2.º).
* Super-reduced (4 % IVA, art. 91 dos) → 0.5 % recargo (art. 161 3.º).
* Tobacco-specific → 1.75 % recargo (art. 161 4.º).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.unit_proportion import UnitProportion
from ..calculations.registry.facts.resolution import FactSelector, MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.schema_base import DateAxis
from .errors import IvaCatalogueError, IvaValidationError

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

IVA_RECARGO_FACT_ID = "iva-recargo-by-applied-rate"


class RecargoRateRecord(BaseModel):
    """One recargo de equivalencia rate, paired with the IVA rate it accompanies.

    Keyed on the accompanying IVA rate rather than on its tier. LIVA art. 161
    pairs each recargo with a tier, and that was a sufficient key only while a
    tier had exactly one rate. Between 2023-01-01 and 2024-09-30 the reduced
    tier carried both its ordinary 10 % and the transitional 5 %, with different
    recargos, so the tier no longer identifies the pairing and the rate does.

    Attributes:
        iva_rate: The IVA rate this recargo accompanies, as a fraction.
        recargo_rate: The recargo rate itself, as a fraction. Zero is a
            legitimate value and means a rate of zero, not an absent one.
        effective_from: First date the pairing applies.
        effective_until: Last date it applies, or ``None`` for open-ended.
        legal_refs: Registry legal-reference identities establishing the value.
        notes: Authoring note; carries no runtime meaning.
    """

    model_config = STRICT_FROZEN_CONFIG

    iva_rate: UnitProportion
    recargo_rate: Decimal = Field(ge=Decimal("0"), lt=Decimal("1"))
    effective_from: date
    effective_until: date | None = None
    legal_refs: tuple[str, ...] = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def _validate_window(self) -> RecargoRateRecord:
        if self.effective_until is not None and self.effective_from > self.effective_until:
            raise IvaValidationError(
                f"RecargoRateRecord[iva_rate={self.iva_rate}]: "
                f"effective_from {self.effective_from} is after effective_until {self.effective_until}",
            )
        return self

    def covers(self, on_date: date) -> bool:
        """Report whether this record's window contains ``on_date``."""
        if on_date < self.effective_from:
            return False
        return self.effective_until is None or on_date <= self.effective_until


def load_recargo_rate_table() -> tuple[RecargoRateRecord, ...]:
    """Return published recargo pairings from the authority artifact.

    The optional source path belongs to development publication only; accepting
    it in runtime would make an unsigned authoring tree a second authority.
    """
    from ..calculations.registry.authority import bundled_authority

    fact = bundled_authority().catalogues.facts.facts.get(IVA_RECARGO_FACT_ID)
    if fact is None:
        raise IvaCatalogueError("installed authority has no IVA recargo facts")
    records: list[RecargoRateRecord] = []
    for variant in fact.variants:
        selectors = {selector.name: selector.value for selector in variant.selectors}
        payload = {str(entry.key): entry.value for entry in variant.payload.entries}
        records.append(
            RecargoRateRecord(
                iva_rate=Decimal(str(selectors["applied_rate"])),
                recargo_rate=Decimal(str(payload["recargo_rate"])),
                effective_from=variant.valid_from,
                effective_until=variant.valid_to,
                legal_refs=variant.legal_refs,
                notes=str(payload["notes"]),
            )
        )
    return tuple(records)


def recargo_rate_for_applied_rate(applied_rate: Decimal, on_date: date) -> Decimal | None:
    """Return the recargo rate paired with ``applied_rate`` on ``on_date``.

    This is the lookup that can express the 2023-2024 transitional rates. Asked
    for 10 % inside that window it answers 1.4 %; asked for 5 % on the same date
    it answers 0.62 %. A tier-keyed lookup cannot separate those, because both
    rates sat on the reduced tier at once.

    Args:
        applied_rate: The IVA rate the line actually carried, as a fraction.
        on_date: The operation date, which selects among windowed pairings.

    Returns:
        The paired recargo rate, which may legitimately be zero. ``None`` when
        the table models no pairing for that rate on that date -- an unmodelled
        combination, which callers must not read as "no recargo applies".

    The tobacco rate is not reachable here: it attaches to a product rather
    than an accompanying IVA rate and remains a separately resolved governed
    fact.
    """
    if not _recargo_fact_candidate_exists(applied_rate, on_date):
        return None
    return recargo_rate_record_from_fact(resolve_recargo_rate_for_applied_rate(applied_rate, on_date)).recargo_rate


def resolve_recargo_rate_for_applied_rate(
    applied_rate: Decimal,
    on_date: date,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> ResolvedMappingFact:
    """Resolve the dated recargo pairing with its complete governed-fact provenance."""
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=IVA_RECARGO_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
            selectors=(FactSelector(name="applied_rate", value=applied_rate),),
        ),
    )
    return cast("ResolvedMappingFact", resolved)


def _recargo_fact_candidate_exists(
    applied_rate: Decimal,
    on_date: date,
    *,
    authority: ValidatedRegistryAuthority | None = None,
) -> bool:
    """Return false only for an unmodelled applied-rate/date pairing.

    A candidate still resolves through the authority afterwards, so any overlap
    or other invalid exact selection remains a loud fail-closed error rather
    than being mistaken for the public ``None`` sentinel.
    """
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    authority.validate_registry()
    fact = authority.catalogues.facts.facts.get(IVA_RECARGO_FACT_ID)
    if fact is None:
        return False
    return any(
        variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from <= on_date
        and (variant.valid_to is None or on_date <= variant.valid_to)
        and {selector.name: selector.value for selector in variant.selectors}.get("applied_rate") == applied_rate
        for variant in fact.variants
    )


def recargo_rate_record_from_fact(resolved: ResolvedMappingFact) -> RecargoRateRecord:
    """Project a provenance-bearing authority result onto the retained public record."""
    selectors = {selector.name: selector.value for selector in resolved.matched_selectors}
    payload = {str(entry.key): entry.value for entry in resolved.payload.entries}
    return RecargoRateRecord(
        iva_rate=Decimal(str(selectors["applied_rate"])),
        recargo_rate=Decimal(str(payload["recargo_rate"])),
        effective_from=resolved.valid_from,
        effective_until=resolved.valid_to,
        legal_refs=resolved.legal_refs,
        notes=str(payload["notes"]),
    )


__all__ = [
    "IVA_RECARGO_FACT_ID",
    "RecargoRateRecord",
    "load_recargo_rate_table",
    "recargo_rate_for_applied_rate",
    "recargo_rate_record_from_fact",
    "resolve_recargo_rate_for_applied_rate",
]
