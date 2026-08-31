"""Real-corpus grounding checks for the shipped EU IVA rate table."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import override

import pypdfium2 as pdfium
import pytest

from ....core.corpus_text import normalise_corpus_text
from ....core.resources.bundled_data import bundled_path
from ....tests.registry_tree import bundled_registry_tree
from ..errors import IvaRateNotFoundError
from ..lookup import lookup_rate
from ..rates import load_iva_rate_table
from ..schema import EUMemberState, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EPRS_SOURCE = "eu-eprs-iva-rates-2025-07-01"
_YOUR_EUROPE_SOURCE = "eu-your-europe-iva-rates-2026-07-13"
_RETIRED_IDENTITY_STEM = re.compile(r"(^|[._:/-])vat([._:/-]|$)", re.IGNORECASE)
_YOUR_EUROPE_CODES = {EUMemberState.GR: "EL"}
_COUNTRY_NAMES = {
    EUMemberState.AT: "austria",
    EUMemberState.BE: "belgium",
    EUMemberState.BG: "bulgaria",
    EUMemberState.CY: "cyprus",
    EUMemberState.CZ: "czech republic",
    EUMemberState.DE: "germany",
    EUMemberState.DK: "denmark",
    EUMemberState.EE: "estonia",
    EUMemberState.FI: "finland",
    EUMemberState.FR: "france",
    EUMemberState.GR: "greece",
    EUMemberState.HR: "croatia",
    EUMemberState.HU: "hungary",
    EUMemberState.IE: "ireland",
    EUMemberState.IT: "italy",
    EUMemberState.LT: "lithuania",
    EUMemberState.LU: "luxembourg",
    EUMemberState.LV: "latvia",
    EUMemberState.MT: "malta",
    EUMemberState.NL: "netherlands",
    EUMemberState.PL: "poland",
    EUMemberState.PT: "portugal",
    EUMemberState.RO: "romania",
    EUMemberState.SE: "sweden",
    EUMemberState.SI: "slovenia",
    EUMemberState.SK: "slovakia",
}


class _VisibleText(HTMLParser):
    """Collect visible text from a bundled official HTML response."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    @override
    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _html_text(path: Path) -> str:
    parser = _VisibleText()
    parser.feed(path.read_text(encoding="utf-8"))
    return normalise_corpus_text(" ".join(parser.parts))


def _pdf_text(path: Path) -> str:
    document = pdfium.PdfDocument(str(path))
    pages: list[str] = []
    try:
        for index in range(len(document)):
            page = document[index]
            try:
                text_page = page.get_textpage()
                try:
                    pages.append(text_page.get_text_range())
                finally:
                    text_page.close()
            finally:
                page.close()
    finally:
        document.close()
    return normalise_corpus_text("\n".join(pages))


def _your_europe_rate_cells(path: Path, country_code: str) -> tuple[str, ...]:
    markup = path.read_text(encoding="utf-8")
    row = re.search(rf"<td>\s*{country_code}\s*</td>(.*?)</tr>", markup, flags=re.DOTALL | re.IGNORECASE)
    assert row is not None, f"official Your Europe table has no {country_code} row"
    cells = re.findall(r"<td>\s*(.*?)\s*</td>", row.group(1), flags=re.DOTALL | re.IGNORECASE)
    return tuple(normalise_corpus_text(re.sub(r"<[^>]+>", " ", cell)) for cell in cells)


def test_every_shipped_rate_resolves_registry_legal_and_source_evidence() -> None:
    """Loading the real table verifies every referenced catalogue row and corpus hash."""
    table = load_iva_rate_table()
    rates = tuple(rate for member_rates in table.values() for rate in member_rates)

    # Gated on the PROPERTY, never on a tally. A hardcoded count encodes one
    # moment, trains every author to bump the constant, and then detects
    # nothing: it cannot tell a deliberately retired record from a lost one.
    # What the count was standing in for is that the table is non-empty and
    # every record it ships is grounded and resolvable -- asserted directly
    # below, and unaffected by a record being legitimately added or withdrawn.
    assert rates, "the shipped rate table must not be empty"
    assert all(rate.legal_refs for rate in rates if rate.member_state is EUMemberState.ES)
    assert all(not rate.legal_refs for rate in rates if rate.member_state is not EUMemberState.ES)
    assert all(rate.source_refs for rate in rates if rate.member_state is not EUMemberState.ES)


def test_rate_source_registry_identities_use_the_canonical_iva_stem() -> None:
    """The registry and bundled corpus paths must not revive the English tax stem."""
    table = load_iva_rate_table()
    referenced_source_ids = {
        source_id for member_rates in table.values() for rate in member_rates for source_id in rate.source_refs
    }
    _, catalogues = bundled_registry_tree()

    violations = [
        identity
        for source_id in sorted(referenced_source_ids)
        for identity in (source_id, catalogues.sources[source_id].corpus_path)
        if _RETIRED_IDENTITY_STEM.search(identity)
    ]
    assert violations == []


def test_every_foreign_numerical_rate_occurs_in_its_official_source() -> None:
    """Each foreign percentage is present in its reviewed official source artifact."""
    table = load_iva_rate_table()
    foreign_rates = tuple(
        rate
        for member_state, member_rates in table.items()
        if member_state is not EUMemberState.ES
        for rate in member_rates
    )
    corpus = bundled_path("corpus", "eu_official", "iva")
    eprs_text = _pdf_text(corpus / "eprs-iva-rates-eu-2025-07-01.pdf")
    eprs_table = eprs_text.split("table 3", maxsplit=1)[1].split(
        "data source: taxes in europe database",
        maxsplit=1,
    )[0]
    your_europe = corpus / "your-europe-iva-rates-2026-07-13.html"
    estonia_text = _html_text(corpus / "estonia-iva-rate-change-2025.html")
    finland_text = _html_text(corpus / "finland-iva-rate-change-2026.html")
    lithuania_text = _html_text(corpus / "lithuania-iva-rate-change-2026.html")
    romania_text = _pdf_text(corpus / "romania-iva-rate-change-2025.pdf")

    proven: set[tuple[EUMemberState, IvaRateKind, date]] = set()
    for rate in foreign_rates:
        key = (rate.member_state, rate.kind, rate.effective_from)
        pct = str(rate.pct)
        initial_source_proven = False
        if _EPRS_SOURCE in rate.source_refs:
            country = _COUNTRY_NAMES[rate.member_state]
            evidence = re.search(
                rf"\b{re.escape(country)}\s+(?P<standard>\d+(?:\.\d+)?)\s+(?P<reduced>[\d./]+)",
                eprs_table,
            )
            assert evidence is not None, f"EPRS table has no parsed row for {country}"
            if rate.kind is IvaRateKind.GENERAL:
                assert pct == evidence.group("standard")
            else:
                assert pct in evidence.group("reduced").split("/")
            initial_source_proven = True
        if "ee-emta-iva-rate-change-2025" in rate.source_refs:
            assert "from 1 july 2025, the standard rate of vat in estonia is 24% instead of 22%" in estonia_text
            assert pct in {"22", "24"}
            initial_source_proven = True
        if "fi-vero-iva-rate-change-2026" in rate.source_refs:
            assert "up to 31 december 2025, the reduced rate was 14%" in finland_text
            assert "reduced vat rate 13,5%" in finland_text
            assert pct in {"14", "13.5"}
            initial_source_proven = True
        if "lt-vmi-iva-rate-change-2026" in rate.source_refs:
            assert "iki 2025-12-31 lengvatinis 9 proc." in lithuania_text
            assert "nuo 2026-01-01 lengvatinis 12 proc." in lithuania_text
            assert pct in {"9", "12"}
            initial_source_proven = True
        if "ro-anaf-iva-rate-change-2025" in rate.source_refs:
            assert "01 august 2025 19% la 21%, iar cota redusa de tva este 11%" in romania_text
            assert "de la 9% la 11%" in romania_text
            assert pct in {"19", "21", "9", "11"}
            initial_source_proven = True

        if rate.effective_until is None:
            assert _YOUR_EUROPE_SOURCE in rate.source_refs
            country_code = _YOUR_EUROPE_CODES.get(rate.member_state, rate.member_state.value.upper())
            cells = _your_europe_rate_cells(your_europe, country_code)
            column = {
                IvaRateKind.GENERAL: 1,
                IvaRateKind.REDUCED: 2,
                IvaRateKind.SUPER_REDUCED: 3,
            }[rate.kind]
            assert pct in cells[column].split(" / ")
            if rate.effective_from >= date(2026, 7, 13):
                initial_source_proven = True

        assert initial_source_proven, f"no official source proves {key} at its effective start"
        proven.add(key)

    expected = {(rate.member_state, rate.kind, rate.effective_from) for rate in foreign_rates}
    assert proven == expected


def test_rate_lookup_crosses_each_grounded_change_boundary() -> None:
    """Date lookup switches exactly where the bundled national sources say it does."""
    assert lookup_rate(EUMemberState.EE, IvaRateKind.GENERAL, date(2025, 6, 30)).pct == Decimal("22")
    assert lookup_rate(EUMemberState.EE, IvaRateKind.GENERAL, date(2025, 7, 1)).pct == Decimal("24")
    assert lookup_rate(EUMemberState.RO, IvaRateKind.GENERAL, date(2025, 7, 31)).pct == Decimal("19")
    assert lookup_rate(EUMemberState.RO, IvaRateKind.GENERAL, date(2025, 8, 1)).pct == Decimal("21")
    assert lookup_rate(EUMemberState.RO, IvaRateKind.REDUCED, date(2025, 7, 31)).pct == Decimal("9")
    assert lookup_rate(EUMemberState.RO, IvaRateKind.REDUCED, date(2025, 8, 1)).pct == Decimal("11")
    assert lookup_rate(EUMemberState.FI, IvaRateKind.REDUCED, date(2025, 12, 31)).pct == Decimal("14")
    assert lookup_rate(EUMemberState.FI, IvaRateKind.REDUCED, date(2026, 1, 1)).pct == Decimal("13.5")
    assert lookup_rate(EUMemberState.LT, IvaRateKind.REDUCED, date(2025, 12, 31)).pct == Decimal("9")
    assert lookup_rate(EUMemberState.LT, IvaRateKind.REDUCED, date(2026, 1, 1)).pct == Decimal("12")
    with pytest.raises(IvaRateNotFoundError):
        lookup_rate(EUMemberState.DE, IvaRateKind.GENERAL, date(2025, 6, 30))
    for member_state in (EUMemberState.DE, EUMemberState.FR, EUMemberState.IT, EUMemberState.NL):
        with pytest.raises(IvaRateNotFoundError):
            lookup_rate(member_state, IvaRateKind.ZERO, date(2026, 7, 13))
