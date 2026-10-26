"""The 2022 eight-page form and the 2023 replacement page retain their own owners."""

from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _model():
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/390"))


@pytest.mark.parametrize("year", ("2022", "2023"))
def test_historical_sources_pages_and_context_owners(year):
    revision = _model().revisions[year]
    form = revision.form_layouts[0]
    assert form_layout_failures(revision) == ()
    assert form.seed_source == "authored" and form.review.state == "generated"
    assert [p.id for p in form.pages] == [f"pag-{n}" for n in range(1, 9)]
    for number, page in enumerate(form.pages, 1):
        expected = f"BOE-A-2022-19290 Annex III, page {number}, printed {159001 + number}"
        if year == "2023" and number == 2:
            expected = "BOE-A-2023-26632 Annex IV, page 2, printed 176085"
        assert page.official_ref == expected
    sources = {s.source_ref for s in form.design_sources}
    assert "boe-modelo-390-2022-form-pdf" in sources
    assert ("boe-modelo-390-2023-form-pdf" in sources) == (year == "2023")
    assert not any("2024" in s or "2025" in s or "2026" in s for s in sources)
    contexts = {b.id: b for s in form.pages[0].sections for b in s.blocks if b.kind == "context_field"}
    assert set(contexts) == {"nif", "surname", "given-name", "year", "prior-receipt"}
    for name, producer in {
        "nif": "taxpayer.tax_id",
        "surname": "taxpayer.surnames_or_legal_name",
        "given-name": "taxpayer.given_name",
        "prior-receipt": "amendment_evidence.original_aeat_receipt",
    }.items():
        assert contexts[name].export_layout_id == revision.export_layouts[0].id
        assert resolve_form_context_field(revision, contexts[name]).producer_key == producer
    assert resolve_form_context_field(revision, contexts["year"]).draft_attribute == "filing_year"


@pytest.mark.parametrize("year", ("2022", "2023"))
def test_nine_four_rate_deduction_tables_follow_the_printed_page(year):
    form = _model().revisions[year].form_layouts[0]
    page = form.pages[2]
    numbers = {p.casilla_id: p.box_number for p in form.placements}
    printed_groups = (
        "190 191 724 725 603 604 605 606 48 49",
        "506 507 726 727 607 608 609 610 512 513",
        "196 197 728 729 611 612 613 614 50 51",
        "514 515 730 731 615 616 617 618 520 521",
        "202 203 732 733 619 620 621 622 52 53",
        "208 209 734 735 623 624 625 626 54 55",
        "214 215 736 737 627 628 629 630 56 57",
        "220 221 738 739 631 632 633 634 58 59",
        "587 588 740 741 635 636 637 638 597 598",
    )
    assert len(page.sections) == 9
    for section, printed in zip(page.sections, printed_groups, strict=True):
        assert len(section.blocks) == 1
        grid = section.blocks[0]
        assert len(grid.rows) == 5
        assert [numbers[c.casilla_id] for row in grid.rows for c in row.cells] == printed.split()
        assert [row.key for row in grid.rows[:4]] == ["tipo-4-pct", "tipo-5-pct", "tipo-10-pct", "tipo-21-pct"]
    continuation = form.pages[3]
    assert len(continuation.sections) == 2
    assert len(continuation.sections[0].blocks) == 1
    adjustment = continuation.sections[0].blocks[0]
    assert [numbers[c.casilla_id] for row in adjustment.rows for c in row.cells] == [
        "60",
        "61",
        "660",
        "661",
        "639",
        "62",
        "651",
        "652",
    ]
    assert [numbers[b.casilla_id] for b in continuation.sections[1].blocks] == ["63", "522", "64", "65"]


@pytest.mark.parametrize("year", ("2022", "2023"))
def test_surcharge_uses_revision_specific_rate_owners_not_aggregate_values(year):
    form = _model().revisions[year].form_layouts[0]
    numbers = {p.casilla_id: p.box_number for p in form.placements}
    section = next(s for s in form.pages[1].sections if s.id.endswith("fef341"))
    rates = ("0-5", "1-4", "5-2", "1-75") if year == "2022" else ("0", "0-5", "0-62", "1-4", "5-2", "1-75")
    boxes = ("35 36", "599 600", "601 602", "41 42")
    if year == "2023":
        boxes = ("663 664", "35 36", "665 666", "599 600", "601 602", "41 42")
    for row, rate, printed in zip(section.blocks[0].rows, rates, boxes, strict=True):
        assert [numbers[c.casilla_id] for c in row.cells] == printed.split()
        assert [c.casilla_id for c in row.cells] == [
            f"iva.anual.repercutido.recargo.tipo-{rate}.base",
            f"iva.anual.repercutido.recargo.tipo-{rate}.cuota",
        ]
    for suffix in ("general", "reducido", "super-reducido"):
        placement = next(p for p in form.placements if p.casilla_id == f"iva.anual.repercutido.recargo.{suffix}")
        assert placement.kind == "working_figure" and placement.box_number is None


@pytest.mark.parametrize("year", ("2022", "2023"))
def test_settlement_restores_printed_repetitions_without_future_fuel_payment(year):
    revision = _model().revisions[year]
    form = revision.form_layouts[0]
    numbers = {p.casilla_id: p.box_number for p in form.placements}
    sections = form.pages[5].sections
    assert [numbers[b.casilla_id] for b in sections[0].blocks] == ["658", "84", "659", "85", "86"]
    assert [numbers[b.casilla_id] for b in sections[1].blocks] == [
        "87",
        "88",
        "89",
        "90",
        "91",
        "658",
        "84",
        "92",
        "659",
        "93",
        "94",
    ]
    repeated = [p for p in form.placements if p.box_number in {"658", "84", "659"}]
    assert len(repeated) == 3
    for placement in repeated:
        assert len(placement.aliases) == 1
        assert placement.aliases[0].section_id == sections[1].id
        # Duplicate positions must be explicitly declared; removing permission is rejected.
        malformed = form.model_copy(
            update={
                "placements": tuple(
                    p.model_copy(update={"aliases": ()}) if p == placement else p for p in form.placements
                ),
            }
        )
        assert form_layout_failures(revision.model_copy(update={"form_layouts": (malformed,)}))
