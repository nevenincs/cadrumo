"""Registry-build validation of the declared authority-grade ladder.

A :class:`~cadrumo.core.RegistryAuthorityGrade` is a claim about what one
:class:`ModeloRevision` can be trusted to do, and the claim is only worth the
families that back it. Each rung requires every family it enrols to be
RESOLVED - populated, or declared inapplicable with a reason and citations -
and treats a family left pending evidence as the claim being unbacked.

The rule is disposition-conditional rather than population-conditional, which is
what lets an informative modelo carrying export layouts and no formulas reach
filing grade honestly: its formula family is resolved as not applicable, with a
reason, rather than left empty and silent.
"""

from __future__ import annotations

from ....core.authority_grade import RegistryAuthorityGrade
from ._schema_family_coverage import build_revision_coverage_manifest
from .schema import ModeloRevision

#: Families whose resolution the calculation rung specifically asserts.
_CALCULATION_FAMILIES: frozenset[str] = frozenset({"formulas"})


def validate_authority_grade_section(
    prefix: str,
    *,
    modelo_id: str,
    revision: ModeloRevision,
) -> list[str]:
    """Return every way this revision's grade is absent, or outruns its coverage.

    Two distinct failures, deliberately not merged. A revision that declares NO
    grade fails on the absence: silence reads as the floor, and the floor has no
    coverage claim to outrun, so an ungraded revision would otherwise take the
    exemption and escape this check entirely. A revision that declares a rung its
    families do not back fails on the gap.

    Accumulating and never raising, so one revision's unbacked claim does not
    hide the next one's.

    Returns:
        One message for an absent grade, or one per unbacked rung; empty when a
        declared grade holds.
    """
    if not revision.is_graded:
        return [
            f"{prefix} declares no authority_grade, so it makes no claim about how far its "
            "authority reaches and silently takes the weakest treatment this check applies. "
            "Declare the rung this revision is INTENDED to support: "
            f"{RegistryAuthorityGrade.APPLICABILITY.value!r} if it is only ever meant to answer "
            "when the modelo is due and to whom it applies; "
            f"{RegistryAuthorityGrade.CALCULATION.value!r} if it is also meant to compute the "
            "modelo's amounts; "
            f"{RegistryAuthorityGrade.FILING.value!r} if it is additionally meant to back a "
            "filing draft and its export. "
            "DO NOT pick the rung by looking at which families this revision currently has. A "
            "grade read off present content makes the claim agree with the content by "
            "construction, so this check could never fail and would be inert again -- harder to "
            "notice than the silence it replaced, because every number would agree. The point of "
            "the declaration is that a revision INTENDED to reach filing, whose families do not "
            "yet back it, fails here and stays failing until they do.",
        ]

    grade = revision.effective_authority_grade
    if grade is RegistryAuthorityGrade.APPLICABILITY:
        # A DECLARED floor asserts scheduling reach only, which the schema already
        # validates; there is no coverage claim to outrun. Read through
        # ``is_graded`` above rather than by collapsing absence into this value:
        # an ungraded revision and one declared at the floor read as the same
        # scope but are not the same claim, and only one of them is a backlog
        # entry.
        return []

    manifest = build_revision_coverage_manifest(modelo=modelo_id, revision=revision)
    if manifest.fully_resolved:
        return []
    unresolved = {row.family for row in manifest.unresolved}

    if grade is RegistryAuthorityGrade.FILING:
        return [
            f"{prefix} claims {grade.value!r} authority grade while "
            f"{sorted(unresolved)!r} remain blocked pending evidence. The filing "
            f"rung asserts every enrolled family is resolved: populate each one, "
            f"or declare it not applicable with a reason and citations.",
        ]

    blocked = sorted(unresolved & _CALCULATION_FAMILIES)
    if blocked:
        return [
            f"{prefix} claims {grade.value!r} authority grade while {blocked!r} "
            f"remain blocked pending evidence. The calculation rung asserts a "
            f"resolved calculation closure: populate the family, or declare it "
            f"not applicable with a reason and citations if this modelo computes "
            f"nothing.",
        ]
    return []
