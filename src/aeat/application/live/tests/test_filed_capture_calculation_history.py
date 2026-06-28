"""Filed AEAT observations feed the calculation history repository."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    ObservedCasillaValue,
)
from ....adapters.outbound.aeat.sede._declarations import (
    _observed_casillas_from_submitted_file,  # pyright: ignore[reportPrivateUsage]
)
from ....core import Period
from ....core.external_constants import load_external_constants
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository, BucketEventType
from ....domain.calculations.registry import (
    CasillaId,
    RegistryModeloObservation,
    RegistryValidationError,
    validated_casilla_id,
)
from ....domain.iva_compensation._carry_forward import IvaCompensationPeriodState
from ....domain.justificante import JustificanteRepository
from ....domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
    ModeloRecord,
    ModeloRecordCatalogueRepository,
    ModeloRecordStatus,
    derive_filing_record_id,
    upsert_filing_record,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._repository import WorkUnitCatalogueRepository, upsert_work_unit
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests import FIXTURES_DIR
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ...calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from ...user_profile._orchestration import profile_create_storage_span
from ...user_profile._testing import register_minimal_profile
from ...workflow._persistence import workflow_state_repository
from .. import (
    _latest_declarations_by_period,
    _persist_iva_compensation_history_observations_strict,
    _persist_latest_filed_calculation_observations,
    enroll_filed_justificante_evidence,
    list_iva_compensation_history,
    load_iva_remote_state,
    persist_filed_calculation_observation,
    persist_filed_justificante_metadata,
)
from .._errors import LiveApplicationInputError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CAPTURED_AT = datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC)
_SYNTHETIC_PROFILE_ID = "SYNTHETIC_PROFILE"
_SYNTHETIC_EXPEDIENTE_ID = "200030300000000Z"
_BUCKET_ID = "operator"
_SESSION_BUCKET_ID = "ephemeral"


def _casilla_id(value: object) -> CasillaId:
    return validated_casilla_id(value, surface="test casilla id")


_M303_DISPONIBLE_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = _casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
)
_M303_POSTERIOR_CASILLA: CasillaId = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")
_M303_APLICADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-aplicada-periodo")
_M303_RESULTADO_FINAL_CASILLA: CasillaId = _casilla_id("71")


@contextmanager
def _secure_backend(tmp_path: Path):
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_SESSION_BUCKET_ID) as profile:
        yield profile.paths.db_dir / "aeat.db"


@contextmanager
def _profile_backend(tmp_path: Path, *, tax_id: str):
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(
                state,
                profile_id="operator",
                overrides={"identity.tax_id": tax_id},
            ),
        )
        bucket_id = workflow_state_repository().load().active_profile_bucket_id()
        assert bucket_id is not None
        yield bucket_id


def test_filed_observation_capture_promotes_previous_303_into_recurrence_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            _prior_303_observation(pending_compensation=Decimal("1200.00")),
            repository=repository,
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
        prefill = resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)
        recurrence, recurrence_prefill = extract_modelo_303_local_iva_compensation_recurrence(
            target_snapshot,
            repository=repository,
            captured_at=_CAPTURED_AT,
        )

        assert calculation_key == "303:2026:1T"
        assert repository.load_observation("303", Period.from_year_and_code(2026, "1T")) is not None
        loaded = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))
        assert loaded is not None
        assert loaded.source_metadata == {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": _SYNTHETIC_EXPEDIENTE_ID,
            "authenticated_identity": _SYNTHETIC_PROFILE_ID,
        }
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}
        assert prefill.prefilled[0].source_modelo == "303"
        assert prefill.prefilled[0].source_periods == ("1T",)
        assert recurrence is not None
        assert recurrence.amount == Decimal("1200.00")
        assert recurrence.source_periods == (Period.from_year_and_code(2026, "1T"),)
        assert recurrence_prefill.binding_values == prefill.binding_values


def test_filed_observation_capture_records_single_justificante_csv_metadata(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        observation = _prior_303_observation(pending_compensation=Decimal("1200.00"))

        persist_filed_calculation_observation(
            observation,
            repository=repository,
            justificante_csvs=("CSV30320261T",),
        )

        loaded = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))

    assert loaded is not None
    assert loaded.source_metadata == {
        "aeat_register_status": "ALTA",
        "aeat_expediente_id": _SYNTHETIC_EXPEDIENTE_ID,
        "authenticated_identity": _SYNTHETIC_PROFILE_ID,
        "aeat_justificante_csv": "CSV30320261T",
    }


def test_latest_filed_observation_capture_threads_justificante_csv_metadata(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        observation = _prior_303_observation(pending_compensation=Decimal("1200.00"))

        keys = _persist_latest_filed_calculation_observations(
            (observation,),
            justificante_csvs_by_observation={
                ("303", 2026, "1T", _SYNTHETIC_EXPEDIENTE_ID): ("CSV30320261T",),
            },
        )
        loaded = CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T"))

    assert keys == ("303:2026:1T",)
    assert loaded is not None
    assert loaded.source_metadata["aeat_justificante_csv"] == "CSV30320261T"


def test_filed_observation_capture_promotes_cross_year_303_recurrence_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            _prior_303_observation(
                year=2025,
                period="4T",
                pending_compensation=Decimal("450.00"),
                expediente_id="200030300000001Z",
            ),
            repository=repository,
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="1T")
        prefill = resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)

        assert calculation_key == "303:2025:4T"
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}
        assert prefill.prefilled[0].source_filing_year == 2025
        assert prefill.prefilled[0].source_periods == ("4T",)


def test_binding_prefill_uses_profile_secure_iva_compensation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        history_repository = IvaCompensationHistoryRepository()
        history_repository.save_period(
            IvaCompensationPeriodState(
                taxpayer_nif=_SYNTHETIC_PROFILE_ID,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                expediente_id=_SYNTHETIC_EXPEDIENTE_ID,
                status="ALTA",
                presented_at=_CAPTURED_AT,
                prior_pending_amount=Decimal("2.34"),
                applied_amount=Decimal("1.23"),
                pending_for_later_amount=Decimal("8.90"),
                period_result_amount=Decimal("-4.32"),
                final_result_amount=Decimal("-4.32"),
                generated_amount=Decimal("4.32"),
                available_end_amount=Decimal("13.22"),
                source_observation_key=f"303:2026:1T:{_SYNTHETIC_EXPEDIENTE_ID}",
                source_artefact_sha256=hashlib.sha256(b"synthetic-submitted-file").hexdigest(),
            ),
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")
        prefill = resolve_bindings_from_local_store(
            target_snapshot,
            repository=repository,
            iva_history_repository=history_repository,
            captured_at=_CAPTURED_AT,
        )

        assert repository.load_observation("303", Period.from_year_and_code(2026, "1T")) is None
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("13.22")}
        assert prefill.prefilled[0].source_modelo == "303"
        assert prefill.prefilled[0].source_filing_year == 2026
        assert prefill.prefilled[0].source_periods == ("1T",)


def test_iva_compensation_history_strict_persist_stores_latest_and_reloads(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        keys = _persist_iva_compensation_history_observations_strict(
            (
                _prior_303_observation(
                    pending_compensation=Decimal("1.00"),
                    expediente_id="200030300000004Z",
                    presented_at=datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC),
                ),
                _prior_303_observation(
                    pending_compensation=Decimal("2.00"),
                    expediente_id="200030300000005Z",
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
            ),
        )

        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert keys == ("303:2026:1T",)
        assert history is not None
        assert history.expediente_id == "200030300000005Z"
        assert history.pending_for_later_amount == Decimal("2.00")


def test_direct_filed_observation_persist_refuses_non_alta_status(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        with pytest.raises(LiveApplicationInputError, match="non-active AEAT filed observation"):
            persist_filed_calculation_observation(
                _prior_303_observation(
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
            )

        assert CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T")) is None
        assert IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T")) is None


def test_filed_observation_capture_enrolls_matching_justificante_metadata(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)

        csvs = persist_filed_justificante_metadata(observation, store=store)

        assert csvs == ("ABCD1234EFGH5678",)
        loaded = JustificanteRepository().load("ABCD1234EFGH5678")
        assert loaded is not None
        assert loaded.modelo == "130"
        assert loaded.period == Period.from_year_and_code(2026, "1T")
        assert loaded.tax_id == "00000000T"


_REFUSED_JUSTIFICANTE_METADATA_CASES = (
    pytest.param("X1234567L", "13020260410ABCD1234EFGH5678", id="wrong-taxpayer"),
    pytest.param("00000000T", "13020260410ZZZZ1234EFGH5678", id="mismatched-presentation-id"),
)


@pytest.mark.parametrize(("authenticated_identity", "expediente_id"), _REFUSED_JUSTIFICANTE_METADATA_CASES)
def test_filed_observation_capture_refuses_invalid_justificante_metadata(
    tmp_path: Path,
    authenticated_identity: str,
    expediente_id: str,
) -> None:
    with _secure_backend(tmp_path):
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(
            store,
            authenticated_identity=authenticated_identity,
            expediente_id=expediente_id,
        )

        csvs = persist_filed_justificante_metadata(observation, store=store)

        assert csvs == ()
        assert JustificanteRepository().load("ABCD1234EFGH5678") is None


def test_filed_observation_capture_stamps_matching_current_filing_record(tmp_path: Path) -> None:
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)
        filing = _seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

        assert result.justificante_csvs == ("ABCD1234EFGH5678",)
        assert result.filing_record_ids == (filing.filing_record_id,)
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )
        assert current is not None
        assert current.aeat_accepted is True
        assert current.external_evidence is not None
        assert current.external_evidence.kind is ExternalEvidenceKind.AEAT_LIVE_CAPTURE
        assert current.external_evidence.reference_id == "ABCD1234EFGH5678"
        events = [
            event
            for event in BucketEventHistoryRepository().load().events.values()
            if event.event_type is BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED
        ]
        assert len(events) == 1
        assert events[0].bucket_id == bucket_id
        assert events[0].actor == "aeat-filed-history"
        assert events[0].object_id == filing.filing_record_id
        assert events[0].payload["evidence_reference_id"] == "ABCD1234EFGH5678"
        assert events[0].payload["expediente_id"] == observation.expediente_id


def test_filed_observation_capture_rejects_mismatched_presentation_id_before_stamping(
    tmp_path: Path,
) -> None:
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store, expediente_id="13020260410ZZZZ1234EFGH5678")
        _seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )

    assert result.justificante_csvs == ()
    assert result.filing_record_ids == ()
    assert result.conflicting_filing_record_ids == ()
    assert current is not None
    assert current.external_evidence is None
    assert current.aeat_accepted is False


def test_filed_observation_capture_keeps_existing_justificante_pdf_evidence_for_same_csv(tmp_path: Path) -> None:
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)
        filing = _seed_current_130_filing(
            bucket_id=bucket_id,
            aeat_accepted=True,
            external_evidence=ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                reference_id="ABCD1234EFGH5678",
                imported_at=_CAPTURED_AT,
            ),
        )

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

        assert result.filing_record_ids == (filing.filing_record_id,)
        assert result.conflicting_filing_record_ids == ()
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )
        assert current is not None
        assert current.external_evidence is not None
        assert current.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
        assert current.external_evidence.reference_id == "ABCD1234EFGH5678"
        events = [
            event
            for event in BucketEventHistoryRepository().load().events.values()
            if event.event_type is BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED
        ]
        assert events == []


def test_filed_observation_capture_keeps_existing_csv_register_evidence_for_same_csv_case_insensitive(
    tmp_path: Path,
) -> None:
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)
        filing = _seed_current_130_filing(
            bucket_id=bucket_id,
            aeat_accepted=True,
            external_evidence=ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                reference_id="abcd1234efgh5678",
                imported_at=_CAPTURED_AT,
            ),
        )

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

        assert result.filing_record_ids == (filing.filing_record_id,)
        assert result.conflicting_filing_record_ids == ()
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )
        assert current is not None
        assert current.external_evidence is not None
        assert current.external_evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER
        assert current.external_evidence.reference_id == "abcd1234efgh5678"
        events = [
            event
            for event in BucketEventHistoryRepository().load().events.values()
            if event.event_type is BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED
        ]
        assert events == []


def test_filed_observation_capture_reports_existing_evidence_conflict_without_overwrite(tmp_path: Path) -> None:
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)
        filing = _seed_current_130_filing(
            bucket_id=bucket_id,
            aeat_accepted=True,
            external_evidence=ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                reference_id="DIFFERENTCSV12345",
                imported_at=_CAPTURED_AT,
            ),
        )

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

        assert result.filing_record_ids == ()
        assert result.conflicting_filing_record_ids == (filing.filing_record_id,)
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )
        assert current is not None
        assert current.external_evidence is not None
        assert current.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
        assert current.external_evidence.reference_id == "DIFFERENTCSV12345"
        events = [
            event
            for event in BucketEventHistoryRepository().load().events.values()
            if event.event_type is BucketEventType.MODELO_LIVE_EVIDENCE_STAMPED
        ]
        assert events == []


def test_filed_observation_capture_does_not_stamp_current_filing_for_wrong_profile_taxpayer(tmp_path: Path) -> None:
    with _profile_backend(tmp_path, tax_id="X1234567L") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)
        _seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

        assert result.justificante_csvs == ("ABCD1234EFGH5678",)
        assert result.filing_record_ids == ()
        current = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="130",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )
        assert current is not None
        assert current.aeat_accepted is False
        assert current.external_evidence is None


def test_iva_history_capture_selects_latest_alta_declaration_per_period() -> None:
    selected = _latest_declarations_by_period(
        (
            _declaration(
                period="1T",
                expediente_id="200030300000006Z",
                estado="BAJA",
                presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
            ),
            _declaration(
                period="1T",
                expediente_id="200030300000007Z",
                estado="ALTA",
                presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            ),
            _declaration(
                period="2T",
                expediente_id="200030300000008Z",
                estado="ALTA",
                presented_at=datetime(2026, 7, 20, 10, 0, 0, tzinfo=UTC),
            ),
        ),
    )

    assert tuple(row.period for row in selected) == (
        Period.from_year_and_code(2026, "1T"),
        Period.from_year_and_code(2026, "2T"),
    )
    assert selected[0].expediente_id == "200030300000007Z"
    assert selected[1].expediente_id == "200030300000008Z"


def test_duplicate_period_capture_promotes_alta_over_later_non_alta_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        keys = _persist_latest_filed_calculation_observations(
            (
                _prior_303_observation(
                    expediente_id="200030300000012Z",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
                _prior_303_observation(
                    expediente_id="200030300000013Z",
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
            ),
        )

        stored = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))
        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert keys == ("303:2026:1T",)
        assert stored is not None
        assert stored.observation.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("1200.00")
        assert history is not None
        assert history.expediente_id == "200030300000012Z"


def test_iva_history_strict_persist_promotes_alta_over_later_non_alta_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        keys = _persist_iva_compensation_history_observations_strict(
            (
                _prior_303_observation(
                    expediente_id="200030300000014Z",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
                _prior_303_observation(
                    expediente_id="200030300000015Z",
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
            ),
        )

        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert keys == ("303:2026:1T",)
        assert history is not None
        assert history.expediente_id == "200030300000014Z"
        assert history.pending_for_later_amount == Decimal("1200.00")


def test_iva_history_strict_persist_skips_non_alta_only_period(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        keys = _persist_iva_compensation_history_observations_strict(
            (
                _prior_303_observation(
                    expediente_id="200030300000016Z",
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
            ),
        )

        assert keys == ()
        assert IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T")) is None
        assert CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T")) is None


def test_duplicate_period_capture_promotes_latest_filing_to_calculation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        _persist_latest_filed_calculation_observations(
            (
                _prior_303_observation(
                    expediente_id="200030300000002Z",
                    pending_compensation=Decimal("800.00"),
                    presented_at=datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC),
                ),
                _prior_303_observation(
                    expediente_id="200030300000003Z",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
            ),
        )

        stored = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))

        assert stored is not None
        assert stored.observation.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("1200.00")


def test_filed_303_capture_persists_secure_iva_compensation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path) as db_path:
        prior_pending = Decimal("19.99")
        applied = Decimal("3.21")
        pending_later = Decimal("7.89")
        period_result = Decimal("-4.56")
        final_result = Decimal("-4.56")
        key = persist_filed_calculation_observation(
            _prior_303_observation(
                pending_compensation=pending_later,
                prior_pending=prior_pending,
                applied=applied,
                result=period_result,
                final_result=final_result,
                expediente_id=_SYNTHETIC_EXPEDIENTE_ID,
            ),
        )

        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert key == "303:2026:1T"
        assert history is not None
        assert history.taxpayer_nif == _SYNTHETIC_PROFILE_ID
        assert history.expediente_id == _SYNTHETIC_EXPEDIENTE_ID
        assert history.prior_pending_amount == prior_pending
        assert history.applied_amount == applied
        assert history.pending_for_later_amount == pending_later
        assert history.period_result_amount == period_result
        assert history.final_result_amount == final_result
        assert history.source_artefact_sha256 == hashlib.sha256(b"303-2026-1T-submitted-file").hexdigest()
        assert history.source_observation_key == f"303:2026:1T:{_SYNTHETIC_EXPEDIENTE_ID}"

        listed = list_iva_compensation_history()
        assert listed.row_count == 1
        assert not hasattr(listed.rows[0], "taxpayer_nif")

        database_bytes = db_path.read_bytes()
        assert _SYNTHETIC_PROFILE_ID.encode("utf-8") not in database_bytes
        assert _SYNTHETIC_EXPEDIENTE_ID.encode("utf-8") not in database_bytes


def test_filed_303_capture_accepts_canonical_compensation_casilla_ids(tmp_path: Path) -> None:
    pending_compensation = Decimal("11.00")
    prior_pending = Decimal("15.00")
    applied = Decimal("4.00")
    period_result = Decimal("-2.50")
    generated = Decimal("2.50")
    expected_available_end = pending_compensation + generated
    with _secure_backend(tmp_path):
        key = persist_filed_calculation_observation(
            _prior_303_observation(
                pending_compensation=pending_compensation,
                prior_pending=prior_pending,
                applied=applied,
                result=period_result,
                final_result=period_result,
                generated=generated,
            ),
        )

        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))
        stored = CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T"))

        assert key == "303:2026:1T"
        assert history is not None
        assert history.prior_pending_amount == prior_pending
        assert history.applied_amount == applied
        assert history.pending_for_later_amount == pending_compensation
        assert history.period_result_amount == period_result
        assert history.available_end_amount == expected_available_end
        assert stored is not None
        assert stored.observation.casilla_values[_M303_DISPONIBLE_CASILLA] == expected_available_end
        available = next(
            item for item in stored.observation.observations if item.casilla_id == _M303_DISPONIBLE_CASILLA
        )
        assert available.formula_id == "modelo-303-compensacion-disponible-fin-periodo"
        assert available.operand_casilla_refs == (_M303_POSTERIOR_CASILLA, _M303_GENERADA_CASILLA)
        assert available.operand_values == (pending_compensation, generated)


def test_multiyear_303_submitted_file_parser_promotes_sanitized_iva_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        observations = (
            _parsed_303_submitted_file_observation(
                year=2025,
                period="4T",
                expediente_id="200030300000009Z",
                presented_at=datetime(2026, 1, 20, 10, 0, 0, tzinfo=UTC),
                casilla_110="00000000000000000",
                casilla_78="00000000000000000",
                casilla_87="00000000000000000",
                casilla_69="N0000000000010000",
                casilla_71="N0000000000010000",
            ),
            _parsed_303_submitted_file_observation(
                year=2026,
                period="1T",
                expediente_id="200030300000010Z",
                presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                casilla_110="00000000000010000",
                casilla_78="00000000000003000",
                casilla_87="00000000000012000",
                casilla_69="N0000000000005000",
                casilla_71="N0000000000005000",
            ),
            _parsed_303_submitted_file_observation(
                year=2026,
                period="2T",
                expediente_id="200030300000011Z",
                presented_at=datetime(2026, 7, 20, 10, 0, 0, tzinfo=UTC),
                casilla_110="00000000000017000",
                casilla_78="00000000000002000",
                casilla_87="00000000000010000",
                casilla_69="00000000000002500",
                casilla_71="00000000000002500",
            ),
        )

        keys = _persist_iva_compensation_history_observations_strict(observations)
        history = list_iva_compensation_history(as_of_year=2026)
        remote_state = load_iva_remote_state(as_of_year=2026)

        rows_by_period = {(row.year, row.period): row for row in history.rows}
        lots_by_period = {(lot.source_filing_year, lot.source_period): lot for lot in history.carry_forward_lots}

        assert keys == ("303:2025:4T", "303:2026:1T", "303:2026:2T")
        assert history.row_count == 3
        period_2025_4t = Period.from_year_and_code(2025, "4T")
        period_2026_1t = Period.from_year_and_code(2026, "1T")
        period_2026_2t = Period.from_year_and_code(2026, "2T")
        assert set(rows_by_period) == {
            (2025, period_2025_4t),
            (2026, period_2026_1t),
            (2026, period_2026_2t),
        }
        assert Decimal(rows_by_period[(2025, period_2025_4t)].generated_amount) == Decimal("100.00")
        assert Decimal(rows_by_period[(2026, period_2026_1t)].generated_amount) == Decimal("50.00")
        assert Decimal(rows_by_period[(2026, period_2026_2t)].generated_amount) == Decimal("0")
        assert Decimal(rows_by_period[(2026, period_2026_2t)].available_end_amount) == Decimal("100.00")
        assert history.carry_forward_lot_count == 2
        assert Decimal(lots_by_period[(2025, period_2025_4t)].remaining_amount) == Decimal("50.00")
        assert Decimal(lots_by_period[(2026, period_2026_1t)].remaining_amount) == Decimal("50.00")
        assert Decimal(history.unallocated_applied_amount) == Decimal("0")
        assert remote_state.history.row_count == history.row_count
        assert remote_state.history.carry_forward_lot_count == history.carry_forward_lot_count


def test_binding_prefill_refuses_incomplete_prior_filing_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        repository.save_observation(
            RegistryModeloObservation(
                modelo="303",
                filing_year=2026,
                period="1T",
                observations=registry_grounded_observations(
                    modelo="303",
                    filing_year=2026,
                    period="1T",
                    casilla_values={_M303_POSTERIOR_CASILLA: Decimal("1200.00")},
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_CAPTURED_AT,
        )

        target_snapshot = resources().modelos.authority.snapshot("303", filing_year=2026, period="2T")

        with pytest.raises(RegistryValidationError, match=r"iva\.compensacion-disponible-fin-periodo"):
            resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)


def _parsed_303_submitted_file_observation(
    *,
    year: int,
    period: str,
    expediente_id: str,
    presented_at: datetime,
    casilla_110: str,
    casilla_78: str,
    casilla_87: str,
    casilla_69: str,
    casilla_71: str,
) -> FiledDeclaracionObservation:
    observation_period = Period.from_year_and_code(year, period)
    body = _modelo_303_page_03_payload(
        casilla_110=casilla_110,
        casilla_78=casilla_78,
        casilla_87=casilla_87,
        casilla_69=casilla_69,
        casilla_71=casilla_71,
    )
    external = load_external_constants().aeat
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(declarations_url),
        content_type="application/octet-stream",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=presented_at,
    )
    declaration = Declaracion(
        modelo="303",
        ejercicio=year,
        period=observation_period,
        expediente_id=expediente_id,
        estado="ALTA",
        tipo_solicitud=None,
        observaciones=None,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
        declaration_copy_link_text=None,
    )
    observed = _observed_casillas_from_submitted_file(
        snapshot=resources().modelos.authority.snapshot("303", filing_year=year, period=period),
        declaration=declaration,
        body=body,
        artefact=artefact,
    )
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=year,
        period=observation_period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=presented_at,
        authenticated_identity=_SYNTHETIC_PROFILE_ID,
        artefacts=(artefact,),
        casillas=observed,
        extraction_coverage={"submitted_file": 1.0},
    )


def _stored_130_justificante_observation(
    store: FiledDeclaracionObservationStore,
    *,
    authenticated_identity: str = "00000000T",
    expediente_id: str = "13020260410ABCD1234EFGH5678",
) -> FiledDeclaracionObservation:
    pdf_bytes = (FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf").read_bytes()
    period = Period.from_year_and_code(2026, "1T")
    external = load_external_constants().aeat
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    artefact = store.persist_artefact(
        ("130", 2026, period, expediente_id),
        FiledDeclaracionArtefact(
            kind="justificante_pdf",
            source_url=AnyHttpUrl(declarations_url),
            content_type="application/pdf",
            byte_count=len(pdf_bytes),
            sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            captured_at=_CAPTURED_AT,
        ),
        pdf_bytes,
    )
    return FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period=period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=_CAPTURED_AT,
        authenticated_identity=authenticated_identity,
        artefacts=(artefact,),
    )


def _seed_current_130_filing(
    *,
    bucket_id: str,
    aeat_accepted: bool = False,
    external_evidence: ExternalEvidence | None = None,
) -> ModeloRecord:
    period = Period.from_year_and_code(2026, "1T")
    revision_id = hashlib.sha256(f"{bucket_id}:130:2026:1T".encode()).hexdigest()
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id,
        modelo="130",
        filing_year=2026,
        period=period,
        revision_id=revision_id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        revision_id=revision_id,
        name="130-2026-1T",
        created_at=_CAPTURED_AT,
        updated_at=_CAPTURED_AT,
    )
    work_unit_repo = WorkUnitCatalogueRepository()
    work_unit_repo.save(upsert_work_unit(work_unit_repo.load(), work_unit))
    filing_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        filed_at=_CAPTURED_AT,
        filed_by="operator",
    )
    filing = ModeloRecord(
        filing_record_id=filing_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=bucket_id,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=period,
        filed_at=_CAPTURED_AT,
        filed_by="operator",
        aeat_accepted=aeat_accepted,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=external_evidence,
    )
    filing_repo = ModeloRecordCatalogueRepository()
    filing_repo.save(upsert_filing_record(filing_repo.load(), filing))
    return filing


def _modelo_303_page_03_payload(
    *,
    casilla_110: str,
    casilla_78: str,
    casilla_87: str,
    casilla_69: str,
    casilla_71: str,
) -> bytes:
    page = list("<T30303000>" + (" " * (1017 - len("<T30303000>"))))
    for position, raw in (
        (255, casilla_110),
        (272, casilla_78),
        (289, casilla_87),
        (323, casilla_69),
        (374, casilla_71),
    ):
        page[position - 1 : position - 1 + len(raw)] = raw
    page[1005:1017] = list("</T30303000>")
    return "".join(page).encode("latin-1")


def _prior_303_observation(
    *,
    pending_compensation: Decimal,
    prior_pending: Decimal | None = None,
    applied: Decimal | None = None,
    result: Decimal = Decimal("0.00"),
    final_result: Decimal | None = None,
    generated: Decimal | None = None,
    year: int = 2026,
    period: str = "1T",
    expediente_id: str = _SYNTHETIC_EXPEDIENTE_ID,
    presented_at: datetime = _CAPTURED_AT,
    status: str = "ALTA",
) -> FiledDeclaracionObservation:
    observation_period = Period.from_year_and_code(year, period)
    body = f"303-{year}-{period}-submitted-file".encode("ascii")
    external = load_external_constants().aeat
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    return FiledDeclaracionObservation(
        modelo="303",
        ejercicio=year,
        period=observation_period,
        expediente_id=expediente_id,
        status=status,
        presented_at=presented_at,
        authenticated_identity=_SYNTHETIC_PROFILE_ID,
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl(declarations_url),
                content_type="application/octet-stream",
                byte_count=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                captured_at=_CAPTURED_AT,
            ),
        ),
        casillas=(
            *(
                    (
                        ObservedCasillaValue(
                            casilla_id=_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
                            value=str(prior_pending),
                            source_artefact_kind="submitted_file",
                            source_locator="submitted-file:110",
                        confidence=1.0,
                    ),
                )
                if prior_pending is not None
                else ()
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_APLICADA_CASILLA,
                        value=str(applied),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:78",
                        confidence=1.0,
                    ),
                )
                if applied is not None
                else ()
            ),
            ObservedCasillaValue(
                casilla_id=_M303_POSTERIOR_CASILLA,
                value=str(pending_compensation),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:87",
                confidence=1.0,
            ),
            ObservedCasillaValue(
                casilla_id=_M303_RESULTADO_CASILLA,
                value=str(result),
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:69",
                confidence=1.0,
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_GENERADA_CASILLA,
                        value=str(generated),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:derived-generated",
                        confidence=1.0,
                    ),
                )
                if generated is not None
                else ()
            ),
            *(
                (
                    ObservedCasillaValue(
                        casilla_id=_M303_RESULTADO_FINAL_CASILLA,
                        value=str(final_result),
                        source_artefact_kind="submitted_file",
                        source_locator="submitted-file:71",
                        confidence=1.0,
                    ),
                )
                if final_result is not None
                else ()
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
        registry_snapshot_id=f"303:2009-y-siguientes:{year}:{period}",
    )


def _declaration(
    *,
    period: str,
    expediente_id: str,
    estado: str,
    presented_at: datetime,
) -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=2026,
        period=Period.from_year_and_code(2026, period),
        expediente_id=expediente_id,
        estado=estado,
        tipo_solicitud=None,
        observaciones=None,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
        declaration_copy_link_text=None,
    )
