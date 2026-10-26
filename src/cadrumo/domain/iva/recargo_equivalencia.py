"""Resolve recargo de equivalencia pairings from governed registry data.

The canonical ``iva-recargo-by-applied-rate`` mapping fact owns the legal
pairing, date window, classification, and provenance.  This module retains
only typed projection, date selection, and fail-closed lookup mechanics.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.unit_proportion import UnitProportion
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.facts.variants import FactSelector
from ..calculations.registry.schema_base import DateAxis
from .errors import IvaCatalogueError, IvaValidationError

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation

IVA_RECARGO_FACT_ID = "iva-recargo-by-applied-rate"


class RecargoRateRecord(BaseModel):
    """One governed recargo pairing projected into the public record.

    The applied rate is the selector because one classification can have more
    than one dated pairing.  The authority supplies the legal references and
    date window; this record carries them without defining their values.

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
    @pydantic_validation_boundary
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


def recargo_rate_record_for_applied_rate(
    applied_rate: Decimal,
    on_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> RecargoRateRecord | None:
    """Return the dated pairing record, or ``None`` when no candidate exists.

    A candidate resolves through the exact governed-fact selector, preserving
    overlap refusal and the selected window's legal provenance. A published
    zero-rate pairing remains a record with ``recargo_rate == 0``; it is not
    confused with the no-candidate ``None`` result.
    """
    if not _recargo_fact_candidate_exists(applied_rate, on_date, operation=operation):
        return None
    resolved = resolve_recargo_rate_for_applied_rate(applied_rate, on_date, operation=operation)
    return recargo_rate_record_from_fact(resolved)


def resolve_recargo_rate_for_applied_rate(
    applied_rate: Decimal,
    on_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> ResolvedMappingFact:
    """Resolve the dated recargo pairing with its complete governed-fact provenance."""
    resolved = operation.resolve_governed_fact(
        MappingFactQuery(
            fact_id=IVA_RECARGO_FACT_ID,
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
            selectors=(FactSelector(name="applied_rate", value=applied_rate),),
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaCatalogueError("IVA recargo fact must resolve as a mapping fact")
    return resolved


def _recargo_fact_candidate_exists(
    applied_rate: Decimal,
    on_date: date,
    *,
    operation: PinnedAuthorityOperation,
) -> bool:
    """Return false only for an unmodelled applied-rate/date pairing.

    A candidate still resolves through the authority afterwards, so any overlap
    or other invalid exact selection remains a loud fail-closed error rather
    than being mistaken for the public ``None`` sentinel.
    """
    fact = operation.governed_fact(IVA_RECARGO_FACT_ID)
    return any(
        variant.date_axis is DateAxis.DEVENGO_DATE
        and variant.valid_from is not None
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
    "recargo_rate_record_for_applied_rate",
    "recargo_rate_record_from_fact",
    "resolve_recargo_rate_for_applied_rate",
]
