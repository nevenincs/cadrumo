"""Filing periods used to render each export-bearing edition.

Each Modelo's table maps an edition (revision id) to the period it is rendered
for. The table is read from the registry, never written out: an edition is
rendered at the first supported ``(year, period)`` that the canonical revision
selection resolves to that very edition, so the support envelope and each
edition's own period selector decide the year and the period token. An edition
that serves no supported year has no renderable export and no entry.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from functools import cache
from typing import Final, override

from cadrumo.core.period import Period, PeriodError
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.temporal import select_revision

from .compiler.loader import load_modelo_directory, load_shared_catalogues

#: The annual period, then the quarters, then the payment periods: the natural renderings of an edition that
#: serves them. Any other token (the months) is used only when an edition serves nothing else.
_PREFERRED_TOKENS: Final = ("0A", "1T", "2T", "3T", "4T", "1P", "2P", "3P")


def _token_preference(token: str) -> int:
    return _PREFERRED_TOKENS.index(token) if token in _PREFERRED_TOKENS else len(_PREFERRED_TOKENS)


def _first_supported_period(
    modelo: ModeloDefinition, revision: ModeloRevision, support: SupportedFilingYearsCatalogue
) -> Period | None:
    """The first supported ``(year, period)`` the canonical selection resolves to ``revision``, if any."""
    for year in support.years:
        if not revision.period_selector.includes_year(year):
            continue
        served = tuple(str(token) for token in revision.period_selector.periods_for_year(year))
        for token in sorted(served, key=_token_preference):
            try:
                selected = select_revision(modelo, filing_year=year, period=token, support=support)
                candidate = Period.from_year_and_code(year, token)
            except (RegistryError, PeriodError, ValueError):
                continue
            if str(selected.id) == str(revision.id):
                return candidate
    return None


@cache
def _edition_periods(modelo_id: str) -> Mapping[str, Period]:
    """Every export-bearing edition of ``modelo_id`` that serves a supported year, with its rendering period."""
    registry_root = bundled_path("registry", "aeat")
    support = load_shared_catalogues(registry_root).require_supported_filing_years()
    modelo = load_modelo_directory(registry_root / "modelos" / modelo_id)
    periods: dict[str, Period] = {}
    for revision_id, revision in modelo.revisions.items():
        if not revision.export_layouts:
            continue
        period = _first_supported_period(modelo, revision, support)
        if period is not None:
            periods[str(revision_id)] = period
    return periods


class _EditionPeriods(Mapping[str, Period]):
    """One Modelo's edition-to-period table, read from the registry on first use."""

    def __init__(self, modelo_id: str) -> None:
        self._modelo_id = modelo_id

    @override
    def __getitem__(self, revision_id: str) -> Period:
        return _edition_periods(self._modelo_id)[revision_id]

    @override
    def __iter__(self) -> Iterator[str]:
        return iter(_edition_periods(self._modelo_id))

    @override
    def __len__(self) -> int:
        return len(_edition_periods(self._modelo_id))


#: The period each Modelo 303 edition is rendered for.
M303_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("303")
#: The period each Modelo 189 edition is rendered for.
M189_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("189")
#: The period each Modelo 190 edition is rendered for.
M190_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("190")
#: The period each Modelo 193 edition is rendered for.
M193_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("193")
#: The period each Modelo 232 edition is rendered for.
M232_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("232")
#: The period each Modelo 345 edition is rendered for.
M345_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("345")
#: The period each Modelo 347 edition is rendered for.
M347_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("347")
#: The period each Modelo 390 edition is rendered for.
M390_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("390")
#: The period each Modelo 131 edition is rendered for.
M131_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("131")
#: The period each Modelo 714 edition is rendered for.
M714_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("714")
#: The period each Modelo 322 edition is rendered for.
M322_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("322")
#: The period each Modelo 490 edition is rendered for.
M490_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("490")
#: The period each Modelo 309 edition is rendered for.
M309_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("309")
#: The period each Modelo 308 edition is rendered for.
M308_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("308")
#: The period each Modelo 123 edition is rendered for.
M123_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("123")
#: The period each Modelo 604 edition is rendered for.
M604_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("604")
#: The period each Modelo 151 edition is rendered for.
M151_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("151")
#: The period each Modelo 165 edition is rendered for.
M165_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("165")
#: The period each Modelo 184 edition is rendered for.
M184_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("184")
#: The period each Modelo 200 edition is rendered for.
M200_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("200")
#: The period each Modelo 202 edition is rendered for.
M202_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("202")
#: The period each Modelo 222 edition is rendered for.
M222_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("222")
#: The period each Modelo 296 edition is rendered for.
M296_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("296")
#: The period each Modelo 180 edition is rendered for.
M180_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("180")
#: The period each Modelo 185 edition is rendered for.
M185_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("185")
#: The period each Modelo 210 edition is rendered for.
M210_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("210")
#: The period each Modelo 270 edition is rendered for.
M270_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("270")
#: The period each Modelo 341 edition is rendered for.
M341_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("341")
#: The period each Modelo 353 edition is rendered for.
M353_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("353")
#: The period each Modelo 576 edition is rendered for.
M576_SCENARIO_PERIODS: Final[Mapping[str, Period]] = _EditionPeriods("576")
