"""Cross-model dependency contract tests for registry-backed modelos."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._loader import load_registry_tree
from ._relations import relation_source_requirements
from ._runtime_graph import expression_relation_refs
from ._schema import ModeloDefinition, ModeloRevision, RegistryCatalogues
from ._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"
_CALCULATION_ROLES = {"direct_calculation", "instalment_to_final_settlement", "periodic_to_annual_summary"}


def _registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return load_registry_tree(_REGISTRY_ROOT)


def _formula_relation_refs(revision: ModeloRevision) -> set[str]:
    refs: set[str] = set()
    for formula in revision.formulas:
        refs.update(expression_relation_refs(formula.expression))
    return refs


def _algorithm_relation_refs(revision: ModeloRevision) -> set[str]:
    relation_ids = {relation.id for relation in revision.relations}
    return {
        str(value)
        for binding in revision.algorithm_bindings
        for value in binding.inputs.values()
        if str(value) in relation_ids
    }


def _revision_matches_selector(revision: ModeloRevision, selector: Mapping[str, str | int]) -> bool:
    year = selector.get("year")
    if isinstance(year, int):
        return revision.period_selector.includes_year(year)
    year_from = selector.get("year_from")
    if isinstance(year_from, int):
        year_to = selector.get("year_to")
        if not isinstance(year_to, int):
            year_to = 2999
        revision_from = revision.period_selector.year_from or min(revision.period_selector.years)
        revision_to = revision.period_selector.year_to
        if revision_to is None and revision.period_selector.years:
            revision_to = max(revision.period_selector.years)
        if revision_to is None:
            revision_to = 2999
        return revision_from <= year_to and year_from <= revision_to
    return False


def test_cross_dependency_roles_match_supported_modelo_hierarchy() -> None:
    modelos, catalogues = _registry_tree()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            for relation in revision.relations:
                assert relation.source_modelo != modelo.id
                if relation.dependency_role == "periodic_to_annual_summary":
                    assert relation.kind == "annual_summary", relation.id
                    assert relation.target_periods == ("0A",), relation.id
                    assert len(relation.source_periods) > 1, relation.id
                    assert (relation.aggregation or {}).get("op") == "sum", relation.id
                elif relation.dependency_role == "instalment_to_final_settlement":
                    assert relation.kind == "cross_model_output", relation.id
                    assert relation.target_periods == ("0A",), relation.id
                    assert relation.source_periods, relation.id
                elif relation.dependency_role == "direct_calculation":
                    assert relation.kind == "cross_model_output", relation.id
                    assert relation.target_periods, relation.id
                elif relation.dependency_role == "factual_evidence":
                    assert relation.kind == "cross_model_output", relation.id
                elif relation.dependency_role == "profile_schedule":
                    assert relation.source_modelo in {"036", "037", "840"}, relation.id


def test_cross_dependency_source_requirements_are_derivable_for_target_periods() -> None:
    modelos, catalogues = _registry_tree()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            for target_period in revision.period_selector.periods:
                requirements = relation_source_requirements(
                    revision,
                    filing_year=revision.period_selector.year_from or next(iter(revision.period_selector.years)),
                    period=target_period,
                )
                expected_relation_ids = {
                    relation.id
                    for relation in revision.relations
                    if not relation.target_periods or target_period in relation.target_periods
                }
                resolved_relation_ids = {
                    relation_id for requirement in requirements for relation_id in requirement.relation_ids
                }
                assert resolved_relation_ids == expected_relation_ids


def test_formula_bearing_revisions_consume_calculation_relations() -> None:
    modelos, catalogues = _registry_tree()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            if not revision.formulas and not revision.algorithm_bindings:
                continue
            consumed = _formula_relation_refs(revision) | _algorithm_relation_refs(revision)
            required = {
                relation.id for relation in revision.relations if relation.dependency_role in _CALCULATION_ROLES
            }
            assert required.issubset(consumed), f"{modelo.id}/{revision.id}: {sorted(required - consumed)}"


def test_formula_relation_dependencies_are_attached_to_computed_casillas() -> None:
    modelos, catalogues = _registry_tree()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            relations = {relation.id: relation for relation in revision.relations}
            casillas = {casilla.id: casilla for casilla in revision.casillas}
            bindings = {binding.id for binding in revision.bindings}
            for formula in revision.formulas:
                for relation_id in expression_relation_refs(formula.expression):
                    relation = relations[relation_id]
                    casilla = casillas[formula.target]
                    assert casilla.input_kind == "computed", f"{modelo.id}/{revision.id}/{formula.id}"
                    assert casilla.formula == formula.id, f"{modelo.id}/{revision.id}/{formula.id}"
                    assert relation.target_binding in bindings, f"{modelo.id}/{revision.id}/{relation.id}"


def test_relation_target_bindings_mirror_source_contract() -> None:
    modelos, catalogues = _registry_tree()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            bindings = {binding.id: binding for binding in revision.bindings}
            for relation in revision.relations:
                binding = bindings[relation.target_binding]
                selector = binding.selector
                selector_modelo = selector.get("source_modelo", selector.get("modelo"))
                selector_casillas = selector.get("source_casillas")
                selector_periods = selector.get("source_periods")
                selector_period = selector.get("period")

                assert binding.source == "previous_filing", f"{modelo.id}/{revision.id}/{relation.id}"
                assert selector_modelo == relation.source_modelo, f"{modelo.id}/{revision.id}/{relation.id}"
                assert selector_casillas == (relation.source_output,), f"{modelo.id}/{revision.id}/{relation.id}"
                if selector_periods is not None:
                    assert selector_periods == relation.source_periods, f"{modelo.id}/{revision.id}/{relation.id}"
                else:
                    assert selector_period == relation.source_periods[0], f"{modelo.id}/{revision.id}/{relation.id}"
                assert (binding.aggregation or {}).get("op") == (relation.aggregation or {}).get("op")


def test_formula_relation_dependencies_carry_relation_legal_basis() -> None:
    modelos, catalogues = _registry_tree()

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            relations = {relation.id: relation for relation in revision.relations}
            for formula in revision.formulas:
                for relation_id in expression_relation_refs(formula.expression):
                    relation = relations[relation_id]
                    assert set(relation.legal_refs).issubset(formula.legal_refs), (
                        f"{modelo.id}/{revision.id}/{formula.id}: {relation_id}"
                    )


def test_relation_source_outputs_are_filing_grade_source_outputs() -> None:
    modelos, catalogues = _registry_tree()
    modelos_by_id = {modelo.id: modelo for modelo in modelos}

    RegistryValidator(catalogues, source_root=PROJECT_ROOT).validate_registry(modelos)

    for modelo in modelos:
        for revision in modelo.revisions.values():
            for relation in revision.relations:
                source_modelo = modelos_by_id[relation.source_modelo]
                source_revisions = tuple(
                    source_revision
                    for source_revision in source_modelo.revisions.values()
                    if _revision_matches_selector(source_revision, relation.source_revision_selector)
                )
                assert source_revisions, f"{modelo.id}/{revision.id}/{relation.id}"
                for source_revision in source_revisions:
                    casillas = {casilla.id: casilla for casilla in source_revision.casillas}
                    algorithm_outputs = {
                        str(output)
                        for algorithm_binding in source_revision.algorithm_bindings
                        for output in algorithm_binding.outputs.values()
                    }
                    if relation.source_output in casillas:
                        assert casillas[relation.source_output].input_kind != "informational", (
                            f"{modelo.id}/{revision.id}/{relation.id}"
                        )
                    else:
                        assert relation.source_output in algorithm_outputs, f"{modelo.id}/{revision.id}/{relation.id}"
