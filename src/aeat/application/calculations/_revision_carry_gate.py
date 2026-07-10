"""Single shared ADR-R2 revision-carry gate.

Used by :mod:`~._binding_prefill`, :mod:`~._cross_period_clean_state`, and
:mod:`~._relation_prefill`: every cross-period or cross-year carry read shares
this gate.

ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2 decides the
carry path is the one place a revision error compounds across years: a prior
filed under the wrong revision injects that revision's norms into every later
filing that folds it in. The carry read therefore re-confirms each carried
observation's ``stamped_revision_id`` against the law-determined revision
for its source context
(:meth:`~domain.calculations.registry.ValidatedRegistryAuthority.snapshot`,
which delegates to law-determined revision selection) before trusting the value.

This module is the single implementation of that gate. Before this extraction
the same revision-stamp refusal decision was open-coded in three carry sites
with subtly duplicated try/except handling; ``carried-observations-stamp-their-
revision`` and ``revision-resolution-is-law-determined`` require one
law-determined re-confirmation, not three parallel copies that can drift.

See Also:
    :func:`~application.calculations._binding_prefill.resolve_bindings_from_local_store`
        Previous-filing binding reader that drops unreconfirmable carries.
    :func:`~application.calculations._relation_prefill.resolve_relations_from_local_store`
        Relation-prefill reader that applies the same revision-stamp gate.
    :func:`~application.calculations._cross_period_clean_state.evaluate_cross_period_clean_state`
        Filing-grade dependency proof that maps the shared outcome to blockers.
"""

from __future__ import annotations

from ...core.resources import resources


def revision_carry_outcome(
    stamped_revision_id: str | None,
    *,
    source_modelo: str,
    source_filing_year: int,
    source_period: str,
) -> bool:
    """Return whether a carried observation's revision stamp must be refused.

    Uses
    :meth:`~domain.calculations.registry.ValidatedRegistryAuthority.snapshot`
    to resolve the current law-determined revision for the source context.

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2:

    - Indeterminate (source context fails to resolve) → carry refused. Current
      observations must be re-confirmable against the law-determined revision;
      there is no legacy advisory bridge.
    - Divergent stamp → carry refused (caller drops the
      observation or raises ``REGISTRY_REVISION_DIVERGENCE``).
    - Matching stamp → clean carry.

    Args:
        stamped_revision_id: The revision the source filing was stamped with.
            ``None`` represents a legacy missing stamp and is refused by this
            shared gate; ADR-specific readers that permit a missing-stamp
            advisory must handle that case before calling this function.
        source_modelo: The carried observation's source modelo id.
        source_filing_year: The source filing year.
        source_period: The source period as the bare registry token
            (``"1T"``, ``"0A"``, …).

    Returns:
        ``True`` when the stamp disagrees with, or cannot be re-confirmed
        against, the law-determined revision.
    """
    try:
        snapshot = resources().modelos.authority.snapshot(
            source_modelo,
            filing_year=source_filing_year,
            period=source_period,
        )
    except Exception:
        # Indeterminate source context: fail closed. A carry that cannot be
        # re-confirmed against the law-determined revision is not current data.
        return True
    return stamped_revision_id != snapshot.revision.id


__all__ = ["revision_carry_outcome"]
