"""The casilla 0564 operands are extracted from the official dictionaries and match the registry.

Editions come from the registry tree in valid-from order; boxes the assertions name
are the ones the dictionaries print, and each expected list is rebuilt here from the
dictionary rows rather than copied from the extraction.
"""

from __future__ import annotations

import dataclasses
import itertools
import re

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.schema_base import CasillaDataType
from cadrumo.domain.calculations.registry.schema_catalogues import RegistryCatalogues

from ..authoring.autonomic_deduction_sum import (
    RESIDENCE_BINDING,
    EditionOperands,
    check,
    extract_editions,
    meaning,
    registry_operands,
    render_delta,
)
from ..authoring.autonomic_deduction_sum_dictionary import (
    NOT_PRINTED,
    PRINTED_ELSEWHERE,
    SUMMARY_BOX,
    UNREADABLE_SIGN,
    AutonomicSumExtractionError,
    ComunidadOperands,
    DictionaryRow,
    LeftOutBox,
    SignedBox,
    extract_comunidad_operands,
    parse_dictionary_rows,
)
from ..authoring.autonomic_deduction_sum_inventory import LeftOutEntry

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
_BALEARIC_ADVANCE: CasillaId = validated_casilla_id("1719", surface="Balearic advance payment")
_BOX_RE = re.compile(r"\[(\d{4})\]")
_EMITTED_RE = re.compile(rf'binding = "{RESIDENCE_BINDING}" \}}, \{{ text_literal = "(\w+)"')
_NUMERIC = frozenset({CasillaDataType.MONEY, CasillaDataType.DECIMAL, CasillaDataType.INTEGER})


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


def _baleares(edition: EditionOperands) -> ComunidadOperands:
    return next(comunidad for comunidad in edition.comunidades if comunidad.row.field == "DEDAUTIB")


def _printing(editions: tuple[EditionOperands, ...], glyph: str) -> list[EditionOperands]:
    printed = f"{glyph} [{_BALEARIC_ADVANCE}]"
    return [edition for edition in editions if printed in _baleares(edition).row.label]


def test_the_balearic_advance_payment_is_subtracted_where_the_sum_prints_a_minus(
    editions: tuple[EditionOperands, ...],
) -> None:
    printing_the_dash = _printing(editions, "-")
    assert printing_the_dash
    for edition in printing_the_dash:
        assert SignedBox(-1, _BALEARIC_ADVANCE) in _baleares(edition).operands, edition.revision_id


def test_the_balearic_advance_payment_is_left_out_where_the_sign_is_unreadable(
    editions: tuple[EditionOperands, ...],
) -> None:
    printing_the_glyph = _printing(editions, "?")
    assert printing_the_glyph
    for edition in printing_the_glyph:
        baleares = _baleares(edition)
        left_out = {item.box: item.reason for item in baleares.left_out}
        assert _BALEARIC_ADVANCE not in {operand.box for operand in baleares.operands}, edition.revision_id
        assert left_out.get(_BALEARIC_ADVANCE) == UNREADABLE_SIGN, edition.revision_id
        assert _BALEARIC_ADVANCE in edition.guards(baleares.residence), edition.revision_id


@pytest.mark.parametrize(
    "replacement",
    [b"[1039] por [1050] )", b"[1039] * [1050] )", b"[1039] a [1050] + )", b"[1050] a [1039] )"],
    ids=["unknown-word", "unknown-glyph", "dangling-sign", "backward-range"],
)
def test_a_malformed_comunidad_row_fails_the_extraction(
    registry_tree: Tree, editions: tuple[EditionOperands, ...], replacement: bytes
) -> None:
    body = _dictionary(registry_tree, editions[0])
    original = b"[1039] a [1050] )"
    assert body.count(original) == 1

    with pytest.raises(AutonomicSumExtractionError):
        extract_comunidad_operands(body.replace(original, replacement))


def _replaced_madrid(edition: EditionOperands, madrid: ComunidadOperands) -> EditionOperands:
    return dataclasses.replace(
        edition,
        comunidades=tuple(madrid if comunidad.residence == _MADRID else comunidad for comunidad in edition.comunidades),
    )


def _differs(edition: EditionOperands) -> str:
    return f"edition {edition.revision_id} {_MADRID}: operands or left-out guards differ from the dictionary"


def test_a_formula_that_disagrees_with_its_dictionary_fails_the_check(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    newest = editions[-1]
    madrid = _madrid(newest)
    disagreeing = _replaced_madrid(newest, dataclasses.replace(madrid, operands=madrid.operands[:-1]))

    assert _differs(newest) in check(registry_tree[0], (*editions[:-1], disagreeing))


def test_a_formula_missing_a_left_out_guard_fails_the_check(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    newest = editions[-1]
    madrid = _madrid(newest)
    moved = LeftOutBox(madrid.operands[-1].box, PRINTED_ELSEWHERE, ())
    entry = LeftOutEntry(_MADRID, madrid.row.field, madrid.row.line, moved, CasillaDataType.MONEY.value, True)
    guarded = dataclasses.replace(
        _replaced_madrid(newest, dataclasses.replace(madrid, operands=madrid.operands[:-1], left_out=(moved,))),
        left_out=(*newest.left_out, entry),
    )

    assert _differs(newest) in check(registry_tree[0], (*editions[:-1], guarded))


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
            assert not {operand.box for operand in comunidad.operands} & {item.box for item in comunidad.left_out}


def test_every_box_the_sum_names_is_summed_or_left_out(editions: tuple[EditionOperands, ...]) -> None:
    for edition in editions:
        for comunidad in edition.comunidades:
            named = set(_BOX_RE.findall(comunidad.row.label)) - {SUMMARY_BOX}
            accounted = {operand.box for operand in comunidad.operands} | {item.box for item in comunidad.left_out}
            assert named <= accounted, (edition.revision_id, comunidad.residence, sorted(named - accounted))


def _reason_holds(item: LeftOutBox, where: list[DictionaryRow], block: str) -> bool:
    """Whether the dictionary rows printing the box bear out the reason it was left out."""
    if item.reason == NOT_PRINTED:
        return not where
    if item.reason == PRINTED_ELSEWHERE:
        return bool(where) and all(row.block != block for row in where)
    return True


def test_each_left_out_reason_matches_the_dictionary_rows(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    for edition in editions:
        rows = parse_dictionary_rows(_dictionary(registry_tree, edition))
        for comunidad in edition.comunidades:
            for item in comunidad.left_out:
                where = [row for row in rows if row.box == item.box]
                assert _reason_holds(item, where, comunidad.row.block), (edition.revision_id, item.box)


def test_a_left_out_box_is_guarded_exactly_when_the_edition_declares_it_as_an_amount(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    revisions = next(modelo for modelo in registry_tree[0] if modelo.id == "100").revisions
    for edition in editions:
        declared = {str(casilla.id): casilla.data_type for casilla in revisions[edition.revision_id].casillas}
        for entry in edition.left_out:
            assert entry.guarded == (declared.get(entry.left_out.box) in _NUMERIC), (
                edition.revision_id,
                entry.left_out.box,
            )


def test_each_edition_overrides_only_the_comunidades_whose_sum_changes(
    registry_tree: Tree, editions: tuple[EditionOperands, ...]
) -> None:
    """The delta re-emits no inherited term: each emitted term computes something new, and nothing else is emitted."""
    revisions = next(modelo for modelo in registry_tree[0] if modelo.id == "100").revisions
    deltas = 0
    for previous, edition in itertools.pairwise(editions):
        inherited = registry_operands(revisions[previous.revision_id])
        own = registry_operands(revisions[edition.revision_id])
        changed = {residence for residence, term in own.items() if meaning(term) != meaning(inherited[residence])}
        emitted = _EMITTED_RE.findall(render_delta(previous, edition, frozenset()))

        assert len(emitted) == len(set(emitted)), edition.revision_id
        assert set(emitted) == changed, (edition.revision_id, sorted(set(emitted) ^ changed))
        deltas += len(emitted)
    assert deltas
