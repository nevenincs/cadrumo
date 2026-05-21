"""Application-owned profile-sourced binding resolution.

A registry binding with ``source = "profile"`` carries a value the
operator already entered onto their user profile (tax-residence CCAA,
census status, declaration type, ...). Without an explicit resolution
step the calculation engine never sees those facts: the operator would
have to re-type, via ``--binding KEY=VALUE``, data the profile already
holds, and a formula that consumes an unsupplied profile binding fails
with ``binding ... has no supplied value``.

This module loads the bucket's :class:`UserProfileRecord`, walks every
``source = "profile"`` binding the registry revision declares, and
projects the matching profile fact into the correct engine channel.

Channel selection is the load-bearing decision. The registry runtime
resolves a binding leaf from one of two channels depending on *how a
formula consumes it*: a binding that is the enum-key argument of a
dispatch op (``lookup_bracket_by_ccaa`` /
``lookup_parameter_by_entity_type``) is read from the string-valued
``enum_binding_values`` channel; every other binding leaf is read from
the Decimal-valued ``binding_values`` channel. The channel is therefore
NOT determined by the binding's ``typed_enum`` annotation -- a binding
may carry ``typed_enum`` yet still be consumed as a Decimal operand.
:func:`enum_consumed_binding_ids` is the authoritative discriminator.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...domain.calculations.registry import (
    DataBindingDefinition,
    RegistrySnapshot,
    enum_consumed_binding_ids,
    expression_binding_refs,
)
from ...domain.modelos._errors import ModeloError
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    load_user_profile_schema,
    profile_binding_selectors,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class ProfileBindingResolutionError(ModeloError):
    """Raised when a profile-sourced binding cannot be resolved for a calculation."""


class ProfileSourcedBindingResult(BaseModel):
    """Profile facts projected into engine binding channels.

    ``binding_values`` carries Decimal-channel bindings; ``enum_binding_values``
    carries string-channel (enum-dispatch) bindings. ``bindings_sourced_from_profile``
    is the union of both key sets, sorted -- a trace of every binding
    the profile satisfied.
    """

    model_config = _STRICT_FROZEN

    binding_values: Mapping[str, Decimal] = Field(default_factory=dict)
    enum_binding_values: Mapping[str, str] = Field(default_factory=dict)
    bindings_sourced_from_profile: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _enforce_trace(self) -> ProfileSourcedBindingResult:
        resolved = set(self.binding_values) | set(self.enum_binding_values)
        if resolved != set(self.bindings_sourced_from_profile):
            raise ProfileBindingResolutionError(
                "profile-sourced binding trace does not match the resolved binding keys"
            )
        return self


def _profile_fact_index(record: object, schema: ProfileSchemaDefinition) -> dict[str, str]:
    """Build a selector -> str(value) index covering both selector forms.

    A profile binding's selector resolves either as the canonical
    ``section.field`` fact path (``profile_key`` form) or as a schema
    ``model_selector`` alias (``profile_model`` + ``field`` form). The
    index exposes each non-null fact under its canonical path AND under
    every ``model_selector`` the schema declares for it, so both
    selector forms find the value.
    """

    selector_index: dict[str, tuple[str, ...]] = {}
    for section in schema.sections:
        for field in section.fields:
            selector_index[f"{section.key}.{field.key}"] = tuple(field.model_selectors)

    index: dict[str, str] = {}
    facts = getattr(record, "facts", ())
    for fact in facts:
        if fact.value is None:
            continue
        rendered = str(fact.value)
        index[fact.path] = rendered
        for selector in selector_index.get(fact.path, ()):
            index[selector] = rendered
    return index


def _decimal_value(binding_id: str, value: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ProfileBindingResolutionError(
            f"profile fact for Decimal-channel binding {binding_id!r} is not decimal-compatible; "
            f"got {value!r}. The registry consumes this binding as a numeric operand, not an enum "
            f"dispatch key; the profile fact must carry a numeric value"
        ) from exc


def resolve_profile_sourced_bindings(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object | None = None,
    caller_binding_ids: frozenset[str] = frozenset(),
    schema: ProfileSchemaDefinition | None = None,
) -> ProfileSourcedBindingResult:
    """Resolve every ``source = "profile"`` binding the revision declares.

    Walks the registry revision's ``source = "profile"`` bindings,
    matches each against a fact on the bucket's user profile, and routes
    the value into the Decimal channel or the enum channel per
    :func:`enum_consumed_binding_ids`.

    A binding the caller already supplied (``caller_binding_ids``) is
    skipped -- caller overrides take precedence over the profile. A
    binding the profile cannot satisfy is skipped silently: the engine
    surfaces the missing-binding error only if a formula needs it.

    ``profile_record`` is injectable for testing; production callers
    leave it ``None`` and the bucket's :class:`UserProfileRecord` is
    loaded. A bucket with no profile yields an empty result.
    """

    # A profile binding only matters to the engine when a formula
    # consumes it. Identity / export-layout profile bindings (the
    # taxpayer NIF, display name, ...) are projected onto the filing
    # draft, never the calculation graph; injecting them into a binding
    # channel would force a non-numeric value through the Decimal
    # channel and fail. Restrict resolution to formula-consumed
    # bindings.
    formula_consumed: set[str] = set()
    for formula in snapshot.revision.formulas:
        formula_consumed.update(expression_binding_refs(formula.expression))
    profile_bindings = [
        binding
        for binding in snapshot.revision.bindings
        if binding.source == "profile" and str(binding.id) in formula_consumed
    ]
    if not profile_bindings:
        return ProfileSourcedBindingResult()

    record = profile_record
    if record is None:
        from ..user_profile import UserProfileLifecycleRepository

        try:
            record = UserProfileLifecycleRepository(bucket_id=bucket_id).load(bucket_id)
        except ProfileNotFoundError:
            return ProfileSourcedBindingResult()

    resolved_schema = schema if schema is not None else load_user_profile_schema()
    fact_index = _profile_fact_index(record, resolved_schema)
    enum_bindings = enum_consumed_binding_ids(snapshot.revision)

    decimal_values: dict[str, Decimal] = {}
    enum_values: dict[str, str] = {}
    for binding in profile_bindings:
        binding_id = str(binding.id)
        if binding_id in caller_binding_ids:
            continue
        value = _resolve_one(binding, fact_index)
        if value is None:
            continue
        if binding_id in enum_bindings:
            enum_values[binding_id] = value
        else:
            decimal_values[binding_id] = _decimal_value(binding_id, value)

    sourced = tuple(sorted(set(decimal_values) | set(enum_values)))
    return ProfileSourcedBindingResult(
        binding_values=decimal_values,
        enum_binding_values=enum_values,
        bindings_sourced_from_profile=sourced,
    )


def _resolve_one(binding: DataBindingDefinition, fact_index: Mapping[str, str]) -> str | None:
    """Return the profile fact value for one profile binding, or None if absent."""

    for selector in profile_binding_selectors(binding.selector):
        value = fact_index.get(selector)
        if value is not None and value.strip():
            return value.strip()
    return None


__all__ = [
    "ProfileBindingResolutionError",
    "ProfileSourcedBindingResult",
    "resolve_profile_sourced_bindings",
]
