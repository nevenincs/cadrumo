from __future__ import annotations

from collections.abc import Iterable

import pytest

from ....core.paths import PROJECT_ROOT
from . import load_registry_tree
from ._schema import DataBindingDefinition, ModeloDefinition, ModeloRevision, RelationDefinition

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def test_registry_relations_reference_existing_modelo_outputs_and_target_bindings() -> None:
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    by_id = {modelo.id: modelo for modelo in modelos}

    errors: list[str] = []
    for modelo, revision, relation in _relations(modelos):
        target_bindings = {binding.id for binding in revision.bindings}
        if relation.target_binding not in target_bindings:
            errors.append(f"{modelo.id}/{revision.id}/{relation.id}: unknown target binding {relation.target_binding}")

        source_modelo = by_id.get(relation.source_modelo)
        if source_modelo is None:
            errors.append(f"{modelo.id}/{revision.id}/{relation.id}: unknown source modelo {relation.source_modelo}")
            continue

        matching_revisions = tuple(_matching_source_revisions(source_modelo, relation))
        if not matching_revisions:
            errors.append(f"{modelo.id}/{revision.id}/{relation.id}: no source revision matches selector")
            continue

        for source_revision in matching_revisions:
            source_outputs = {casilla.id for casilla in source_revision.casillas}
            if relation.source_output not in source_outputs:
                errors.append(
                    f"{modelo.id}/{revision.id}/{relation.id}: source output {relation.source_output} "
                    f"not defined by {source_modelo.id}/{source_revision.id}"
                )

            revision_periods = set(source_revision.period_selector.periods)
            relation_periods = set(relation.source_periods)
            if relation_periods and not relation_periods.issubset(revision_periods):
                unknown_periods = sorted(relation_periods - revision_periods)
                errors.append(
                    f"{modelo.id}/{revision.id}/{relation.id}: source periods {unknown_periods} "
                    f"not accepted by {source_modelo.id}/{source_revision.id}"
                )

    assert not errors


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
                f"source periods {source_periods}"
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
                    f"not defined by any period-compatible {source_modelo.id} revision"
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
    return ()


def _matching_source_revisions(
    source_modelo: ModeloDefinition,
    relation: RelationDefinition,
) -> Iterable[ModeloRevision]:
    year = relation.source_revision_selector.get("year")
    year_from = relation.source_revision_selector.get("year_from")
    year_to = relation.source_revision_selector.get("year_to")

    for revision in source_modelo.revisions.values():
        selector = revision.period_selector
        if isinstance(year, int):
            if selector.year_from is not None and selector.year_from > year:
                continue
            if selector.year_to is not None and selector.year_to < year:
                continue
        if isinstance(year_from, int) and selector.year_to is not None and selector.year_to < year_from:
            continue
        if isinstance(year_to, int) and selector.year_from is not None and selector.year_from > year_to:
            continue
        yield revision
