"""Registry-wide validation gates.

Applies corpus-wide invariants across all :class:`ModeloDefinition` instances,
including duplicate-id checks, relation closure, and semantic-role consistency.
"""

from __future__ import annotations

from collections.abc import Iterable

from ._schema import ModeloDefinition
from ._validate_cross_revision import (
    _validate_cross_revision_casilla_consistency,
    _validate_strict_cross_revision_casilla_continuity,
)
from ._validate_label_artifacts import validate_no_label_artifacts
from ._validate_relation_sources import (
    validate_previous_filing_binding_closure,
    validate_relation_closure,
    validate_slot_source_hygiene,
)
from ._validate_revision_identity import _duplicates
from ._validate_semantic_role_required import _validate_required_role_declarations
from ._validate_semantic_roles import (
    _validate_semantic_role_cardinality,
    _validate_semantic_role_consistency,
    _validate_semantic_role_typo_twins,
)


def validate_registry_scope(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Validate cross-model and corpus-wide registry invariants.

    Args:
        modelos: Iterable of :class:`ModeloDefinition` entries to validate.
    """
    modelo_tuple = tuple(modelos)
    failures: list[str] = []
    modelo_ids = [modelo.id for modelo in modelo_tuple]
    for duplicate in sorted(_duplicates(modelo_ids)):
        failures.append(f"registry: duplicate modelo id {duplicate!r}")

    modelos_by_id = {modelo.id: modelo for modelo in modelo_tuple}
    if len(modelos_by_id) == len(modelo_tuple):
        failures.extend(validate_relation_closure(modelo_tuple, modelos_by_id))
        failures.extend(validate_previous_filing_binding_closure(modelo_tuple, modelos_by_id))
        failures.extend(validate_slot_source_hygiene(modelo_tuple, modelos_by_id))

    failures.extend(_validate_binding_selector_shapes(modelo_tuple))
    failures.extend(_validate_semantic_role_consistency(modelo_tuple))
    failures.extend(_validate_semantic_role_cardinality(modelo_tuple))
    failures.extend(_validate_required_role_declarations(modelo_tuple))
    failures.extend(_validate_cross_revision_casilla_consistency(modelo_tuple))
    # This is the surface-scoped strict continuity gate; it complements,
    # but does not replace, the overlap-aware repeated-id hard gate above.
    failures.extend(_validate_strict_cross_revision_casilla_continuity(modelo_tuple))
    failures.extend(validate_no_label_artifacts(modelo_tuple))
    failures.extend(_validate_semantic_role_typo_twins(modelo_tuple))
    return tuple(failures)


def _validate_binding_selector_shapes(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Validate binding selector discriminators at registry-tree scope."""
    from ._bindings import validate_binding_selector_shape

    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            for binding in revision.bindings:
                failures.extend(f"{prefix}: {fail}" for fail in validate_binding_selector_shape(binding))
    return tuple(failures)
