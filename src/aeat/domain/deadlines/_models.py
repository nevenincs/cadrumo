"""Pydantic v2 strict models for the :mod:`aeat.domain.deadlines` subpackage.

Every type that crosses a public boundary lives here as a strict, frozen
:class:`pydantic.BaseModel` (or :class:`enum.StrEnum` for closed
enumerations). No dataclasses; no bare ``dict[str, Any]``.

Consumed by :class:`aeat.domain.deadlines.DeadlineEngine` and re-exported
from :mod:`aeat.domain.deadlines`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ._errors import DeadlineValidationError


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
    """Status of a single :class:`ModeloDeadline` against a reference date.

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


class ModeloEnrollment(BaseModel):
    """AEAT enrollment facts used by registry filing schedules."""

    model_config = _STRICT_FROZEN

    large_company: bool = False
    public_administration_budget_gt_6000000: bool = False


class ModeloIVAProfile(BaseModel):
    """IVA facts used by registry filing schedules."""

    model_config = _STRICT_FROZEN

    roi_enrolled: bool = False
    oss_enrolled: bool = False
    intracommunity_operations_exceed_50000_eur: bool = False


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
        iva: IVA-specific filing facts that can change filing cadence.
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
    iva: ModeloIVAProfile = Field(default_factory=ModeloIVAProfile)
    enrollment: ModeloEnrollment = Field(default_factory=ModeloEnrollment)
    fiscal_address_cadastral_reference: str = ""
    fiscal_address_is_habitual_vivienda: bool = False
    activity_start_date: date | None = None
    activity_end_date: date | None = None
    establecimiento_type: str = ""
    elected_withholding_pct: str = ""
    vivienda_office_total_m2: Decimal | None = None
    vivienda_office_office_m2: Decimal | None = None
    iae_epigraph: str = ""
    notes: str = ""


class RecargoBand(BaseModel):
    """One Ley 58/2003 art-27 recargo band loaded from the registry TOML.

    The bracket table at
    ``registry/aeat/legal/ley-58-2003-recargo-bands.toml`` carries the
    surcharge schedule for self-assessments filed after the deadline
    without prior AEAT notice. Each row materialises into one
    :class:`RecargoBand`; the :class:`Recovery` value attached to an
    OVERDUE :class:`ModeloDeadline` references the resolved band
    by ``id``.

    Attributes:
        id: Stable identifier (``within_30_days``, ``after_12_months``,
            ...). Used by the CLI for per-band rendering.
        min_days_late: Inclusive lower bound on the days-late window
            this band covers.
        max_days_late: Inclusive upper bound, or ``None`` for the
            open-ended ``after_12_months`` band.
        surcharge_pct: Recargo percentage applied on the cuota.
        interest_applies: True only for the after-12-months band; the
            CLI renders the interest hint when set.
        legal_ref: Stable corpus reference (``ley-58-2003:art-27.2``).
    """

    model_config = _STRICT_FROZEN

    id: str = Field(min_length=1, max_length=64)
    min_days_late: int = Field(ge=1)
    max_days_late: int | None = None
    surcharge_pct: Decimal
    interest_applies: bool = False
    legal_ref: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _validate_window(self) -> Self:
        if self.max_days_late is not None and self.max_days_late < self.min_days_late:
            raise DeadlineValidationError(
                f"RecargoBand {self.id}: max_days_late ({self.max_days_late}) "
                f"is below min_days_late ({self.min_days_late})"
            )
        return self


class Recovery(BaseModel):
    """Operator-facing recovery payload attached to an OVERDUE obligation.

    Surfaces the resolved Ley 58/2003 art-27 recargo band plus a runnable
    next-action command the operator can copy. The CLI's calendar
    renderer surfaces ``recovery\\t<band_id>\\t<surcharge_pct>%\\t<next_command>``
    underneath each OVERDUE entry.

    Attributes:
        still_filable: True for every band -- art-27 self-assessments
            remain admissible past the original deadline; the surcharge
            is the only consequence. The flag exists so a future band
            for absolutely-time-barred filings can be added without
            reshaping the model.
        recargo_band: The :class:`RecargoBand` resolved from the
            ``days_late`` window.
        legal_ref: Same as ``recargo_band.legal_ref``; carried at the
            top level so renderers do not dereference.
        next_command: Literal shell command the operator can copy to
            calculate the late filing.
    """

    model_config = _STRICT_FROZEN

    still_filable: bool = True
    recargo_band: RecargoBand
    legal_ref: str = Field(min_length=1, max_length=128)
    next_command: str = Field(min_length=1, max_length=256)


class ModeloDeadline(BaseModel):
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
        recovery: Resolved :class:`Recovery` payload when ``status`` is
            ``OVERDUE``; ``None`` for every other status. Populated by
            the deadline engine using the days-late window and the
            registry's recargo bracket table.
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
    recovery: Recovery | None = None

    @model_validator(mode="after")
    def _check_window_order(self) -> ModeloDeadline:
        """Reject obligations whose ``opens_on`` is after ``closes_on``."""
        if self.opens_on > self.closes_on:
            raise DeadlineValidationError(f"opens_on ({self.opens_on}) is after closes_on ({self.closes_on})")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise DeadlineValidationError(
                f"payment_cutoff_on ({self.payment_cutoff_on}) is after closes_on ({self.closes_on})"
            )
        return self


class Schedule(BaseModel):
    """The full filing schedule for an autónomo for a given year.

    Attributes:
        profile: The :class:`AutonomoProfile` the schedule was computed
            for.
        year: The target year.
        obligations: Tuple of :class:`ModeloDeadline` ordered by
            ``(closes_on, modelo, period)``.
        generated_at: UTC timestamp of when :meth:`DeadlineEngine.compute`
            built this schedule. The only non-deterministic field.
    """

    model_config = _STRICT_FROZEN

    profile: AutonomoProfile
    year: int = Field(ge=1900, le=2999)
    obligations: tuple[ModeloDeadline, ...]
    generated_at: datetime
