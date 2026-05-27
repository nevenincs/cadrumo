"""Profile construction helpers for deadline and schedule consumers.

The helper projects a ``ProfileRecord.values``-shaped mapping into an
:class:`TaxpayerProfile` by deferring to the wizard descriptor's
typed projection (``project_answers``). The wizard catalogue is the
single source of truth for the canonical-token shape of every field;
this helper composes the typed answer over the deadline-engine's
record.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal, InvalidOperation

from ._errors import ProfileError
from ._models import (
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
    :func:`project_answers` so canonical-token semantics for every
    boolean / select / text field stay in lockstep with the wizard's
    on-prompt validation. Missing identity fields fall back to
    ``tax_id_default`` / ``iva_regime_default``.
    """

    # Coerce mixed-typed mappings to canonical-token strings before the
    # descriptor's projection runs.
    canonical: dict[str, str] = {key: _stringify(raw) for key, raw in values.items()}
    # The wizard's SELECT validator only accepts the IVARegime
    # canonical uppercase token, so the mapping is normalised here
    # against the enum's value form before projection.
    if canonical.get("iva.regime"):
        canonical["iva.regime"] = canonical["iva.regime"].strip().upper().replace("-", "_")

    from ...application.wizard._catalogue import SETUP_FLOW
    from ...application.wizard._persistence import project_answers
    from ...application.wizard._setup_answers import SetupAnswers

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
        ("pays_rent_with_retencion", "withholding.pays_rent_with_retencion"),
        ("pays_capital_income_with_retencion", "withholding.pays_capital_income_with_retencion"),
        ("does_intracomunitario", "iva.does_intracomunitario"),
        ("bienes_extranjero_above_threshold", "obligations.bienes_extranjero_above_threshold"),
        ("enrollment.large_company", "census.large_company"),
        ("enrollment.public_administration_budget_gt_6000000", "census.public_administration_budget_gt_6000000"),
    ):
        if bare in canonical and canonical_key not in canonical:
            padded[canonical_key] = canonical[bare]

    typed = project_answers(SETUP_FLOW, padded)
    if not isinstance(typed, SetupAnswers):
        raise ProfileError("setup flow projection did not yield a SetupAnswers instance")

    tax_id = canonical.get("identity.tax_id") or canonical.get("tax.id") or tax_id_default
    iva_regime = _resolve_iva_regime(canonical.get("iva.regime"), iva_regime_default)

    entity_type = typed.entity_type or None
    legal_entity_form = typed.legal_entity_form or None
    income_categories = _resolve_income_categories(typed.irpf_income_categories)
    estimation_regime = typed.irpf_estimation_regime or None

    # The structured estimation_regime is authoritative over the legacy
    # uses_objective_estimation_irpf boolean. When a regime is declared,
    # let TaxpayerProfile's mode="before" validator derive the boolean
    # from it so the projection never raises a regime/boolean conflict;
    # when no regime is declared the boolean is forwarded as before.
    objective_fields: dict[str, object] = {}
    if estimation_regime is None:
        objective_fields["uses_objective_estimation_irpf"] = typed.uses_objective_estimation_irpf

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
        pays_rent_with_retencion=typed.pays_rent_with_retencion,
        pays_capital_income_with_retencion=typed.pays_capital_income_with_retencion,
        **objective_fields,
        does_intracomunitario=typed.does_intracomunitario,
        third_party_transactions_above_347_threshold=typed.third_party_transactions_above_347_threshold,
        bienes_extranjero_above_threshold=typed.bienes_extranjero_above_threshold,
        iva=ModeloIVAProfile(
            roi_enrolled=typed.iva_roi_enrolled,
            oss_enrolled=typed.iva_oss_enrolled,
            sii_enrolled=typed.iva_sii_enrolled,
            redeme_enrolled=typed.iva_redeme_enrolled,
            intracommunity_operations_exceed_50000_eur=typed.iva_intracommunity_operations_exceed_50000_eur,
        ),
        enrollment=ModeloEnrollment(
            large_company=typed.enrollment_large_company,
            public_administration_budget_gt_6000000=typed.enrollment_public_administration_budget_gt_6000000,
        ),
        fiscal_address_cadastral_reference=canonical.get("address.cadastral_reference", ""),
        fiscal_address_is_habitual_vivienda=_parse_bool(canonical.get("address.is_habitual_vivienda")),
        activity_start_date=_parse_date(canonical.get("census.activity_start_date")),
        activity_end_date=_parse_date(canonical.get("census.activity_end_date")),
        incn_prior_12_months=_parse_decimal(canonical.get("taxpayer_type.incn_prior_12_months")),
        new_entity_first_two_profit_periods=_parse_optional_bool(
            canonical.get("taxpayer_type.new_entity_first_two_profit_periods")
        ),
        establecimiento_type=canonical.get("census.establecimiento_type", ""),
        elected_withholding_pct=canonical.get("census.elected_withholding_pct", ""),
        vivienda_office_total_m2=_parse_decimal(canonical.get("vivienda_office.total_m2")),
        vivienda_office_office_m2=_parse_decimal(canonical.get("vivienda_office.office_m2")),
        iae_epigraph=canonical.get("activities.iae_epigraph", ""),
        notes=typed.notes,
        irpf_special_regime=_resolve_special_regime(
            # Prefer the typed wizard answer; fall back to the canonical
            # path-keyed value from record_to_path_values so the field is
            # reachable from persisted facts even before a wizard question is
            # added to the SETUP_FLOW.
            typed.irpf_special_regime or canonical.get("irpf.special_regime", "")
        ),
        special_regime_start_date=_parse_date(
            typed.irpf_special_regime_start_date or canonical.get("irpf.special_regime_start_date")
        ),
        fiscal_residency=_resolve_fiscal_residency(
            typed.fiscal_residency or canonical.get("taxpayer_type.fiscal_residency", "")
        ),
        country_of_fiscal_residence=_coerce_country_code(
            typed.country_of_fiscal_residence or canonical.get("taxpayer_type.country_of_fiscal_residence", "")
        ),
    )


def _parse_bool(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"true", "1", "yes", "y", "si", "sí"}


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
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ProfileError(f"invalid census date {raw!r}; expected ISO-8601") from exc


def _parse_decimal(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    try:
        return Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ProfileError(f"invalid census decimal {raw!r}") from exc


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
