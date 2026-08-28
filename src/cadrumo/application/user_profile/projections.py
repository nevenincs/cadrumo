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

from collections.abc import Mapping, Sequence
from datetime import date
from typing import TypeGuard

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG
from ...domain.deadlines import IVARegime, TaxpayerProfile, taxpayer_profile_from_mapping
from ...domain.user_profile.loader import load_user_profile_schema
from ...domain.user_profile.schema import ProfileSchemaDefinition
from ...domain.user_profile.values import (
    UserProfileFact,
    UserProfileFactValue,
    UserProfileRecord,
    UserProfileSnapshot,
)

_WINDOWLESS_SENTINEL = date.min
"""Sort position for a fact carrying no ``valid_from``.

An absent window means "no stated start", which orders before every
stated one, so a windowed fact supersedes an unwindowed one at the same
path. Matches the sentinel the record resolvers already sort on.
"""

_default_schema_cache: ProfileSchemaDefinition | None = None


def _default_schema() -> ProfileSchemaDefinition:
    global _default_schema_cache
    if _default_schema_cache is None:
        _default_schema_cache = load_user_profile_schema()
    return _default_schema_cache


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


def _in_window_order(facts: Sequence[UserProfileFact]) -> tuple[UserProfileFact, ...]:
    """Order facts so the chronologically last effective window wins.

    The record model permits several live facts at one path with
    different effective-dating windows, and the schema declares
    ``effective_dated`` on most of its sections and fields, so which of
    them is effective is a real question rather than a hypothetical one.
    Both projections resolve it by taking the LAST fact per path, so
    ordering by window here is what makes that answer the in-force one.

    The rule is the one the record resolvers already use - sort on
    ``valid_from``, absent windows first, and let the last win.

    ``valid_to`` is deliberately NOT consulted, and the reason is that
    honouring it needs an ``as_of`` date the caller supplies, not the
    clock. Expiry is only meaningful relative to some instant, and the
    only instant available here is "now"; a projection that dropped
    expired facts against ``date.today()`` would return different values
    for the same record on different days. These projections feed filing
    inputs and completeness checks, where the effective instant is the
    PERIOD being filed rather than the day the command runs - so an
    implicit-today rule would resolve a 2024 filing against 2026's
    calendar, and would do it silently. Dropping a path also reads
    downstream as unset rather than expired, so a required field whose
    window closed would surface as missing rather than as ended.

    Honouring expiry therefore means threading an explicit ``as_of``
    through every caller, each deciding the instant its own read is
    effective at. That is a different change; until it is made,
    supersession is expressed by recording a later ``valid_from`` at the
    same path, which this ordering already resolves. A ``valid_to`` that
    nothing supersedes is reported to the operator by the profile
    validation surface rather than silently ignored.

    The sort is stable, so a record whose facts carry no window at all
    keeps its declaration order exactly. Nothing in production sets a
    window today, which is what makes this behaviour-neutral now and
    correct when something starts.

    Args:
        facts: The record's facts, in declaration order.

    Returns:
        The same facts, ordered so a later window resolves last.
    """
    return tuple(sorted(facts, key=lambda fact: fact.valid_from or _WINDOWLESS_SENTINEL))


in_window_order = _in_window_order


def record_to_path_values(record: UserProfileRecord | UserProfileSnapshot | None) -> dict[str, str]:
    """Project a :class:`UserProfileRecord` (or snapshot) into a schema-path-keyed string mapping.

    Unlike :func:`record_to_values` (which projects via the schema's
    ``model_selectors`` aliases), this keeps the canonical schema
    path as the key. The mapping is what the wizard catalogue,
    :func:`validate_profile_values`, and CLI status surfaces consume.
    """
    if record is None:
        return {}
    return {
        fact.path: _render_fact_value(fact.value) for fact in _in_window_order(record.facts) if fact.value is not None
    }


def fact_value(record: UserProfileRecord | UserProfileSnapshot | None, path: str) -> str | None:
    """Read one effective current fact through the canonical projection."""
    return record_to_path_values(record).get(path)


class EffectiveFact(BaseModel):
    """The fact at one schema path whose effective window starts latest.

    ``value`` is the rendered canonical token, or ``None`` when the path was
    explicitly CLEARED. A cleared path is not the same as an unset one: it
    carries an operator decision — *I do not want this on my profile* — and a
    caller that cannot see the difference will treat the deletion as absence
    and quietly undo it.

    Several facts may be live at one path with different effective-dating
    windows, and this resolves them the way the record resolvers do: the
    latest ``valid_from`` wins, with an absent window ordering first. That
    is deliberately the same rule rather than a better one, so no two
    readers can disagree about which fact is effective.

    ``valid_to`` is not consulted, so a fact whose window has closed still
    resolves. That is the shared rule rather than a limit of this
    projection, and :func:`_in_window_order` carries the reason: expiry
    needs an ``as_of`` the caller supplies, and resolving it against the
    clock would make one record project differently on different days.
    """

    model_config = STRICT_FROZEN_CONFIG

    value: str | None = None
    source: str


def record_to_effective_facts(
    record: UserProfileRecord | UserProfileSnapshot | None,
) -> dict[str, EffectiveFact]:
    """Project a :class:`UserProfileRecord` into the effective fact at each schema path.

    Unlike :func:`record_to_path_values`, which resolves the last fact whose
    value is not ``None`` (correct for callers that want an effective VALUE,
    since a cleared path has none), this resolves the last fact per path
    REGARDLESS of value, so an explicit clear stays visible as
    ``value=None``.

    Returning one record per path rather than parallel value and source
    mappings is deliberate: two mappings can disagree about which fact is
    effective, and a value adjudicated against a different fact's provenance
    is a subtler failure than the one such a split is usually introduced to
    fix. Here they cannot disagree, because there is only one answer.
    """
    if record is None:
        return {}
    effective: dict[str, EffectiveFact] = {}
    for fact in _in_window_order(record.facts):
        effective[fact.path] = EffectiveFact(
            value=None if fact.value is None else _render_fact_value(fact.value),
            source=fact.source,
        )
    return effective


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
    # The deadline-domain projection reads core registration slots populated by
    # the application wizard layer. Import the concrete modules here so service
    # callers outside the CLI startup path get the same canonical projection.
    from ..wizard.compiler import ensure_profile_keys_registered

    ensure_profile_keys_registered()

    if isinstance(facts, UserProfileRecord | UserProfileSnapshot):
        mapping = _merged_taxpayer_values(facts, schema=schema)
    else:
        mapping = {str(key): str(value) for key, value in facts.items() if value is not None}
    return taxpayer_profile_from_mapping(mapping, tax_id_default=tax_id_default, iva_regime_default=iva_regime_default)


def _merged_taxpayer_values(
    record: UserProfileRecord | UserProfileSnapshot,
    *,
    schema: ProfileSchemaDefinition | None = None,
) -> dict[str, str]:
    """Merge the path-keyed and selector-keyed projections for the taxpayer coercion.

    :func:`~cadrumo.domain.deadlines.taxpayer_profile_from_mapping` reads
    most fields at their canonical schema path (which is also the key space
    the wizard's ``project_answers`` resolves questions against), but a
    field family is read at its declared ``model_selectors`` alias instead
    (``address.cadastral_reference``, ``address.is_habitual_vivienda``, …).
    Feeding only one key space silently blanks the other family, so the
    taxpayer projection carries both: the path projection first, with
    selector aliases layered alongside. The two key spaces are disjoint for
    aliased fields and identical for unaliased ones, so no key ever
    resolves to conflicting values.
    """
    mapping = record_to_path_values(record)
    if isinstance(record, UserProfileRecord):
        selector_values = record_to_values(record, schema=schema)
    else:
        selector_values = snapshot_to_values(record, schema=schema)
    for key, value in selector_values.items():
        mapping.setdefault(key, value)
    return mapping


__all__ = [
    "fact_value",
    "facts_to_values",
    "profile_fact_index",
    "projection_for_taxpayer",
    "record_to_path_values",
    "record_to_values",
    "snapshot_to_values",
]


def _is_user_profile_record(record: object) -> TypeGuard[UserProfileRecord]:
    """Prove that an optional caller override is the canonical live record."""
    return isinstance(record, UserProfileRecord)


def profile_fact_index(record: object, schema: ProfileSchemaDefinition) -> dict[str, UserProfileFactValue]:
    """Build a selector -> typed-value index covering both selector forms.

    A profile binding's selector resolves either as the canonical
    ``section.field`` fact path (``profile_key`` form) or as a schema
    ``model_selector`` alias (``profile_model`` + ``field`` form). The
    index exposes each non-null fact under its canonical path AND under
    every ``model_selector`` the schema declares for it, so both
    selector forms find the value.

    Values are preserved as their original :data:`UserProfileFactValue` type
    (``bool``, ``Decimal``, ``date``, ``str``, …) so that downstream
    channel routing can branch on the concrete Python type rather than
    re-parsing a ``str(value)`` rendering.
    """
    selector_index: dict[str, tuple[str, ...]] = {}
    for section in schema.sections:
        for field in section.fields:
            selector_index[f"{section.key}.{field.key}"] = tuple(field.model_selectors)

    if not _is_user_profile_record(record):
        return {}

    index: dict[str, UserProfileFactValue] = {}
    for fact in record.facts:
        if fact.value is None:
            continue
        index[fact.path] = fact.value
        for selector in selector_index.get(fact.path, ()):
            index[selector] = fact.value
    return index
