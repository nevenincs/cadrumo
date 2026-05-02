"""Canonical filing-window calendar for the autónomo modelo set.

The :data:`CALENDAR` table is the in-code source of truth for
filing windows. Every entry is sourced from the AEAT *calendario
del contribuyente* and the BOE order that fixes the filing schedule
for the modelo, with citations propagated through to every emitted
:class:`aeat.domain.deadlines.FilingObligation`.

The supported years are listed in :data:`SUPPORTED_YEARS` and the
authoritative modelo set in :data:`KNOWN_AUTONOMO_MODELOS`.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class PeriodKind(StrEnum):
    """Period granularity supported by the deadline engine.

    Attributes:
        MONTHLY: Monthly filing cadence.
        QUARTERLY: Quarterly filing cadence.
        ANNUAL: Annual filing cadence.
    """

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUAL = "annual"


class CanonicalWindow(BaseModel):
    """A single filing window for one ``(modelo, year, period)`` triple.

    Attributes:
        modelo: The modelo string identifier.
        year: The fiscal year the window belongs to.
        period: The period label, e.g. ``"2026Q1"`` or ``"2026"``.
        kind: Quarterly vs annual.
        opens_on: First day of the filing window.
        closes_on: Last day of the filing window.
        payment_cutoff_on: Direct-debit cutoff, if applicable.
        boe_references: Tuple of stable BOE / Manual práctico citation
            keys.
    """

    model_config = _STRICT_FROZEN

    modelo: str = Field(min_length=1)
    year: int = Field(ge=1900, le=2999)
    period: str = Field(min_length=1)
    kind: PeriodKind
    opens_on: date
    closes_on: date
    payment_cutoff_on: date | None = None
    boe_references: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def _check_window_order(self) -> CanonicalWindow:
        """Reject windows whose ``opens_on`` is after ``closes_on``."""
        if self.opens_on > self.closes_on:
            raise ValueError(f"opens_on ({self.opens_on}) is after closes_on ({self.closes_on})")
        if self.payment_cutoff_on is not None and self.payment_cutoff_on > self.closes_on:
            raise ValueError(f"payment_cutoff_on ({self.payment_cutoff_on}) is after closes_on ({self.closes_on})")
        return self


# Stable BOE / Manual práctico citation keys. Opaque identifiers, never
# URLs - URLs decay; legal citations do not.
_CITE_IRPF_PAGOS = "BOE-Orden-IRPF-pagos-fraccionados"
_CITE_IVA_AUTOLIQ = "BOE-Orden-IVA-autoliquidacion"
_CITE_IVA_RESUMEN = "BOE-Orden-IVA-resumen-anual"
_CITE_IRPF_ANUAL = "BOE-Orden-IRPF-declaracion-anual"
_CITE_RET_IRPF = "BOE-Orden-Retenciones-IRPF-trabajo-profesionales"
_CITE_RET_IRPF_ANUAL = "BOE-Orden-Retenciones-IRPF-resumen-anual"
_CITE_RET_ALQUILER = "BOE-Orden-Retenciones-Alquiler-Inmuebles-Urbanos"
_CITE_RET_ALQUILER_ANUAL = "BOE-Orden-Retenciones-Alquiler-Resumen-Anual"
_CITE_OPERACIONES_TERCEROS = "BOE-Orden-347-Operaciones-Terceros"
_CITE_INTRA_EU = "BOE-Orden-Recapitulativa-Intracomunitaria"
_CITE_BIENES_EXTRANJERO = "BOE-Orden-720-Bienes-Extranjero"


def _quarterly_windows(
    modelo: str,
    year: int,
    *,
    citations: tuple[str, ...],
) -> tuple[CanonicalWindow, ...]:
    """Build the four quarterly windows for ``(modelo, year)``.

    The standard autónomo schedule is:

    - Q1: 1–20 April
    - Q2: 1–20 July
    - Q3: 1–20 October
    - Q4: 1–30 January (of ``year + 1``)

    Direct-debit cutoff is ``closes_on - 5`` days.
    """
    starts = [
        (date(year, 4, 1), date(year, 4, 20)),
        (date(year, 7, 1), date(year, 7, 20)),
        (date(year, 10, 1), date(year, 10, 20)),
        (date(year + 1, 1, 1), date(year + 1, 1, 30)),
    ]
    out: list[CanonicalWindow] = []
    for idx, (opens_on, closes_on) in enumerate(starts, start=1):
        out.append(
            CanonicalWindow(
                modelo=modelo,
                year=year,
                period=f"{year}Q{idx}",
                kind=PeriodKind.QUARTERLY,
                opens_on=opens_on,
                closes_on=closes_on,
                payment_cutoff_on=date.fromordinal(closes_on.toordinal() - 5),
                boe_references=citations,
            )
        )
    return tuple(out)


def _annual_window(
    modelo: str,
    year: int,
    *,
    opens_on: date,
    closes_on: date,
    payment_cutoff_on: date | None,
    citations: tuple[str, ...],
    period_label: str | None = None,
) -> CanonicalWindow:
    """Build a single annual window for ``(modelo, year)``."""
    return CanonicalWindow(
        modelo=modelo,
        year=year,
        period=period_label or str(year),
        kind=PeriodKind.ANNUAL,
        opens_on=opens_on,
        closes_on=closes_on,
        payment_cutoff_on=payment_cutoff_on,
        boe_references=citations,
    )


def _last_business_day(year: int, month: int) -> date:
    """Return the month-end date extended to the next Monday when needed."""
    closes_on = date(year, month, monthrange(year, month)[1])
    while closes_on.weekday() >= 5:
        closes_on = date.fromordinal(closes_on.toordinal() + 1)
    return closes_on


def _build_year(year: int) -> tuple[CanonicalWindow, ...]:
    """Materialise the canonical windows for ``year``.

    The 2025 and 2026 entries derive from the AEAT *calendario del
    contribuyente* for those years; both follow the same standard
    autónomo schedule. The helper produces deterministic output for
    any year in :data:`SUPPORTED_YEARS`.
    """
    out: list[CanonicalWindow] = []

    # Quarterly modelos that follow the standard 1-20 / 1-30 schedule.
    out.extend(_quarterly_windows("130", year, citations=(_CITE_IRPF_PAGOS,)))
    out.extend(_quarterly_windows("303", year, citations=(_CITE_IVA_AUTOLIQ,)))
    out.extend(_quarterly_windows("111", year, citations=(_CITE_RET_IRPF,)))
    out.extend(_quarterly_windows("115", year, citations=(_CITE_RET_ALQUILER,)))
    out.extend(_quarterly_windows("349", year, citations=(_CITE_INTRA_EU,)))

    # Annual IVA resumen - opens 1 Jan of year+1, closes 30 Jan.
    out.append(
        _annual_window(
            "390",
            year,
            opens_on=date(year + 1, 1, 1),
            closes_on=date(year + 1, 1, 30),
            payment_cutoff_on=None,
            citations=(_CITE_IVA_RESUMEN,),
        )
    )
    # Annual retenciones IRPF resumen.
    out.append(
        _annual_window(
            "190",
            year,
            opens_on=date(year + 1, 1, 1),
            closes_on=date(year + 1, 1, 30),
            payment_cutoff_on=None,
            citations=(_CITE_RET_IRPF_ANUAL,),
        )
    )
    # Annual retenciones alquiler resumen.
    out.append(
        _annual_window(
            "180",
            year,
            opens_on=date(year + 1, 1, 1),
            closes_on=date(year + 1, 1, 30),
            payment_cutoff_on=None,
            citations=(_CITE_RET_ALQUILER_ANUAL,),
        )
    )
    # Annual third-party transactions.
    out.append(
        _annual_window(
            "347",
            year,
            opens_on=date(year + 1, 2, 1),
            closes_on=_last_business_day(year + 1, 2),
            payment_cutoff_on=None,
            citations=(_CITE_OPERACIONES_TERCEROS,),
        )
    )
    # Modelo 100 - IRPF anual: filed in year+1 for income earned in year.
    # Window: 2 April → 30 June of year+1.
    out.append(
        _annual_window(
            "100",
            year,
            opens_on=date(year + 1, 4, 2),
            closes_on=date(year + 1, 6, 30),
            payment_cutoff_on=date(year + 1, 6, 25),
            citations=(_CITE_IRPF_ANUAL,),
        )
    )
    # Modelo 720 - bienes en el extranjero: 1 Jan → 31 March of year+1.
    out.append(
        _annual_window(
            "720",
            year,
            opens_on=date(year + 1, 1, 1),
            closes_on=date(year + 1, 3, 31),
            payment_cutoff_on=None,
            citations=(_CITE_BIENES_EXTRANJERO,),
        )
    )

    return tuple(out)


SUPPORTED_YEARS: tuple[int, ...] = (2024, 2025, 2026, 2027)
"""Years for which the in-code canonical calendar is authoritative."""


CALENDAR: tuple[CanonicalWindow, ...] = tuple(window for year in SUPPORTED_YEARS for window in _build_year(year))
"""Closed, frozen tuple of canonical filing windows."""


KNOWN_AUTONOMO_MODELOS: tuple[str, ...] = (
    "100",
    "111",
    "115",
    "130",
    "180",
    "190",
    "303",
    "347",
    "349",
    "390",
    "720",
)
"""Closed set of autónomo-relevant modelos the engine considers."""
