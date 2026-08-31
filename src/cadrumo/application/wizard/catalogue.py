"""The closed catalogue of wizard flows.

Adding a new flow means appending a :class:`WizardFlow` literal to
:data:`WIZARD_FLOWS`. The catalogue is import-time pure: every
question, choice, and condition is a frozen literal and there are no
file reads or environment lookups during construction.
"""

from __future__ import annotations

from ...core.aggregation import ThirdPartyDeclarationRole
from ...core.i18n import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n import Translatable as tr
from ...core.renta_declaracion_type import RentaDeclaracionType
from ...core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH, SetupAnswers
from ...core.wizard_catalogue import register_wizard_catalogue
from ...domain.contribuyente.ccaa import CCAA
from ...domain.contribuyente.renta_codes import (
    RentaDisabilityGrade,
    RentaMaritalStatus,
    RentaSexCode,
    SituacionFamiliar,
)
from ...domain.deadlines.models import (
    EntityType,
    FiscalResidency,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    LegalEntityForm,
    M303RegimeComposition,
    M303TaxTerritory,
)
from .models import (
    WizardChoice,
    WizardCondition,
    WizardFlow,
    WizardQuestion,
    WizardSection,
    WizardVisibility,
    WizardWidget,
)


def _confirm(
    qid: str,
    profile_key: str,
    *,
    suffix: str,
    default: str | None = "false",
    required: bool = False,
    visible_when: WizardCondition | WizardVisibility | None = None,
) -> WizardQuestion:
    """Build a CONFIRM question that persists into ``profile_key``."""
    return WizardQuestion(
        id=qid,
        profile_key=profile_key,
        widget=WizardWidget.CONFIRM,
        prompt=tr(f"wizard.setup.{suffix}.{qid}.prompt"),
        default=default,
        required=required,
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


_DEFAULT_IVA_REGIME: str = IVARegime.GENERAL.value
"""Wizard default for the iva.regime question.

Shared between the :data:`_IVA_CHOICES` default-marker and the
:func:`_IVA_SECTION` question's ``default=`` so the two never drift."""


_IVA_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=_DEFAULT_IVA_REGIME,
        label=tr("wizard.setup.profile.iva-regime.choices.general.label"),
        description=tr("wizard.setup.profile.iva-regime.choices.general.description"),
    ),
    WizardChoice(
        value=IVARegime.SIMPLIFICADO.value,
        label=tr("wizard.setup.profile.iva-regime.choices.simplificado.label"),
        description=tr("wizard.setup.profile.iva-regime.choices.simplificado.description"),
    ),
    WizardChoice(
        value=IVARegime.RECARGO_EQUIVALENCIA.value,
        label=tr("wizard.setup.profile.iva-regime.choices.recargo-equivalencia.label"),
        description=tr("wizard.setup.profile.iva-regime.choices.recargo-equivalencia.description"),
    ),
    WizardChoice(
        value=IVARegime.REAGP.value,
        label=tr("wizard.setup.profile.iva-regime.choices.reagp.label"),
        description=tr("wizard.setup.profile.iva-regime.choices.reagp.description"),
    ),
    WizardChoice(
        value=IVARegime.EXENTO.value,
        label=tr("wizard.setup.profile.iva-regime.choices.exento.label"),
        description=tr("wizard.setup.profile.iva-regime.choices.exento.description"),
    ),
)

_M303_TAX_TERRITORY_LABELS: dict[M303TaxTerritory, tr] = {
    M303TaxTerritory.COMMON_REGIME: tr(
        "wizard.setup.residence.tax-residence-jurisdiction-scope.choices.common_regime.label",
    ),
    M303TaxTerritory.FORAL: tr(
        "wizard.setup.residence.tax-residence-jurisdiction-scope.choices.foral_unsupported.label",
    ),
}
_M303_TAX_TERRITORY_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=_M303_TAX_TERRITORY_LABELS[member],
    )
    for member in M303TaxTerritory
)

_M303_REGIME_COMPOSITION_LABELS: dict[M303RegimeComposition, tr] = {
    M303RegimeComposition.GENERAL: tr(
        "wizard.setup.iva.m303-regime-composition.choices.general.label",
    ),
    M303RegimeComposition.SIMPLIFIED: tr(
        "wizard.setup.iva.m303-regime-composition.choices.simplified.label",
    ),
    M303RegimeComposition.MIXED: tr(
        "wizard.setup.iva.m303-regime-composition.choices.mixed.label",
    ),
}
_M303_REGIME_COMPOSITION_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=_M303_REGIME_COMPOSITION_LABELS[member],
    )
    for member in M303RegimeComposition
)


_ENTITY_TYPE_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label"),
        description=tr(f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.description"),
    )
    for member in EntityType
)

# Only the forms whose choice carries curated explainer copy; the rest render
# label-only (an unlisted member must never mint an unresolvable description ref).
_DESCRIBED_LEGAL_ENTITY_FORMS = frozenset({"sl", "sin_fines_lucrativos"})

_LEGAL_ENTITY_FORM_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label"),
        description=(
            tr(f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.description")
            if member.value in _DESCRIBED_LEGAL_ENTITY_FORMS
            else None
        ),
    )
    for member in LegalEntityForm
)

_IRPF_INCOME_CATEGORY_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.label"),
        description=tr(
            f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.description",
        ),
    )
    for member in IrpfIncomeCategory
)

_THIRD_PARTY_DECLARATION_ROLE_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.taxpayer-type.declaration-roles.choices.{member.value.replace('_', '-')}.label"),
        description=tr(
            f"wizard.setup.taxpayer-type.declaration-roles.choices.{member.value.replace('_', '-')}.description",
        ),
    )
    for member in ThirdPartyDeclarationRole
)

_IRPF_ESTIMATION_REGIME_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.obligations.irpf-estimation-regime.choices.{member.value.replace('_', '-')}.label"),
        description=tr(
            f"wizard.setup.obligations.irpf-estimation-regime.choices.{member.value.replace('_', '-')}.description",
        ),
    )
    for member in IrpfEstimationRegime
)

_IRPF_SPECIAL_REGIME_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.obligations.irpf-special-regime.choices.{member.value.replace('_', '-')}.label"),
    )
    for member in IrpfSpecialRegime
)

_IMPATRIADO_REGIME = WizardCondition(question_id="irpf-special-regime", equals=IrpfSpecialRegime.IMPATRIADO.value)
_IRPF_OBJECTIVE_ESTIMATION = WizardCondition(
    question_id="irpf-estimation-regime",
    equals=IrpfEstimationRegime.OBJETIVA.value,
)

_FISCAL_RESIDENCY_CHOICES: tuple[WizardChoice, ...] = tuple(
    WizardChoice(
        value=member.value,
        label=tr(f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label"),
        description=tr(f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.description"),
    )
    for member in FiscalResidency
)

_NON_RESIDENT_IRNR = WizardCondition(question_id="fiscal-residency", equals=FiscalResidency.NON_RESIDENT_IRNR.value)


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
    WizardChoice(
        value=RentaMaritalStatus.PAREJA_HECHO.value,
        label=tr("wizard.setup.taxpayer.taxpayer-marital-status.choices.pareja-hecho.label"),
    ),
)

_SITUACION_FAMILIAR_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=SituacionFamiliar.CASADO.value,
        label=tr("wizard.setup.taxpayer.situacion-familiar.choices.casado.label"),
        description=tr("wizard.setup.taxpayer.situacion-familiar.choices.casado.description"),
    ),
    WizardChoice(
        value=SituacionFamiliar.PAREJA_HECHO_REGISTRADA.value,
        label=tr("wizard.setup.taxpayer.situacion-familiar.choices.pareja-hecho-registrada.label"),
        description=tr("wizard.setup.taxpayer.situacion-familiar.choices.pareja-hecho-registrada.description"),
    ),
    WizardChoice(
        value=SituacionFamiliar.PAREJA_HECHO_NO_REGISTRADA.value,
        label=tr("wizard.setup.taxpayer.situacion-familiar.choices.pareja-hecho-no-registrada.label"),
        description=tr("wizard.setup.taxpayer.situacion-familiar.choices.pareja-hecho-no-registrada.description"),
    ),
    WizardChoice(
        value=SituacionFamiliar.SOLTERO.value,
        label=tr("wizard.setup.taxpayer.situacion-familiar.choices.soltero.label"),
        description=tr("wizard.setup.taxpayer.situacion-familiar.choices.soltero.description"),
    ),
    WizardChoice(
        value=SituacionFamiliar.SEPARADO_DIVORCIADO.value,
        label=tr("wizard.setup.taxpayer.situacion-familiar.choices.separado-divorciado.label"),
        description=tr("wizard.setup.taxpayer.situacion-familiar.choices.separado-divorciado.description"),
    ),
)

_DISABILITY_GRADE_CHOICES: tuple[WizardChoice, ...] = (
    WizardChoice(
        value=RentaDisabilityGrade.GE_33_LT_65.value,
        label=tr("wizard.setup.codes.disability-grade.choices.33-64.label"),
        description=tr("wizard.setup.codes.disability-grade.choices.33-64.description"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.GE_65.value,
        label=tr("wizard.setup.codes.disability-grade.choices.65-plus.label"),
        description=tr("wizard.setup.codes.disability-grade.choices.65-plus.description"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.JUDICIAL_INCAPACITY.value,
        label=tr("wizard.setup.codes.disability-grade.choices.judicial-incapacity.label"),
        description=tr("wizard.setup.codes.disability-grade.choices.judicial-incapacity.description"),
    ),
    WizardChoice(
        value=RentaDisabilityGrade.ASSISTANCE_OR_REDUCED_MOBILITY.value,
        label=tr("wizard.setup.codes.disability-grade.choices.assistance-or-mobility.label"),
        description=tr("wizard.setup.codes.disability-grade.choices.assistance-or-mobility.description"),
    ),
)


_ENTITY_LEGAL = WizardCondition(question_id="entity-type", equals=EntityType.LEGAL_ENTITY.value)
_ENTITY_ATTRIBUTION = WizardCondition(question_id="entity-type", equals=EntityType.ATTRIBUTION_ENTITY.value)
_LEY_49_2002_FORM = WizardCondition(
    question_id="legal-entity-form",
    equals=LegalEntityForm.SIN_FINES_LUCRATIVOS.value,
)
_LEY_49_2002_OPTION_DECLARED = WizardCondition(question_id="ley-49-2002-option-declared", equals="true")
_LEY_49_2002_RENUNCIATION_DECLARED = WizardCondition(
    question_id="ley-49-2002-renunciation-declared",
    equals="true",
)

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
    ),
)
_IVA_REGIME_VISIBLE = WizardVisibility(
    any_of=(
        _ENTITY_LEGAL,
        _ENTITY_ATTRIBUTION,
        WizardCondition(question_id="irpf-income-categories", contains=IrpfIncomeCategory.ACTIVIDAD_ECONOMICA.value),
    ),
)

# Every question whose answer CLAIMS the IVA block is gated here, not on
# _IVA_REGIME_VISIBLE. Declaring any IVA fact obliges the whole block, so a
# gate that admits one block-owned question without admitting the questions
# the block requires produces a profile the domain resolver then refuses. Six
# enrolment confirms sat on the entity-shaped gate while the facts they oblige
# sat on this one, so answering "no" to ROI without declaring a regime built a
# claimed block the wizard never finished asking about.
_IVA_BLOCK_CLAIMED = WizardVisibility(
    any_of=tuple(
        WizardCondition(question_id="iva-regime", equals=member.value)
        for member in IVARegime
        if member is not IVARegime.NO_APLICA
    ),
)


_IDENTIDAD_SECTION = WizardSection(
    id="identidad",
    title=tr("wizard.setup.identidad.title"),
    questions=(
        WizardQuestion(
            id="output-language",
            profile_key=PROFILE_OUTPUT_LANGUAGE_PATH,
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.profile.output-language.prompt"),
            choices=_OUTPUT_LANGUAGE_CHOICES,
            default="es",
            required=False,
            answer_type=str,
        ),
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
            id="legal-name",
            profile_key="identity.legal_name",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.legal-name.prompt"),
            help=tr("wizard.setup.profile.legal-name.help"),
            required=False,
            visible_when=_ENTITY_LEGAL,
            answer_type=str,
        ),
    ),
)


_RESIDENCE_SECTION = WizardSection(
    id="residence",
    title=tr("wizard.setup.residence.title"),
    questions=(
        WizardQuestion(
            id="fiscal-residency",
            profile_key="taxpayer_type.fiscal_residency",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.residence.fiscal-residency.prompt"),
            choices=_FISCAL_RESIDENCY_CHOICES,
            default=FiscalResidency.RESIDENT_IRPF.value,
            required=False,
            answer_type=str,
        ),
        WizardQuestion(
            id="country-of-fiscal-residence",
            profile_key="taxpayer_type.country_of_fiscal_residence",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.residence.country-of-fiscal-residence.prompt"),
            required=False,
            visible_when=_NON_RESIDENT_IRNR,
            answer_type=str,
        ),
        WizardQuestion(
            id="representante-fiscal-nif",
            profile_key="taxpayer_type.representante_fiscal_nif",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.residence.representante-fiscal-nif.prompt"),
            required=False,
            visible_when=_NON_RESIDENT_IRNR,
            answer_type=str,
        ),
        WizardQuestion(
            id="representante-fiscal-nombre",
            profile_key="taxpayer_type.representante_fiscal_nombre",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.residence.representante-fiscal-nombre.prompt"),
            required=False,
            visible_when=_NON_RESIDENT_IRNR,
            answer_type=str,
        ),
        WizardQuestion(
            id="tax-residence-jurisdiction-scope",
            profile_key="tax_residence.jurisdiction_scope",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.residence.tax-residence-jurisdiction-scope.prompt"),
            choices=_M303_TAX_TERRITORY_CHOICES,
            required=True,
            answer_type=str,
        ),
        WizardQuestion(
            # IRNR non-residents have no CCAA residencia fiscal; only
            # IRPF residents are assigned a CCAA. Suppress the question
            # for NON_RESIDENT_IRNR so the wizard never silently defaults
            # a non-resident onto "madrid".
            id="tax-residence-ccaa",
            profile_key="tax_residence.ccaa",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.residence.tax-residence-ccaa.prompt"),
            choices=_CCAA_CHOICES,
            default=CCAA.MADRID.value,
            required=False,
            visible_when=WizardCondition(
                question_id="fiscal-residency",
                equals=FiscalResidency.RESIDENT_IRPF.value,
            ),
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
    ),
)


_ACTIVIDAD_SECTION = WizardSection(
    id="actividad",
    title=tr("wizard.setup.actividad.title"),
    questions=(
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
            id="declaration-roles",
            profile_key="taxpayer_type.declaration_roles",
            widget=WizardWidget.CHECKBOX,
            prompt=tr("wizard.setup.taxpayer-type.declaration-roles.prompt"),
            help=tr("wizard.setup.taxpayer-type.declaration-roles.help"),
            choices=_THIRD_PARTY_DECLARATION_ROLE_CHOICES,
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
            # Optional censo alta date. When set, the deadline engine
            # suppresses obligation windows that close before it, so a
            # recent registrant is not shown overdue returns for periods
            # that precede their alta.
            id="activity-start-date",
            profile_key="censo.activity_start_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.activity-start-date.prompt"),
            help=tr("wizard.setup.profile.activity-start-date.help"),
            required=False,
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
            # entity_type == legal_entity. No descriptor default: the
            # override is opt-in and three-state. A profile that has
            # not declared the fact must persist nothing, so the typed
            # projection reloads as ``None`` (undeclared) — never
            # collapsed onto declared-``False`` by a default value the
            # operator never approved. A positively-declared
            # ``--new-entity-first-two-profit-periods`` writes ``true``
            # and opts into the override; ``--no-new-entity-...`` writes
            # ``false`` and positively declines it.
            id="new-entity-first-two-profit-periods",
            profile_key="taxpayer_type.new_entity_first_two_profit_periods",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.taxpayer-type.new-entity-first-two-profit-periods.prompt"),
            help=tr("wizard.setup.taxpayer-type.new-entity-first-two-profit-periods.help"),
            required=False,
            visible_when=_ENTITY_LEGAL,
            answer_type=bool,
        ),
        WizardQuestion(
            id="ley-49-2002-option-declared",
            profile_key="taxpayer_type.ley_49_2002_special_regime_option_declared",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.taxpayer-type.ley-49-2002-option-declared.prompt"),
            help=tr("wizard.setup.taxpayer-type.ley-49-2002-option-declared.help"),
            required=False,
            visible_when=_LEY_49_2002_FORM,
            answer_type=bool,
        ),
        WizardQuestion(
            id="ley-49-2002-option-date",
            profile_key="taxpayer_type.ley_49_2002_special_regime_option_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer-type.ley-49-2002-option-date.prompt"),
            help=tr("wizard.setup.taxpayer-type.ley-49-2002-option-date.help"),
            required=False,
            visible_when=_LEY_49_2002_OPTION_DECLARED,
            answer_type=str,
        ),
        WizardQuestion(
            id="ley-49-2002-renunciation-declared",
            profile_key="taxpayer_type.ley_49_2002_special_regime_renunciation_declared",
            widget=WizardWidget.CONFIRM,
            prompt=tr("wizard.setup.taxpayer-type.ley-49-2002-renunciation-declared.prompt"),
            help=tr("wizard.setup.taxpayer-type.ley-49-2002-renunciation-declared.help"),
            required=False,
            visible_when=_LEY_49_2002_FORM,
            answer_type=bool,
        ),
        WizardQuestion(
            id="ley-49-2002-renunciation-date",
            profile_key="taxpayer_type.ley_49_2002_special_regime_renunciation_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer-type.ley-49-2002-renunciation-date.prompt"),
            help=tr("wizard.setup.taxpayer-type.ley-49-2002-renunciation-date.help"),
            required=False,
            visible_when=_LEY_49_2002_RENUNCIATION_DECLARED,
            answer_type=str,
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
            prompt=tr("wizard.setup.profile.iva-regime.prompt"),
            choices=_IVA_CHOICES,
            required=False,
            visible_when=_IVA_REGIME_VISIBLE,
            answer_type=str,
        ),
        WizardQuestion(
            id="iva-m303-regime-composition",
            profile_key="iva.m303_regime_composition",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.iva.m303-regime-composition.prompt"),
            choices=_M303_REGIME_COMPOSITION_CHOICES,
            required=True,
            visible_when=_IVA_BLOCK_CLAIMED,
            answer_type=str,
        ),
        _confirm(
            "iva-roi-enrolled",
            "iva.roi_enrolled",
            suffix="iva",
            default=None,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-oss-enrolled",
            "iva.oss_enrolled",
            suffix="iva",
            default=None,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-group-member-enrolled",
            "iva.group_member_enrolled",
            suffix="iva",
            default=None,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-group-dominant-entity-enrolled",
            "iva.group_dominant_entity_enrolled",
            suffix="iva",
            default=None,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-sii-enrolled",
            "iva.sii_enrolled",
            suffix="iva",
            default=None,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-redeme-enrolled",
            "iva.redeme_enrolled",
            suffix="iva",
            default=None,
            required=True,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-intracommunity-operations-exceed-50000-eur",
            "iva.intracommunity_operations_exceed_50000_eur",
            suffix="iva",
            default=None,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-cash-accounting-regime-enrolled",
            "iva.cash_accounting_regime_enrolled",
            suffix="iva",
            default=None,
            required=True,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-voluntary-sii-enrolled",
            "iva.voluntary_sii_enrolled",
            suffix="iva",
            default=None,
            required=True,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
        _confirm(
            "iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
            suffix="iva",
            default=None,
            required=True,
            visible_when=_IVA_BLOCK_CLAIMED,
        ),
    ),
)


_ENROLLMENT_SECTION = WizardSection(
    id="enrollment",
    title=tr("wizard.setup.enrollment.title"),
    questions=(
        _confirm("enrollment-large-company", "censo.large_company", suffix="enrollment"),
        _confirm(
            "enrollment-public-administration-budget-gt-6000000",
            "censo.public_administration_budget_gt_6000000",
            suffix="enrollment",
        ),
    ),
)


_FAMILIA_SECTION = WizardSection(
    id="familia",
    title=tr("wizard.setup.familia.title"),
    questions=(
        WizardQuestion(
            id="taxation-type",
            profile_key="renta_filing.declaration_type",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.profile.taxation-type.prompt"),
            choices=_DECLARATION_TYPE_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
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
            # Art. 82 LIRPF: situación familiar determines whether conjunta
            # (joint) taxation is available and which unidad-familiar variant
            # applies. Distinct from the Modelo 100 marital-status code
            # (which maps to form rows); this axis drives the verifier check
            # and future casilla routing.
            id="situacion-familiar",
            profile_key="renta_family.situacion_familiar",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.taxpayer.situacion-familiar.prompt"),
            help=tr("wizard.setup.taxpayer.situacion-familiar.help"),
            choices=_SITUACION_FAMILIAR_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            # Art. 82.1 LIRPF: matrimonio sobrevenido — records the date the
            # current marriage began.  Drives casillas 0245 (vigente todo el año),
            # 0246 (primer mes), and 0247 (último mes completo).  Only asked when
            # the taxpayer is married (marital_status = "2").
            id="taxpayer-marriage-date",
            profile_key="renta_taxpayer.marriage_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.taxpayer.taxpayer-marriage-date.prompt"),
            required=False,
            visible_when=WizardCondition(question_id="taxpayer-marital-status", equals=RentaMaritalStatus.CASADO.value),
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
            "art109-activity-income-withholding-ge-70pct",
            "irpf.art109_activity_income_withholding_ge_70pct",
            suffix="obligations",
        ),
        _confirm("pays-rent-with-retencion", "withholding.pays_rent_with_retencion", suffix="obligations"),
        _confirm(
            "pays-capital-income-with-retencion",
            "withholding.pays_capital_income_with_retencion",
            suffix="obligations",
        ),
        WizardQuestion(
            id="modelo-111-no-retenciones-periods",
            profile_key="withholding.modelo_111_no_retenciones_periods",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.modelo-111-no-retenciones-periods.prompt"),
            help=tr("wizard.setup.obligations.modelo-111-no-retenciones-periods.help"),
            required=False,
            answer_type=str,
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
        WizardQuestion(
            id="objective-estimation-modulos-iae-epigraph",
            profile_key="irpf.objective_estimation_modulos_iae_epigraph",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-iae-epigraph.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-iae-epigraph.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="objective-estimation-modulos-module-1-units",
            profile_key="irpf.objective_estimation_modulos_module_1_units",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-module-1-units.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-module-units.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="objective-estimation-modulos-module-2-units",
            profile_key="irpf.objective_estimation_modulos_module_2_units",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-module-2-units.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-module-units.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="objective-estimation-modulos-module-3-units",
            profile_key="irpf.objective_estimation_modulos_module_3_units",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-module-3-units.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-module-units.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="objective-estimation-modulos-module-4-units",
            profile_key="irpf.objective_estimation_modulos_module_4_units",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-module-4-units.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-module-units.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="objective-estimation-modulos-module-5-units",
            profile_key="irpf.objective_estimation_modulos_module_5_units",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-module-5-units.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-module-units.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="objective-estimation-modulos-module-6-units",
            profile_key="irpf.objective_estimation_modulos_module_6_units",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-module-6-units.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-module-units.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="objective-estimation-modulos-module-7-units",
            profile_key="irpf.objective_estimation_modulos_module_7_units",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.objective-estimation-modulos-module-7-units.prompt"),
            help=tr("wizard.setup.obligations.objective-estimation-modulos-module-units.help"),
            required=False,
            visible_when=_IRPF_OBJECTIVE_ESTIMATION,
            answer_type=str,
        ),
        WizardQuestion(
            id="irpf-special-regime",
            profile_key="irpf.special_regime",
            widget=WizardWidget.SELECT,
            prompt=tr("wizard.setup.obligations.irpf-special-regime.prompt"),
            help=tr("wizard.setup.obligations.irpf-special-regime.help"),
            choices=_IRPF_SPECIAL_REGIME_CHOICES,
            required=False,
            visible_when=_NATURAL_PERSON,
            answer_type=str,
        ),
        WizardQuestion(
            id="irpf-special-regime-start-date",
            profile_key="irpf.special_regime_start_date",
            widget=WizardWidget.TEXT,
            prompt=tr("wizard.setup.obligations.irpf-special-regime-start-date.prompt"),
            help=tr("wizard.setup.obligations.irpf-special-regime-start-date.help"),
            required=False,
            visible_when=_IMPATRIADO_REGIME,
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
        _confirm(
            "monedas-virtuales-extranjero-above-threshold",
            "obligations.monedas_virtuales_extranjero_above_threshold",
            suffix="obligations",
        ),
    ),
)


_PREFERENCIAS_SECTION = WizardSection(
    id="preferencias",
    title=tr("wizard.setup.preferencias.title"),
    questions=(
        _confirm("llm-vision", "capabilities.llm_vision", suffix="capabilities", default="true"),
        _confirm("google-export", "capabilities.google_export", suffix="capabilities", default="true"),
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
        _IDENTIDAD_SECTION,
        _RESIDENCE_SECTION,
        _ACTIVIDAD_SECTION,
        _IVA_SECTION,
        _ENROLLMENT_SECTION,
        _FAMILIA_SECTION,
        _OBLIGATIONS_SECTION,
        _PREFERENCIAS_SECTION,
    ),
    answers_model=SetupAnswers,
)


WIZARD_FLOWS: tuple[WizardFlow, ...] = (SETUP_FLOW,)

# Register the canonical descriptors into the core slot so domain modules
# that import from cadrumo.core.wizard_catalogue receive the real objects
# without making upward imports into the application layer.
register_wizard_catalogue(SETUP_FLOW, WIZARD_FLOWS)


__all__ = ["SETUP_FLOW", "WIZARD_FLOWS"]
