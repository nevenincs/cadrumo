"""The closed catalogue of wizard flows.

Adding a new flow means appending a :class:`WizardFlow` literal to
:data:`WIZARD_FLOWS`. The catalogue is import-time pure: every
question, choice, and condition is a frozen literal and there are no
file reads or environment lookups during construction.
"""

from __future__ import annotations

from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES, Translatable
from ...domain.deadlines._models import IVARegime
from ...domain.profile import RentaDeclarationType, RentaDisabilityGrade, RentaMaritalStatus, RentaSexCode
from ...domain.profile._ccaa import CCAA
from ._models import (
    WizardChoice,
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardSection,
    WizardWidget,
)
from ._setup_answers import SetupAnswers


def _t(suffix: str) -> Translatable:
    """Return a ``Translatable`` for the ``setup`` flow namespace."""

    return Translatable(f"wizard.setup.{suffix}")


def _confirm(qid: str, profile_key: str, *, suffix: str, default: str = "false") -> WizardQuestion:
    """Build a CONFIRM question that persists into ``profile_key``."""

    return WizardQuestion(
        id=qid,
        profile_key=profile_key,
        widget=WizardWidget.CONFIRM,
        prompt=_t(f"{suffix}.{qid}.prompt"),
        default=default,
        required=False,
        answer_type=bool,
    )


_JOINT_DECLARATION = WizardCondition(question_id="taxation-type", equals="2")
_NON_RESIDENT_IRPF = WizardCondition(question_id="spouse-non-resident-irpf", equals="true")
_EU_EEA_RESIDENT = WizardCondition(question_id="spouse-eu-eea-resident", equals="true")


_IVA_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=IVARegime.GENERAL.value,
        label=_t("profile.iva-regime.choices.general.label"),
    ),
    WizardChoice(
        value=IVARegime.SIMPLIFICADO.value,
        label=_t("profile.iva-regime.choices.simplificado.label"),
    ),
    WizardChoice(
        value=IVARegime.RECARGO_EQUIVALENCIA.value,
        label=_t("profile.iva-regime.choices.recargo-equivalencia.label"),
    ),
    WizardChoice(
        value=IVARegime.EXENTO.value,
        label=_t("profile.iva-regime.choices.exento.label"),
    ),
)


_CCAA_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=_t(f"residence.ccaa.choices.{member.value}.label"),
    )
    for member in CCAA
)

_OUTPUT_LANGUAGE_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=language,
        label=_t(f"profile.output-language.choices.{language}.label"),
    )
    for language in SUPPORTED_OUTPUT_LANGUAGES
)

_DECLARATION_TYPE_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaDeclarationType.INDIVIDUAL.value,
        label=_t("profile.taxation-type.choices.individual.label"),
        description=_t("profile.taxation-type.choices.individual.description"),
    ),
    WizardChoice(
        value=RentaDeclarationType.JOINT.value,
        label=_t("profile.taxation-type.choices.joint.label"),
        description=_t("profile.taxation-type.choices.joint.description"),
    ),
)

_SEX_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaSexCode.HOMBRE.value,
        label=_t("codes.sex.choices.h.label"),
    ),
    WizardChoice(
        value=RentaSexCode.MUJER.value,
        label=_t("codes.sex.choices.m.label"),
    ),
)

_MARITAL_STATUS_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaMaritalStatus.SOLTERO.value,
        label=_t("taxpayer.taxpayer-marital-status.choices.soltero.label"),
    ),
    WizardChoice(
        value=RentaMaritalStatus.CASADO.value,
        label=_t("taxpayer.taxpayer-marital-status.choices.casado.label"),
    ),
    WizardChoice(
        value=RentaMaritalStatus.VIUDO.value,
        label=_t("taxpayer.taxpayer-marital-status.choices.viudo.label"),
    ),
    WizardChoice(
        value=RentaMaritalStatus.SEPARADO_DIVORCIADO.value,
        label=_t("taxpayer.taxpayer-marital-status.choices.separado-divorciado.label"),
    ),
)

_DISABILITY_GRADE_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaDisabilityGrade.GE_33_LT_65.value,
        label=_t("codes.disability-grade.choices.33-64.label"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.GE_65.value,
        label=_t("codes.disability-grade.choices.65-plus.label"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.JUDICIAL_INCAPACITY.value,
        label=_t("codes.disability-grade.choices.judicial-incapacity.label"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.ASSISTANCE_OR_REDUCED_MOBILITY.value,
        label=_t("codes.disability-grade.choices.assistance-or-mobility.label"),
    ),
)


_PROFILE_SECTION = WizardSection(
    id="profile",
    title=_t("profile.title"),
    questions=(
        WizardQuestion(
            id="tax-id",
            profile_key="tax.id",
            widget=WizardWidget.TEXT,
            prompt=_t("profile.tax-id.prompt"),
            required=True,
            answer_type=str,
        ),
        WizardQuestion(
            id="name",
            profile_key="name",
            widget=WizardWidget.TEXT,
            prompt=_t("profile.name.prompt"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="surnames",
            profile_key="surnames",
            widget=WizardWidget.TEXT,
            prompt=_t("profile.surnames.prompt"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="activity",
            profile_key="activity",
            widget=WizardWidget.TEXT,
            prompt=_t("profile.activity.prompt"),
            required=True,
            answer_type=str,
        ),
        WizardQuestion(
            id="address-postcode",
            profile_key="address.postcode",
            widget=WizardWidget.TEXT,
            prompt=_t("profile.address-postcode.prompt"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxation-type",
            profile_key="declaration.type",
            widget=WizardWidget.TEXT,
            prompt=_t("profile.taxation-type.prompt"),
            choices=_DECLARATION_TYPE_CHOICES,
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="output-language",
            profile_key="output.language",
            widget=WizardWidget.SELECT,
            prompt=_t("profile.output-language.prompt"),
            choices=_OUTPUT_LANGUAGE_CHOICES,
            default="es",
            required=False,
            answer_type=str,
        ),
    ),
)


_TAXPAYER_SECTION = WizardSection(
    id="taxpayer",
    title=_t("taxpayer.title"),
    questions=(
        WizardQuestion(
            id="taxpayer-sex",
            profile_key="taxpayer.sex",
            widget=WizardWidget.TEXT,
            prompt=_t("taxpayer.taxpayer-sex.prompt"),
            choices=_SEX_CHOICES,
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-marital-status",
            profile_key="taxpayer.marital_status",
            widget=WizardWidget.TEXT,
            prompt=_t("taxpayer.taxpayer-marital-status.prompt"),
            choices=_MARITAL_STATUS_CHOICES,
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-birth-date",
            profile_key="taxpayer.birth_date",
            widget=WizardWidget.TEXT,
            prompt=_t("taxpayer.taxpayer-birth-date.prompt"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-disability-grade",
            profile_key="taxpayer.disability_grade",
            widget=WizardWidget.TEXT,
            prompt=_t("taxpayer.taxpayer-disability-grade.prompt"),
            choices=_DISABILITY_GRADE_CHOICES,
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-death-date",
            profile_key="taxpayer.death_date",
            widget=WizardWidget.TEXT,
            prompt=_t("taxpayer.taxpayer-death-date.prompt"),
            required=False,
            answer_type=str,
        ),
    ),
)


_SPOUSE_SECTION = WizardSection(
    id="spouse",
    title=_t("spouse.title"),
    questions=(
        WizardQuestion(
            id="spouse-tax-id",
            profile_key="spouse.tax.id",
            widget=WizardWidget.TEXT,
            prompt=_t("spouse.spouse-tax-id.prompt"),
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-name",
            profile_key="spouse.name",
            widget=WizardWidget.TEXT,
            prompt=_t("spouse.spouse-name.prompt"),
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-surnames",
            profile_key="spouse.surnames",
            widget=WizardWidget.TEXT,
            prompt=_t("spouse.spouse-surnames.prompt"),
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-birth-date",
            profile_key="spouse.birth_date",
            widget=WizardWidget.TEXT,
            prompt=_t("spouse.spouse-birth-date.prompt"),
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-sex",
            profile_key="spouse.sex",
            widget=WizardWidget.TEXT,
            prompt=_t("spouse.spouse-sex.prompt"),
            choices=_SEX_CHOICES,
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-disability-grade",
            profile_key="spouse.disability_grade",
            widget=WizardWidget.TEXT,
            prompt=_t("spouse.spouse-disability-grade.prompt"),
            choices=_DISABILITY_GRADE_CHOICES,
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-non-resident-irpf",
            profile_key="spouse.non_resident_irpf",
            widget=WizardWidget.CONFIRM,
            prompt=_t("spouse.spouse-non-resident-irpf.prompt"),
            required=False,
            default="false",
            answer_type=bool,
        ),
        WizardQuestion(
            id="spouse-eu-eea-resident",
            profile_key="spouse.eu_eea_resident",
            widget=WizardWidget.CONFIRM,
            prompt=_t("spouse.spouse-eu-eea-resident.prompt"),
            required=False,
            default="false",
            visible_when=_NON_RESIDENT_IRPF,
            answer_type=bool,
        ),
        WizardQuestion(
            id="spouse-eu-eea-country",
            profile_key="spouse.eu_eea_country",
            widget=WizardWidget.TEXT,
            prompt=_t("spouse.spouse-eu-eea-country.prompt"),
            required=False,
            visible_when=_EU_EEA_RESIDENT,
            answer_type=str,
        ),
    ),
)


_FAMILY_SECTION = WizardSection(
    id="family",
    title=_t("family.title"),
    questions=(
        _confirm("family-descendants-eu-eea-deduction", "family.descendants_eu_eea_deduction", suffix="family"),
        _confirm("family-minor-children-in-unit", "family.minor_children_in_unit", suffix="family"),
    ),
)


_IVA_SECTION = WizardSection(
    id="iva",
    title=_t("iva.title"),
    questions=(
        WizardQuestion(
            id="iva-regime",
            profile_key="iva.regime",
            widget=WizardWidget.SELECT,
            prompt=_t("iva.iva-regime.prompt"),
            choices=_IVA_CHOICES,
            default=IVARegime.GENERAL.value,
            required=False,
            answer_type=str,
        ),
        _confirm("iva-roi-enrolled", "iva.roi_enrolled", suffix="iva"),
        _confirm("iva-oss-enrolled", "iva.oss_enrolled", suffix="iva"),
        _confirm(
            "iva-intracommunity-operations-exceed-50000-eur",
            "iva.intracommunity_operations_exceed_50000_eur",
            suffix="iva",
        ),
    ),
)


_ENROLLMENT_SECTION = WizardSection(
    id="enrollment",
    title=_t("enrollment.title"),
    questions=(
        _confirm("enrollment-large-company", "enrollment.large_company", suffix="enrollment"),
        _confirm(
            "enrollment-public-administration-budget-gt-6000000",
            "enrollment.public_administration_budget_gt_6000000",
            suffix="enrollment",
        ),
    ),
)


_OBLIGATIONS_SECTION = WizardSection(
    id="obligations",
    title=_t("obligations.title"),
    questions=(
        _confirm("has-employees", "has_employees", suffix="obligations"),
        _confirm(
            "pays-professionals-with-retencion",
            "pays_professionals_with_retencion",
            suffix="obligations",
        ),
        _confirm(
            "professional-income-withholding-ge-70pct",
            "professional_income_withholding_ge_70pct",
            suffix="obligations",
        ),
        _confirm("pays-rent-with-retencion", "pays_rent_with_retencion", suffix="obligations"),
        _confirm(
            "pays-capital-income-with-retencion",
            "pays_capital_income_with_retencion",
            suffix="obligations",
        ),
        _confirm(
            "uses-objective-estimation-irpf",
            "uses_objective_estimation_irpf",
            suffix="obligations",
        ),
        _confirm("does-intracomunitario", "does_intracomunitario", suffix="obligations"),
        _confirm(
            "third-party-transactions-above-347-threshold",
            "third_party_transactions_above_347_threshold",
            suffix="obligations",
        ),
        _confirm(
            "bienes-extranjero-above-threshold",
            "bienes_extranjero_above_threshold",
            suffix="obligations",
        ),
    ),
)


_RESIDENCE_SECTION = WizardSection(
    id="residence",
    title=_t("residence.title"),
    questions=(
        WizardQuestion(
            id="tax-residence-ccaa",
            profile_key="tax.residence.ccaa",
            widget=WizardWidget.SELECT,
            prompt=_t("residence.tax-residence-ccaa.prompt"),
            choices=_CCAA_CHOICES,
            default=CCAA.MADRID.value,
            required=False,
            answer_type=str,
        ),
    ),
)


_NOTES_SECTION = WizardSection(
    id="notes",
    title=_t("notes.title"),
    questions=(
        WizardQuestion(
            id="notes",
            profile_key="notes",
            widget=WizardWidget.TEXT,
            prompt=_t("notes.notes.prompt"),
            required=False,
            answer_type=str,
        ),
    ),
)


SETUP_FLOW = WizardFlow(
    id="setup",
    title=_t("title"),
    description=_t("description"),
    sections=(
        _PROFILE_SECTION,
        _TAXPAYER_SECTION,
        _SPOUSE_SECTION,
        _FAMILY_SECTION,
        _IVA_SECTION,
        _ENROLLMENT_SECTION,
        _OBLIGATIONS_SECTION,
        _RESIDENCE_SECTION,
        _NOTES_SECTION,
    ),
    answers_model=SetupAnswers,
)


WIZARD_FLOWS: tuple[WizardFlow, ...] = (SETUP_FLOW,)


__all__ = ["SETUP_FLOW", "WIZARD_FLOWS"]
