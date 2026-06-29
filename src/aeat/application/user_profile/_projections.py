"""Canonical projections from :class:`UserProfileRecord` to consumer shapes.

The schema-driven user-profile backend is the canonical authority. Every
existing consumer (deadlines, filing runtime, overview calendar,
wizard, workflow adapters) reads through one of these projection
helpers rather than keeping its own profile fact decoding branch.

The projections compose against a *fact map* (``path -> str(value)``)
derived from the record. Deadline-engine projection uses the domain
coercer so field-level coercion logic stays in one place.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.deadlines import TaxpayerProfile, taxpayer_profile_from_mapping
from ...domain.deadlines._models import IVARegime
from ...domain.user_profile import (
    ProfileSchemaDefinition,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    load_user_profile_schema,
)

_DEFAULT_SCHEMA: ProfileSchemaDefinition | None = None


def _default_schema() -> ProfileSchemaDefinition:
    global _DEFAULT_SCHEMA
    if _DEFAULT_SCHEMA is None:
        _DEFAULT_SCHEMA = load_user_profile_schema()
    return _DEFAULT_SCHEMA


def _render_fact_value(value: object) -> str:
    """Render a profile-fact value as its canonical-token string.

    A :class:`UserProfileFact` value is a typed union (``str | bool |
    int | Decimal | date``). Downstream coercers — the wizard
    descriptor's ``project_answers`` in particular — accept only the
    lowercase canonical boolean tokens ``true`` / ``false``. Plain
    ``str(True)`` yields ``"True"``, which ``project_answers`` rejects
    as falsey, so a boolean fact must be lowercased here before the
    projection's flat-string contract is built.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _selector_index(schema: ProfileSchemaDefinition) -> dict[str, tuple[str, ...]]:
    """Map ``section.field`` paths to their declared ``model_selectors`` tuple."""
    index: dict[str, tuple[str, ...]] = {}
    for section in schema.sections:
        for field in section.fields:
            index[f"{section.key}.{field.key}"] = tuple(field.model_selectors)
    return index


def facts_to_values(
    facts: tuple[UserProfileFact, ...],
    *,
    schema: ProfileSchemaDefinition | None = None,
) -> dict[str, str]:
    """Project a tuple of profile facts into the flat ``selector -> str(value)`` map.

    The flat shape is the selector-keyed mapping consumed by
    :func:`taxpayer_profile_from_mapping` and similar coercers. Each
    schema field's ``model_selectors`` are honored: a fact at
    ``identity.tax_id`` whose schema declares
    ``model_selectors = ["tax.id"]`` is emitted under the key
    ``tax.id``. Facts whose path is not in the schema fall through
    untranslated.
    """
    selector_index = _selector_index(schema or _default_schema())
    values: dict[str, str] = {}
    for fact in facts:
        if fact.value is None:
            continue
        selectors = selector_index.get(fact.path, (fact.path,))
        rendered = _render_fact_value(fact.value)
        for selector in selectors or (fact.path,):
            values[selector] = rendered
    return values


def record_to_values(
    record: UserProfileRecord,
    *,
    schema: ProfileSchemaDefinition | None = None,
) -> dict[str, str]:
    """Project a live profile record into the selector-keyed flat values mapping.

    Args:
        record: The :class:`UserProfileRecord` to project.
        schema: Optional profile schema definition override.
    """
    return facts_to_values(record.facts, schema=schema)


def snapshot_to_values(
    snapshot: UserProfileSnapshot,
    *,
    schema: ProfileSchemaDefinition | None = None,
) -> dict[str, str]:
    """Project an immutable filing snapshot into the selector-keyed flat values mapping."""
    return facts_to_values(snapshot.facts, schema=schema)


def record_to_path_values(record: UserProfileRecord | UserProfileSnapshot | None) -> dict[str, str]:
    """Project a :class:`UserProfileRecord` (or snapshot) into a schema-path-keyed string mapping.

    Unlike :func:`record_to_values` (which projects via the schema's
    ``model_selectors`` aliases), this keeps the canonical schema
    path as the key. The mapping is what the wizard catalogue,
    :func:`validate_profile_values`, and CLI status surfaces consume.
    """
    if record is None:
        return {}
    return {fact.path: _render_fact_value(fact.value) for fact in record.facts if fact.value is not None}


def projection_for_taxpayer(
    facts: Mapping[str, object] | UserProfileRecord | UserProfileSnapshot,
    *,
    tax_id_default: str = "00000000T",
    iva_regime_default: IVARegime = IVARegime.GENERAL,
    schema: ProfileSchemaDefinition | None = None,
) -> TaxpayerProfile:
    """Return the deadline-engine :class:`TaxpayerProfile` for the supplied profile facts.

    Args:
        facts: Either a :class:`UserProfileRecord`, an immutable
            :class:`UserProfileSnapshot`, or a pre-projected flat mapping.
        tax_id_default: Fallback NIF when the profile carries none.
        iva_regime_default: Fallback IVA regime when the profile carries none.
        schema: Optional profile schema definition override.

    The single coercion path goes through :func:`taxpayer_profile_from_mapping`
    so canonical-token semantics stay in lockstep with the wizard descriptor.
    """
    if isinstance(facts, UserProfileRecord | UserProfileSnapshot):
        mapping = record_to_path_values(facts)
    else:
        mapping = {str(key): str(value) for key, value in facts.items() if value is not None}
    return taxpayer_profile_from_mapping(mapping, tax_id_default=tax_id_default, iva_regime_default=iva_regime_default)


__all__ = [
    "facts_to_values",
    "projection_for_taxpayer",
    "record_to_path_values",
    "record_to_values",
    "snapshot_to_values",
]
