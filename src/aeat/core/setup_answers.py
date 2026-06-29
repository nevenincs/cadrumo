"""Canonical typed-answer model and projection registry for the setup flow.

:class:`SetupAnswers` is the authoritative typed-answers model for the wizard
``setup`` flow.  Domain modules import it from here — never from the application
wizard layer — so the hexagonal boundary (domain → core is allowed; domain →
application is forbidden) is respected.

The :func:`project_answers` callable is initially unregistered and is populated
at application startup by the wizard layer via :func:`register_project_answers`.
Domain consumers call :func:`project_answers` directly; it raises
:class:`ProjectAnswersNotRegisteredError` when the application layer has not
yet run.

This pattern mirrors the one established in :mod:`aeat.core.wizard_catalogue`
for ``SETUP_FLOW`` / ``WIZARD_FLOWS``.

Domain taxonomy types (``EntityType``, ``IVARegime``, etc.) are imported lazily
inside validators rather than at module level to break the circular import
path: ``aeat.core.setup_answers`` → ``aeat.domain.deadlines._models`` →
``aeat.domain.deadlines.__init__`` → ``aeat.domain.deadlines._profiles`` →
``aeat.core.setup_answers``.  This mirrors the deferral strategy used in
``aeat.core.resources._repos.*`` and is the established project pattern.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

from ..core import STRICT_FROZEN_CONFIG
from .errors import CoreError, ProfileAnswerTypeError
from .external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from .logging import get_logger

_log = get_logger(__name__)


def _parse_optional_bool_token(value: object, *, field_name: str) -> object:
    """Parse a three-state optional wizard boolean token.

    Blank means undeclared and must survive as ``""`` so profile persistence
    drops the fact instead of writing a declared false value.
    """
    if value == "" or value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        token = value.strip().lower()
        if token == "":
            return ""
        if token in {"true", "1", "yes", "y", "si", "sí"}:
            return True
        if token in {"false", "0", "no", "n"}:
            return False
    raise ValueError(f"{field_name} must be a boolean, blank, or a recognised canonical token")


# ---------------------------------------------------------------------------
# project_answers registration slot
# ---------------------------------------------------------------------------


class ProfileRegistrationError(CoreError):
    """Raised when :func:`register_project_answers` is called a second time with a different callable.

    A double-registration with the same callable is a safe no-op; a double-registration
    with a *different* callable is a programming error that must be surfaced as a
    typed, registry-bound exception so callers receive a structured error envelope
    rather than a bare :exc:`RuntimeError`.
    """


class ProjectAnswersNotRegisteredError(CoreError):
    """Raised when domain code calls project_answers before registration."""

    def __init__(self) -> None:
        """Initialise with a fixed message directing the caller to register the projection."""
        super().__init__(
            "project_answers has not been registered. "
            "Call register_project_answers() at application startup before "
            "any domain module invokes the projection.",
        )


@runtime_checkable
class ProjectAnswersFn(Protocol):
    """Structural type for the project_answers callable.

    Satisfied by ``aeat.application.wizard._persistence.project_answers``.
    Domain code depends only on this protocol.
    """

    # KWARGS-ANY-RATIONALE-PROFILE-WIZARD-FLOW-CIRCULAR:
    # WizardFlow type lives in aeat.application.wizard; importing here would
    # create circular dependency.
    def __call__(self, flow: Any, values: Mapping[str, str]) -> BaseModel:
        """Project canonical-token values into the typed answers model."""
        ...  # pragma: no cover


_PROJECT_ANSWERS_SLOT: list[ProjectAnswersFn] = []


def register_project_answers(fn: ProjectAnswersFn) -> None:
    """Register the concrete project_answers implementation from the application layer.

    Call exactly once at application startup (e.g. in
    ``aeat.application.wizard._persistence`` module body after the function is
    defined). A second call with an identical callable is a no-op; a second
    call with a different callable raises :class:`RuntimeError`.
    """
    if _PROJECT_ANSWERS_SLOT:
        if _PROJECT_ANSWERS_SLOT[0] is fn:
            return
        raise ProfileRegistrationError(
            translated_message="core.profile.errors.registration_duplicate_callable",
        )
    _PROJECT_ANSWERS_SLOT.append(fn)
    _log.debug("project_answers registered: %r", fn)


def get_project_answers() -> ProjectAnswersFn:
    """Return the registered project_answers implementation.

    Returns:
        The :class:`ProjectAnswersFn` registered via
        :func:`register_project_answers`.

    Raises:
        ProjectAnswersNotRegisteredError: When the application layer has not yet
            called :func:`register_project_answers`.
    """
    if not _PROJECT_ANSWERS_SLOT:
        raise ProjectAnswersNotRegisteredError()
    return _PROJECT_ANSWERS_SLOT[0]


# KWARGS-ANY-RATIONALE-PROFILE-WIZARD-FLOW-CIRCULAR:
# WizardFlow type lives in aeat.application.wizard; importing here would create
# circular dependency.
def project_answers(flow: Any, values: Mapping[str, str]) -> BaseModel:
    """Invoke the registered project_answers implementation.

    Delegates to the application-layer function registered via
    :func:`register_project_answers`.  Domain callers import this function from
    ``aeat.core.setup_answers`` so they never acquire a direct dependency on
    ``aeat.application.wizard._persistence``.

    Args:
        flow: The wizard flow descriptor identifying which flow to
            project answers for.
        values: Mapping of canonical token keys to raw string values
            collected from the wizard.

    Returns:
        A typed answers model instance produced by the registered
        implementation.
    """
    return get_project_answers()(flow, values)


# ---------------------------------------------------------------------------
# Lazy domain-type accessors
#
# All domain imports are deferred inside validators and accessors below to
# avoid the circular import:
#   aeat.core.setup_answers → aeat.domain.deadlines._models
#   → aeat.domain.deadlines.__init__ → aeat.domain.deadlines._profiles
#   → aeat.core.setup_answers   (partially initialised → ImportError)
# ---------------------------------------------------------------------------


# ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE: returns the
# aeat.domain.deadlines._models module object; a typed return would require
# importing the module at definition time, re-introducing the circular import
# described in the block comment above.
def _m() -> Any:
    """Return the aeat.domain.deadlines._models module (lazy)."""
    import importlib

    return importlib.import_module("aeat.domain.deadlines._models")


# ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE: returns the
# aeat.domain.contribuyente module object; typed return would require importing the
# module at definition time, re-introducing the circular import.
def _p() -> Any:
    """Return the aeat.domain.contribuyente module (lazy)."""
    import importlib

    return importlib.import_module("aeat.domain.contribuyente")


# ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE: returns the CCAA enum class object;
# typed return would require importing the module at definition time,
# re-introducing the circular import.
def _ccaa() -> Any:
    """Return the CCAA enum class (lazy)."""
    import importlib

    return importlib.import_module("aeat.domain.contribuyente._ccaa").CCAA


# ---------------------------------------------------------------------------
# SetupAnswers
# ---------------------------------------------------------------------------


class SetupAnswers(BaseModel):
    """Typed answers collected by the ``setup`` flow.

    Canonical home is :mod:`aeat.core.setup_answers`.  The application wizard layer
    imports :class:`SetupAnswers` from here; the domain deadline engine likewise
    imports it from here — no layer needs to cross the hexagonal boundary.

    Field annotations use ``Any`` for domain taxonomy union types because those
    types are loaded lazily inside validators to prevent a circular import.
    Validators enforce the same invariants the original typed annotations
    carried: they reject values outside the declared enum / blank-string set and
    raise :class:`~aeat.core.errors.ProfileAnswerTypeError`.
    """

    model_config = STRICT_FROZEN_CONFIG

    # ── profile identity ─────────────────────────────────────────────────
    tax_id: str = Field(min_length=1)
    name: str = ""
    surnames: str = ""
    legal_name: str = ""
    activity: str = ""
    """Free-text actividad económica / epígrafe IAE description."""
    address_postcode: str = ""
    """Optional Spanish postcode for the taxpayer's activity/contact address."""
    activity_start_date: str = ""
    """Optional ISO-8601 censo alta date for the economic activity."""
    taxation_type: Any = ""
    output_language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE

    @field_validator("output_language", mode="before")
    @classmethod
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
    """Optional three-state bool for the Ley 49/2002 Title II option."""
    ley_49_2002_option_date: str = ""
    """ISO-8601 date declared for the Ley 49/2002 Title II option."""
    ley_49_2002_renunciation_declared: Any = ""
    """Optional three-state bool for Ley 49/2002 Title II renunciation."""
    ley_49_2002_renunciation_date: str = ""
    """ISO-8601 date declared for the Ley 49/2002 Title II renunciation."""
    irpf_income_categories: str = ""
    """Comma-separated set of IrpfIncomeCategory tokens."""

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
    iva_regime: Any = None
    iva_roi_enrolled: bool = False
    iva_oss_enrolled: bool = False
    iva_sii_enrolled: bool = False
    iva_redeme_enrolled: bool = False
    iva_intracommunity_operations_exceed_50000_eur: bool = False

    # ── enrollment ───────────────────────────────────────────────────────
    enrollment_large_company: bool = False
    enrollment_public_administration_budget_gt_6000000: bool = False

    # ── retencion / modelo obligation booleans ───────────────────────────
    has_employees: bool = False
    pays_professionals_with_retencion: bool = False
    professional_income_withholding_ge_70pct: bool = False
    pays_rent_with_retencion: bool = False
    pays_capital_income_with_retencion: bool = False
    irpf_estimation_regime: Any = ""
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
    fiscal_residency: Any = ""
    """Fiscal residency category."""
    country_of_fiscal_residence: str = ""
    """ISO 3166-1 alpha-2 code of the country of fiscal residence."""
    representante_fiscal_nif: str = ""
    """NIF/NIE of the fiscal representative in Spain."""
    representante_fiscal_nombre: str = ""
    """Full name of the fiscal representative in Spain."""

    # ── capabilities ─────────────────────────────────────────────────────
    cloud_evidence_upload: bool = False
    llm_vision: bool = True
    google_export: bool = True

    # ── notes ────────────────────────────────────────────────────────────
    notes: str = ""

    # ------------------------------------------------------------------
    # Validators — each lazily resolves domain types via _m() / _p()
    # ------------------------------------------------------------------

    # CAST-RATIONALE-PROFILE-FIELD-VALIDATOR-ANY: pydantic's @field_validator
    # with mode="before" requires the validator to return Any; the post-coercion
    # value is validated by pydantic against the field's declared type after
    # this validator returns.  A narrower return type (e.g., IVARegime) is not
    # expressible here because IVARegime is resolved lazily via _m() to avoid
    # a circular import at module load time.
    @field_validator("iva_regime", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_iva_regime(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        iva_regime_cls = _m().IVARegime
        if isinstance(value, iva_regime_cls):
            return value
        if value is None:
            return iva_regime_cls.GENERAL
        if isinstance(value, str):
            return iva_regime_cls(value.upper()) if value else iva_regime_cls.GENERAL
        raise ProfileAnswerTypeError("iva_regime must be an IVARegime member or string token")

    @field_validator("tax_residence_ccaa", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_tax_residence_ccaa(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        ccaa_cls = _ccaa()
        if isinstance(value, ccaa_cls):
            return value
        if value is None:
            return ccaa_cls.MADRID
        if isinstance(value, str):
            return ccaa_cls(value) if value else ccaa_cls.MADRID
        raise ProfileAnswerTypeError("tax_residence_ccaa must be a CCAA member or string token")

    @field_validator("entity_type", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_entity_type(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        entity_type_cls = _m().EntityType
        if isinstance(value, entity_type_cls):
            return value
        if isinstance(value, str):
            return entity_type_cls(value)
        raise ProfileAnswerTypeError("entity_type must be an EntityType member, string token, or blank")

    @field_validator("legal_entity_form", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_legal_entity_form(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        legal_entity_form_cls = _m().LegalEntityForm
        if isinstance(value, legal_entity_form_cls):
            return value
        if isinstance(value, str):
            return legal_entity_form_cls(value)
        raise ProfileAnswerTypeError("legal_entity_form must be a LegalEntityForm member, string token, or blank")

    @field_validator("irpf_estimation_regime", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_irpf_estimation_regime(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        irpf_estimation_regime_cls = _m().IrpfEstimationRegime
        if isinstance(value, irpf_estimation_regime_cls):
            return value
        if isinstance(value, str):
            return irpf_estimation_regime_cls(value)
        raise ProfileAnswerTypeError(
            "irpf_estimation_regime must be an IrpfEstimationRegime member, string token, or blank",
        )

    @field_validator("situacion_familiar", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_situacion_familiar(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        situacion_familiar_cls = _p().SituacionFamiliar
        if isinstance(value, situacion_familiar_cls):
            return value
        if isinstance(value, str):
            return situacion_familiar_cls(value)
        raise ProfileAnswerTypeError("situacion_familiar must be a SituacionFamiliar member, string token, or blank")

    @field_validator("unidad_familiar_descendientes_exclusivos", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_unidad_familiar_descendientes_exclusivos(  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
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
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_irpf_special_regime(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        irpf_special_regime_cls = _m().IrpfSpecialRegime
        if isinstance(value, irpf_special_regime_cls):
            return value
        if isinstance(value, str):
            return irpf_special_regime_cls(value)
        raise ProfileAnswerTypeError("irpf_special_regime must be an IrpfSpecialRegime member, string token, or blank")

    @field_validator("fiscal_residency", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_fiscal_residency(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        fiscal_residency_cls = _m().FiscalResidency
        if isinstance(value, fiscal_residency_cls):
            return value
        if isinstance(value, str):
            return fiscal_residency_cls(value)
        raise ProfileAnswerTypeError("fiscal_residency must be a FiscalResidency member, string token, or blank")

    @field_validator("irpf_income_categories")
    @classmethod
    def _validate_irpf_income_categories(cls, value: str) -> str:
        irpf_income_category_cls = _m().IrpfIncomeCategory
        tokens = [token.strip() for token in value.split(",") if token.strip()]
        for token in tokens:
            irpf_income_category_cls(token)
        return ",".join(tokens)

    @field_validator("taxation_type", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_taxation_type(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        renta_declaracion_type_cls = _p().RentaDeclaracionType
        if isinstance(value, renta_declaracion_type_cls):
            return value
        if isinstance(value, str):
            return renta_declaracion_type_cls(value)
        raise ProfileAnswerTypeError("taxation_type must be a RentaDeclaracionType member, string token, or blank")

    @field_validator("taxpayer_sex", "spouse_sex", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_sex_code(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        sex_code_cls = _p().RentaSexCode
        if isinstance(value, sex_code_cls):
            return value
        if isinstance(value, str):
            return sex_code_cls(value)
        raise ProfileAnswerTypeError("sex code must be a RentaSexCode member, string token, or blank")

    @field_validator("taxpayer_marital_status", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_marital_status(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        marital_status_cls = _p().RentaMaritalStatus
        if isinstance(value, marital_status_cls):
            return value
        if isinstance(value, str):
            return marital_status_cls(value)
        raise ProfileAnswerTypeError(
            "taxpayer_marital_status must be a RentaMaritalStatus member, string token, or blank",
        )

    @field_validator("taxpayer_marriage_date")
    @classmethod
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
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_disability_grade(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        disability_grade_cls = _p().RentaDisabilityGrade
        if isinstance(value, disability_grade_cls):
            return value
        if isinstance(value, str):
            return disability_grade_cls(value)
        raise ProfileAnswerTypeError("disability grade must be a RentaDisabilityGrade member, string token, or blank")

    @field_validator("incn_prior_12_months")
    @classmethod
    def _validate_incn_prior_12_months(cls, value: str) -> str:
        from decimal import Decimal, InvalidOperation

        if value == "":
            return value
        try:
            Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"incn_prior_12_months must be a decimal number, got {value!r}") from exc
        return value

    @field_validator("new_entity_first_two_profit_periods", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_new_entity_first_two_profit_periods(  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
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
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is a
    # bool or the blank undeclared sentinel.
    def _parse_ley_49_2002_optional_bool(  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        cls,
        value: object,
    ) -> Any:
        return _parse_optional_bool_token(value, field_name="ley_49_2002_optional_bool")

    @field_validator("activity_start_date")
    @classmethod
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
    def _validate_spouse_fields_when_joint(self) -> SetupAnswers:
        renta_declaracion_type_cls = _p().RentaDeclaracionType
        if self.taxation_type == renta_declaracion_type_cls.JOINT and not self.spouse_tax_id:
            raise ValueError("spouse_tax_id is required when taxation_type is joint (taxation_type='2')")
        return self

    @model_validator(mode="after")
    def _validate_eu_eea_country_when_resident(self) -> SetupAnswers:
        if self.spouse_eu_eea_resident and not self.spouse_eu_eea_country:
            raise ValueError("spouse_eu_eea_country is required when spouse_eu_eea_resident is true")
        return self


__all__ = [
    "ProfileAnswerTypeError",
    "ProjectAnswersFn",
    "ProjectAnswersNotRegisteredError",
    "SetupAnswers",
    "get_project_answers",
    "project_answers",
    "register_project_answers",
]
