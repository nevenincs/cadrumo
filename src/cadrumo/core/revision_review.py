"""Closed review-provenance vocabulary for shipped registry records.

Every :class:`~domain.calculations.registry.ModeloRevision` carries a declared
governance stamp naming who engineered the revision and how far its review has
progressed. :class:`RevisionReviewStatus` closes that value set so loader
hydration rejects an unknown token at registry-load time rather than at a
downstream branch on the string.

The status is *declared*, not derived: authorship and signoff are facts about
the humans and agents who built a revision, and nothing in the tree can compute
them. Absence of the stamp block means :attr:`RevisionReviewStatus.PENDING_REVIEW`
- the fail-closed reading, so an unreviewed revision is a visible backlog entry
rather than a silent pass.

The legal catalogue shares this vocabulary rather than declaring its own. Its rows
ask the same question about the same kind of subject -- how far review of a shipped
registry artefact has progressed -- and a second enum with identical members was a
duplicate definition, not a distinct one. The distinction drawn below still holds
against the runtime review vocabularies, which describe a taxpayer's own rows.

This enum is deliberately distinct from the three same-shaped vocabularies the
codebase already ships, none of which can carry this subject:

- The registry schema base once carried a degenerate ``Literal["reviewed"]``
  for the *legal catalogue* rows, with no unreviewed member at all. It has been
  retired onto this vocabulary, which is what lets those rows express the
  pending state.
- ``LedgerReviewStatus``, ``InvoiceReviewStatus``, and
  ``DeclaracionReviewStatus`` in the application review surface are CLI
  filter-value catalogues over a taxpayer's own bucket rows. They describe
  per-taxpayer runtime data, not the authorship of a shipped registry schema,
  and they live outward of the registry domain that needs this value set.

Hydration happens at the registry boundary:
:func:`~domain.calculations.registry.load_registry_tree` parses the
``revision.toml`` token into the member before strict schema validation.
"""

from __future__ import annotations

from enum import StrEnum


class RevisionReviewStatus(StrEnum):
    """How far the review of one modelo registry revision has progressed.

    The members are ordered by increasing assurance. Only
    :attr:`PENDING_REVIEW` may omit the ``reviewed_by`` / ``reviewed_at``
    companions; the two reviewed members require both, so a claimed review
    always names its reviewer and its date.
    """

    PENDING_REVIEW = "pending_review"
    """No review has been recorded for this revision - the fail-closed default."""

    AGENT_REVIEWED = "agent_reviewed"
    """An agent reviewed the revision; an operator has not yet countersigned."""

    OPERATOR_REVIEWED = "operator_reviewed"
    """The operator reviewed and signed off the revision."""


REVIEWED_REVISION_REVIEW_STATUSES: frozenset[RevisionReviewStatus] = frozenset(
    status for status in RevisionReviewStatus if status is not RevisionReviewStatus.PENDING_REVIEW
)
"""The statuses that assert a review happened, derived from the enum.

A revision at one of these statuses must name its ``reviewed_by`` and
``reviewed_at``; a revision at :attr:`RevisionReviewStatus.PENDING_REVIEW` must
name neither. Derived from the member list so a new reviewed member enrolls
automatically.
"""


__all__ = ["REVIEWED_REVISION_REVIEW_STATUSES", "RevisionReviewStatus"]
