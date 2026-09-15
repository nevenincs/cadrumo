"""Filing-grade profile identity baseline checks."""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.contribuyente.entity_type import (
    entity_type_attribution_entity_token,
    entity_type_legal_entity_token,
)
from .completeness import conditional_profile_missing_required


def missing_filing_baseline_flags(
    values: Mapping[str, object],
    *,
    profile_path_flags: Mapping[str, str],
) -> tuple[str, ...]:
    """Return profile-create/edit/import flags needed for filing identity."""
    missing: list[str] = []
    entity_type = _profile_token(values, "taxpayer_type.entity_type")
    if not entity_type:
        missing.append("entity-type")
    if entity_type == entity_type_legal_entity_token().value:
        if not _profile_token(values, "taxpayer_type.legal_entity_form"):
            missing.append("legal-entity-form")
        if not _profile_token(values, "identity.legal_name"):
            missing.append("legal-name")
        return _dedupe_with_conditional_profile_flags(
            values,
            missing,
            profile_path_flags=profile_path_flags,
        )
    if entity_type == entity_type_attribution_entity_token().value:
        if not _profile_token(values, "identity.name"):
            missing.append("name")
        return _dedupe_with_conditional_profile_flags(
            values,
            missing,
            profile_path_flags=profile_path_flags,
        )
    if not _profile_token(values, "identity.name"):
        missing.append("name")
    if not _profile_token(values, "identity.surnames"):
        missing.append("surnames")
    return _dedupe_with_conditional_profile_flags(values, missing, profile_path_flags=profile_path_flags)


def _dedupe_with_conditional_profile_flags(
    values: Mapping[str, object],
    missing: list[str],
    *,
    profile_path_flags: Mapping[str, str],
) -> tuple[str, ...]:
    for path in conditional_profile_missing_required(values):
        missing.append(_profile_path_flag(path, profile_path_flags=profile_path_flags))
    return tuple(dict.fromkeys(missing))


def _profile_path_flag(path: str, *, profile_path_flags: Mapping[str, str]) -> str:
    """Return the long-option spelling for a profile path.

    The refusal that carries this names flags the operator retypes verbatim, so
    a dotted path must never reach it: this CLI's operator is an autonomous
    agent that follows the instruction literally and cannot recover from a flag
    that does not parse. An unregistered path falls back to a dash form, which
    may be the wrong flag but is at least a well-formed one.
    """
    registered = profile_path_flags.get(path)
    if registered is not None:
        return registered
    return path.replace(".", "-").replace("_", "-")


def _profile_token(values: Mapping[str, object], path: str) -> str:
    return str(values.get(path) or "").strip()


__all__ = ["missing_filing_baseline_flags"]
