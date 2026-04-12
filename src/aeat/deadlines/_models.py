"""Pydantic v2 strict models for the deadline-engine subpackage.

Every type that crosses a public boundary lives here as a strict,
frozen :class:`pydantic.BaseModel` (or :class:`enum.StrEnum` for closed
enumerations). No dataclasses; no bare ``dict[str, Any]``.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IVARegime(StrEnum):
    """The IVA regime an autónomo files under.

    Drives the applicability of Modelo 303 and Modelo 390. The closed
    set tracks the four regimes the project supports for autónomos.
    """

    GENERAL = "GENERAL"
    SIMPLIFICADO = "SIMPLIFICADO"
    RECARGO_EQUIVALENCIA = "RECARGO_EQUIVALENCIA"
    EXENTO = "EXENTO"


class ObligationStatus(StrEnum):
    """Status of a single :class:`FilingObligation` against a reference date.

    ``UPCOMING`` and ``DUE_SOON`` are differentiated by the
    ``AEAT_DEADLINE_DUE_SOON_DAYS`` setting (default 14 days).
    ``FILED`` and ``NOT_APPLICABLE`` are reserved for downstream
    consumers - the engine never produces them in v1.
    """

    UPCOMING = "UPCOMING"
    DUE_SOON = "DUE_SOON"
    DUE_TODAY = "DUE_TODAY"
    OVERDUE = "OVERDUE"
    FILED = "FILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AutonomoProfile(BaseModel):
    """The profile of a Spanish autónomo for filing-deadline computation.

    Attributes:
        tax_id: NIF / NIE. Stored verbatim, no normalisation.
        iva_regime: The IVA regime the autónomo files under.
        has_employees: Whether the autónomo pays salaries / professional
            fees with retención. Drives Modelo 111 and 190.
        pays_rent_with_retencion: Whether the autónomo pays alquiler de
            local with retención. Drives Modelo 115 and 180.
        does_intracomunitario: Whether the autónomo conducts
            operaciones intracomunitarias. Drives Modelo 349.
        bienes_extranjero_above_threshold: Whether the autónomo holds
            bienes en el extranjero above the legal threshold. Drives
            Modelo 720.
        notes: Free-form notes for the user. Never consumed by the
            engine.
    """

    model_config = _STRICT_FROZEN

    tax_id: str = Field(min_length=1)
    iva_regime: IVARegime
    has_employees: bool
    pays_rent_with_retencion: bool
    does_intracomunitario: bool
    bienes_extranjero_above_threshold: bool
    notes: str = ""


class FilingObligation(BaseModel):
    """A single filing obligation in a :class:`Schedule`.

    Attributes:
        modelo: The modelo string identifier (referencing #6 via the
            :class:`aeat.deadlines._protocols.ModeloIdentifier` stub).
        period: The period covered, e.g. ``"2026Q1"``, ``"2026"``,
            ``"2026-03"``.
        opens_on: The first day the AEAT filing window accepts the
            modelo for this period.
        closes_on: The last day the AEAT filing window accepts the
            modelo for this period.
        payment_cutoff_on: The cutoff for direct-debit payment, if
            applicable. ``None`` when there is no payment leg.
        status: The :class:`ObligationStatus` against the reference
            ``today`` used by :meth:`DeadlineEngine.compute`.
        applies_because: Human-readable explanation of why the profile
            is obliged to file this modelo. References the rule from
            :mod:`aeat.deadlines._applies`.
        boe_references: Tuple of opaque BOE / Manual práctico citation
            keys. Stable identifiers, never URLs.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1)
    period: str = Field(min_length=1)
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    status: ObligationStatus
    applies_because: str = Field(min_length=1)
    boe_references: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_window_order(self) -> FilingObligation:
        """Reject obligations whose ``opens_on`` is after ``closes_on``."""
        if self.opens_on > self.closes_on:
            raise ValueError(f"opens_on ({self.opens_on}) is after closes_on ({self.closes_on})")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise ValueError(f"payment_cutoff_on ({self.payment_cutoff_on}) is after closes_on ({self.closes_on})")
        return self


class Schedule(BaseModel):
    """The full filing schedule for an autónomo for a given year.

    Attributes:
        profile: The :class:`AutonomoProfile` the schedule was computed
            for.
        year: The target year.
        obligations: Tuple of :class:`FilingObligation` ordered by
            ``(closes_on, modelo, period)``.
        generated_at: UTC timestamp of when :meth:`DeadlineEngine.compute`
            built this schedule. The only non-deterministic field.
    """

    model_config = _STRICT_FROZEN

    profile: AutonomoProfile
    year: int = Field(ge=1900, le=2999)
    obligations: tuple[FilingObligation, ...]
    generated_at: datetime
