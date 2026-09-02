"""Single shared revision-carry gate.

Used by :mod:`~._binding_prefill`, :mod:`~._cross_period_clean_state`, and
:mod:`~._relation_prefill`: every cross-period or cross-year carry read shares
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

from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.ids import RevisionId


@dataclass(frozen=True, slots=True)
class RevisionCarryOutcome:
    """Law-determined result of re-confirming one persisted revision stamp."""

    refused: bool
    selected_revision_id: RevisionId | None
    detail: str | None


def revision_carry_outcome(
    stamped_revision_id: RevisionId,
    *,
    source_modelo: str,
    source_filing_year: int,
    source_period: str,
) -> RevisionCarryOutcome:
    """Return the single law-determined decision for a carried revision stamp.

    Resolves through the process-wide validated registry authority already
    used by modelo application services. Reusing that authority preserves the
    law-determined inspection contract without re-discovering and recompiling
    the entire authoring tree once per carried observation.

    - Indeterminate (source context fails to resolve) → carry refused. Current
      observations must be re-confirmable against the law-determined revision;
      there is no legacy advisory bridge.
    - Divergent stamp → carry refused (caller drops the
      observation or raises ``REGISTRY_REVISION_DIVERGENCE``).
    - Matching stamp → clean carry.

    Args:
        stamped_revision_id: Required revision persisted with the source filing.
        source_modelo: The carried observation's source modelo id.
        source_filing_year: The source filing year.
        source_period: The source period as the bare registry token
            (``"1T"``, ``"0A"``, …).

    Returns:
        A typed outcome containing the selected revision when resolution succeeds,
        plus the refusal reason when the stamp diverges or cannot be re-confirmed.
    """
    try:
        inspection = bundled_authority().inspect_revision(
            source_modelo,
            filing_year=source_filing_year,
            period=source_period,
        )
    except Exception as exc:
        return RevisionCarryOutcome(
            refused=True,
            selected_revision_id=None,
            detail=f"revision selection failed: {type(exc).__name__}",
        )
    selected_revision_id = inspection.revision_id
    if stamped_revision_id != selected_revision_id:
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
