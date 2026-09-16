"""Profile-sourced binding auto-resolution into the calculation engine.

A registry binding with ``source = "profile"`` carries a fact the
operator already entered onto their user profile. These tests prove
``calculate_modelo_revision`` resolves those facts into the engine's
binding channels automatically, routing each through the channel the
registry formula consumes (Decimal vs string enum), so the operator
does not have to re-type profile data and the estimacion-directa
enum/Decimal channel mismatch is rejected at the binding boundary.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....core.aggregation import BindingSourceKind
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ....domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import BindingDefinition, FormulaDefinition, RegistrySnapshot
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...aggregation.source_mesh import CalculationSourceResolution
from ..profile_binding import (
    ProfileBindingResolutionError,
    resolve_profile_sourced_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    """Lease one generation for each profile-binding resolution test."""
    with bundled_indexed_authority().operation() as operation:
        yield operation


_PROFILE_ID = "10000000-0000-4000-8000-000000000476"
_BUCKET_ID = _PROFILE_ID
_YEAR = 2025
_PERIOD = "0A"
_CCAA_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_SYNTHETIC_DECIMAL_PROFILE_BINDING: BindingId = "test-profile-business-ratio-decimal-binding"
_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)


def _sourced_binding_ids(result: CalculationSourceResolution) -> set[BindingId]:
    """The set of bindings the profile satisfied across the three engine channels.

    ``resolve_profile_sourced_bindings`` now returns the canonical
    :class:`CalculationSourceResolution`; the per-channel keys are the trace the
    retired ``bindings_sourced_from_profile`` field used to materialise.
    """
    return set(result.binding_values) | set(result.enum_binding_values) | set(result.date_binding_values)


def _modelo_100_snapshot() -> RegistrySnapshot:
    return published_snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="tax_residence.ccaa", value=ccaa),
            # M100 2025 added age_at_year_end date binding + declaration-type
            # and derived marriage facts. Seed minimum values so M100 calculate
            # resolves the profile-sourced bindings.
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )


def test_profile_ccaa_fact_resolves_into_the_enum_binding_channel(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The tax-residence CCAA profile fact lands in the string enum channel.

    The Modelo 100 autonomic chain consumes the CCAA binding via the
    ``lookup_parameter_by_entity_type`` / ``lookup_bracket_by_ccaa``
    dispatch ops, which read the string ``enum_binding_values`` channel.
    The resolver must route the profile fact there, not into the
    Decimal channel.
    """
    result = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("cataluna"),
        operation=authority_operation,
    )
    assert result.enum_binding_values[_CCAA_BINDING] == "cataluna"
    assert _CCAA_BINDING not in result.binding_values
    assert _CCAA_BINDING in _sourced_binding_ids(result)


def test_profile_resolution_skips_caller_supplied_bindings(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A binding the caller already supplied is not overridden by the profile."""
    result = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("madrid"),
        caller_binding_ids=frozenset({_CCAA_BINDING}),
        operation=authority_operation,
    )
    assert _CCAA_BINDING not in result.enum_binding_values
    assert _CCAA_BINDING not in _sourced_binding_ids(result)


def test_profile_resolution_is_empty_when_no_profile_fact_is_set(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A profile without the CCAA fact contributes nothing for that binding."""
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )
    result = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=record,
        operation=authority_operation,
    )
    assert _CCAA_BINDING not in result.enum_binding_values
    assert _CCAA_BINDING not in result.binding_values


def test_profile_resolution_routes_two_ccaa_values_distinctly(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Anti-tautology: the resolved enum value tracks the profile fact.

    Two profiles differing only by their CCAA fact resolve to distinct
    enum-channel values, so the value is genuinely read off the profile.
    """
    cataluna = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("cataluna"),
        operation=authority_operation,
    )
    madrid = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("madrid"),
        operation=authority_operation,
    )
    assert cataluna.enum_binding_values[_CCAA_BINDING] == "cataluna"
    assert madrid.enum_binding_values[_CCAA_BINDING] == "madrid"
    assert cataluna.enum_binding_values[_CCAA_BINDING] != madrid.enum_binding_values[_CCAA_BINDING]


def test_profile_numeric_fact_resolves_into_the_decimal_binding_channel(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A formula-consumed numeric profile fact lands in the Decimal channel.

    Modelo 100 currently consumes its real profile-sourced CCAA binding
    through enum dispatch formulas. This synthetic revision extension
    covers the sibling channel contract: a profile-sourced binding
    referenced as a numeric formula operand must be Decimal-coerced and
    must not leak into ``enum_binding_values``.
    """
    snapshot = _snapshot_with_decimal_profile_binding(_modelo_100_snapshot())
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="usage_ratios.business_ratio", value=Decimal("0.37")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )

    result = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=record,
        operation=authority_operation,
    )

    assert result.binding_values[_SYNTHETIC_DECIMAL_PROFILE_BINDING] == Decimal("0.37")
    assert _SYNTHETIC_DECIMAL_PROFILE_BINDING not in result.enum_binding_values
    assert _SYNTHETIC_DECIMAL_PROFILE_BINDING in _sourced_binding_ids(result)


def _snapshot_with_decimal_profile_binding(snapshot: RegistrySnapshot) -> RegistrySnapshot:
    binding = BindingDefinition.model_validate(
        {
            "id": _SYNTHETIC_DECIMAL_PROFILE_BINDING,
            "provider": {"kind": BindingSourceKind.PROFILE, "profile_key": "usage_ratios.business_ratio"},
            "value": {"data_type": "money", "channel": "decimal"},
            "legal_refs": snapshot.revision.legal_refs,
            "source_refs": snapshot.revision.source_refs,
        },
    )
    formula = FormulaDefinition(
        id="test-profile-business-ratio-decimal-formula",
        target_casilla_id=snapshot.revision.casillas[0].id,
        expression=FormulaExpression(binding=_SYNTHETIC_DECIMAL_PROFILE_BINDING),
        legal_refs=snapshot.revision.legal_refs,
        source_refs=snapshot.revision.source_refs,
    )
    revision = snapshot.revision.model_copy(
        update={
            "bindings": (*snapshot.revision.bindings, binding),
            "formulas": (*snapshot.revision.formulas, formula),
        },
    )
    return snapshot.model_copy(update={"revision": revision})


# ---------------------------------------------------------------------------
# contract regression: bool-typed profile facts preserved and routed correctly
# ---------------------------------------------------------------------------

_SYNTHETIC_BOOL_PROFILE_BINDING: BindingId = "test-profile-new-entity-bool-binding"


def _snapshot_with_bool_profile_binding(snapshot: RegistrySnapshot) -> RegistrySnapshot:
    """Extend the M100 snapshot with a synthetic bool-channel profile binding.

    The synthetic binding mirrors the LIS Art. 29 new-entity-override
    pattern: a yes/no profile fact consumed as a numeric 1/0 operand
    inside an ``if_then_else`` predicate on the Decimal channel.
    """
    binding = BindingDefinition.model_validate(
        {
            "id": _SYNTHETIC_BOOL_PROFILE_BINDING,
            "provider": {"kind": BindingSourceKind.PROFILE, "profile_key": "entity.new_entity_override"},
            "value": {"data_type": "boolean", "channel": "boolean"},
            "legal_refs": snapshot.revision.legal_refs,
            "source_refs": snapshot.revision.source_refs,
        },
    )
    formula = FormulaDefinition(
        id="test-profile-new-entity-bool-formula",
        target_casilla_id=snapshot.revision.casillas[0].id,
        expression=FormulaExpression(binding=_SYNTHETIC_BOOL_PROFILE_BINDING),
        legal_refs=snapshot.revision.legal_refs,
        source_refs=snapshot.revision.source_refs,
    )
    revision = snapshot.revision.model_copy(
        update={
            "bindings": (*snapshot.revision.bindings, binding),
            "formulas": (*snapshot.revision.formulas, formula),
        },
    )
    return snapshot.model_copy(update={"revision": revision})


def _profile_with_bool_fact(value: bool) -> UserProfileRecord:
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="entity.new_entity_override", value=value),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )


class TestBoolTypedProfileBinding:
    """Pin the typed-bool path through profile_fact_index → _decimal_value.

    contract regression: a bool-typed profile fact must arrive at the Decimal
    channel as Decimal("1")/Decimal("0") via the isinstance(value, bool)
    branch in _decimal_value, never as a string "True"/"False" that would
    require re-parsing, and never silently as Decimal("1") via the int
    subclass path without the explicit bool check.
    """

    def test_bool_true_fact_resolves_to_decimal_one_in_binding_channel(
        self,
        authority_operation: PinnedAuthorityOperation,
    ) -> None:
        snapshot = _snapshot_with_bool_profile_binding(_modelo_100_snapshot())
        result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(True),
            operation=authority_operation,
        )
        assert result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING] == Decimal("1")
        assert _SYNTHETIC_BOOL_PROFILE_BINDING not in result.enum_binding_values

    def test_bool_false_fact_resolves_to_decimal_zero_in_binding_channel(
        self,
        authority_operation: PinnedAuthorityOperation,
    ) -> None:
        snapshot = _snapshot_with_bool_profile_binding(_modelo_100_snapshot())
        result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(False),
            operation=authority_operation,
        )
        assert result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING] == Decimal("0")
        assert _SYNTHETIC_BOOL_PROFILE_BINDING not in result.enum_binding_values

    def test_bool_true_and_false_resolve_to_distinct_decimal_values(
        self,
        authority_operation: PinnedAuthorityOperation,
    ) -> None:
        """Anti-tautology: the two bool values produce distinct Decimal outputs."""
        snapshot = _snapshot_with_bool_profile_binding(_modelo_100_snapshot())
        true_result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(True),
            operation=authority_operation,
        )
        false_result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(False),
            operation=authority_operation,
        )
        assert (
            true_result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING]
            != false_result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING]
        )

    def test_bool_fact_on_enum_channel_raises(
        self,
        authority_operation: PinnedAuthorityOperation,
    ) -> None:
        """A bool fact wired to an enum-dispatch binding raises ProfileBindingResolutionError.

        Boolean facts are never valid enum dispatch keys; the resolver
        must refuse rather than silently coercing True -> "True" and
        producing a dispatch-table miss.
        """
        # Construct a snapshot whose CCAA binding (enum channel) is satisfied
        # by a bool fact — a mis-wired scenario the guard must catch.
        snapshot = _modelo_100_snapshot()
        bool_profile = _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="tax_residence.ccaa", value=True),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
            context=_profile_creation_context_for_test(),
        )
        with pytest.raises(
            ProfileBindingResolutionError,
            match="boolean facts are not valid enum dispatch keys",
        ) as exc_info:
            resolve_profile_sourced_bindings(
                snapshot,
                bucket_id=_BUCKET_ID,
                profile_record=bool_profile,
                operation=authority_operation,
            )
        assert exc_info.value.translated_message == "application.modelo.profile_binding.errors.enum_boolean_invalid"
        assert exc_info.value.context == {"binding_id": _CCAA_BINDING, "value_type": "bool"}


def test_string_decimal_profile_raises_type_invalid_error_without_leaking_value(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A string-typed profile fact in a Decimal channel raises a type-invalid error.

    ``_coerce_profile_fact_value`` promotes canonical Decimal/bool/date strings
    to their typed counterparts at the Pydantic boundary.  A string that is not
    a valid Decimal, boolean token, or date falls through as ``str``.  The
    Decimal-channel resolver now refuses it via the typed ``ProfileBindingResolutionError``
    without echoing the raw value, preserving redaction and localization.
    """
    snapshot = _snapshot_with_decimal_profile_binding(_modelo_100_snapshot())
    record = _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="usage_ratios.business_ratio", value="not-a-decimal-secret"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=_profile_creation_context_for_test(),
    )

    with pytest.raises(ProfileBindingResolutionError, match="decimal-compatible") as exc_info:
        resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=record,
            operation=authority_operation,
        )

    assert "not-a-decimal-secret" not in str(exc_info.value)
    assert exc_info.value.translated_message == "application.modelo.profile_binding.errors.decimal_value_type_invalid"
    assert exc_info.value.context == {"binding_id": _SYNTHETIC_DECIMAL_PROFILE_BINDING, "value_type": "str"}


def test_profile_resolution_declares_the_terminal_origin_it_produced(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The real resolver names the class of terminal fact behind each value.

    Provenance that says which resolver ran but not what kind of fact it
    reached cannot be audited against the binding's declared terminal origin:
    the value and the declaration would agree by assumption. This pins that the
    live profile resolver states ``profile_field`` on every row it emits, with
    the evidence fingerprint that class is expected to carry.
    """
    result = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("cataluna"),
        operation=authority_operation,
    )

    assert result.provenance
    assert all(row.terminal_origin is TerminalOriginClass.PROFILE_FIELD for row in result.provenance)
    assert all(row.fingerprint is not None for row in result.provenance)
