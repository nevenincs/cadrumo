"""Declared governance provenance for a modelo revision: bounds and validation rules.

Every other conformance fact about the registry is DERIVED — coverage, grounding,
classification coherence are all read back out of the tree. Authorship and signoff
are not: who engineered a revision and who reviewed it are facts about people and
agents, and nothing in the tree can compute them. They are therefore *declared*, on
a four-scalar stamp — ``engineered_by``, ``review_status``, ``reviewed_by``,
``reviewed_at`` — and this module owns the rules that keep a declaration honest.

The stamp is optional and its absence reads as
:attr:`~cadrumo.core.RevisionReviewStatus.PENDING_REVIEW`, so an unstamped revision
is a visible unreviewed backlog entry rather than a silent pass. That fail-closed
default is what makes the remaining rules matter: the only way to leave the backlog
is to make a claim, and a claim that cannot be checked is worse than the backlog it
escapes.

What a dishonest stamp looks like
---------------------------------

Three shapes each render in a conformance report as a signed-off revision while
recording nothing an auditor could verify, and each has a rule here:

* **Naming nobody.** ``reviewed_by = "   "`` satisfies any length constraint —
  whitespace counts — while leaving the attribution exactly as unfalsifiable as
  omitting it (:func:`validate_attribution_names_somebody`).
* **A date outside human reach.** A signoff stamped ``9999-12-31`` or ``1970-01-01``
  is a sentinel or a template artefact wearing a date
  (:func:`validate_reviewed_at_within_horizon`).
* **A stamp disagreeing with itself.** A reviewed status with no reviewer is an
  unfalsifiable claim; a reviewer recorded against ``pending_review`` is a review
  the status denies (:func:`validate_governance_stamp_coherence`).

Why the horizon is a fixed date and not the clock
-------------------------------------------------

The registry is the authority behind every calculation the application performs, so
a validation rule that consults the wall clock would make the shipped tree's
validity a property of the machine that loads it: a container whose clock is behind
reality, or a stamp written the other side of a timezone boundary, would refuse the
whole registry and take the product with it. A false refusal here costs incomparably
more than a missed absurd date, so the bounds are fixed calendar dates, identical on
every machine in every year.

They are consequently *absurdity* bounds, not freshness checks. They catch the
sentinel no auditor could ever check and deliberately do not catch a near-future
typo or a review stamped last year. Freshness is a governance question for the
dev-side conformance audit, where consulting the clock costs one contributor a
re-run rather than bricking the registry.

Why the stamp must be readable in one place
-------------------------------------------

A revision compiles from its ``revision.toml`` manifest plus up to several hundred
section fragments. The stamp is an authorship and signoff claim about the whole
revision, so it has to be readable in the manifest alone: a fragment thousands deep
that declared ``reviewed_by`` would win the merge while ``revision.toml`` still read
unstamped. The loader therefore refuses the governance keys anywhere but the
manifest, and takes its input from the field markers rather than a hand-written
list — a hand-written list catches a rename, because the names stop matching real
fields, but cannot catch an *addition*, and a fifth governance scalar forgotten
there would become silently declarable in any fragment. Marking the field is the
whole of enrolling it.

The same placement guarantee, for a different subject, covers the legally
load-bearing scalars ``legal_refs``, ``orden_aplicabilidad`` and ``valid_to``:
``orden_aplicabilidad`` is an append array, so a fragment silently ADDS an approving
orden the manifest never names, while ``valid_to`` and ``legal_refs`` merge in
wherever the manifest is silent. Governance provenance and legal grounding are
different subjects, which is why they carry different markers, but they need the
same guarantee and the loader refuses both sets in the same place.

See Also:
    :class:`~cadrumo.domain.calculations.registry.ModeloRevision`
        Declares the four stamp scalars and delegates its validators here.
    :data:`~cadrumo.domain.calculations.registry.REVISION_GOVERNANCE_FIELDS`
        The stamp vocabulary, derived from the field markers this module documents.
"""

from __future__ import annotations

from datetime import date

from ....core.revision_review import REVIEWED_REVISION_REVIEW_STATUSES, RevisionReviewStatus
from .errors import RegistryValidationError
from .ids import RevisionId

REVISION_REVIEW_DATE_CEILING: date = date(2100, 1, 1)
"""Exclusive upper bound on a governance stamp's ``reviewed_at`` signoff date.

A signoff dated beyond any living reviewer's horizon is not a signoff: it is a
sentinel or a template artefact wearing a date, and it renders in a conformance
report as an operator countersignature. The bound refuses that class. See this
module's docstring for why the bound is a fixed calendar date rather than a
reading of the local clock.
"""

REVISION_REVIEW_DATE_FLOOR: date = date(2000, 1, 1)
"""Inclusive lower bound on a governance stamp's ``reviewed_at`` signoff date.

A signoff predating the year 2000 is a sentinel or a template artefact: the Unix
epoch (``1970-01-01``), common template placeholders (``1900-01-01``,
``0001-01-01``), or a date so remote it cannot record a real signoff of any
revision in this registry. Each renders in a conformance report as a valid
countersignature while naming a date no auditor can verify.
"""


def validate_attribution_names_somebody(value: str | None, *, field_name: str | None) -> str | None:
    """Refuse an attribution that is declared but names nobody.

    A length constraint counts whitespace, so ``reviewed_by = "   "`` would satisfy
    one while leaving the claim exactly as unfalsifiable as the omission
    :func:`validate_governance_stamp_coherence` refuses — and a blank reviewer
    renders in a conformance report as a signed-off revision. Omission is the honest
    way to say nobody reviewed it.

    Args:
        value: The declared attribution, or ``None`` when the field is omitted.
        field_name: Name of the field being validated, used in the refusal message.

    Returns:
        ``value`` unchanged when it is absent or names somebody.

    Raises:
        RegistryValidationError: When ``value`` is declared but blank.
    """
    if value is not None and not value.strip():
        raise RegistryValidationError(
            f"revision governance field {field_name!r} must name somebody; "
            f"omit the field instead of declaring it blank",
        )
    return value


def validate_reviewed_at_within_horizon(value: date | None) -> date | None:
    """Refuse a signoff date no auditor could ever check.

    See :data:`REVISION_REVIEW_DATE_CEILING` and :data:`REVISION_REVIEW_DATE_FLOOR`
    for why the horizon is a fixed calendar date rather than a reading of the local
    clock.

    Args:
        value: The declared signoff date, or ``None`` when the field is omitted.

    Returns:
        ``value`` unchanged when it is absent or inside the horizon.

    Raises:
        RegistryValidationError: When ``value`` falls outside the horizon.
    """
    if value is not None and value >= REVISION_REVIEW_DATE_CEILING:
        raise RegistryValidationError(
            f"revision governance field 'reviewed_at' is {value.isoformat()}, beyond the signoff horizon "
            f"{REVISION_REVIEW_DATE_CEILING.isoformat()}; a review dated there records no signoff anyone can check",
        )
    if value is not None and value < REVISION_REVIEW_DATE_FLOOR:
        raise RegistryValidationError(
            f"revision governance field 'reviewed_at' is {value.isoformat()}, before the signoff floor "
            f"{REVISION_REVIEW_DATE_FLOOR.isoformat()}; a review dated that far in the past records no "
            "signoff anyone can verify",
        )
    return value


def validate_governance_stamp_coherence(
    *,
    revision_id: RevisionId,
    review_status: RevisionReviewStatus,
    reviewed_by: str | None,
    reviewed_at: date | None,
) -> None:
    """Bind the reviewer identity to the claim that a review happened.

    A reviewed status without a reviewer or a date is an unfalsifiable claim, and a
    reviewer recorded against ``pending_review`` is a review the status denies. Both
    directions refuse so the stamp cannot say one thing on the status axis and
    another on the attribution axis.

    Args:
        revision_id: Revision the stamp belongs to, named in the refusal message.
        review_status: The declared review status.
        reviewed_by: The declared reviewer, or ``None`` when omitted.
        reviewed_at: The declared signoff date, or ``None`` when omitted.

    Raises:
        RegistryValidationError: When the status and the attribution disagree in
            either direction.
    """
    companions = {"reviewed_by": reviewed_by, "reviewed_at": reviewed_at}
    if review_status in REVIEWED_REVISION_REVIEW_STATUSES:
        missing = sorted(name for name, value in companions.items() if value is None)
        if missing:
            raise RegistryValidationError(
                f"revision {revision_id!r} declares review_status={review_status.value!r} but omits "
                f"{missing!r}; a reviewed revision must name its reviewer and the date of review",
            )
        return
    present = sorted(name for name, value in companions.items() if value is not None)
    if present:
        raise RegistryValidationError(
            f"revision {revision_id!r} declares review_status="
            f"{RevisionReviewStatus.PENDING_REVIEW.value!r} but also declares {present!r}; "
            f"record the review by advancing review_status, or drop the reviewer fields",
        )


__all__ = [
    "REVISION_REVIEW_DATE_CEILING",
    "REVISION_REVIEW_DATE_FLOOR",
    "validate_attribution_names_somebody",
    "validate_governance_stamp_coherence",
    "validate_reviewed_at_within_horizon",
]
