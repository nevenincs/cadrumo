from __future__ import annotations

from collections.abc import Iterable, Mapping

import pytest

from .....core.resources import bundled_path
from .. import load_registry_tree
from .._schema import DataBindingDefinition, ModeloDefinition, ModeloRevision, RelationDefinition

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
    source_outputs = {casilla.id for casilla in source_revision.casillas}
    if relation.source_output not in source_outputs:
        errors.append(
            f"{modelo.id}/{revision.id}/{relation.id}: source output {relation.source_output} "
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
        source_modelo_id = binding.selector.get("source_modelo")
        if not isinstance(source_modelo_id, str):
            continue

        source_modelo = by_id.get(source_modelo_id)
        if source_modelo is None:
            errors.append(f"{modelo.id}/{revision.id}/{binding.id}: unknown source modelo {source_modelo_id}")
            continue

        source_periods = _binding_source_periods(binding)
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

        source_outputs = _binding_source_outputs(binding)
        if not source_outputs:
            continue

        source_outputs_by_revision = {
            source_revision.id: {casilla.id for casilla in source_revision.casillas}
            for source_revision in matching_revisions
        }
        for source_output in source_outputs:
            if not any(source_output in outputs for outputs in source_outputs_by_revision.values()):
                errors.append(
                    f"{modelo.id}/{revision.id}/{binding.id}: source output {source_output} "
                    f"not defined by any period-compatible {source_modelo.id} revision",
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


def _binding_source_periods(binding: DataBindingDefinition) -> tuple[str, ...]:
    source_periods = binding.selector.get("source_periods")
    if isinstance(source_periods, tuple):
        return source_periods
    period = binding.selector.get("period")
    if isinstance(period, str):
        return (period,)
    return ()


def _binding_source_outputs(binding: DataBindingDefinition) -> tuple[str, ...]:
    source_casillas = binding.selector.get("source_casillas")
    if isinstance(source_casillas, tuple):
        return source_casillas
    source_output = binding.selector.get("source_output")
    if isinstance(source_output, str):
        return (source_output,)
    return ()


def _matching_source_revisions(
    source_modelo: ModeloDefinition,
    relation: RelationDefinition,
) -> Iterable[ModeloRevision]:
    year = relation.source_revision_selector.get("year")
    year_from = relation.source_revision_selector.get("year_from")
    year_to = relation.source_revision_selector.get("year_to")
    for revision in source_modelo.revisions.values():
        if _revision_covers_relation_year_window(
            revision,
            year=year,
            year_from=year_from,
            year_to=year_to,
        ):
            yield revision


def _revision_covers_relation_year_window(
    revision: ModeloRevision,
    *,
    year: object,
    year_from: object,
    year_to: object,
) -> bool:
    """Return True when ``revision``'s period selector overlaps the relation's source-year window.

    Three independent predicates, each gating one selector field:

    * Single ``year``: revision must contain that year (closed
      interval against year_from / year_to).
    * ``year_from`` floor: revision's upper bound must reach at
      least year_from.
    * ``year_to`` ceiling: revision's lower bound must not exceed
      year_to.

    Non-int selector values short-circuit to "no constraint" so
    the revision passes through.
    """
    selector = revision.period_selector
    if isinstance(year, int):
        if selector.year_from is not None and selector.year_from > year:
            return False
        if selector.year_to is not None and selector.year_to < year:
            return False
    if isinstance(year_from, int) and selector.year_to is not None and selector.year_to < year_from:
        return False
    return not (isinstance(year_to, int) and selector.year_from is not None and selector.year_from > year_to)
