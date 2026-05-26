"""The closed catalogue of wizard flows.

Adding a new flow means appending a :class:`WizardFlow` literal to
:data:`WIZARD_FLOWS`. The catalogue is import-time pure: every
question, choice, and condition is a frozen literal and there are no
file reads or environment lookups during construction.
"""

from __future__ import annotations

from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n import Translatable as tr
from ...domain.deadlines._models import (
    EntityType,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IVARegime,
    LegalEntityForm,
)
from ...domain.profile import RentaDeclaracionType, RentaDisabilityGrade, RentaMaritalStatus, RentaSexCode
from ...domain.profile._ccaa import CCAA
from ._models import (
    WizardChoice,
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardSection,
    WizardVisibility,
    WizardWidget,
)
from ._setup_answers import SetupAnswers


def _confirm(
    qid: str,
    profile_key: str,
    *,
    suffix: str,
    default: str = "false",
    visible_when: WizardCondition | WizardVisibility | None = None,
) -> WizardQuestion:
    """Build a CONFIRM question that persists into ``profile_key``."""

    return WizardQuestion(
        id=qid,
        profile_key=profile_key,
        widget=WizardWidget.CONFIRM,
        prompt=tr(f"wizard.setup.{suffix}.{qid}.prompt"),
        default=default,
        required=False,
        visible_when=visible_when,
        answer_type=bool,
    )


# The entity-type axis decides whether the IRPF-personal surface — the
# spouse, family, and personal-biographic questions, plus the
# individual-vs-joint taxation choice — is collected at all. A legal
# entity (sociedad limitada, etc.) and an attribution entity have no
# spouse and no personal IRPF facts: those questions are gated to the
# natural-person path so the non-interactive `--quiet` flow never asks
# (or, before this gate, wrongly demands) them for a company.
_NATURAL_PERSON = WizardCondition(question_id="entity-type", equals=EntityType.NATURAL_PERSON.value)

_JOINT_DECLARATION = WizardCondition(question_id="taxation-type", equals="2")
_NON_RESIDENT_IRPF = WizardCondition(question_id="spouse-non-resident-irpf", equals="true")
_EU_EEA_RESIDENT = WizardCondition(question_id="spouse-eu-eea-resident", equals="true")


_IVA_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=IVARegime.GENERAL.value,
        label=tr("wizard.setup.profile.iva-regime.choices.general.label"),
    ),
    WizardChoice(
        value=IVARegime.SIMPLIFICADO.value,
        label=tr("wizard.setup.profile.iva-regime.choices.simplificado.label"),
    ),
    WizardChoice(
        value=IVARegime.RECARGO_EQUIVALENCIA.value,
        label=tr("wizard.setup.profile.iva-regime.choices.recargo-equivalencia.label"),
    ),
    WizardChoice(
        value=IVARegime.REAGP.value,
        label=tr("wizard.setup.profile.iva-regime.choices.reagp.label"),
    ),
    WizardChoice(
        value=IVARegime.EXENTO.value,
        label=tr("wizard.setup.profile.iva-regime.choices.exento.label"),
    ),
)


_ENTITY_TYPE_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label"),
    )
    for member in EntityType
)

_LEGAL_ENTITY_FORM_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label"),
    )
    for member in LegalEntityForm
)

_IRPF_INCOME_CATEGORY_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.label"),
    )
    for member in IrpfIncomeCategory
)

_IRPF_ESTIMATION_REGIME_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.obligations.irpf-estimation-regime.choices.{member.value.replace('_', '-')}.label"),
    )
    for member in IrpfEstimationRegime
)


_CCAA_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.residence.ccaa.choices.{member.value}.label"),
    )
    for member in CCAA
)

_OUTPUT_LANGUAGE_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=language,
        label=tr(f"wizard.setup.profile.output-language.choices.{language}.label"),
    )
    for language in SUPPORTED_OUTPUT_LANGUAGES
)

_DECLARATION_TYPE_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaDeclaracionType.INDIVIDUAL.value,
        label=tr("wizard.setup.profile.taxation-type.choices.individual.label"),
        description=tr("wizard.setup.profile.taxation-type.choices.individual.description"),
    ),
    WizardChoice(
        value=RentaDeclaracionType.JOINT.value,
        label=tr("wizard.setup.profile.taxation-type.choices.joint.label"),
        description=tr("wizard.setup.profile.taxation-type.choices.joint.description"),
    ),
)

_SEX_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaSexCode.HOMBRE.value,
        label=tr("wizard.setup.codes.sex.choices.h.label"),
    ),
    WizardChoice(
        value=RentaSexCode.MUJER.value,
        label=tr("wizard.setup.codes.sex.choices.m.label"),
    ),
)

_MARITAL_STATUS_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaMaritalStatus.SOLTERO.value,
        label=tr("wizard.setup.taxpayer.taxpayer-marital-status.choices.soltero.label"),
    ),
    WizardChoice(
        value=RentaMaritalStatus.CASADO.value,
        label=tr("wizard.setup.taxpayer.taxpayer-marital-status.choices.casado.label"),
    ),
    WizardChoice(
        value=RentaMaritalStatus.VIUDO.value,
        label=tr("wizard.setup.taxpayer.taxpayer-marital-status.choices.viudo.label"),
    ),
    WizardChoice(
        value=RentaMaritalStatus.SEPARADO_DIVORCIADO.value,
        label=tr("wizard.setup.taxpayer.taxpayer-marital-status.choices.separado-divorciado.label"),
    ),
)

_DISABILITY_GRADE_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaDisabilityGrade.GE_33_LT_65.value,
        label=tr("wizard.setup.codes.disability-grade.choices.33-64.label"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.GE_65.value,
        label=tr("wizard.setup.codes.disability-grade.choices.65-plus.label"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.JUDICIAL_INCAPACITY.value,
        label=tr("wizard.setup.codes.disability-grade.choices.judicial-incapacity.label"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.ASSISTANCE_OR_REDUCED_MOBILITY.value,
        label=tr("wizard.setup.codes.disability-grade.choices.assistance-or-mobility.label"),
    ),
)


_ENTITY_LEGAL = WizardCondition(question_id="entity-type", equals=EntityType.LEGAL_ENTITY.value)

# `activity` (the actividad económica / epígrafe IAE free-text field)
# is collected only for a taxpayer that actually carries on an
# activity: a legal entity, or a natural person who declared the
# `actividad_economica` IRPF income category. A pure landlord,
# a salaried-only taxpayer, and a pensioner have no actividad
# económica and must not be forced to invent one.
_HAS_ACTIVITY = WizardVisibility(
    any_of=(
        _ENTITY_LEGAL,
        WizardCondition(question_id="irpf-income-categories", contains=IrpfIncomeCategory.ACTIVIDAD_ECONOMICA.value),
    )
)


_TAXPAYER_TYPE_SECTION = WizardSection(
    id="taxpayer-type",
    title=tr("wizard.setup.taxpayer-type.title"),
    questions=(
        WizardQuestion(
            id="entity-type",
            profile_key="taxpayer_type.entity_type",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.taxpayer-type.entity-type.prompt"),
            help=tr("wizard.setup.taxpayer-type.entity-type.help"),
            choices=_ENTITY_TYPE_CHOICES,
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="legal-entity-form",
            profile_key="taxpayer_type.legal_entity_form",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.taxpayer-type.legal-entity-form.prompt"),
            choices=_LEGAL_ENTITY_FORM_CHOICES,
            required=False,
            visible_when=_ENTITY_LEGAL,
            answer_type=str,
        ),
        WizardQuestion(
            id="irpf-income-categories",
            profile_key="taxpayer_type.irpf_income_categories",
            widget=WizardWidget.CHECKBOX,
            prompt=tr("wizard.setup.taxpayer-type.irpf-income-categories.prompt"),
            help=tr("wizard.setup.taxpayer-type.irpf-income-categories.help"),
            choices=_IRPF_INCOME_CATEGORY_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            # Optional INCN (importe neto de la cifra de negocios) of
            # the prior 12 months. Gates the Modelo 202 modality split
            # at the 6.000.000 EUR threshold (LIS Art. 40.3): above it
            # Art. 40.3 is mandatory, below it both modalities are
            # reachable. An undeclared value yields an INCOMPLETE
            # downstream verdict, never a guessed modality.
            id="incn-prior-12-months",
            profile_key="taxpayer_type.incn_prior_12_months",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer-type.incn-prior-12-months.prompt"),
            help=tr("wizard.setup.taxpayer-type.incn-prior-12-months.help"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            # Optional LIS Art. 29 first-two-profit-making-periods
            # state. Gates the 15 percent new-entity rate override.
            # Only meaningful for a legal entity; gated visible_when on
            # entity_type == legal_entity. ``default="false"`` keeps the
            # CONFIRM widget validator happy under ``--quiet`` when the
            # operator does not pass the flag — the override is opt-in,
            # so an unset profile equals "no override", semantically
            # identical to the undeclared three-state ``None``. A
            # positively-declared ``--new-entity-first-two-profit-periods``
            # writes ``true`` and opts into the override.
            id="new-entity-first-two-profit-periods",
            profile_key="taxpayer_type.new_entity_first_two_profit_periods",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.taxpayer-type.new-entity-first-two-profit-periods.prompt"),
            help=tr("wizard.setup.taxpayer-type.new-entity-first-two-profit-periods.help"),
            default="false",
            required=False,
            visible_when=_ENTITY_LEGAL,
            answer_type=bool,
        ),
    ),
)


_PROFILE_SECTION = WizardSection(
    id="profile",
    title=tr("wizard.setup.profile.title"),
    questions=(
        WizardQuestion(
            id="tax-id",
            profile_key="identity.tax_id",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.tax-id.prompt"),
            required=True,
            answer_type=str,
        ),
        WizardQuestion(
            id="name",
            profile_key="identity.name",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.name.prompt"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="surnames",
            profile_key="identity.surnames",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.surnames.prompt"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="activity",
            profile_key="activities.description",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.activity.prompt"),
            required=False,
            visible_when=_HAS_ACTIVITY,
            answer_type=str,
        ),
        WizardQuestion(
            id="address-postcode",
            profile_key="contact.postcode",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.address-postcode.prompt"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            # Optional census alta date. When set, the deadline engine
            # suppresses obligation windows that close before it, so a
            # recent registrant is not shown overdue returns for periods
            # that precede their alta.
            id="activity-start-date",
            profile_key="census.activity_start_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.activity-start-date.prompt"),
            help=tr("wizard.setup.profile.activity-start-date.help"),
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxation-type",
            profile_key="filing_export.declaration_type",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.taxation-type.prompt"),
            choices=_DECLARATION_TYPE_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            id="output-language",
            profile_key="preferences.output_language",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.profile.output-language.prompt"),
            choices=_OUTPUT_LANGUAGE_CHOICES,
            default="es",
            required=False,
            answer_type=str,
        ),
    ),
)


_TAXPAYER_SECTION = WizardSection(
    id="taxpayer",
    title=tr("wizard.setup.taxpayer.title"),
    questions=(
        WizardQuestion(
            id="taxpayer-sex",
            profile_key="renta_taxpayer.sex",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer.taxpayer-sex.prompt"),
            choices=_SEX_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-marital-status",
            profile_key="renta_taxpayer.marital_status",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer.taxpayer-marital-status.prompt"),
            choices=_MARITAL_STATUS_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-birth-date",
            profile_key="renta_taxpayer.birth_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer.taxpayer-birth-date.prompt"),
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-disability-grade",
            profile_key="renta_taxpayer.disability_grade",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer.taxpayer-disability-grade.prompt"),
            choices=_DISABILITY_GRADE_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            id="taxpayer-death-date",
            profile_key="renta_taxpayer.death_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer.taxpayer-death-date.prompt"),
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
    ),
)


_SPOUSE_SECTION = WizardSection(
    id="spouse",
    title=tr("wizard.setup.spouse.title"),
    questions=(
        WizardQuestion(
            # Required *when visible*: a joint declaration is invalid
            # without the spouse NIF (SetupAnswers enforces the same
            # invariant). The widget validator still accepts a blank
            # answer for a gated question; the conditional requirement
            # is enforced at `validate_profile_values` via the compiled
            # `required_when_*` pair.
            id="spouse-tax-id",
            profile_key="renta_spouse.tax_id",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-tax-id.prompt"),
            required=True,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-name",
            profile_key="renta_spouse.name",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-name.prompt"),
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-surnames",
            profile_key="renta_spouse.surnames",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-surnames.prompt"),
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-birth-date",
            profile_key="renta_spouse.birth_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-birth-date.prompt"),
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-sex",
            profile_key="renta_spouse.sex",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-sex.prompt"),
            choices=_SEX_CHOICES,
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-disability-grade",
            profile_key="renta_spouse.disability_grade",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-disability-grade.prompt"),
            choices=_DISABILITY_GRADE_CHOICES,
            required=False,
            visible_when=_JOINT_DECLARATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="spouse-non-resident-irpf",
            profile_key="renta_spouse.non_resident_irpf",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.spouse.spouse-non-resident-irpf.prompt"),
            required=False,
            default="false",
            visible_when=_JOINT_DECLARATION,
            answer_type=bool,
        ),
        WizardQuestion(
            id="spouse-eu-eea-resident",
            profile_key="renta_spouse.eu_eea_resident",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.spouse.spouse-eu-eea-resident.prompt"),
            required=False,
            default="false",
            visible_when=_NON_RESIDENT_IRPF,
            answer_type=bool,
        ),
        WizardQuestion(
            # Required *when visible*: an EU/EEA-resident spouse must
            # name the residence country (SetupAnswers enforces the
            # same invariant). The conditional requirement is compiled
            # into the `required_when_*` pair.
            id="spouse-eu-eea-country",
            profile_key="renta_spouse.eu_eea_country",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.spouse.spouse-eu-eea-country.prompt"),
            required=True,
            visible_when=_EU_EEA_RESIDENT,
            answer_type=str,
        ),
    ),
)


_FAMILY_SECTION = WizardSection(
    id="family",
    title=tr("wizard.setup.family.title"),
    questions=(
        _confirm(
            "family-descendants-eu-eea-deduction",
            "renta_family.descendants_eu_eea_deduction",
            suffix="family",
            visible_when=_NATURAL_PERSON,
        ),
        _confirm(
            "family-minor-children-in-unit",
            "renta_family.minor_children_in_unit",
            suffix="family",
            visible_when=_NATURAL_PERSON,
        ),
    ),
)


_IVA_SECTION = WizardSection(
    id="iva",
    title=tr("wizard.setup.iva.title"),
    questions=(
        WizardQuestion(
            id="iva-regime",
            profile_key="iva.regime",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.iva.iva-regime.prompt"),
            choices=_IVA_CHOICES,
            default=IVARegime.GENERAL.value,
            required=False,
            answer_type=str,
        ),
        _confirm("iva-roi-enrolled", "iva.roi_enrolled", suffix="iva"),
        _confirm("iva-oss-enrolled", "iva.oss_enrolled", suffix="iva"),
        _confirm("iva-sii-enrolled", "iva.sii_enrolled", suffix="iva"),
        _confirm("iva-redeme-enrolled", "iva.redeme_enrolled", suffix="iva"),
        _confirm(
            "iva-intracommunity-operations-exceed-50000-eur",
            "iva.intracommunity_operations_exceed_50000_eur",
            suffix="iva",
        ),
    ),
)


_ENROLLMENT_SECTION = WizardSection(
    id="enrollment",
    title=tr("wizard.setup.enrollment.title"),
    questions=(
        _confirm("enrollment-large-company", "census.large_company", suffix="enrollment"),
        _confirm(
            "enrollment-public-administration-budget-gt-6000000",
            "census.public_administration_budget_gt_6000000",
            suffix="enrollment",
        ),
    ),
)


_OBLIGATIONS_SECTION = WizardSection(
    id="obligations",
    title=tr("wizard.setup.obligations.title"),
    questions=(
        _confirm("has-employees", "withholding.has_employees", suffix="obligations"),
        _confirm(
            "pays-professionals-with-retencion",
            "withholding.pays_professionals_with_retencion",
            suffix="obligations",
        ),
        _confirm(
            "professional-income-withholding-ge-70pct",
            "irpf.professional_income_withholding_ge_70pct",
            suffix="obligations",
        ),
        _confirm("pays-rent-with-retencion", "withholding.pays_rent_with_retencion", suffix="obligations"),
        _confirm(
            "pays-capital-income-with-retencion",
            "withholding.pays_capital_income_with_retencion",
            suffix="obligations",
        ),
        _confirm(
            "uses-objective-estimation-irpf",
            "irpf.uses_objective_estimation",
            suffix="obligations",
        ),
        WizardQuestion(
            id="irpf-estimation-regime",
            profile_key="irpf.estimation_regime",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.obligations.irpf-estimation-regime.prompt"),
            help=tr("wizard.setup.obligations.irpf-estimation-regime.help"),
            choices=_IRPF_ESTIMATION_REGIME_CHOICES,
            required=False,
            answer_type=str,
        ),
        _confirm("does-intracomunitario", "iva.does_intracomunitario", suffix="obligations"),
        _confirm(
            "third-party-transactions-above-347-threshold",
            "obligations.third_party_transactions_above_347_threshold",
            suffix="obligations",
        ),
        _confirm(
            "bienes-extranjero-above-threshold",
            "obligations.bienes_extranjero_above_threshold",
            suffix="obligations",
        ),
    ),
)


_RESIDENCE_SECTION = WizardSection(
    id="residence",
    title=tr("wizard.setup.residence.title"),
    questions=(
        WizardQuestion(
            id="tax-residence-ccaa",
            profile_key="tax_residence.ccaa",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.residence.tax-residence-ccaa.prompt"),
            choices=_CCAA_CHOICES,
            default=CCAA.MADRID.value,
            required=False,
            answer_type=str,
        ),
    ),
)


_NOTES_SECTION = WizardSection(
    id="notes",
    title=tr("wizard.setup.notes.title"),
    questions=(
        WizardQuestion(
            id="notes",
            profile_key="identity.notes",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.notes.notes.prompt"),
            required=False,
            answer_type=str,
        ),
    ),
)


SETUP_FLOW = WizardFlow(
    id="setup",
    title=tr("wizard.setup.title"),
    description=tr("wizard.setup.description"),
    sections=(
        _TAXPAYER_TYPE_SECTION,
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
