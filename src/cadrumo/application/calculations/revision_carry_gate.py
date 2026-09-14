"""Single shared revision-carry gate.

Used by :mod:`~.binding_prefill`, :mod:`~.cross_period_clean_state`, and
:mod:`~.relation_prefill`: every cross-period or cross-year carry read shares
this gate.

The carry path is the one place a revision error compounds across years: a
prior filed under the wrong revision injects that revision's norms into every
later filing that folds it in. The carry read therefore re-confirms each
carried observation's ``stamped_revision_id`` against the law-determined
revision for its source context
(:meth:`~domain.calculations.registry.ValidatedRegistryAuthority.inspect_revision`,
which resolves the same law-determined revision selection without demanding
filing-grade admission -- this gate answers "which revision does the law
select", never "may this be filed") before trusting the value.

This module is the single implementation of that gate: one law-determined
re-confirmation, not three parallel copies that can drift across the carry
sites that use it.

See Also:
    :func:`~application.calculations._binding_prefill.resolve_bindings_from_local_store`
        Previous-filing binding reader that drops unreconfirmable carries.
    :func:`~application.calculations.relation_prefill.resolve_relations_from_local_store`
        Relation-prefill reader that applies the same revision-stamp gate.
    :func:`~application.calculations.cross_period_clean_state.evaluate_cross_period_clean_state`
        Filing-grade dependency proof that maps the shared outcome to blockers.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    ValidatedRegistryAuthority,
    bundled_indexed_authority,
)
from ...domain.calculations.registry.ids import RevisionId
from ...domain.calculations.registry.schema_references import RegistrySnapshotRef


@dataclass(frozen=True, slots=True)
class RevisionCarryOutcome:
    """Law-determined result of re-confirming one persisted revision stamp."""

    refused: bool
    selected_revision_id: RevisionId | None
    detail: str | None


def revision_carry_outcome(
    snapshot_ref: RegistrySnapshotRef,
    *,
    authority: ValidatedRegistryAuthority | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> RevisionCarryOutcome:
    """Return the single law-determined decision for a carried revision stamp.

    Resolves through the supplied pinned operation or validated registry
    authority. When neither is supplied, one indexed operation is opened at
    this composition boundary; no eager authority graph is consulted.

    - Indeterminate (source context fails to resolve) → carry refused. Current
      observations must be re-confirmable against the law-determined revision;
      there is no legacy advisory bridge.
    - Divergent stamp → carry refused (caller drops the
      observation or raises ``REGISTRY_REVISION_DIVERGENCE``).
    - Matching stamp → clean carry.

    Args:
        snapshot_ref: Required complete registry coordinate persisted with the
            source value.
        authority: Existing validated authority for callers evaluating an
            explicit registry root.
        operation: Existing generation-pinned indexed operation. It takes
            precedence over ``authority`` when supplied.

    Returns:
        A typed outcome containing the selected revision when resolution succeeds,
        plus the refusal reason when the stamp diverges or cannot be re-confirmed.
    """
    if operation is None and authority is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return revision_carry_outcome(snapshot_ref, operation=indexed_operation)
    try:
        if operation is not None:
            selected_revision_id = str(
                operation.revision_for_context(
                    str(snapshot_ref.modelo),
                    filing_year=int(snapshot_ref.modelo_year),
                    period=str(snapshot_ref.period),
                ).id
            )
        elif authority is not None:
            inspection = authority.inspect_revision(
                str(snapshot_ref.modelo),
                filing_year=int(snapshot_ref.modelo_year),
                period=str(snapshot_ref.period),
            )
            selected_revision_id = inspection.revision_id
        else:
            raise RuntimeError("revision carry selection requires an authority operation")
    except Exception as exc:
        return RevisionCarryOutcome(
            refused=True,
            selected_revision_id=None,
            detail=f"revision selection failed: {type(exc).__name__}",
        )
    if snapshot_ref.revision_id != selected_revision_id:
        return RevisionCarryOutcome(
            refused=True,
            selected_revision_id=selected_revision_id,
            detail="stamped revision differs from the law-determined revision",
        )
    return RevisionCarryOutcome(
        refused=False,
        selected_revision_id=selected_revision_id,
        detail=None,
    )


__all__ = ["RevisionCarryOutcome", "revision_carry_outcome"]
