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
    :func:`~application.calculations._relation_prefill.resolve_relations_from_local_store`
        Relation-prefill reader that applies the same revision-stamp gate.
    :func:`~application.calculations._cross_period_clean_state.evaluate_cross_period_clean_state`
        Filing-grade dependency proof that maps the shared outcome to blockers.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...core.resources import bundled_path
from ...domain.calculations.registry import RevisionId, load_registry_tree, select_revision


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

    Uses
    :func:`~domain.calculations.registry.select_revision`
    to resolve the current law-determined revision for the source context.
    Deliberately does NOT go through
    :class:`~domain.calculations.registry.ValidatedRegistryAuthority` at all
    (neither ``.snapshot()`` nor ``.inspect_revision()``): obtaining that
    authority object at all now means ``.load()``'s own unconditional
    ``validate_registry()`` call, which validates the ENTIRE tree -- so a gap
    anywhere else in the registry, unrelated to this carry, would refuse it.
    ``load_registry_tree`` compiles the tree without validating it, and
    ``select_revision`` is a pure function with no validation of its own.

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
        modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
        modelo = next(candidate for candidate in modelos if candidate.id == source_modelo)
        revision = select_revision(
            modelo,
            filing_year=source_filing_year,
            period=source_period,
        )
    except Exception as exc:
        return RevisionCarryOutcome(
            refused=True,
            selected_revision_id=None,
            detail=f"revision selection failed: {type(exc).__name__}",
        )
    selected_revision_id = revision.id
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
