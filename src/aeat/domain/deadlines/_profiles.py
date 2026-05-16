"""Profile construction helpers for deadline and schedule consumers.

The helper projects a ``ProfileRecord.values``-shaped mapping into an
:class:`AutonomoProfile` by deferring to the wizard descriptor's
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
from ._models import AutonomoProfile, FilingEnrollment, FilingIVAProfile, IVARegime


def autonomo_profile_from_mapping(
    values: Mapping[str, object],
    *,
    tax_id_default: str,
    iva_regime_default: IVARegime = IVARegime.GENERAL,
) -> AutonomoProfile:
    """Build an :class:`AutonomoProfile` from a profile-values mapping.

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

    typed = project_answers(SETUP_FLOW, padded)
    if not isinstance(typed, SetupAnswers):
        raise ProfileError("setup flow projection did not yield a SetupAnswers instance")

    tax_id = canonical.get("identity.tax_id") or canonical.get("tax.id") or tax_id_default
    iva_regime = _resolve_iva_regime(canonical.get("iva.regime"), iva_regime_default)

    return AutonomoProfile(
        tax_id=tax_id,
        iva_regime=iva_regime,
        has_employees=typed.has_employees,
        pays_professionals_with_retencion=typed.pays_professionals_with_retencion,
        professional_income_withholding_ge_70pct=typed.professional_income_withholding_ge_70pct,
        pays_rent_with_retencion=typed.pays_rent_with_retencion,
        pays_capital_income_with_retencion=typed.pays_capital_income_with_retencion,
        uses_objective_estimation_irpf=typed.uses_objective_estimation_irpf,
        does_intracomunitario=typed.does_intracomunitario,
        third_party_transactions_above_347_threshold=typed.third_party_transactions_above_347_threshold,
        bienes_extranjero_above_threshold=typed.bienes_extranjero_above_threshold,
        iva=FilingIVAProfile(
            roi_enrolled=typed.iva_roi_enrolled,
            oss_enrolled=typed.iva_oss_enrolled,
            intracommunity_operations_exceed_50000_eur=typed.iva_intracommunity_operations_exceed_50000_eur,
        ),
        enrollment=FilingEnrollment(
            large_company=typed.enrollment_large_company,
            public_administration_budget_gt_6000000=typed.enrollment_public_administration_budget_gt_6000000,
        ),
        fiscal_address_cadastral_reference=canonical.get("address.cadastral_reference", ""),
        fiscal_address_is_habitual_vivienda=_parse_bool(canonical.get("address.is_habitual_vivienda")),
        activity_start_date=_parse_date(canonical.get("census.activity_start_date")),
        activity_end_date=_parse_date(canonical.get("census.activity_end_date")),
        establecimiento_type=canonical.get("census.establecimiento_type", ""),
        elected_withholding_pct=canonical.get("census.elected_withholding_pct", ""),
        vivienda_office_total_m2=_parse_decimal(canonical.get("vivienda_office.total_m2")),
        vivienda_office_office_m2=_parse_decimal(canonical.get("vivienda_office.office_m2")),
        iae_epigraph=canonical.get("activities.iae_epigraph", ""),
        notes=typed.notes,
    )


def _parse_bool(raw: str | None) -> bool:
    if not raw:
        return False
    return raw.strip().lower() in {"true", "1", "yes", "y", "si", "sí"}


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


def _resolve_iva_regime(raw: str | None, default: IVARegime) -> IVARegime:
    if raw is None or raw == "":
        return default
    canonical = raw.strip().upper().replace("-", "_")
    return IVARegime(canonical)
