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
from typing import TypedDict

from ...core import Modelo, Period
from ...core.parsing import parse_bool as _parse_bool
from ...core.parsing import parse_date as _parse_date_canonical
from ...core.setup_answers import project_setup_answers
from ._errors import ProfileError
from ._models import (
    CrossPeriodGroupMemberRoster,
    EntityType,
    FiscalResidency,
    IrpfIncomeCategory,
    IrpfSpecialRegime,
    IVARegime,
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

    entity_type = typed.entity_type or None
    legal_entity_form = typed.legal_entity_form or None
    income_categories = _resolve_income_categories(typed.irpf_income_categories)
    estimation_regime = typed.irpf_estimation_regime or None
    tax_id = canonical.get("identity.tax_id") or canonical.get("tax.id") or tax_id_default
    iva_regime = _resolve_iva_regime(
        canonical.get("iva.regime"),
        _default_iva_regime_for_profile(
            entity_type=entity_type,
            income_categories=income_categories,
            configured_default=iva_regime_default,
        ),
    )

    return TaxpayerProfile(
        tax_id=tax_id,
        entity_type=entity_type,
        legal_entity_form=legal_entity_form,
        irpf_income_categories=income_categories,
        irpf_estimation_regime=estimation_regime,
        iva_regime=iva_regime,
        has_employees=typed.has_employees,
        pays_professionals_with_retencion=typed.pays_professionals_with_retencion,
        professional_income_withholding_ge_70pct=typed.professional_income_withholding_ge_70pct,
        art109_activity_income_withholding_ge_70pct=typed.art109_activity_income_withholding_ge_70pct,
        pays_rent_with_retencion=typed.pays_rent_with_retencion,
        pays_capital_income_with_retencion=typed.pays_capital_income_with_retencion,
        **_objective_estimation_fields(canonical),
        does_intracomunitario=typed.does_intracomunitario,
        third_party_transactions_above_347_threshold=typed.third_party_transactions_above_347_threshold,
        bienes_extranjero_above_threshold=typed.bienes_extranjero_above_threshold,
        monedas_virtuales_extranjero_above_threshold=typed.monedas_virtuales_extranjero_above_threshold,
        iva=ModeloIVAProfile(
            roi_enrolled=typed.iva_roi_enrolled,
            oss_enrolled=typed.iva_oss_enrolled,
            group_member_enrolled=typed.iva_group_member_enrolled,
            group_dominant_entity_enrolled=typed.iva_group_dominant_entity_enrolled,
            sii_enrolled=typed.iva_sii_enrolled,
            redeme_enrolled=typed.iva_redeme_enrolled,
            intracommunity_operations_exceed_50000_eur=typed.iva_intracommunity_operations_exceed_50000_eur,
        ),
        cross_period_group_member_rosters=_parse_cross_period_group_member_rosters(canonical),
        enrollment=ModeloEnrollment(
            large_company=typed.enrollment_large_company,
            public_administration_budget_gt_6000000=typed.enrollment_public_administration_budget_gt_6000000,
        ),
        fiscal_address_cadastral_reference=canonical.get("address.cadastral_reference", ""),
        fiscal_address_is_habitual_vivienda=_parse_bool(canonical.get("address.is_habitual_vivienda")) or False,
        activity_start_date=_parse_date(canonical.get("censo.activity_start_date")),
        activity_end_date=_parse_date(canonical.get("censo.activity_end_date")),
        incn_prior_12_months=_parse_decimal(canonical.get("taxpayer_type.incn_prior_12_months")),
        new_entity_first_two_profit_periods=_parse_optional_bool(
            canonical.get("taxpayer_type.new_entity_first_two_profit_periods"),
        ),
        ley_49_2002_special_regime_option_declared=_parse_optional_bool(
            canonical.get("taxpayer_type.ley_49_2002_special_regime_option_declared"),
        ),
        ley_49_2002_special_regime_option_date=_parse_date(
            canonical.get("taxpayer_type.ley_49_2002_special_regime_option_date"),
        ),
        ley_49_2002_special_regime_renunciation_declared=_parse_optional_bool(
            canonical.get("taxpayer_type.ley_49_2002_special_regime_renunciation_declared"),
        ),
        ley_49_2002_special_regime_renunciation_date=_parse_date(
            canonical.get("taxpayer_type.ley_49_2002_special_regime_renunciation_date"),
        ),
        establecimiento_type=canonical.get("censo.establecimiento_type", ""),
        elected_withholding_pct=canonical.get("censo.elected_withholding_pct", ""),
        vivienda_office_total_m2=_parse_decimal(canonical.get("vivienda_office.total_m2")),
        vivienda_office_office_m2=_parse_decimal(canonical.get("vivienda_office.office_m2")),
        iae_epigraph=canonical.get("activities.iae_epigraph", ""),
        notes=typed.notes,
        irpf_special_regime=_resolve_special_regime(
            # Prefer the typed wizard answer; fall back to the canonical
            # path-keyed value from record_to_path_values so the field is
            # reachable from persisted facts even before a wizard question is
            # added to the SETUP_FLOW.
            typed.irpf_special_regime or canonical.get("irpf.special_regime", ""),
        ),
        special_regime_start_date=_parse_date(
            typed.irpf_special_regime_start_date or canonical.get("irpf.special_regime_start_date"),
        ),
        fiscal_residency=_resolve_fiscal_residency(
            typed.fiscal_residency or canonical.get("taxpayer_type.fiscal_residency", ""),
        ),
        country_of_fiscal_residence=_coerce_country_code(
            typed.country_of_fiscal_residence or canonical.get("taxpayer_type.country_of_fiscal_residence", ""),
        ),
        representante_fiscal_nif=canonical.get("taxpayer_type.representante_fiscal_nif") or None,
        representante_fiscal_nombre=canonical.get("taxpayer_type.representante_fiscal_nombre") or None,
        irpf_pagadores_count=_parse_optional_int(canonical.get("irpf.pagadores_count")),
        irpf_pagadores_secondary_income=_parse_decimal(canonical.get("irpf.pagadores_secondary_income")),
        irpf_pagadores_total_work_income=_parse_decimal(canonical.get("irpf.pagadores_total_work_income")),
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
    # Coerce mixed-typed mappings to canonical-token strings before the
    # descriptor's projection runs.
    canonical: dict[str, str] = {key: _stringify(raw) for key, raw in values.items()}
    # The wizard's SELECT validator only accepts the IVARegime
    # canonical uppercase token, so the mapping is normalised here
    # against the enum's value form before projection.
    if canonical.get("iva.regime"):
        canonical["iva.regime"] = canonical["iva.regime"].strip().upper().replace("-", "_")

    # SetupAnswers requires identity.tax_id and activities.description;
    # the deadline engine supplies a tax_id default so it can render
    # diagnostic schedules against an empty profile. Pad here so
    # project_answers' strict validation runs against the same shape.
    padded = dict(canonical)
    padded.setdefault("identity.tax_id", canonical.get("tax.id") or tax_id_default)
    padded.setdefault("activities.description", canonical.get("activity") or "schedule-only")
    # Forward selector-keyed input from external callers to the canonical
    # schema path the wizard projects against.
    if "tax.id" in canonical and "identity.tax_id" not in canonical:
        padded["identity.tax_id"] = canonical["tax.id"]
    if "activity" in canonical and "activities.description" not in canonical:
        padded["activities.description"] = canonical["activity"]
    # Bare boolean flag names map to their canonical wizard keys so the
    # descriptor's project_answers picks them up.
    for bare, canonical_key in (
        ("has_employees", "withholding.has_employees"),
        ("pays_professionals_with_retencion", "withholding.pays_professionals_with_retencion"),
        ("art109_activity_income_withholding_ge_70pct", "irpf.art109_activity_income_withholding_ge_70pct"),
        ("pays_rent_with_retencion", "withholding.pays_rent_with_retencion"),
        ("pays_capital_income_with_retencion", "withholding.pays_capital_income_with_retencion"),
        ("does_intracomunitario", "iva.does_intracomunitario"),
        ("bienes_extranjero_above_threshold", "obligations.bienes_extranjero_above_threshold"),
        (
            "monedas_virtuales_extranjero_above_threshold",
            "obligations.monedas_virtuales_extranjero_above_threshold",
        ),
        ("enrollment.large_company", "censo.large_company"),
        ("enrollment.public_administration_budget_gt_6000000", "censo.public_administration_budget_gt_6000000"),
    ):
        if bare in canonical and canonical_key not in canonical:
            padded[canonical_key] = canonical[bare]

    return canonical, padded


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


def _parse_optional_bool(raw: str | None) -> bool | None:
    """Three-state boolean: undeclared (``None``), affirmative, or negative.

    Distinguishes an absent fact from a positively-declared ``False``.
    The new-entity first-two-profit-periods state is opt-in: a profile
    that has not declared the fact must remain outside the LIS Art. 29
    15 percent override, which requires telling ``None`` apart from
    ``False`` at the typed boundary.
    """
    if raw is None or raw == "":
        return None
    token = raw.strip().lower()
    if token in {"true", "1", "yes", "y", "si", "sí"}:
        return True
    if token in {"false", "0", "no", "n"}:
        return False
    return None


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


def _parse_cross_period_group_member_rosters(canonical: dict[str, str]) -> tuple[CrossPeriodGroupMemberRoster, ...]:
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
                source_modelo=source_modelo,
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
            return Modelo.M322.value, int(parts[0]), parts[1]
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
    if raw == "" or raw is None:
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
    if raw == "" or raw is None:
        return None
    if isinstance(raw, IrpfSpecialRegime):
        return raw
    return IrpfSpecialRegime(raw)
