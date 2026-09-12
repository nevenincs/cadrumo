"""Contract tests for relation-prefill bindings and dependency classifications."""

from __future__ import annotations

from functools import cache

import pytest

from dev.registry.compiler.validator import RegistryValidator
from dev.registry.conformance.registry_schema_support import committed_registry_tree

from .....core.resources.bundled_data import bundled_path
from ..bindings import binding_source_casilla_ids
from ..relations import relation_prefill_bindings_for_period, relation_source_requirements
from ..schema import ModeloDefinition, RegistryCatalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _validated_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    modelos, catalogues = committed_registry_tree()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)
    return modelos, catalogues


def test_relation_prefill_providers_are_grounded_and_role_typed() -> None:
    modelos, _catalogues = _validated_registry_tree()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            classifications = {
                classification.source_modelo: classification for classification in revision.dependency_classifications
            }
            for binding, provider in relation_prefill_bindings_for_period(revision):
                assert provider.source_modelo in classifications, f"{modelo.id}/{revision.id}/{binding.id}"
                assert binding_source_casilla_ids(binding) == provider.declared_source_casilla_ids
                if provider.relation_kind == "annual_summary":
                    assert provider.dependency_role == "periodic_to_annual_summary"


def test_relation_prefill_requirements_are_keyed_by_the_target_binding() -> None:
    modelos, _catalogues = _validated_registry_tree()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            for target_period in revision.period_selector.periods:
                requirements = relation_source_requirements(
                    revision,
                    filing_year=revision.period_selector.year_from or next(iter(revision.period_selector.years)),
                    period=target_period,
                )
                resolved_binding_ids = {
                    binding_id for requirement in requirements for binding_id in requirement.target_bindings
                }
                expected_binding_ids = {
                    binding.id
                    for binding, _provider in relation_prefill_bindings_for_period(revision, period=target_period)
                }
                assert resolved_binding_ids == expected_binding_ids, f"{modelo.id}/{revision.id}/{target_period}"


def test_relation_prefill_provider_source_models_exist_in_the_loaded_tree() -> None:
    modelos, _catalogues = _validated_registry_tree()
    modelo_ids = {modelo.id for modelo in modelos}

    for modelo in modelos:
        for revision in modelo.revisions.values():
            for binding, provider in relation_prefill_bindings_for_period(revision):
                assert provider.source_modelo in modelo_ids, f"{modelo.id}/{revision.id}/{binding.id}"
