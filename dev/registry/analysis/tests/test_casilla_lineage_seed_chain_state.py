"""The lineage seeder's chain state indexes declared chains and judges a proposed link."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ...tests.casilla_lineage_planted_support import planted_casilla, planted_modelo, planted_revision
from ..casilla_lineage_seed_chain_state import ChainState

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_EVIDENCE = "disenos_registro/modelo_999/files/2024.txt:3 box [01] printed in both editions"


def _two_editions(*, first: dict[str, object], second: dict[str, object]) -> ModeloDefinition:
    return planted_modelo(
        planted_revision("2023", date(2023, 1, 1), date(2023, 12, 31), (2023,), (planted_casilla(**first),)),
        planted_revision("2024", date(2024, 1, 1), date(2024, 12, 31), (2024,), (planted_casilla(**second),)),
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

    assert state.ids_in("2023") == {"base-imponible"}
    assert state.ids_in("2024") == {"base-imponible"}
    assert state.predecessor_of[("2024", "01")] == ("2023", "01")
    assert state.grounded_link[("2024", "01")] is True


def test_a_link_without_grounding_evidence_is_not_grounded() -> None:
    modelo = _two_editions(
        first={"continuidad_id": "base-imponible"},
        second={"continuidad_id": "base-imponible", "continuidad_origin": "seeded"},
    )

    assert ChainState.of(modelo).grounded_link[("2024", "01")] is False


def test_linking_assigns_a_chain_only_to_rows_not_yet_linked() -> None:
    state = ChainState.of(_two_editions(first={"continuidad_id": "base-imponible"}, second={}))

    state.link("other", [("2023", "01"), ("2024", "01")])

    assert state.ids[("2023", "01")] == "base-imponible"
    assert state.ids[("2024", "01")] == "other"
    assert state.members["other"] == [("2024", "01")]


def test_an_ungrounded_link_between_rows_without_a_role_is_a_violation_and_a_grounded_one_is_not() -> None:
    state = ChainState.of(_two_editions(first={"semantic_role": None}, second={"semantic_role": None}))
    link = (("2023", "01"), ("2024", "01"))

    violation = state.linkage_violation("planted-chain", link, grounded=False)

    assert violation is not None and "without semantic_role" in violation
    assert state.linkage_violation("planted-chain", link, grounded=True) is None


def test_a_chain_whose_role_is_unique_in_every_edition_must_carry_the_role_derived_name() -> None:
    state = ChainState.of(_two_editions(first={}, second={}))
    link = (("2023", "01"), ("2024", "01"))

    violation = state.linkage_violation("base", link, grounded=False)

    assert violation is not None and "'base-imponible'" in violation
    assert state.linkage_violation("base-imponible", link, grounded=False) is None
