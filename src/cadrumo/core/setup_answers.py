"""Canonical typed-answer model and projection slot for the setup flow.

:class:`SetupAnswers` is the authoritative typed-answers model for the wizard
``setup`` flow. Domain modules import it from here, not from the application
wizard layer, so the permitted dependency direction remains domain-to-core
rather than domain-to-application.

This module owns typed answer validation and the core registration slot for the
reverse projection from persisted canonical-token strings. It does not own
prompt rendering, profile persistence, secure storage, deadline scheduling, or
registry semantics. The application wizard registers its concrete projector at
startup with :func:`register_project_answers`; domain consumers call
:func:`project_answers` through this core slot and receive
:class:`ProjectAnswersNotRegisteredError` if startup has not installed it.

The contract mirrors :mod:`cadrumo.core.wizard_catalogue`: the application layer
declares the ``SETUP_FLOW`` descriptor, while core exposes the stable answer
model and the projection hook. Downstream profile construction, including
``taxpayer_profile_from_mapping``, therefore stays aligned with wizard
canonical-token parsing without importing application modules directly.

Domain taxonomy types (``EntityType``, ``IVARegime``, etc.) are imported lazily
inside validators rather than at module level to break the circular import
path: ``cadrumo.core.setup_answers`` -> ``cadrumo.domain.deadlines._models`` ->
``cadrumo.domain.deadlines.__init__`` -> ``cadrumo.domain.deadlines._profiles`` ->
``cadrumo.core.setup_answers``. This mirrors the deferral strategy used in
``cadrumo.core.resources._repos.*`` and is the established project pattern.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from ..core import STRICT_FROZEN_CONFIG
from .errors import CoreError, ProfileAnswerTypeError
from .external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from .logging import get_logger
from .parsing import parse_bool

_log = get_logger(__name__)


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


# ---------------------------------------------------------------------------
# project_answers registration slot
# ---------------------------------------------------------------------------


class ProjectAnswersRegistrationError(CoreError):
    """Raised when :func:`register_project_answers` is called a second time with a different callable.

    A double-registration with the same callable is a safe no-op; a double-registration
    with a *different* callable is a programming error that must be surfaced as a
    typed, registry-bound exception so callers receive a structured error envelope
    rather than a bare :exc:`RuntimeError`.
    """


class ProjectAnswersNotRegisteredError(CoreError):
    """Raised when domain code calls :func:`project_answers` before registration."""

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

    Satisfied by ``cadrumo.application.wizard._persistence.project_answers``.
    Domain code depends only on this protocol.
    """

    # KWARGS-ANY-RATIONALE-PROFILE-WIZARD-FLOW-CIRCULAR:
    # WizardFlow type lives in cadrumo.application.wizard; importing here would
    # create circular dependency.
    def __call__(self, flow: Any, values: Mapping[str, str]) -> BaseModel:
        """Project canonical-token values into the typed answers model."""
        ...  # pragma: no cover


_PROJECT_ANSWERS_SLOT: list[ProjectAnswersFn] = []


def register_project_answers(fn: ProjectAnswersFn) -> None:
    """Register the concrete project_answers implementation from the application layer.

    Call exactly once at application startup (e.g. in
    ``cadrumo.application.wizard._persistence`` module body after the function is
    defined). A second call with an identical callable is a no-op; a second
    call with a different callable raises :class:`ProjectAnswersRegistrationError`.
    Domain code should depend on :func:`project_answers`, not on the
    application-layer implementation object registered here.
    """
    if _PROJECT_ANSWERS_SLOT:
        if _PROJECT_ANSWERS_SLOT[0] is fn:
            return
        raise ProjectAnswersRegistrationError(
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
# WizardFlow type lives in cadrumo.application.wizard; importing here would create
# circular dependency.
def project_answers(flow: Any, values: Mapping[str, str]) -> BaseModel:
    """Invoke the registered project_answers implementation.

    Delegates to the application-layer function registered via
    :func:`register_project_answers`.  Domain callers import this function from
    ``cadrumo.core.setup_answers`` so they never acquire a direct dependency on
    ``cadrumo.application.wizard._persistence``.

    Args:
        flow: The wizard flow descriptor identifying which flow to
            project answers for.
        values: Mapping of canonical token keys to raw string values
            collected from the wizard or read from profile storage. Blank
            strings preserve undeclared optional facts for the registered
            projector to interpret.

    Returns:
        A typed answers model instance produced by the registered
        implementation.
    """
    return get_project_answers()(flow, values)


# ---------------------------------------------------------------------------
# Profile-record projection
#
# The mapping below is what a persisted profile record needs to fill
# :class:`SetupAnswers`: for each answer field, the profile path its value
# is stored under, the type that value carries, and the default to assume
# when the record is silent. Nothing else — no prompt, no widget, no
# ordering, no visibility condition — participates in the projection.
#
# It lives here, beside the model it fills, because the deadline engine
# projects a taxpayer profile out of stored facts on every schedule
# computation, and that must not depend on the presence of an interactive
# setup surface. Previously the engine reached the same information by
# walking the terminal wizard's question catalogue, which coupled a
# regulatory computation to a UI script and made the wizard undeletable.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetupFieldSpec:
    """Where one :class:`SetupAnswers` field is read from and how it parses."""

    path: str
    """Dotted profile-record path, e.g. ``identity.tax_id``.

    Every path here is declared in the user-profile schema; the schema
    remains the authority on which fields exist, this table only records
    which answer field each one feeds.
    """

    answer_type: type[str] | type[bool]
    """The stored token's type. Only these two occur in the setup answers."""

    default: str | None = None
    """Token to assume when the record carries no value for ``path``.

    ``None`` means "leave the field to the model's own default", which is
    not the same as an empty string: a blank token is a *declared* blank
    and reaches the model, where an optional boolean reads it as
    undeclared rather than as a positive ``False``.
    """


PROFILE_OUTPUT_LANGUAGE_PATH: Final[str] = "preferences.output_language"
"""Dotted profile-record path for the setup flow's output-language answer."""


SETUP_ANSWER_FIELDS: Mapping[str, SetupFieldSpec] = {
    "activity": SetupFieldSpec("activities.description", str),
    "activity_start_date": SetupFieldSpec("censo.activity_start_date", str),
    "address_postcode": SetupFieldSpec("contact.postcode", str),
    "art109_activity_income_withholding_ge_70pct": SetupFieldSpec(
        "irpf.art109_activity_income_withholding_ge_70pct",
        bool,
        "false",
    ),
    "bienes_extranjero_above_threshold": SetupFieldSpec("obligations.bienes_extranjero_above_threshold", bool, "false"),
    "country_of_fiscal_residence": SetupFieldSpec("taxpayer_type.country_of_fiscal_residence", str),
    "does_intracomunitario": SetupFieldSpec("iva.does_intracomunitario", bool, "false"),
    "enrollment_large_company": SetupFieldSpec("censo.large_company", bool, "false"),
    "enrollment_public_administration_budget_gt_6000000": SetupFieldSpec(
        "censo.public_administration_budget_gt_6000000",
        bool,
        "false",
    ),
    "entity_type": SetupFieldSpec("taxpayer_type.entity_type", str),
    "family_descendants_eu_eea_deduction": SetupFieldSpec("renta_family.descendants_eu_eea_deduction", bool, "false"),
    "family_minor_children_in_unit": SetupFieldSpec("renta_family.minor_children_in_unit", bool, "false"),
    "fiscal_residency": SetupFieldSpec("taxpayer_type.fiscal_residency", str, "resident_irpf"),
    "google_export": SetupFieldSpec("capabilities.google_export", bool, "true"),
    "has_employees": SetupFieldSpec("withholding.has_employees", bool, "false"),
    # No default: the Modelo 111 producer refuses an undeclared value rather
    # than assert "not a concerted school" on the operator's behalf, so an
    # unanswered question must stay unanswered here.
    "colegio_concertado": SetupFieldSpec("withholding.colegio_concertado", bool),
    "incn_prior_12_months": SetupFieldSpec("taxpayer_type.incn_prior_12_months", str),
    "irpf_estimation_regime": SetupFieldSpec("irpf.estimation_regime", str),
    "irpf_activity_kind": SetupFieldSpec("irpf.activity_kind", str),
    "irpf_income_categories": SetupFieldSpec("taxpayer_type.irpf_income_categories", str),
    "irpf_special_regime": SetupFieldSpec("irpf.special_regime", str),
    "irpf_special_regime_start_date": SetupFieldSpec("irpf.special_regime_start_date", str),
    "iva_group_dominant_entity_enrolled": SetupFieldSpec("iva.group_dominant_entity_enrolled", bool),
    "iva_group_member_enrolled": SetupFieldSpec("iva.group_member_enrolled", bool),
    "iva_intracommunity_operations_exceed_50000_eur": SetupFieldSpec(
        "iva.intracommunity_operations_exceed_50000_eur",
        bool,
    ),
    "iva_oss_enrolled": SetupFieldSpec("iva.oss_enrolled", bool),
    "iva_redeme_enrolled": SetupFieldSpec("iva.redeme_enrolled", bool),
    "iva_regime": SetupFieldSpec("iva.regime", str),
    "iva_roi_enrolled": SetupFieldSpec("iva.roi_enrolled", bool),
    "iva_sii_enrolled": SetupFieldSpec("iva.sii_enrolled", bool),
    "iva_m303_regime_composition": SetupFieldSpec("iva.m303_regime_composition", str),
    "iva_cash_accounting_regime_enrolled": SetupFieldSpec("iva.cash_accounting_regime_enrolled", bool),
    "iva_voluntary_sii_enrolled": SetupFieldSpec("iva.voluntary_sii_enrolled", bool),
    "iva_hydrocarbon_deposit_advance_payment_deduction_entitled": SetupFieldSpec(
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
        bool,
    ),
    "legal_entity_form": SetupFieldSpec("taxpayer_type.legal_entity_form", str),
    "legal_name": SetupFieldSpec("identity.legal_name", str),
    "ley_49_2002_option_date": SetupFieldSpec("taxpayer_type.ley_49_2002_special_regime_option_date", str),
    "ley_49_2002_option_declared": SetupFieldSpec("taxpayer_type.ley_49_2002_special_regime_option_declared", bool),
    "ley_49_2002_renunciation_date": SetupFieldSpec("taxpayer_type.ley_49_2002_special_regime_renunciation_date", str),
    "ley_49_2002_renunciation_declared": SetupFieldSpec(
        "taxpayer_type.ley_49_2002_special_regime_renunciation_declared",
        bool,
    ),
    "llm_vision": SetupFieldSpec("capabilities.llm_vision", bool, "true"),
    "modelo_111_no_retenciones_periods": SetupFieldSpec("withholding.modelo_111_no_retenciones_periods", str),
    "monedas_virtuales_extranjero_above_threshold": SetupFieldSpec(
        "obligations.monedas_virtuales_extranjero_above_threshold",
        bool,
        "false",
    ),
    "name": SetupFieldSpec("identity.name", str),
    "new_entity_first_two_profit_periods": SetupFieldSpec("taxpayer_type.new_entity_first_two_profit_periods", bool),
    "notes": SetupFieldSpec("identity.notes", str),
    "objective_estimation_modulos_iae_epigraph": SetupFieldSpec("irpf.objective_estimation_modulos_iae_epigraph", str),
    "objective_estimation_modulos_module_1_units": SetupFieldSpec(
        "irpf.objective_estimation_modulos_module_1_units",
        str,
    ),
    "objective_estimation_modulos_module_2_units": SetupFieldSpec(
        "irpf.objective_estimation_modulos_module_2_units",
        str,
    ),
    "objective_estimation_modulos_module_3_units": SetupFieldSpec(
        "irpf.objective_estimation_modulos_module_3_units",
        str,
    ),
    "objective_estimation_modulos_module_4_units": SetupFieldSpec(
        "irpf.objective_estimation_modulos_module_4_units",
        str,
    ),
    "objective_estimation_modulos_module_5_units": SetupFieldSpec(
        "irpf.objective_estimation_modulos_module_5_units",
        str,
    ),
    "objective_estimation_modulos_module_6_units": SetupFieldSpec(
        "irpf.objective_estimation_modulos_module_6_units",
        str,
    ),
    "objective_estimation_modulos_module_7_units": SetupFieldSpec(
        "irpf.objective_estimation_modulos_module_7_units",
        str,
    ),
    "output_language": SetupFieldSpec(PROFILE_OUTPUT_LANGUAGE_PATH, str, "es"),
    "pays_capital_income_with_retencion": SetupFieldSpec(
        "withholding.pays_capital_income_with_retencion",
        bool,
        "false",
    ),
    "pays_professionals_with_retencion": SetupFieldSpec("withholding.pays_professionals_with_retencion", bool, "false"),
    "pays_rent_with_retencion": SetupFieldSpec("withholding.pays_rent_with_retencion", bool, "false"),
    # No setup question ever collected this, so the engine read the model
    # default and a taxpayer who HAD declared the fact was still scheduled
    # as though they had not — the flag governs Modelo 130 applicability.
    # The schema has always declared the path and named this very field in
    # its model selector; only the projection was missing.
    "professional_income_withholding_ge_70pct": SetupFieldSpec(
        "irpf.professional_income_withholding_ge_70pct",
        bool,
        "false",
    ),
    "representante_fiscal_nif": SetupFieldSpec("taxpayer_type.representante_fiscal_nif", str),
    "representante_fiscal_nombre": SetupFieldSpec("taxpayer_type.representante_fiscal_nombre", str),
    "situacion_familiar": SetupFieldSpec("renta_family.situacion_familiar", str),
    "spouse_birth_date": SetupFieldSpec("renta_spouse.birth_date", str),
    "spouse_disability_grade": SetupFieldSpec("renta_spouse.disability_grade", str),
    "spouse_eu_eea_country": SetupFieldSpec("renta_spouse.eu_eea_country", str),
    "spouse_eu_eea_resident": SetupFieldSpec("renta_spouse.eu_eea_resident", bool, "false"),
    "spouse_name": SetupFieldSpec("renta_spouse.name", str),
    "spouse_non_resident_irpf": SetupFieldSpec("renta_spouse.non_resident_irpf", bool, "false"),
    "spouse_sex": SetupFieldSpec("renta_spouse.sex", str),
    "spouse_surnames": SetupFieldSpec("renta_spouse.surnames", str),
    "spouse_tax_id": SetupFieldSpec("renta_spouse.tax_id", str),
    "surnames": SetupFieldSpec("identity.surnames", str),
    "tax_id": SetupFieldSpec("identity.tax_id", str),
    "tax_residence_ccaa": SetupFieldSpec("tax_residence.ccaa", str, "madrid"),
    "tax_residence_jurisdiction_scope": SetupFieldSpec("tax_residence.jurisdiction_scope", str),
    "taxation_type": SetupFieldSpec("renta_filing.declaration_type", str),
    "taxpayer_birth_date": SetupFieldSpec("renta_taxpayer.birth_date", str),
    "taxpayer_death_date": SetupFieldSpec("renta_taxpayer.death_date", str),
    "taxpayer_disability_grade": SetupFieldSpec("renta_taxpayer.disability_grade", str),
    "taxpayer_marital_status": SetupFieldSpec("renta_taxpayer.marital_status", str),
    "taxpayer_marriage_date": SetupFieldSpec("renta_taxpayer.marriage_date", str),
    "taxpayer_sex": SetupFieldSpec("renta_taxpayer.sex", str),
    "third_party_transactions_above_347_threshold": SetupFieldSpec(
        "obligations.third_party_transactions_above_347_threshold",
        bool,
        "false",
    ),
}
"""Every :class:`SetupAnswers` field a persisted profile record can fill.

A field absent from this table is filled by some other route (the
descendant flow writes ``unidad_familiar_descendientes_exclusivos``) and
keeps its model default here.
"""


def project_setup_answers(values: Mapping[str, str]) -> SetupAnswers:
    """Build :class:`SetupAnswers` from a profile-record path mapping.

    A path present in ``values`` wins even when its value is blank, because
    a stored blank is a declared blank; only a genuinely absent path falls
    back to the table's default. A blank boolean projects to the empty
    string rather than ``False`` so that "not declared" survives the round
    trip — collapsing it would let a persistence layer store a positive
    ``"false"`` the operator never asserted.
    """
    typed: dict[str, object] = {}
    for field, spec in SETUP_ANSWER_FIELDS.items():
        raw = values.get(spec.path)
        if raw is None:
            raw = spec.default
        if raw is None:
            continue
        typed[field] = (raw == "true" if raw else "") if spec.answer_type is bool else raw
    return SetupAnswers.model_validate(typed)


# ---------------------------------------------------------------------------
# Lazy domain-type accessors
#
# All domain imports are deferred inside validators and accessors below to
# avoid the circular import:
#   cadrumo.core.setup_answers → cadrumo.domain.deadlines._models
#   → cadrumo.domain.deadlines.__init__ → cadrumo.domain.deadlines._profiles
#   → cadrumo.core.setup_answers   (partially initialised → ImportError)
# ---------------------------------------------------------------------------


# ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE: returns the
# cadrumo.domain.deadlines module object; a typed return would require
# importing the module at definition time, re-introducing the circular
# import described in the block comment above.
def _m() -> Any:
    """Return the cadrumo.domain.deadlines module (lazy)."""
    import importlib

    return importlib.import_module("cadrumo.domain.deadlines")


# ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE: returns the
# cadrumo.domain.contribuyente module object; typed return would require importing the
# module at definition time, re-introducing the circular import.
def _p() -> Any:
    """Return the cadrumo.domain.contribuyente module (lazy)."""
    import importlib

    return importlib.import_module("cadrumo.domain.contribuyente")


# ANY-RETURN-RATIONALE-PROFILE-LAZY-MODULE: returns the CCAA enum class object;
# typed return would require importing the module at definition time,
# re-introducing the circular import.
def _ccaa() -> Any:
    """Return the CCAA enum class (lazy)."""
    import importlib

    return importlib.import_module("cadrumo.domain.contribuyente").CCAA


# ---------------------------------------------------------------------------
# SetupAnswers
# ---------------------------------------------------------------------------


class SetupAnswers(BaseModel):
    """Typed answers collected by the ``setup`` flow.

    Canonical home is :mod:`cadrumo.core.setup_answers`.  The application wizard layer
    imports :class:`SetupAnswers` from here; the domain deadline engine likewise
    imports it from here — no layer needs to cross the hexagonal boundary.

    The model stores canonical answer tokens and typed taxonomy values for the
    setup flow. It is not the persisted profile record and it is not the
    deadline-engine taxpayer profile; those are produced downstream by wizard
    persistence and deadline profile projection. Where validators allow the
    empty string, the value means undeclared/no answer rather than false, zero,
    or a default legal fact.

    Field annotations use ``Any`` for domain taxonomy union types because those
    types are loaded lazily inside validators to prevent a circular import.
    That ``Any`` is not a loose schema: validators enforce the same invariants
    the original typed annotations carried, reject values outside the declared
    enum / blank-string set, and raise
    :class:`~cadrumo.core.errors.ProfileAnswerTypeError`.
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
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            return iva_regime_cls(value.upper())
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
    def _parse_optional_iva_bool(cls, value: object) -> Any:
        return _parse_optional_bool_token(value, field_name="Modelo IVA boolean")

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

    @field_validator("irpf_activity_kind", mode="before")
    @classmethod
    # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR: Pydantic
    # field_validator(mode='before') requires -> Any; actual return is always
    # a typed StrEnum/enum member.
    def _parse_irpf_activity_kind(cls, value: object) -> Any:  # ANY-RETURN-RATIONALE-PROFILE-PYDANTIC-VALIDATOR
        if value == "":
            return ""
        irpf_activity_kind_cls = _m().IrpfActivityKind
        if isinstance(value, irpf_activity_kind_cls):
            return value
        if isinstance(value, str):
            return irpf_activity_kind_cls(value)
        raise ProfileAnswerTypeError(
            "irpf_activity_kind must be an IrpfActivityKind member, string token, or blank",
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
        from ._renta_declaracion_type import RentaDeclaracionType

        renta_declaracion_type_cls = RentaDeclaracionType
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
        from ._renta_declaracion_type import RentaDeclaracionType

        renta_declaracion_type_cls = RentaDeclaracionType
        if self.taxation_type == renta_declaracion_type_cls.JOINT and not self.spouse_tax_id:
            # A stable custom error type (not the generic ``value_error``) lets
            # the operator-facing boundary route this cross-field refusal to its
            # own localized message rather than the raw English text below.
            raise PydanticCustomError(
                "spouse_tax_id_required_joint",
                "spouse_tax_id is required when taxation_type is joint (taxation_type='2')",
            )
        return self

    @model_validator(mode="after")
    def _validate_eu_eea_country_when_resident(self) -> SetupAnswers:
        if self.spouse_eu_eea_resident and not self.spouse_eu_eea_country:
            raise PydanticCustomError(
                "eu_eea_country_required",
                "spouse_eu_eea_country is required when spouse_eu_eea_resident is true",
            )
        return self


__all__ = [
    "PROFILE_OUTPUT_LANGUAGE_PATH",
    "SETUP_ANSWER_FIELDS",
    "ProfileAnswerTypeError",
    "ProjectAnswersFn",
    "ProjectAnswersNotRegisteredError",
    "ProjectAnswersRegistrationError",
    "SetupAnswers",
    "SetupFieldSpec",
    "get_project_answers",
    "project_answers",
    "project_setup_answers",
    "register_project_answers",
]
