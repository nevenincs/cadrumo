"""Canonical temporal request matrix and source-side selection comparisons."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import date

from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.calculations.registry.temporal import (
    revision_temporal_resolution,
    select_revision,
)

from .registry_collapse_comparison import _first_difference, _typed_projection
from .registry_collapse_models import CheckStatus, ComparisonResult, RequestCoordinate


def request_matrix(modelo: ModeloDefinition, *, floor: int, ceiling: int) -> tuple[RequestCoordinate, ...]:
    """Derive exact, boundary, gap, and support-edge requests from canonical metadata."""
    coordinates: dict[tuple[object, ...], RequestCoordinate] = {}
    authored_years: set[int] = set()
    period_tokens: set[str] = set()
    for revision_id, revision in modelo.revisions.items():
        _record_revision_coordinates(
            str(revision_id),
            revision,
            floor=floor,
            ceiling=ceiling,
            coordinates=coordinates,
            authored_years=authored_years,
            period_tokens=period_tokens,
        )
    _record_support_coordinates(coordinates, floor, ceiling, period_tokens)
    _record_internal_gap_coordinates(coordinates, floor, ceiling, authored_years, period_tokens)
    ordered = sorted(
        coordinates,
        key=lambda item: tuple("" if value is None else str(value) for value in item),
    )
    return tuple(coordinates[key] for key in ordered)


def _record_revision_coordinates(
    revision_id: str,
    revision: ModeloRevision,
    *,
    floor: int,
    ceiling: int,
    coordinates: dict[tuple[object, ...], RequestCoordinate],
    authored_years: set[int],
    period_tokens: set[str],
) -> None:
    years = _selector_years_from_revision(revision, floor=floor, ceiling=ceiling)
    authored_years.update(years)
    for year in years:
        for period in revision.period_selector.periods_for_year(year):
            token = str(period)
            period_tokens.add(token)
            _record_revision_period_coordinates(revision_id, revision, year, token, coordinates)


def _selector_years_from_revision(revision: ModeloRevision, *, floor: int, ceiling: int) -> tuple[int, ...]:
    selector = revision.period_selector
    if selector.years:
        return tuple(year for year in selector.years if floor <= year <= ceiling)
    start = max(selector.year_from or floor, floor)
    end = min(selector.year_to if selector.year_to is not None else ceiling, ceiling)
    return tuple(range(start, end + 1)) if start <= end else ()


def _record_revision_period_coordinates(
    revision_id: str,
    revision: ModeloRevision,
    year: int,
    token: str,
    coordinates: dict[tuple[object, ...], RequestCoordinate],
) -> None:
    for on, case in ((None, "exact"), (revision.valid_from, "valid_from"), (revision.valid_to, "valid_to")):
        if on is None and case != "exact":
            continue
        coordinate = RequestCoordinate(
            year,
            token,
            None if on is None else on.isoformat(),
            revision_id,
            case,
        )
        coordinates[(year, token, coordinate.on, revision_id)] = coordinate


def _record_support_coordinates(
    coordinates: dict[tuple[object, ...], RequestCoordinate],
    floor: int,
    ceiling: int,
    period_tokens: set[str],
) -> None:
    for period in sorted(period_tokens):
        for year, case in ((floor, "support_floor"), (ceiling, "support_ceiling")):
            coordinate = RequestCoordinate(year, period, None, None, case)
            coordinates[(year, period, None, None)] = coordinate


def _record_internal_gap_coordinates(
    coordinates: dict[tuple[object, ...], RequestCoordinate],
    floor: int,
    ceiling: int,
    authored_years: set[int],
    period_tokens: set[str],
) -> None:
    if not authored_years:
        return
    first = max(floor, min(authored_years))
    last = min(ceiling, max(authored_years))
    for year in range(first, last + 1):
        if year in authored_years:
            continue
        for period in sorted(period_tokens):
            coordinates[(year, period, None, None)] = RequestCoordinate(year, period, None, None, "internal_gap")


def _selection_result(
    modelo: ModeloDefinition,
    coordinate: RequestCoordinate,
    support: SupportedFilingYearsCatalogue,
) -> Mapping[str, object]:
    try:
        selected = select_revision(
            modelo,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            on=None if coordinate.on is None else date.fromisoformat(coordinate.on),
            revision_id=coordinate.revision_id,
            support=support,
        )
        resolution = revision_temporal_resolution(
            selected,
            filing_year=coordinate.filing_year,
            period=coordinate.period,
            support=support,
        )
        return {
            "outcome": "selected",
            "revision": str(selected.id),
            "requested_filing_year": resolution.requested_filing_year,
            "authored_filing_year": resolution.authored_filing_year,
            "projection_direction": str(resolution.projection_direction),
            "value": _typed_projection(selected),
        }
    except Exception as exc:
        return {"outcome": "refused", "error_type": type(exc).__name__, "detail": str(exc)}


def compare_temporal(
    before: ModeloDefinition,
    after: ModeloDefinition,
    *,
    support: SupportedFilingYearsCatalogue,
    floor: int,
    ceiling: int,
) -> ComparisonResult:
    """Compare canonical temporal selection and complete selected typed meaning."""
    differences: list[Mapping[str, object]] = []
    matrix = request_matrix(before, floor=floor, ceiling=ceiling)
    for coordinate in matrix:
        left = _selection_result(before, coordinate, support)
        right = _selection_result(after, coordinate, support)
        difference = _first_difference(left, right)
        if difference is not None:
            differences.append({"coordinate": asdict(coordinate), **difference})
    return ComparisonResult(
        status=CheckStatus.PASSED if not differences else CheckStatus.FAILED,
        checked=len(matrix),
        differences=tuple(differences),
    )
