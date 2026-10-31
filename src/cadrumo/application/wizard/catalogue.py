"""Operation-scoped construction of the wizard flow catalogue.

The descriptor is built only by :func:`build_setup_flow`, while a caller holds
one leased indexed authority operation.  Importing this module is therefore
safe for metadata/help paths and cannot silently select a process-global
registry generation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import partial
from typing import TYPE_CHECKING, Final, Protocol

from ...core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n.translatable import Translatable as tr
from ...domain.contribuyente.renta_codes import (
    RentaDeclaracionType,
    RentaDisabilityGrade,
    RentaMaritalStatus,
    RentaSexCode,
)
from .models import (
    WizardChoice,
    WizardCondition,
    WizardFlow,
    WizardVisibility,
)
from .setup_family_sections import build_family_section
from .setup_identity_sections import (
    build_activity_section,
    build_identity_section,
    build_preferences_section,
    build_residence_section,
)
from .setup_tax_sections import build_enrollment_section, build_iva_section, build_obligations_section

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


class _RegistryToken(Protocol):
    @property
    def value(self) -> str: ...


def _localized_choice(value: str, label_key: str, description_key: str | None = None) -> WizardChoice:
    """Create one choice from its canonical token and reviewed copy keys."""
    return WizardChoice(
        value=value,
        label=tr(label_key),
        description=tr(description_key) if description_key is not None else None,
    )


def _build_iva_m303_choices(
    operation: PinnedAuthorityOperation,
    iva_regime_tokens: Sequence[_RegistryToken],
) -> tuple[tuple[WizardChoice, ...], tuple[WizardChoice, ...], tuple[WizardChoice, ...]]:
    from ...domain.calculations.registry.m303_schema_vocabulary import (
        m303_regime_composition_choices,
        m303_tax_territory_choices,
    )

    wizard_iva_choices = tuple(
        _localized_choice(
            token.value,
            f"wizard.setup.profile.iva-regime.choices.{token.value.lower().replace('_', '-')}.label",
            f"wizard.setup.profile.iva-regime.choices.{token.value.lower().replace('_', '-')}.description",
        )
        for token in iva_regime_tokens
    )
    wizard_m303_tax_territory_choices = tuple(
        _localized_choice(
            token.value,
            f"wizard.setup.residence.tax-residence-jurisdiction-scope.choices.{token.value}.label",
        )
        for token in m303_tax_territory_choices(authority=operation)
    )
    wizard_m303_regime_composition_choices = tuple(
        _localized_choice(
            token.value,
            f"wizard.setup.iva.m303-regime-composition.choices.{token.value}.label",
        )
        for token in m303_regime_composition_choices(authority=operation)
    )
    return wizard_iva_choices, wizard_m303_tax_territory_choices, wizard_m303_regime_composition_choices


def _build_entity_choices(
    operation: PinnedAuthorityOperation,
) -> tuple[tuple[WizardChoice, ...], tuple[WizardChoice, ...]]:
    from ...domain.calculations.registry.entity_type import (
        entity_type_tokens,
        legal_entity_form_choice_description_tokens,
        legal_entity_form_tokens,
    )

    wizard_entity_type_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.label",
            f"wizard.setup.taxpayer-type.entity-type.choices.{member.value.replace('_', '-')}.description",
        )
        for member in entity_type_tokens(authority=operation)
    )
    described_forms = frozenset(
        member.value for member in legal_entity_form_choice_description_tokens(authority=operation)
    )
    wizard_legal_entity_form_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label",
            (
                f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.description"
                if member.value in described_forms
                else None
            ),
        )
        for member in legal_entity_form_tokens(authority=operation)
    )
    return wizard_entity_type_choices, wizard_legal_entity_form_choices


def _build_irpf_choices(
    operation: PinnedAuthorityOperation,
) -> tuple[
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
    WizardCondition,
]:
    from ...domain.calculations.registry.irpf_income_categories import irpf_income_category_choices
    from ...domain.calculations.registry.irpf_regimes import (
        irpf_estimation_regime_tokens,
        irpf_special_regime_impatriado_token,
        irpf_special_regime_tokens,
    )
    from ...domain.calculations.registry.third_party_declaration_roles import third_party_declaration_role_choices

    wizard_irpf_income_category_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.label",
            f"wizard.setup.taxpayer-type.irpf-income-categories.choices.{member.value.replace('_', '-')}.description",
        )
        for member in irpf_income_category_choices(authority=operation)
    )
    wizard_third_party_declaration_role_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.taxpayer-type.declaration-roles.choices.{member.value.replace('_', '-')}.label",
            f"wizard.setup.taxpayer-type.declaration-roles.choices.{member.value.replace('_', '-')}.description",
        )
        for member in third_party_declaration_role_choices(authority=operation)
    )
    wizard_irpf_estimation_regime_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.obligations.irpf-estimation-regime.choices.{member.value.replace('_', '-')}.label",
            f"wizard.setup.obligations.irpf-estimation-regime.choices.{member.value.replace('_', '-')}.description",
        )
        for member in irpf_estimation_regime_tokens(authority=operation)
    )
    wizard_irpf_special_regime_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.obligations.irpf-special-regime.choices.{member.value.replace('_', '-')}.label",
            f"wizard.setup.obligations.irpf-special-regime.choices.{member.value.replace('_', '-')}.description",
        )
        for member in irpf_special_regime_tokens(authority=operation)
    )
    _impatriado_regime = WizardCondition(
        question_id="irpf-special-regime",
        equals=irpf_special_regime_impatriado_token(authority=operation).value,
    )
    return (
        wizard_irpf_income_category_choices,
        wizard_third_party_declaration_role_choices,
        wizard_irpf_estimation_regime_choices,
        wizard_irpf_special_regime_choices,
        _impatriado_regime,
    )


def _build_residence_choices(
    operation: PinnedAuthorityOperation,
) -> tuple[tuple[WizardChoice, ...], str, WizardCondition, tuple[WizardChoice, ...]]:
    from ...domain.calculations.registry.ccaa_catalogue import ccaa_choices
    from ...domain.calculations.registry.renta_codes_catalogue import (
        default_fiscal_residency,
        fiscal_residency_choices,
        fiscal_residency_requires_country,
    )

    wizard_fiscal_residency_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label",
            f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.description",
        )
        for member in fiscal_residency_choices(authority=operation)
    )
    _fiscal_residency_default = default_fiscal_residency(authority=operation).value
    _non_resident_irnr = WizardCondition(
        question_id="fiscal-residency",
        equals=next(
            member.value
            for member in fiscal_residency_choices(authority=operation)
            if fiscal_residency_requires_country(member)
        ),
    )
    wizard_ccaa_choices = tuple(
        _localized_choice(member.value, f"wizard.setup.residence.ccaa.choices.{member.value}.label")
        for member in ccaa_choices(authority=operation)
    )
    return wizard_fiscal_residency_choices, _fiscal_residency_default, _non_resident_irnr, wizard_ccaa_choices


def _build_profile_and_personal_choices(
    operation: PinnedAuthorityOperation,
) -> tuple[
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
    tuple[WizardChoice, ...],
]:
    from ...domain.calculations.registry.situacion_familiar_catalogue import situacion_familiar_choices

    wizard_output_language_choices = tuple(
        _localized_choice(language, f"wizard.setup.profile.output-language.choices.{language}.label")
        for language in SUPPORTED_OUTPUT_LANGUAGES
    )
    declaration_type_codes = RentaDeclaracionType.form_codes(authority=operation)
    sex_codes = RentaSexCode.form_codes(authority=operation)
    marital_status_codes = RentaMaritalStatus.form_codes(authority=operation)
    disability_grade_codes = RentaDisabilityGrade.form_codes(authority=operation)
    wizard_declaration_type_choices = (
        _localized_choice(
            declaration_type_codes[RentaDeclaracionType.INDIVIDUAL],
            "wizard.setup.profile.taxation-type.choices.individual.label",
            "wizard.setup.profile.taxation-type.choices.individual.description",
        ),
        _localized_choice(
            declaration_type_codes[RentaDeclaracionType.JOINT],
            "wizard.setup.profile.taxation-type.choices.joint.label",
            "wizard.setup.profile.taxation-type.choices.joint.description",
        ),
    )
    wizard_sex_choices = (
        _localized_choice(sex_codes[RentaSexCode.HOMBRE], "wizard.setup.codes.sex.choices.h.label"),
        _localized_choice(sex_codes[RentaSexCode.MUJER], "wizard.setup.codes.sex.choices.m.label"),
    )
    wizard_marital_status_choices = (
        _localized_choice(
            marital_status_codes[RentaMaritalStatus.SOLTERO],
            "wizard.setup.taxpayer.taxpayer-marital-status.choices.soltero.label",
        ),
        _localized_choice(
            marital_status_codes[RentaMaritalStatus.CASADO],
            "wizard.setup.taxpayer.taxpayer-marital-status.choices.casado.label",
        ),
        _localized_choice(
            marital_status_codes[RentaMaritalStatus.VIUDO],
            "wizard.setup.taxpayer.taxpayer-marital-status.choices.viudo.label",
        ),
        _localized_choice(
            marital_status_codes[RentaMaritalStatus.SEPARADO_DIVORCIADO],
            "wizard.setup.taxpayer.taxpayer-marital-status.choices.separado-divorciado.label",
        ),
        _localized_choice(
            marital_status_codes[RentaMaritalStatus.PAREJA_HECHO],
            "wizard.setup.taxpayer.taxpayer-marital-status.choices.pareja-hecho.label",
        ),
    )
    wizard_situacion_familiar_choices = tuple(
        _localized_choice(
            member.value,
            f"wizard.setup.taxpayer.situacion-familiar.choices.{member.value.replace('_', '-')}.label",
            f"wizard.setup.taxpayer.situacion-familiar.choices.{member.value.replace('_', '-')}.description",
        )
        for member in situacion_familiar_choices(authority=operation)
    )
    wizard_disability_grade_choices = (
        _localized_choice(
            disability_grade_codes[RentaDisabilityGrade.GE_33_LT_65],
            "wizard.setup.codes.disability-grade.choices.33-64.label",
            "wizard.setup.codes.disability-grade.choices.33-64.description",
        ),
        _localized_choice(
            disability_grade_codes[RentaDisabilityGrade.GE_65],
            "wizard.setup.codes.disability-grade.choices.65-plus.label",
            "wizard.setup.codes.disability-grade.choices.65-plus.description",
        ),
        _localized_choice(
            disability_grade_codes[RentaDisabilityGrade.JUDICIAL_INCAPACITY],
            "wizard.setup.codes.disability-grade.choices.judicial-incapacity.label",
            "wizard.setup.codes.disability-grade.choices.judicial-incapacity.description",
        ),
        _localized_choice(
            disability_grade_codes[RentaDisabilityGrade.ASSISTANCE_OR_REDUCED_MOBILITY],
            "wizard.setup.codes.disability-grade.choices.assistance-or-reduced-mobility.label",
            "wizard.setup.codes.disability-grade.choices.assistance-or-reduced-mobility.description",
        ),
    )
    return (
        wizard_output_language_choices,
        wizard_declaration_type_choices,
        wizard_sex_choices,
        wizard_marital_status_choices,
        wizard_situacion_familiar_choices,
        wizard_disability_grade_choices,
    )


# The entity-type axis decides whether the IRPF-personal surface — the
# spouse, family, and personal-biographic questions, plus the
# individual-vs-joint taxation choice — is collected at all. A legal
# entity (sociedad limitada, etc.) and an attribution entity have no
# spouse and no personal IRPF facts: those questions are gated to the
# natural-person path so the non-interactive `--quiet` flow never asks
# (or, before this gate, wrongly demands) them for a company.
def _build_activity_visibility(
    _entity_legal: WizardCondition,
    _entity_attribution: WizardCondition,
    irpf_income_category_actividad_economica_token: Callable[[], _RegistryToken],
    _iva_regime_tokens: Sequence[_RegistryToken],
) -> tuple[WizardVisibility, WizardVisibility, WizardVisibility]:
    # `activity` (the actividad económica / epígrafe IAE free-text field)
    # is collected only for a taxpayer that actually carries on an
    # activity: a legal entity, or a natural person who declared the
    # `actividad_economica` IRPF income category. A pure landlord,
    # a salaried-only taxpayer, and a pensioner have no actividad
    # económica and must not be forced to invent one.
    _has_activity = WizardVisibility(
        any_of=(
            _entity_legal,
            WizardCondition(
                question_id="irpf-income-categories",
                contains=irpf_income_category_actividad_economica_token().value,
            ),
        ),
    )
    _iva_regime_visible = WizardVisibility(
        any_of=(
            _entity_legal,
            _entity_attribution,
            WizardCondition(
                question_id="irpf-income-categories",
                contains=irpf_income_category_actividad_economica_token().value,
            ),
        ),
    )

    # Every question whose answer CLAIMS the IVA block is gated here, not on
    # _iva_regime_visible. Declaring any IVA fact obliges the whole block, so a
    # gate that admits one block-owned question without admitting the questions
    # the block requires produces a profile the domain resolver then refuses. Six
    # enrolment confirms sat on the entity-shaped gate while the facts they oblige
    # sat on this one, so answering "no" to ROI without declaring a regime built a
    # claimed block the wizard never finished asking about.
    _iva_block_claimed = WizardVisibility(
        any_of=tuple(WizardCondition(question_id="iva-regime", equals=token.value) for token in _iva_regime_tokens),
    )

    return _has_activity, _iva_regime_visible, _iva_block_claimed


def _entity_token_readers(
    operation: PinnedAuthorityOperation,
) -> tuple[
    Callable[[], _RegistryToken],
    Callable[[], _RegistryToken],
    Callable[[], _RegistryToken],
]:
    from ...domain.calculations.registry.entity_type import (
        entity_type_attribution_entity_token as _entity_type_attribution_entity_token,
    )
    from ...domain.calculations.registry.entity_type import (
        entity_type_legal_entity_token as _entity_type_legal_entity_token,
    )
    from ...domain.calculations.registry.entity_type import (
        entity_type_natural_person_token as _entity_type_natural_person_token,
    )

    entity_type_attribution_entity_token = partial(_entity_type_attribution_entity_token, authority=operation)
    entity_type_legal_entity_token = partial(_entity_type_legal_entity_token, authority=operation)
    entity_type_natural_person_token = partial(_entity_type_natural_person_token, authority=operation)
    return entity_type_attribution_entity_token, entity_type_legal_entity_token, entity_type_natural_person_token


def _family_visibility(
    operation: PinnedAuthorityOperation,
) -> tuple[WizardCondition, WizardCondition, WizardCondition, WizardCondition, WizardCondition]:
    _joint_declaration = WizardCondition(
        question_id="taxation-type",
        equals=RentaDeclaracionType.form_codes(authority=operation)[RentaDeclaracionType.JOINT],
    )
    _married = WizardCondition(
        question_id="taxpayer-marital-status",
        equals=RentaMaritalStatus.form_codes(authority=operation)[RentaMaritalStatus.CASADO],
    )
    _premio_loteria_declared = WizardCondition(
        question_id="premio-loteria-gravamen-especial-sin-retencion",
        equals="true",
    )
    _non_resident_irpf = WizardCondition(question_id="spouse-non-resident-irpf", equals="true")
    _eu_eea_resident = WizardCondition(question_id="spouse-eu-eea-resident", equals="true")

    return _joint_declaration, _married, _premio_loteria_declared, _non_resident_irpf, _eu_eea_resident


def build_setup_flow(operation: PinnedAuthorityOperation) -> WizardFlow:
    """Build the setup flow from the caller's pinned authority operation."""
    from ...domain.calculations.registry.ccaa_catalogue import (
        default_ccaa as _default_ccaa,
    )
    from ...domain.calculations.registry.irpf_income_categories import (
        irpf_income_category_actividad_economica_token as _irpf_income_category_actividad_economica_token,
    )
    from ...domain.calculations.registry.iva_regime_vocabulary import (
        default_iva_regime as _default_iva_regime,
    )
    from ...domain.calculations.registry.iva_regime_vocabulary import (
        iva_regime_choices as _iva_regime_choices,
    )
    from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH, SetupAnswers

    # Every registry projection below is evaluated through this operation.
    # The resulting descriptor must not escape the operation that supplied it
    # as a process-global catalogue.
    default_ccaa = partial(_default_ccaa, authority=operation)
    irpf_income_category_actividad_economica_token = partial(
        _irpf_income_category_actividad_economica_token, authority=operation
    )
    default_iva_regime = partial(_default_iva_regime, authority=operation)
    iva_regime_choices = partial(_iva_regime_choices, authority=operation)
    entity_type_attribution_entity_token, entity_type_legal_entity_token, entity_type_natural_person_token = (
        _entity_token_readers(operation)
    )
    _natural_person = WizardCondition(question_id="entity-type", equals=entity_type_natural_person_token().value)

    _joint_declaration, _married, _premio_loteria_declared, _non_resident_irpf, _eu_eea_resident = _family_visibility(
        operation
    )

    _iva_regime_tokens = iva_regime_choices()
    _default_iva_regime_value: str = default_iva_regime().value
    # Resolve the IVA default through the same pinned operation as the choices.

    (
        wizard_iva_choices,
        wizard_m303_tax_territory_choices,
        wizard_m303_regime_composition_choices,
    ) = _build_iva_m303_choices(operation, _iva_regime_tokens)
    wizard_entity_type_choices, wizard_legal_entity_form_choices = _build_entity_choices(operation)
    (
        wizard_irpf_income_category_choices,
        wizard_third_party_declaration_role_choices,
        wizard_irpf_estimation_regime_choices,
        wizard_irpf_special_regime_choices,
        _impatriado_regime,
    ) = _build_irpf_choices(operation)
    (
        wizard_fiscal_residency_choices,
        _fiscal_residency_default,
        _non_resident_irnr,
        wizard_ccaa_choices,
    ) = _build_residence_choices(operation)
    (
        wizard_output_language_choices,
        wizard_declaration_type_choices,
        wizard_sex_choices,
        wizard_marital_status_choices,
        wizard_situacion_familiar_choices,
        wizard_disability_grade_choices,
    ) = _build_profile_and_personal_choices(operation)

    _entity_legal = WizardCondition(question_id="entity-type", equals=entity_type_legal_entity_token().value)
    _entity_attribution = WizardCondition(
        question_id="entity-type", equals=entity_type_attribution_entity_token().value
    )

    _has_activity, _iva_regime_visible, _iva_block_claimed = _build_activity_visibility(
        _entity_legal,
        _entity_attribution,
        irpf_income_category_actividad_economica_token,
        _iva_regime_tokens,
    )

    _identidad_section = build_identity_section(
        PROFILE_OUTPUT_LANGUAGE_PATH,
        _entity_legal,
        wizard_entity_type_choices,
        wizard_legal_entity_form_choices,
        wizard_output_language_choices,
    )

    _residence_section = build_residence_section(
        _fiscal_residency_default,
        _non_resident_irnr,
        default_ccaa,
        wizard_ccaa_choices,
        wizard_fiscal_residency_choices,
        wizard_m303_tax_territory_choices,
    )

    _actividad_section = build_activity_section(
        _entity_legal,
        _has_activity,
        _natural_person,
        wizard_irpf_income_category_choices,
        wizard_third_party_declaration_role_choices,
    )

    _iva_section = build_iva_section(
        _iva_block_claimed, _iva_regime_visible, wizard_iva_choices, wizard_m303_regime_composition_choices
    )

    _enrollment_section = build_enrollment_section()

    _familia_section = build_family_section(
        _eu_eea_resident,
        _joint_declaration,
        _married,
        _natural_person,
        _non_resident_irpf,
        wizard_declaration_type_choices,
        wizard_disability_grade_choices,
        wizard_marital_status_choices,
        wizard_sex_choices,
        wizard_situacion_familiar_choices,
    )

    _obligations_section = build_obligations_section(
        _impatriado_regime,
        _natural_person,
        _premio_loteria_declared,
        wizard_irpf_estimation_regime_choices,
        wizard_irpf_special_regime_choices,
    )

    _preferencias_section = build_preferences_section()

    return WizardFlow(
        id="setup",
        title=tr("wizard.setup.title"),
        description=tr("wizard.setup.description"),
        sections=(
            _identidad_section,
            _residence_section,
            _actividad_section,
            _iva_section,
            _enrollment_section,
            _familia_section,
            _obligations_section,
            _preferencias_section,
        ),
        answers_model=SetupAnswers,
    )


FAMILIA_SECTION_ID: Final = "familia"
"""The setup flow section carrying the family unit and its descendants."""


__all__ = ["FAMILIA_SECTION_ID", "build_setup_flow"]
