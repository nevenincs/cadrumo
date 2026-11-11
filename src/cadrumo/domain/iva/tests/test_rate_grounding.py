"""Real-corpus grounding checks for the shipped EU IVA rate table."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import override

import pypdfium2 as pdfium
import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....core.resources.bundled_data import bundled_path
from ....core.text_fold import normalise_corpus_text
from ...calculations.registry.eu_member_state_catalogue import require_eu_member_state
from ..errors import IvaRateNotFoundError
from ..lookup import lookup_published_rate, lookup_rate
from ..rates import load_iva_rate_table
from ..schema import EUMemberState, IvaRateKind, IvaRateRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EPRS_SOURCE = "eu-eprs-iva-rates-2025-07-01"
_YOUR_EUROPE_SOURCE = "eu-your-europe-iva-rates-2026-07-13"
_RETIRED_IDENTITY_STEM = re.compile(r"(^|[._:/-])vat([._:/-]|$)", re.IGNORECASE)
_YOUR_EUROPE_CODES = {EUMemberState.from_registry("gr"): "EL"}
_COUNTRY_NAMES = {
    EUMemberState.from_registry("at"): "austria",
    EUMemberState.from_registry("be"): "belgium",
    EUMemberState.from_registry("bg"): "bulgaria",
    EUMemberState.from_registry("cy"): "cyprus",
    EUMemberState.from_registry("cz"): "czech republic",
    EUMemberState.from_registry("de"): "germany",
    EUMemberState.from_registry("dk"): "denmark",
    EUMemberState.from_registry("ee"): "estonia",
    EUMemberState.from_registry("fi"): "finland",
    EUMemberState.from_registry("fr"): "france",
    EUMemberState.from_registry("gr"): "greece",
    EUMemberState.from_registry("hr"): "croatia",
    EUMemberState.from_registry("hu"): "hungary",
    EUMemberState.from_registry("ie"): "ireland",
    EUMemberState.from_registry("it"): "italy",
    EUMemberState.from_registry("lt"): "lithuania",
    EUMemberState.from_registry("lu"): "luxembourg",
    EUMemberState.from_registry("lv"): "latvia",
    EUMemberState.from_registry("mt"): "malta",
    EUMemberState.from_registry("nl"): "netherlands",
    EUMemberState.from_registry("pl"): "poland",
    EUMemberState.from_registry("pt"): "portugal",
    EUMemberState.from_registry("ro"): "romania",
    EUMemberState.from_registry("se"): "sweden",
    EUMemberState.from_registry("si"): "slovenia",
    EUMemberState.from_registry("sk"): "slovakia",
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
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        table = load_iva_rate_table(operation=_authority_operation_for_test)
        rates = tuple(rate for member_rates in table.values() for rate in member_rates)

        # Gated on the PROPERTY, never on a tally. A hardcoded count encodes one
        # moment, trains every author to bump the constant, and then detects
        # nothing: it cannot tell a deliberately retired record from a lost one.
        # What the count was standing in for is that the table is non-empty and
        # every record it ships is grounded and resolvable -- asserted directly
        # below, and unaffected by a record being legitimately added or withdrawn.
        assert rates, "the shipped rate table must not be empty"
        assert all(rate.legal_refs for rate in rates if rate.member_state == require_eu_member_state("ES"))
        assert all(not rate.legal_refs for rate in rates if rate.member_state != require_eu_member_state("ES"))
        assert all(rate.source_refs for rate in rates if rate.member_state != require_eu_member_state("ES"))


def test_rate_source_registry_identities_use_the_canonical_iva_stem() -> None:
    """The registry and bundled corpus paths must not revive the English tax stem."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        table = load_iva_rate_table(operation=_authority_operation_for_test)
        referenced_source_ids = {
            source_id for member_rates in table.values() for rate in member_rates for source_id in rate.source_refs
        }
        violations = [
            identity
            for source_id in sorted(referenced_source_ids)
            for identity in (source_id, _authority_operation_for_test.source_reference(source_id).corpus_path)
            if _RETIRED_IDENTITY_STEM.search(identity)
        ]
        assert violations == []


@dataclass(frozen=True)
class _OfficialTexts:
    eprs_table: str
    your_europe: Path
    rate_change: dict[str, str]


# Each dated national rate change: the phrases its official notice must carry
# and the percentages that notice can ground.
_RATE_CHANGE_NOTICES: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {
    "ee-emta-iva-rate-change-2025": (
        (
            "from 1 july 2025, the standard rate of vat in estonia is 24% instead of 22%",
            "taxed at 13% vat rate instead of the current 9%",
            "press publications will rise from 5% to 9%",
        ),
        frozenset({"22", "24", "13", "9", "5"}),
    ),
    "fi-vero-iva-rate-change-2026": (
        (
            "up to 31 december 2025, the reduced rate was 14%",
            "reduced vat rate 13,5%",
            "reduced vat rate 10%",
            "basic vat rate (25,5%)",
        ),
        frozenset({"14", "13.5", "10", "25.5"}),
    ),
    "lt-vmi-iva-rate-change-2026": (
        ("iki 2025-12-31 lengvatinis 9 proc.", "nuo 2026-01-01 lengvatinis 12 proc."),
        frozenset({"9", "12"}),
    ),
    "ro-anaf-iva-rate-change-2025": (
        (
            "01 august 2025 19% la 21%, iar cota redusa de tva este 11%",
            "de la 9% la 11%",
            "se majoreaza de la 5% la 11%",
        ),
        frozenset({"19", "21", "9", "11", "5"}),
    ),
}


def _load_official_texts() -> _OfficialTexts:
    corpus = bundled_path("corpus", "eu_official", "iva")
    eprs_text = _pdf_text(corpus / "eprs-iva-rates-eu-2025-07-01.pdf")
    eprs_table = eprs_text.split("table 3", maxsplit=1)[1].split(
        "data source: taxes in europe database",
        maxsplit=1,
    )[0]
    return _OfficialTexts(
        eprs_table=eprs_table,
        your_europe=corpus / "your-europe-iva-rates-2026-07-13.html",
        rate_change={
            "ee-emta-iva-rate-change-2025": _html_text(corpus / "estonia-iva-rate-change-2025.html"),
            "fi-vero-iva-rate-change-2026": _html_text(corpus / "finland-iva-rate-change-2026.html"),
            "lt-vmi-iva-rate-change-2026": _html_text(corpus / "lithuania-iva-rate-change-2026.html"),
            "ro-anaf-iva-rate-change-2025": _pdf_text(corpus / "romania-iva-rate-change-2025.pdf"),
        },
    )


def _prove_against_eprs(rate: IvaRateRecord, pct: str, texts: _OfficialTexts) -> None:
    country = _COUNTRY_NAMES[rate.member_state]
    evidence = re.search(
        rf"\b{re.escape(country)}\s+(?P<standard>\d+(?:\.\d+)?)\s+(?P<reduced>[\d./]+)",
        texts.eprs_table,
    )
    assert evidence is not None, f"EPRS table has no parsed row for {country}"
    if rate.kind == IvaRateKind("general"):
        assert pct == evidence.group("standard")
    else:
        assert pct in evidence.group("reduced").split("/")


def _prove_against_rate_change_notices(rate: IvaRateRecord, pct: str, texts: _OfficialTexts) -> bool:
    proven = False
    for source_ref, (phrases, allowed_pcts) in _RATE_CHANGE_NOTICES.items():
        if source_ref not in rate.source_refs:
            continue
        for phrase in phrases:
            assert phrase in texts.rate_change[source_ref]
        assert pct in allowed_pcts
        proven = True
    return proven


def _prove_against_your_europe(rate: IvaRateRecord, pct: str, texts: _OfficialTexts, snapshot_date: date) -> bool:
    """Check the current-rate cell; report whether it also grounds the effective start."""
    assert _YOUR_EUROPE_SOURCE in rate.source_refs
    country_code = _YOUR_EUROPE_CODES.get(rate.member_state, rate.member_state.value.upper())
    cells = _your_europe_rate_cells(texts.your_europe, country_code)
    column = {
        IvaRateKind("general"): 1,
        IvaRateKind("reduced"): 2,
        IvaRateKind("super_reduced"): 3,
    }[rate.kind]
    assert pct in cells[column].split(" / ")
    return rate.effective_from >= snapshot_date


def test_every_foreign_numerical_rate_occurs_in_its_official_source() -> None:
    """Each foreign percentage is present in its reviewed official source artifact."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        table = load_iva_rate_table(operation=_authority_operation_for_test)
        foreign_rates = tuple(
            rate
            for member_state, member_rates in table.items()
            if member_state != require_eu_member_state("ES")
            for rate in member_rates
        )
        texts = _load_official_texts()
        snapshot_date = _authority_operation_for_test.source_reference(_YOUR_EUROPE_SOURCE).applies_from
        assert snapshot_date is not None

        proven: set[tuple[EUMemberState, IvaRateKind, date]] = set()
        for rate in foreign_rates:
            key = (rate.member_state, rate.kind, rate.effective_from)
            pct = str(rate.pct)
            initial_source_proven = _prove_against_rate_change_notices(rate, pct, texts)
            if _EPRS_SOURCE in rate.source_refs:
                _prove_against_eprs(rate, pct, texts)
                initial_source_proven = True
            # A national notice can state a rate the EU summary leaves out, as Estonia's 13 is.
            cited_or_unproven = _YOUR_EUROPE_SOURCE in rate.source_refs or not initial_source_proven
            if (
                rate.effective_until is None
                and cited_or_unproven
                and _prove_against_your_europe(rate, pct, texts, snapshot_date)
            ):
                initial_source_proven = True

            assert initial_source_proven, f"no official source proves {key} at its effective start"
            proven.add(key)

        expected = {(rate.member_state, rate.kind, rate.effective_from) for rate in foreign_rates}
        assert proven == expected


_ENGLISH_MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}


def _notice_day(text: str, pattern: str) -> date:
    """Read the day an official notice prints, from a pattern whose groups are day, month name, year."""
    match = re.search(pattern, text)
    assert match is not None, f"the official notice does not print {pattern!r}"
    day, month, year = match.groups()
    return date(int(year), _ENGLISH_MONTHS[month], int(day))


def _notice_iso_day(text: str, pattern: str) -> date:
    """Read the ISO day an official notice prints, from a pattern whose one group is that day."""
    match = re.search(pattern, text)
    assert match is not None, f"the official notice does not print {pattern!r}"
    return date.fromisoformat(match.group(1))


def _rate_changes(texts: _OfficialTexts) -> dict[str, date]:
    """The first day of each new rate, as the bundled national notices print it."""
    notices = texts.rate_change
    one_day = timedelta(days=1)
    return {
        "EE": _notice_day(
            notices["ee-emta-iva-rate-change-2025"],
            r"from (\d{1,2}) (\w+) (\d{4}), the standard rate of vat in estonia",
        ),
        "RO": _notice_day(notices["ro-anaf-iva-rate-change-2025"], r"(\d{2}) (\w+) (\d{4}) 19% la 21%"),
        "FI": _notice_day(
            notices["fi-vero-iva-rate-change-2026"], r"up to (\d{1,2}) (\w+) (\d{4}), the reduced rate was 14%"
        )
        + one_day,
        "LT": _notice_iso_day(notices["lt-vmi-iva-rate-change-2026"], r"nuo (\S+) lengvatinis 12 proc\."),
    }


def test_rate_lookup_crosses_each_grounded_change_boundary() -> None:
    """Date lookup switches exactly where the bundled national sources say it does."""
    with bundled_indexed_authority().operation() as _authority_operation_for_test:
        changes = _rate_changes(_load_official_texts())
        day = timedelta(days=1)

        def pct(member_state: str, kind: str, on_date: date) -> Decimal:
            return lookup_rate(
                require_eu_member_state(member_state),
                IvaRateKind(kind),
                on_date,
                operation=_authority_operation_for_test,
            ).pct

        assert pct("EE", "general", changes["EE"] - day) == Decimal("22")
        assert pct("EE", "general", changes["EE"]) == Decimal("24")
        assert pct("RO", "general", changes["RO"] - day) == Decimal("19")
        assert pct("RO", "general", changes["RO"]) == Decimal("21")
        assert pct("RO", "reduced", changes["RO"] - day) == Decimal("9")
        assert pct("RO", "reduced", changes["RO"]) == Decimal("11")
        assert pct("FI", "reduced", changes["FI"] - day) == Decimal("14")
        assert pct("FI", "reduced", changes["FI"]) == Decimal("13.5")
        assert pct("LT", "reduced", changes["LT"] - day) == Decimal("9")
        assert pct("LT", "reduced", changes["LT"]) == Decimal("12")
        with pytest.raises(IvaRateNotFoundError):
            lookup_published_rate(
                require_eu_member_state("DE"),
                IvaRateKind("general"),
                changes["EE"] - day,
                operation=_authority_operation_for_test,
            )
        for member_state in (
            require_eu_member_state("DE"),
            require_eu_member_state("FR"),
            require_eu_member_state("IT"),
            require_eu_member_state("NL"),
        ):
            with pytest.raises(IvaRateNotFoundError):
                lookup_published_rate(
                    member_state,
                    IvaRateKind("zero"),
                    date(filing_year_envelope().horizon, 7, 13),
                    operation=_authority_operation_for_test,
                )
