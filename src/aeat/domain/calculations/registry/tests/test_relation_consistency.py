from __future__ import annotations

from collections.abc import Iterable, Mapping

import pytest

from .....core.resources import bundled_path
from .. import load_registry_tree, previous_filing_source_reference
from .._schema import DataBindingDefinition, ModeloDefinition, ModeloRevision, RelationDefinition
from .._validate_relation_periods import select_relation_source_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


@pytest.fixture(scope="module")
def _registry_relation_cases() -> tuple[
    tuple[ModeloDefinition, ModeloRevision, RelationDefinition, dict[str, ModeloDefinition]],
    ...,
]:
    """Pre-load the committed registry once and expose every (modelo, revision, relation) triple.

    Module-scoped fixture so the costly :func:`load_registry_tree` walk
    runs exactly once per pytest module. The ``by_id`` lookup is
    snapshotted alongside each triple so the per-case body never
    re-loads the tree.
    """
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    by_id = {modelo.id: modelo for modelo in modelos}
    return tuple((modelo, revision, relation, by_id) for modelo, revision, relation in _relations(modelos))


def _relation_consistency_errors(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    relation: RelationDefinition,
    by_id: Mapping[str, ModeloDefinition],
) -> list[str]:
    """Return every consistency offence the (modelo, revision, relation) triple carries.

    Per-relation checks split out so each one reads as a single rule:
    target binding present → source modelo present → at least one
    matching source revision → each source revision's outputs +
    periods + offset-derived periods accept the relation's claim.
    """
    errors: list[str] = []
    errors.extend(_target_binding_errors(modelo, revision, relation))
    source_modelo = by_id.get(relation.source_modelo)
    if source_modelo is None:
        errors.append(f"{modelo.id}/{revision.id}/{relation.id}: unknown source modelo {relation.source_modelo}")
        return errors
    matching_revisions = tuple(_matching_source_revisions(source_modelo, relation))
    if not matching_revisions:
        errors.append(f"{modelo.id}/{revision.id}/{relation.id}: no source revision matches selector")
        return errors
    for source_revision in matching_revisions:
        errors.extend(_source_revision_consistency_errors(modelo, revision, relation, source_modelo, source_revision))
    return errors


def _target_binding_errors(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    relation: RelationDefinition,
) -> list[str]:
    target_bindings = {binding.id for binding in revision.bindings}
    if relation.target_binding in target_bindings:
        return []
    return [f"{modelo.id}/{revision.id}/{relation.id}: unknown target binding {relation.target_binding}"]


def _source_revision_consistency_errors(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    relation: RelationDefinition,
    source_modelo: ModeloDefinition,
    source_revision: ModeloRevision,
) -> list[str]:
    """Three checks against one source-revision candidate: outputs, periods, offset-derived periods."""
    errors: list[str] = []
    source_casilla_ids = {casilla.id for casilla in source_revision.casillas}
    if relation.source_casilla_id not in source_casilla_ids:
        errors.append(
            f"{modelo.id}/{revision.id}/{relation.id}: source casilla id {relation.source_casilla_id} "
            f"not defined by {source_modelo.id}/{source_revision.id}",
        )
    revision_periods = set(source_revision.period_selector.periods)
    relation_periods = set(relation.source_periods)
    if relation_periods and not relation_periods.issubset(revision_periods):
        unknown_periods = sorted(relation_periods - revision_periods)
        errors.append(
            f"{modelo.id}/{revision.id}/{relation.id}: source periods {unknown_periods} "
            f"not accepted by {source_modelo.id}/{source_revision.id}",
        )
    errors.extend(
        _offset_derived_period_errors(
            modelo,
            revision,
            relation,
            source_modelo,
            source_revision,
            revision_periods=revision_periods,
        ),
    )
    return errors


def _offset_derived_period_errors(
    modelo: ModeloDefinition,
    revision: ModeloRevision,
    relation: RelationDefinition,
    source_modelo: ModeloDefinition,
    source_revision: ModeloRevision,
    *,
    revision_periods: set[str],
) -> list[str]:
    """For offset-driven relations, verify every derived source period is in revision_periods."""
    if relation.source_period_offset_from_target is None:
        return []
    from .._relations import _derive_offset_source_period

    derived: set[str] = set()
    for target_period in relation.target_periods:
        candidate = _derive_offset_source_period(relation, target_period=target_period)
        if candidate is not None:
            derived.add(candidate)
    unknown_derived = sorted(derived - revision_periods)
    if not unknown_derived:
        return []
    return [
        f"{modelo.id}/{revision.id}/{relation.id}: offset-derived source periods "
        f"{unknown_derived} not accepted by {source_modelo.id}/{source_revision.id}",
    ]


def test_registry_relations_reference_existing_modelo_outputs_and_target_bindings(
    _registry_relation_cases: tuple[
        tuple[ModeloDefinition, ModeloRevision, RelationDefinition, Mapping[str, ModeloDefinition]],
        ...,
    ],
) -> None:
    """Every relation in the committed registry must point at real source/target rows.

    The body now reads as a flat fold over the (modelo, revision,
    relation) cases; per-case logic is in :func:`_relation_consistency_errors`
    and its three concern-specific helpers
    (:func:`_target_binding_errors`,
    :func:`_source_revision_consistency_errors`,
    :func:`_offset_derived_period_errors`). When the assertion fails
    the message lists every offending triple at once so the developer
    can fix the registry in a single edit rather than chasing one
    triple per test-run cycle.
    """
    errors: list[str] = []
    for modelo, revision, relation, by_id in _registry_relation_cases:
        errors.extend(_relation_consistency_errors(modelo, revision, relation, by_id))
    assert not errors, "registry relation-consistency offences:\n  " + "\n  ".join(errors)


def test_previous_filing_bindings_reference_existing_source_modelo_outputs_and_periods() -> None:
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    by_id = {modelo.id: modelo for modelo in modelos}

    errors: list[str] = []
    for modelo, revision, binding in _previous_filing_bindings(modelos):
        source_reference = previous_filing_source_reference(binding)
        source_modelo_id = source_reference.source_modelo

        source_modelo = by_id.get(source_modelo_id)
        if source_modelo is None:
            errors.append(f"{modelo.id}/{revision.id}/{binding.id}: unknown source modelo {source_modelo_id}")
            continue

        source_periods = source_reference.required_periods
        matching_revisions = tuple(
            source_revision
            for source_revision in source_modelo.revisions.values()
            if not source_periods or set(source_periods).issubset(set(source_revision.period_selector.periods))
        )
        if not matching_revisions:
            errors.append(
                f"{modelo.id}/{revision.id}/{binding.id}: no {source_modelo.id} revision accepts "
                f"source periods {source_periods}",
            )
            continue

        source_casilla_ids = source_reference.source_casilla_ids
        if not source_casilla_ids:
            continue

        for source_revision in matching_revisions:
            revision_outputs = {casilla.id for casilla in source_revision.casillas}
            for source_casilla_id in source_casilla_ids:
                if source_casilla_id in revision_outputs:
                    continue
                errors.append(
                    f"{modelo.id}/{revision.id}/{binding.id}: source casilla id {source_casilla_id} "
                    f"not defined by period-compatible {source_modelo.id}/{source_revision.id}",
                )

    assert not errors


def _relations(
    modelos: Iterable[ModeloDefinition],
) -> Iterable[tuple[ModeloDefinition, ModeloRevision, RelationDefinition]]:
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for relation in revision.relations:
                yield modelo, revision, relation


def _previous_filing_bindings(
    modelos: Iterable[ModeloDefinition],
) -> Iterable[tuple[ModeloDefinition, ModeloRevision, DataBindingDefinition]]:
    for modelo in modelos:
        for revision in modelo.revisions.values():
            for binding in revision.bindings:
                if binding.source == "previous_filing":
                    yield modelo, revision, binding


def _matching_source_revisions(
    source_modelo: ModeloDefinition,
    relation: RelationDefinition,
) -> Iterable[ModeloRevision]:
    source_revisions, selector_failures = select_relation_source_revisions(
        source_modelo,
        relation.source_revision_selector,
    )
    assert not selector_failures, relation.id
    return source_revisions
