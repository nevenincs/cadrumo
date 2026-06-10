"""Application-owned profile-sourced binding resolution.

A registry binding with ``source = "profile"`` carries a value the
operator already entered onto their user profile (tax-residence CCAA,
censo status, declaration type, ...). Without an explicit resolution
step the calculation engine never sees those facts: the operator would
have to re-type, via ``--binding KEY=VALUE``, data the profile already
holds, and a formula that consumes an unsupplied profile binding fails
with ``binding ... has no supplied value``.

This module loads the bucket's :class:`UserProfileRecord`, walks every
``source = "profile"`` binding the :class:`RegistrySnapshot` revision declares,
and projects the matching profile fact into the correct engine channel.
The resolved bindings use :class:`ProfileSchemaDefinition` and
:class:`UserProfileFactValue` to translate raw facts.

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

import hashlib
from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from ...core._models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.external_constants import UTF_8_ENCODING
from ...core.logging import get_logger
from ...core.parsing._dates import _parse_iso8601_date
from ...core.parsing._utils import _parse_bool
from ...domain.calculations.registry import (
    DataBindingDefinition,
    RegistrySnapshot,
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_date_binding_refs,
)
from ...domain.contribuyente import marriage_full_year, marriage_month_start
from ...domain.modelos._errors import ModeloError
from ...domain.user_profile import (
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    UserProfileFactValue,
    load_user_profile_schema,
    profile_binding_selectors,
)
from ._decimal_binding_value import decimal_from_string


class ProfileBindingResolutionError(ModeloError):
    """Raised when a profile-sourced binding cannot be resolved for a calculation."""


class ProfileSourcedBindingResult(BaseModel):
    """Profile facts projected into engine binding channels.

    ``binding_values`` carries Decimal-channel bindings; ``enum_binding_values``
    carries string-channel (enum-dispatch) bindings; ``date_binding_values``
    carries date-channel bindings consumed by ``age_at_year_end``.
    ``bindings_sourced_from_profile`` is the union of all key sets, sorted
    -- a trace of every binding the profile satisfied.
    """

    model_config = _STRICT_FROZEN

    binding_values: Mapping[str, Decimal] = Field(default_factory=dict)
    enum_binding_values: Mapping[str, str] = Field(default_factory=dict)
    date_binding_values: Mapping[str, date] = Field(default_factory=dict)
    bindings_sourced_from_profile: tuple[str, ...] = ()
    profile_record_fingerprint: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _enforce_trace(self) -> ProfileSourcedBindingResult:
        resolved = set(self.binding_values) | set(self.enum_binding_values) | set(self.date_binding_values)
        if resolved != set(self.bindings_sourced_from_profile):
            raise ProfileBindingResolutionError(
                "profile-sourced binding trace does not match the resolved binding keys",
                translated_message="application.modelo.profile_binding.errors.source_trace_mismatch",
                context={
                    "resolved_bindings": tuple(sorted(resolved)),
                    "trace_bindings": tuple(sorted(self.bindings_sourced_from_profile)),
                },
            )
        return self


def _profile_record_fingerprint(profile_record: object | None) -> str | None:
    """Return a stable provenance fingerprint for the loaded profile record."""
    if profile_record is None:
        return None
    payload = profile_record.model_dump_json() if isinstance(profile_record, BaseModel) else repr(profile_record)
    digest = hashlib.sha256(payload.encode(UTF_8_ENCODING)).hexdigest()
    return f"sha256:{digest}"


def _profile_fact_index(record: object, schema: ProfileSchemaDefinition) -> dict[str, UserProfileFactValue]:
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

    index: dict[str, UserProfileFactValue] = {}
    facts = getattr(record, "facts", ())
    for fact in facts:
        if fact.value is None:
            continue
        index[fact.path] = fact.value
        for selector in selector_index.get(fact.path, ()):
            index[selector] = fact.value
    return index


def _inject_derived_marriage_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
) -> None:
    """Inject computed matrimonio-sobrevenido integers into *fact_index* in-place.

    When ``renta_taxpayer.marriage_date`` is present as a ``date``-typed fact,
    the three derived binding keys (``marriage_full_year``,
    ``marriage_month_start``, ``marriage_month_end``) are computed from the raw
    date and the snapshot's ``filing_year``.  They are injected as ``Decimal``
    values so the Decimal-channel binding resolver picks them up without a
    special case in the main loop.

    This function is idempotent: if the keys are already present (e.g. written
    as explicit profile facts by an older tooling version) they are not
    overwritten.
    """
    raw_date = fact_index.get("renta_taxpayer.marriage_date")
    if not isinstance(raw_date, date):
        return

    month_start = marriage_month_start(raw_date, filing_year)
    if month_start is None:
        # marriage_date is in a future filing year — derived facts not applicable.
        return

    full_year = marriage_full_year(raw_date, filing_year)

    if "renta_taxpayer.marriage_full_year" not in fact_index:
        fact_index["renta_taxpayer.marriage_full_year"] = Decimal("1") if full_year else Decimal("0")
    if "renta_taxpayer.marriage_month_start" not in fact_index:
        fact_index["renta_taxpayer.marriage_month_start"] = Decimal(month_start)
    if "renta_taxpayer.marriage_month_end" not in fact_index:
        fact_index["renta_taxpayer.marriage_month_end"] = Decimal("12")


def _inject_derived_family_facts(
    fact_index: dict[str, UserProfileFactValue],
    filing_year: int,
) -> None:
    """Inject computed Art. 81 bis guardería integers into *fact_index* in-place.

    When ``renta_family.descendiente.{n}.birth_date`` facts are present the
    count of children whose age at year-end is < 3 (Art. 58.3 LIRPF) is
    computed and stored as ``renta_family.descendientes_menores_3_{year}``.

    This function is idempotent: keys already present are not overwritten.
    Only the 2024 filing year is handled; other years are ignored until a
    dedicated binding is declared.
    """
    if filing_year != 2024:
        return

    menores_key = "renta_family.descendientes_menores_3_2024"
    if menores_key in fact_index:
        return

    # Reconstruct per-descendant birth_dates from stored facts.
    count_menores = 0
    idx = 0
    while True:
        birth_raw = fact_index.get(f"renta_family.descendiente.{idx}.birth_date")
        if birth_raw is None:
            break
        convivencia_raw = fact_index.get(f"renta_family.descendiente.{idx}.convivencia", "true")
        convive = str(convivencia_raw).lower() not in ("false", "0")
        if convive:
            try:
                birth = _parse_iso8601_date(str(birth_raw))
                if birth is None:
                    raise ValueError("birth date parsed as None")
                age_at_year_end = filing_year - birth.year
                if age_at_year_end < 3:
                    count_menores += 1
            except (ValueError, TypeError) as exc:
                get_logger(__name__).debug(
                    "profile-binding: failed to parse birth date for menores count; skipping entry (%s: %s)",
                    type(exc).__name__,
                    exc,
                )
        idx += 1

    fact_index[menores_key] = Decimal(count_menores)


def _inject_derived_state_attribution_facts(
    fact_index: dict[str, UserProfileFactValue],
) -> None:
    """Inject the M303 state-attribution ratio derived from jurisdiction_scope.

    The IVA model attributes the periodic result to the State (territorio
    común) vs the foral administrations as a percentage in casilla 65. The
    profile records the operator's jurisdiction as the typed enum
    ``tax_residence.jurisdiction_scope`` with values ``common_regime`` (the
    full State attribution applies) or ``foral_unsupported`` (the foral
    branch is not supported; the calc downstream emits zero, blocking the
    filing). Project the enum onto the Decimal-channel synthetic key
    ``tax_residence.state_attribution_ratio`` so the registry binding
    consumes it through the existing Decimal-channel resolver without a
    new enum→Decimal transform op.

    Idempotent: if the synthetic key is already present (explicit profile
    fact written by an older tooling version) it is not overwritten.
    """
    synthetic_key = "tax_residence.state_attribution_ratio"
    if synthetic_key in fact_index:
        return
    scope = fact_index.get("tax_residence.jurisdiction_scope")
    if scope == "common_regime":
        fact_index[synthetic_key] = Decimal("100")
    elif scope == "foral_unsupported":
        fact_index[synthetic_key] = Decimal("0")
    # No scope on the profile yet: leave the synthetic key absent so the
    # engine's missing-binding refusal surfaces the gap operator-side
    # rather than silently defaulting.


def _decimal_value(binding_id: str, value: object) -> Decimal:
    # Boolean-typed profile facts arrive as Python ``bool`` now that
    # ``_profile_fact_index`` preserves the typed value. ``bool`` is a
    # subclass of ``int``, so ``isinstance(value, bool)`` must be tested
    # before ``isinstance(value, (int, Decimal))`` to avoid the ``1``/``0``
    # integer path silently accepting booleans.
    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        # Legacy path: tolerate string-encoded booleans and numeric strings
        # that may arrive from older serialised records or direct callers.
        stripped = value.strip()
        _bool_candidate = _parse_bool(stripped)
        if isinstance(_bool_candidate, bool):
            return Decimal("1") if _bool_candidate else Decimal("0")
        return decimal_from_string(
            binding_id,
            stripped,
            error_factory=lambda _message: ProfileBindingResolutionError(
                f"profile fact for numeric binding {binding_id!r} must be decimal-compatible. "
                "The registry consumes this binding as a numeric operand, not an enum "
                "dispatch key; the profile fact must carry a numeric value",
                translated_message="application.modelo.profile_binding.errors.decimal_value_invalid",
                context={"binding_id": binding_id, "value_type": "str"},
            ),
            pipeline_label="profile fact",
        )
    raise ProfileBindingResolutionError(
        f"profile fact for Decimal-channel binding {binding_id!r} is not decimal-compatible; "
        f"got value type {type(value).__name__!r}. The registry consumes this binding as a "
        f"numeric operand; the profile fact must carry a numeric value",
        translated_message="application.modelo.profile_binding.errors.decimal_value_type_invalid",
        context={"binding_id": binding_id, "value_type": type(value).__name__},
    )


def resolve_profile_sourced_bindings(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object | None = None,
    caller_binding_ids: frozenset[str] = frozenset(),
    schema: ProfileSchemaDefinition | None = None,
) -> ProfileSourcedBindingResult:
    """Resolve every ``source = "profile"`` binding the revision declares.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision's profile bindings
            are resolved against the bucket's user profile facts.
        bucket_id: Stable bucket identifier used to load the user profile.
        profile_record: Optional :class:`UserProfileRecord` override for testing.
        caller_binding_ids: Binding ids already supplied by the caller; these are
            skipped so caller overrides take precedence over the profile.
        schema: Optional profile schema definition override.

    Walks the registry revision's ``source = "profile"`` bindings,
    matches each against a fact on the bucket's user profile, and routes
    the value into the Decimal channel or the enum channel per
    :func:`enum_consumed_binding_ids`.

    A binding the profile cannot satisfy is skipped silently: the engine
    surfaces the missing-binding error only if a formula needs it.
    A bucket with no profile yields an empty result.

    Returns a :class:`ProfileSourcedBindingResult` with resolved binding
    values split across Decimal and enum channels.
    """
    # A profile binding only matters to the engine when a formula
    # consumes it. Identity / export-layout profile bindings (the
    # taxpayer NIF, display name, ...) are projected onto the filing
    # draft, never the calculation graph; injecting them into a binding
    # channel would force a non-numeric value through the Decimal
    # channel and fail. Restrict resolution to formula-consumed
    # bindings.
    formula_consumed: set[str] = set()
    formula_date_consumed: set[str] = set()
    for formula in snapshot.revision.formulas:
        formula_consumed.update(expression_binding_refs(formula.expression))
        formula_date_consumed.update(expression_date_binding_refs(formula.expression))
    profile_bindings = [
        binding
        for binding in snapshot.revision.bindings
        if binding.source == "profile"
        and (str(binding.id) in formula_consumed or str(binding.id) in formula_date_consumed)
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
    profile_record_fingerprint = _profile_record_fingerprint(record)

    resolved_schema = schema if schema is not None else load_user_profile_schema()
    fact_index = _profile_fact_index(record, resolved_schema)
    _inject_derived_marriage_facts(fact_index, snapshot.filing_year)
    _inject_derived_family_facts(fact_index, snapshot.filing_year)
    _inject_derived_state_attribution_facts(fact_index)
    enum_bindings = enum_consumed_binding_ids(snapshot.revision)

    decimal_values: dict[str, Decimal] = {}
    enum_values: dict[str, str] = {}
    date_values: dict[str, date] = {}
    for binding in profile_bindings:
        binding_id = str(binding.id)
        if binding_id in caller_binding_ids:
            continue
        value = _resolve_one(binding, fact_index)
        if binding_id in formula_date_consumed:
            # Date-channel bindings carry date-typed facts (e.g. birth_date)
            # consumed by the age_at_year_end op.  They must not be projected
            # through the Decimal or enum channels.  A missing date fact is
            # an unrecoverable input — no defensible zero-default for a
            # date — so the engine surfaces it as a missing-binding refusal.
            if value is None:
                continue
            if not isinstance(value, date):
                raise ProfileBindingResolutionError(
                    f"profile fact for date-channel binding {binding_id!r} must be a date, "
                    f"got {type(value).__name__!r}",
                    translated_message="application.modelo.profile_binding.errors.date_value_type_invalid",
                    context={"binding_id": binding_id, "value_type": type(value).__name__},
                )
            date_values[binding_id] = value
        elif binding_id in enum_bindings:
            # Boolean-typed facts must never reach the enum dispatch channel —
            # enum dispatch keys are string category codes, not yes/no flags.
            # A bool here signals a mis-wired registry binding; refuse early
            # rather than letting the engine silently mismatch the dispatch table.
            # A missing enum fact is unrecoverable — categorical dispatch has
            # no defensible default — so the engine raises a missing-binding
            # refusal downstream.
            if value is None:
                continue
            if isinstance(value, bool):
                raise ProfileBindingResolutionError(
                    f"profile fact for enum-channel binding {binding_id!r} resolved to a boolean "
                    f"({value!r}); boolean facts are not valid enum dispatch keys",
                    translated_message="application.modelo.profile_binding.errors.enum_boolean_invalid",
                    context={"binding_id": binding_id, "value_type": "bool"},
                )
            enum_values[binding_id] = str(value)
        else:
            # The resolver projects profile facts into engine channels;
            # it does not invent values the operator never supplied. A
            # missing Decimal-channel fact is skipped so the engine
            # surfaces the missing-binding refusal — unless the caller
            # supplies an explicit baseline. Per-verb baselines (e.g.
            # ``verb_baseline_bindings`` in ``modelo project``,
            # work_calculate's analogous setup) own the "operator declared
            # nothing" semantics for each call site, because the right
            # default differs per verb (single-filer for projection vs.
            # explicit operator entry for work_calculate). The classifier
            # discovered 9 of 12 M100 profile bindings are core inputs
            # whose zero-default corrupts the calculation, not optional
            # levers — a blanket resolver-side zero is structurally wrong.
            if value is None:
                continue
            decimal_values[binding_id] = _decimal_value(binding_id, value)

    sourced = tuple(sorted(set(decimal_values) | set(enum_values) | set(date_values)))
    return ProfileSourcedBindingResult(
        binding_values=decimal_values,
        enum_binding_values=enum_values,
        date_binding_values=date_values,
        bindings_sourced_from_profile=sourced,
        profile_record_fingerprint=profile_record_fingerprint if sourced else None,
    )


def _resolve_one(
    binding: DataBindingDefinition, fact_index: Mapping[str, UserProfileFactValue]
) -> UserProfileFactValue | None:
    """Return the typed profile fact value for one profile binding, or None if absent."""
    for selector in profile_binding_selectors(binding.selector):
        value = fact_index.get(selector)
        if value is None:
            continue
        # Blank strings are treated as absent; all other typed values (bool,
        # Decimal, date, int) are non-blank by definition.
        if isinstance(value, str) and not value.strip():
            continue
        return value.strip() if isinstance(value, str) else value
    return None


__all__ = [
    "ProfileBindingResolutionError",
    "ProfileSourcedBindingResult",
    "resolve_profile_sourced_bindings",
]
