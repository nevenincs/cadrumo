"""Parity and referential integrity tests for shared Modelo locale keys."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition
from cadrumo.domain.calculations.registry.tests import registry_locales_parity_scenarios as scenarios
from cadrumo.domain.calculations.registry.tests.authored_editions import open_ended_revision
from dev.registry.compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelos_by_id() -> dict[str, ModeloDefinition]:
    return {modelo.id: modelo for modelo in compiled_bundled_authority().modelos}


def test_complete_registry_tree_locales_compile_and_validate_cleanly() -> None:
    scenarios.check_complete_registry_tree_locales_compile_and_validate_cleanly(_modelos_by_id())


def test_modelo_130_all_casillas_have_shared_localized_labels_and_help() -> None:
    scenarios.check_modelo_130_all_casillas_have_shared_localized_labels_and_help(_modelos_by_id())
    # 19 printed boxes, the saldo and art. 32.1 working figures, and box 02's two working figures.
    assert len(_modelos_by_id()["130"].revisions[str(open_ended_revision("130").id)].casillas) == 23
