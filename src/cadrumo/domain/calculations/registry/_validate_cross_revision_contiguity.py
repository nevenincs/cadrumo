"""Continuity-chain contiguity policy for registry casillas.

A `continuidad_id` asserts one legal concept running continuously across the
:class:`ModeloRevision` entries that carry it. This module owns the policy that refuses a chain which
is present, absent, then present again: such a chain asserts continuity across a
period in which the modelo itself declares the concept does not exist, and no
legal grounding can support that claim.

The declared resolution is two chains -- the later concept takes a new grounded
`continuidad_id`. `retired` therefore ends a chain permanently, and this policy
is what makes that contract enforceable rather than advisory prose: a
retired-then-resurrected chain is one shape of the non-contiguous chain rejected
here, and the retirement policy in
:mod:`cadrumo.domain.calculations.registry._validate_cross_revision` only proves
the chain left, never that it stayed gone.

The evolution-kind and surface-scoped strictness rules below were later
amended to tolerate gapped chains.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import pairwise

from ._cross_revision_divergence import ordered_revisions as _ordered_revisions
from ._cross_revision_divergence import revisions_overlap
from .schema import ModeloDefinition, ModeloRevision

__all__ = ("strict_continuity_chain_contiguity_failures",)


def _validate_strict_continuity_chain_contiguity(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Reject a continuity chain that skips a revision and resumes later.

    Args:
        modelo: The :class:`ModeloDefinition` whose declared chains are read.

    Returns:
        One failure string per gap found, empty when every chain is contiguous.
    """
    ordered_revisions = _ordered_revisions(modelo)
    if len(ordered_revisions) < 3:
        return ()
    positions = {revision.id: index for index, revision in enumerate(ordered_revisions)}

    chain_positions: dict[str, set[int]] = defaultdict(set)
    for revision in ordered_revisions:
        for casilla in revision.casillas:
            if casilla.continuidad_id is not None:
                chain_positions[casilla.continuidad_id].add(positions[revision.id])

    failures: list[str] = []
    for continuidad_id in sorted(chain_positions):
        for left, right in pairwise(sorted(chain_positions[continuidad_id])):
            skipped = _skipped_revisions(ordered_revisions, left, right)
            if not skipped:
                continue
            if not any(revision.continuidad_validation == "strict" for revision in ordered_revisions[left : right + 1]):
                continue
            failures.append(
                _format_gapped_chain_failure(
                    modelo.id,
                    continuidad_id,
                    ordered_revisions[left],
                    ordered_revisions[right],
                    skipped,
                ),
            )
    return tuple(failures)


def _skipped_revisions(
    ordered_revisions: tuple[ModeloRevision, ...],
    left: int,
    right: int,
) -> tuple[ModeloRevision, ...]:
    """Return the revisions between two chain occurrences that are a real gap.

    Variant schemas sharing a validity window are alternative shapes of one
    period, not a temporal gap, so an overlapping revision never counts as a
    skipped one.
    """
    return tuple(
        revision
        for revision in ordered_revisions[left + 1 : right]
        if not revisions_overlap(revision, ordered_revisions[left])
        and not revisions_overlap(revision, ordered_revisions[right])
    )


def _format_gapped_chain_failure(
    modelo_id: str,
    continuidad_id: str,
    left_revision: ModeloRevision,
    right_revision: ModeloRevision,
    skipped: tuple[ModeloRevision, ...],
) -> str:
    return (
        "strict continuity chain is not contiguous: "
        f"modelo {modelo_id} continuidad_id {continuidad_id!r} "
        f"is declared in {left_revision.id!r} and {right_revision.id!r} "
        f"but absent from {tuple(revision.id for revision in skipped)!r}; "
        "a chain cannot resume after the concept leaves the modelo - "
        "declare the later concept under a new grounded continuidad_id"
    )


strict_continuity_chain_contiguity_failures = _validate_strict_continuity_chain_contiguity
