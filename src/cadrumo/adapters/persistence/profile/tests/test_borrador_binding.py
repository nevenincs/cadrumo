"""Persistence-adapter integration tests for Modelo 100 borrador bindings."""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from dev.registry.compiler.authority import compiled_bundled_authority
from dev.registry.tests.profile_schema_support import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.profile.snapshots import SecureSnapshotRepository
from cadrumo.adapters.persistence.profile.tests._file_flow_support import calculation_ports_for_test
from cadrumo.adapters.persistence.storage.secure_object_namespaces import LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
)
from cadrumo.application.live.errors import LiveApplicationInputError
from cadrumo.application.live.snapshot_base import SnapshotLifecycleState
from cadrumo.application.modelo.calculation_actions import calculate_modelo_revision
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.ids import BindingId, RelationId
from cadrumo.domain.calculations.registry.relations import relation_prefill_bindings_for_period
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.tests.aeat_literal_fixtures import aeat_url, configured_path

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_YEAR = 2025
_PERIOD = "0A"
_DECIMAL_BINDING: BindingId = "renta-modelo-111-retenciones-periodicas"
_ENUM_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_R210_SIMULATOR_URL = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))


def _modelo_100_registry_snapshot() -> RegistrySnapshot:
    return compiled_bundled_authority().snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _borrador_repository(objects: SecureObjectRepository) -> Borrador100SnapshotRepository:
    """Bind the application snapshot port to the encrypted persistence adapter."""
    return SecureSnapshotRepository(
        bucket_id=_BUCKET_ID,
        payload_model=Borrador100Snapshot,
        namespace_definition=LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE,
        object_key=borrador_100_snapshot_object_key,
        not_found_factory=lambda snapshot_id: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_not_found",
            context={"snapshot_id": snapshot_id},
        ),
        ambiguous_prefix_factory=lambda snapshot_id, snapshot_ids: BorradorSnapshotNotFoundError(
            translated_message="application.live.borrador.errors.snapshot_prefix_ambiguous",
            context={"snapshot_id": snapshot_id, "match_count": len(snapshot_ids)},
        ),
        domain_label="borrador",
        input_error_cls=LiveApplicationInputError,
        objects=objects,
    )


@pytest.fixture
def service_repositories(
    tmp_path: Path,
) -> Generator[
    tuple[
        WorkUnitCatalogueRepository,
        CalculationRevisionCatalogueRepository,
        BucketEventHistoryRepository,
        Borrador100SnapshotRepository,
        SecureObjectRepository,
    ]
]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        objects = profile.repository
        yield (
            WorkUnitCatalogueRepository(objects=objects),
            CalculationRevisionCatalogueRepository(objects=objects),
            BucketEventHistoryRepository(objects=objects),
            _borrador_repository(objects),
            objects,
        )


def _save_snapshot(
    repository: Borrador100SnapshotRepository,
    values: dict[str, Decimal | str],
) -> str:
    snapshot = Borrador100Snapshot(
        snapshot_id="a" * 64,
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        registry_snapshot_ref=_modelo_100_registry_snapshot().snapshot_ref,
        captured_at=datetime(2026, 4, 3, 10, 0, tzinfo=UTC),
        source_url=_R210_SIMULATOR_URL,
        state=SnapshotLifecycleState.ACTIVE,
        binding_values=values,
    )
    repository.save(snapshot)
    return snapshot.snapshot_id


def _non_borrador_decimal_binding_values() -> dict[BindingId, Decimal]:
    snapshot = _modelo_100_registry_snapshot()
    alternate_binding_ids = {
        binding_id for casilla in snapshot.revision.casillas for binding_id in casilla.alternate_bindings
    }
    exclusions = {_DECIMAL_BINDING, _ENUM_BINDING, *alternate_binding_ids}
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id not in exclusions and binding.source != "profile"
    }


def _zero_relation_values() -> dict[RelationId, Decimal]:
    return {
        binding.id: Decimal("0")
        for binding, _ in relation_prefill_bindings_for_period(_modelo_100_registry_snapshot().revision)
    }


def _seed_profile_with_birth_date(objects: SecureObjectRepository) -> None:
    """Persist the profile facts required by the live calculation adapter path."""
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="economic activity"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
                UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
                UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
                UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
                UserProfileFact(path="renta_filing.declaration_type", value="1"),
                UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            ),
            created_at=datetime(2026, 4, 1, tzinfo=UTC),
            updated_at=datetime(2026, 4, 1, tzinfo=UTC),
            context=_profile_creation_context_for_test(),
        ),
    )


def test_calculate_modelo_revision_consumes_borrador_snapshot_through_application_service(
    service_repositories: tuple[
        WorkUnitCatalogueRepository,
        CalculationRevisionCatalogueRepository,
        BucketEventHistoryRepository,
        Borrador100SnapshotRepository,
        SecureObjectRepository,
    ],
) -> None:
    work_unit_repository, calculation_repository, bucket_event_repository, snapshot_repository, objects = (
        service_repositories
    )
    _seed_profile_with_birth_date(objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision_id="2025",
        ports=WorkLifecyclePorts(
            work_unit_repository=work_unit_repository, bucket_event_repository=bucket_event_repository
        ),
    )
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )

    relation_values = _zero_relation_values()
    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={},
        binding_values=_non_borrador_decimal_binding_values(),
        enum_binding_values={},
        borrador_snapshot_id=snapshot_id,
        relation_values=relation_values,
        ports=calculation_ports_for_test(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            borrador_snapshot_repository=snapshot_repository,
        ),
    )

    assert Decimal(revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("125.50")
    assert revision.binding_overrides[_ENUM_BINDING] == "madrid"
    assert set(revision.relation_overrides) == set(relation_values)
    assert all(Decimal(value) == Decimal("0") for value in revision.relation_overrides.values())
    assert set(revision.binding_overrides).isdisjoint(revision.relation_overrides)
    assert revision.borrador_snapshot_id == snapshot_id
    assert revision.bindings_sourced_from_borrador == (_DECIMAL_BINDING, _ENUM_BINDING)
    fresh_calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
    stored_revision = fresh_calculation_repository.load().get(revision.calculation_revision_id)
    assert stored_revision == revision
    assert stored_revision is not None
    assert stored_revision.borrador_snapshot_id == snapshot_id
    assert stored_revision.bindings_sourced_from_borrador == (_DECIMAL_BINDING, _ENUM_BINDING)
    assert Decimal(stored_revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("125.50")
    assert stored_revision.relation_overrides == revision.relation_overrides
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


def test_calculate_modelo_revision_precedence_keeps_caller_above_borrador_and_backend(
    service_repositories: tuple[
        WorkUnitCatalogueRepository,
        CalculationRevisionCatalogueRepository,
        BucketEventHistoryRepository,
        Borrador100SnapshotRepository,
        SecureObjectRepository,
    ],
) -> None:
    work_unit_repository, calculation_repository, bucket_event_repository, snapshot_repository, objects = (
        service_repositories
    )
    _seed_profile_with_birth_date(objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _PERIOD),
        revision_id="2025",
        ports=WorkLifecyclePorts(
            work_unit_repository=work_unit_repository, bucket_event_repository=bucket_event_repository
        ),
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
        enum_binding_values={_ENUM_BINDING: "cataluna"},
        backend_binding_values={_DECIMAL_BINDING: Decimal("1.00")},
        borrador_snapshot_id=snapshot_id,
        relation_values=_zero_relation_values(),
        ports=calculation_ports_for_test(
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=bucket_event_repository,
            borrador_snapshot_repository=snapshot_repository,
        ),
    )

    assert Decimal(revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("125.50")
    assert revision.binding_overrides[_ENUM_BINDING] == "cataluna"
    assert revision.bindings_sourced_from_borrador == (_DECIMAL_BINDING,)
