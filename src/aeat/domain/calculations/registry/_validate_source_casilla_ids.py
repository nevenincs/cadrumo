"""Shared source-casilla-id helpers for cross-model validation.

Returns the canonical casilla ids a :class:`ModeloRevision` can expose to
cross-model relation validators.
"""

from __future__ import annotations

from ._casilla_membership import casilla_noncanonical_reference_targets, declared_casilla_ids
from ._ids import CasillaId
from ._schema import ModeloRevision


def revision_output_ids(revision: ModeloRevision) -> set[CasillaId]:
    outputs = set(declared_casilla_ids(revision))
    outputs.update(output for binding in revision.algorithm_bindings for output in binding.output_casilla_ids.values())
    return outputs


def source_casilla_id_reference_failure(
    revision: ModeloRevision,
    source_casilla_id: CasillaId,
    *,
    source_scope: str,
    missing_failure: str,
) -> str | None:
    """Return a closure failure for a source casilla reference, if invalid.

    Cross-revision source references consume only canonical ``casilla.id`` values.
    Display numbers, form numbers, and export refs are refused even when they map
    to exactly one source casilla; the diagnostic names the canonical candidate so
    the author fixes the registry source instead of treating the token as unknown.

    Args:
        revision: Source :class:`ModeloRevision` whose canonical outputs are
            available to relation or previous-filing closure.
        source_casilla_id: Candidate source casilla reference token to validate.
        source_scope: Human-readable scope prefix for the emitted failure.
        missing_failure: Failure message to reuse for a truly unknown source id.
    """
    if source_casilla_id in revision_output_ids(revision):
        return None
    noncanonical_targets = casilla_noncanonical_reference_targets(revision, source_casilla_id)
    if noncanonical_targets:
        rendered_targets = ", ".join(noncanonical_targets)
        if len(noncanonical_targets) > 1:
            return (
                f"{source_scope} source casilla id {source_casilla_id!r} is not a canonical casilla.id "
                f"and is ambiguous; candidate casilla.id values: {rendered_targets}"
            )
        return (
            f"{source_scope} source casilla id {source_casilla_id!r} is not a canonical casilla.id; "
            f"use canonical casilla.id {rendered_targets!r}"
        )
    return missing_failure
