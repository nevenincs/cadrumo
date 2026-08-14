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

from ....core import UNDECLARED_REGISTRY_AUTHORITY_GRADE, RegistryAuthorityGrade
from ._schema import ModeloRevision
from ._schema_family_coverage import build_revision_coverage_manifest

#: Families whose resolution the calculation rung specifically asserts.
_CALCULATION_FAMILIES: frozenset[str] = frozenset({"formulas"})


def validate_authority_grade_section(
    prefix: str,
    *,
    modelo_id: str,
    revision: ModeloRevision,
) -> list[str]:
    """Return every way this revision's declared grade outruns its coverage.

    Accumulating and never raising, so one revision's unbacked claim does not
    hide the next one's.

    Returns:
        One message per unbacked rung, empty when the declared grade holds.
    """
    grade = revision.authority_grade or UNDECLARED_REGISTRY_AUTHORITY_GRADE
    if grade is RegistryAuthorityGrade.APPLICABILITY:
        # The floor asserts scheduling reach only, which the schema already
        # validates; there is no coverage claim to outrun.
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
