"""Advisory completeness audit for the registry-supported filing-year catalogue."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import RegistrySelectorPeriodCode
from .errors import RegistrySnapshotError
from .ids import ModeloId
from .period_selector_match import selector_period_matches_request
from .schema import ModeloDefinition, SupportedFilingYearsCatalogue
from .schema_references import SourceReference
from .temporal import select_revision


@dataclass(frozen=True, slots=True)
class SupportedFilingYearGap:
    """One exact modelo/year/period prerequisite absent from declared support."""

    modelo: ModeloId
    filing_year: int
    period: RegistrySelectorPeriodCode
    missing_prerequisite: str


def audit_supported_filing_years(
    modelos: Sequence[ModeloDefinition],
    *,
    catalogue: SupportedFilingYearsCatalogue,
    sources: Mapping[str, SourceReference],
) -> tuple[SupportedFilingYearGap, ...]:
    """Enumerate every unsupported cell without turning advisories into refusal.

    The later enforcement flip consumes this same projection as blocking input;
    until then callers can inspect all gaps while registry loading remains usable.
    Period expectations are derived from revision selectors, revision ownership
    is resolved only by :func:`select_revision`, and evidence is read only from
    the selected revision's source declarations.
    """
    gaps: list[SupportedFilingYearGap] = []
    for modelo in sorted(modelos, key=lambda item: item.id):
        expected_periods = tuple(
            sorted({period for revision in modelo.revisions.values() for period in revision.period_selector.periods})
        )
        for filing_year in catalogue.years:
            for period in expected_periods:
                gaps.extend(
                    _cell_gaps(
                        modelo,
                        filing_year=filing_year,
                        period=period,
                        sources=sources,
                    ),
                )
    return tuple(gaps)


def _cell_gaps(
    modelo: ModeloDefinition,
    *,
    filing_year: int,
    period: RegistrySelectorPeriodCode,
    sources: Mapping[str, SourceReference],
) -> tuple[SupportedFilingYearGap, ...]:
    try:
        revision = select_revision(modelo, filing_year=filing_year, period=period)
    except RegistrySnapshotError:
        return (_gap(modelo.id, filing_year, period, "law-resolvable revision"),)

    gaps: list[SupportedFilingYearGap] = []
    if revision.effective_authority_grade is not RegistryAuthorityGrade.FILING:
        gaps.append(_gap(modelo.id, filing_year, period, "filing authority grade"))
    if not any(
        _source_backs_cell(sources.get(source_ref), filing_year=filing_year, period=period)
        for source_ref in revision.source_refs
    ):
        gaps.append(_gap(modelo.id, filing_year, period, "evidence-backed source cell"))
    return tuple(gaps)


def _source_backs_cell(
    source: SourceReference | None,
    *,
    filing_year: int,
    period: RegistrySelectorPeriodCode,
) -> bool:
    if source is None or source.applies_from is None or source.applies_to is None:
        return False
    if not source.applies_across(date(filing_year, 1, 1), date(filing_year, 12, 31)):
        return False
    selector = source.period_selector
    return selector is None or (
        selector.includes_year(filing_year)
        and any(selector_period_matches_request(token, period) for token in selector.periods)
    )


def _gap(
    modelo: ModeloId,
    filing_year: int,
    period: RegistrySelectorPeriodCode,
    prerequisite: str,
) -> SupportedFilingYearGap:
    return SupportedFilingYearGap(
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        missing_prerequisite=prerequisite,
    )
