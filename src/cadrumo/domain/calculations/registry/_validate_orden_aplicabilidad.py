"""The ``orden_aplicabilidad`` gate for a :class:`ModeloRevision`.

Every revision's ``orden_aplicabilidad`` field declares the legal-catalogue
:class:`~cadrumo.domain.calculations.registry.schema.LegalReference` id(s) of
the ordenes ministeriales that approve or amend the modelo form for this
revision's applicability window.  The gate is strict:

- Every revision MUST declare at least one entry; missing entries are a hard
  failure.
- Every declared entry MUST resolve in the legal catalogue with a ``corpus_ref``
  (per ``aeat-calculation-grounding``).
- Every declared entry MUST also appear in (or be merged into) ``legal_refs``
  so existing snapshot ref-collection carries it.

For ``*-y-siguientes`` (open-ended) revisions the ``orden_aplicabilidad``
MUST cite the orden establishing the open-ended applicability — the
connective gate ensuring even the "y siguientes" claim is BOE-anchored.
Per-year norm values *inside* the open-ended revision (rate brackets,
thresholds) are the parameter-bracket layer's responsibility gated by
:func:`~cadrumo.domain.calculations.registry.validate_revision_rules.validate_bracket_table_temporal_coverage`;
a wrong-but-present bracket value is a legal-grounding defect, NOT a
resolution defect.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from .schema import LegalReference, ModeloRevision
from ._schema_references import governed_period_span


@dataclass(frozen=True, slots=True)
class RevisionLegalApplicabilityWindow:
    """Presentation-aware interval an applicability authority must overlap.

    ``ModeloRevision.valid_from`` / ``valid_to`` describe the tax-period
    revision, while annual and informative forms are commonly approved and
    filed in the following calendar year.  Declared deadline windows therefore
    extend a bounded revision through its latest legally grounded presentation
    close.  An open-ended revision keeps an open upper bound: a later amendment
    can legitimately be one of its applicability authorities.
    """

    starts_on: date
    closes_on: date | None

    @classmethod
    def from_revision(cls, revision: ModeloRevision) -> RevisionLegalApplicabilityWindow:
        """Derive the inclusive revision-plus-presentation interval for a :class:`ModeloRevision`."""
        if revision.valid_to is None:
            return cls(starts_on=revision.valid_from, closes_on=None)
        closes_on_candidates = [
            revision.valid_to,
            *(window.closes_on for window in revision.deadline_windows),
        ]
        return cls(
            starts_on=revision.valid_from,
            closes_on=max(closes_on_candidates),
        )

    def overlaps(self, reference: LegalReference) -> bool:
        """Return whether ``reference`` reaches anywhere in this interval.

        A norm that takes effect AFTER this window closes can still ground it:
        an informativa Orden published at the end of December is effective the
        following January while governing the ejercicio just ended. The
        catalogue states that explicitly through ``governs_periods_from``,
        which the reference schema enforces to be strictly earlier than
        ``effective_from`` precisely because it declares retroactive reach.
        Comparing ``effective_from`` alone therefore refuses a citation the
        catalogue already says governs these periods.
        """
        governs_from, governs_to = governed_period_span(reference)
        if governs_to is not None and governs_to < self.starts_on:
            return False
        return self.closes_on is None or governs_from <= self.closes_on


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

    Connective gate:
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
            f"aeat-calculation-grounding rule",
        )
        return hard

    # Validate each declared entry.
    legal_refs_set = set(revision.legal_refs)
    applicability_window = RevisionLegalApplicabilityWindow.from_revision(revision)
    for ref_id in revision.orden_aplicabilidad:
        # (i) Must resolve in the legal catalogue.
        if ref_id not in legal_catalogue:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"does not resolve in the legal catalogue; add the full LegalReference "
                f"entry to a legal/*.toml file (aeat-calculation-grounding rule)",
            )
            continue  # Cannot check corpus_ref on an absent entry.

        # (ii) Must carry a corpus_ref (already validated by LegalReference schema,
        # but we surface a more helpful revision-level message if it's missing).
        ref = legal_catalogue[ref_id]
        if not ref.corpus_ref:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"exists in the catalogue but has no corpus_ref; add a corpus_ref pointing "
                f"to real BOE/AEAT text (aeat-calculation-grounding rule)",
            )

        # (iii) Must also appear in legal_refs so snapshot ref-collection carries it.
        if ref_id not in legal_refs_set:
            hard.append(
                f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                f"is not present in the revision's legal_refs; add it to legal_refs so "
                f"snapshot ref-collection carries the orden",
            )

        # (iv) The form-approval authority must be effective during the
        # revision's tax-period interval or its declared presentation window.
        # This deliberately validates the typed ``orden_aplicabilidad`` claim,
        # not every legal_refs member: revision legal_refs also aggregate
        # substantive law and amendments whose individual temporal semantics
        # are not interchangeable with form approval.
        if not applicability_window.overlaps(ref):
            closes_on = applicability_window.closes_on
            if ref.effective_to is not None and ref.effective_to < applicability_window.starts_on:
                hard.append(
                    f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                    f"expired on {ref.effective_to.isoformat()} before revision applicability "
                    f"starts on {applicability_window.starts_on.isoformat()}",
                )
            elif closes_on is not None:
                hard.append(
                    f"{scope}: revision {revision.id!r} orden_aplicabilidad entry {ref_id!r} "
                    f"takes effect on {ref.effective_from.isoformat()} after the presentation-aware "
                    f"applicability window closes on {closes_on.isoformat()}",
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
            :class:`~cadrumo.domain.calculations.registry.LegalReference`
            catalogue mapping.

    Returns:
        A list of load-blocking failures.
    """
    return validate_orden_aplicabilidad(scope, modelo_id, revision, legal_catalogue)
