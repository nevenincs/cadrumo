"""Closed disposition vocabulary for a registry revision's schema families.

A revision declares content in collections - casillas, formulas, bindings,
export layouts - and an empty one is ambiguous in a way that matters. It can
mean the family genuinely does not apply to this modelo, which is a legitimate
and citable claim: an informative modelo has no formulas because it computes
nothing. It can equally mean nobody has built that family yet. Read as a bare
count, the two are indistinguishable, and the second silently reads as the
first - which is how a revision with no calculation closure can present as
complete.

:class:`RegistrySchemaFamilyDisposition` closes that vocabulary so the
distinction is recorded rather than inferred. A family is ``populated`` because
it holds content, ``not_applicable`` because somebody stated it does not apply
and cited why, or ``blocked_pending_evidence`` because neither is true yet.

The third member is the fail-closed default and the point of the whole
vocabulary. It is what an empty, undeclared family reads as, and what it DOES is
refuse: a revision claiming any rung above applicability while one of its
enrolled families sits blocked fails registry build, named family by family. It
clears nothing and permits nothing. It is deliberately never allowlistable -
there is no mechanism for marking one as acceptable, because the only honest
ways out are to populate the family or to state and cite why it does not apply.
An allowlist would be a third way that records nothing and clears the entry.

This vocabulary is about a family's CONTENT. It is not about the evidence
backing that content, which the coverage ledger's evidence tiers already answer
on a different axis, and it is not about how far a revision's authority reaches,
which :class:`RegistryAuthorityGrade` answers. The grade READS these
dispositions - a rung requires the families it enrols to be resolved - so the
two are ordered, not overlapping.
"""

from __future__ import annotations

from enum import StrEnum


class RegistrySchemaFamilyDisposition(StrEnum):
    """Why one of a revision's schema families holds what it holds."""

    POPULATED = "populated"
    """The family holds content; no further claim is needed or permitted."""

    NOT_APPLICABLE = "not_applicable"
    """The family is empty because it does not apply, and the reason is cited.

    A substantive claim, so it carries a reason and legal references. An
    informative modelo declaring no formula family is the canonical case.
    """

    BLOCKED_PENDING_EVIDENCE = "blocked_pending_evidence"
    """The family is empty and nobody has said why - the fail-closed default.

    Never allowlistable. The only exits are populating the family or declaring
    and citing its inapplicability.
    """


UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS: frozenset[RegistrySchemaFamilyDisposition] = frozenset(
    {RegistrySchemaFamilyDisposition.BLOCKED_PENDING_EVIDENCE},
)
"""The dispositions that do NOT resolve a family, as a set rather than a member.

A grade rung requires every family it enrols to be RESOLVED, so the consumer's
question is set membership, not equality against one member. Expressing it as a
set means a future unresolved disposition enrols itself into every such check
instead of needing each call site found and widened - the same reason
:data:`REVIEWED_REVISION_REVIEW_STATUSES` is a set beside its enum.
"""


__all__ = ["UNRESOLVED_SCHEMA_FAMILY_DISPOSITIONS", "RegistrySchemaFamilyDisposition"]
