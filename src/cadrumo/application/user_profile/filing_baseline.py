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
    return _dedupe_with_conditional_profile_flags(
        values,
        list(_identity_baseline_flags(values)),
        profile_path_flags=profile_path_flags,
    )


def _identity_baseline_flags(values: Mapping[str, object]) -> tuple[str, ...]:
    """Return the identity flags this entity type owes, ignoring conditionals."""
    missing: list[str] = []
    entity_type = _profile_token(values, "taxpayer_type.entity_type")
    if not entity_type:
        missing.append("entity-type")
    if entity_type == entity_type_legal_entity_token().value:
        if not _profile_token(values, "taxpayer_type.legal_entity_form"):
            missing.append("legal-entity-form")
        if not _profile_token(values, "identity.legal_name"):
            missing.append("legal-name")
        return tuple(missing)
    if entity_type == entity_type_attribution_entity_token().value:
        if not _profile_token(values, "identity.name"):
            missing.append("name")
        return tuple(missing)
    if not _profile_token(values, "identity.name"):
        missing.append("name")
    if not _profile_token(values, "identity.surnames"):
        missing.append("surnames")
    return tuple(missing)


def _dedupe_with_conditional_profile_flags(
    values: Mapping[str, object],
    missing: list[str],
    *,
    profile_path_flags: Mapping[str, str],
) -> tuple[str, ...]:
    for path in conditional_profile_missing_required(values):
        missing.append(_profile_path_flag(path, profile_path_flags=profile_path_flags))
    return tuple(dict.fromkeys(missing))


def missing_filing_baseline_flag_groups(
    values: Mapping[str, object],
    *,
    profile_path_flags: Mapping[str, str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return the missing flags split into identity and conditional groups.

    Both groups block the same write, but they are different obligations and
    reporting them under one message misdescribed whichever group the operator
    actually hit: a profile lacking only the Modelo 303 IVA block was told its
    "identity data" was incomplete while its name and NIF were plainly set.

    Identity takes precedence where the two overlap. The conditional resolver
    also demands the legal-entity fields once the entity type is a legal
    entity, so subtracting the conditional set instead would empty the identity
    group and report a missing legal name as a Modelo 303 requirement.
    """
    identity = tuple(dict.fromkeys(_identity_baseline_flags(values)))
    identity_set = set(identity)
    conditional = tuple(
        flag
        for flag in dict.fromkeys(
            _profile_path_flag(path, profile_path_flags=profile_path_flags)
            for path in conditional_profile_missing_required(values)
        )
        if flag not in identity_set
    )
    return identity, conditional


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


__all__ = ["missing_filing_baseline_flag_groups", "missing_filing_baseline_flags"]
