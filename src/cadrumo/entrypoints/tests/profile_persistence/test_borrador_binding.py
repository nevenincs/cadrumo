"""Persistence-adapter integration tests for Modelo 100 borrador bindings.

The 2025 borrador may supply the tax-residence enum, which takes its value from
it, and may hold the work-withholding credit, which it only cross-checks: the
credit is the taxpayer's to evidence, so the borrador never supplies it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Generator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.snapshots import SecureSnapshotRepository
from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from ....adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from ....adapters.persistence.storage.secure_object_namespaces import LIVE_BORRADOR_100_SNAPSHOT_NAMESPACE
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.live.borrador_100 import (
    Borrador100Snapshot,
    Borrador100SnapshotRepository,
    BorradorSnapshotNotFoundError,
    borrador_100_snapshot_object_key,
)
from ....application.live.errors import LiveApplicationInputError
from ....application.live.snapshot_base import SnapshotLifecycleState
from ....application.modelo.calculation_bucket_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ....application.modelo.calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES
from ....application.modelo.work_lifecycle import create_work_unit
from ....application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from ....core.period import Period
from ....core.retencion_soportada import RetencionSoportadaClase
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.binding_targets import casillas_by_binding
from ....domain.calculations.registry.ids import BindingId, RelationId
from ....domain.calculations.registry.relations import relation_prefill_bindings_for_period
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.user_profile.tests.general_regime_facts import (
    RENTA_UNMARRIED_TAXPAYER_FACTS,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.aeat_literal_fixtures import aeat_url, configured_path
from .file_flow_test_support import calculation_ports_for_test

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_YEAR = 2025
_PERIOD = "0A"
_DECIMAL_BINDING: BindingId = "renta-retencion-soportada-trabajo"
_ENUM_BINDING: BindingId = "renta-profile-tax-residence-ccaa"
_R210_SIMULATOR_URL = aeat_url("www2", configured_path("sede_paths", "r210_simulator_open_ajax"))


def _modelo_100_registry_snapshot() -> RegistrySnapshot:
    return published_authority_operation().snapshot("100", filing_year=_YEAR, period=_PERIOD)


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
        if binding.id not in exclusions
        and binding.source != "profile"
        and binding.source not in BUCKET_AGGREGATION_LOCK_SOURCES
        and binding.provider.kind != "retencion_soportada"
    }


def _zero_relation_values() -> dict[RelationId, Decimal]:
    """Zero every relation that does not feed the casilla the borrador holds.

    Relations share their binding's identity, and equivalent bindings of one
    casilla must agree, so a zero filler there would stand in for the credit.
    """
    revision = _modelo_100_registry_snapshot().revision
    targets = casillas_by_binding(revision)
    borrador_casillas = set(targets.get(_DECIMAL_BINDING, ()))
    return {
        binding.id: Decimal("0")
        for binding, _ in relation_prefill_bindings_for_period(revision)
        if not borrador_casillas.intersection(targets.get(binding.id, ()))
    }


def _seed_profile_with_birth_date(objects: SecureObjectRepository) -> None:
    """Persist the profile facts required by the live calculation adapter path."""
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=persona_facts_beneath(
                (
                    UserProfileFact(path="identity.tax_id", value="12345678Z"),
                    UserProfileFact(path="identity.name", value="Test"),
                    UserProfileFact(path="identity.surnames", value="Operator"),
                    UserProfileFact(path="activities.description", value="economic activity"),
                    *RENTA_UNMARRIED_TAXPAYER_FACTS,
                )
            ),
            created_at=datetime(2026, 4, 1, tzinfo=UTC),
            updated_at=datetime(2026, 4, 1, tzinfo=UTC),
            context=profile_creation_context_for_test(),
        ),
    )


def _seed_work_unit_and_borrador_snapshot(
    objects: SecureObjectRepository,
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
    snapshot_repository: Borrador100SnapshotRepository,
    operation: PinnedAuthorityOperation,
) -> tuple[str, str]:
    """Seed the profile, create the 2025 renta work unit and save a snapshot sourcing both bindings."""
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
        operation=operation,
    )
    snapshot_id = _save_snapshot(
        snapshot_repository,
        {
            _DECIMAL_BINDING: Decimal("125.50"),
            _ENUM_BINDING: "madrid",
        },
    )
    return work_unit.work_unit_id, snapshot_id


def test_calculate_modelo_revision_consumes_borrador_snapshot_through_application_service(
    service_repositories: tuple[
        WorkUnitCatalogueRepository,
        CalculationRevisionCatalogueRepository,
        BucketEventHistoryRepository,
        Borrador100SnapshotRepository,
        SecureObjectRepository,
    ],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository, bucket_event_repository, snapshot_repository, objects = (
        service_repositories
    )
    work_unit_id, snapshot_id = _seed_work_unit_and_borrador_snapshot(
        objects,
        work_unit_repository=work_unit_repository,
        bucket_event_repository=bucket_event_repository,
        snapshot_repository=snapshot_repository,
        operation=operation,
    )

    relation_values = _zero_relation_values()
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=snapshot_repository,
    ) as _calculation_ports_221:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            actor="operator-A",
            casilla_inputs={},
            binding_values=_non_borrador_decimal_binding_values(),
            enum_binding_values={},
            borrador_snapshot_id=snapshot_id,
            relation_values=relation_values,
            ports=_calculation_ports_221,
        ).revision

    # The borrador's 125,50 is held for comparison only: it never becomes the credit.
    # The credit's owner, the payer records, holds none for this profile, so it is zero.
    assert Decimal(revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("0")
    assert Decimal(revision.casilla_values["0596"]) == Decimal("0")
    assert revision.binding_overrides[_ENUM_BINDING] == "madrid"
    # A relation shares its binding's identity, so each id is persisted on one
    # channel only; the relation channel keeps the ids no binding supplied.
    assert set(revision.relation_overrides) == set(relation_values) - set(revision.binding_overrides)
    assert all(Decimal(value) == Decimal("0") for value in revision.relation_overrides.values())
    assert set(revision.binding_overrides).isdisjoint(revision.relation_overrides)
    assert revision.borrador_snapshot_id == snapshot_id
    assert revision.bindings_sourced_from_borrador == (_ENUM_BINDING,)
    fresh_calculation_repository = CalculationRevisionCatalogueRepository(objects=objects)
    stored_revision = fresh_calculation_repository.load().get(revision.calculation_revision_id)
    assert stored_revision == revision
    assert stored_revision is not None
    assert stored_revision.borrador_snapshot_id == snapshot_id
    assert stored_revision.bindings_sourced_from_borrador == (_ENUM_BINDING,)
    assert stored_revision.binding_overrides[_DECIMAL_BINDING] == revision.binding_overrides[_DECIMAL_BINDING]
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
    assert event.payload["borrador_binding_count"] == "1"
    assert event.payload["borrador_bindings_trace_sha256"] == hashlib.sha256(_ENUM_BINDING.encode("utf-8")).hexdigest()


def test_calculate_modelo_revision_precedence_keeps_caller_above_borrador_and_the_credit_with_its_backend(
    service_repositories: tuple[
        WorkUnitCatalogueRepository,
        CalculationRevisionCatalogueRepository,
        BucketEventHistoryRepository,
        Borrador100SnapshotRepository,
        SecureObjectRepository,
    ],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_unit_repository, calculation_repository, bucket_event_repository, snapshot_repository, objects = (
        service_repositories
    )
    work_unit_id, snapshot_id = _seed_work_unit_and_borrador_snapshot(
        objects,
        work_unit_repository=work_unit_repository,
        bucket_event_repository=bucket_event_repository,
        snapshot_repository=snapshot_repository,
        operation=operation,
    )
    # The payer's certificate is the backend source of the work-income credit.
    seed_payer_certificate(
        operation=operation,
        taxpayer_tax_id="12345678Z",
        ejercicio=_YEAR,
        payer_tax_id="B00015016",
        income_class=RetencionSoportadaClase.TRABAJO,
        retencion=Decimal("1.00"),
    )
    with calculation_ports_for_test(
        bucket_id=_BUCKET_ID,
        work_unit_repository=work_unit_repository,
        calculation_repository=calculation_repository,
        bucket_event_repository=bucket_event_repository,
        borrador_snapshot_repository=snapshot_repository,
    ) as _calculation_ports_303:
        revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit_id,
            actor="operator-A",
            casilla_inputs={},
            binding_values=_non_borrador_decimal_binding_values(),
            enum_binding_values={_ENUM_BINDING: "cataluna"},
            borrador_snapshot_id=snapshot_id,
            relation_values=_zero_relation_values(),
            ports=_calculation_ports_303,
        ).revision

    # The backend's credit stands; the borrador's differing 125,50 does not replace it.
    assert Decimal(revision.binding_overrides[_DECIMAL_BINDING]) == Decimal("1.00")
    assert Decimal(revision.casilla_values["0596"]) == Decimal("1.00")
    assert revision.binding_overrides[_ENUM_BINDING] == "cataluna"
    assert revision.bindings_sourced_from_borrador == ()
