"""Official and pending-local observation layers, and audited operator overrides.

Each ``(modelo, filing_year, period[, member])`` coordinate stores two layers
over real encrypted storage: AEAT evidence and a pending local answer. These
tests pin that a local write never destroys AEAT evidence, that readers see the
pending layer while it exists, and that operator overrides are recorded, audited
and cleared through their events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.entrypoints.tests.profile_persistence.import_flow_support import seed_ready_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.calculations.observations_repository import ObservationOverride, ObservationSourceKind
from cadrumo.application.modelo.action_errors import ModeloLocalObservationError
from cadrumo.application.modelo.local_observation_actions import (
    LocalObservationPorts,
    clear_operator_local_observation,
    record_operator_local_observation,
)
from cadrumo.application.modelo.work_lifecycle import create_work_unit
from cadrumo.application.modelo.work_lifecycle_ports import WorkLifecyclePorts
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from cadrumo.domain.calculations.registry.tests.registry_observations import revision_id_for_observation

if TYPE_CHECKING:
    from pathlib import Path

    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CAPTURED_AT = datetime(2026, 4, 1, 9, 30, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "1T")
_CASILLA = validated_casilla_id("19")
_OFFICIAL_METADATA = {"aeat_register_status": "ALTA", "aeat_expediente_id": "202513000000001Z"}


def _observation(value: str) -> RegistryModeloObservation:
    return RegistryModeloObservation(
        modelo="130",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id=_CASILLA,
                value=Decimal(value),
                formula_id=None,
                operand_refs=(),
                operand_casilla_refs=(),
                operand_values=(),
                legal_refs=("ley-35-2006:art-99",),
                source_refs=("boe-modelo-130-2025-form",),
            ),
        ),
    )


def _save(repo: CalculationObservationRepository, value: str, *, source_kind: str, offset: int = 0) -> None:
    observation = _observation(value)
    repo.save(
        repo.prepare_observation_envelope(
            observation,
            source_kind=source_kind,
            captured_at=_CAPTURED_AT + timedelta(hours=offset),
            source_metadata=_OFFICIAL_METADATA if source_kind.startswith("aeat_") else {},
            stamped_revision_id=revision_id_for_observation(observation),
        )
    )


def _ports(bucket_id: str, repo: CalculationObservationRepository) -> LocalObservationPorts:
    return LocalObservationPorts(
        bucket_id=bucket_id,
        observation_repository=repo,
        bucket_event_repository=BucketEventHistoryRepository(),
        work_unit_repository=WorkUnitCatalogueRepository(),
    )


@pytest.mark.parametrize("local_kind", ["operator_manual", "app_filing"])
def test_a_local_write_sits_above_aeat_evidence_without_destroying_it(tmp_path: Path, local_kind: str) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        _save(repo, "250.00", source_kind="aeat_sede_justificante")
        _save(repo, "300.00", source_kind=local_kind, offset=1)

        layers = repo.load_observation_layers("130", _PERIOD)
        assert layers.official is not None and layers.pending_local is not None
        assert layers.official.observation.casilla_values[_CASILLA] == Decimal("250.00")
        assert dict(layers.official.source_metadata)["aeat_expediente_id"] == "202513000000001Z"
        assert layers.effective == layers.pending_local

        effective = repo.load_observation("130", _PERIOD)
        assert effective is not None and effective.source_kind == local_kind
        assert [row.source_kind for row in repo.iter_modelo("130")] == [local_kind]


def test_an_official_write_keeps_a_pending_local_answer_effective(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        _save(repo, "300.00", source_kind="app_filing")
        _save(repo, "250.00", source_kind="aeat_sede_justificante", offset=1)

        layers = repo.load_observation_layers("130", _PERIOD)
        assert layers.official is not None
        assert layers.effective is not None and layers.effective.source_kind == ObservationSourceKind.APP_FILING


def test_an_unwritten_coordinate_has_no_layers(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        layers = CalculationObservationRepository().load_observation_layers("130", _PERIOD)
        assert (layers.official, layers.pending_local, layers.effective) == (None, None, None)


def test_promoting_the_pending_layer_makes_it_official(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        _save(repo, "300.00", source_kind="app_filing")

        writes = repo.promote_pending_local(
            "130",
            _PERIOD,
            source_kind=ObservationSourceKind.AEAT_CSV_REGISTER,
            source_metadata={"aeat_expediente_id": "EXP-1"},
            captured_at=_CAPTURED_AT + timedelta(days=1),
        )
        profile.repository.apply_batch(writes)

        layers = repo.load_observation_layers("130", _PERIOD)
        assert layers.pending_local is None
        assert layers.official is not None
        assert layers.official.source_kind is ObservationSourceKind.AEAT_CSV_REGISTER
        assert layers.official.observation.casilla_values[_CASILLA] == Decimal("300.00")
        assert dict(layers.official.source_metadata) == {"aeat_expediente_id": "EXP-1"}


def test_clearing_the_pending_layer_restores_the_official_answer(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        _save(repo, "250.00", source_kind="aeat_sede_justificante")
        _save(repo, "300.00", source_kind="app_filing", offset=1)

        profile.repository.apply_batch(repo.clear_pending_local("130", _PERIOD))

        effective = repo.load_observation("130", _PERIOD)
        assert effective is not None and effective.source_kind == ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
        assert repo.clear_pending_local("130", _PERIOD) == ()


def test_an_official_envelope_refuses_an_operator_override(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        observation = _observation("1.00")
        with pytest.raises(ValueError, match="cannot carry an operator override"):
            repo.prepare_observation_envelope(
                observation,
                source_kind="aeat_csv_register",
                stamped_revision_id=revision_id_for_observation(observation),
                override=ObservationOverride(actor="operator-A", reason="typo", recorded_at=_CAPTURED_AT),
            )


def test_an_override_is_audited_evented_and_cleared(tmp_path: Path, operation: PinnedAuthorityOperation) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        seed_ready_profile(bucket_id=profile.bucket_id)
        repo = CalculationObservationRepository()
        ports = _ports(profile.bucket_id, repo)
        work_unit = create_work_unit(
            bucket_id=profile.bucket_id,
            modelo="130",
            filing_year=2025,
            period=_PERIOD,
            revision_id="2019-y-siguientes",
            ports=WorkLifecyclePorts(
                work_unit_repository=ports.work_unit_repository,
                bucket_event_repository=ports.bucket_event_repository,
            ),
            clock=_CAPTURED_AT,
            operation=operation,
        )
        _save(repo, "250.00", source_kind="aeat_sede_justificante")

        recorded = record_operator_local_observation(
            modelo="130",
            filing_year=2025,
            period=_PERIOD,
            casilla_values={_CASILLA: Decimal("275.00")},
            reason="AEAT figure misread from the receipt",
            actor="operator-A",
            ports=ports,
            operation=operation,
            clock=_CAPTURED_AT + timedelta(days=1),
        )

        assert recorded.override.replaced_source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
        assert recorded.override.replaced_values == {_CASILLA: "250.00"}
        layers = repo.load_observation_layers("130", _PERIOD)
        assert layers.pending_local is not None and layers.pending_local.override == recorded.override
        assert layers.official is not None
        assert layers.official.observation.casilla_values[_CASILLA] == Decimal("250.00")

        cleared = clear_operator_local_observation(
            "130",
            2025,
            _PERIOD,
            reason="receipt re-read",
            actor="operator-B",
            ports=ports,
            clock=_CAPTURED_AT + timedelta(days=2),
        )

        assert cleared.cleared_override == recorded.override
        assert cleared.effective_source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
        assert repo.load_observation_layers("130", _PERIOD).pending_local is None
        events = {
            event.event_type: event
            for event in ports.bucket_event_repository.load().events.values()
            if event.event_type
            in {BucketEventType.MODELO_OBSERVATION_OVERRIDDEN, BucketEventType.MODELO_OBSERVATION_OVERRIDE_CLEARED}
        }
        assert set(events) == {
            BucketEventType.MODELO_OBSERVATION_OVERRIDDEN,
            BucketEventType.MODELO_OBSERVATION_OVERRIDE_CLEARED,
        }
        for event in events.values():
            assert event.payload["work_unit_id"] == work_unit.work_unit_id
            assert (event.payload["modelo"], event.payload["filing_year"], event.payload["period"]) == (
                "130",
                "2025",
                "1T",
            )
        assert events[BucketEventType.MODELO_OBSERVATION_OVERRIDDEN].payload["reason"] == (
            "AEAT figure misread from the receipt"
        )
        assert events[BucketEventType.MODELO_OBSERVATION_OVERRIDE_CLEARED].actor == "operator-B"


def test_clearing_without_an_override_is_refused(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        _save(repo, "300.00", source_kind="app_filing")

        with pytest.raises(ModeloLocalObservationError) as refusal:
            clear_operator_local_observation(
                "130",
                2025,
                _PERIOD,
                reason="nothing to clear",
                actor="operator-A",
                ports=_ports(profile.bucket_id, repo),
            )

        assert refusal.value.translated_message == "application.modelo.errors.local_observation_override_missing"
        assert repo.load_observation_layers("130", _PERIOD).pending_local is not None


@pytest.mark.parametrize(("actor", "reason", "key"), [(" ", "why", "actor_blank"), ("operator-A", " ", "reason_blank")])
def test_an_override_requires_an_actor_and_a_reason(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    actor: str,
    reason: str,
    key: str,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repo = CalculationObservationRepository()
        with pytest.raises(ModeloLocalObservationError) as refusal:
            record_operator_local_observation(
                modelo="130",
                filing_year=2025,
                period=_PERIOD,
                casilla_values={_CASILLA: Decimal("1.00")},
                reason=reason,
                actor=actor,
                ports=_ports(profile.bucket_id, repo),
                operation=operation,
            )

        assert refusal.value.translated_message == f"application.modelo.errors.local_observation_{key}"
        assert repo.load_observation_layers("130", _PERIOD).effective is None
