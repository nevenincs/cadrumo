"""Filing-grade profile identity baseline checks."""

from __future__ import annotations

from collections.abc import Mapping

from ...core.setup_answers import SETUP_ANSWER_FIELDS
from .completeness import conditional_profile_missing_required

#: Profile path to the long-option spelling an operator actually types, derived
#: from the one field registry rather than restated. The namespace is not
#: uniformly dropped -- ``taxpayer_type.country_of_fiscal_residence`` is
#: ``--country-of-fiscal-residence`` while ``iva.regime`` is ``--iva-regime`` --
#: so no textual rule reproduces it and the registry is the only authority.
_PROFILE_PATH_FLAGS: dict[str, str] = {
    spec.path: field.replace("_", "-") for field, spec in SETUP_ANSWER_FIELDS.items()
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
        missing.append(_profile_path_flag(path))
    return tuple(dict.fromkeys(missing))


def _profile_path_flag(path: str) -> str:
    """Return the long-option spelling for a profile path.

    The refusal that carries this names flags the operator retypes verbatim, so
    a dotted path must never reach it: this CLI's operator is an autonomous
    agent that follows the instruction literally and cannot recover from a flag
    that does not parse. An unregistered path falls back to a dash form, which
    may be the wrong flag but is at least a well-formed one.
    """
    registered = _PROFILE_PATH_FLAGS.get(path)
    if registered is not None:
        return registered
    return path.replace(".", "-").replace("_", "-")


def _profile_token(values: Mapping[str, object], path: str) -> str:
    return str(values.get(path) or "").strip()


__all__ = ["missing_filing_baseline_flags"]
