"""Parity and referential integrity tests for shared Modelo locale keys."""

from __future__ import annotations

import pytest

from ..schema import ModeloDefinition
from . import registry_locales_parity_scenarios as scenarios
from .registry_tree import bundled_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelos_by_id() -> dict[str, ModeloDefinition]:
    return {modelo.id: modelo for modelo in bundled_registry_tree()[0]}


def test_complete_registry_tree_locales_compile_and_validate_cleanly() -> None:
    scenarios.check_complete_registry_tree_locales_compile_and_validate_cleanly(_modelos_by_id())


def test_modelo_130_all_casillas_have_shared_localized_labels_and_help() -> None:
    scenarios.check_modelo_130_all_casillas_have_shared_localized_labels_and_help(_modelos_by_id())
