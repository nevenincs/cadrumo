"""Annual filing windows of Modelos 151, 165 and 180 against AEAT's own calendars.

A supported ejercicio is filed in the following year, and the Calendario del
Contribuyente AEAT publishes for that year prints each modelo under the day its
plazo ends. Every supported ejercicio whose calendar is bundled must therefore
carry its window in the edition the canonical resolver selects for it, and the
window's nominal close must be the date the calendar prints once a weekend is
skipped. The expected dates are read from the bundled calendar text and the
approving orden rather than restated here, so neither oracle is the registry
declaration under test.

Modelo 151 files on the Renta calendar by remission, and the calendar's
domiciliacion table prints its payment cutoff beside its close. Where the
governing orden fixes a different cutoff of its own, the two official
statements disagree and the window must declare none rather than pick one.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from datetime import date, timedelta
from functools import cache

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority as CompiledAuthority
from cadrumo.domain.calculations.registry.schema import ModeloRevision, RegistryCatalogues
from cadrumo.domain.calculations.registry.schema_deadlines import DeadlineWindowDefinition
from dev.corpus.manual_corpus_sidecar import (
    MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX,
    MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX,
    ManualCorpusTextSidecar,
)

from ..compiler.loader import load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERIOD = "0A"
_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
_MONTH = "|".join(_MONTHS)
_CALENDAR_HEADING = re.compile(rf"hasta el (\d{{1,2}}) de ({_MONTH})")
_DOMICILIACION_ROW = re.compile(
    rf"modelos 100, 151 y 714 hasta (\d{{1,2}}) de ({_MONTH}) hasta (\d{{1,2}}) de ({_MONTH})"
)
_ORDEN_151_2015 = "orden-hap-2783-2015"


@cache
def _catalogues() -> RegistryCatalogues:
    return load_shared_catalogues(bundled_path("registry", "aeat"))


@cache
def _supported_years() -> tuple[int, ...]:
    support = _catalogues().supported_filing_years
    assert support is not None, "the registry declares no supported filing years"
    return tuple(int(year) for year in support.years)


def _calendar_source_id(filing_year: int) -> str:
    """The catalogued calendar of the year an ejercicio is filed in."""
    return f"aeat-calendario-contribuyente-{filing_year + 1}"


@cache
def _calendar_text(filing_year: int) -> str:
    source = _catalogues().sources[_calendar_source_id(filing_year)]
    relative = str(source.corpus_path).removeprefix(MANUAL_CORPUS_TEXT_CORPUS_PATH_PREFIX)
    sidecar = bundled_path("manual_corpus_text", relative + MANUAL_CORPUS_TEXT_SIDECAR_SUFFIX)
    return ManualCorpusTextSidecar.model_validate_json(sidecar.read_text(encoding="utf-8")).normalised_text


def _calendar_years() -> tuple[int, ...]:
    """Supported ejercicios whose filing-year calendar is bundled."""
    return tuple(year for year in _supported_years() if _calendar_source_id(year) in _catalogues().sources)


CALENDAR_YEARS = _calendar_years()


def _printed(day: str, month: str, filing_year: int) -> date:
    return date(filing_year + 1, _MONTHS.index(month) + 1, int(day))


def _heading_before(text: str, position: int, filing_year: int) -> date:
    headings = list(_CALENDAR_HEADING.finditer(text, 0, position))
    assert headings, (filing_year, text[max(0, position - 200) : position])
    day, month = headings[-1].groups()
    return _printed(day, month, filing_year)


def _first_weekday_from(nominal: date) -> date:
    shifted = nominal
    while shifted.weekday() >= 5:
        shifted += timedelta(days=1)
    return shifted


@pytest.fixture(scope="module")
def edition(registry_authority: CompiledAuthority) -> Callable[[str, int], ModeloRevision]:
    """The annual edition the canonical resolver selects for one modelo and ejercicio."""

    def select(modelo: str, filing_year: int) -> ModeloRevision:
        return registry_authority.snapshot(
            modelo, filing_year=filing_year, period=_PERIOD, grade=RegistryAuthorityGrade.APPLICABILITY
        ).revision

    return select


def _annual_window(revision: ModeloRevision, filing_year: int) -> DeadlineWindowDefinition:
    windows = [
        window
        for window in revision.deadline_windows
        if window.period.filing_year == filing_year and window.period.registry_token == _PERIOD
    ]
    assert len(windows) == 1, (revision.id, filing_year, [str(window.id) for window in revision.deadline_windows])
    return windows[0]


def test_the_calendars_reach_the_support_floor() -> None:
    assert min(_supported_years()) in CALENDAR_YEARS


@pytest.mark.parametrize("modelo", ("165", "180"))
@pytest.mark.parametrize("filing_year", CALENDAR_YEARS)
def test_january_summary_window_closes_where_the_calendar_prints_it(
    edition: Callable[[str, int], ModeloRevision], modelo: str, filing_year: int
) -> None:
    text = _calendar_text(filing_year)
    listing = re.search(rf"resumen anual {filing_year}: (?:[0-9a-z-]+, )*{modelo}\b", text)
    assert listing is not None, (modelo, filing_year)
    printed = _heading_before(text, listing.start(), filing_year)

    window = _annual_window(edition(modelo, filing_year), filing_year)

    assert window.opens_on == date(filing_year + 1, 1, 1)
    assert window.closes_on <= printed
    assert _first_weekday_from(window.closes_on) == printed


@cache
def _orden_2015_domiciliacion_day() -> tuple[str, str]:
    """The fixed domiciliacion day Orden HAP/2783/2015 art. 4.2 states for its own model."""
    raw = bundled_path("corpus", "normatives", "html", f"{_ORDEN_151_2015}.html").read_text(encoding="utf-8")
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    match = re.search(
        rf"domiciliación bancaria, esta podrá realizarse desde el inicio del plazo hasta el (\d+) de ({_MONTH})", text
    )
    assert match is not None
    return str(match.group(1)), str(match.group(2))


@pytest.mark.parametrize("filing_year", CALENDAR_YEARS)
def test_modelo_151_window_matches_the_renta_calendar(
    edition: Callable[[str, int], ModeloRevision], filing_year: int
) -> None:
    text = _calendar_text(filing_year)
    row = _DOMICILIACION_ROW.search(text)
    assert row is not None, filing_year
    domiciliacion = _printed(row.group(1), row.group(2), filing_year)
    closes = _printed(row.group(3), row.group(4), filing_year)

    window = _annual_window(edition("151", filing_year), filing_year)

    assert window.closes_on == closes
    assert window.opens_on < window.closes_on
    if window.payment_cutoff_on is not None:
        assert window.payment_cutoff_on == domiciliacion
    else:
        # Only an edition governed by the 2015 orden may leave it undeclared, and
        # only because that orden's own fixed date contradicts the calendar.
        assert any(str(ref).startswith(f"{_ORDEN_151_2015}:") for ref in window.legal_refs)
        assert _printed(*_orden_2015_domiciliacion_day(), filing_year) != domiciliacion


@pytest.mark.parametrize("filing_year", _supported_years())
def test_modelo_151_states_one_schedule_and_one_export_link(
    edition: Callable[[str, int], ModeloRevision], filing_year: int
) -> None:
    revision = edition("151", filing_year)
    exports = [link for link in revision.application_links if link.surface == "export"]

    assert [str(schedule.id) for schedule in revision.filing_schedules] == ["modelo-151-anual"]
    assert [str(link.id) for link in exports] == ["modelo-151-export"]

    # The link and the schedule cite the same approving orden: the one whose
    # model the edition's export layout reproduces.
    (link,) = exports
    link_ordens = {str(ref).split(":")[0] for ref in link.legal_refs if str(ref).startswith("orden-")}
    schedule_ordens = {
        str(ref).split(":")[0] for ref in revision.filing_schedules[0].legal_refs if str(ref).startswith("orden-")
    }
    layout_sources = {str(ref) for layout in revision.export_layouts for ref in layout.source_refs}
    assert len(link_ordens) == 1
    assert schedule_ordens == link_ordens
    assert {str(ref) for ref in link.source_refs} == layout_sources
