"""The D3 ``orden_aplicabilidad`` ratchet gate for a :class:`ModeloRevision`.

D3 / Ruling 4 (period-revision-resolution ADR)
-----------------------------------------------
Every revision's ``orden_aplicabilidad`` field declares the legal-catalogue
:class:`~aeat.domain.calculations.registry._schema.LegalReference` id(s) of
the ordenes ministeriales that approve or amend the modelo form for this
revision's applicability window.  The gate is a **ratchet**:

- A *new* revision (``valid_from`` on or after the ratchet date ``2026-06-10``)
  MUST declare at least one entry — missing entries are a hard failure.
- An *existing* revision (``valid_from`` before the ratchet date) MAY omit
  the field — missing entries produce a tracked follow-up failure that callers
  can surface as an advisory rather than a hard error.
- Every declared entry MUST resolve in the legal catalogue with a ``corpus_ref``
  (per ``registry-calculation-legal-grounding``).
- Every declared entry MUST also appear in (or be merged into) ``legal_refs``
  so existing snapshot ref-collection carries it.

S24 / Ruling 5 boundary (R3):
    For ``*-y-siguientes`` (open-ended) revisions the ``orden_aplicabilidad``
    MUST cite the orden establishing the open-ended applicability — the
    connective gate ensuring even the "y siguientes" claim is BOE-anchored.
    Per-year norm values *inside* the open-ended revision (rate brackets,
    thresholds) are the parameter-bracket layer's responsibility gated by
    :func:`~aeat.domain.calculations.registry._validate_revision_rules.validate_bracket_table_temporal_coverage`;
    a wrong-but-present bracket value is a legal-grounding defect, NOT a
    resolution defect.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from ._schema import LegalReference, ModeloRevision

# Ratchet date: revisions whose valid_from is on or after this date MUST
# declare orden_aplicabilidad.  Revisions before this date are accepted
# without it but tracked as follow-up items.
_ORDEN_APLICABILIDAD_RATCHET_DATE = date(2026, 6, 10)


def validate_orden_aplicabilidad(
    scope: str,
    modelo_id: str,
    revision: ModeloRevision,
    legal_catalogue: Mapping[str, LegalReference],
) -> tuple[list[str], list[str]]:
    """Validate the ``orden_aplicabilidad`` ratchet gate for one revision.

    Returns ``(hard_failures, follow_up_items)`` where:

    - ``hard_failures`` are errors that MUST block registry load (new revision
      missing the field, or a declared entry that fails catalogue / corpus_ref /
      legal_refs cross-checks).
    - ``follow_up_items`` are tracked deficits on existing revisions that are
      accepted but must shrink monotonically (unstamped pre-ratchet revisions).

    S24 connective gate (Ruling 5 boundary):
        For open-ended ``*-y-siguientes`` revisions (``valid_to is None`` and
        ``period_selector.year_from`` is set) the ``orden_aplicabilidad`` MUST
        be non-empty — the open-ended applicability claim MUST be BOE-anchored.
        A pre-ratchet open-ended revision without ``orden_aplicabilidad`` is a
        follow-up item, not a hard failure, to avoid breaking the existing
        corpus; a post-ratchet one is a hard failure.

    Args:
        scope: Diagnostic scope string prefixed to each message.
        modelo_id: The modelo identifier, used in advisory messages.
        revision: The :class:`ModeloRevision` to validate.
        legal_catalogue: The loaded legal-reference catalogue mapping.

    Returns:
        A ``(hard_failures, follow_up_items)`` tuple; both lists may be empty.
    """
    hard: list[str] = []
    follow_up: list[str] = []

    is_new_revision = revision.valid_from >= _ORDEN_APLICABILIDAD_RATCHET_DATE
    is_open_ended = revision.valid_to is None and revision.period_selector.year_from is not None

    if not revision.orden_aplicabilidad:
        # Missing field: hard failure for new revisions; follow-up for existing.
        if is_new_revision or is_open_ended:
            # Post-ratchet or open-ended: MUST declare.
            if is_new_revision:
                hard.append(
                    f"{scope}: revision {revision.id!r} (valid_from {revision.valid_from.isoformat()}) "
                    f"is a new revision (on or after ratchet date "
                    f"{_ORDEN_APLICABILIDAD_RATCHET_DATE.isoformat()}) and MUST declare "
                    f"orden_aplicabilidad citing the orden ministerial that approves this form; "
                    f"see registry-calculation-legal-grounding rule and D3 of the "
                    f"period-revision-resolution ADR"
                )
            else:
                # Pre-ratchet open-ended: follow-up so it burns down.
                follow_up.append(
                    f"{scope}: open-ended revision {revision.id!r} (valid_from "
                    f"{revision.valid_from.isoformat()}, valid_to open) has no "
                    f"orden_aplicabilidad — the open-ended applicability claim is not "
                    f"BOE-anchored; add the orden that establishes 'y siguientes' "
                    f"applicability (S24 connective gate, Ruling 5 boundary, "
                    f"period-revision-resolution ADR)"
                )
        else:
            # Pre-ratchet bounded: simple follow-up.
            follow_up.append(
                f"{scope}: revision {revision.id!r} (valid_from {revision.valid_from.isoformat()}) "
                f"has no orden_aplicabilidad — follow-up backfill required; cite the orden "
                f"ministerial that approves this form revision in the legal catalogue with a "
                f"corpus_ref (D3 backfill, period-revision-resolution ADR)"
            )
        # No entries to validate further.
        return hard, follow_up

    # Validate each declared entry.
    legal_refs_set = set(revision.legal_refs)
    for ref_id in revision.orden_aplicabilidad:
        # (i) Must resolve in the legal catalogue.
        if ref_id not in legal_catalogue:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"does not resolve in the legal catalogue; add the full LegalReference "
                f"entry to a legal/*.toml file (registry-calculation-legal-grounding rule)"
            )
            continue  # Cannot check corpus_ref on an absent entry.

        # (ii) Must carry a corpus_ref (already validated by LegalReference schema,
        # but we surface a more helpful revision-level message if it's missing).
        ref = legal_catalogue[ref_id]
        if not ref.corpus_ref:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"exists in the catalogue but has no corpus_ref; add a corpus_ref pointing "
                f"to real BOE/AEAT text (registry-calculation-legal-grounding rule)"
            )

        # (iii) Must also appear in legal_refs so snapshot ref-collection carries it.
        if ref_id not in legal_refs_set:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"is not present in the revision's legal_refs; add it to legal_refs so "
                f"snapshot ref-collection carries the orden (D3, period-revision-resolution ADR)"
            )

    return hard, follow_up


def orden_aplicabilidad_hard_failures(
    scope: str,
    modelo_id: str,
    revision: ModeloRevision,
    legal_catalogue: Mapping[str, LegalReference],
) -> list[str]:
    """Return only the load-blocking failures of the ``orden_aplicabilidad`` gate.

    The full :func:`validate_orden_aplicabilidad` returns a
    ``(hard_failures, follow_up_items)`` split.  The registry section validator
    enforces only the hard failures (new unstamped revisions, dangling /
    corpus-less entries, entries absent from ``legal_refs``); the follow-up items
    (pre-ratchet unstamped existing revisions) are intentionally not blocking so
    the corpus keeps loading while the backfill burns down monotonically.  The
    test suite asserts the full split via :func:`validate_orden_aplicabilidad`.
    The ``revision`` is the :class:`ModeloRevision` whose ``orden_aplicabilidad``
    entries are checked for load-blocking grounding failures.
    """
    hard, _follow_up = validate_orden_aplicabilidad(scope, modelo_id, revision, legal_catalogue)
    return hard
