"""Profile construction helpers for deadline and schedule consumers."""

from __future__ import annotations

from collections.abc import Mapping

from ._models import AutonomoProfile, FilingEnrollment, FilingIVAProfile, IVARegime

_TRUE_TOKENS = frozenset({"1", "true", "yes", "y", "on", "si", "sí"})
_FALSE_TOKENS = frozenset({"0", "false", "no", "n", "off"})


def autonomo_profile_from_mapping(
    values: Mapping[str, object],
    *,
    tax_id_default: str,
    iva_regime_default: IVARegime = IVARegime.GENERAL,
) -> AutonomoProfile:
    """Build an :class:`AutonomoProfile` from persisted profile field values."""

    tax_id = _text_value(values, "tax.id") or tax_id_default
    iva_regime = _iva_regime_value(values, "iva.regime", default=iva_regime_default)
    enrollment = FilingEnrollment(
        large_company=_bool_value(values, "enrollment.large_company"),
        public_administration_budget_gt_6000000=_bool_value(
            values,
            "enrollment.public_administration_budget_gt_6000000",
        ),
    )
    iva = FilingIVAProfile(
        roi_enrolled=_bool_value(values, "iva.roi_enrolled"),
        oss_enrolled=_bool_value(values, "iva.oss_enrolled"),
        intracommunity_operations_exceed_50000_eur=_bool_value(
            values,
            "iva.intracommunity_operations_exceed_50000_eur",
        ),
    )
    return AutonomoProfile(
        tax_id=tax_id,
        iva_regime=iva_regime,
        has_employees=_bool_value(values, "has_employees", "has.employees"),
        pays_professionals_with_retencion=_bool_value(
            values,
            "pays_professionals_with_retencion",
            "pays.professionals.with.retencion",
        ),
        professional_income_withholding_ge_70pct=_bool_value(
            values,
            "professional_income_withholding_ge_70pct",
            "professional.income.withholding.ge.70pct",
        ),
        pays_rent_with_retencion=_bool_value(values, "pays_rent_with_retencion", "pays.rent.with.retencion"),
        pays_capital_income_with_retencion=_bool_value(
            values,
            "pays_capital_income_with_retencion",
            "pays.capital.income.with.retencion",
        ),
        uses_objective_estimation_irpf=_bool_value(
            values,
            "uses_objective_estimation_irpf",
            "uses.objective.estimation.irpf",
        ),
        does_intracomunitario=_bool_value(values, "does_intracomunitario", "does.intracomunitario"),
        third_party_transactions_above_347_threshold=_bool_value(
            values,
            "third_party_transactions_above_347_threshold",
            "third.party.transactions.above.347.threshold",
        ),
        bienes_extranjero_above_threshold=_bool_value(
            values,
            "bienes_extranjero_above_threshold",
            "bienes.extranjero.above.threshold",
        ),
        iva=iva,
        enrollment=enrollment,
        notes=_text_value(values, "notes"),
    )


def _text_value(values: Mapping[str, object], *keys: str) -> str:
    for key in keys:
        raw = values.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return ""


def _bool_value(values: Mapping[str, object], *keys: str) -> bool:
    for key in keys:
        raw = values.get(key)
        if raw is None:
            continue
        if isinstance(raw, bool):
            return raw
        token = str(raw).strip().lower()
        if token in _TRUE_TOKENS:
            return True
        if token in _FALSE_TOKENS:
            return False
        raise ValueError(f"profile field {key!r} must be a boolean token")
    return False


def _iva_regime_value(
    values: Mapping[str, object],
    key: str,
    *,
    default: IVARegime,
) -> IVARegime:
    raw = values.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    return IVARegime(str(raw).strip())
