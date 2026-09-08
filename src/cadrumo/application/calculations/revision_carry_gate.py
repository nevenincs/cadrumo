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

from ...domain.calculations.registry.authority import ValidatedRegistryAuthority, bundled_authority
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
) -> RevisionCarryOutcome:
    """Return the single law-determined decision for a carried revision stamp.

    Resolves through the supplied validated registry authority, or the
    process-wide bundled authority used by modelo application services when no
    explicit authority is in scope. Both routes retain this one comparison gate.

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
            explicit registry root; defaults to the bundled authority.

    Returns:
        A typed outcome containing the selected revision when resolution succeeds,
        plus the refusal reason when the stamp diverges or cannot be re-confirmed.
    """
    try:
        inspection = (authority or bundled_authority()).inspect_revision(
            str(snapshot_ref.modelo),
            filing_year=int(snapshot_ref.modelo_year),
            period=str(snapshot_ref.period),
        )
    except Exception as exc:
        return RevisionCarryOutcome(
            refused=True,
            selected_revision_id=None,
            detail=f"revision selection failed: {type(exc).__name__}",
        )
    selected_revision_id = inspection.revision_id
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
