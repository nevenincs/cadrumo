"""Modelo 200 editions declare the boxes their own record design prints.

Each Modelo 200 edition cites exactly one AEAT record design. A numbered box
that design does not print cannot belong to the edition, and a box the earlier
design already prints cannot first appear in the later edition: it belongs to
the edition whose design prints it first, and the later edition reaches it by
storage reuse. A cohort cell the later design no longer prints is retired by an
evolution record rather than silently dropped.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import cache
from itertools import pairwise

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaEvolutionKind

from ..compiler.authority import compiled_bundled_authority
from ..compiler.record_design import extract_record_design
from .authored_edition_support import authored_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "200"
_PRINTED_BOX = re.compile(r"\[([0-9]{3,6})\]")
_NUMBERED = re.compile(r"[0-9]{3,6}")

type Box = tuple[str | None, str]
"""A declared box: its record sheet when the edition names one, and its printed number."""


@cache
def _design_boxes(revision_id: str) -> frozenset[tuple[str, str]]:
    """Return every (sheet, number) the record design an edition cites prints."""
    revision = compiled_bundled_authority().modelo(_MODELO).revisions[revision_id]
    sources = compiled_bundled_authority().catalogues.sources
    designs = [ref for ref in revision.source_refs if sources[ref].kind == "record_design"]
    assert len(designs) == 1, f"edition {revision.id} cites record designs {designs}"
    extraction = extract_record_design(bundled_path() / sources[designs[0]].corpus_path)
    return frozenset(
        (sheet.name.strip(), str(number))
        for sheet in extraction.require_complete()
        for field in sheet.fields
        for number in _PRINTED_BOX.findall(field.description)
    )


def _declared_boxes(revision: ModeloRevision) -> frozenset[Box]:
    return frozenset(
        (casilla.segmento, str(casilla.number))
        for casilla in revision.casillas
        if _NUMBERED.fullmatch(str(casilla.number))
    )


def unprinted_boxes(declared: Iterable[Box], printed: frozenset[tuple[str, str]]) -> list[Box]:
    """Return declared boxes the design does not print; an unsheeted box matches its number on any sheet."""
    numbers = {number for _sheet, number in printed}
    return sorted(
        (sheet, number)
        for sheet, number in declared
        if ((sheet, number) not in printed if sheet is not None else number not in numbers)
    )


def late_boxes(
    later: Iterable[Box],
    earlier: Iterable[Box],
    earlier_printed: frozenset[tuple[str, str]],
) -> list[Box]:
    """Return later-edition boxes the earlier design prints on that sheet but the earlier edition omits.

    An earlier row without a sheet stands for its number on any sheet, as the edition declares it.
    """
    earlier = set(earlier)
    unsheeted = {number for sheet, number in earlier if sheet is None}
    all_numbers = {number for _sheet, number in earlier}
    late = []
    for sheet, number in later:
        if sheet is None:
            printed = any(printed_number == number for _s, printed_number in earlier_printed)
            declared = number in all_numbers
        else:
            printed = (sheet, number) in earlier_printed
            declared = (sheet, number) in earlier or number in unsheeted
        if printed and not declared:
            late.append((sheet, number))
    return sorted(late, key=lambda box: (box[0] or "", box[1]))


def _consecutive_editions() -> list[tuple[ModeloRevision, ModeloRevision]]:
    revisions = authored_revisions(_MODELO)
    assert len(revisions) >= 2, "modelo 200 needs two authored editions for this comparison"
    return list(pairwise(revisions))


def test_every_numbered_box_an_edition_declares_is_printed_by_its_own_design() -> None:
    for revision in authored_revisions(_MODELO):
        assert unprinted_boxes(_declared_boxes(revision), _design_boxes(str(revision.id))) == [], revision.id


def test_no_box_the_earlier_design_prints_first_appears_in_the_later_edition() -> None:
    for earlier, later in _consecutive_editions():
        assert late_boxes(_declared_boxes(later), _declared_boxes(earlier), _design_boxes(str(earlier.id))) == [], (
            f"{later.id} declares boxes {earlier.id}'s design already prints"
        )


def test_the_checks_detect_a_box_declared_by_the_wrong_edition() -> None:
    earlier, later = _consecutive_editions()[-1]
    earlier_printed = _design_boxes(str(earlier.id))
    later_printed = _design_boxes(str(later.id))
    only_later = sorted(later_printed - earlier_printed)
    printed_both = sorted(earlier_printed & later_printed)
    assert only_later and printed_both
    sheet, number = only_later[0]
    assert unprinted_boxes({(sheet, number)}, earlier_printed) == [(sheet, number)]
    sheet, number = printed_both[0]
    assert late_boxes({(sheet, number)}, set(), earlier_printed) == [(sheet, number)]


def test_cells_the_later_design_stops_printing_are_retired_not_dropped() -> None:
    for earlier, later in _consecutive_editions():
        later_ids = {str(casilla.id) for casilla in later.casillas}
        retired = {
            evolution.continuidad_id
            for evolution in later.casilla_continuidad_evolutions
            if evolution.evolution_kind is CasillaEvolutionKind.RETIRED
            and str(evolution.from_revision) == str(earlier.id)
        }
        dropped = [
            str(casilla.id)
            for casilla in earlier.casillas
            if str(casilla.id) not in later_ids
            and casilla.continuidad_id not in {c.continuidad_id for c in later.casillas}
            and _NUMBERED.fullmatch(str(casilla.number))
        ]
        assert dropped, f"{later.id} drops no {earlier.id} box, so this check proves nothing"
        assert [box for box in dropped if _chain(earlier, box) not in retired] == []


def _chain(revision: ModeloRevision, casilla_id: str) -> str | None:
    return next(casilla.continuidad_id for casilla in revision.casillas if str(casilla.id) == casilla_id)


_WIDENED_GROUP_KEYS = ("00081", "DP200001:00082")
"""The two 'otros caracteres' keys the later design widens to the grupo nacional de gran magnitud."""

_WIDENING_PROVISION = "ley-7-2024:art-6"
"""The Impuesto Complementario article whose wording the later design's keys adopt."""


def _printed_description(revision_id: str, sheet: str, number: str) -> str:
    """Return the one description the edition's own design prints for ``[number]`` on ``sheet``."""
    revision = compiled_bundled_authority().modelo(_MODELO).revisions[revision_id]
    sources = compiled_bundled_authority().catalogues.sources
    (design,) = [ref for ref in revision.source_refs if sources[ref].kind == "record_design"]
    extraction = extract_record_design(bundled_path() / sources[design].corpus_path)
    (description,) = [
        field.description
        for design_sheet in extraction.require_complete()
        if design_sheet.name.strip() == sheet
        for field in design_sheet.fields
        if f"[{number}]" in field.description
    ]
    return description


@pytest.mark.parametrize("box", _WIDENED_GROUP_KEYS)
def test_a_widened_group_key_keeps_one_chain_with_a_label_evolution_grounded_in_the_law(box: str) -> None:
    earlier, later = _consecutive_editions()[-1]
    before = next(casilla for casilla in earlier.casillas if str(casilla.id) == box)
    after = next(casilla for casilla in later.casillas if str(casilla.id) == box)
    sheet = before.segmento or "DP200001"
    assert "gran magnitud" not in _printed_description(str(earlier.id), sheet, str(before.number))
    assert "gran magnitud" in _printed_description(str(later.id), sheet, str(after.number))
    chain = before.continuidad_id
    assert chain is not None
    assert after.continuidad_id == chain
    assert not _NUMBERED.fullmatch(chain), "a seeded number is not a grounded identity"
    assert "gran magnitud" not in before.label
    assert "gran magnitud" in after.label
    assert before.section != after.section
    evolutions = [evolution for evolution in later.casilla_continuidad_evolutions if evolution.continuidad_id == chain]
    assert [evolution.evolution_kind for evolution in evolutions] == [CasillaEvolutionKind.LABEL_EVOLVED]
    assert _WIDENING_PROVISION in evolutions[0].legal_refs
    assert _WIDENING_PROVISION in compiled_bundled_authority().catalogues.legal
