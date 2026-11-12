"""The casilla 0564 operands are extracted from the official dictionaries and match the registry.

Editions come from the registry tree in valid-from order; boxes the assertions name
are the ones the dictionaries print, and each expected list is rebuilt here from the
dictionary rows rather than copied from the extraction.
"""

from __future__ import annotations

import dataclasses

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues

from ..authoring.autonomic_deduction_sum import EditionOperands, check, extract_editions
from ..authoring.autonomic_deduction_sum_dictionary import (
    AutonomicSumExtractionError,
    ComunidadOperands,
    DictionaryRow,
    SignedBox,
    extract_comunidad_operands,
    parse_dictionary_rows,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

type Tree = tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]

_MADRID = "madrid"
_MONEY = "P102"
_MADRID_RANGES = (("1039", "1050"), ("1115", "1120"))
_MADRID_SINGLES: tuple[CasillaId, ...] = (
    validated_casilla_id("2020", surface="Madrid single operand"),
    validated_casilla_id("2021", surface="Madrid single operand"),
    validated_casilla_id("2026", surface="Madrid single operand"),
    validated_casilla_id("2027", surface="Madrid single operand"),
    validated_casilla_id("2030", surface="Madrid single operand"),
)
_MADRID_UNNAMED_BOX: CasillaId = validated_casilla_id("2017", surface="Madrid box the sum does not name")


@pytest.fixture(scope="module")
def editions(registry_tree: Tree) -> tuple[EditionOperands, ...]:
    return extract_editions(*registry_tree)


def _dictionary(registry_tree: Tree, edition: EditionOperands) -> bytes:
    source = registry_tree[1].sources[edition.source_ref]
    assert source.corpus_path is not None
    return bundled_path(*source.corpus_path.split("/")).read_bytes()


def _madrid(edition: EditionOperands) -> ComunidadOperands:
    return next(comunidad for comunidad in edition.comunidades if comunidad.residence == _MADRID)


def _madrid_money(rows: tuple[DictionaryRow, ...], first: str, last: str) -> set[str]:
    return {
        row.box
        for row in rows
        if row.block == "MadridRes"
        and row.data_type == _MONEY
        and row.box.isdigit()
        and int(first) <= int(row.box) <= int(last)
    }


def _printed(rows: tuple[DictionaryRow, ...]) -> set[str]:
    return {row.box for row in rows}


def test_the_registry_matches_a_fresh_extraction(registry_tree: Tree, editions: tuple[EditionOperands, ...]) -> None:
    assert check(registry_tree[0], editions) == []


def test_madrid_sums_its_early_range_in_the_oldest_edition(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    oldest = editions[0]
    madrid = _madrid(oldest)
    rows = parse_dictionary_rows(_dictionary(registry_tree, oldest))

    assert "[1039] a [1050]" in madrid.row.label
    assert "[1115]" not in madrid.row.label
    assert {operand.box for operand in madrid.operands} == _madrid_money(rows, *_MADRID_RANGES[0])
    assert all(operand.sign == 1 for operand in madrid.operands)


def test_madrid_adds_its_late_ranges_and_boxes_in_the_newest_edition(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    newest = editions[-1]
    madrid = _madrid(newest)
    rows = parse_dictionary_rows(_dictionary(registry_tree, newest))
    expected = set().union(*(_madrid_money(rows, first, last) for first, last in _MADRID_RANGES))
    expected |= set(_MADRID_SINGLES)

    assert {operand.box for operand in madrid.operands} == expected
    assert all(operand.sign == 1 for operand in madrid.operands)


def test_a_madrid_box_the_sum_does_not_name_is_not_summed(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    naming_the_late_boxes = [
        edition for edition in editions if f"[{_MADRID_SINGLES[-1]}]" in _madrid(edition).row.label
    ]
    assert naming_the_late_boxes
    for edition in naming_the_late_boxes:
        rows = parse_dictionary_rows(_dictionary(registry_tree, edition))
        assert _MADRID_UNNAMED_BOX in _madrid_money(rows, _MADRID_UNNAMED_BOX, _MADRID_UNNAMED_BOX)
        assert SignedBox(1, _MADRID_UNNAMED_BOX) not in _madrid(edition).operands


def test_the_balearic_advance_payment_is_subtracted_whatever_the_printed_sign(
    editions: tuple[EditionOperands, ...],
) -> None:
    rows = [
        comunidad.row for edition in editions for comunidad in edition.comunidades if comunidad.row.field == "DEDAUTIB"
    ]
    printing_the_glyph = [row for row in rows if "[1718] ? [1719]" in row.label]
    printing_the_dash = [row for row in rows if "[1718] - [1719]" in row.label]
    assert printing_the_glyph and printing_the_dash
    for edition in editions:
        baleares = next(comunidad for comunidad in edition.comunidades if comunidad.row.field == "DEDAUTIB")
        if "[1719]" in baleares.row.label:
            assert SignedBox(-1, "1719") in baleares.operands, edition.revision_id


@pytest.mark.parametrize(
    "replacement",
    [b"[1039] por [1050] )", b"[1039] ? [1050] )", b"[1039] a [1050] + )", b"[1050] a [1039] )"],
    ids=["unknown-word", "unreviewed-glyph", "dangling-sign", "backward-range"],
)
def test_a_malformed_comunidad_row_fails_the_extraction(
    registry_tree: Tree, editions: tuple[EditionOperands, ...], replacement: bytes
) -> None:
    body = _dictionary(registry_tree, editions[0])
    original = b"[1039] a [1050] )"
    assert body.count(original) == 1

    with pytest.raises(AutonomicSumExtractionError):
        extract_comunidad_operands(body.replace(original, replacement))


def test_a_formula_that_disagrees_with_its_dictionary_fails_the_check(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    newest = editions[-1]
    madrid = _madrid(newest)
    shortened = dataclasses.replace(madrid, operands=madrid.operands[:-1])
    disagreeing = dataclasses.replace(
        newest,
        comunidades=tuple(shortened if comunidad is madrid else comunidad for comunidad in newest.comunidades),
    )

    problems = check(registry_tree[0], (*editions[:-1], disagreeing))

    assert f"edition {newest.revision_id} {_MADRID}: operands differ from the dictionary" in problems


def test_every_edition_prints_a_box_for_each_operand(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    for edition in editions:
        printed = _printed(parse_dictionary_rows(_dictionary(registry_tree, edition)))
        for comunidad in edition.comunidades:
            assert {operand.box for operand in comunidad.operands} <= printed, (
                edition.revision_id,
                comunidad.residence,
            )
            assert not {operand.box for operand in comunidad.operands} & {item.box for item in comunidad.dropped}
