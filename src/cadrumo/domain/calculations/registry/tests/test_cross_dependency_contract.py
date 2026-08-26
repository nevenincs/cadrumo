"""Cross-model dependency contract tests for registry-backed modelos."""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from typing import Protocol, get_args

import pytest

from .....core.aggregation import RelationAggregationOp
from .....core.resources import bundled_path
from .._relation_aggregation import relation_aggregation_op
from .._validate_relation_periods import select_relation_source_revisions
from ..binding_selector_utils import selector_as_dict
from ..bindings import binding_source_casilla_ids
from ..errors import RegistryValidationError
from ..handoffs import relation_consumption_index, relation_is_consumed
from ..iva_wallet_relation_targets import is_iva_wallet_owned_relation_target
from ..relations import relation_source_requirements
from ..runtime_graph import expression_relation_refs
from ..schema import (
    DataBindingDefinition,
    DependencyClassificationDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
)
from ..schema_input_kind import InputKind
from ..schema_surfaces import RelationDefinition
from ..validate import RegistryValidator
from ._registry_schema_support import _committed_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CALCULATION_ROLES = {"direct_calculation", "instalment_to_final_settlement", "periodic_to_annual_summary"}


def _registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    return _committed_registry_tree()


@cache
def _validated_registry_tree() -> tuple[tuple[ModeloDefinition, ...], RegistryCatalogues]:
    modelos, catalogues = _registry_tree()
    RegistryValidator(catalogues, source_root=bundled_path()).validate_registry(modelos)
    return modelos, catalogues


def _consumed_relation_refs(revision: ModeloRevision) -> set[str]:
    index = relation_consumption_index(revision)
    return {str(relation.id) for relation in revision.relations if relation_is_consumed(relation, index)}


def test_cross_dependency_roles_match_supported_modelo_hierarchy() -> None:
    modelos, _catalogues = _validated_registry_tree()
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for relation in revision.relations:
                # Intra-modelo dependencies are valid when they read a
                # previous period or a prior filing year; same-period
                # self-source relations would be circular.
                if relation.source_modelo == modelo.id:
                    filing_year_delta = relation.source_revision_selector.filing_year_delta or 0
                    assert relation.kind == "previous_period" or filing_year_delta < 0, (
                        f"{modelo.id}/{revision.id}/{relation.id}"
                    )
                _assert_relation_role_contract(relation, scope=f"{modelo.id}/{revision.id}/{relation.id}")


def test_every_relation_dependency_role_has_a_bundled_consumer() -> None:
    """The accepted relation-role vocabulary contains no speculative member."""
    modelos, _catalogues = _validated_registry_tree()
    bundled_roles = {
        relation.dependency_role
        for modelo in modelos
        for revision in modelo.revisions.values()
        for relation in revision.relations
    }
    declared_roles = set(get_args(RelationDefinition.model_fields["dependency_role"].annotation))
    assert declared_roles == bundled_roles


def _assert_periodic_to_annual_summary_contract(relation: RelationDefinition, *, scope: str) -> None:
    assert relation.kind == "annual_summary", scope
    assert relation.target_periods == ("0A",), scope
    aggregation_op = relation_aggregation_op(relation)
    if aggregation_op == RelationAggregationOp.SUM:
        assert len(relation.source_periods) > 1, scope
        return
    if aggregation_op == RelationAggregationOp.COPY:
        assert relation.source_periods == ("4T",), scope
        assert "simplificado" in relation.id, scope
        return
    raise AssertionError(scope)


def _assert_instalment_to_final_settlement_contract(relation: RelationDefinition, *, scope: str) -> None:
    assert relation.kind == "cross_model_output", scope
    assert relation.target_periods == ("0A",), scope
    assert relation.source_periods, scope


def _assert_direct_calculation_contract(relation: RelationDefinition, *, scope: str) -> None:
    # A direct-calculation relation feeds a value into a calculation:
    # either a cross-model output, or an intra-modelo prior-period
    # carry-forward (`previous_period`) where a modelo reads its own
    # earlier filing.
    assert relation.kind in ("cross_model_output", "previous_period"), scope
    assert relation.target_periods, scope


def _assert_factual_evidence_contract(relation: RelationDefinition, *, scope: str) -> None:
    assert relation.kind == "cross_model_output", scope


class _RelationRoleContractValidator(Protocol):
    def __call__(self, relation: RelationDefinition, *, scope: str) -> None: ...


_ROLE_CONTRACT_VALIDATORS: Mapping[str, _RelationRoleContractValidator] = {
    "periodic_to_annual_summary": _assert_periodic_to_annual_summary_contract,
    "instalment_to_final_settlement": _assert_instalment_to_final_settlement_contract,
    "direct_calculation": _assert_direct_calculation_contract,
    "factual_evidence": _assert_factual_evidence_contract,
}


def _assert_relation_role_contract(relation: RelationDefinition, *, scope: str) -> None:
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


def test_dependency_classifications_exclude_inactive_census_modelo_037() -> None:
    modelos, _catalogues = _validated_registry_tree()
    offenders = [
        f"{modelo.id}/{revision.id}/{classification.id}"
        for modelo in modelos
        for revision in modelo.revisions.values()
        for classification in revision.dependency_classifications
        if classification.source_modelo == "037"
    ]

    assert not offenders, "inactive Modelo 037 must not be an active dependency source: " + ", ".join(offenders)


def test_unconsumed_factual_evidence_relations_use_evidence_treatment() -> None:
    modelos, _catalogues = _validated_registry_tree()
    offenders: list[str] = []

    for modelo in modelos:
        for revision in modelo.revisions.values():
            classifications_by_source = {
                classification.source_modelo: classification for classification in revision.dependency_classifications
            }
            consumed = _consumed_relation_refs(revision)
            for relation in revision.relations:
                if relation.dependency_role != "factual_evidence" or relation.id in consumed:
                    continue
                classification = classifications_by_source.get(relation.source_modelo)
                if classification is not None and classification.treatment != "factual_evidence":
                    offenders.append(
                        f"{modelo.id}/{revision.id}/{relation.id}: classification {classification.id!r} "
                        f"treatment={classification.treatment!r}"
                    )

    assert not offenders, (
        "Unconsumed factual-evidence relation(s) must not advertise direct annual-settlement treatment:\n"
        + "\n".join(f"  * {offender}" for offender in offenders)
    )


def test_formula_bearing_revisions_consume_calculation_relations() -> None:
    modelos, _catalogues = _validated_registry_tree()

    for modelo in modelos:
        for revision in modelo.revisions.values():
            if not revision.formulas:
                continue
            consumed = _consumed_relation_refs(revision)
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
                    casilla = casillas[formula.target_casilla_id]
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
                    modelo_id=str(modelo.id),
                    revision_id=str(revision.id),
                )


def _assert_relation_binding_mirrors_source(
    *,
    binding: DataBindingDefinition,
    relation: RelationDefinition,
    scope: str,
    modelo_id: str,
    revision_id: str,
) -> None:
    """Verify a relation's target binding mirrors the relation's source contract.

    Reads four optional selector keys (``source_modelo`` /
    ``modelo``, ``source_casilla_id``, ``source_casilla_ids``,
    ``source_periods``) and asserts that whichever are declared
    match the relation's published source contract. The
    aggregation-op equality check ensures the binding's
    materialisation strategy agrees with what the relation
    declared.
    """
    selector = selector_as_dict(binding)
    selector_modelo = selector.get("source_modelo", selector.get("modelo"))
    selector_periods = selector.get("source_periods")
    selector_source_casilla_ids = binding_source_casilla_ids(binding)

    # A relation's target_binding is canonically a ``relation_prefill`` slot
    # (aggregation-taxonomy decision ruling 3): the relation owns the cross-period
    # fold-in and the slot only materialises the resolved Decimal. The single
    # documented exception is the iva-wallet-owned M303 compensación binding,
    # which stays ``previous_filing`` (resolved pre-mesh by the iva-wallet gate,
    # ruling D3).
    _iva_wallet_owned = is_iva_wallet_owned_relation_target(
        modelo_id=modelo_id,
        revision_id=revision_id,
        relation_id=str(relation.id),
        target_binding=str(binding.id),
    )
    assert binding.source == ("previous_filing" if _iva_wallet_owned else "relation_prefill"), scope
    assert selector_modelo == relation.source_modelo, scope
    assert selector_source_casilla_ids == (relation.source_casilla_id,), scope
    if selector_periods is not None:
        assert selector_periods == relation.source_periods, scope
    binding_op = binding.aggregation.op if binding.aggregation is not None else None
    assert binding_op == relation_aggregation_op(relation)


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


def test_relation_source_casilla_ids_are_filing_grade_source_casilla_ids() -> None:
    modelos, _catalogues = _validated_registry_tree()
    modelos_by_id = {modelo.id: modelo for modelo in modelos}

    for modelo in modelos:
        for revision in modelo.revisions.values():
            for relation in revision.relations:
                source_modelo = modelos_by_id[relation.source_modelo]
                source_revisions, selector_failures = select_relation_source_revisions(
                    source_modelo,
                    relation.source_revision_selector,
                )
                assert not selector_failures, f"{modelo.id}/{revision.id}/{relation.id}: {selector_failures!r}"
                assert source_revisions, f"{modelo.id}/{revision.id}/{relation.id}"
                for source_revision in source_revisions:
                    casillas = {casilla.id: casilla for casilla in source_revision.casillas}
                    assert relation.source_casilla_id in casillas, f"{modelo.id}/{revision.id}/{relation.id}"
                    assert casillas[relation.source_casilla_id].input_kind != InputKind.INFORMATIONAL, (
                        f"{modelo.id}/{revision.id}/{relation.id}"
                    )


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


def test_dependency_classification_sources_require_official_source_guidance() -> None:
    modelos, catalogues = _registry_tree()
    modelo, _revision, classification, _relation = _first_classified_relation(modelos)
    sources = dict(catalogues.sources)
    for source_ref in classification.source_refs:
        sources[source_ref] = sources[source_ref].model_copy(update={"evidence_tier": "layout_authority"})
    mutated_catalogues = catalogues.model_copy(update={"sources": sources})

    with pytest.raises(
        RegistryValidationError,
        match=r"dependency classification .* requires official_source_guidance source evidence",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_dependency_classification_legal_refs_require_legal_authority() -> None:
    modelos, catalogues = _registry_tree()
    modelo, _revision, classification, _relation = _first_classified_relation(modelos)
    legal = dict(catalogues.legal)
    legal_ref = classification.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=r"dependency classification .* legal ref .* is not legal authority",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


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


def test_relation_sources_require_official_source_guidance() -> None:
    modelos, catalogues = _registry_tree()
    modelo, _revision, relation = _first_relation(modelos)
    sources = dict(catalogues.sources)
    for source_ref in relation.source_refs:
        sources[source_ref] = sources[source_ref].model_copy(update={"evidence_tier": "layout_authority"})
    mutated_catalogues = catalogues.model_copy(update={"sources": sources})

    with pytest.raises(
        RegistryValidationError,
        match=r"relation .* requires official_source_guidance source evidence",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_relation_legal_refs_require_legal_authority() -> None:
    modelos, catalogues = _registry_tree()
    modelo, _revision, relation = _first_relation(modelos)
    legal = dict(catalogues.legal)
    legal_ref = relation.legal_refs[0]
    legal[legal_ref] = legal[legal_ref].model_copy(update={"evidence_tier": "official_source_guidance"})
    mutated_catalogues = catalogues.model_copy(update={"legal": legal})

    with pytest.raises(
        RegistryValidationError,
        match=r"relation .* legal ref .* is not legal authority",
    ):
        RegistryValidator(mutated_catalogues, source_root=bundled_path()).validate_modelo(modelo)


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
