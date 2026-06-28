"""Filing-grade profile identity baseline checks."""

from __future__ import annotations

from collections.abc import Mapping


def missing_filing_baseline_flags(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return profile-create/edit/import flags needed for filing identity."""
    missing: list[str] = []
    entity_type = _profile_token(values, "taxpayer_type.entity_type")
    if not entity_type:
        missing.append("entity-type")
    if entity_type == "legal_entity":
        if not _profile_token(values, "identity.legal_name"):
            missing.append("legal-name")
        return tuple(dict.fromkeys(missing))
    if entity_type == "attribution_entity":
        if not _profile_token(values, "identity.name"):
            missing.append("name")
        return tuple(dict.fromkeys(missing))
    if not entity_type or not _profile_token(values, "identity.name"):
        missing.append("name")
    if not entity_type or not _profile_token(values, "identity.surnames"):
        missing.append("surnames")
    return tuple(dict.fromkeys(missing))


def _profile_token(values: Mapping[str, object], path: str) -> str:
    return str(values.get(path) or "").strip()


__all__ = ["missing_filing_baseline_flags"]
