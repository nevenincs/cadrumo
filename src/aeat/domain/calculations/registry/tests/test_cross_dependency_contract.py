"""Cross-model dependency contract tests for registry-backed modelos."""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache

import pytest

from .....core.resources import bundled_path
from .._errors import RegistryValidationError
from .._loader import load_registry_tree
from .._relations import relation_source_requirements
from .._runtime_graph import expression_relation_refs
from .._schema import (
    DependencyClassificationDefinition,
    InputKind,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RelationDefinition,
)
from .._validate import RegistryValidator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_CALCULATION_ROLES = {"direct_calculation", "instalment_to_final_settlement", "periodic_to_annual_summary"}


def _registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return load_registry_tree(_REGISTRY_ROOT)


@lru_cache(maxsize=1)
def _validated_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    modelos, catalogues = _registry_tree()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)
    return modelos, catalogues


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
    return isinstance(selector.get("filing_year_delta"), int)


def test_cross_dependency_roles_match_supported_modelo_hierarchy() -> None:
    modelos, _catalogues = _validated_registry_tree()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for relation in revision.relations:
                # Intra-modelo dependencies are valid when they read a
                # previous period or a prior filing year; same-period
                # self-source relations would be circular.
                if relation.source_modelo == modelo.id:
                    selector = relation.source_revision_selector or {}
                    filing_year_delta = selector.get("filing_year_delta", 0)
                    assert isinstance(filing_year_delta, int), (
                        f"filing_year_delta must be int, got {type(filing_year_delta).__name__}"
                    )
                    assert relation.kind == "previous_period" or filing_year_delta < 0, (
                        f"{modelo.id}/{revision.id}/{relation.id}"
                    )
                _assert_relation_role_contract(relation, scope=f"{modelo.id}/{revision.id}/{relation.id}")


_PROFILE_SCHEDULE_SOURCE_MODELOS = frozenset({"036", "037", "840"})


def _assert_periodic_to_annual_summary_contract(relation, *, scope: str) -> None:  # type: ignore[no-untyped-def]
    assert relation.kind == "annual_summary", scope
    assert relation.target_periods == ("0A",), scope
    assert len(relation.source_periods) > 1, scope
    assert (relation.aggregation or {}).get("op") == "sum", scope


def _assert_instalment_to_final_settlement_contract(relation, *, scope: str) -> None:  # type: ignore[no-untyped-def]
    assert relation.kind == "cross_model_output", scope
    assert relation.target_periods == ("0A",), scope
    assert relation.source_periods, scope


def _assert_direct_calculation_contract(relation, *, scope: str) -> None:  # type: ignore[no-untyped-def]
    # A direct-calculation relation feeds a value into a calculation:
    # either a cross-model output, or an intra-modelo prior-period
    # carry-forward (`previous_period`) where a modelo reads its own
    # earlier filing.
    assert relation.kind in ("cross_model_output", "previous_period"), scope
    assert relation.target_periods, scope


def _assert_factual_evidence_contract(relation, *, scope: str) -> None:  # type: ignore[no-untyped-def]
    assert relation.kind == "cross_model_output", scope


def _assert_profile_schedule_contract(relation, *, scope: str) -> None:  # type: ignore[no-untyped-def]
    assert relation.source_modelo in _PROFILE_SCHEDULE_SOURCE_MODELOS, scope


_ROLE_CONTRACT_VALIDATORS = {
    "periodic_to_annual_summary": _assert_periodic_to_annual_summary_contract,
    "instalment_to_final_settlement": _assert_instalment_to_final_settlement_contract,
    "direct_calculation": _assert_direct_calculation_contract,
    "factual_evidence": _assert_factual_evidence_contract,
    "profile_schedule": _assert_profile_schedule_contract,
}


def _assert_relation_role_contract(relation, *, scope: str) -> None:  # type: ignore[no-untyped-def]
    """Dispatch to the per-role contract validator (no-op for unrecognised roles).

    Each role's contract lives in its own
    ``_assert_<role>_contract`` helper so a change to one role's
    rules touches exactly one function. Unrecognised roles are a
    no-op here so the gate only enforces the declared families.
    """
    validator = _ROLE_CONTRACT_VALIDATORS.get(relation.dependency_role)
    if validator is not None:
        validator(relation, scope=scope)


def test_cross_dependency_source_requirements_are_derivable_for_target_periods() -> None:
    modelos, _catalogues = _validated_registry_tree()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            classifications_by_source = {
                classification.source_modelo: classification for classification in revision.dependency_classifications
            }
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
                for requirement in requirements:
                    assert (
                        requirement.dependency_treatment
                        == classifications_by_source[requirement.source_modelo].treatment
                    )


def test_formula_bearing_revisions_consume_calculation_relations() -> None:
    modelos, _catalogues = _validated_registry_tree()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            if not revision.formulas and not revision.algorithm_bindings:
                continue
            consumed = _formula_relation_refs(revision) | _algorithm_relation_refs(revision)
            required = {
                relation.id
                for relation in revision.relations
                if relation.dependency_role in _CALCULATION_ROLES
                # `previous_period` carry-forward relations deliver their
                # value through a `target_binding`, not a formula
                # expression, so they are not formula-consumed.
                and relation.kind != "previous_period"
            }
            assert required.issubset(consumed), f"{modelo.id}/{revision.id}: {sorted(required - consumed)}"


def test_formula_relation_dependencies_are_attached_to_computed_casillas() -> None:
    modelos, _catalogues = _validated_registry_tree()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            relations = {relation.id: relation for relation in revision.relations}
            casillas = {casilla.id: casilla for casilla in revision.casillas}
            bindings = {binding.id for binding in revision.bindings}
            for formula in revision.formulas:
                for relation_id in expression_relation_refs(formula.expression):
                    relation = relations[relation_id]
                    casilla = casillas[formula.target]
                    assert casilla.input_kind == InputKind.COMPUTED, f"{modelo.id}/{revision.id}/{formula.id}"
                    assert casilla.formula == formula.id, f"{modelo.id}/{revision.id}/{formula.id}"
                    assert relation.target_binding in bindings, f"{modelo.id}/{revision.id}/{relation.id}"


def test_relation_target_bindings_mirror_source_contract() -> None:
    modelos, _catalogues = _validated_registry_tree()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            bindings = {binding.id: binding for binding in revision.bindings}
            for relation in revision.relations:
                _assert_relation_binding_mirrors_source(
                    binding=bindings[relation.target_binding],
                    relation=relation,
                    scope=f"{modelo.id}/{revision.id}/{relation.id}",
                )


def _assert_relation_binding_mirrors_source(*, binding, relation, scope: str) -> None:  # type: ignore[no-untyped-def]
    """Verify a relation's target binding mirrors the relation's source contract.

    Reads four optional selector keys (``source_modelo`` /
    ``modelo``, ``source_output``, ``source_casillas``,
    ``source_periods``) and asserts that whichever are declared
    match the relation's published source contract. The
    aggregation-op equality check ensures the binding's
    materialisation strategy agrees with what the relation
    declared.
    """
    selector = binding.selector
    selector_modelo = selector.get("source_modelo", selector.get("modelo"))
    selector_output = selector.get("source_output")
    selector_casillas = selector.get("source_casillas")
    selector_periods = selector.get("source_periods")

    # A relation's target_binding is canonically a ``relation_prefill`` slot
    # (aggregation-taxonomy decision ruling 3): the relation owns the cross-period
    # fold-in and the slot only materialises the resolved Decimal. The single
    # documented exception is the iva-wallet-owned M303 compensación binding,
    # which stays ``previous_filing`` (resolved pre-mesh by the iva-wallet gate,
    # ruling D3).
    _iva_wallet_owned = binding.id == "modelo-303-compensacion-pendiente-anteriores"
    assert binding.source == ("previous_filing" if _iva_wallet_owned else "relation_prefill"), scope
    assert selector_modelo == relation.source_modelo, scope
    if selector_output is not None:
        assert selector_output == relation.source_output, scope
    if selector_casillas is not None:
        assert selector_casillas == (relation.source_output,), scope
    if selector_periods is not None:
        assert selector_periods == relation.source_periods, scope
    binding_op = binding.aggregation.op if binding.aggregation is not None else None
    assert binding_op == (relation.aggregation or {}).get("op")


def test_formula_relation_dependencies_carry_relation_legal_basis() -> None:
    modelos, _catalogues = _validated_registry_tree()

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
    modelos, _catalogues = _validated_registry_tree()
    modelos_by_id = {modelo.id: modelo for modelo in modelos}

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
                        assert casillas[relation.source_output].input_kind != InputKind.INFORMATIONAL, (
                            f"{modelo.id}/{revision.id}/{relation.id}"
                        )
                    else:
                        assert relation.source_output in algorithm_outputs, f"{modelo.id}/{revision.id}/{relation.id}"


def test_dependency_classifications_preserve_relation_authority_basis() -> None:
    modelos, catalogues = _registry_tree()
    modelo, revision, classification, _relation = _first_classified_relation(modelos)
    stripped = classification.model_copy(update={"source_refs": ()})
    mutated_revision = revision.model_copy(
        update={
            "dependency_classifications": tuple(
                stripped if item.id == classification.id else item for item in revision.dependency_classifications
            ),
        },
    )
    mutated_modelo = _replace_revision(modelo, mutated_revision)

    with pytest.raises(
        RegistryValidationError,
        match=r"dependency classification .* does not include relation source refs",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def test_relation_target_bindings_preserve_relation_authority_basis() -> None:
    modelos, catalogues = _registry_tree()
    modelo, revision, relation = _first_relation(modelos)
    binding = next(item for item in revision.bindings if item.id == relation.target_binding)
    stripped = binding.model_copy(update={"legal_refs": ()})
    mutated_revision = revision.model_copy(
        update={"bindings": tuple(stripped if item.id == binding.id else item for item in revision.bindings)},
    )
    mutated_modelo = _replace_revision(modelo, mutated_revision)

    with pytest.raises(
        RegistryValidationError,
        match=r"relation .* target binding .* does not include relation legal refs",
    ):
        RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(mutated_modelo)


def _first_relation(
    modelos: tuple[ModeloDefinition, ...],
) -> tuple[ModeloDefinition, ModeloRevision, RelationDefinition]:
    for modelo in modelos:
        for revision in modelo.revisions.values():
            if revision.relations:
                return modelo, revision, revision.relations[0]
    raise AssertionError("committed registry has no relations")


def _first_classified_relation(
    modelos: tuple[ModeloDefinition, ...],
) -> tuple[ModeloDefinition, ModeloRevision, DependencyClassificationDefinition, RelationDefinition]:
    for modelo in modelos:
        for revision in modelo.revisions.values():
            relations = {relation.id: relation for relation in revision.relations}
            for classification in revision.dependency_classifications:
                if classification.relation_refs:
                    return modelo, revision, classification, relations[classification.relation_refs[0]]
    raise AssertionError("committed registry has no classified relations")


def _replace_revision(modelo: ModeloDefinition, revision: ModeloRevision) -> ModeloDefinition:
    return modelo.model_copy(
        update={
            "revisions": {
                revision_id: revision if revision_id == revision.id else item
                for revision_id, item in modelo.revisions.items()
            },
        },
    )
