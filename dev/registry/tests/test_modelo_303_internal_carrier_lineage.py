"""Modelo 303's internal carriers keep a grounded claim on the edge after the edition that states them.

The intracomunitaria acquisitions base carrier and the promotor's autoconsumo
base are stated once, at the edition covering the support floor, where each
declares that no official form prints it. A row's claim speaks only about the
edge into the edition that states it, so the next edition's row needs its own:
each 2023 row continues its 2022 counterpart, grounded in the two record designs
whose rows the carrier feeds. The cited design lines must print those boxes.
"""

from __future__ import annotations

import re
from functools import cache

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from ..compiler.loader import load_modelo_directory
from ..compiler.validate_cross_revision_lineage_origin import lineage_origin_continuity_failures

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO = "303"
_STATING_EDITION = "2022"
_CONTINUING_EDITION = "2023"
# Carrier casilla -> the printed boxes its grounding must find on each cited design line.
_CARRIER_BOXES = {
    "iva.autorepercutido.intracomunitaria.devengado.base": ("[10]",),
    "iva.autoconsumo.promotor.base": ("[01]", "[09]"),
}
_CITATION = re.compile(r"(corpus/\S+?\.extracted\.md):(\d+)")


@cache
def _modelo() -> ModeloDefinition:
    return load_modelo_directory(bundled_path("registry", "aeat", "modelos", _MODELO))


def _row(revision: ModeloRevision, casilla_id: str) -> CasillaDefinition:
    return next(casilla for casilla in revision.casillas if str(casilla.id) == casilla_id)


def _cited_lines(evidence: str) -> tuple[str, ...]:
    """Return the text of every ``path:line`` design citation in ``evidence``."""
    lines = []
    for path, number in _CITATION.findall(evidence):
        text = bundled_path(*path.split("/")).read_text(encoding="utf-8").splitlines()
        index = int(number) - 1
        assert 0 <= index < len(text), f"{path}:{number} is past the end of the captured design"
        lines.append(text[index])
    return tuple(lines)


def _cites_every_box(evidence: str, boxes: tuple[str, ...]) -> bool:
    """Whether every design line ``evidence`` cites prints one of ``boxes``."""
    lines = _cited_lines(evidence)
    return bool(lines) and all(any(box in line for box in boxes) for line in lines)


@pytest.mark.parametrize("casilla_id", sorted(_CARRIER_BOXES))
def test_the_stating_edition_declares_the_carrier_is_on_no_form(casilla_id: str) -> None:
    row = _row(_modelo().revisions[_STATING_EDITION], casilla_id)

    assert row.continuidad_origin is CasillaLineageOrigin.NOT_ON_FORM
    assert row.continuidad_evidence


@pytest.mark.parametrize("casilla_id", sorted(_CARRIER_BOXES))
def test_the_next_edition_grounds_the_carrier_in_both_designs(casilla_id: str) -> None:
    modelo = _modelo()
    stated = _row(modelo.revisions[_STATING_EDITION], casilla_id)
    continuing = _row(modelo.revisions[_CONTINUING_EDITION], casilla_id)

    assert continuing.continuidad_id == stated.continuidad_id
    assert continuing.continuidad_origin is CasillaLineageOrigin.GROUNDED
    evidence = continuing.continuidad_evidence or ""
    cited_designs = {path for path, _ in _CITATION.findall(evidence)}
    assert len(cited_designs) == 2, "the claim must cite the design of each edition it links"
    assert _cites_every_box(evidence, _CARRIER_BOXES[casilla_id])


def test_every_modelo_303_continuation_resolves_its_predecessor() -> None:
    assert lineage_origin_continuity_failures(_modelo()) == ()


@pytest.mark.parametrize("casilla_id", sorted(_CARRIER_BOXES))
def test_the_grounded_claim_speaks_only_for_its_own_edge(casilla_id: str) -> None:
    modelo = _modelo()
    claim = _row(modelo.revisions[_CONTINUING_EDITION], casilla_id).continuidad_evidence
    later = [
        revision
        for revision in modelo.revisions.values()
        if isinstance(revision.predecessor, DeclaredPredecessor)
        and str(revision.predecessor.revision_id) == _CONTINUING_EDITION
    ]

    assert later, "an edition must continue the 2023 edition for this edge to be observable"
    for revision in later:
        assert _row(revision, casilla_id).continuidad_evidence != claim, revision.id


def test_a_citation_of_a_line_that_prints_another_box_is_detected() -> None:
    evidence = _row(
        _modelo().revisions[_CONTINUING_EDITION], "iva.autorepercutido.intracomunitaria.devengado.base"
    ).continuidad_evidence
    assert evidence is not None
    shifted = _CITATION.sub(lambda match: f"{match.group(1)}:{int(match.group(2)) + 1}", evidence)

    assert not _cites_every_box(shifted, _CARRIER_BOXES["iva.autorepercutido.intracomunitaria.devengado.base"])
