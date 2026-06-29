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
(:meth:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority.snapshot`,
which delegates to law-determined revision selection) before trusting the value.

This module is the single implementation of that gate. Before this extraction
the same ``(diverges, advisory)`` decision was open-coded in three carry sites
with subtly duplicated try/except handling; ``carried-observations-stamp-their-
revision`` and ``revision-resolution-is-law-determined`` require one
law-determined re-confirmation, not three parallel copies that can drift.

See Also:
    :func:`~aeat.application.calculations._binding_prefill.resolve_bindings_from_local_store`
        Previous-filing binding reader that drops divergent carries and surfaces
        unstamped advisories.
    :func:`~aeat.application.calculations._relation_prefill.resolve_relations_from_local_store`
        Relation-prefill reader that applies the same revision-stamp gate.
    :func:`~aeat.application.calculations._cross_period_clean_state.evaluate_cross_period_clean_state`
        Filing-grade dependency proof that maps the shared outcome to blockers
        and advisories.
"""

from __future__ import annotations

from ...core.resources import resources


def revision_carry_outcome(
    stamped_revision_id: str | None,
    *,
    source_modelo: str,
    source_filing_year: int,
    source_period: str,
) -> tuple[bool, bool]:
    """Return ``(diverges, advisory)`` for a carried observation's revision stamp.

    Uses
    :meth:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority.snapshot`
    to resolve the current law-determined revision for the source context.

    ADR 2026-06-10-period-revision-resolution-adr, Ruling 3 / R2:

    - Missing stamp (unstamped record) → ``(False, True)``: carry proceeds, advisory set.
    - Indeterminate (source context fails to resolve) → ``(False, True)``: carry
      proceeds, but the stamp could not be re-confirmed so the advisory MUST be set
      rather than carrying silently clean.
    - Divergent stamp → ``(True, False)``: carry refused (caller drops the
      observation or raises ``REGISTRY_REVISION_DIVERGENCE``).
    - Matching stamp → ``(False, False)``: clean carry, no advisory.

    Args:
        stamped_revision_id: The revision the source filing was stamped with, or
            ``None`` for a record that carries no stamp.
        source_modelo: The carried observation's source modelo id.
        source_filing_year: The source filing year.
        source_period: The source period as the bare registry token
            (``"1T"``, ``"0A"``, …).

    Returns:
        A ``(diverges, advisory)`` pair. ``diverges`` is ``True`` only when a
        present stamp disagrees with the law-determined revision; ``advisory`` is
        ``True`` when the stamp is absent or could not be re-confirmed.
    """
    if stamped_revision_id is None:
        return False, True
    try:
        snapshot = resources().modelos.authority.snapshot(
            source_modelo,
            filing_year=source_filing_year,
            period=source_period,
        )
    except Exception:
        # Indeterminate: the source context will not resolve, so the stamp cannot
        # be re-confirmed. Surface the advisory rather than silently carrying a
        # clean, unverifiable stamp.
        return False, True
    return stamped_revision_id != snapshot.revision.id, False


__all__ = ["revision_carry_outcome"]
