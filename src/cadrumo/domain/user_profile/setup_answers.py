"""Canonical typed-answer model for the user-profile setup flow.

:class:`SetupAnswers` is the authoritative typed-answers model for the wizard
``setup`` flow. It lives with the user-profile domain because its fields are
the typed vocabulary of a profile, while the application wizard only renders
and persists those answers.

This module owns typed answer validation and the stable output-language profile
path. It does not own prompt rendering, profile persistence, secure storage,
deadline scheduling, or registry semantics. The registry-aware reverse
projection is defined by
:mod:`cadrumo.domain.deadlines.setup_answer_projection`.

The application layer declares the ``SETUP_FLOW`` descriptor and consumes this
model directly. Downstream profile construction, including
``taxpayer_profile_from_mapping``, therefore stays aligned with wizard
canonical-token parsing without importing application modules directly.

Domain taxonomy types (``EntityType``, ``IVARegime``, etc.) are imported from
their defining domain modules at module load time. Keeping those finite imports
here makes this model domain-owned and removes the former core-to-domain lazy
import cycle.
"""

from __future__ import annotations

from typing import Any, Final

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from ...core.errors.hierarchy import ProfileAnswerTypeError, pydantic_validation_boundary
from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.parsing.utils import parse_bool
from ...core.renta_declaracion_type import RentaDeclaracionType
from ...core.spanish_postcode import OptionalSpanishPostcode
from ..calculations.registry.activity_kind_catalogue import require_irpf_activity_kind
from ..calculations.registry.ccaa_catalogue import default_ccaa, require_ccaa
from ..calculations.registry.entity_type import require_entity_type, require_legal_entity_form
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.irpf_income_categories import require_irpf_income_category
from ..calculations.registry.irpf_regimes import require_irpf_estimation_regime, require_irpf_special_regime
from ..calculations.registry.iva_schema_vocabulary import require_iva_regime
from ..calculations.registry.situacion_familiar_catalogue import require_situacion_familiar
from ..calculations.registry.third_party_declaration_roles import require_third_party_declaration_role
from ..contribuyente.ccaa import CCAA
from ..contribuyente.entity_type import EntityType, LegalEntityForm
from ..contribuyente.renta_codes import (
    FiscalResidency,
    RentaDisabilityGrade,
    RentaMaritalStatus,
    RentaSexCode,
    SituacionFamiliar,
)
from ..deadlines.models import IVARegime


def _parse_optional_bool_token(value: object, *, field_name: str) -> object:
    """Parse a three-state optional wizard boolean token.

    Accepted affirmative tokens become ``True``; accepted negative tokens become
    ``False``. Blank input and ``None`` remain the empty-string sentinel so
    profile persistence drops the fact instead of writing a declared false
    value. This helper does not parse prompt labels or locale text; it accepts
    only canonical yes/no tokens.
    """
    if value == "" or value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.strip() == "":
            return ""
        parsed = parse_bool(value)
        if parsed is not None:
            return parsed
    raise ValueError(f"{field_name} must be a boolean, blank, or a recognised canonical token")


PROFILE_OUTPUT_LANGUAGE_PATH: Final[str] = "preferences.output_language"
"""Dotted profile-record path for the setup flow's output-language answer."""


# ---------------------------------------------------------------------------
# SetupAnswers
# ---------------------------------------------------------------------------


class SetupAnswers(BaseModel):
    """Typed answers collected by the ``setup`` flow.

    Canonical home is :mod:`cadrumo.domain.user_profile.setup_answers`. The
    application wizard and deadline domain import :class:`SetupAnswers` from
    here; no layer needs to cross into the application boundary.

    The model stores canonical answer tokens and typed taxonomy values for the
    setup flow. It is not the persisted profile record and it is not the
    deadline-engine taxpayer profile; those are produced downstream by wizard
    persistence and deadline profile projection. Where validators allow the
    empty string, the value means undeclared/no answer rather than false, zero,
    or a default legal fact.

    Field annotations use ``Any`` for taxonomy union types because the setup
    flow carries typed enum members alongside the blank undeclared sentinel.
    That ``Any`` is not a loose schema: validators enforce the same invariants,
    reject values outside the declared enum / blank-string set, and raise
    :class:`~cadrumo.core.errors.hierarchy.ProfileAnswerTypeError`.
    """

    model_config = STRICT_FROZEN_CONFIG

    # ── profile identity ─────────────────────────────────────────────────
    tax_id: str = Field(min_length=1)
    name: str = ""
    surnames: str = ""
    legal_name: str = ""
    activity: str = ""
    """Free-text actividad económica / epígrafe IAE description."""
    address_postcode: OptionalSpanishPostcode = ""
    """Optional Spanish postcode for the taxpayer's activity/contact address."""
    activity_start_date: str = ""
    """Optional ISO-8601 censo alta date for the economic activity."""
    taxation_type: Any = ""
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE

    @field_validator("output_language", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _coerce_output_language(cls, value: object) -> OutputLanguage:
        if isinstance(value, OutputLanguage):
            return value
        if isinstance(value, str):
            return OutputLanguage(value)
        raise ProfileAnswerTypeError(
            translated_message="core.profile.errors.output_language_type",
        )

    # ── taxpayer type (three-axis taxpayer model) ────────────────────────
    entity_type: Any = ""
    legal_entity_form: Any = ""
    incn_prior_12_months: str = ""
    """Optional INCN as a canonical decimal string."""
    new_entity_first_two_profit_periods: Any = ""
    """Optional three-state bool for LIS Art. 29 new-entity rate."""
    ley_49_2002_option_declared: Any = ""
    """Optional three-state bool for the governed special-regime option."""
    ley_49_2002_option_date: str = ""
    """ISO-8601 date declared for the governed special-regime option."""
    ley_49_2002_renunciation_declared: Any = ""
    """Optional three-state bool for governed special-regime renunciation."""
    ley_49_2002_renunciation_date: str = ""
    """ISO-8601 date declared for governed special-regime renunciation."""
    irpf_income_categories: str = ""
    """Comma-separated set of IrpfIncomeCategory tokens."""
    declaration_roles: str = ""
    """Comma-separated set of ThirdPartyDeclarationRole tokens."""

    # ── taxpayer biographic ──────────────────────────────────────────────
    taxpayer_sex: Any = ""
    taxpayer_marital_status: Any = ""
    taxpayer_marriage_date: str = ""
    """ISO-8601 date when the current marriage began."""
    taxpayer_birth_date: str = ""
    taxpayer_disability_grade: Any = ""
    taxpayer_death_date: str = ""

    # ── spouse (taxation_type == "2") ────────────────────────────────────
    spouse_tax_id: str = ""
    spouse_name: str = ""
    spouse_surnames: str = ""
    spouse_birth_date: str = ""
    spouse_sex: Any = ""
    spouse_disability_grade: Any = ""
    spouse_non_resident_irpf: bool = False
    spouse_eu_eea_resident: bool = False
    spouse_eu_eea_country: str = ""

    # ── family ───────────────────────────────────────────────────────────
    family_descendants_eu_eea_deduction: bool = False
    family_minor_children_in_unit: bool = False
    situacion_familiar: Any = ""
    """Art. 82 LIRPF family situation governing conjunta eligibility."""
    unidad_familiar_descendientes_exclusivos: Any = ""
    """Custodia compartida progenitor claiming the monoparental unidad familiar."""

    # ── IVA ──────────────────────────────────────────────────────────────
    iva_regime: Any = ""
    iva_roi_enrolled: Any = ""
    iva_oss_enrolled: Any = ""
    iva_group_member_enrolled: Any = ""
    iva_group_dominant_entity_enrolled: Any = ""
    iva_sii_enrolled: Any = ""
    iva_redeme_enrolled: Any = ""
    iva_intracommunity_operations_exceed_50000_eur: Any = ""
    iva_m303_regime_composition: str = ""
    iva_cash_accounting_regime_enrolled: Any = ""
    iva_voluntary_sii_enrolled: Any = ""
    iva_hydrocarbon_deposit_advance_payment_deduction_entitled: Any = ""

    # ── enrollment ───────────────────────────────────────────────────────
    enrollment_large_company: bool = False
    enrollment_public_administration_budget_gt_6000000: bool = False

    # ── retencion / modelo obligation booleans ───────────────────────────
    has_employees: bool = False
    colegio_concertado: Any = ""
    pays_professionals_with_retencion: bool = False
    professional_income_withholding_ge_70pct: bool = False
    art109_activity_income_withholding_ge_70pct: bool = False
    pays_rent_with_retencion: bool = False
    pays_capital_income_with_retencion: bool = False
    modelo_111_no_retenciones_periods: str = ""
    modelo_115_no_relevant_payment_periods: str = ""
    irpf_estimation_regime: Any = ""
    irpf_activity_kind: Any = ""
    objective_estimation_modulos_iae_epigraph: str = ""
    objective_estimation_modulos_module_1_units: str = ""
    objective_estimation_modulos_module_2_units: str = ""
    objective_estimation_modulos_module_3_units: str = ""
    objective_estimation_modulos_module_4_units: str = ""
    objective_estimation_modulos_module_5_units: str = ""
    objective_estimation_modulos_module_6_units: str = ""
    objective_estimation_modulos_module_7_units: str = ""
    irpf_special_regime: Any = ""
    """IRPF special-regime axis. Blank for the general regime."""
    irpf_special_regime_start_date: str = ""
    """ISO-8601 opt-in election date for the special regime."""
    does_intracomunitario: bool = False
    third_party_transactions_above_347_threshold: bool = False
    bienes_extranjero_above_threshold: bool = False
    monedas_virtuales_extranjero_above_threshold: bool = False

    # ── residence ────────────────────────────────────────────────────────
    tax_residence_ccaa: Any = None
    tax_residence_jurisdiction_scope: str = ""
    fiscal_residency: Any = ""
    """Fiscal residency category."""
    country_of_fiscal_residence: str = ""
    """ISO 3166-1 alpha-2 code of the country of fiscal residence."""
    representante_fiscal_nif: str = ""
    """NIF/NIE of the fiscal representative in Spain."""
    representante_fiscal_nombre: str = ""
    """Full name of the fiscal representative in Spain."""

    # ── capabilities ─────────────────────────────────────────────────────
    llm_vision: bool = True
    google_export: bool = True

    # ── notes ────────────────────────────────────────────────────────────
    notes: str = ""

    # ------------------------------------------------------------------
    # Validators — taxonomy classes are imported from their defining modules
    # ------------------------------------------------------------------

    # Pydantic's ``mode="before"`` field validators accept the raw token and
    # return either the typed taxonomy member or the blank sentinel. The
    # answer fields remain ``Any`` because that sentinel is intentionally
    # distinct from each enum's value space.
    @field_validator("iva_regime", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_iva_regime(cls, value: object) -> Any:
        if isinstance(value, IVARegime):
            try:
                return require_iva_regime(value)
            except ValueError as exc:
                raise ProfileAnswerTypeError("iva_regime must be declared by the IVA facts registry") from exc
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            try:
                return require_iva_regime(value.upper())
            except ValueError as exc:
                raise ProfileAnswerTypeError("iva_regime must be declared by the IVA facts registry") from exc
        raise ProfileAnswerTypeError("iva_regime must be an IVARegime member or string token")

    @field_validator(
        "colegio_concertado",
        "iva_roi_enrolled",
        "iva_oss_enrolled",
        "iva_group_member_enrolled",
        "iva_group_dominant_entity_enrolled",
        "iva_sii_enrolled",
        "iva_redeme_enrolled",
        "iva_intracommunity_operations_exceed_50000_eur",
        "iva_cash_accounting_regime_enrolled",
        "iva_voluntary_sii_enrolled",
        "iva_hydrocarbon_deposit_advance_payment_deduction_entitled",
        mode="before",
    )
    @classmethod
    @pydantic_validation_boundary
    def _parse_optional_iva_bool(cls, value: object) -> Any:
        return _parse_optional_bool_token(value, field_name="Modelo IVA boolean")

    @field_validator("tax_residence_ccaa", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_tax_residence_ccaa(cls, value: object) -> Any:
        if isinstance(value, CCAA):
            return value
        if value is None:
            return default_ccaa()
        if isinstance(value, str):
            if not value:
                return default_ccaa()
            try:
                return require_ccaa(value)
            except RegistryValidationError as exc:
                raise ProfileAnswerTypeError("tax_residence_ccaa must be declared by the CCAA facts registry") from exc
        raise ProfileAnswerTypeError("tax_residence_ccaa must be a CCAA member or string token")

    @field_validator("entity_type", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_entity_type(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, EntityType):
            return value
        if isinstance(value, str):
            try:
                return require_entity_type(value)
            except RegistryValidationError as exc:
                raise ProfileAnswerTypeError("entity_type must be declared by the facts registry") from exc
        raise ProfileAnswerTypeError("entity_type must be a registry token or blank")

    @field_validator("legal_entity_form", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_legal_entity_form(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, LegalEntityForm):
            return value
        if isinstance(value, str):
            try:
                return require_legal_entity_form(value)
            except RegistryValidationError as exc:
                raise ProfileAnswerTypeError("legal_entity_form must be declared by the facts registry") from exc
        raise ProfileAnswerTypeError("legal_entity_form must be a registry token or blank")

    @field_validator("irpf_estimation_regime", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_irpf_estimation_regime(cls, value: object) -> Any:
        if value == "":
            return ""
        try:
            return require_irpf_estimation_regime(value)
        except RegistryValidationError as exc:
            raise ProfileAnswerTypeError("irpf_estimation_regime must be declared by the facts registry") from exc

    @field_validator("irpf_activity_kind", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_irpf_activity_kind(cls, value: object) -> Any:
        if value == "":
            return ""
        try:
            return require_irpf_activity_kind(value)
        except RegistryValidationError as exc:
            raise ProfileAnswerTypeError(
                "irpf_activity_kind must be declared by the facts registry",
            ) from exc

    @field_validator("situacion_familiar", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_situacion_familiar(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, (SituacionFamiliar, str)):
            try:
                return require_situacion_familiar(value)
            except RegistryValidationError as exc:
                raise ProfileAnswerTypeError("situacion_familiar must be declared by the facts registry") from exc
        raise ProfileAnswerTypeError("situacion_familiar must be a SituacionFamiliar member, string token, or blank")

    @field_validator("unidad_familiar_descendientes_exclusivos", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_unidad_familiar_descendientes_exclusivos(
        cls,
        value: object,
    ) -> Any:
        if value == "":
            return ""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            if value.lower() == "false":
                return False
        raise ProfileAnswerTypeError(
            "unidad_familiar_descendientes_exclusivos must be a bool, 'true', 'false', or blank",
        )

    @field_validator("irpf_special_regime", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_irpf_special_regime(cls, value: object) -> Any:
        if value == "":
            return ""
        try:
            return require_irpf_special_regime(value)
        except RegistryValidationError as exc:
            raise ProfileAnswerTypeError("irpf_special_regime must be declared by the facts registry") from exc

    @field_validator("fiscal_residency", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_fiscal_residency(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, FiscalResidency):
            return value
        if isinstance(value, str):
            from ..calculations.registry.renta_codes_catalogue import require_fiscal_residency

            try:
                return require_fiscal_residency(value)
            except ValueError as exc:
                raise ProfileAnswerTypeError(
                    "fiscal_residency must be declared by the residency facts registry",
                ) from exc
        raise ProfileAnswerTypeError("fiscal_residency must be a FiscalResidency member, string token, or blank")

    @field_validator("irpf_income_categories")
    @classmethod
    @pydantic_validation_boundary
    def _validate_irpf_income_categories(cls, value: str) -> str:
        tokens = [token.strip() for token in value.split(",") if token.strip()]
        for token in tokens:
            try:
                require_irpf_income_category(token)
            except RegistryValidationError as exc:
                raise ProfileAnswerTypeError(
                    "irpf_income_categories must contain only values declared by the income-category facts registry",
                ) from exc
        return ",".join(tokens)

    @field_validator("declaration_roles")
    @classmethod
    @pydantic_validation_boundary
    def _validate_declaration_roles(cls, value: str) -> str:
        tokens = [token.strip() for token in value.split(",") if token.strip()]
        for token in tokens:
            try:
                require_third_party_declaration_role(token)
            except RegistryValidationError as exc:
                raise ProfileAnswerTypeError(
                    "declaration_roles must contain only values declared by the facts registry",
                ) from exc
        return ",".join(tokens)

    @field_validator("taxation_type", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_taxation_type(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, RentaDeclaracionType):
            return value
        if isinstance(value, str):
            return RentaDeclaracionType(value)
        raise ProfileAnswerTypeError("taxation_type must be a RentaDeclaracionType member, string token, or blank")

    @field_validator("taxpayer_sex", "spouse_sex", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_sex_code(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, RentaSexCode):
            return value
        if isinstance(value, str):
            return RentaSexCode(value)
        raise ProfileAnswerTypeError("sex code must be a RentaSexCode member, string token, or blank")

    @field_validator("taxpayer_marital_status", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_marital_status(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, RentaMaritalStatus):
            return value
        if isinstance(value, str):
            return RentaMaritalStatus(value)
        raise ProfileAnswerTypeError(
            "taxpayer_marital_status must be a RentaMaritalStatus member, string token, or blank",
        )

    @field_validator("taxpayer_marriage_date")
    @classmethod
    @pydantic_validation_boundary
    def _validate_taxpayer_marriage_date(cls, value: str) -> str:
        from datetime import date

        if value == "":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"taxpayer_marriage_date must be an ISO-8601 date (YYYY-MM-DD), got {value!r}") from exc
        return value

    @field_validator(
        "taxpayer_disability_grade",
        "spouse_disability_grade",
        mode="before",
    )
    @classmethod
    @pydantic_validation_boundary
    def _parse_disability_grade(cls, value: object) -> Any:
        if value == "":
            return ""
        if isinstance(value, RentaDisabilityGrade):
            return value
        if isinstance(value, str):
            return RentaDisabilityGrade(value)
        raise ProfileAnswerTypeError("disability grade must be a RentaDisabilityGrade member, string token, or blank")

    @field_validator("incn_prior_12_months")
    @classmethod
    @pydantic_validation_boundary
    def _validate_incn_prior_12_months(cls, value: str) -> str:
        from decimal import Decimal, InvalidOperation

        if value == "":
            return value
        try:
            Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"incn_prior_12_months must be a decimal number, got {value!r}") from exc
        return value

    @field_validator(
        "objective_estimation_modulos_module_1_units",
        "objective_estimation_modulos_module_2_units",
        "objective_estimation_modulos_module_3_units",
        "objective_estimation_modulos_module_4_units",
        "objective_estimation_modulos_module_5_units",
        "objective_estimation_modulos_module_6_units",
        "objective_estimation_modulos_module_7_units",
    )
    @classmethod
    @pydantic_validation_boundary
    def _validate_objective_estimation_modulos_units(cls, value: str) -> str:
        from decimal import Decimal, InvalidOperation

        if value == "":
            return value
        try:
            Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"objective-estimation modulos units must be decimal numbers, got {value!r}") from exc
        return value

    @field_validator("new_entity_first_two_profit_periods", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _parse_new_entity_first_two_profit_periods(
        cls,
        value: object,
    ) -> Any:
        return _parse_optional_bool_token(
            value,
            field_name="new_entity_first_two_profit_periods",
        )

    @field_validator(
        "ley_49_2002_option_declared",
        "ley_49_2002_renunciation_declared",
        mode="before",
    )
    @classmethod
    @pydantic_validation_boundary
    def _parse_ley_49_2002_optional_bool(
        cls,
        value: object,
    ) -> Any:
        return _parse_optional_bool_token(value, field_name="ley_49_2002_optional_bool")

    @field_validator("activity_start_date")
    @classmethod
    @pydantic_validation_boundary
    def _validate_activity_start_date(cls, value: str) -> str:
        from datetime import date

        if value == "":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"activity_start_date must be an ISO-8601 date (YYYY-MM-DD), got {value!r}") from exc
        return value

    @field_validator("ley_49_2002_option_date", "ley_49_2002_renunciation_date")
    @classmethod
    @pydantic_validation_boundary
    def _validate_ley_49_2002_dates(cls, value: str) -> str:
        from datetime import date

        if value == "":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"Ley 49/2002 dates must be ISO-8601 (YYYY-MM-DD), got {value!r}") from exc
        return value

    @field_validator("irpf_special_regime_start_date")
    @classmethod
    @pydantic_validation_boundary
    def _validate_irpf_special_regime_start_date(cls, value: str) -> str:
        from datetime import date

        if value == "":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"special_regime_start_date must be an ISO-8601 date (YYYY-MM-DD), got {value!r}") from exc
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_spouse_fields_when_joint(self) -> SetupAnswers:
        if self.taxation_type == RentaDeclaracionType.JOINT and not self.spouse_tax_id:
            # A stable custom error type (not the generic ``value_error``) lets
            # the operator-facing boundary route this cross-field refusal to its
            # own localized message rather than the raw English text below.
            raise PydanticCustomError(
                "spouse_tax_id_required_joint",
                "spouse_tax_id is required when taxation_type is joint (taxation_type='2')",
            )
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_eu_eea_country_when_resident(self) -> SetupAnswers:
        if self.spouse_eu_eea_resident and not self.spouse_eu_eea_country:
            raise PydanticCustomError(
                "eu_eea_country_required",
                "spouse_eu_eea_country is required when spouse_eu_eea_resident is true",
            )
        return self


__all__ = [
    "PROFILE_OUTPUT_LANGUAGE_PATH",
    "SetupAnswers",
]
