"""Pydantic v2 strict models for the :mod:`aeat.domain.deadlines` subpackage.

Every type that crosses a public boundary lives here as a strict, frozen
:class:`pydantic.BaseModel` (or :class:`enum.StrEnum` for closed
enumerations). No dataclasses; no bare ``dict[str, Any]``.

Consumed by :class:`aeat.domain.deadlines.DeadlineEngine` and re-exported
from :mod:`aeat.domain.deadlines`.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IVARegime(StrEnum):
    """The IVA regime an autónomo files under.

    Registry deadline applicability can reference this value. The closed
    set tracks the four regimes the project supports for autónomos.

    Attributes:
        GENERAL: Régimen general.
        SIMPLIFICADO: Régimen simplificado.
        RECARGO_EQUIVALENCIA: Recargo de equivalencia.
        EXENTO: IVA-exempt activity.
    """

    GENERAL = "GENERAL"
    SIMPLIFICADO = "SIMPLIFICADO"
    RECARGO_EQUIVALENCIA = "RECARGO_EQUIVALENCIA"
    EXENTO = "EXENTO"


class ObligationStatus(StrEnum):
    """Status of a single :class:`FilingObligation` against a reference date.

    :attr:`UPCOMING` and :attr:`DUE_SOON` are differentiated by the
    ``AEAT_DEADLINE_DUE_SOON_DAYS`` setting (default 14 days).
    :attr:`FILED` and :attr:`NOT_APPLICABLE` are reserved for downstream
    consumers — the engine never produces them.

    Attributes:
        UPCOMING: Window opens in the future or is open but more than
            ``due_soon_days`` ahead of close.
        DUE_SOON: Window closes within ``due_soon_days`` of the
            reference date.
        DUE_TODAY: Reference date is the close date.
        OVERDUE: Reference date is past the close date.
        FILED: Downstream marker for filings already submitted.
        NOT_APPLICABLE: Downstream marker for obligations the profile
            no longer triggers.
    """

    UPCOMING = "UPCOMING"
    DUE_SOON = "DUE_SOON"
    DUE_TODAY = "DUE_TODAY"
    OVERDUE = "OVERDUE"
    FILED = "FILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class FilingEnrollment(BaseModel):
    """AEAT enrollment facts used by registry filing schedules."""

    model_config = _STRICT_FROZEN

    large_company: bool = False
    public_administration_budget_gt_6000000: bool = False


class AutonomoProfile(BaseModel):
    """The profile of a Spanish autónomo for filing-deadline computation.

    Attributes:
        tax_id: NIF / NIE. Stored verbatim, no normalisation.
        iva_regime: The IVA regime the autónomo files under.
        has_employees: Whether the autónomo pays salaries with
            retención.
        pays_professionals_with_retencion: Whether the autónomo pays
            professional fees subject to retención.
        professional_income_withholding_ge_70pct: Whether at least 70%
            of the autónomo's prior-year professional income was
            already subject to withholding.
        pays_rent_with_retencion: Whether the autónomo pays alquiler de
            local with retención.
        pays_capital_income_with_retencion: Whether the autónomo pays
            capital-income rents subject to withholding.
        uses_objective_estimation_irpf: Whether the autónomo computes IRPF
            economic-activity income under estimación objetiva.
        does_intracomunitario: Whether the autónomo conducts
            operaciones intracomunitarias.
        third_party_transactions_above_347_threshold: Whether the
            profile exceeded the applicable third-party transaction
            threshold during the prior year.
        bienes_extranjero_above_threshold: Whether the autónomo holds
            bienes en el extranjero above the legal threshold.
        enrollment: AEAT enrollment facts that can change filing cadence.
        notes: Free-form notes for the user. Never consumed by the
            engine.
    """

    model_config = _STRICT_FROZEN

    tax_id: str = Field(min_length=1)
    iva_regime: IVARegime
    has_employees: bool = False
    pays_professionals_with_retencion: bool = False
    professional_income_withholding_ge_70pct: bool = False
    pays_rent_with_retencion: bool = False
    pays_capital_income_with_retencion: bool = False
    uses_objective_estimation_irpf: bool = False
    does_intracomunitario: bool = False
    third_party_transactions_above_347_threshold: bool = False
    bienes_extranjero_above_threshold: bool = False
    enrollment: FilingEnrollment = Field(default_factory=FilingEnrollment)
    notes: str = ""


class FilingObligation(BaseModel):
    """A single filing obligation in a :class:`Schedule`.

    Attributes:
        modelo: The modelo string identifier; carried as a plain
            ``str`` on this record so JSON round-tripping is loss-free
            for downstream consumers.
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
            is obliged to file this modelo, resolved from the registry
            deadline applicability rule.
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
