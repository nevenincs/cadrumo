"""Registry-prepared setup questions for tax sections."""

from __future__ import annotations

from ...core.i18n.translatable import Translatable as tr
from .models import WizardChoice, WizardCondition, WizardQuestion, WizardSection, WizardVisibility, WizardWidget
from .setup_questions import confirmation_question


def build_iva_section(
    _iva_block_claimed: WizardVisibility,
    _iva_regime_visible: WizardVisibility,
    wizard_iva_choices: tuple[WizardChoice, ...],
    wizard_m303_regime_composition_choices: tuple[WizardChoice, ...],
) -> WizardSection:
    """Build the iva section under the caller's prepared choices."""
    return WizardSection(
        id="iva",
        title=tr("wizard.setup.iva.title"),
        questions=(
            WizardQuestion(
                id="iva-regime",
                profile_key="iva.regime",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.profile.iva-regime.prompt"),
                choices=wizard_iva_choices,
                required=False,
                visible_when=_iva_regime_visible,
                answer_type=str,
            ),
            WizardQuestion(
                id="iva-m303-regime-composition",
                profile_key="iva.m303_regime_composition",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.iva.m303-regime-composition.prompt"),
                choices=wizard_m303_regime_composition_choices,
                required=True,
                visible_when=_iva_block_claimed,
                answer_type=str,
            ),
            confirmation_question(
                "iva-roi-enrolled",
                "iva.roi_enrolled",
                suffix="iva",
                default=None,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-oss-enrolled",
                "iva.oss_enrolled",
                suffix="iva",
                default=None,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-group-member-enrolled",
                "iva.group_member_enrolled",
                suffix="iva",
                default=None,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-group-dominant-entity-enrolled",
                "iva.group_dominant_entity_enrolled",
                suffix="iva",
                default=None,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-sii-enrolled",
                "iva.sii_enrolled",
                suffix="iva",
                default=None,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-redeme-enrolled",
                "iva.redeme_enrolled",
                suffix="iva",
                default=None,
                required=True,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-intracommunity-operations-exceed-50000-eur",
                "iva.intracommunity_operations_exceed_50000_eur",
                suffix="iva",
                default=None,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-cash-accounting-regime-enrolled",
                "iva.cash_accounting_regime_enrolled",
                suffix="iva",
                default=None,
                required=True,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-voluntary-sii-enrolled",
                "iva.voluntary_sii_enrolled",
                suffix="iva",
                default=None,
                required=True,
                visible_when=_iva_block_claimed,
            ),
            confirmation_question(
                "iva-hydrocarbon-deposit-advance-payment-deduction-entitled",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
                suffix="iva",
                default=None,
                required=True,
                visible_when=_iva_block_claimed,
            ),
        ),
    )


def build_enrollment_section() -> WizardSection:
    """Build the enrollment section under the caller's prepared choices."""
    return WizardSection(
        id="enrollment",
        title=tr("wizard.setup.enrollment.title"),
        questions=(
            confirmation_question("enrollment-large-company", "censo.large_company", suffix="enrollment"),
            confirmation_question(
                "enrollment-public-administration-budget-gt-6000000",
                "censo.public_administration_budget_gt_6000000",
                suffix="enrollment",
            ),
        ),
    )


def build_obligations_section(
    _impatriado_regime: WizardCondition,
    _natural_person: WizardCondition,
    _premio_loteria_declared: WizardCondition,
    wizard_irpf_estimation_regime_choices: tuple[WizardChoice, ...],
    wizard_irpf_special_regime_choices: tuple[WizardChoice, ...],
) -> WizardSection:
    """Build the obligations section under the caller's prepared choices."""
    return WizardSection(
        id="obligations",
        title=tr("wizard.setup.obligations.title"),
        questions=(
            confirmation_question("has-employees", "withholding.has_employees", suffix="obligations"),
            confirmation_question(
                "pays-professionals-with-retencion",
                "withholding.pays_professionals_with_retencion",
                suffix="obligations",
            ),
            confirmation_question(
                "art109-activity-income-withholding-ge-70pct",
                "irpf.art109_activity_income_withholding_ge_70pct",
                suffix="obligations",
            ),
            confirmation_question(
                "pays-rent-with-retencion", "withholding.pays_rent_with_retencion", suffix="obligations"
            ),
            confirmation_question(
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
                id="modelo-115-no-relevant-payment-periods",
                profile_key="withholding.modelo_115_no_relevant_payment_periods",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.obligations.modelo-115-no-relevant-payment-periods.prompt"),
                help=tr("wizard.setup.obligations.modelo-115-no-relevant-payment-periods.help"),
                required=False,
                answer_type=str,
            ),
            WizardQuestion(
                id="irpf-estimation-regime",
                profile_key="irpf.estimation_regime",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.obligations.irpf-estimation-regime.prompt"),
                help=tr("wizard.setup.obligations.irpf-estimation-regime.help"),
                choices=wizard_irpf_estimation_regime_choices,
                required=False,
                answer_type=str,
            ),
            WizardQuestion(
                id="irpf-special-regime",
                profile_key="irpf.special_regime",
                widget=WizardWidget.SELECT,
                prompt=tr("wizard.setup.obligations.irpf-special-regime.prompt"),
                help=tr("wizard.setup.obligations.irpf-special-regime.help"),
                choices=wizard_irpf_special_regime_choices,
                required=False,
                visible_when=_natural_person,
                answer_type=str,
            ),
            WizardQuestion(
                id="irpf-special-regime-start-date",
                profile_key="irpf.special_regime_start_date",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.obligations.irpf-special-regime-start-date.prompt"),
                help=tr("wizard.setup.obligations.irpf-special-regime-start-date.help"),
                required=False,
                visible_when=_impatriado_regime,
                answer_type=str,
            ),
            confirmation_question("does-intracomunitario", "iva.does_intracomunitario", suffix="obligations"),
            # Payer-fact questions carry no default: an unanswered question
            # stays absent, so it reads as undeclared rather than as a "no".
            confirmation_question(
                "third-party-transactions-above-347-threshold",
                "obligations.third_party_transactions_above_347_threshold",
                suffix="obligations",
                default=None,
            ),
            confirmation_question(
                "bienes-extranjero-above-threshold",
                "obligations.bienes_extranjero_above_threshold",
                suffix="obligations",
                default=None,
            ),
            confirmation_question(
                "monedas-virtuales-extranjero-above-threshold",
                "obligations.monedas_virtuales_extranjero_above_threshold",
                suffix="obligations",
                default=None,
            ),
            confirmation_question(
                "premio-loteria-gravamen-especial-sin-retencion",
                "obligations.premio_loteria_gravamen_especial_sin_retencion",
                suffix="obligations",
                default=None,
                visible_when=_natural_person,
            ),
            WizardQuestion(
                id="premio-loteria-gravamen-especial-trimestres",
                profile_key="obligations.premio_loteria_gravamen_especial_trimestres",
                widget=WizardWidget.TEXT,
                prompt=tr("wizard.setup.obligations.premio-loteria-gravamen-especial-trimestres.prompt"),
                help=tr("wizard.setup.obligations.premio-loteria-gravamen-especial-trimestres.help"),
                required=False,
                visible_when=_premio_loteria_declared,
                answer_type=str,
            ),
        ),
    )
