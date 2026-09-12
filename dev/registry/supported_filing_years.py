"""Development-time completeness audit for declared filing-year cells."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.period import RegistrySelectorPeriodCode
from cadrumo.domain.calculations.registry.errors import RegistrySnapshotError
from cadrumo.domain.calculations.registry.ids import ModeloId
from cadrumo.domain.calculations.registry.period_selector_match import selector_period_matches_request
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.calculations.registry.temporal import select_revision


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
    """Derive the review worklist without attaching it to production authority."""
    gaps: list[SupportedFilingYearGap] = []
    for modelo in sorted(modelos, key=lambda item: item.id):
        expected_periods = tuple(
            sorted(
                {
                    period
                    for revision in modelo.revisions.values()
                    for period in revision.period_selector.declared_periods
                }
            )
        )
        for filing_year in catalogue.years:
            for period in expected_periods:
                gaps.extend(_cell_gaps(modelo, filing_year=filing_year, period=period, sources=sources))
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
        _source_backs_cell(sources.get(ref), filing_year=filing_year, period=period) for ref in revision.source_refs
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
        and any(selector_period_matches_request(token, period) for token in selector.periods_for_year(filing_year))
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
