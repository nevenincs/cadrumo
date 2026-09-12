"""Profile construction helpers for deadline and schedule consumers.

The helper projects a ``ProfileRecord.values``-shaped mapping into an
:class:`TaxpayerProfile` through
:func:`~cadrumo.core.setup_answers.project_setup_answers`, which reads
stored facts by their profile path and applies the canonical-token
parsing every field declares.

The projection deliberately depends on the core answer table and not on
any interactive surface. Deciding which modelos a taxpayer must file is a
regulatory computation that runs on stored facts; when it instead walked
the terminal wizard's question catalogue, a schedule could not be
computed in a process that had never built a setup UI, and the UI could
not be replaced without moving the tax logic with it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import TypedDict

from ...core.aggregation import ThirdPartyDeclarationRole
from ...core.modelo import Modelo
from ...core.parsing.dates import parse_date as _parse_date_canonical
from ...core.parsing.utils import parse_bool as _parse_bool
from ...core.period import Period
from ...core.setup_answers import SetupAnswers, project_setup_answers
from ..contribuyente.entity_type import EntityType, LegalEntityForm
from ..contribuyente.renta_codes import FiscalResidency
from .errors import ProfileError
from .models import (
    CrossPeriodGroupMemberRoster,
    IrpfActivityKind,
    IrpfEstimationRegime,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloEnrollment,
    ModeloIVAProfile,
    TaxpayerProfile,
)


def taxpayer_profile_from_mapping(
    values: Mapping[str, object],
    *,
    tax_id_default: str,
    iva_regime_default: IVARegime = IVARegime.GENERAL,
) -> TaxpayerProfile:
    """Build an :class:`TaxpayerProfile` from a profile-values mapping.

    The mapping is projected through the descriptor's
    ``project_answers`` so canonical-token semantics for every
    boolean / select / text field stay in lockstep with the wizard's
    on-prompt validation. Missing identity fields fall back to
    ``tax_id_default``. Missing IVA regime falls back to
    ``NO_APLICA`` for natural persons without economic-activity income
    and to ``iva_regime_default`` for profiles that still require an
    IVA regime declaration.
    """
    canonical, padded = _canonicalize_and_pad(values, tax_id_default=tax_id_default)
    typed = project_setup_answers(padded)
    return _build_taxpayer_profile(
        canonical,
        typed,
        tax_id_default=tax_id_default,
        iva_regime_default=iva_regime_default,
    )


def _canonicalize_and_pad(
    values: Mapping[str, object],
    *,
    tax_id_default: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Coerce ``values`` to canonical-token strings and pad it for projection.

    Returns ``(canonical, padded)``: ``canonical`` is the raw mapping
    stringified to canonical tokens (used throughout the caller to read back
    individual fields); ``padded`` layers the identity/activity defaults and
    bare-flag forwarding ``project_answers`` needs to run its strict
    validation against a well-formed shape.
    """
    canonical = _canonicalize_values(values)
    padded = _pad_projection_values(canonical, tax_id_default=tax_id_default)
    _forward_bare_profile_flags(canonical, padded)
    return canonical, padded


def _canonicalize_values(values: Mapping[str, object]) -> dict[str, str]:
    """Stringify profile facts and normalize the IVA selector token."""
    canonical: dict[str, str] = {key: _stringify(raw) for key, raw in values.items()}
    if canonical.get("iva.regime"):
        canonical["iva.regime"] = canonical["iva.regime"].strip().upper().replace("-", "_")
    return canonical


def _pad_projection_values(canonical: Mapping[str, str], *, tax_id_default: str) -> dict[str, str]:
    """Add only the structural values required by strict answer projection."""
    padded = dict(canonical)
    padded.setdefault("identity.tax_id", canonical.get("tax.id") or tax_id_default)
    padded.setdefault("activities.description", canonical.get("activity") or "schedule-only")
    if "tax.id" in canonical and "identity.tax_id" not in canonical:
        padded["identity.tax_id"] = canonical["tax.id"]
    if "activity" in canonical and "activities.description" not in canonical:
        padded["activities.description"] = canonical["activity"]
    return padded


_BARE_PROFILE_FLAG_KEYS: tuple[tuple[str, str], ...] = (
    ("has_employees", "withholding.has_employees"),
    ("colegio_concertado", "withholding.colegio_concertado"),
    ("pays_professionals_with_retencion", "withholding.pays_professionals_with_retencion"),
    ("art109_activity_income_withholding_ge_70pct", "irpf.art109_activity_income_withholding_ge_70pct"),
    ("pays_rent_with_retencion", "withholding.pays_rent_with_retencion"),
    ("pays_capital_income_with_retencion", "withholding.pays_capital_income_with_retencion"),
    ("does_intracomunitario", "iva.does_intracomunitario"),
    ("bienes_extranjero_above_threshold", "obligations.bienes_extranjero_above_threshold"),
    ("monedas_virtuales_extranjero_above_threshold", "obligations.monedas_virtuales_extranjero_above_threshold"),
    ("enrollment.large_company", "censo.large_company"),
    ("enrollment.public_administration_budget_gt_6000000", "censo.public_administration_budget_gt_6000000"),
)


def _forward_bare_profile_flags(canonical: Mapping[str, str], padded: dict[str, str]) -> None:
    """Forward legacy bare flag names to the canonical wizard paths."""
    for bare, canonical_key in _BARE_PROFILE_FLAG_KEYS:
        if bare in canonical and canonical_key not in canonical:
            padded[canonical_key] = canonical[bare]


class _ObjectiveEstimationFields(TypedDict):
    objective_estimation_prior_year_gross_income_eur: Decimal | None
    objective_estimation_prior_year_invoice_gross_income_eur: Decimal | None
    objective_estimation_prior_year_agri_livestock_forest_gross_eur: Decimal | None
    objective_estimation_prior_year_purchases_eur: Decimal | None
    objective_estimation_modulos_iae_epigraph: str
    objective_estimation_modulos_module_1_units: Decimal | None
    objective_estimation_modulos_module_2_units: Decimal | None
    objective_estimation_modulos_module_3_units: Decimal | None
    objective_estimation_modulos_module_4_units: Decimal | None
    objective_estimation_modulos_module_5_units: Decimal | None
    objective_estimation_modulos_module_6_units: Decimal | None
    objective_estimation_modulos_module_7_units: Decimal | None


class _ProfileAxisFields(TypedDict):
    tax_id: str
    entity_type: EntityType | None
    declaration_roles: frozenset[ThirdPartyDeclarationRole]
    legal_entity_form: LegalEntityForm | None
    irpf_income_categories: frozenset[IrpfIncomeCategory]
    irpf_estimation_regime: IrpfEstimationRegime | None
    irpf_activity_kind: IrpfActivityKind | None
    iva_regime: IVARegime


class _ProfileWithholdingFields(TypedDict):
    has_employees: bool
    colegio_concertado: bool | None
    pays_professionals_with_retencion: bool
    professional_income_withholding_ge_70pct: bool
    art109_activity_income_withholding_ge_70pct: bool
    pays_rent_with_retencion: bool
    pays_capital_income_with_retencion: bool


class _ProfileObligationFields(TypedDict):
    does_intracomunitario: bool
    third_party_transactions_above_347_threshold: bool
    bienes_extranjero_above_threshold: bool
    monedas_virtuales_extranjero_above_threshold: bool


class _ProfileRelationshipFields(TypedDict):
    iva: ModeloIVAProfile | None
    cross_period_group_member_rosters: tuple[CrossPeriodGroupMemberRoster, ...]
    enrollment: ModeloEnrollment


class _ProfileAddressFields(TypedDict):
    fiscal_address_cadastral_reference: str
    fiscal_address_is_habitual_vivienda: bool


class _ProfileActivityFields(TypedDict):
    activity_start_date: date | None
    activity_end_date: date | None
    incn_prior_12_months: Decimal | None


class _ProfileCorporateFields(TypedDict):
    new_entity_first_two_profit_periods: bool | None
    ley_49_2002_special_regime_option_declared: bool | None
    ley_49_2002_special_regime_option_date: date | None
    ley_49_2002_special_regime_renunciation_declared: bool | None
    ley_49_2002_special_regime_renunciation_date: date | None


class _ProfileEstablishmentFields(TypedDict):
    establecimiento_type: str
    elected_withholding_pct: str
    vivienda_office_total_m2: Decimal | None
    vivienda_office_office_m2: Decimal | None
    iae_epigraph: str
    notes: str


class _ProfileRegimeFields(TypedDict):
    irpf_special_regime: IrpfSpecialRegime | None
    special_regime_start_date: date | None
    fiscal_residency: FiscalResidency | None
    country_of_fiscal_residence: str | None


class _ProfileRepresentativeFields(TypedDict):
    representante_fiscal_nif: str | None
    representante_fiscal_nombre: str | None


class _ProfilePagadoresFields(TypedDict):
    irpf_pagadores_count: int | None
    irpf_pagadores_secondary_income: Decimal | None
    irpf_pagadores_total_work_income: Decimal | None


def _objective_estimation_fields(canonical: Mapping[str, str]) -> _ObjectiveEstimationFields:
    """Return the estimación objetiva (módulos) ``TaxpayerProfile`` kwargs.

    Groups the prior-year gross-income figures and the seven módulos unit
    counts the M131/M303 régimen de módulos formulas consume, keeping this
    cohesive field family out of the main constructor call.
    """
    return _ObjectiveEstimationFields(
        objective_estimation_prior_year_gross_income_eur=_parse_decimal(
            canonical.get("irpf.objective_estimation_prior_year_gross_income_eur"),
        ),
        objective_estimation_prior_year_invoice_gross_income_eur=_parse_decimal(
            canonical.get("irpf.objective_estimation_prior_year_invoice_gross_income_eur"),
        ),
        objective_estimation_prior_year_agri_livestock_forest_gross_eur=_parse_decimal(
            canonical.get("irpf.objective_estimation_prior_year_agri_livestock_forest_gross_eur"),
        ),
        objective_estimation_prior_year_purchases_eur=_parse_decimal(
            canonical.get("irpf.objective_estimation_prior_year_purchases_eur"),
        ),
        objective_estimation_modulos_iae_epigraph=canonical.get(
            "irpf.objective_estimation_modulos_iae_epigraph",
            "",
        ),
        objective_estimation_modulos_module_1_units=_parse_decimal(
            canonical.get("irpf.objective_estimation_modulos_module_1_units"),
        ),
        objective_estimation_modulos_module_2_units=_parse_decimal(
            canonical.get("irpf.objective_estimation_modulos_module_2_units"),
        ),
        objective_estimation_modulos_module_3_units=_parse_decimal(
            canonical.get("irpf.objective_estimation_modulos_module_3_units"),
        ),
        objective_estimation_modulos_module_4_units=_parse_decimal(
            canonical.get("irpf.objective_estimation_modulos_module_4_units"),
        ),
        objective_estimation_modulos_module_5_units=_parse_decimal(
            canonical.get("irpf.objective_estimation_modulos_module_5_units"),
        ),
        objective_estimation_modulos_module_6_units=_parse_decimal(
            canonical.get("irpf.objective_estimation_modulos_module_6_units"),
        ),
        objective_estimation_modulos_module_7_units=_parse_decimal(
            canonical.get("irpf.objective_estimation_modulos_module_7_units"),
        ),
    )


def _build_taxpayer_profile(
    canonical: dict[str, str],
    typed: SetupAnswers,
    *,
    tax_id_default: str,
    iva_regime_default: IVARegime,
) -> TaxpayerProfile:
    """Assemble the profile from ordered, domain-specific field families."""
    return TaxpayerProfile(
        **_resolve_profile_axes(
            canonical,
            typed,
            tax_id_default=tax_id_default,
            iva_regime_default=iva_regime_default,
        ),
        **_resolve_profile_withholding_fields(typed),
        **_objective_estimation_fields(canonical),
        **_resolve_profile_obligation_fields(typed),
        **_resolve_profile_relationship_fields(canonical, typed),
        **_resolve_profile_address_fields(canonical),
        **_resolve_profile_activity_fields(canonical),
        **_resolve_profile_corporate_fields(canonical),
        **_resolve_profile_establishment_fields(canonical, typed),
        **_resolve_profile_regime_fields(canonical, typed),
        **_resolve_profile_representative_fields(canonical),
        **_resolve_profile_pagadores_fields(canonical),
    )


def _resolve_profile_axes(
    canonical: Mapping[str, str],
    typed: SetupAnswers,
    *,
    tax_id_default: str,
    iva_regime_default: IVARegime,
) -> _ProfileAxisFields:
    """Resolve identity, tax axes, and the profile-level IVA default."""
    entity_type = typed.entity_type or None
    legal_entity_form = typed.legal_entity_form or None
    income_categories = _resolve_income_categories(typed.irpf_income_categories)
    declaration_roles = _resolve_declaration_roles(typed.declaration_roles)
    estimation_regime = typed.irpf_estimation_regime or None
    activity_kind = typed.irpf_activity_kind or None
    tax_id = canonical.get("identity.tax_id") or canonical.get("tax.id") or tax_id_default
    iva_regime = _resolve_iva_regime(
        canonical.get("iva.regime"),
        _default_iva_regime_for_profile(
            entity_type=entity_type,
            income_categories=income_categories,
            configured_default=iva_regime_default,
        ),
    )
    return {
        "tax_id": tax_id,
        "entity_type": entity_type,
        "declaration_roles": declaration_roles,
        "legal_entity_form": legal_entity_form,
        "irpf_income_categories": income_categories,
        "irpf_estimation_regime": estimation_regime,
        "irpf_activity_kind": activity_kind,
        "iva_regime": iva_regime,
    }


def _resolve_profile_withholding_fields(typed: SetupAnswers) -> _ProfileWithholdingFields:
    """Project the withholding answers that are already typed by SetupAnswers."""
    colegio_concertado = typed.colegio_concertado if isinstance(typed.colegio_concertado, bool) else None
    return {
        "has_employees": typed.has_employees,
        "colegio_concertado": colegio_concertado,
        "pays_professionals_with_retencion": typed.pays_professionals_with_retencion,
        "professional_income_withholding_ge_70pct": typed.professional_income_withholding_ge_70pct,
        "art109_activity_income_withholding_ge_70pct": typed.art109_activity_income_withholding_ge_70pct,
        "pays_rent_with_retencion": typed.pays_rent_with_retencion,
        "pays_capital_income_with_retencion": typed.pays_capital_income_with_retencion,
    }


def _resolve_profile_obligation_fields(typed: SetupAnswers) -> _ProfileObligationFields:
    """Project the obligation flags that are already typed by SetupAnswers."""
    return {
        "does_intracomunitario": typed.does_intracomunitario,
        "third_party_transactions_above_347_threshold": typed.third_party_transactions_above_347_threshold,
        "bienes_extranjero_above_threshold": typed.bienes_extranjero_above_threshold,
        "monedas_virtuales_extranjero_above_threshold": typed.monedas_virtuales_extranjero_above_threshold,
    }


def _resolve_profile_relationship_fields(
    canonical: Mapping[str, str],
    typed: SetupAnswers,
) -> _ProfileRelationshipFields:
    """Resolve IVA detail, grouped rosters, and enrollment facts."""
    return {
        "iva": _resolve_modelo_iva_profile(canonical, typed),
        "cross_period_group_member_rosters": _parse_cross_period_group_member_rosters(canonical),
        "enrollment": ModeloEnrollment(
            large_company=typed.enrollment_large_company,
            public_administration_budget_gt_6000000=typed.enrollment_public_administration_budget_gt_6000000,
        ),
    }


def _resolve_profile_address_fields(canonical: Mapping[str, str]) -> _ProfileAddressFields:
    """Resolve fiscal-address facts and preserve the explicit bool parser."""
    return {
        "fiscal_address_cadastral_reference": canonical.get("address.cadastral_reference", ""),
        "fiscal_address_is_habitual_vivienda": _parse_bool(canonical.get("address.is_habitual_vivienda")) or False,
    }


def _resolve_profile_activity_fields(canonical: Mapping[str, str]) -> _ProfileActivityFields:
    """Resolve activity dates and the prior-year INCN amount."""
    return {
        "activity_start_date": _parse_date(canonical.get("censo.activity_start_date")),
        "activity_end_date": _parse_date(canonical.get("censo.activity_end_date")),
        "incn_prior_12_months": _parse_decimal(canonical.get("taxpayer_type.incn_prior_12_months")),
    }


def _resolve_profile_corporate_fields(canonical: Mapping[str, str]) -> _ProfileCorporateFields:
    """Resolve corporate option declarations and their dates."""
    from ..calculations.registry.setup_profile_bindings import profile_field_bindings

    resolved: dict[str, object] = {}
    for field, path in profile_field_bindings().items():
        raw = canonical.get(path)
        if field == "new_entity_first_two_profit_periods" or field.endswith("_declared"):
            resolved[field] = _parse_optional_bool(raw)
        elif field.endswith("_date"):
            resolved[field] = _parse_date(raw)
    expected = set(_ProfileCorporateFields.__annotations__)
    if set(resolved) != expected:
        raise ProfileError(
            "registry setup profile catalogue does not declare the complete corporate field set",
        )
    return resolved  # type: ignore[return-value]


def _resolve_profile_establishment_fields(
    canonical: Mapping[str, str],
    typed: SetupAnswers,
) -> _ProfileEstablishmentFields:
    """Resolve establishment, office, activity, and user-note fields."""
    return {
        "establecimiento_type": canonical.get("censo.establecimiento_type", ""),
        "elected_withholding_pct": canonical.get("censo.elected_withholding_pct", ""),
        "vivienda_office_total_m2": _parse_decimal(canonical.get("vivienda_office.total_m2")),
        "vivienda_office_office_m2": _parse_decimal(canonical.get("vivienda_office.office_m2")),
        "iae_epigraph": canonical.get("activities.iae_epigraph", ""),
        "notes": typed.notes,
    }


def _resolve_profile_regime_fields(
    canonical: Mapping[str, str],
    typed: SetupAnswers,
) -> _ProfileRegimeFields:
    """Resolve special-regime and fiscal-residency fallback facts."""
    # Prefer typed wizard answers; fall back to canonical path-keyed values so
    # persisted facts remain reachable before a wizard question is added.
    return {
        "irpf_special_regime": _resolve_special_regime(
            typed.irpf_special_regime or canonical.get("irpf.special_regime", ""),
        ),
        "special_regime_start_date": _parse_date(
            typed.irpf_special_regime_start_date or canonical.get("irpf.special_regime_start_date"),
        ),
        "fiscal_residency": _resolve_fiscal_residency(
            typed.fiscal_residency or canonical.get("taxpayer_type.fiscal_residency", ""),
        ),
        "country_of_fiscal_residence": _coerce_country_code(
            typed.country_of_fiscal_residence or canonical.get("taxpayer_type.country_of_fiscal_residence", ""),
        ),
    }


def _resolve_profile_representative_fields(canonical: Mapping[str, str]) -> _ProfileRepresentativeFields:
    """Resolve optional fiscal-representative identity facts."""
    return {
        "representante_fiscal_nif": canonical.get("taxpayer_type.representante_fiscal_nif") or None,
        "representante_fiscal_nombre": canonical.get("taxpayer_type.representante_fiscal_nombre") or None,
    }


def _resolve_profile_pagadores_fields(canonical: Mapping[str, str]) -> _ProfilePagadoresFields:
    """Resolve the multiple-payer work-income facts."""
    return {
        "irpf_pagadores_count": _parse_optional_int(canonical.get("irpf.pagadores_count")),
        "irpf_pagadores_secondary_income": _parse_decimal(canonical.get("irpf.pagadores_secondary_income")),
        "irpf_pagadores_total_work_income": _parse_decimal(canonical.get("irpf.pagadores_total_work_income")),
    }


def _parse_optional_bool(raw: str | None) -> bool | None:
    """Three-state boolean: undeclared (``None``), affirmative, or negative.

    Distinguishes an absent fact from a positively-declared ``False``.
    The new-entity first-two-profit-periods state is opt-in: a profile
    that has not declared the fact must remain outside the LIS Art. 29
    15 percent override, which requires telling ``None`` apart from
    ``False`` at the typed boundary.

    The three-state shape is exactly what the canonical parser already
    returns, so this delegates rather than restating the token sets --
    which is what it used to do, while importing that same parser.
    """
    return _parse_bool(raw)


def _accepted(enum: type[StrEnum]) -> str:
    """Render a closed value set for a refusal, derived from the enum itself.

    Derived rather than hand-listed so a new member cannot ship while the
    refusal keeps naming the old set, which would send an operator looking
    for a value the code already accepts.
    """
    return ", ".join(sorted(member.value for member in enum))


def _resolve_m303_tax_territory(raw: str) -> M303TaxTerritory:
    if not raw.strip():
        raise ProfileError(
            f"tax_residence.jurisdiction_scope must be explicitly declared for Modelo IVA; "
            f"accepted values: {_accepted(M303TaxTerritory)}",
        )
    try:
        return M303TaxTerritory(raw)
    except ValueError as exc:
        raise ProfileError(
            f"unsupported tax_residence.jurisdiction_scope {raw!r}; accepted values: {_accepted(M303TaxTerritory)}",
        ) from exc


#: Every profile path whose presence claims the Modelo IVA block.
#:
#: The claiming set and :data:`MODELO_IVA_BLOCK_REQUIRED_PATHS` are one
#: family read from both directions: declaring any path here obliges every
#: path there. Consumers that gate a surface on the block -- the wizard's
#: question visibility, profile completeness -- need the membership set
#: itself, not only the mapping-shaped
#: :func:`profile_claims_modelo_iva_block` predicate over it.
MODELO_IVA_BLOCK_CLAIMING_PATHS: frozenset[str] = frozenset(
    {
        "iva.regime",
        "iva.roi_enrolled",
        "iva.oss_enrolled",
        "iva.group_member_enrolled",
        "iva.group_dominant_entity_enrolled",
        "iva.sii_enrolled",
        "iva.redeme_enrolled",
        "iva.intracommunity_operations_exceed_50000_eur",
        "iva.m303_regime_composition",
        "iva.cash_accounting_regime_enrolled",
        "iva.voluntary_sii_enrolled",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
    },
)

#: Booleans a claimed IVA block must state either way.
#:
#: Undeclared is not the same answer as "no" for these four: each selects a
#: filing obligation or a deduction entitlement, so defaulting an unanswered
#: one to ``False`` would file a taxpayer out of a regime they never spoke
#: about.
_MODELO_IVA_REQUIRED_BOOL_PATHS = (
    "iva.redeme_enrolled",
    "iva.cash_accounting_regime_enrolled",
    "iva.voluntary_sii_enrolled",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
)

#: Every path :func:`_resolve_modelo_iva_profile` refuses to build without.
#:
#: Declared beside the resolver that enforces it so the readiness surfaces
#: and the resolver read ONE answer. They did not: the resolver hard-required
#: six facts while profile completeness knew of none of them, so a profile
#: declaring any IVA fact was reported ready and then refused two commands
#: later by a resolver naming a path no surface had asked for.
MODELO_IVA_BLOCK_REQUIRED_PATHS: tuple[str, ...] = (
    "iva.m303_regime_composition",
    "tax_residence.jurisdiction_scope",
    *_MODELO_IVA_REQUIRED_BOOL_PATHS,
)


def profile_claims_modelo_iva_block(values: Mapping[str, object]) -> bool:
    """Report whether ``values`` declares any fact owned by the Modelo IVA block.

    Presence is value-bearing, not truth-bearing: answering "no" to an IVA
    enrolment still claims the block, because declining a regime is a
    declaration about IVA. Only an absent or blank path leaves it unclaimed.
    """
    return any(_declared(values.get(path)) for path in MODELO_IVA_BLOCK_CLAIMING_PATHS)


def modelo_iva_profile_required_paths(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return the profile paths a claimed Modelo IVA block obliges ``values`` to carry.

    Empty when no IVA fact is declared at all, so a taxpayer with no IVA
    obligation is never asked for one.
    """
    if not profile_claims_modelo_iva_block(values):
        return ()
    return MODELO_IVA_BLOCK_REQUIRED_PATHS


def _declared(value: object) -> bool:
    return value is not None and bool(str(value).strip())


def _required_iva_bool(value: object, *, path: str) -> bool:
    if not isinstance(value, bool):
        raise ProfileError(f"{path} must be explicitly declared as yes or no; it is currently undeclared")
    return value


def _resolve_modelo_iva_profile(canonical: Mapping[str, str], typed: SetupAnswers) -> ModeloIVAProfile | None:
    """Build an IVA block only when a block-owned fact is explicitly present."""
    if not profile_claims_modelo_iva_block(canonical):
        return None
    if not typed.iva_m303_regime_composition:
        raise ProfileError(
            f"iva.m303_regime_composition must be explicitly declared for Modelo IVA; "
            f"accepted values: {_accepted(M303RegimeComposition)}",
        )
    try:
        composition = M303RegimeComposition(typed.iva_m303_regime_composition)
    except ValueError as exc:
        raise ProfileError(
            f"unsupported iva.m303_regime_composition {typed.iva_m303_regime_composition!r}; "
            f"accepted values: {_accepted(M303RegimeComposition)}",
        ) from exc
    return ModeloIVAProfile(
        tax_territory=_resolve_m303_tax_territory(typed.tax_residence_jurisdiction_scope),
        regime_composition=composition,
        roi_enrolled=typed.iva_roi_enrolled is True,
        oss_enrolled=typed.iva_oss_enrolled is True,
        group_member_enrolled=typed.iva_group_member_enrolled is True,
        group_dominant_entity_enrolled=typed.iva_group_dominant_entity_enrolled is True,
        sii_enrolled=typed.iva_sii_enrolled is True,
        redeme_enrolled=_required_iva_bool(typed.iva_redeme_enrolled, path="iva.redeme_enrolled"),
        intracommunity_operations_exceed_50000_eur=(typed.iva_intracommunity_operations_exceed_50000_eur is True),
        cash_accounting_regime_enrolled=_required_iva_bool(
            typed.iva_cash_accounting_regime_enrolled,
            path="iva.cash_accounting_regime_enrolled",
        ),
        voluntary_sii_enrolled=_required_iva_bool(
            typed.iva_voluntary_sii_enrolled,
            path="iva.voluntary_sii_enrolled",
        ),
        hydrocarbon_deposit_advance_payment_deduction_entitled=_required_iva_bool(
            typed.iva_hydrocarbon_deposit_advance_payment_deduction_entitled,
            path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled",
        ),
    )


def _parse_date(raw: str | None) -> date | None:
    try:
        return _parse_date_canonical(raw, fmt="iso8601", on_error="raise")
    except ValueError as exc:
        raise ProfileError(f"invalid censo date {raw!r}; expected ISO-8601") from exc


def _parse_decimal(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    try:
        return Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ProfileError(f"invalid censo decimal {raw!r}") from exc


def _parse_optional_int(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _parse_cross_period_group_member_rosters(canonical: Mapping[str, str]) -> tuple[CrossPeriodGroupMemberRoster, ...]:
    """Parse profile-declared member rosters for grouped cross-period fan-in.

    Supported profile fact keys:

    - ``cross_period.group_member_roster.<source_modelo>.<year>.<period>``
    - ``iva_grupo.member_roster.<source_modelo>.<year>.<period>``
    - ``iva_grupo.member_roster.<year>.<period>`` (defaults source modelo to 322)
    """
    rosters: list[CrossPeriodGroupMemberRoster] = []
    for key, raw in canonical.items():
        source_modelo, filing_year, period = _parse_group_member_roster_key(key)
        if source_modelo is None or filing_year is None or period is None:
            continue
        member_nifs = tuple(token.strip() for token in raw.replace(";", ",").split(",") if token.strip())
        if not member_nifs:
            continue
        rosters.append(
            CrossPeriodGroupMemberRoster(
                source_modelo=Modelo(source_modelo),
                filing_year=filing_year,
                period=Period.from_year_and_code(filing_year, period),
                member_nifs=member_nifs,
            ),
        )
    return tuple(
        sorted(
            rosters,
            key=lambda item: (item.source_modelo, item.period.filing_year, item.period.registry_token),
        ),
    )


def _parse_group_member_roster_key(key: str) -> tuple[str | None, int | None, str | None]:
    for prefix in ("cross_period.group_member_roster.", "iva_grupo.member_roster."):
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix) :].split(".")
        if len(parts) == 3 and parts[1].isdigit():
            return parts[0], int(parts[1]), parts[2]
        if len(parts) == 2 and parts[0].isdigit():
            return Modelo("3").value, int(parts[0]), parts[1]
    return None, None, None


def _stringify(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, bool):
        return "true" if raw else "false"
    return str(raw).strip()


def _resolve_income_categories(raw: str) -> frozenset[IrpfIncomeCategory]:
    """Parse the comma-separated income-category token into a typed set.

    ``SetupAnswers.irpf_income_categories`` carries the canonical
    comma-separated string the CHECKBOX widget produces; this projects
    it into the typed ``frozenset`` ``TaxpayerProfile`` declares.
    """
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    return frozenset(IrpfIncomeCategory(token) for token in tokens)


def _resolve_declaration_roles(raw: str) -> frozenset[ThirdPartyDeclarationRole]:
    """Parse the comma-separated role token into a typed set.

    Mirrors :func:`_resolve_income_categories`: ``SetupAnswers.declaration_roles``
    carries the canonical comma-separated string the CHECKBOX widget produces;
    this projects it into the typed ``frozenset`` ``TaxpayerProfile`` declares.
    """
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    return frozenset(ThirdPartyDeclarationRole(token) for token in tokens)


def _resolve_iva_regime(raw: str | None, default: IVARegime) -> IVARegime:
    if raw is None or raw == "":
        return default
    canonical = raw.strip().upper().replace("-", "_")
    return IVARegime(canonical)


def _default_iva_regime_for_profile(
    *,
    entity_type: EntityType | None,
    income_categories: frozenset[IrpfIncomeCategory],
    configured_default: IVARegime,
) -> IVARegime:
    if entity_type is EntityType.NATURAL_PERSON and IrpfIncomeCategory.ACTIVIDAD_ECONOMICA not in income_categories:
        return IVARegime.NO_APLICA
    return configured_default


def _resolve_fiscal_residency(raw: FiscalResidency | str) -> FiscalResidency | None:
    """Project the SetupAnswers fiscal-residency field to a typed enum or None.

    A blank string means the operator has not declared fiscal residency
    (treated as RESIDENT_IRPF by engine consumers); typed ``None`` signals that.
    """
    if raw == "":
        return None
    if isinstance(raw, FiscalResidency):
        return raw
    return FiscalResidency(raw)


def _coerce_country_code(raw: str) -> str | None:
    """Normalise a raw country-code token to upper-case or None when absent."""
    if not raw or raw.strip() == "":
        return None
    return raw.strip().upper()


def _resolve_special_regime(raw: IrpfSpecialRegime | str) -> IrpfSpecialRegime | None:
    """Project the SetupAnswers special-regime field to a typed enum or None.

    A blank string means the operator has not declared a special regime
    (equivalent to the general case); the typed ``None`` signals that
    to downstream consumers.
    """
    if raw == "":
        return None
    if isinstance(raw, IrpfSpecialRegime):
        return raw
    return IrpfSpecialRegime(raw)
