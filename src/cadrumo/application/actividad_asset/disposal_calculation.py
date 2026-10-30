"""Assemble one element's baja facts from its revision, history and authority, and project the result."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from ...domain.calculations.registry.actividad_asset_bindings import (
    ActivityAssetDisposalBounds,
    resolve_activity_asset_disposal_bounds,
)
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryError
from ...domain.renta.actividad_asset.claims import effective_claims, uncovered_claim_intervals
from ...domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalCalculation,
    ActivityAssetDisposalFacts,
    ActivityAssetDisposalReason,
    ActivityAssetDisposalYearFacts,
    calculate_disposal,
)
from ...domain.renta.actividad_asset.election import AmortizationMethod
from ...domain.renta.actividad_asset.errors import ActividadAssetIncompleteError
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ..operations.public_scalar import project_scalar
from .activity_asset_read_models import (
    DISPOSAL_FINDING_FAMILY,
    ActivityAssetDisposalCalculationView,
    ActivityAssetDisposalFindingView,
    ActivityAssetDisposalYearView,
    activity_asset_label_key,
)
from .history import ActivityAssetHistory

_EXCESS_METHODS = frozenset({AmortizationMethod.ELECTRIC_VEHICLE_FREE, AmortizationMethod.CHARGING_INFRASTRUCTURE_FREE})
"""The elections whose deduction above the table is excess at transmission (LIRPF DA 59.2)."""

DisposalBoundsReader = Callable[[ActivityAssetRevision, int], ActivityAssetDisposalBounds]


def pinned_disposal_bounds(operation: PinnedAuthorityOperation) -> DisposalBoundsReader:
    """Read a baja's bounds under one authority pin; a year no edition covers says so."""

    def read(revision: ActivityAssetRevision, tax_year: int) -> ActivityAssetDisposalBounds:
        try:
            modelo_revision = operation.revision_for_context("100", filing_year=tax_year, period="0A")
            return resolve_activity_asset_disposal_bounds(modelo_revision, tax_year=tax_year, asset_revision=revision)
        except RegistryError:
            return ActivityAssetDisposalBounds(edition_available=False)

    return read


def disposal_excess_applies(revision: ActivityAssetRevision, disposal: ActivityAssetDisposal) -> bool:
    """Say whether this baja can carry an excess: not a withdrawal, on a free-depreciation element."""
    return disposal.reason is not ActivityAssetDisposalReason.WITHDRAWAL and (
        revision.amortization.method in _EXCESS_METHODS or disposal.prior_free_depreciation_regime is not None
    )


def calculate_element_disposal(
    revision: ActivityAssetRevision,
    disposal: ActivityAssetDisposal,
    history: ActivityAssetHistory,
    *,
    bounds: DisposalBoundsReader,
) -> ActivityAssetDisposalCalculation:
    """Work out one baja from every service year of the element.

    Raises:
        ActividadAssetIncompleteError: When the opening history is missing.
        ActividadAssetUnsupportedError: When an excess needs a year with no table class.
    """
    opening = revision.opening_history.accumulated_amount
    if opening is None:
        raise ActividadAssetIncompleteError(translated_message="ledger.actividad_asset.errors.opening_history_missing")
    return calculate_disposal(
        ActivityAssetDisposalFacts(
            disposal=disposal,
            acquisition_value=revision.basis.allocated_acquisition_value(),
            allocation_share=revision.basis.allocation_share(),
            amortizable_value=revision.amortizable_basis(),
            opening_amount=opening,
            opening_covered_through=revision.opening_history.covered_through_tax_year,
            years=tuple(
                _year_facts(revision, disposal, history, tax_year=tax_year, bounds=bounds(revision, tax_year))
                for tax_year in range(revision.in_service_date.year, disposal.disposal_date.year + 1)
            ),
            excess_applies=disposal_excess_applies(revision, disposal),
            later_affectation_period_years=bounds(revision, disposal.disposal_date.year).later_affectation_period_years,
        ),
    )


def _year_facts(
    revision: ActivityAssetRevision,
    disposal: ActivityAssetDisposal,
    history: ActivityAssetHistory,
    *,
    tax_year: int,
    bounds: ActivityAssetDisposalBounds,
) -> ActivityAssetDisposalYearFacts:
    start, end = date(tax_year, 1, 1), date(tax_year + 1, 1, 1)
    calendar_days = (end - start).days
    service_days = _overlap_days(revision.in_service_date, disposal.boundary, start, end)
    share_of_year = Decimal(service_days) / calendar_days
    minimum = year_minimum(revision, tax_year=tax_year, boundary=disposal.boundary, bounds=bounds)
    maximum = (
        None
        if bounds.maximum_coefficient is None
        else revision.amortizable_basis() * bounds.maximum_coefficient * share_of_year
    )
    claims = tuple(
        claim
        for claim in effective_claims(history.claims)
        if claim.asset_id == revision.asset_id and claim.tax_year == tax_year
    )
    return ActivityAssetDisposalYearFacts(
        tax_year=tax_year,
        claims=sum((claim.amount for claim in claims), Decimal("0")),
        minimum=minimum,
        maximum_charge=maximum,
        claim_gap=bool(uncovered_claim_intervals(revision, history.claims, start=start, end=end)),
        minimum_unresolved=not bounds.edition_available,
    )


def year_minimum(
    revision: ActivityAssetRevision,
    *,
    tax_year: int,
    boundary: date,
    bounds: ActivityAssetDisposalBounds,
) -> Decimal | None:
    """Work out one service year's minimum amortization, unrounded; ``None`` when no authority supplies it.

    This is what reduces cost at a baja under RIRPF art. 40.  It is never taken from
    the value still deductible.
    """
    start, end = date(tax_year, 1, 1), date(tax_year + 1, 1, 1)
    base = revision.amortizable_basis()
    if bounds.useful_life_ends_on is not None:
        life_days = (bounds.useful_life_ends_on - revision.in_service_date).days
        if life_days <= 0:
            return None
        lived = _overlap_days(revision.in_service_date, min(boundary, bounds.useful_life_ends_on), start, end)
        return base * lived / life_days
    if bounds.minimum_coefficient is None:
        return None
    share_of_year = Decimal(_overlap_days(revision.in_service_date, boundary, start, end)) / (end - start).days
    return base * bounds.minimum_coefficient * share_of_year


def _overlap_days(first: date, last: date, start: date, end: date) -> int:
    return max((min(last, end) - max(first, start)).days, 0)


def project_disposal_calculation(
    disposal: ActivityAssetDisposal,
    calculation: ActivityAssetDisposalCalculation,
) -> ActivityAssetDisposalCalculationView:
    """Project one baja's figures to their public form."""

    def optional(value: Decimal | None):
        return None if value is None else project_scalar(value)

    return ActivityAssetDisposalCalculationView(
        disposal_date=disposal.disposal_date,
        reason=disposal.reason,
        acquisition_value=project_scalar(calculation.acquisition_value),
        deducted=project_scalar(calculation.deducted),
        minimum=optional(calculation.minimum),
        reduction=project_scalar(calculation.reduction),
        excess=project_scalar(calculation.excess),
        net_value=project_scalar(calculation.net_value),
        transmission_value=optional(calculation.transmission_value),
        transmission_costs=optional(calculation.transmission_costs),
        result=optional(calculation.result),
        route_changed_by_later_affectation=calculation.route_changed_by_later_affectation,
        years=tuple(
            ActivityAssetDisposalYearView(
                tax_year=year.tax_year,
                claims=project_scalar(year.claims),
                deducted_through=project_scalar(year.deducted_through),
                minimum_through=optional(year.minimum_through),
                reduction_through=project_scalar(year.reduction_through),
            )
            for year in calculation.years
        ),
        findings=tuple(
            ActivityAssetDisposalFindingView(
                kind=finding.kind,
                label_key=activity_asset_label_key(DISPOSAL_FINDING_FAMILY, finding.kind),
                tax_year=finding.tax_year,
                effect_on_cost=optional(finding.effect_on_cost),
            )
            for finding in calculation.findings
        ),
    )


__all__ = [
    "DisposalBoundsReader",
    "calculate_element_disposal",
    "disposal_excess_applies",
    "pinned_disposal_bounds",
    "project_disposal_calculation",
    "year_minimum",
]
