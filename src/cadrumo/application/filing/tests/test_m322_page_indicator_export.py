"""Modelo 322 writes its página-complementaria indicator blank and marks a complementaria in its own box.

Every Modelo 322 record design (``aeat-dr-322-2022``, ``aeat-dr-322-2023``,
``aeat-dr-322-2024-2025`` and ``aeat-dr-322-2026``) prints posición 12 of
DR32202, DR32203 and DR32204 as ``Indicador de página complementaria``,
``obligatorio``, ``blanco``: it marks a further page of the same type, which a
Modelo 322 file never carries, and says nothing about the declaration's kind.
The declaración complementaria is declared on DR32202 itself, in the
``Autoliquidación complementaria`` box, ``X o blanco``.

So an original return writes blank at every posición 12 and in the
complementaria box, and a complementaria writes ``X`` in that box only. The
expected positions are read from each edition's record design in the bundled
corpus, never from the layout under test.

Real-behaviour: the published authority, the real producer snapshot and the
whole ``export_draft`` path with its post-write verification. No mocks, stubs,
skips or xfail.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath

import pytest

from ....core.modelo import Modelo
from ....core.period import Period
from ....core.prior_domiciliation_election import PriorDomiciliationElection
from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ....domain.calculations.registry.tests.authored_editions import open_ended_revision
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_source_reference,
    published_supported_filing_years,
)
from ....domain.filing.software_identity import development_mock_software_identity
from ....domain.submission.models import ModeloDraftStatus
from ..draft_construction import build_draft
from ..export import export_draft
from ..producer_snapshot import FilingProducerSnapshot, GeneralFilingProfileFacts, build_filing_producer_snapshot
from ..runtime import ModeloOperatorProfile
from .export_support import export_schema_provider, typed_producer_snapshot

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_MODELO = "322"
_PROJECTED_YEAR = "errors.snapshot.filing_year_projected"
_INDICATED_PAGES = ("DR32202", "DR32203", "DR32204")
_COMPLEMENTARIA_PAGE = "DR32202"
_PAGE_INDICATOR = "Indicador de página complementaria"
_COMPLEMENTARIA_BOX = "Autoliquidación complementaria. Autoliquidación complementaria"
_OPENING_CONSTANT = "Constante "
#: The Contenido column each design prints for the two slots.
_INDICATOR_CONTENT = "blanco"
_BOX_CONTENT = "X o blanco"
_BLANK = " "
_MARKED = "X"


@dataclass(frozen=True, slots=True)
class _DesignedPage:
    """One record of a Modelo 322 design: its opening constant and the one-based positions this test reads."""

    opening: bytes
    page_indicator: int
    complementaria_box: int | None


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")]


def _page_from_rows(rows: list[list[str]]) -> _DesignedPage:
    opening = next(cell for row in rows for cell in row if cell.startswith(_OPENING_CONSTANT))
    [indicator_row] = [row for row in rows if _PAGE_INDICATOR in row]
    assert indicator_row[-1] == _INDICATOR_CONTENT, indicator_row
    indicator = int(indicator_row[1])
    boxes = [row for row in rows if _COMPLEMENTARIA_BOX in row]
    assert all(row[-1] == _BOX_CONTENT for row in boxes), boxes
    box = int(boxes[0][1]) if boxes else None
    return _DesignedPage(
        opening=opening.removeprefix(_OPENING_CONSTANT).strip('"').encode("ascii"),
        page_indicator=indicator,
        complementaria_box=box,
    )


@cache
def _designed_pages(source_ref: str) -> dict[str, _DesignedPage]:
    """Read each indicated page of one Modelo 322 record design from its extracted corpus text."""
    relative = PurePosixPath(published_source_reference(source_ref).corpus_path)
    design = bundled_path(*relative.parent.parts, f"{relative.name}.extracted.md")
    sections: dict[str, list[list[str]]] = {}
    current: list[list[str]] | None = None
    for line in design.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            sheet = line.removeprefix("# ").strip()
            current = sections.setdefault(sheet, []) if sheet in _INDICATED_PAGES else None
        elif current is not None and line[:1].isdigit():
            current.append(_cells(line))
    assert set(sections) == set(_INDICATED_PAGES), source_ref
    return {sheet: _page_from_rows(rows) for sheet, rows in sections.items()}


def _period() -> str:
    """The last period of the modelo's monthly selector, which every Modelo 322 edition shares."""
    periods = open_ended_revision(_MODELO).period_selector.periods
    assert periods
    return periods[-1]


@cache
def _own_edition_years() -> tuple[int, ...]:
    """The supported years an authored Modelo 322 edition of their own governs; projected years are left out."""
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot(_MODELO, filing_year=year, period=_period())
        except FilingYearOutsideSupportEnvelopeError:
            continue
        except RegistryValidationError as refused:
            if refused.translated_message != _PROJECTED_YEAR:
                raise
            continue
        years.append(year)
    return tuple(years)


def _producer_snapshot(*, complementaria: bool) -> FilingProducerSnapshot:
    standard = typed_producer_snapshot(complementaria=complementaria)
    return build_filing_producer_snapshot(
        modelo=Modelo(_MODELO),
        taxpayer_tax_id=standard.taxpayer_tax_id,
        taxpayer_identity=standard.taxpayer_identity,
        presenter=standard.presenter,
        model_profile=GeneralFilingProfileFacts(),
        elections=standard.elections,
        amendment_evidence=standard.amendment_evidence,
        refund_account=None,
        charge_account=None,
        m303_filing_facts=None,
    )


def _exported(year: int, tmp_path: Path, *, complementaria: bool) -> tuple[bytes, dict[str, _DesignedPage]]:
    """Export a whole Modelo 322 return for ``year`` and return its bytes with the design that governs them."""
    provider = export_schema_provider(filing_year=year, period=_period(), modelos=(_MODELO,))
    draft = build_draft(
        modelo=_MODELO,
        period=Period.from_year_and_code(year, _period()),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="Grupo IVA prueba"),
        inputs={},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})
    output_path = tmp_path / "modelo-322.txt"

    export_draft(
        draft,
        output_path=output_path,
        producer_snapshot=_producer_snapshot(complementaria=complementaria),
        product_software_identity=development_mock_software_identity(),
        prior_domiciliation_election=PriorDomiciliationElection.KEEP,
        schema_provider=provider,
    )

    [layout] = provider.get_snapshot(_MODELO).revision.export_layouts
    [design] = layout.source_refs
    return output_path.read_bytes(), _designed_pages(str(design))


def _byte_at(payload: bytes, page: _DesignedPage, position: int) -> str:
    """Return the one byte at a design's one-based ``position`` of the single occurrence of ``page``."""
    assert payload.count(page.opening) == 1, page.opening
    start = payload.index(page.opening)
    return payload[start + position - 1 : start + position].decode("ascii")


def test_some_supported_year_exports_an_own_edition() -> None:
    assert _own_edition_years()


@pytest.mark.parametrize("year", _own_edition_years())
def test_an_original_return_writes_every_page_indicator_blank(year: int, tmp_path: Path) -> None:
    payload, pages = _exported(year, tmp_path, complementaria=False)

    for sheet in _INDICATED_PAGES:
        assert _byte_at(payload, pages[sheet], pages[sheet].page_indicator) == _BLANK, (year, sheet)
    complementaria = pages[_COMPLEMENTARIA_PAGE]
    assert complementaria.complementaria_box is not None
    assert _byte_at(payload, complementaria, complementaria.complementaria_box) == _BLANK, year


@pytest.mark.parametrize("year", _own_edition_years())
def test_a_complementaria_is_marked_only_in_its_own_box(year: int, tmp_path: Path) -> None:
    payload, pages = _exported(year, tmp_path, complementaria=True)

    for sheet in _INDICATED_PAGES:
        assert _byte_at(payload, pages[sheet], pages[sheet].page_indicator) == _BLANK, (year, sheet)
    complementaria = pages[_COMPLEMENTARIA_PAGE]
    assert complementaria.complementaria_box is not None
    assert _byte_at(payload, complementaria, complementaria.complementaria_box) == _MARKED, year
