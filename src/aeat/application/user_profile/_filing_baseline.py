"""Filing-grade profile identity baseline checks."""

from __future__ import annotations

from collections.abc import Mapping

from ._completeness import (
    COUNTRY_OF_FISCAL_RESIDENCE_PATH,
    REPRESENTANTE_FISCAL_NIF_PATH,
    REPRESENTANTE_FISCAL_NOMBRE_PATH,
    conditional_profile_missing_required,
)

_PROFILE_PATH_FLAGS: dict[str, str] = {
    COUNTRY_OF_FISCAL_RESIDENCE_PATH: "country-of-fiscal-residence",
    REPRESENTANTE_FISCAL_NIF_PATH: "representante-fiscal-nif",
    REPRESENTANTE_FISCAL_NOMBRE_PATH: "representante-fiscal-nombre",
}


def missing_filing_baseline_flags(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return profile-create/edit/import flags needed for filing identity."""
    missing: list[str] = []
    entity_type = _profile_token(values, "taxpayer_type.entity_type")
    if not entity_type:
        missing.append("entity-type")
    if entity_type == "legal_entity":
        if not _profile_token(values, "taxpayer_type.legal_entity_form"):
            missing.append("legal-entity-form")
        if not _profile_token(values, "identity.legal_name"):
            missing.append("legal-name")
        return _dedupe_with_conditional_profile_flags(values, missing)
    if entity_type == "attribution_entity":
        if not _profile_token(values, "identity.name"):
            missing.append("name")
        return _dedupe_with_conditional_profile_flags(values, missing)
    if not _profile_token(values, "identity.name"):
        missing.append("name")
    if not _profile_token(values, "identity.surnames"):
        missing.append("surnames")
    return _dedupe_with_conditional_profile_flags(values, missing)


def _dedupe_with_conditional_profile_flags(values: Mapping[str, object], missing: list[str]) -> tuple[str, ...]:
    for path in conditional_profile_missing_required(values):
        missing.append(_PROFILE_PATH_FLAGS.get(path, path))
    return tuple(dict.fromkeys(missing))


def _profile_token(values: Mapping[str, object], path: str) -> str:
    return str(values.get(path) or "").strip()


__all__ = ["missing_filing_baseline_flags"]
