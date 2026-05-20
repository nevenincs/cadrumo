"""Application-layer aggregation for IVA prorrata (LIVA arts. 101-103).

This module sits between the bucket's persisted revenue records and the
pure prorrata domain calculator in :mod:`aeat.domain.iva`. It takes a
year's classified IVA operations, applies the LIVA art. 104 exclusions,
sums the remaining amounts into the two prorrata pools (operations
granting the right to deduct vs operations exempt without that right),
and produces a :class:`~aeat.domain.iva.ProrrataInputs` value the
:func:`~aeat.domain.iva.compute_prorrata_general` calculator consumes.

The aggregator is a pure function: it does not touch the registry,
persistence, or the CLI. The caller — typically the modelo 303 or 390
binding provider — supplies a sequence of already-classified
:class:`IvaOperation` records sourced from the active bucket's
collectible invoices and ledger transactions. The classification step
itself happens upstream in :mod:`aeat.domain.iva._classification`; this
module relies on the upstream decision and only routes amounts.

Two high-level orchestrators wrap the aggregation:

* :func:`aggregate_provisional_prorrata` computes the provisional
  percentage to apply during the current tax year. Per LIVA art. 105 the
  provisional is normally derived from the prior year's definitiva
  result, so the aggregator runs against the prior year's operations
  and stamps the resulting percentage with the current year and
  current-year quarterly/monthly period.

* :func:`aggregate_definitiva_prorrata` computes the year-end definitiva
  percentage. Per LIVA art. 109 the definitiva uses the current year's
  actuals, producing the regularisation entry that lands on the Q4
  Modelo 303 (casilla 44) and Modelo 390 (casilla 33).

Both orchestrators emit :class:`~aeat.domain.iva.ProrrataResult` values
ready for consumption by the modelo binding providers.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ...domain.iva import (
    ProrrataInputs,
    ProrrataKind,
    ProrrataResult,
    compute_prorrata_general,
)
from ._errors import AggregationPeriodError, AggregationValidationError, t


class IvaOperationKind(StrEnum):
    """Routing of a single IVA operation into the prorrata pools.

    * ``GRANTS_DEDUCTION`` — the operation grants the right to deduct
      input VAT. Sales bearing IVA at any rate (general, reduced, super-
      reduced, zero), intra-EU supplies of goods to taxable persons,
      services to EU B2B counterparties, and exports outside the EU all
      fall here. The base amount lands in
      ``operaciones_con_derecho_deduccion``.

    * ``EXEMPT_WITHOUT_DEDUCTION`` — the operation is IVA-exempt without
      the right to deduct. The LIVA art. 20 exempt supplies (medical
      services, education, certain rental, certain financial /
      insurance, etc.) all fall here. The base amount lands in
      ``operaciones_sin_derecho_deduccion``.

    * ``EXCLUDED_BY_ART_104`` — the operation is excluded from both
      numerator and denominator per LIVA art. 104. Examples:
      subvenciones not linked to a specific operation, autoconsumos
      under arts. 9.1.a or 12, the sale or transfer of bienes de
      inversión owned by the taxpayer, and the non-recurring financial
      or immovable operations meeting the art. 104.Tres tests. The base
      amount does NOT contribute to the prorrata.
    """

    GRANTS_DEDUCTION = "grants_deduction"
    EXEMPT_WITHOUT_DEDUCTION = "exempt_without_deduction"
    EXCLUDED_BY_ART_104 = "excluded_by_art_104"


_NonEmptyShortString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]


class IvaOperation(BaseModel):
    """A single revenue operation classified for prorrata routing.

    Source records (collectible invoices, ledger transactions, or
    explicit AEAT pre-fill amounts) are reduced to this record before
    aggregation. Each record carries its own classification source
    (a free-form short tag such as ``"vat-classify:R10-ic-supply"`` or
    ``"liva-art-20-rental"``) so the aggregation's source trace stays
    legible in the calculation revision.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    operation_id: _NonEmptyShortString
    operation_date: date
    base_amount: Decimal = Field(..., ge=Decimal("0"))
    kind: IvaOperationKind
    classification_source: _NonEmptyShortString


class ProrrataAggregation(BaseModel):
    """The full aggregation outcome for one year window.

    Carries the resulting :class:`ProrrataInputs` plus the breakdown of
    how many operations contributed to each pool and the total amount
    excluded by LIVA art. 104. The breakdown is the caller-facing
    provenance: binding providers read it to surface a readiness report
    on the ``aeat app modelo bindings list`` output.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    year: Annotated[int, Field(ge=2000, le=2100)]
    inputs: ProrrataInputs
    operation_count_con_derecho: Annotated[int, Field(ge=0)]
    operation_count_sin_derecho: Annotated[int, Field(ge=0)]
    operation_count_excluded: Annotated[int, Field(ge=0)]
    excluded_amount_total: Decimal = Field(..., ge=Decimal("0"))


# ---------------------------------------------------------------------------
# Pure aggregation.
# ---------------------------------------------------------------------------


def aggregate_prorrata_inputs(
    operations: Sequence[IvaOperation],
    *,
    year: int,
) -> ProrrataAggregation:
    """Sum a year's operations into prorrata input pools.

    The function filters to operations whose ``operation_date.year``
    matches ``year`` and then sums their ``base_amount`` per ``kind``.
    Operations marked ``EXCLUDED_BY_ART_104`` are counted and their
    amount tracked separately, but they do NOT contribute to either
    prorrata pool — per LIVA art. 104 they are excluded from both
    numerator and denominator.

    Raises :class:`AggregationPeriodError` if ``year`` is outside the
    supported window (2000-2100).
    """

    if year < 2000 or year > 2100:
        raise AggregationPeriodError(t(f"prorrata aggregation year out of supported range 2000..2100: {year}"))

    con_derecho = Decimal("0")
    sin_derecho = Decimal("0")
    excluded_total = Decimal("0")
    count_con = 0
    count_sin = 0
    count_excluded = 0

    for operation in operations:
        if operation.operation_date.year != year:
            continue
        if operation.kind is IvaOperationKind.GRANTS_DEDUCTION:
            con_derecho += operation.base_amount
            count_con += 1
        elif operation.kind is IvaOperationKind.EXEMPT_WITHOUT_DEDUCTION:
            sin_derecho += operation.base_amount
            count_sin += 1
        elif operation.kind is IvaOperationKind.EXCLUDED_BY_ART_104:
            excluded_total += operation.base_amount
            count_excluded += 1

    return ProrrataAggregation(
        year=year,
        inputs=ProrrataInputs(
            operaciones_con_derecho_deduccion=con_derecho,
            operaciones_sin_derecho_deduccion=sin_derecho,
        ),
        operation_count_con_derecho=count_con,
        operation_count_sin_derecho=count_sin,
        operation_count_excluded=count_excluded,
        excluded_amount_total=excluded_total,
    )


# ---------------------------------------------------------------------------
# Orchestrators consumed by modelo 303 + 390 binding providers.
# ---------------------------------------------------------------------------


def aggregate_provisional_prorrata(
    prior_year_operations: Sequence[IvaOperation],
    *,
    prior_year: int,
    current_year: int,
    period: str,
) -> tuple[ProrrataResult, ProrrataAggregation]:
    """Compute the provisional prorrata percentage for one period in
    ``current_year``, derived from ``prior_year``'s actuals per LIVA art.
    105.

    The provisional percentage applies on every Modelo 303 quarter or
    month within ``current_year``. The same provisional may be reused
    across all periods of the same year; this orchestrator stamps the
    result with the supplied ``period`` token so callers can persist
    one ``ProrrataResult`` per filing window.

    The function returns the calculator result plus the underlying
    aggregation so binding providers may surface counts and excluded
    totals in their readiness output.

    Raises :class:`AggregationValidationError` when ``current_year`` is
    not strictly greater than ``prior_year``, or when ``period`` is not
    a valid in-year token (``Q1``..``Q4`` or ``M01``..``M12``).
    """

    if current_year <= prior_year:
        raise AggregationValidationError(
            t(
                f"current_year must be strictly greater than prior_year; "
                f"got prior_year={prior_year} current_year={current_year}"
            )
        )
    if not (period.startswith("Q") or period.startswith("M")):
        raise AggregationValidationError(
            t(f"provisional period must be a quarterly (Qn) or monthly (Mnn) token; got {period!r}")
        )

    aggregation = aggregate_prorrata_inputs(prior_year_operations, year=prior_year)
    result = compute_prorrata_general(
        aggregation.inputs,
        year=current_year,
        kind=ProrrataKind.PROVISIONAL,
        period=period,
    )
    return result, aggregation


def aggregate_definitiva_prorrata(
    current_year_operations: Sequence[IvaOperation],
    *,
    year: int,
) -> tuple[ProrrataResult, ProrrataAggregation]:
    """Compute the definitiva prorrata percentage for year-end
    regularisation under LIVA art. 109.

    The definitiva uses the year's actual operations and produces the
    regularisation entry that lands on the Q4 Modelo 303 (casilla 44)
    and the Modelo 390 (casilla 33). The result is stamped with
    ``period=None`` and ``kind=DEFINITIVA``; the calculator's
    :class:`ProrrataResult` validator accepts that combination.
    """

    aggregation = aggregate_prorrata_inputs(current_year_operations, year=year)
    result = compute_prorrata_general(
        aggregation.inputs,
        year=year,
        kind=ProrrataKind.DEFINITIVA,
    )
    return result, aggregation


__all__ = (
    "ProrrataAggregation",
    "IvaOperation",
    "IvaOperationKind",
    "aggregate_definitiva_prorrata",
    "aggregate_prorrata_inputs",
    "aggregate_provisional_prorrata",
)
