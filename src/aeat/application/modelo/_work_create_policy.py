"""Application policies for creating modelo work units."""

from __future__ import annotations

from dataclasses import dataclass

from ...core import Modelo
from ...core.config import load_settings

STUB_MODELO_LOCALE_KEYS: dict[str, str] = {
    Modelo.M151.value: "cli.app.modelo.work.create_stub_modelo_151_refused",
    Modelo.M210.value: "cli.app.modelo.work.create_stub_modelo_210_refused",
    "600": "cli.app.modelo.work.create_stub_modelo_600_refused",
    "620": "cli.app.modelo.work.create_stub_modelo_620_refused",
    "650": "cli.app.modelo.work.create_stub_modelo_650_refused",
    "660": "cli.app.modelo.work.create_stub_modelo_660_refused",
    Modelo.M714.value: "cli.app.modelo.work.create_stub_modelo_714_refused",
    Modelo.M721.value: "cli.app.modelo.work.create_stub_modelo_refused",
}

STUB_ONLY_MODELOS: frozenset[str] = frozenset(STUB_MODELO_LOCALE_KEYS)


@dataclass(frozen=True, slots=True)
class ModeloWorkCreateApplicabilityRefusal:
    """Application refusal for a modelo the active profile should not file."""

    modelo: str
    reason: str


def modelo_work_create_refusal_locale_key(modelo: str) -> str | None:
    """Return the locale key for a refused stub-modelo create request."""
    modelo_code = modelo.strip()
    if modelo_code not in STUB_ONLY_MODELOS:
        return None
    if modelo_code == Modelo.M210 and load_settings().aeat_m210_engine_live:
        return None
    return STUB_MODELO_LOCALE_KEYS[modelo_code]


def modelo_work_create_applicability_refusal(
    modelo: str,
    *,
    allow_not_applicable: bool,
) -> ModeloWorkCreateApplicabilityRefusal | None:
    """Return a :class:`ModeloWorkCreateApplicabilityRefusal` for the active profile, or ``None`` when applicable."""
    if allow_not_applicable:
        return None

    from ...application.user_profile import projection_for_taxpayer
    from ...application.workflow import workflow_state_repository
    from ...domain.calculations.registry.applicability import (
        ApplicabilityVerdict,
        derive_modelo_applicability,
    )

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    profile = projection_for_taxpayer(record or {}, tax_id_default="00000000T")
    applicability = derive_modelo_applicability(profile, modelo.strip())
    blocking = {
        ApplicabilityVerdict.NOT_APPLICABLE,
        ApplicabilityVerdict.ATTRIBUTION_PASS_THROUGH,
    }
    if applicability.verdict not in blocking:
        return None
    return ModeloWorkCreateApplicabilityRefusal(modelo=modelo.strip(), reason=applicability.reason)


def guard_active_profile_foral_ccaa() -> None:
    """Raise the canonical foral-regime refusal for the active profile, if present."""
    from ...application.user_profile import fact_value
    from ...application.workflow import workflow_state_repository
    from ...domain.contribuyente import parse_tax_region

    state = workflow_state_repository().load()
    record = state.active_profile_record()
    raw_ccaa = fact_value(record, "tax_residence.ccaa")
    if raw_ccaa:
        parse_tax_region(raw_ccaa)


__all__ = [
    "STUB_MODELO_LOCALE_KEYS",
    "STUB_ONLY_MODELOS",
    "ModeloWorkCreateApplicabilityRefusal",
    "guard_active_profile_foral_ccaa",
    "modelo_work_create_applicability_refusal",
    "modelo_work_create_refusal_locale_key",
]
