"""Registry-prepared setup questions for identity sections."""

from __future__ import annotations

from collections.abc import Callable

from ...core.i18n.translatable import Translatable as tr
from ...domain.contribuyente.ccaa import CCAA
from .models import WizardChoice, WizardCondition, WizardQuestion, WizardSection, WizardVisibility, WizardWidget
from .setup_questions import confirmation_question


def build_identity_section(
    profile_output_language_path: str,
    _entity_legal: WizardCondition,
    wizard_entity_type_choices: tuple[WizardChoice, ...],
    wizard_legal_entity_form_choices: tuple[WizardChoice, ...],
    wizard_output_language_choices: tuple[WizardChoice, ...],
) -> WizardSection:
    """Build the identidad section under the caller's prepared choices."""
    return WizardSection(
        id="identidad",
        title=tr("wizard.setup.identidad.title"),
        questions=(
            WizardQuestion(
                id="output-language",
                profile_key=profile_output_language_path,
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.profile.output-language.prompt"),
                choices=wizard_output_language_choices,
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
                choices=wizard_entity_type_choices,
                required=False,
                answer_type=str,
            ),
            WizardQuestion(
                id="legal-entity-form",
                profile_key="taxpayer_type.legal_entity_form",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.taxpayer-type.legal-entity-form.prompt"),
                choices=wizard_legal_entity_form_choices,
                required=False,
                visible_when=_entity_legal,
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
                visible_when=_entity_legal,
                answer_type=str,
            ),
        ),
    )


def build_residence_section(
    _fiscal_residency_default: str,
    _non_resident_irnr: WizardCondition,
    default_ccaa: Callable[[], CCAA],
    wizard_ccaa_choices: tuple[WizardChoice, ...],
    wizard_fiscal_residency_choices: tuple[WizardChoice, ...],
    wizard_m303_tax_territory_choices: tuple[WizardChoice, ...],
) -> WizardSection:
    """Build the residence section under the caller's prepared choices."""
    return WizardSection(
        id="residence",
        title=tr("wizard.setup.residence.title"),
        questions=(
            WizardQuestion(
                id="fiscal-residency",
                profile_key="taxpayer_type.fiscal_residency",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.residence.fiscal-residency.prompt"),
                choices=wizard_fiscal_residency_choices,
                default=_fiscal_residency_default,
                required=False,
                answer_type=str,
            ),
            WizardQuestion(
                id="country-of-fiscal-residence",
                profile_key="taxpayer_type.country_of_fiscal_residence",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.residence.country-of-fiscal-residence.prompt"),
                required=False,
                visible_when=_non_resident_irnr,
                answer_type=str,
            ),
            WizardQuestion(
                id="representante-fiscal-nif",
                profile_key="taxpayer_type.representante_fiscal_nif",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.residence.representante-fiscal-nif.prompt"),
                required=False,
                visible_when=_non_resident_irnr,
                answer_type=str,
            ),
            WizardQuestion(
                id="representante-fiscal-nombre",
                profile_key="taxpayer_type.representante_fiscal_nombre",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.residence.representante-fiscal-nombre.prompt"),
                required=False,
                visible_when=_non_resident_irnr,
                answer_type=str,
            ),
            WizardQuestion(
                id="tax-residence-jurisdiction-scope",
                profile_key="tax_residence.jurisdiction_scope",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.residence.tax-residence-jurisdiction-scope.prompt"),
                choices=wizard_m303_tax_territory_choices,
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
                choices=wizard_ccaa_choices,
                default=default_ccaa().value,
                required=False,
                visible_when=WizardCondition(
                    question_id="fiscal-residency",
                    equals=_fiscal_residency_default,
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


def build_activity_section(
    _entity_legal: WizardCondition,
    _has_activity: WizardVisibility,
    _natural_person: WizardCondition,
    wizard_irpf_income_category_choices: tuple[WizardChoice, ...],
    wizard_third_party_declaration_role_choices: tuple[WizardChoice, ...],
) -> WizardSection:
    """Build the actividad section under the caller's prepared choices."""
    return WizardSection(
        id="actividad",
        title=tr("wizard.setup.actividad.title"),
        questions=(
            WizardQuestion(
                id="irpf-income-categories",
                profile_key="taxpayer_type.irpf_income_categories",
                widget=WizardWidget.CHECKBOX,
                prompt=tr("wizard.setup.taxpayer-type.irpf-income-categories.prompt"),
                help=tr("wizard.setup.taxpayer-type.irpf-income-categories.help"),
                choices=wizard_irpf_income_category_choices,
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                id="declaration-roles",
                profile_key="taxpayer_type.declaration_roles",
                widget=WizardWidget.CHECKBOX,
                prompt=tr("wizard.setup.taxpayer-type.declaration-roles.prompt"),
                help=tr("wizard.setup.taxpayer-type.declaration-roles.help"),
                choices=wizard_third_party_declaration_role_choices,
                required=False,
                answer_type=str,
            ),
            WizardQuestion(
                id="activity",
                profile_key="activities.description",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.profile.activity.prompt"),
                required=False,
                visible_when=_has_activity,
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
                visible_when=_entity_legal,
                answer_type=bool,
            ),
        ),
    )


def build_preferences_section() -> WizardSection:
    """Build the preferencias section under the caller's prepared choices."""
    return WizardSection(
        id="preferencias",
        title=tr("wizard.setup.preferencias.title"),
        questions=(
            confirmation_question("llm-vision", "capabilities.llm_vision", suffix="capabilities", default="true"),
            confirmation_question("google-export", "capabilities.google_export", suffix="capabilities", default="true"),
        ),
    )
