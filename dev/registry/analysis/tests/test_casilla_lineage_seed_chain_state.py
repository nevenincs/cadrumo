"""The lineage seeder's chain state indexes declared chains and judges a proposed link."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ...tests.casilla_lineage_planted_support import planted_casilla, planted_modelo, planted_revision
from ..casilla_lineage_seed_chain_state import ChainState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SECOND_YEAR = filing_year_envelope().horizon
_FIRST_YEAR = _SECOND_YEAR - 1
_FIRST = str(_FIRST_YEAR)
_SECOND = str(_SECOND_YEAR)

_EVIDENCE = "disenos_registro/modelo_999/files/2024.txt:3 box [01] printed in both editions"


def _two_editions(*, first: dict[str, object], second: dict[str, object]) -> ModeloDefinition:
    return planted_modelo(
        planted_revision(
            _FIRST, date(_FIRST_YEAR, 1, 1), date(_FIRST_YEAR, 12, 31), (_FIRST_YEAR,), (planted_casilla(**first),)
        ),
        planted_revision(
            _SECOND, date(_SECOND_YEAR, 1, 1), date(_SECOND_YEAR, 12, 31), (_SECOND_YEAR,), (planted_casilla(**second),)
        ),
    )


def test_declared_chains_and_their_grounded_link_are_indexed() -> None:
    modelo = _two_editions(
        first={"continuidad_id": "base-imponible"},
        second={
            "continuidad_id": "base-imponible",
            "continuidad_origin": "grounded",
            "continuidad_evidence": _EVIDENCE,
        },
    )

    state = ChainState.of(modelo)

    assert state.ids_in(_FIRST) == {"base-imponible"}
    assert state.ids_in(_SECOND) == {"base-imponible"}
    assert state.predecessor_of[(_SECOND, "01")] == (_FIRST, "01")
    assert state.grounded_link[(_SECOND, "01")] is True


def test_a_link_without_grounding_evidence_is_not_grounded() -> None:
    modelo = _two_editions(
        first={"continuidad_id": "base-imponible"},
        second={"continuidad_id": "base-imponible", "continuidad_origin": "seeded"},
    )

    assert ChainState.of(modelo).grounded_link[(_SECOND, "01")] is False


def test_linking_assigns_a_chain_only_to_rows_not_yet_linked() -> None:
    state = ChainState.of(_two_editions(first={"continuidad_id": "base-imponible"}, second={}))

    state.link("other", [(_FIRST, "01"), (_SECOND, "01")])

    assert state.ids[(_FIRST, "01")] == "base-imponible"
    assert state.ids[(_SECOND, "01")] == "other"
    assert state.members["other"] == [(_SECOND, "01")]


def test_an_ungrounded_link_between_rows_without_a_role_is_a_violation_and_a_grounded_one_is_not() -> None:
    state = ChainState.of(_two_editions(first={"semantic_role": None}, second={"semantic_role": None}))
    link = ((_FIRST, "01"), (_SECOND, "01"))

    violation = state.linkage_violation("planted-chain", link, grounded=False)

    assert violation is not None and "without semantic_role" in violation
    assert state.linkage_violation("planted-chain", link, grounded=True) is None


def test_a_chain_whose_role_is_unique_in_every_edition_must_carry_the_role_derived_name() -> None:
    state = ChainState.of(_two_editions(first={}, second={}))
    link = ((_FIRST, "01"), (_SECOND, "01"))

    violation = state.linkage_violation("base", link, grounded=False)

    assert violation is not None and "'base-imponible'" in violation
    assert state.linkage_violation("base-imponible", link, grounded=False) is None
