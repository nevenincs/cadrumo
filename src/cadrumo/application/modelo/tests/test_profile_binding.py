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

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.schema import DataBindingDefinition, FormulaDefinition, RegistrySnapshot
from ....domain.calculations.registry.schema_formula import FormulaExpression
from ....domain.modelos.errors import ModeloError
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceResolution
from ..calculation_actions import calculate_modelo_revision
from ..profile_binding import (
    ProfileBindingResolutionError,
    resolve_profile_sourced_bindings,
)
from ..work_lifecycle import create_work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "10000000-0000-4000-8000-000000000476"
_BUCKET_ID = _PROFILE_ID
_YEAR = 2025
_PERIOD = "0A"
_TYPED_PERIOD = Period.from_year_and_code(_YEAR, _PERIOD)
_CCAA_BINDING: BindingId = "renta-2025-profile-tax-residence-ccaa"
_ESTIMACION_BINDING: BindingId = "renta-2025-modelo-100-estimacion-directa-es-normal"
_SYNTHETIC_DECIMAL_PROFILE_BINDING: BindingId = "test-profile-business-ratio-decimal-binding"
_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)


def _sourced_binding_ids(result: CalculationSourceResolution) -> set[BindingId]:
    """The set of bindings the profile satisfied across the three engine channels.

    ``resolve_profile_sourced_bindings`` now returns the canonical
    :class:`CalculationSourceResolution`; the per-channel keys are the trace the
    retired ``bindings_sourced_from_profile`` field used to materialise.
    """
    return set(result.binding_values) | set(result.enum_binding_values) | set(result.date_binding_values)


@contextmanager
def _secure_backend(tmp_path: Path) -> Generator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


def _calculation_repositories() -> tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    BucketEventHistoryRepository,
]:
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _store_profile(record: UserProfileRecord) -> None:
    seed_test_profile_record(record)


def _modelo_100_snapshot() -> RegistrySnapshot:
    return bundled_authority().snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    return UserProfileRecord(
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
    )


def test_profile_ccaa_fact_resolves_into_the_enum_binding_channel() -> None:
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
    )
    assert result.enum_binding_values[_CCAA_BINDING] == "cataluna"
    assert _CCAA_BINDING not in result.binding_values
    assert _CCAA_BINDING in _sourced_binding_ids(result)


def test_profile_resolution_skips_caller_supplied_bindings() -> None:
    """A binding the caller already supplied is not overridden by the profile."""
    result = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("madrid"),
        caller_binding_ids=frozenset({_CCAA_BINDING}),
    )
    assert _CCAA_BINDING not in result.enum_binding_values
    assert _CCAA_BINDING not in _sourced_binding_ids(result)


def test_profile_resolution_is_empty_when_no_profile_fact_is_set() -> None:
    """A profile without the CCAA fact contributes nothing for that binding."""
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )
    result = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=record,
    )
    assert _CCAA_BINDING not in result.enum_binding_values
    assert _CCAA_BINDING not in result.binding_values


def test_profile_resolution_routes_two_ccaa_values_distinctly() -> None:
    """Anti-tautology: the resolved enum value tracks the profile fact.

    Two profiles differing only by their CCAA fact resolve to distinct
    enum-channel values, so the value is genuinely read off the profile.
    """
    cataluna = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("cataluna"),
    )
    madrid = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("madrid"),
    )
    assert cataluna.enum_binding_values[_CCAA_BINDING] == "cataluna"
    assert madrid.enum_binding_values[_CCAA_BINDING] == "madrid"
    assert cataluna.enum_binding_values[_CCAA_BINDING] != madrid.enum_binding_values[_CCAA_BINDING]


def test_profile_numeric_fact_resolves_into_the_decimal_binding_channel() -> None:
    """A formula-consumed numeric profile fact lands in the Decimal channel.

    Modelo 100 currently consumes its real profile-sourced CCAA binding
    through enum dispatch formulas. This synthetic revision extension
    covers the sibling channel contract: a profile-sourced binding
    referenced as a numeric formula operand must be Decimal-coerced and
    must not leak into ``enum_binding_values``.
    """
    snapshot = _snapshot_with_decimal_profile_binding(_modelo_100_snapshot())
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="usage_ratios.business_ratio", value=Decimal("0.37")),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )

    result = resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_BUCKET_ID,
        profile_record=record,
    )

    assert result.binding_values[_SYNTHETIC_DECIMAL_PROFILE_BINDING] == Decimal("0.37")
    assert _SYNTHETIC_DECIMAL_PROFILE_BINDING not in result.enum_binding_values
    assert _SYNTHETIC_DECIMAL_PROFILE_BINDING in _sourced_binding_ids(result)


def _snapshot_with_decimal_profile_binding(snapshot: RegistrySnapshot) -> RegistrySnapshot:
    binding = DataBindingDefinition.model_validate(
        {
            "id": _SYNTHETIC_DECIMAL_PROFILE_BINDING,
            "source": BindingSourceKind.PROFILE,
            "selector": {"profile_key": "usage_ratios.business_ratio"},
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


def _non_ccaa_decimal_binding_values(snapshot: RegistrySnapshot) -> dict[BindingId, Decimal]:
    """Supply every non-CCAA, non-profile binding through the Decimal channel as zero.

    The CCAA binding is deliberately omitted: the calculation under test
    must source it from the user profile, not from caller input. Other
    ``source="profile"`` bindings (M100 2025 added an age_at_year_end
    date binding plus declaration-type) are likewise excluded so the
    profile resolver populates them from the seeded
    :class:`UserProfileRecord`.
    """
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id != _CCAA_BINDING and binding.source != "profile"
    }


def _zero_relation_values(snapshot: RegistrySnapshot) -> dict[RelationId, Decimal]:
    return {relation.id: Decimal("0") for relation in snapshot.revision.relations}


def test_calculate_modelo_revision_resolves_ccaa_from_profile_without_caller_input(
    tmp_path: Path,
) -> None:
    """A Modelo 100 calculation succeeds with CCAA sourced only from the profile.

    The operator supplies no ``--enum-binding`` for CCAA; the engine's
    autonomic-chain dispatch ops require it. The calculation completing
    and producing autonomic-chain casillas proves the profile fact
    reached the enum channel through ``calculate_modelo_revision``.
    """
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            repository=work_repo,
            clock=_CLOCK,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_non_ccaa_decimal_binding_values(snapshot),
            relation_values=_zero_relation_values(snapshot),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_CLOCK,
        )
        # The autonomic minimo-contribuyente casilla is computed by a
        # CCAA-dispatch formula; its presence proves the dispatch resolved.
        assert "0512" in revision.casilla_values
        assert revision.binding_overrides[_CCAA_BINDING] == "madrid"


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
    binding = DataBindingDefinition.model_validate(
        {
            "id": _SYNTHETIC_BOOL_PROFILE_BINDING,
            "source": BindingSourceKind.PROFILE,
            "selector": {"profile_key": "entity.new_entity_override"},
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
    return UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="entity.new_entity_override", value=value),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


class TestBoolTypedProfileBinding:
    """Pin the typed-bool path through profile_fact_index → _decimal_value.

    contract regression: a bool-typed profile fact must arrive at the Decimal
    channel as Decimal("1")/Decimal("0") via the isinstance(value, bool)
    branch in _decimal_value, never as a string "True"/"False" that would
    require re-parsing, and never silently as Decimal("1") via the int
    subclass path without the explicit bool check.
    """

    def test_bool_true_fact_resolves_to_decimal_one_in_binding_channel(self) -> None:
        snapshot = _snapshot_with_bool_profile_binding(_modelo_100_snapshot())
        result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(True),
        )
        assert result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING] == Decimal("1")
        assert _SYNTHETIC_BOOL_PROFILE_BINDING not in result.enum_binding_values

    def test_bool_false_fact_resolves_to_decimal_zero_in_binding_channel(self) -> None:
        snapshot = _snapshot_with_bool_profile_binding(_modelo_100_snapshot())
        result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(False),
        )
        assert result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING] == Decimal("0")
        assert _SYNTHETIC_BOOL_PROFILE_BINDING not in result.enum_binding_values

    def test_bool_true_and_false_resolve_to_distinct_decimal_values(self) -> None:
        """Anti-tautology: the two bool values produce distinct Decimal outputs."""
        snapshot = _snapshot_with_bool_profile_binding(_modelo_100_snapshot())
        true_result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(True),
        )
        false_result = resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=_profile_with_bool_fact(False),
        )
        assert (
            true_result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING]
            != false_result.binding_values[_SYNTHETIC_BOOL_PROFILE_BINDING]
        )

    def test_bool_fact_on_enum_channel_raises(self) -> None:
        """A bool fact wired to an enum-dispatch binding raises ProfileBindingResolutionError.

        Boolean facts are never valid enum dispatch keys; the resolver
        must refuse rather than silently coercing True -> "True" and
        producing a dispatch-table miss.
        """
        # Construct a snapshot whose CCAA binding (enum channel) is satisfied
        # by a bool fact — a mis-wired scenario the guard must catch.
        snapshot = _modelo_100_snapshot()
        bool_profile = UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_PROFILE_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="tax_residence.ccaa", value=True),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )
        with pytest.raises(
            ProfileBindingResolutionError,
            match="boolean facts are not valid enum dispatch keys",
        ) as exc_info:
            resolve_profile_sourced_bindings(
                snapshot,
                bucket_id=_BUCKET_ID,
                profile_record=bool_profile,
            )
        assert exc_info.value.translated_message == "application.modelo.profile_binding.errors.enum_boolean_invalid"
        assert exc_info.value.context == {"binding_id": _CCAA_BINDING, "value_type": "bool"}


def test_string_decimal_profile_raises_type_invalid_error_without_leaking_value() -> None:
    """A string-typed profile fact in a Decimal channel raises a type-invalid error.

    ``_coerce_profile_fact_value`` promotes canonical Decimal/bool/date strings
    to their typed counterparts at the Pydantic boundary.  A string that is not
    a valid Decimal, boolean token, or date falls through as ``str``.  The
    Decimal-channel resolver now refuses it via the typed ``ProfileBindingResolutionError``
    without echoing the raw value, preserving redaction and localization.
    """
    snapshot = _snapshot_with_decimal_profile_binding(_modelo_100_snapshot())
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="usage_ratios.business_ratio", value="not-a-decimal-secret"),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )

    with pytest.raises(ProfileBindingResolutionError, match="decimal-compatible") as exc_info:
        resolve_profile_sourced_bindings(
            snapshot,
            bucket_id=_BUCKET_ID,
            profile_record=record,
        )

    assert "not-a-decimal-secret" not in str(exc_info.value)
    assert exc_info.value.translated_message == "application.modelo.profile_binding.errors.decimal_value_type_invalid"
    assert exc_info.value.context == {"binding_id": _SYNTHETIC_DECIMAL_PROFILE_BINDING, "value_type": "str"}


def test_calculate_modelo_revision_rejects_ccaa_supplied_through_decimal_channel(
    tmp_path: Path,
) -> None:
    """Supplying the enum-consumed CCAA binding as a Decimal is refused.

    CCAA is consumed by a dispatch op (string enum channel). Routing it
    through the Decimal ``--binding`` channel is a binding-type
    mismatch; the boundary rejects it with a clear message instead of
    letting the engine raise an opaque ``binding has no supplied value``.
    """
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            repository=work_repo,
            clock=_CLOCK,
        )
        decimal_bindings = {binding.id: Decimal("0") for binding in snapshot.revision.bindings}
        with pytest.raises(ModeloError):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=decimal_bindings,
                relation_values=_zero_relation_values(snapshot),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_CLOCK,
            )
        assert calc_repo.load().revisions == {}


def test_estimacion_directa_binding_stays_in_the_decimal_channel(
    tmp_path: Path,
) -> None:
    """The estimacion-directa modality binding is a Decimal-channel binding.

    ``renta-2025-modelo-100-estimacion-directa-es-normal`` carries a
    ``typed_enum`` annotation, yet the Modelo 100 rendimiento-neto
    formula consumes it as a Decimal operand (compared to a numeric
    literal). Supplying it as a Decimal must be accepted; the boundary
    must not misroute it to the enum channel on the strength of its
    ``typed_enum`` tag alone.
    """
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            repository=work_repo,
            clock=_CLOCK,
        )
        revision = calculate_modelo_revision(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            binding_values=_non_ccaa_decimal_binding_values(snapshot),
            relation_values=_zero_relation_values(snapshot),
            work_unit_repository=work_repo,
            calculation_repository=calc_repo,
            bucket_event_repository=event_repo,
            clock=_CLOCK,
        )
        assert Decimal(revision.binding_overrides[_ESTIMACION_BINDING]) == Decimal("0")


def test_estimacion_directa_binding_rejected_through_enum_channel(
    tmp_path: Path,
) -> None:
    """Routing the Decimal-consumed estimacion-directa binding as an enum is refused.

    This is the estimacion-directa enum/Decimal mismatch: the binding
    declares ``typed_enum`` so a caller might route it to the enum
    channel, but the formula consumes it as a Decimal operand. The
    boundary rejects the mismatch with a clear message.
    """
    with _secure_backend(tmp_path):
        _store_profile(_profile_with_ccaa("madrid"))
        snapshot = _modelo_100_snapshot()
        work_repo, calc_repo, event_repo = _calculation_repositories()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_TYPED_PERIOD,
            revision_id="2025",
            repository=work_repo,
            clock=_CLOCK,
        )
        with pytest.raises(ModeloError):
            calculate_modelo_revision(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                binding_values=_non_ccaa_decimal_binding_values(snapshot),
                enum_binding_values={_ESTIMACION_BINDING: "normal"},
                relation_values=_zero_relation_values(snapshot),
                work_unit_repository=work_repo,
                calculation_repository=calc_repo,
                bucket_event_repository=event_repo,
                clock=_CLOCK,
            )
        assert calc_repo.load().revisions == {}
