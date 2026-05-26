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
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from aeat.application.modelo import calculate_modelo_revision, create_work_unit
from aeat.application.modelo._actions import ModeloError
from aeat.application.modelo._profile_binding import (
    ProfileSourcedBindingResult,
    resolve_profile_sourced_bindings,
)
from aeat.application.user_profile import UserProfileLifecycleRepository
from aeat.core.resources import resources
from aeat.domain.buckets import BucketEventHistoryRepository
from aeat.domain.calculations.registry import (
    DataBindingDefinition,
    FormulaDefinition,
    FormulaExpression,
    RegistrySnapshot,
)
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.domain.user_profile import UserProfileFact, UserProfileRecord
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_BUCKET_ID = "operator"
_YEAR = 2025
_PERIOD = "0A"
_CCAA_BINDING = "renta-2025-profile-tax-residence-ccaa"
_ESTIMACION_BINDING = "renta-2025-modelo-100-estimacion-directa-es-normal"
_SYNTHETIC_DECIMAL_PROFILE_BINDING = "test-profile-business-ratio-decimal-binding"
_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)


@contextmanager
def _secure_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


def _calculation_repositories() -> tuple:
    return (
        WorkUnitCatalogueRepository(),
        CalculationRevisionCatalogueRepository(),
        BucketEventHistoryRepository(),
    )


def _store_profile(record: UserProfileRecord) -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(record)


def _modelo_100_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Renta profile taxpayer",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value=ccaa),
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
    assert _CCAA_BINDING in result.bindings_sourced_from_profile


def test_profile_resolution_skips_caller_supplied_bindings() -> None:
    """A binding the caller already supplied is not overridden by the profile."""
    result = resolve_profile_sourced_bindings(
        _modelo_100_snapshot(),
        bucket_id=_BUCKET_ID,
        profile_record=_profile_with_ccaa("madrid"),
        caller_binding_ids=frozenset({_CCAA_BINDING}),
    )
    assert _CCAA_BINDING not in result.enum_binding_values
    assert _CCAA_BINDING not in result.bindings_sourced_from_profile


def test_profile_resolution_is_empty_when_no_profile_fact_is_set() -> None:
    """A profile without the CCAA fact contributes nothing for that binding."""
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="No-CCAA taxpayer",
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
    assert (
        cataluna.enum_binding_values[_CCAA_BINDING]
        != madrid.enum_binding_values[_CCAA_BINDING]
    )


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
        profile_id=_BUCKET_ID,
        display_name="Numeric profile taxpayer",
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
    assert _SYNTHETIC_DECIMAL_PROFILE_BINDING in result.bindings_sourced_from_profile


def _snapshot_with_decimal_profile_binding(snapshot: RegistrySnapshot) -> RegistrySnapshot:
    binding = DataBindingDefinition(
        id=_SYNTHETIC_DECIMAL_PROFILE_BINDING,
        source="profile",
        selector={"profile_key": "usage_ratios.business_ratio"},
        legal_refs=snapshot.revision.legal_refs,
        source_refs=snapshot.revision.source_refs,
    )
    formula = FormulaDefinition(
        id="test-profile-business-ratio-decimal-formula",
        target=snapshot.revision.casillas[0].id,
        expression=FormulaExpression(binding=_SYNTHETIC_DECIMAL_PROFILE_BINDING),
        legal_refs=snapshot.revision.legal_refs,
        source_refs=snapshot.revision.source_refs,
    )
    revision = snapshot.revision.model_copy(
        update={
            "bindings": (*snapshot.revision.bindings, binding),
            "formulas": (*snapshot.revision.formulas, formula),
        }
    )
    return snapshot.model_copy(update={"revision": revision})


def _non_ccaa_decimal_binding_values(snapshot: RegistrySnapshot) -> dict[str, Decimal]:
    """Supply every non-CCAA binding through the Decimal channel as zero.

    The CCAA binding is deliberately omitted: the calculation under
    test must source it from the user profile, not from caller input.
    """
    return {
        str(binding.id): Decimal("0")
        for binding in snapshot.revision.bindings
        if str(binding.id) != _CCAA_BINDING
    }


def _zero_relation_values(snapshot: RegistrySnapshot) -> dict[str, Decimal]:
    return {str(relation.id): Decimal("0") for relation in snapshot.revision.relations}


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
            period=_PERIOD,
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
            period=_PERIOD,
            revision_id="2025",
            repository=work_repo,
            clock=_CLOCK,
        )
        decimal_bindings = {
            str(binding.id): Decimal("0") for binding in snapshot.revision.bindings
        }
        with pytest.raises(ModeloError, match="enum dispatch keys"):
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
            period=_PERIOD,
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
            period=_PERIOD,
            revision_id="2025",
            repository=work_repo,
            clock=_CLOCK,
        )
        with pytest.raises(ModeloError, match="Decimal operands"):
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


def test_profile_sourced_binding_result_rejects_inconsistent_trace() -> None:
    """The result model enforces the trace matches the resolved keys."""
    with pytest.raises(ModeloError):
        ProfileSourcedBindingResult(
            binding_values={},
            enum_binding_values={_CCAA_BINDING: "madrid"},
            bindings_sourced_from_profile=(),
        )
