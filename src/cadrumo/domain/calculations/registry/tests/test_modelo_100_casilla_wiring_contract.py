"""Regression gates for formula-to-casilla wiring across the registry."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from ..schema import RelationDefinition
from ..schema_input_kind import InputKind
from ._modelo_100_registry_support import _loaded_registry, _registry_validator

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_every_formula_target_is_declared_as_the_matching_computed_casilla() -> None:
    """Formula evaluation and casilla input classification share one contract."""
    modelos_by_id, _catalogues = _loaded_registry()

    _registry_validator().validate_registry(modelos_by_id.values())

    for modelo in modelos_by_id.values():
        for revision in modelo.revisions.values():
            casillas_by_id = {casilla.id: casilla for casilla in revision.casillas}
            for formula in revision.formulas:
                casilla = casillas_by_id[formula.target_casilla_id]
                assert casilla.input_kind is InputKind.COMPUTED, (
                    f"{modelo.id}/{revision.id}/{formula.id}: "
                    f"target {formula.target_casilla_id} is {casilla.input_kind.value}"
                )
                assert casilla.formula == formula.id, (
                    f"{modelo.id}/{revision.id}/{formula.id}: "
                    f"target {formula.target_casilla_id} declares {casilla.formula!r}"
                )


def test_revision_producer_inventory_keeps_formula_and_non_formula_paths_visible() -> None:
    """The real registry inventory preserves deterministic and intentional producers."""
    modelos_by_id, _catalogues = _loaded_registry()
    observed_kinds: set[str] = set()

    for modelo in modelos_by_id.values():
        for revision in modelo.revisions.values():
            inventory = revision.producer_inventory()
            declared_casilla_ids = {casilla.id for casilla in revision.casillas}
            assert set(inventory.producer_kind_by_casilla) == declared_casilla_ids
            assert set(inventory.producer_reason_by_casilla) == declared_casilla_ids
            assert set(inventory.producer_provenance_by_casilla) == declared_casilla_ids
            assert inventory.computed_casilla_ids == frozenset(
                casilla.id for casilla in revision.casillas if casilla.input_kind is InputKind.COMPUTED
            )
            assert sum(len(formula_ids) for formula_ids in inventory.formula_ids_by_target.values()) == len(
                revision.formulas
            )
            for formula in revision.formulas:
                assert formula.id in inventory.formula_ids_by_target[formula.target_casilla_id]
            for casilla in revision.casillas:
                traces = inventory.producer_provenance_by_casilla[casilla.id]
                assert traces
                assert all(trace.casilla.id == casilla.id for trace in traces)
                assert {trace.producer_kind for trace in traces} == {inventory.producer_kind_by_casilla[casilla.id]}
                assert {trace.reason for trace in traces} == {inventory.producer_reason_by_casilla[casilla.id]}
                assert all(trace.casilla.legal_refs == casilla.legal_refs for trace in traces)
                assert all(trace.casilla.source_refs == casilla.source_refs for trace in traces)

                producer_kind = inventory.producer_kind_by_casilla[casilla.id]
                if producer_kind == "formula":
                    formulas = tuple(trace.formula for trace in traces)
                    assert all(formula is not None for formula in formulas)
                    assert all(formula.target_casilla_id == casilla.id for formula in formulas if formula is not None)
                    assert {formula.id for formula in formulas if formula is not None} == {casilla.formula}
                    assert all(
                        trace.producer_legal_refs == trace.formula.legal_refs
                        and trace.producer_source_refs == trace.formula.source_refs
                        for trace in traces
                        if trace.formula is not None
                    )
                elif producer_kind == "manual":
                    assert len(traces) == 1
                    trace = traces[0]
                    assert trace.formula is None and trace.binding is None and trace.relation is None
                    assert trace.producer_legal_refs == casilla.legal_refs
                    assert trace.producer_source_refs == casilla.source_refs
                elif producer_kind == "upstream":
                    assert len(traces) == 1
                    trace = traces[0]
                    assert trace.binding is not None and trace.binding.id == casilla.binding
                    assert trace.formula is None and trace.relation is None
                    assert trace.producer_legal_refs == trace.binding.legal_refs
                    assert trace.producer_source_refs == trace.binding.source_refs
                elif producer_kind == "relation":
                    assert all(trace.binding is not None and trace.binding.id == casilla.binding for trace in traces)
                    assert all(trace.formula is None for trace in traces)
                    relation_ids = {trace.relation.id for trace in traces if trace.relation is not None}
                    expected_relation_ids = {
                        relation.id for relation in revision.relations if relation.target_binding == casilla.binding
                    }
                    assert relation_ids == expected_relation_ids
                    assert all(
                        trace.relation is not None
                        and trace.producer_legal_refs == trace.relation.legal_refs
                        and trace.producer_source_refs == trace.relation.source_refs
                        for trace in traces
                    )
                else:
                    # The two kinds that produce no calculation edge at all, so
                    # their grounding is the casilla's own. Asserted together
                    # because they share a SHAPE rather than a name; a kind
                    # added later still reds here instead of falling through,
                    # which is what keeps this branch exhaustive.
                    assert producer_kind in {"informational", "projection_only"}, producer_kind
                    assert len(traces) == 1
                    trace = traces[0]
                    assert trace.formula is None and trace.binding is None and trace.relation is None
                    assert trace.producer_legal_refs == casilla.legal_refs
                    assert trace.producer_source_refs == casilla.source_refs
            observed_kinds.update(inventory.producer_kind_by_casilla.values())

    assert observed_kinds >= {"formula", "manual", "upstream", "relation", "informational"}


def test_revision_producer_inventory_does_not_flatten_relation_provenance() -> None:
    """Each real relation declaration retains its own refs in the producer trace."""
    modelos_by_id, _catalogues = _loaded_registry()

    for modelo in modelos_by_id.values():
        for revision in modelo.revisions.values():
            relations_by_binding: dict[str, list[RelationDefinition]] = {}
            for relation in revision.relations:
                relations_by_binding.setdefault(relation.target_binding, []).append(relation)
            for binding_id, relations in relations_by_binding.items():
                if len(relations) < 2:
                    continue
                casilla = next(
                    (casilla for casilla in revision.casillas if casilla.binding == binding_id),
                    None,
                )
                if casilla is None:
                    continue
                inventory = revision.producer_inventory()
                traces = inventory.producer_provenance_by_casilla[casilla.id]
                relation_traces = tuple(trace for trace in traces if trace.relation is not None)
                relation_ids = {
                    relation.id for trace in relation_traces for relation in (trace.relation,) if relation is not None
                }
                assert relation_ids == {relation.id for relation in relations}
                assert all(trace.binding is not None and trace.binding.id == binding_id for trace in relation_traces)
                return

    raise AssertionError("bundled registry has no casilla with multiple relation declarations")


def test_registry_validator_rejects_a_manual_formula_target() -> None:
    """The load-boundary validator prevents the old M100 drift from returning."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    target = next(formula.target_casilla_id for formula in revision.formulas)
    broken_casillas = tuple(
        casilla.model_copy(update={"input_kind": InputKind.MANUAL}) if casilla.id == target else casilla
        for casilla in revision.casillas
    )
    broken_revision = revision.model_copy(update={"casillas": broken_casillas})
    broken_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: broken_revision}})

    with pytest.raises(RegistryValidationError, match=r"formula .*targets casilla"):
        _registry_validator().validate_modelo(broken_modelo)


def test_registry_validator_rejects_a_formula_target_without_back_reference() -> None:
    """The formula target must also name the same formula in its casilla row."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    target = next(formula.target_casilla_id for formula in revision.formulas)
    broken_casillas = tuple(
        casilla.model_copy(update={"formula": None}) if casilla.id == target else casilla
        for casilla in revision.casillas
    )
    broken_revision = revision.model_copy(update={"casillas": broken_casillas})
    broken_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: broken_revision}})

    with pytest.raises(RegistryValidationError, match=r"whose declared formula is None"):
        _registry_validator().validate_modelo(broken_modelo)


def test_registry_validator_rejects_a_computed_casilla_without_a_formula_producer() -> None:
    """A computed row cannot silently fall back to an input path."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    manual_casilla = next(casilla for casilla in revision.casillas if casilla.input_kind is InputKind.MANUAL)
    broken_casillas = tuple(
        casilla.model_copy(update={"input_kind": InputKind.COMPUTED, "formula": None})
        if casilla.id == manual_casilla.id
        else casilla
        for casilla in revision.casillas
    )
    broken_revision = revision.model_copy(update={"casillas": broken_casillas})
    broken_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: broken_revision}})

    with pytest.raises(RegistryValidationError, match=r"computed casilla .*no formula producer declaration"):
        _registry_validator().validate_modelo(broken_modelo)


def test_registry_validator_rejects_a_noncomputed_casilla_formula_declaration() -> None:
    """Manual rows may remain manual, but cannot carry a deterministic formula declaration."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    manual_casilla = next(casilla for casilla in revision.casillas if casilla.input_kind is InputKind.MANUAL)
    formula_id = revision.formulas[0].id
    broken_casillas = tuple(
        casilla.model_copy(update={"formula": formula_id}) if casilla.id == manual_casilla.id else casilla
        for casilla in revision.casillas
    )
    broken_revision = revision.model_copy(update={"casillas": broken_casillas})
    broken_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: broken_revision}})

    with pytest.raises(RegistryValidationError, match=r"formula declarations must be computed"):
        _registry_validator().validate_modelo(broken_modelo)


def test_registry_validator_rejects_duplicate_formula_targets() -> None:
    """Two deterministic producers cannot claim the same casilla target."""
    modelos_by_id, _catalogues = _loaded_registry()
    modelo = modelos_by_id["100"]
    revision = modelo.revisions["2025"]
    first_formula, second_formula = revision.formulas[:2]
    broken_formulas = tuple(
        formula.model_copy(update={"target_casilla_id": first_formula.target_casilla_id})
        if formula.id == second_formula.id
        else formula
        for formula in revision.formulas
    )
    broken_revision = revision.model_copy(update={"formulas": broken_formulas})
    broken_modelo = modelo.model_copy(update={"revisions": {**modelo.revisions, revision.id: broken_revision}})

    with pytest.raises(RegistryValidationError, match=r"duplicate formula target"):
        _registry_validator().validate_modelo(broken_modelo)
