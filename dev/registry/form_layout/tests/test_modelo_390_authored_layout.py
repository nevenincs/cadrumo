"""Historical and current Modelo 390 geometry and arithmetic grounded in BOE forms."""

from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.formula_runtime import evaluate_expression
from cadrumo.domain.calculations.registry.formula_runtime_ops import UnresolvedFormulaDependencyError

from ...compiler.form_layout_integrity import form_layout_failures
from ...compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _model():
    return load_modelo_directory(Path("src/cadrumo/_data/registry/aeat/modelos/390"))


@pytest.mark.parametrize("year", ("2024", "2025"))
def test_identity_uses_exact_registry_owners_and_refuses_wrong_records(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-1")
    assert "136895" in page.official_ref
    contexts = {b.id: b for s in page.sections for b in s.blocks if b.kind == "context_field"}
    assert set(contexts) == {"nif", "surname", "given-name", "year", "prior-receipt"}
    expected = {
        "nif": "taxpayer.tax_id",
        "surname": "taxpayer.surnames_or_legal_name",
        "given-name": "taxpayer.given_name",
        "prior-receipt": "amendment_evidence.original_aeat_receipt",
    }
    for name, owner in expected.items():
        assert resolve_form_context_field(revision, contexts[name]).producer_key == owner
    assert resolve_form_context_field(revision, contexts["year"]).draft_attribute == "filing_year"
    with pytest.raises(RegistryValidationError, match="exactly one"):
        resolve_form_context_field(revision, contexts["nif"].model_copy(update={"export_record_id": "missing-record"}))
    # A predecessor's filing field is not an owner for the designless 2026 edition.
    with pytest.raises(RegistryValidationError, match="exactly one"):
        resolve_form_context_field(_model().revisions["2026"], contexts["nif"])


@pytest.mark.parametrize("year", ("2024", "2025"))
def test_six_activity_rows_keep_description_code_and_iae_together(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    page = next(page for page in revision.form_layouts[0].pages if page.id == "pag-1")
    section = next(section for section in page.sections if section.id == "3-activities")
    grid = section.blocks[0]
    assert [column.official_heading for column in grid.columns] == ["Actividad", "Código de actividad", "Epígrafe IAE"]
    assert len(grid.rows) == 6
    for row, suffix, iae_suffix in zip(
        grid.rows,
        ("principal", "otras-1a", "otras-2a", "otras-3a", "otras-4a", "otras-5a"),
        ("principal", "otras-1o", "otras-2o", "otras-3o", "otras-4o", "otras-5o"),
        strict=True,
    ):
        assert [cell.binding_id for cell in row.cells] == [
            f"modelo-390.page_1.datos-estadisticos-a-actividades-{suffix}",
            f"modelo-390.page_1.datos-estadisticos-b-codigo-de-actividad-{suffix}",
            f"modelo-390.page_1.datos-estadisticos-c-epigrafe-i-a-e-{iae_suffix}",
        ]


@pytest.mark.parametrize("year", ("2024", "2025"))
def test_legal_representatives_follow_three_printed_columns_without_crossing_bindings(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-1")
    section = next(s for s in page.sections if s.id == "4-representante-personas-juridicas")
    grid = section.blocks[0]
    assert [c.key for c in grid.columns] == ["represent-1", "represent-2", "represent-3"]
    assert [r.key for r in grid.rows] == ["nombre-y-apellidos", "nif", "fecha-poder-ddmmaaaa", "notaria"]
    for row in grid.rows:
        assert [cell.binding_id for cell in row.cells] == [
            f"modelo-390.page_1.representante-personas-juridicas-represent-{n}-{row.key}" for n in (1, 2, 3)
        ]


def _evaluate(number, values, missing=(), *, year="2026"):
    revision = _model().revisions[year]
    boxes = {c.number: c for c in revision.casillas}
    by_id = {c.id: c for c in revision.casillas}
    for placement in revision.form_layouts[0].placements:
        if placement.box_number:
            boxes[placement.box_number] = by_id[placement.casilla_id]
    formula = next(f for f in revision.formulas if f.id == boxes[str(number)].formula)
    return evaluate_expression(
        formula.expression,
        values={boxes[str(n)].id: Decimal(str(v)) for n, v in values.items()},
        binding_values={},
        parameters={},
        date_context={},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids={boxes[str(n)].id for n in missing},
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
    )


def test_current_settlement_preserves_both_printed_fuel_payment_positions():
    revision = _model().revisions["2026"]
    assert form_layout_failures(revision) == ()
    layout = revision.form_layouts[0]
    page = next(p for p in layout.pages if p.id == "pag-6")
    numbers = {c.id: c.number for c in revision.casillas}
    assert "12141" in page.official_ref
    assert [[numbers[b.casilla_id] for b in section.blocks] for section in page.sections[:4]] == [
        ["658", "84", "659", "85", "112", "86"],
        ["87", "88", "89", "90", "91", "658", "84", "92", "659", "93", "112", "94"],
        ["95", "96", "524", "97", "98", "662"],
        ["525", "526"],
    ]
    assert layout.review.state == "generated"


@pytest.mark.parametrize("year", ("2024", "2025"))
def test_historical_settlement_keeps_printed_branches_without_future_fuel_payment(year):
    revision = _model().revisions[year]
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-6")
    assert "136901" in page.official_ref
    numbers = {c.id: c.number for c in revision.casillas}
    assert [[numbers[b.casilla_id] for b in s.blocks] for s in page.sections] == [
        ["658", "84", "659", "85", "86"],
        ["87", "88", "89", "90", "91", "658", "84", "92", "659", "93", "94"],
        ["95", "96", "524", "97", "98", "662"],
        ["525", "526"],
        [
            "99",
            "653",
            "103",
            "104",
            "105",
            "110",
            "125",
            "126",
            "127",
            "128",
            "100",
            "101",
            "102",
            "227",
            "228",
            "106",
            "107",
            "108",
        ],
    ]


def test_territorial_percentage_and_fuel_deduction_are_live():
    assert _evaluate(92, {84: 10000, 87: 25}) == Decimal("2500")
    assert _evaluate(92, {84: 10000, 87: 0}) == Decimal("0")
    assert _evaluate(94, {92: 2500, 659: 400, 93: 300, 112: 200}) == Decimal("2400")
    assert _evaluate(94, {92: 2500, 659: 400, 93: 300, 112: 250}) == Decimal("2350")
    for n in (92, 659, 93, 112):
        with pytest.raises(UnresolvedFormulaDependencyError):
            _evaluate(94, {k: 0 for k in (92, 659, 93, 112) if k != n}, (n,))


@pytest.mark.parametrize("year", ("2024", "2025", "2026"))
def test_specific_operations_preserve_the_printed_order_under_one_heading(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-7")
    assert ("12142" if year == "2026" else "136902") in page.official_ref
    sections = [s for s in page.sections if s.id.startswith("11-oper-especificas")]
    assert len(sections) == 1
    section = sections[0]
    assert section.official_heading == "11. Operaciones específicas"
    boxes = {c.id: c.number for c in revision.casillas}
    assert [boxes[b.casilla_id] for b in section.blocks[:-1]] == ["230", "109", "231", "232", "111", "113", "523"]
    grid = section.blocks[-1]
    assert [[boxes[c.casilla_id] for c in row.cells] for row in grid.rows] == [["654", "655"], ["656", "657"]]
    assert len({b.id for b in section.blocks}) == len(section.blocks)


@pytest.mark.parametrize("year", ("2024", "2025"))
def test_prorrata_preserves_five_separate_activity_blocks_and_all_thirty_bindings(year):
    revision = _model().revisions[year]
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-7")
    section = next(s for s in page.sections if s.id == "12-prorratas")
    assert len(section.blocks) == 10
    suffixes = (
        "codigo-cnae",
        "importe-de-operaciones",
        "importe-de-operaciones-con-derecho-a-deduccion",
        "tipo-de-prorrata",
        "porcentaje-de-prorrata",
    )
    for n in range(1, 6):
        description, grid = section.blocks[2 * (n - 1) : 2 * n]
        assert description.binding_id == f"modelo-390.page_7.prorratas-{n}-actividad-desarrollada"
        assert len(grid.columns) == 5 and len(grid.rows) == 1
        assert [c.binding_id for c in grid.rows[0].cells] == [
            f"modelo-390.page_7.prorratas-{n}-{suffix}" for suffix in suffixes
        ]


@pytest.mark.parametrize("year", ("2022", "2023", "2024", "2025", "2026"))
def test_annual_turnover_obeys_every_printed_sign_and_missing_input(year):
    additions = (99, 653, 103, 104, 105, 110, 100, 101, 102, 125, 126, 127, 128, 227, 228)
    deductions = (106, 107)
    values = dict.fromkeys((*additions, *deductions), 100)
    assert _evaluate(108, values, year=year) == Decimal("1300")
    for n in additions:
        assert _evaluate(108, {**values, n: 107}, year=year) == Decimal("1307")
    for n in deductions:
        assert _evaluate(108, {**values, n: 107}, year=year) == Decimal("1293")
    assert _evaluate(108, dict.fromkeys(values, 0), year=year) == Decimal("0")
    for n in values:
        with pytest.raises(UnresolvedFormulaDependencyError):
            _evaluate(108, {k: v for k, v in values.items() if k != n}, (n,), year=year)


@pytest.mark.parametrize("year", ("2022", "2023", "2024", "2025"))
def test_historical_territorial_settlement_uses_percentage_without_future_deduction(year):
    assert _evaluate(92, {84: 10000, 87: 25}, year=year) == Decimal("2500")
    assert _evaluate(92, {84: 10000, 87: 0}, year=year) == Decimal("0")
    assert _evaluate(94, {92: 2500, 659: 400, 93: 300}, year=year) == Decimal("2600")
    for n in (92, 659, 93):
        with pytest.raises(UnresolvedFormulaDependencyError):
            _evaluate(94, {k: 0 for k in (92, 659, 93) if k != n}, (n,), year=year)


def test_new_formula_evidence_does_not_rewrite_the_2021_edition():
    revision = _model().revisions["2021"]
    unchanged = ("92", "94", "108", "155", "172", "189")
    assert all(c.formula is None for c in revision.casillas if c.number in unchanged)
    for year in ("2022", "2023"):
        historical = _model().revisions[year]
        formulas = {f.id: f for f in historical.formulas}
        for casilla in historical.casillas:
            if casilla.number in unchanged:
                assert casilla.formula is not None
                assert formulas[casilla.formula].source_refs == ("boe-modelo-390-2022-printed-calculations",)


@pytest.mark.parametrize(
    "total,printed_boxes",
    [
        (
            33,
            "700 667 01 702 669 03 05 704 671 500 706 673 502 504 708 675 643 710 677 645 647 "
            "712 679 07 714 681 09 11 13 716 683 21 718 685 23 25 720 687 545 722 689 547 551 27 29 649 31",
        ),
        (
            34,
            "701 668 02 703 670 04 06 705 672 501 707 674 503 505 709 676 644 711 678 646 648 "
            "713 680 08 715 682 10 12 14 717 684 22 719 686 24 26 721 688 546 723 690 548 552 28 30 650 32",
        ),
    ],
)
@pytest.mark.parametrize("year", ("2024", "2025", "2026"))
def test_page_two_totals_include_all_printed_rows(total, printed_boxes, year):
    # Independently inspected BOE printed pages 136896 (2024 form) and 12136 (2026).
    numbers = printed_boxes.split()
    values = dict.fromkeys(numbers, 100)
    assert _evaluate(total, values, year=year) == Decimal("4700")
    for number in numbers:
        assert _evaluate(total, {**values, number: 107}, year=year) == Decimal("4707")
        with pytest.raises(UnresolvedFormulaDependencyError):
            _evaluate(total, {k: v for k, v in values.items() if k != number}, (number,), year=year)
    assert _evaluate(total, dict.fromkeys(numbers, 0), year=year) == Decimal("0")
    # Adjustments are signed; a negative correction must reduce the total.
    assert _evaluate(total, {**values, numbers[-1]: -100}, year=year) == Decimal("4500")
    revision = _model().revisions[year]
    boxes = {c.id: c.number for c in revision.casillas}
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-2")
    column = 0 if total == 33 else 1
    placed = [
        boxes[row.cells[column].casilla_id]
        for section in page.sections
        for block in section.blocks
        for row in block.rows
    ]
    assert placed == [*numbers, str(total)]


def test_page_two_totals_keep_older_editions_scoped_to_their_own_form():
    for key, revision in _model().revisions.items():
        if key in ("2024", "2025", "2026"):
            continue
        boxes = {c.number: c for c in revision.casillas}
        if key == "2021":
            assert "33" not in boxes and "34" not in boxes
            continue
        assert boxes["33"].formula == "modelo-390-iva-anual-total-bases-iva"
        formula = next(f for f in revision.formulas if f.id == boxes["34"].formula)
        assert len(formula.expression.args) == 35
        assert formula.source_refs == ("boe-modelo-390-2022-printed-calculations",)


@pytest.mark.parametrize("year", ("2022", "2023"))
@pytest.mark.parametrize("total", (33, 34))
def test_early_vat_subtotal_includes_all_35_printed_amounts(year, total):
    numbers = [
        "701",
        "02",
        "703",
        "04",
        "06",
        "705",
        "501",
        "707",
        "503",
        "505",
        "709",
        "644",
        "711",
        "646",
        "648",
        "713",
        "08",
        "715",
        "10",
        "12",
        "14",
        "717",
        "22",
        "719",
        "24",
        "26",
        "721",
        "546",
        "723",
        "548",
        "552",
        "28",
        "30",
        "650",
        "32",
    ]
    if total == 33:
        printed = (
            "700 01 702 03 05 704 500 706 502 504 708 643 710 645 647 "
            "712 07 714 09 11 13 716 21 718 23 25 720 545 722 547 551 27 29 649 31"
        )
        numbers = printed.split()
    values = dict.fromkeys(numbers, 100)
    assert _evaluate(total, values, year=year) == Decimal("3500")
    assert _evaluate(total, dict.fromkeys(numbers, 0), year=year) == 0
    for number in numbers:
        assert _evaluate(total, {**values, number: 107}, year=year) == Decimal("3507")
        assert _evaluate(total, {**values, number: -100}, year=year) == Decimal("3300")
        with pytest.raises(UnresolvedFormulaDependencyError):
            _evaluate(total, {k: v for k, v in values.items() if k != number}, (number,), year=year)


@pytest.mark.parametrize(
    "total,quotas",
    [
        (155, (140, 142, 144, 146, 148, 150, 152, 153, 154)),
        (172, (157, 159, 161, 163, 165, 167, 169, 170, 171)),
        (189, (174, 176, 178, 180, 182, 184, 186, 187, 188)),
    ],
)
@pytest.mark.parametrize("year", ("2022", "2023", "2024", "2025", "2026"))
def test_differentiated_totals_sum_only_the_nine_printed_quotas(total, quotas, year):
    values = dict.fromkeys(quotas, 100)
    assert _evaluate(total, values, year=year) == Decimal("900")
    assert _evaluate(total, dict.fromkeys(quotas, 0), year=year) == Decimal("0")
    assert _evaluate(total, {**values, quotas[-1]: -100}, year=year) == Decimal("700")
    for n in quotas:
        assert _evaluate(total, {**values, n: 107}, year=year) == Decimal("907")
        with pytest.raises(UnresolvedFormulaDependencyError):
            _evaluate(total, {k: v for k, v in values.items() if k != n}, (n,), year=year)
    revision = _model().revisions[year]
    target = next(c for c in revision.casillas if c.number == str(total))
    formula = next(f for f in revision.formulas if f.id == target.formula)
    expected_source = (
        "boe-modelo-390-2026-printed-calculations" if year == "2026" else "aeat-modelo-390-2024-printed-calculations"
    )
    if year in ("2022", "2023"):
        expected_source = "boe-modelo-390-2022-printed-calculations"
    assert tuple(formula.source_refs) == (expected_source,)
    construct = next(c for c in revision.constructs if c.id == "modelo-390-iva-resumen-anual")
    assert expected_source in construct.source_refs
    if year == "2026":
        assert "aeat-modelo-390-2024-printed-calculations" not in construct.source_refs


@pytest.mark.parametrize("year", ("2022", "2023", "2024", "2025", "2026"))
def test_differentiated_adjustments_and_totals_stay_in_the_quota_column(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    numbers = {c.id: c.number for c in revision.casillas}
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-8")
    assert len(page.sections) == 3
    for section, expected in zip(page.sections, [(154, 155), (171, 172), (188, 189)], strict=True):
        grid = section.blocks[0]
        assert len(grid.rows) == 10
        assert all(row.cells[0].kind == "blank" for row in grid.rows[-2:])
        assert [numbers[row.cells[1].casilla_id] for row in grid.rows[-2:]] == list(map(str, expected))
    printed_pairs = (
        [(139, 140), (141, 142), (143, 144), (145, 146), (147, 148), (149, 150), (151, 152), (640, 153)],
        [(156, 157), (158, 159), (160, 161), (162, 163), (164, 165), (166, 167), (168, 169), (641, 170)],
        [(173, 174), (175, 176), (177, 178), (179, 180), (181, 182), (183, 184), (185, 186), (642, 187)],
    )
    for section, pairs in zip(page.sections, printed_pairs, strict=True):
        assert [[numbers[c.casilla_id] for c in row.cells] for row in section.blocks[0].rows[:8]] == [
            list(map(str, pair)) for pair in pairs
        ]


def test_surcharge_rows_preserve_all_printed_pairs():
    revision = _model().revisions["2026"]
    numbers = {c.id: c.number for c in revision.casillas}
    surcharge = next(p for p in revision.form_layouts[0].pages if p.id == "pag-2-bis")
    rows = surcharge.sections[0].blocks[0].rows
    assert [[numbers[c.casilla_id] for c in rows[i].cells] for i in (2, 5, 6)] == [
        ["35", "36"],
        ["599", "600"],
        ["601", "602"],
    ]
    assert not any(p.id == "numbered-boxes" for p in revision.form_layouts[0].pages)


@pytest.mark.parametrize(
    "year,total,components",
    [
        ("2022", 47, (34, 36, 600, 602, 42, 44, 46)),
        ("2023", 47, (34, 664, 36, 666, 600, 602, 42, 44, 46)),
        ("2024", 47, (34, 664, 692, 36, 666, 694, 600, 602, 42, 44, 46)),
        ("2025", 47, (34, 664, 692, 36, 666, 694, 600, 602, 42, 44, 46)),
        ("2026", 47, (34, 664, 692, 36, 666, 694, 600, 602, 42, 44, 46)),
        ("2022", 64, (49, 513, 51, 521, 53, 55, 57, 59, 598, 61, 661, 62, 652, 63, 522)),
        ("2023", 64, (49, 513, 51, 521, 53, 55, 57, 59, 598, 61, 661, 62, 652, 63, 522)),
        ("2024", 64, (49, 513, 51, 521, 53, 55, 57, 59, 598, 61, 661, 62, 652, 63, 522)),
        ("2025", 64, (49, 513, 51, 521, 53, 55, 57, 59, 598, 61, 661, 62, 652, 63, 522)),
        ("2026", 64, (49, 513, 51, 521, 53, 55, 57, 59, 598, 61, 661, 62, 652, 63, 522)),
    ],
)
def test_main_vat_totals_include_every_printed_component(year, total, components):
    # BOE-A-2024-21961 p136897 and BOE-A-2026-1761 pp12137/12139.
    values = dict.fromkeys(components, 100)
    expected = Decimal(len(components) * 100)
    assert _evaluate(total, values, year=year) == expected
    assert _evaluate(total, dict.fromkeys(components, 0), year=year) == Decimal("0")
    for n in components:
        assert _evaluate(total, {**values, n: 107}, year=year) == expected + 7
        assert _evaluate(total, {**values, n: -100}, year=year) == expected - 200
        with pytest.raises(UnresolvedFormulaDependencyError):
            _evaluate(total, {k: v for k, v in values.items() if k != n}, (n,), year=year)
    assert _evaluate(65, {47: 1100, 64: 1500}, year=year) == Decimal("-400")


@pytest.mark.parametrize("year", ("2024", "2025"))
def test_historical_surcharge_rows_use_printed_rate_owners_and_scoped_evidence(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    layout = revision.form_layouts[0]
    page = next(p for p in layout.pages if p.id == "pag-2-bis")
    assert "136897" in page.official_ref
    numbers = {p.casilla_id: p.box_number for p in layout.placements}
    rows = page.sections[0].blocks[0].rows
    assert [[numbers[c.casilla_id] for c in row.cells] for row in rows] == [
        ["663", "664"],
        ["691", "692"],
        ["35", "36"],
        ["665", "666"],
        ["693", "694"],
        ["599", "600"],
        ["601", "602"],
        ["41", "42"],
    ]
    for row, rate in zip(rows, ("0", "0-26", "0-5", "0-62", "1", "1-4", "5-2", "1-75"), strict=True):
        assert [c.casilla_id for c in row.cells] == [
            f"iva.anual.repercutido.recargo.tipo-{rate}.base",
            f"iva.anual.repercutido.recargo.tipo-{rate}.cuota",
        ]
    formula = next(f for f in revision.formulas if f.target_casilla_id == "iva.anual.cuota-devengada-total")
    assert formula.source_refs == ("aeat-modelo-390-2024-printed-calculations",)
    for suffix in ("general", "reducido", "super-reducido"):
        owner = f"iva.anual.repercutido.recargo.{suffix}"
        assert next(p for p in layout.placements if p.casilla_id == owner).kind == "working_figure"
        assert owner not in {a.casilla_id for a in formula.expression.args}


@pytest.mark.parametrize("year", ("2024", "2025", "2026"))
def test_deduction_rate_groups_keep_their_own_subtotals_in_the_same_grid(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-3")
    numbers = {p.casilla_id: p.box_number for p in revision.form_layouts[0].placements}
    expected = (
        "695 696 190 191 724 725 697 698 603 604 605 606 48 49",
        "745 746 506 507 726 727 747 748 607 608 609 610 512 513",
        "749 750 196 197 728 729 751 752 611 612 613 614 50 51",
        "753 754 514 515 730 731 755 756 615 616 617 618 520 521",
        "757 758 202 203 732 733 759 760 619 620 621 622 52 53",
        "761 762 208 209 734 735 763 764 623 624 625 626 54 55",
        "765 766 214 215 736 737 767 768 627 628 629 630 56 57",
    )
    assert len(page.sections) == 7
    for section, printed in zip(page.sections, expected, strict=True):
        assert len(section.blocks) == 1
        grid = section.blocks[0]
        assert len(grid.rows) == 7
        assert [numbers[c.casilla_id] for row in grid.rows for c in row.cells] == printed.split()
        assert [row.key for row in grid.rows[:6]] == [
            "tipo-2-pct",
            "tipo-4-pct",
            "tipo-5-pct",
            "tipo-7-5-pct",
            "tipo-10-pct",
            "tipo-21-pct",
        ]


@pytest.mark.parametrize("year", ("2024", "2025", "2026"))
def test_deduction_continuation_keeps_subtotals_and_adjustments_in_printed_order(year):
    revision = _model().revisions[year]
    assert form_layout_failures(revision) == ()
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-4")
    numbers = {p.casilla_id: p.box_number for p in revision.form_layouts[0].placements}
    assert len(page.sections) == 4
    expected = (
        "769 770 220 221 738 739 771 772 631 632 633 634 58 59",
        "773 774 587 588 740 741 775 776 635 636 637 638 597 598",
        "60 61 660 661 639 62 651 652",
    )
    for section, printed in zip(page.sections[:3], expected, strict=True):
        assert len(section.blocks) == 1
        assert [numbers[c.casilla_id] for row in section.blocks[0].rows for c in row.cells] == printed.split()
    assert [numbers[b.casilla_id] for b in page.sections[3].blocks] == ["63", "522", "64", "65"]


def test_deduction_subtotals_are_next_to_their_printed_bases():
    revision = _model().revisions["2026"]
    labels = {c.id: c.number for c in revision.casillas}
    labels.update({p.casilla_id: p.box_number for p in revision.form_layouts[0].placements if p.box_number})
    page = next(p for p in revision.form_layouts[0].pages if p.id == "pag-3")
    pairs = [
        [labels.get(cell.casilla_id) for cell in row.cells]
        for section in page.sections
        for block in section.blocks
        for row in block.rows
    ]
    assert ["48", "49"] in pairs
    assert ["52", "53"] in pairs
