"""Application-owned Modelo 100 borrador binding resolution tests."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from aeat.application.aggregation import CalculationSourceContext
from aeat.application.live import Borrador100Snapshot, Borrador100SnapshotRepository, SnapshotLifecycleState
from aeat.application.modelo import (
    Modelo100BorradorBindingCommand,
    Modelo100BorradorBindingError,
    Modelo100BorradorBindingResult,
    Modelo100BorradorSourceResolver,
    calculate_modelo_revision,
    create_work_unit,
    resolve_modelo_100_borrador_bindings,
)
from aeat.core.errors import ErrorCategory, get_registered_error_code
from aeat.core.resources import resources
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType
from aeat.domain.calculations.registry import RegistrySnapshot
from aeat.domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from aeat.domain.modelos._calculation_revision import derive_calculation_revision_id
from aeat.domain.modelos._repository import WorkUnitCatalogueRepository
from aeat.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_BUCKET_ID = "bucket-renta"
_YEAR = 2025
_PERIOD = "0A"
_DECIMAL_BINDING = "renta-2025-modelo-111-retenciones-periodicas"
_ENUM_BINDING = "renta-2025-profile-tax-residence-ccaa"
_UNMARKED_BINDING = "renta-2025-ledger-expense-0186-deductible"


@pytest.fixture
def snapshot_repository(tmp_path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield Borrador100SnapshotRepository(
            bucket_id=_BUCKET_ID,
            objects=profile.repository,
        )


@pytest.fixture
def service_repositories(tmp_path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
            Borrador100SnapshotRepository(bucket_id=_BUCKET_ID, objects=objects),
            objects,
        )


def _modelo_100_registry_snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _save_snapshot(
    repository: Borrador100SnapshotRepository,
    values: dict[str, Decimal | str],
    *,
    state: SnapshotLifecycleState = SnapshotLifecycleState.ACTIVE,
    superseded_by_snapshot_id: str | None = None,
    discarded_by: str = "",
) -> str:
    snapshot = Borrador100Snapshot(
        snapshot_id="borrador-100-2025-active",
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=_PERIOD,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url="https://www2.agenciatributaria.gob.es/wlpl/PRET-R210/SimuladorOpenAjax",
        state=state,
        binding_values=values,
        superseded_by_snapshot_id=superseded_by_snapshot_id,
        discarded_at=datetime(2026, 4, 4, 10, 0, tzinfo=UTC) if state is SnapshotLifecycleState.DISCARDED else None,
        discarded_by=discarded_by,
        discard_reason="refetched" if state is SnapshotLifecycleState.DISCARDED else "",
    )
    repository.save(snapshot)
    return snapshot.snapshot_id


def _command(
    *,
    borrador_snapshot_id: str | None,
    modelo: str = "100",
    bucket_id: str = _BUCKET_ID,
    caller_binding_values: dict[str, Decimal] | None = None,
    caller_enum_binding_values: dict[str, str] | None = None,
    filing_year: int = _YEAR,
    period: str = _PERIOD,
) -> Modelo100BorradorBindingCommand:
    return Modelo100BorradorBindingCommand(
        bucket_id=bucket_id,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        borrador_snapshot_id=borrador_snapshot_id,
        caller_binding_values=caller_binding_values or {},
        caller_enum_binding_values=caller_enum_binding_values or {},
    )


def _non_borrador_decimal_binding_values() -> dict[str, Decimal]:
    return {
        str(binding.id): Decimal("0")
        for binding in _modelo_100_registry_snapshot().revision.bindings
        if str(binding.id) not in {_DECIMAL_BINDING, _ENUM_BINDING}
    }


def _non_borrador_enum_binding_values() -> dict[str, str]:
    return {}


def _zero_relation_values() -> dict[str, Decimal]:
    return {str(relation.id): Decimal("0") for relation in _modelo_100_registry_snapshot().revision.relations}


def test_borrador_binding_command_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Modelo100BorradorBindingCommand.model_validate(
            {
                "bucket_id": _BUCKET_ID,
                "modelo": "100",
                "filing_year": _YEAR,
                "period": _PERIOD,
                "borrador_snapshot_id": None,
                "unknown": "field",
            }
        )


def test_borrador_binding_command_rejects_blank_caller_binding_keys() -> None:
    with pytest.raises(Modelo100BorradorBindingError, match="claves de binding"):
        _command(borrador_snapshot_id="snap-1", caller_binding_values={" ": Decimal("1")})


def test_borrador_binding_result_requires_trace_to_match_values() -> None:
    with pytest.raises(Modelo100BorradorBindingError, match="traza de origen"):
        Modelo100BorradorBindingResult(
            borrador_snapshot_id="snap-1",
            binding_values={_DECIMAL_BINDING: Decimal("1")},
            enum_binding_values={},
            bindings_sourced_from_borrador=(),
        )


def test_borrador_resolution_is_inert_without_named_snapshot(snapshot_repository) -> None:
    result = resolve_modelo_100_borrador_bindings(
        _command(borrador_snapshot_id=None),
        registry_snapshot=_modelo_100_registry_snapshot(),
        snapshot_repository=snapshot_repository,
    )

    assert result.borrador_snapshot_id is None
    assert result.binding_values == {}
    assert result.enum_binding_values == {}
    assert result.bindings_sourced_from_borrador == ()


def test_committed_modelo_100_registry_declares_borrador_prefilled_bindings() -> None:
    bindings = {str(binding.id): binding for binding in _modelo_100_registry_snapshot().revision.bindings}

    assert bindings[_DECIMAL_BINDING].aeat_prefilled is True
    assert bindings[_ENUM_BINDING].aeat_prefilled is True


def test_borrador_resolution_consumes_only_registry_prefilled_bindings(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )

    result = resolve_modelo_100_borrador_bindings(
        _command(borrador_snapshot_id=snapshot_id),
        registry_snapshot=_modelo_100_registry_snapshot(),
        snapshot_repository=snapshot_repository,
    )

    assert result.borrador_snapshot_id == "borrador-100-2025-active"
    assert result.binding_values == {_DECIMAL_BINDING: Decimal("125.50")}
    assert result.enum_binding_values == {_ENUM_BINDING: "madrid"}
    assert result.bindings_sourced_from_borrador == (_DECIMAL_BINDING, _ENUM_BINDING)


def test_borrador_source_resolver_matches_application_binding_resolution(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )
    registry_snapshot = _modelo_100_registry_snapshot()
    expected = resolve_modelo_100_borrador_bindings(
        _command(borrador_snapshot_id=snapshot_id),
        registry_snapshot=registry_snapshot,
        snapshot_repository=snapshot_repository,
    )

    resolution = Modelo100BorradorSourceResolver(
        borrador_snapshot_id=snapshot_id,
        caller_binding_values={},
        caller_enum_binding_values={},
        registry_snapshot=registry_snapshot,
        snapshot_repository=snapshot_repository,
    ).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=_PERIOD,
            revision=registry_snapshot.revision,
        )
    )

    assert resolution.binding_values == expected.binding_values
    assert resolution.enum_binding_values == expected.enum_binding_values
    assert resolution.owned_sources == ("borrador",)
    assert {item.source_kind for item in resolution.provenance} == {"borrador"}
    assert {item.source_ref for item in resolution.provenance} == {
        f"borrador:{snapshot_id}:binding:{_DECIMAL_BINDING}",
        f"borrador:{snapshot_id}:binding:{_ENUM_BINDING}",
    }
    expected_fingerprint = f"sha256:{hashlib.sha256(snapshot_id.encode('utf-8')).hexdigest()}"
    assert {item.fingerprint for item in resolution.provenance} == {expected_fingerprint}


def test_calculate_modelo_revision_consumes_borrador_snapshot_through_application_service(
    service_repositories,
) -> None:
    work_unit_repository, calculation_repository, bucket_event_repository, snapshot_repository, objects = (
        service_repositories
    )
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=_PERIOD,
        revision_id="2025",
        repository=work_unit_repository,
    )
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={},
        binding_values=_non_borrador_decimal_binding_values(),
        enum_binding_values=_non_borrador_enum_binding_values(),
        borrador_snapshot_id=snapshot_id,
        relation_values=_zero_relation_values(),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=snapshot_repository,
    )

    assert Decimal(revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("125.50")
    assert revision.binding_overrides[_ENUM_BINDING] == "madrid"
    assert revision.borrador_snapshot_id == snapshot_id
    assert revision.bindings_sourced_from_borrador == (_DECIMAL_BINDING, _ENUM_BINDING)
    fresh_calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
    stored_revision = fresh_calculation_repository.load().get(revision.calculation_revision_id)
    assert stored_revision == revision
    assert stored_revision is not None
    assert stored_revision.borrador_snapshot_id == snapshot_id
    assert stored_revision.bindings_sourced_from_borrador == (_DECIMAL_BINDING, _ENUM_BINDING)
    assert Decimal(stored_revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("125.50")
    calculation_events = [
        event
        for event in bucket_event_repository.load().for_bucket(_BUCKET_ID)
        if event.event_type is BucketEventType.MODELO_CALCULATION_CREATED
    ]
    assert len(calculation_events) == 1
    event = calculation_events[0]
    assert event.object_id == revision.calculation_revision_id
    assert event.payload_version == 2
    assert event.payload["calculation_revision_id"] == revision.calculation_revision_id
    assert event.payload["borrador_snapshot_id"] == snapshot_id
    assert event.payload["borrador_participated"] == "true"
    assert event.payload["borrador_binding_count"] == "2"
    assert (
        event.payload["borrador_bindings_trace_sha256"]
        == hashlib.sha256("\n".join((_DECIMAL_BINDING, _ENUM_BINDING)).encode("utf-8")).hexdigest()
    )


def test_borrador_binding_error_has_stable_service_error_code() -> None:
    code = get_registered_error_code(Modelo100BorradorBindingError)

    assert code.code == "REFUSED_MODELO_100_BORRADOR_BINDING"
    assert code.category is ErrorCategory.REFUSED
    assert code.message_key == "errors.refused.refused_modelo_100_borrador_binding"


def test_calculate_modelo_revision_precedence_keeps_caller_above_borrador_and_backend(
    service_repositories,
) -> None:
    work_unit_repository, calculation_repository, bucket_event_repository, snapshot_repository, _ = service_repositories
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=_PERIOD,
        revision_id="2025",
        repository=work_unit_repository,
    )
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={},
        binding_values=_non_borrador_decimal_binding_values(),
        enum_binding_values={**_non_borrador_enum_binding_values(), _ENUM_BINDING: "cataluna"},
        backend_binding_values={_DECIMAL_BINDING: Decimal("1.00")},
        borrador_snapshot_id=snapshot_id,
        relation_values=_zero_relation_values(),
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=snapshot_repository,
    )

    assert Decimal(revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("125.50")
    assert revision.binding_overrides[_ENUM_BINDING] == "cataluna"
    assert revision.bindings_sourced_from_borrador == (_DECIMAL_BINDING,)


def test_borrador_snapshot_id_participates_in_calculation_revision_identity() -> None:
    first = derive_calculation_revision_id(
        work_unit_id="1" * 64,
        inputs_snapshot={},
        binding_overrides={_DECIMAL_BINDING: "125.50"},
        casilla_values={"0100": Decimal("125.50")},
        borrador_snapshot_id="borrador-one",
        bindings_sourced_from_borrador=(_DECIMAL_BINDING,),
    )
    second = derive_calculation_revision_id(
        work_unit_id="1" * 64,
        inputs_snapshot={},
        binding_overrides={_DECIMAL_BINDING: "125.50"},
        casilla_values={"0100": Decimal("125.50")},
        borrador_snapshot_id="borrador-two",
        bindings_sourced_from_borrador=(_DECIMAL_BINDING,),
    )

    assert first != second


def test_borrador_resolution_leaves_explicit_caller_binding_in_control(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("1"),
            _ENUM_BINDING: "madrid",
        },
    )

    result = resolve_modelo_100_borrador_bindings(
        _command(
            borrador_snapshot_id=snapshot_id,
            caller_binding_values={_DECIMAL_BINDING: Decimal("0")},
            caller_enum_binding_values={_ENUM_BINDING: "cataluna"},
        ),
        registry_snapshot=_modelo_100_registry_snapshot(),
        snapshot_repository=snapshot_repository,
    )

    assert result.binding_values == {}
    assert result.enum_binding_values == {}
    assert result.bindings_sourced_from_borrador == ()


def test_borrador_resolution_rejects_registry_unmarked_binding_values(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(snapshot_repository, {_UNMARKED_BINDING: Decimal("1")})

    with pytest.raises(Modelo100BorradorBindingError, match="aeat_prefilled"):
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )


def test_borrador_resolution_rejects_non_decimal_value_for_numeric_binding(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(snapshot_repository, {_DECIMAL_BINDING: "not-a-decimal"})

    with pytest.raises(Modelo100BorradorBindingError, match="must be decimal-compatible"):
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )


def test_borrador_resolution_rejects_missing_snapshot_with_live_list_pointer(snapshot_repository) -> None:
    with pytest.raises(Modelo100BorradorBindingError, match="not found") as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id="missing-snapshot"),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )

    assert exc_info.value.suggestion == "aeat app live borrador 100 list"


def test_borrador_resolution_rejects_non_modelo_100_consumers(snapshot_repository) -> None:
    with pytest.raises(Modelo100BorradorBindingError, match="registry snapshot modelo does not match"):
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id="snapshot-does-not-need-loading", modelo="303"),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )


def test_borrador_resolution_rejects_registry_snapshot_axis_mismatch(snapshot_repository) -> None:
    with pytest.raises(Modelo100BorradorBindingError, match="registry snapshot axis"):
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id="snapshot-does-not-need-loading", filing_year=2024),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )


def test_borrador_resolution_rejects_superseded_snapshot_with_list_pointer(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {_DECIMAL_BINDING: Decimal("1")},
        state=SnapshotLifecycleState.SUPERSEDED,
        superseded_by_snapshot_id="borrador-100-2025-newer",
    )

    with pytest.raises(Modelo100BorradorBindingError, match="aeat app live borrador 100 list") as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )

    assert exc_info.value.suggestion == "aeat app live borrador 100 list"


def test_borrador_resolution_rejects_discarded_snapshot_with_list_pointer(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {_DECIMAL_BINDING: Decimal("1")},
        state=SnapshotLifecycleState.DISCARDED,
        discarded_by="operator",
    )

    with pytest.raises(Modelo100BorradorBindingError, match="aeat app live borrador 100 list") as exc_info:
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )

    assert exc_info.value.suggestion == "aeat app live borrador 100 list"


def test_borrador_resolution_rejects_bucket_or_axis_mismatch(snapshot_repository) -> None:
    snapshot_id = _save_snapshot(snapshot_repository, {_DECIMAL_BINDING: Decimal("1")})

    with pytest.raises(Modelo100BorradorBindingError, match="active bucket"):
        resolve_modelo_100_borrador_bindings(
            _command(borrador_snapshot_id=snapshot_id, bucket_id="other-bucket"),
            registry_snapshot=_modelo_100_registry_snapshot(),
            snapshot_repository=snapshot_repository,
        )
