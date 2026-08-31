"""Closed authority-grade vocabulary for modelo registry revisions.

A registry revision declares one temporal selector, and that selector was for a
long time read as the answer to three different questions: which filing years the
form legally applies to, which years the project holds evidence for, and which
years a runtime surface may serve as filing authority. Nothing in the tree
distinguished a revision that only knows *when a modelo is due* from one that can
compute its amounts and back an export. :class:`RegistryAuthorityGrade` closes
that vocabulary so the distinction is a typed declaration rather than an
inference from how many fragments a revision happens to carry.

The grade is *declared*, not derived - and only in one direction. Demotion is a
fact the corpus can compute: a revision whose formula family is empty cannot
claim to calculate. Promotion is an attestation about evidence a human has read,
so no program, migration or bulk command may raise a revision's grade. The
declaration is therefore a claim registry validation checks against the families
the revision actually resolves; a grade that outruns them refuses at build, which
is what keeps the field from being aspirational.

Absence is the fail-closed ungraded state, read through
:data:`UNDECLARED_REGISTRY_AUTHORITY_GRADE`: an undeclared revision reaches only
:attr:`RegistryAuthorityGrade.APPLICABILITY` scope, so it stays a visible
backlog entry rather than a silent pass. Absence is deliberately NOT the same
value as a declared ``applicability`` grade even though both read as the same
scope - one is a claim somebody made, the other is the absence of one, and a
later corpus-completeness check needs to tell them apart.

This enum is deliberately distinct from the review vocabulary in
:mod:`._revision_review`, which is easy to confuse with it: ``RevisionReviewStatus``
records *who has signed off* on a revision, and this enum records *how far the
revision's authority reaches*. A revision can be operator-reviewed and still only
carry applicability data; a revision can carry a complete calculation closure and
never have been reviewed. Neither implies the other, so they are two fields.

Hydration happens at the registry loader boundary: registry TOML stays free-form
and the ``revision.toml`` token is coerced into a member before strict schema
validation, so an unknown grade fails registry load rather than a downstream
branch on a string.
"""

from __future__ import annotations

from enum import StrEnum


class RegistryAuthorityGrade(StrEnum):
    """How far one modelo registry revision's declared authority reaches.

    The members form a ladder of increasing claim, each rung requiring
    everything the rung below it requires. Which families a rung demands is a question about *dispositions*, not raw
    population - a family may be honestly resolved as not applicable, with a
    reason and legal references - so an informative modelo carrying export
    layouts and no formulas can legitimately reach :attr:`FILING`. Registry
    build validation owns that rule; this enum owns only the vocabulary.
    """

    APPLICABILITY = "applicability"
    """The revision knows when the modelo is due and to whom it applies.

    Scheduling and deadline reach only. This is also the scope an undeclared
    grade reads as, per :data:`UNDECLARED_REGISTRY_AUTHORITY_GRADE`.
    """

    CALCULATION = "calculation"
    """The revision can additionally compute the modelo's amounts.

    Everything :attr:`APPLICABILITY` asserts, plus a resolved calculation
    closure wherever the formula family applies.
    """

    FILING = "filing"
    """The revision can additionally back a filing draft and its export.

    The top rung: everything the lower rungs assert, with every family the
    revision enrols resolved rather than left pending evidence.
    """


UNDECLARED_REGISTRY_AUTHORITY_GRADE: RegistryAuthorityGrade = RegistryAuthorityGrade.APPLICABILITY
"""The scope an undeclared ``authority_grade`` reads as - the fail-closed floor.

Reading absence as the LOWEST rung rather than the highest is what makes the
field safe to land optional: a revision nobody has graded confers scheduling
reach and nothing more, so an ungraded corpus degrades to advisory visibility
instead of silently presenting every revision as filing authority. Named here
rather than open-coded as ``grade or APPLICABILITY`` at each consumer, so the
floor is one decision and a later change to it cannot land half-swept.
"""


__all__ = ["UNDECLARED_REGISTRY_AUTHORITY_GRADE", "RegistryAuthorityGrade"]
