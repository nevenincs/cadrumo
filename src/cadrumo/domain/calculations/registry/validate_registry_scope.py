"""Registry-wide validation gates.

Applies corpus-wide invariants across all :class:`ModeloDefinition` instances,
including duplicate-id checks, relation closure, and semantic-role consistency.
"""

from __future__ import annotations

from collections.abc import Iterable

from . import validate_cross_revision
from .schema import ModeloDefinition
from .validate_cross_revision import (
    cross_revision_casilla_consistency_failures as _validate_cross_revision_casilla_consistency,
)
from .validate_cross_revision import (
    strict_cross_revision_casilla_continuity_failures as _validate_strict_cross_revision_casilla_continuity,
)
from ._validate_label_artifacts import validate_no_label_artifacts
from ._validate_previous_filing_year_coverage import validate_previous_filing_source_year_coverage
from ._validate_relation_sources import (
    validate_previous_filing_binding_closure,
    validate_relation_closure,
    validate_slot_source_hygiene,
)
from .validate_revision_identity import duplicates as _duplicates
from ._validate_semantic_role_required import required_role_declaration_failures as _validate_required_role_declarations
from ._validate_semantic_roles import (
    semantic_role_cardinality_failures as _validate_semantic_role_cardinality,
)
from ._validate_semantic_roles import (
    semantic_role_consistency_failures as _validate_semantic_role_consistency,
)
from ._validate_semantic_roles import (
    semantic_role_typo_twin_failures as _validate_semantic_role_typo_twins,
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
        failures.extend(_validate_dependency_classification_source_modelos(modelo_tuple, modelos_by_id))
        failures.extend(validate_relation_closure(modelo_tuple, modelos_by_id))
        failures.extend(validate_previous_filing_binding_closure(modelo_tuple, modelos_by_id))
        failures.extend(validate_previous_filing_source_year_coverage(modelo_tuple, modelos_by_id))
        failures.extend(validate_slot_source_hygiene(modelo_tuple, modelos_by_id))

    failures.extend(_validate_binding_selector_shapes(modelo_tuple))
    failures.extend(_validate_semantic_role_consistency(modelo_tuple))
    failures.extend(_validate_semantic_role_cardinality(modelo_tuple))
    failures.extend(_validate_required_role_declarations(modelo_tuple))
    failures.extend(_validate_cross_revision_casilla_consistency(modelo_tuple))
    failures.extend(_validate_cross_revision.declared_cross_revision_continuity_semantic_linkage_failures(modelo_tuple))
    # This is the surface-scoped strict continuity gate; it complements,
    # but does not replace, the overlap-aware repeated-id hard gate above.
    failures.extend(_validate_strict_cross_revision_casilla_continuity(modelo_tuple))
    failures.extend(validate_no_label_artifacts(modelo_tuple))
    if _tree_can_answer_role_singleton_questions(modelo_tuple):
        failures.extend(_validate_semantic_role_typo_twins(modelo_tuple))
    return tuple(failures)


def _tree_can_answer_role_singleton_questions(modelos: tuple[ModeloDefinition, ...]) -> bool:
    """Return whether this tree carries enough corpus to judge a role singleton.

    The typo-twin check asks whether a ``semantic_role`` appears exactly ONCE
    across the tree and has a near-duplicate twin, which reads as either a typo
    or missing declarations on sibling casillas. That question is answerable
    only over a tree that actually contains the siblings.

    A tree of exactly one modelo carrying exactly one revision cannot contain
    them: every role in it is a singleton BY CONSTRUCTION, so the check would
    measure the pruning rather than the data. That shape is not hypothetical --
    it is precisely what generated-export-tree validation mandates, where the
    candidate registry must hold one modelo and one revision and nothing else.
    Running there refused every role in the tree and would have done so for any
    modelo, on a defect that exists only because the siblings were removed.

    Deliberately narrow: one modelo with SEVERAL revisions can answer the
    question, because a role shared across its own revisions is no longer a
    singleton. Only the one-by-one case abstains, and abstaining is the honest
    answer rather than a suppression -- full-tree validation still runs it.
    """
    if len(modelos) != 1:
        return True
    return len(modelos[0].revisions) != 1


def _validate_dependency_classification_source_modelos(
    modelos: Iterable[ModeloDefinition],
    modelos_by_id: dict[str, ModeloDefinition],
) -> tuple[str, ...]:
    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            for classification in revision.dependency_classifications:
                if classification.source_modelo not in modelos_by_id:
                    failures.append(
                        f"{prefix}: dependency classification {classification.id!r} "
                        f"references unknown source modelo {classification.source_modelo!r}",
                    )
    return tuple(failures)


def _validate_binding_selector_shapes(modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
    """Validate binding selector discriminators at registry-tree scope."""
    from .bindings import validate_binding_selector_shape

    failures: list[str] = []
    for modelo in modelos:
        for revision in modelo.revisions.values():
            prefix = f"modelo {modelo.id} revision {revision.id}"
            for binding in revision.bindings:
                failures.extend(f"{prefix}: {fail}" for fail in validate_binding_selector_shape(binding))
    return tuple(failures)
