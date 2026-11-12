"""The enrolment of an autonomic deducción (LIRPF art. 77) on the formula that computes it.

A comunidad autónoma grants a deducción in the cuota autonómica. The Modelo 100
carries each in its own box, and the box is computed only once its deducción is
enrolled: the formula that targets the box declares, in one typed table, which
comunidad's residents it reaches, the box by its semantic role, the closed
eligibility axis whose primitive counts the entitled persons, the dated amount
parameter, the income limit the comunidad's text sets (or that it sets none),
the prorrateo the text states, and the comunidad's own provision beside the
art. 77 framework.

The table is authored once, on the formula of the edition where the comunidad's
text first applies, and later editions inherit the formula with it. A change of
amount is a dated parameter value, never a second enrolment. A field outside
this vocabulary, an axis outside the closed set, or a prorrateo the axis cannot
apply is refused when the registry loads; the references to the revision's
casillas, bindings and parameters are checked after hydration by
:mod:`.autonomic_deduccion_enrolment_checks`.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Final, Literal

from pydantic import BeforeValidator, Field, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from .errors import RegistryValidationError
from .ids import BindingId, ParameterId
from .schema_base import LegalRefs, RegistryModel, coerce_enum_member

__all__ = [
    "AUTONOMIC_DEDUCCION_FRAMEWORK_LEGAL_REF",
    "AUTONOMIC_DEDUCCION_SECTION",
    "AscendantMinimumEntitlementAxis",
    "AutonomicDeduccionEnrolment",
    "AutonomicEligibilityAxis",
    "AutonomicIncomeLimit",
    "AutonomicIncomeUnit",
    "AutonomicProrrateo",
    "DescendantEntryWindowAxis",
    "NoAutonomicIncomeLimit",
]

AUTONOMIC_DEDUCCION_FRAMEWORK_LEGAL_REF: Final = "ley-35-2006:art-77"
"""The LIRPF article every comunidad deducción rests on, cited beside the comunidad's own provision."""

AUTONOMIC_DEDUCCION_SECTION: Final = "deduccion_autonomica_res"
"""The casilla section an autonomic deducción box belongs to."""


class AutonomicEligibilityAxis(StrEnum):
    """The closed set of eligibility primitives an enrolment can name.

    Each member has exactly one primitive that reads the stated profile facts. A
    deducción whose eligibility no member expresses needs a new member and its
    primitive, reviewed once, before it can be enrolled.
    """

    DESCENDANT_ENTRY_WINDOW_COUNT = "descendant_entry_window_count"
    """Cohabiting descendants whose birth or adoption falls within a window of periods."""
    ASCENDANT_MINIMUM_ENTITLEMENT = "ascendant_minimum_entitlement"
    """Ascendants the filer applies the art. 59 and 61 mínimo for, meeting the comunidad's age or disability."""


class AutonomicProrrateo(StrEnum):
    """How the comunidad's text shares the amount between taxpayers entitled for the same person."""

    EQUAL_PARTS = "equal_parts"
    """Equal parts between the parents a descendant lives with, when they file individually."""
    STATE_MINIMUM_SHARING = "state_minimum_sharing"
    """The sharing of the state mínimo the deducción rests on (LIRPF arts. 60 and 61)."""
    NONE = "none"
    """The text shares nothing: each entitled taxpayer applies the full amount."""


class AutonomicIncomeUnit(StrEnum):
    """Whose base the comunidad's income limit measures."""

    CONTRIBUYENTE = "contribuyente"
    """The taxpayer's own base only."""
    UNIDAD_FAMILIAR = "unidad_familiar"
    """The taxpayer's own base, and separately that of the whole unidad familiar."""


class DescendantEntryWindowAxis(RegistryModel):
    """Cohabiting descendants born or adopted within the entry period and its following periods."""

    kind: Literal["descendant_entry_window_count"]
    following_periods_fact: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    """The governed fact counting the periods after the entry period in which the deducción still applies."""


class AscendantMinimumEntitlementAxis(RegistryModel):
    """Ascendants the filer applies the mínimo por ascendientes for, meeting the comunidad's condition.

    The comunidad's condition is an age or a disability grade, either of which suffices.
    """

    kind: Literal["ascendant_minimum_entitlement"]
    minimum_age: ParameterId
    """The age at the devengo from which an ascendant qualifies."""
    minimum_discapacidad_grado: ParameterId
    """The disability grade from which an ascendant of any age qualifies."""


AutonomicEligibility = Annotated[
    DescendantEntryWindowAxis | AscendantMinimumEntitlementAxis,
    Field(discriminator="kind"),
]


class NoAutonomicIncomeLimit(RegistryModel):
    """The comunidad's text sets no income limit for this deducción."""

    kind: Literal["none"]


class AutonomicIncomeLimit(RegistryModel):
    """The income limit the comunidad's text sets, read from the calculated return's own boxes.

    ``base_semantic_roles`` names, by semantic role, the boxes whose sum is the base the
    text measures (for instance the bases imponibles general and del ahorro). The
    thresholds are dated parameters, one for an individual and one for a joint
    return; a limit over the unidad familiar adds its own threshold and the binding
    that supplies the other members' base.
    """

    kind: Literal["base"]
    base_semantic_roles: tuple[str, ...] = Field(min_length=1)
    unit: Annotated[AutonomicIncomeUnit, BeforeValidator(coerce_enum_member(AutonomicIncomeUnit))]
    individual_limit: ParameterId
    joint_limit: ParameterId
    unidad_familiar_limit: ParameterId | None = None
    other_members_base_binding: BindingId | None = None
    legal_refs: LegalRefs

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _unit_terms_match_unit(self) -> AutonomicIncomeLimit:
        if len(set(self.base_semantic_roles)) != len(self.base_semantic_roles):
            raise RegistryValidationError("an autonomic income limit names each base role once")
        unit_terms = (self.unidad_familiar_limit, self.other_members_base_binding)
        if self.unit is AutonomicIncomeUnit.UNIDAD_FAMILIAR and None in unit_terms:
            raise RegistryValidationError(
                "an autonomic income limit over the unidad familiar declares its threshold and the binding "
                "that supplies the other members' base"
            )
        if self.unit is AutonomicIncomeUnit.CONTRIBUYENTE and unit_terms != (None, None):
            raise RegistryValidationError("an autonomic income limit over the taxpayer alone declares no unit terms")
        return self


_PRORRATEO_BY_AXIS: Final[dict[AutonomicEligibilityAxis, frozenset[AutonomicProrrateo]]] = {
    AutonomicEligibilityAxis.DESCENDANT_ENTRY_WINDOW_COUNT: frozenset(
        {AutonomicProrrateo.EQUAL_PARTS, AutonomicProrrateo.NONE}
    ),
    AutonomicEligibilityAxis.ASCENDANT_MINIMUM_ENTITLEMENT: frozenset({AutonomicProrrateo.STATE_MINIMUM_SHARING}),
}
"""The prorrateo each axis primitive can apply; the ascendant axis shares as the art. 61 mínimo does."""


class AutonomicDeduccionEnrolment(RegistryModel):
    """One comunidad deducción, enrolled on the formula that computes its box."""

    ccaa: str = Field(pattern=r"^[a-z][a-z_]*$")
    """The comunidad's residence token, as the CCAA catalogue states it."""
    target_semantic_role: str = Field(min_length=1)
    """The semantic role of the box the deducción is declared in."""
    eligibility: AutonomicEligibility
    count_binding: BindingId
    """The profile binding the axis primitive's weighted count reaches the formula through."""
    amount: ParameterId
    """The dated amount for each entitled person."""
    income_limit: Annotated[NoAutonomicIncomeLimit | AutonomicIncomeLimit, Field(discriminator="kind")]
    prorrateo: Annotated[AutonomicProrrateo, BeforeValidator(coerce_enum_member(AutonomicProrrateo))]
    legal_refs: LegalRefs
    """The comunidad's provision, with the art. 77 framework beside it."""

    @property
    def axis(self) -> AutonomicEligibilityAxis:
        """The closed axis the eligibility declaration belongs to."""
        return AutonomicEligibilityAxis(self.eligibility.kind)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _grounded_and_shareable(self) -> AutonomicDeduccionEnrolment:
        if AUTONOMIC_DEDUCCION_FRAMEWORK_LEGAL_REF not in self.legal_refs:
            raise RegistryValidationError(
                f"the {self.target_semantic_role!r} enrolment cites {AUTONOMIC_DEDUCCION_FRAMEWORK_LEGAL_REF!r} "
                "beside its comunidad's provision"
            )
        if len(self.legal_refs) < 2:
            raise RegistryValidationError(
                f"the {self.target_semantic_role!r} enrolment cites its comunidad's own provision"
            )
        if self.prorrateo not in _PRORRATEO_BY_AXIS[self.axis]:
            raise RegistryValidationError(
                f"the {self.target_semantic_role!r} enrolment declares prorrateo {self.prorrateo.value!r}, "
                f"which the {self.axis.value!r} axis cannot apply"
            )
        return self
