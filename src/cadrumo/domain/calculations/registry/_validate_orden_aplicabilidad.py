"""The D3 ``orden_aplicabilidad`` gate for a :class:`ModeloRevision`.

D3 / Ruling 4 (period-revision-resolution ADR)
-----------------------------------------------
Every revision's ``orden_aplicabilidad`` field declares the legal-catalogue
:class:`~aeat.domain.calculations.registry._schema.LegalReference` id(s) of
the ordenes ministeriales that approve or amend the modelo form for this
revision's applicability window.  The gate is strict:

- Every revision MUST declare at least one entry; missing entries are a hard
  failure.
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

from ._schema import LegalReference, ModeloRevision


def validate_orden_aplicabilidad(
    scope: str,
    modelo_id: str,
    revision: ModeloRevision,
    legal_catalogue: Mapping[str, LegalReference],
) -> list[str]:
    """Validate the ``orden_aplicabilidad`` gate for one revision.

    Returned failures MUST block registry load: missing applicability Ordenes,
    dangling entries, corpus-less entries, and entries absent from
    ``legal_refs`` are all current-data defects.

    S24 connective gate (Ruling 5 boundary):
        For open-ended ``*-y-siguientes`` revisions (``valid_to is None`` and
        ``period_selector.year_from`` is set) the ``orden_aplicabilidad`` MUST
        be non-empty — the open-ended applicability claim MUST be BOE-anchored.

    Args:
        scope: Diagnostic scope string prefixed to each message.
        modelo_id: The modelo identifier.
        revision: The :class:`ModeloRevision` to validate.
        legal_catalogue: The loaded legal-reference catalogue mapping.

    Returns:
        A list of load-blocking failures.
    """
    hard: list[str] = []

    if not revision.orden_aplicabilidad:
        hard.append(
            f"{scope}: revision {revision.id!r} (valid_from {revision.valid_from.isoformat()}) "
            f"MUST declare orden_aplicabilidad citing the orden ministerial that approves "
            f"modelo {modelo_id} for this applicability window; see "
            f"registry-calculation-legal-grounding rule and D3 of the "
            f"period-revision-resolution ADR",
        )
        return hard

    # Validate each declared entry.
    legal_refs_set = set(revision.legal_refs)
    for ref_id in revision.orden_aplicabilidad:
        # (i) Must resolve in the legal catalogue.
        if ref_id not in legal_catalogue:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"does not resolve in the legal catalogue; add the full LegalReference "
                f"entry to a legal/*.toml file (registry-calculation-legal-grounding rule)",
            )
            continue  # Cannot check corpus_ref on an absent entry.

        # (ii) Must carry a corpus_ref (already validated by LegalReference schema,
        # but we surface a more helpful revision-level message if it's missing).
        ref = legal_catalogue[ref_id]
        if not ref.corpus_ref:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"exists in the catalogue but has no corpus_ref; add a corpus_ref pointing "
                f"to real BOE/AEAT text (registry-calculation-legal-grounding rule)",
            )

        # (iii) Must also appear in legal_refs so snapshot ref-collection carries it.
        if ref_id not in legal_refs_set:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"is not present in the revision's legal_refs; add it to legal_refs so "
                f"snapshot ref-collection carries the orden (D3, period-revision-resolution ADR)",
            )

    return hard


def orden_aplicabilidad_hard_failures(
    scope: str,
    modelo_id: str,
    revision: ModeloRevision,
    legal_catalogue: Mapping[str, LegalReference],
) -> list[str]:
    """Return load-blocking failures of the ``orden_aplicabilidad`` gate.

    Args:
        scope: Diagnostic scope string prefixed to each message.
        modelo_id: The modelo identifier.
        revision: The :class:`ModeloRevision` to validate.
        legal_catalogue: The loaded
            :class:`~aeat.domain.calculations.registry.LegalReference`
            catalogue mapping.

    Returns:
        A list of load-blocking failures.
    """
    return validate_orden_aplicabilidad(scope, modelo_id, revision, legal_catalogue)
