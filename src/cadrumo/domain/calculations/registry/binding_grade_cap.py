"""The declared grade cap one registry binding carries.

A revision's ``authority_grade`` states how far the revision reaches. A single
binding can rest on a reading that grade does not cover: Modelo 130 casilla 06
and the income casilla beside it share one provider kind and differ only in the
fact they read, so a cap on the kind would demote the income box too. The cap
is therefore declared on the binding row, where it narrows that binding's reach
and nothing else.

The cap only narrows. A binding without one reaches as far as its revision's
grade, and a cap never raises that grade. Removing a cap is a promotion, which
is a human attestation that lands as an ordinary registry delta; no program
removes or rewrites one.

The cap is authored as one inline table on the binding row::

    grade_cap = { grade = "calculation", reason = "imputation_period_ungrounded",
                  legal_refs = ["rd-439-2007:art-79"] }

Grade and reason are closed vocabularies hydrated at the loader boundary, so an
unknown token fails registry load. Registry build validation owns the rules that
need the rest of the revision or the legal catalogue.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BeforeValidator, field_validator

from ....core.authority_grade import BINDING_GRADE_CAP_GRADES, BindingGradeCapReason, RegistryAuthorityGrade
from ....core.errors.hierarchy import pydantic_validation_boundary
from .errors import RegistryValidationError
from .schema_base import LegalRefs, RegistryAuthorityGradeField, RegistryModel, coerce_enum_member

BindingGradeCapReasonField = Annotated[
    BindingGradeCapReason, BeforeValidator(coerce_enum_member(BindingGradeCapReason))
]
"""Registry token hydrated into a :class:`~cadrumo.core.authority_grade.BindingGradeCapReason` member."""


class BindingGradeCap(RegistryModel):
    """The rung one binding's value reaches, why, and the provisions behind the reason.

    ``legal_refs`` are the provisions that leave the value short of filing
    grade. They also state the reconsideration condition: the cap is removed
    when what they leave open is grounded.
    """

    grade: RegistryAuthorityGradeField
    reason: BindingGradeCapReasonField
    legal_refs: LegalRefs

    @field_validator("grade")
    @classmethod
    @pydantic_validation_boundary
    def _admit_only_a_cap_grade(cls, value: RegistryAuthorityGrade) -> RegistryAuthorityGrade:
        if value not in BINDING_GRADE_CAP_GRADES:
            raise RegistryValidationError(
                f"a binding grade cap admits only {sorted(grade.value for grade in BINDING_GRADE_CAP_GRADES)}, "
                f"not {value.value!r}",
                context={"grade": value.value},
            )
        return value


__all__ = ["BindingGradeCap", "BindingGradeCapReasonField"]
