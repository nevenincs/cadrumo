"""Application-owned profile-sourced Modelo binding resolution.

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

The :class:`ModeloRevision` on that snapshot is also what decides whether a
derived-fact injector runs at all: the injectors are gated on the revision
declaring a binding that consumes their output, so extending coverage to a
new filing year is registry work rather than a code edit.

Channel selection is the load-bearing decision. The registry runtime
resolves profile bindings through four engine channels:
``date_binding_values`` for date operands, ``enum_binding_values`` for
dispatch keys, ``boolean_binding_values`` for truth values, and
Decimal-valued ``binding_values`` for numeric operands. The boolean channel
is selected from the binding's OWN declared value contract
(``value.channel = "boolean"``), never from the Python type of the fact that
turned up: a truth value routed by type would follow whatever the profile
happened to store, which is how a yes/no fact came to be labelled as currency.
The remaining three are determined by the consumer shape:
:func:`expression_date_binding_refs` finds date operands,
:func:`enum_consumed_binding_ids` finds enum dispatch operands, and
formula-consumed or bound numeric casillas use the Decimal channel. A
calculation-only typed enum also uses the enum channel. Profile bindings
that only populate identity or export-layout fields are intentionally left
out of the calculation source mesh.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.aggregation import BindingSourceKind, BindingTypedEnumKind, CalculationSourceLineageRole
from ...core.external_constants import UTF_8_ENCODING
from ...core.hashing import prefixed_digest
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.binding_value_contract import BindingValueChannel
from ...domain.calculations.registry.ids import BindingId
from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.calculations.registry.rental_reduction import require_rental_reduction_art232_tier
from ...domain.calculations.registry.runtime_graph import (
    enum_consumed_binding_ids,
    expression_binding_refs,
    expression_date_binding_refs,
)
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_base import NUMERIC_CASILLA_DATA_TYPES
from ...domain.user_profile.errors import ProfileNotFoundError
from ...domain.user_profile.registry_contract import profile_binding_selectors
from ...domain.user_profile.schema import ProfileSchemaDefinition, derived_selector_for_path
from ...domain.user_profile.values import UserProfileFactValue
from ..aggregation.source_mesh import (
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from ..user_profile.projections import profile_fact_index
from .profile_derived_facts import (
    ProfileBindingResolutionError,
    declared_profile_selectors,
    family_fact_context,
    inject_derived_anualidades_eligibility_facts,
    inject_derived_autonomic_deduccion_facts,
    inject_derived_deduccion_maternidad_facts,
    inject_derived_incremento_guarderia_facts,
    inject_derived_marriage_facts,
    inject_derived_minimo_descendientes_facts,
    inject_derived_state_attribution_facts,
    inject_ordinary_work_maritime_facts,
)

_PROFILE_RESOLVER_ID = "profile"
_PROFILE_OWNED_SOURCES: tuple[BindingSourceKind, ...] = (BindingSourceKind.PROFILE,)


if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


# Marital-status token sets, derived from the enum rather than restated.
#
# Every predicate below reads ``renta_taxpayer.marital_status``, which the
# profile schema constrains to :class:`RentaMaritalStatus` -- the AEAT ECIVIL
# filing code, ``'1'``-``'5'``. These sets previously also carried word forms
# (``"casado"``, ``"pareja_hecho_registrada"``, ...) belonging to
# :class:`SituacionFamiliar`, a DIFFERENT taxonomy stored at a different field
# (``renta_family.situacion_familiar``). Those words could never match a value
# this field can hold, so they were dead -- and worse than dead: a test passing
# a word form straight to an injector matched on the dead half while every real
# filer took the code half, so dropping a CODE from the set regressed
# production and failed nothing. Measured: removing ``'5'`` left the word form
# answering True while the code form flipped to False.
#
# Deriving them from the enum removes the foreign vocabulary by construction
# and makes a future divergence a type error rather than a silent miss.
#
# SOURCE CHOICE, deliberate. The Art. 61 norma 1a conjunta question is an
# Art. 82.1 question, and :class:`SituacionFamiliar` is the canonical Art. 82
# authority. This still reads the ECIVIL code because both fields are
# ``required = false`` and are asked side by side in the same setup walk, so
# neither is more reliably populated -- while switching would silently drop the
# prorrata for any profile carrying only the ECIVIL code, which is the
# OVER-granting direction. If the source is ever moved, note that
# ``SituacionFamiliar`` distinguishes registered from unregistered pareja de
# hecho and Art. 82.1.2a is registration-agnostic, so BOTH must count as
# partnered; treating only the registered form as partnered would over-grant
# for an unregistered couple.
_ECONOMIC_ACTIVITY_INCOME_CATEGORY = "actividad_economica"
_ECONOMIC_ACTIVITY_PREDICATE_BINDING_SUFFIX = "-profile-has-economic-activity"


def _profile_record_fingerprint(profile_record: object | None) -> str | None:
    """Return a stable provenance fingerprint for the loaded profile record."""
    if profile_record is None:
        return None
    payload = profile_record.model_dump_json() if isinstance(profile_record, BaseModel) else repr(profile_record)
    return prefixed_digest(payload.encode(UTF_8_ENCODING))


def _decimal_value(binding_id: BindingId, value: object) -> Decimal:
    # Boolean-typed profile facts arrive as Python ``bool`` now that
    # ``profile_fact_index`` preserves the typed value. ``bool`` is a
    # subclass of ``int``, so ``isinstance(value, bool)`` must be tested
    # before ``isinstance(value, (int, Decimal))`` to avoid the ``1``/``0``
    # integer path silently accepting booleans.
    if isinstance(value, bool):
        return Decimal("1") if value else Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    raise ProfileBindingResolutionError(
        f"profile fact for Decimal-channel binding {binding_id!r} is not decimal-compatible; "
        f"got value type {type(value).__name__!r}. The registry consumes this binding as a "
        f"numeric operand; the profile fact must carry a numeric value",
        translated_message="application.modelo.profile_binding.errors.decimal_value_type_invalid",
        context={"binding_id": binding_id, "value_type": type(value).__name__},
    )


def _boolean_value(binding_id: BindingId, value: object) -> bool:
    """Return the truth value for a boolean-contract binding, or refuse.

    Deliberately narrow: only a real :class:`bool` satisfies a boolean value
    contract. A ``Decimal("1")`` is accepted nowhere here, because accepting it
    is the coercion this channel exists to remove -- ``Decimal("1") == True`` in
    Python, so a permissive reading would make the two encodings
    indistinguishable again at exactly the boundary meant to tell them apart.
    """
    if isinstance(value, bool):
        return value
    raise ProfileBindingResolutionError(
        f"profile fact for boolean-channel binding {binding_id!r} is not a boolean; "
        f"got value type {type(value).__name__!r}. The registry declares this binding's "
        f"value contract as boolean; a numeric stand-in for a truth value is refused "
        f"rather than coerced",
        translated_message="application.modelo.profile_binding.errors.boolean_value_type_invalid",
        context={"binding_id": binding_id, "value_type": type(value).__name__},
    )


@dataclass(slots=True)
class _ResolvedBindingChannels:
    """Mutable accumulator for the four engine channels a profile binding routes into.

    The Decimal channel carries numeric operands, the enum channel carries
    string dispatch keys, the date channel carries date-typed facts, and the
    boolean channel carries truth values. Object identity of the four dicts is
    preserved across the resolution loop so :func:`_route_resolved_binding`
    mutates the same accumulator in place.
    """

    decimal_values: dict[BindingId, Decimal] = dataclass_field(default_factory=dict)
    enum_values: dict[BindingId, str] = dataclass_field(default_factory=dict)
    date_values: dict[BindingId, date] = dataclass_field(default_factory=dict)
    boolean_values: dict[BindingId, bool] = dataclass_field(default_factory=dict)


def _route_resolved_binding(
    binding_id: BindingId,
    value: UserProfileFactValue,
    *,
    is_date_channel: bool,
    is_enum_channel: bool,
    declared_channel: BindingValueChannel,
    channels: _ResolvedBindingChannels,
) -> None:
    """Route one resolved profile fact into its engine channel on ``channels``.

    The binding's AUTHORED value contract decides the transport, for every
    channel. That is the only authority that can be right about a binding whose
    consumers have not been written yet, or whose consumer disappeared: a
    declared date binding with no ``age_at_year_end`` op still holds a date, and
    inferring its transport from the formulas that happen to read it made the
    contract a function of downstream code rather than of the declaration.

    The consumer shape is retained as a CROSS-CHECK rather than dropped. A
    binding a formula consumes as a date operand while declaring some other
    contract is a declaration that disagrees with its own use, and resolving it
    on either channel would silently pick a winner between two authorities; it
    is refused instead. Measured across the bundled registry when this routing
    landed, exactly two declarations disagreed -- a birth date declared ``text``
    and an ISO country code declared ``money`` -- and both were corrected at the
    declaration rather than absorbed here.

    The caller has already skipped ``None`` (absent) facts.
    """
    _reject_channel_declaration_conflict(
        binding_id,
        declared_channel=declared_channel,
        is_date_channel=is_date_channel,
        is_enum_channel=is_enum_channel,
    )
    if declared_channel is BindingValueChannel.DATE:
        # Date-channel bindings carry date-typed facts (e.g. birth_date)
        # consumed by the age_at_year_end op. They must not be projected
        # through the Decimal, enum, or boolean channels.
        if not isinstance(value, date):
            raise ProfileBindingResolutionError(
                f"profile fact for date-channel binding {binding_id!r} must be a date, got {type(value).__name__!r}",
                translated_message="application.modelo.profile_binding.errors.date_value_type_invalid",
                context={"binding_id": binding_id, "value_type": type(value).__name__},
            )
        channels.date_values[binding_id] = value
        return
    if declared_channel is BindingValueChannel.BOOLEAN:
        channels.boolean_values[binding_id] = _boolean_value(binding_id, value)
        return
    if declared_channel is BindingValueChannel.ENUM or is_enum_channel:
        # Boolean-typed facts must never reach the enum dispatch channel --
        # enum dispatch keys are string category codes, not yes/no flags.
        # A bool here signals a mis-wired registry binding; refuse early
        # rather than letting the engine silently mismatch the dispatch table.
        if isinstance(value, bool):
            raise ProfileBindingResolutionError(
                f"profile fact for enum-channel binding {binding_id!r} resolved to a boolean "
                f"({value!r}); boolean facts are not valid enum dispatch keys",
                translated_message="application.modelo.profile_binding.errors.enum_boolean_invalid",
                context={"binding_id": binding_id, "value_type": "bool"},
            )
        channels.enum_values[binding_id] = str(value)
        return
    if isinstance(value, bool):
        # A truth value for a contract that is not boolean. Folding it onto the
        # Decimal channel is how "no" became the number zero: the resulting
        # figure is a filing-grade amount the fact never asserted.
        raise ProfileBindingResolutionError(
            f"profile fact for binding {binding_id!r} is a boolean but the binding declares the "
            f"{declared_channel.value!r} value channel; a truth value is not a "
            f"{declared_channel.value} quantity and is refused rather than coerced",
            translated_message="application.modelo.profile_binding.errors.boolean_value_channel_mismatch",
            context={"binding_id": binding_id, "declared_channel": declared_channel.value},
        )
    # The resolver projects profile facts into engine channels; it does not
    # invent values the operator never supplied. Per-verb baselines own the
    # "operator declared nothing" semantics for each call site, because the
    # right default differs per verb (single-filer for projection vs.
    # explicit operator entry for work_calculate). The classifier discovered
    # 9 of 12 M100 profile bindings are core inputs whose zero-default
    # corrupts the calculation, not optional levers -- a blanket
    # resolver-side zero is structurally wrong.
    channels.decimal_values[binding_id] = _decimal_value(binding_id, value)


def _reject_channel_declaration_conflict(
    binding_id: BindingId,
    *,
    declared_channel: BindingValueChannel,
    is_date_channel: bool,
    is_enum_channel: bool,
) -> None:
    """Refuse a binding whose consuming formula contradicts its declared contract.

    The cross-check that keeps declared-channel routing honest. Without it,
    moving the authority to the declaration would convert a disagreement into
    silence: a birth date declared ``text`` would simply resolve as text and the
    ``age_at_year_end`` op would then report a missing date binding, blaming the
    profile for a declaration defect.

    The enum direction is asymmetric on purpose. A declared ENUM binding with no
    enum-dispatch consumer is legal -- a calculation-only typed enum, or a
    dispatch key whose consumer lives on another revision -- so only the reverse
    (consumed as enum, declared as something else) is a contradiction.
    """
    if is_date_channel and declared_channel is not BindingValueChannel.DATE:
        raise ProfileBindingResolutionError(
            f"binding {binding_id!r} is consumed as a date operand but declares the "
            f"{declared_channel.value!r} value channel; correct the binding's value contract "
            f"rather than resolving it on a channel its declaration does not name",
            translated_message="application.modelo.profile_binding.errors.channel_declaration_conflict",
            context={"binding_id": binding_id, "declared_channel": declared_channel.value, "consumer_channel": "date"},
        )
    if is_enum_channel and declared_channel not in {BindingValueChannel.ENUM, BindingValueChannel.TEXT}:
        raise ProfileBindingResolutionError(
            f"binding {binding_id!r} is consumed as an enum dispatch key but declares the "
            f"{declared_channel.value!r} value channel; correct the binding's value contract "
            f"rather than resolving it on a channel its declaration does not name",
            translated_message="application.modelo.profile_binding.errors.channel_declaration_conflict",
            context={"binding_id": binding_id, "declared_channel": declared_channel.value, "consumer_channel": "enum"},
        )


@dataclass(frozen=True, slots=True)
class _ProfileBindingSelection:
    """Profile bindings the source mesh must resolve, plus the date-consumed set."""

    bindings: tuple[BindingDefinition, ...]
    formula_date_consumed: frozenset[BindingId]


@dataclass(frozen=True, slots=True)
class _ProfileFacts:
    """The bucket's resolved profile fact index plus its record fingerprint."""

    fact_index: dict[str, UserProfileFactValue]
    fingerprint: str | None


def _is_calculation_only_profile_binding(binding: BindingDefinition) -> bool:
    provider = binding.provider
    if not isinstance(provider, ProfileProvider):
        return False
    return not any((provider.xsd_path, provider.xsd_attribute, provider.dictionary_field))


def _is_relevant_profile_binding(
    binding: BindingDefinition,
    *,
    formula_consumed: set[BindingId],
    formula_date_consumed: set[BindingId],
    bound_casilla_binding_ids: set[BindingId],
) -> bool:
    return binding.source == BindingSourceKind.PROFILE and (
        binding.id in formula_consumed
        or binding.id in formula_date_consumed
        or binding.id in bound_casilla_binding_ids
        or _is_calculation_only_profile_binding(binding)
    )


def _select_profile_bindings(snapshot: RegistrySnapshot) -> _ProfileBindingSelection:
    """Select the ``source = "profile"`` bindings the source mesh must resolve.

    A profile binding matters to the calculation source mesh when a formula
    consumes it, when it feeds a ``bound`` NUMERIC input casilla (e.g. M303
    casilla 65), or when it is a calculation-only selector. The latter has no
    XSD/dictionary export address: M202's INCN applicability fact and M036's
    censo event are registry-owned profile inputs even though neither is read
    by a numeric formula. Identity/export-layout bindings (NIF, display name,
    and similar) retain an export address and must not be pushed through a
    calculation channel: a bound text casilla reads them through
    :func:`~application.modelo.profile_export_binding.resolve_profile_text_casilla_inputs`.
    """
    formula_consumed: set[BindingId] = set()
    formula_date_consumed: set[BindingId] = set()
    for formula in snapshot.revision.formulas:
        formula_consumed.update(expression_binding_refs(formula.expression))
        formula_date_consumed.update(expression_date_binding_refs(formula.expression))
    bound_casilla_binding_ids: set[BindingId] = {
        casilla.binding
        for casilla in snapshot.revision.casillas
        if casilla.binding is not None and casilla.data_type in NUMERIC_CASILLA_DATA_TYPES
    }
    bindings = tuple(
        binding
        for binding in snapshot.revision.bindings
        if _is_relevant_profile_binding(
            binding,
            formula_consumed=formula_consumed,
            formula_date_consumed=formula_date_consumed,
            bound_casilla_binding_ids=bound_casilla_binding_ids,
        )
    )
    return _ProfileBindingSelection(bindings=bindings, formula_date_consumed=frozenset(formula_date_consumed))


def _load_profile_facts(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object | None,
    schema: ProfileSchemaDefinition | None,
    selected_bindings: tuple[BindingDefinition, ...],
    operation: PinnedAuthorityOperation,
) -> _ProfileFacts | None:
    """Load and derive the bucket's profile fact index, or ``None`` when absent."""
    record = profile_record
    if record is None:
        from ..user_profile.profile_record_repository import ProfileRecordRepository

        try:
            record = ProfileRecordRepository.for_current_session(
                bucket_id,
                profile_decode_context=operation.profile_decode_context(),
            ).load(bucket_id)
        except ProfileNotFoundError:
            return None
    profile_record_fingerprint = _profile_record_fingerprint(record)
    if schema is None:
        schema = operation.profile_schema()
    resolved_schema = schema
    fact_index = profile_fact_index(record, resolved_schema)
    family_context = family_fact_context(snapshot, operation=operation)
    inject_derived_marriage_facts(fact_index, snapshot.filing_year)
    inject_ordinary_work_maritime_facts(fact_index)
    declared_selectors = declared_profile_selectors(snapshot.revision)
    inject_derived_anualidades_eligibility_facts(
        fact_index,
        snapshot,
        context=family_context,
        operation=operation,
    )
    inject_derived_autonomic_deduccion_facts(
        fact_index,
        snapshot.filing_year,
        context=family_context,
        operation=operation,
    )
    inject_derived_minimo_descendientes_facts(
        fact_index,
        snapshot,
        context=family_context,
        operation=operation,
    )
    inject_derived_deduccion_maternidad_facts(
        fact_index,
        snapshot,
        declared_selectors,
        context=family_context,
        operation=operation,
    )
    inject_derived_incremento_guarderia_facts(
        fact_index,
        snapshot,
        declared_selectors,
        context=family_context,
        operation=operation,
    )
    if "tax_residence.state_attribution_ratio" in {
        selector for binding in selected_bindings for selector in profile_binding_selectors(binding.provider)
    }:
        inject_derived_state_attribution_facts(
            fact_index,
            effective_date=date(snapshot.filing_year, 1, 1),
            operation=operation,
        )
    return _ProfileFacts(fact_index=fact_index, fingerprint=profile_record_fingerprint)


def resolve_profile_binding_channels(
    bindings: tuple[BindingDefinition, ...],
    fact_index: Mapping[str, UserProfileFactValue],
    *,
    caller_binding_ids: frozenset[BindingId],
    formula_date_consumed: frozenset[BindingId],
    enum_bindings: frozenset[BindingId],
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation,
) -> _ResolvedBindingChannels:
    """Resolve each selected binding into the Decimal / enum / date / boolean channels."""
    channels = _ResolvedBindingChannels()
    for binding in bindings:
        binding_id = binding.id
        if binding_id in caller_binding_ids:
            continue
        value = resolve_profile_binding_value(binding, fact_index)
        if value is None:
            continue
        if binding.value.typed_enum is BindingTypedEnumKind.RENTAL_REDUCTION_ART_23_2_TIER:
            value = require_rental_reduction_art232_tier(
                value,
                effective_date=effective_date,
                authority=operation,
            )
        _route_resolved_binding(
            binding_id,
            value,
            is_date_channel=binding_id in formula_date_consumed,
            is_enum_channel=binding_id in enum_bindings or binding.value.typed_enum is not None,
            declared_channel=binding.value.channel,
            channels=channels,
        )
    return channels


def _profile_value_channel_ids(
    decimal_values: Mapping[BindingId, Decimal],
    enum_values: Mapping[BindingId, str],
    date_values: Mapping[BindingId, date],
    boolean_values: Mapping[BindingId, bool],
) -> frozenset[BindingId]:
    """Union the four value channels a profile resolution populates."""
    return frozenset(set(decimal_values) | set(enum_values) | set(date_values) | set(boolean_values))


def profile_resolved_binding_ids(resolution: CalculationSourceResolution) -> frozenset[BindingId]:
    """Return the binding ids a profile resolution actually satisfied.

    :class:`CalculationSourceResolution` is the shared envelope for every
    source resolver and carries eight value channels; a profile resolution
    populates exactly four of them. Which four is a fact about this
    resolver, so it is stated here once rather than re-encoded by each
    consumer -- the Modelo binding-readiness gate and the operator state
    projection previously open-coded the same union independently, and a
    fourth channel would have been picked up by whichever site was edited.

    Args:
        resolution: The result returned by
            :func:`resolve_profile_sourced_bindings`.

    Returns:
        The binding ids the profile satisfied, across all populated channels.
    """
    return _profile_value_channel_ids(
        resolution.binding_values,
        resolution.enum_binding_values,
        resolution.date_binding_values,
        resolution.boolean_binding_values,
    )


def resolve_profile_sourced_bindings(
    snapshot: RegistrySnapshot,
    *,
    bucket_id: str,
    profile_record: object | None = None,
    caller_binding_ids: frozenset[BindingId] = frozenset(),
    schema: ProfileSchemaDefinition | None = None,
    operation: PinnedAuthorityOperation,
) -> CalculationSourceResolution:
    """Resolve every ``source = "profile"`` binding the revision declares.

    Args:
        snapshot: The :class:`RegistrySnapshot` whose revision's profile bindings
            are resolved against the bucket's user profile facts.
        bucket_id: Stable bucket identifier used to load the user profile.
        profile_record: Optional :class:`UserProfileRecord` override for testing.
        caller_binding_ids: Binding ids already supplied by the caller; these are
            skipped so caller overrides take precedence over the profile.
        schema: Optional profile schema definition override.
        operation: Caller-held pinned authority operation for every governed
            schema, vocabulary, and catalogue lookup in this resolution.

    Walks the registry revision's ``source = "profile"`` bindings,
    matches each against a fact on the bucket's user profile, and routes
    the value into the Decimal, enum, date, or boolean channel: boolean from
    the binding's own declared value contract, the other three from the
    consuming formula, bound numeric casilla, or calculation-only selector
    with no export address.

    A binding the profile cannot satisfy is skipped silently: the engine
    surfaces the missing-binding error only if a formula needs it.
    A bucket with no profile yields an empty result.

    Returns a :class:`CalculationSourceResolution` with resolved binding
    values split across the Decimal, enum, date, and boolean engine channels and a
    :class:`CalculationSourceProvenance` row per profile-sourced binding.

    See Also:
        :func:`enum_consumed_binding_ids`:
            Identifies profile bindings consumed as enum dispatch keys.
        :func:`expression_date_binding_refs`:
            Identifies profile bindings consumed by date-aware formula ops.
    """
    selection = _select_profile_bindings(snapshot)
    if not selection.bindings:
        return CalculationSourceResolution(resolver_id=_PROFILE_RESOLVER_ID, owned_sources=_PROFILE_OWNED_SOURCES)
    resolved_schema = schema or operation.profile_schema()
    facts = _load_profile_facts(
        snapshot,
        bucket_id=bucket_id,
        profile_record=profile_record,
        schema=resolved_schema,
        selected_bindings=selection.bindings,
        operation=operation,
    )
    if facts is None:
        return CalculationSourceResolution(resolver_id=_PROFILE_RESOLVER_ID, owned_sources=_PROFILE_OWNED_SOURCES)
    channels = resolve_profile_binding_channels(
        selection.bindings,
        facts.fact_index,
        caller_binding_ids=caller_binding_ids,
        formula_date_consumed=selection.formula_date_consumed,
        enum_bindings=enum_consumed_binding_ids(snapshot.revision),
        effective_date=date(snapshot.filing_year, 1, 1),
        operation=operation,
    )
    decimal_values = channels.decimal_values
    enum_values = channels.enum_values
    date_values = channels.date_values
    boolean_values = channels.boolean_values
    sourced = tuple(
        sorted(_profile_value_channel_ids(decimal_values, enum_values, date_values, boolean_values)),
    )
    fingerprint = facts.fingerprint if sourced else None
    return CalculationSourceResolution(
        resolver_id=_PROFILE_RESOLVER_ID,
        owned_sources=_PROFILE_OWNED_SOURCES,
        binding_values=decimal_values,
        enum_binding_values=enum_values,
        date_binding_values=date_values,
        boolean_binding_values=boolean_values,
        diagnostics=_derived_binding_diagnostics(
            selection.bindings,
            facts.fact_index,
            resolved_schema,
            bucket_id=bucket_id,
        ),
        provenance=tuple(
            CalculationSourceProvenance(
                resolver_id=_PROFILE_RESOLVER_ID,
                resolved_binding_source=BindingSourceKind.PROFILE,
                contributor_source_kind=BindingSourceKind.PROFILE.value,
                contributor_binding_source=BindingSourceKind.PROFILE,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=f"profile:{bucket_id}:binding:{binding_id}",
                parent_source_ref=None,
                terminal_origin=TerminalOriginClass.PROFILE_FIELD,
                fingerprint=fingerprint,
            )
            for binding_id in sourced
        ),
    )


def _derived_binding_diagnostics(
    bindings: tuple[BindingDefinition, ...],
    fact_index: Mapping[str, UserProfileFactValue],
    schema: ProfileSchemaDefinition,
    *,
    bucket_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise on a SELECTED derived binding that still resolved to nothing.

    Narrow by construction, and that narrowness is the whole design. A blanket
    "profile binding resolved to nothing" advisory would fire constantly on
    optional facts an ordinary filer legitimately leaves blank, and an
    operator who learns to ignore an advisory is worse off than one who never
    saw it.

    A DERIVED path is different: the engine owns it and every derived injector
    now writes unconditionally, with a zero default where the law says zero.
    So a derived binding that is selected and still resolves to nothing cannot
    be an ordinary absence -- no injector claimed it, which means a structural
    gap (a registry year with no injector coverage, or a pattern whose
    consuming binding drifted). Every fire is real.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for binding in bindings:
        if resolve_profile_binding_value(binding, fact_index) is not None:
            continue
        for selector in profile_binding_selectors(binding.provider):
            derived = derived_selector_for_path(selector, schema.derived_selectors)
            if derived is None:
                continue
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="unresolved_derived_binding",
                    source_kind=BindingSourceKind.PROFILE.value,
                    resolver_id=_PROFILE_RESOLVER_ID,
                    binding_id=binding.id,
                    source_ref=f"profile:{bucket_id}:binding:{binding.id}",
                    message=(
                        f"binding {binding.id!r} selects the engine-derived path {selector!r} "
                        f"but no value was computed for it; the aggregate derived from "
                        f"{', '.join(derived.derived_from)} is missing from this calculation"
                    ),
                ),
            )
            break
    return tuple(diagnostics)


def _economic_activity_binding_value(
    fact_index: Mapping[str, UserProfileFactValue],
) -> bool:
    """Derive the activity predicate from the canonical category fact."""
    raw_categories = str(fact_index.get("taxpayer_type.irpf_income_categories", ""))
    categories = {token.strip() for token in raw_categories.split(",") if token.strip()}
    return _ECONOMIC_ACTIVITY_INCOME_CATEGORY in categories


def _profile_selector_value(
    selector: str,
    fact_index: Mapping[str, UserProfileFactValue],
) -> UserProfileFactValue | None:
    """Read and normalize one profile selector, treating blank text as absent."""
    value = fact_index.get(selector)
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return value


def _first_profile_binding_selector_value(
    binding: BindingDefinition,
    fact_index: Mapping[str, UserProfileFactValue],
    *,
    gate_selector: object | None,
) -> UserProfileFactValue | None:
    """Resolve the first non-gate selector value in declared selector order."""
    for selector in profile_binding_selectors(binding.provider):
        if gate_selector is not None and selector == gate_selector:
            continue
        value = _profile_selector_value(selector, fact_index)
        if value is not None:
            return value
    return None


def resolve_profile_binding_value(
    binding: BindingDefinition,
    fact_index: Mapping[str, UserProfileFactValue],
) -> UserProfileFactValue | None:
    """Return the typed profile fact value for one profile binding, or None if absent."""
    if binding.id.endswith(_ECONOMIC_ACTIVITY_PREDICATE_BINDING_SUFFIX):
        return _economic_activity_binding_value(fact_index)
    # ``profile_binding_selectors`` returns the binding's DEPENDENCY set -- every
    # fact it references -- and that includes ``required_when_profile_key``. The
    # gate fact states WHETHER the binding applies, never WHAT it holds, so it
    # must not stand in as a value. Without this, a gated binding whose real
    # fact is absent silently resolves to its precondition: a conjunta filing
    # missing the spouse's birth date wrote the declaration type ("2") into
    # DPFNAC_C, and a missing EU country wrote a boolean into ZRUE2 -- wrong
    # values on a filed artefact, indistinguishable from real ones. Measured
    # across the whole registry: 12 gated bindings, all Modelo 100, every one
    # declaring a real profile_key/profile_keys, so skipping the gate here
    # can never leave a binding with nothing to resolve from.
    # Read through the registry's own selector normaliser rather than getattr.
    # ``selector`` is legally ``BindingSelector | Mapping``, and on the Mapping
    # shape a getattr returns None, which does not weaken this gate -- it deletes
    # it, silently, and reinstates exactly the regression described above. The
    # accessor answers both shapes, so the gate cannot be defeated by an input
    # shape the type already permits.
    gate_selector = selector_as_dict(binding).get("required_when_profile_key")
    return _first_profile_binding_selector_value(
        binding,
        fact_index,
        gate_selector=gate_selector,
    )
