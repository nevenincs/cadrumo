"""Filed AEAT observations feed the calculation history repository."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.inbound.justificante import parse_justificante_bytes
from ....adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    ObservedCasillaValue,
)
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....core import CasillaValueKind, Period
from ....core.config import Settings
from ....domain.buckets import BucketEventType
from ....domain.calculations.registry import (
    RegistryModeloObservation,
    RegistryValidationError,
    validated_casilla_id,
)
from ....domain.iva_compensation import IvaCompensationPeriodState
from ....domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
)
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import read_db_at_rest_bytes
from ...calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    ObservationSourceKind,
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from .. import (
    enroll_filed_justificante_evidence,
    list_iva_compensation_history,
    load_iva_remote_state,
    persist_filed_calculation_observation,
    persist_filed_justificante_metadata,
)
from .._errors import LiveApplicationError, LiveApplicationInputError
from .._filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from .._filed_observation_persistence import (
    latest_declarations_by_period,
    persist_iva_compensation_history_observations_strict,
    select_latest_filed_observations_in_history_order,
)
from ._filed_capture_history_support import (
    _CAPTURED_AT,
    _M303_DISPONIBLE_CASILLA,
    _M303_GENERADA_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _SYNTHETIC_EXPEDIENTE_ID,
    _SYNTHETIC_PROFILE_ID,
    _declaration,
    _modelo_130_justificante_pdf_bytes,
    _parsed_303_submitted_file_observation,
    _prior_303_observation,
    _profile_backend,
    _registry_snapshot,
    _secure_backend,
    _seed_current_130_filing,
    _stored_130_justificante_observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_filed_observation_capture_promotes_previous_303_into_recurrence_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            _prior_303_observation(pending_compensation=Decimal("1200.00")),
            repository=repository,
        )

        target_snapshot = _registry_snapshot("303", 2026, "2T")
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

        keys = finalize_filed_capture(
            (observation,),
            justificante_csvs_by_observation={
                ("303", 2026, "1T", _SYNTHETIC_EXPEDIENTE_ID): ("CSV30320261T",),
            },
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
        ).calculation_observation_keys
        loaded = CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T"))

    assert keys == ("303:2026:1T",)
    assert loaded is not None
    assert loaded.source_metadata["aeat_justificante_csv"] == "CSV30320261T"


def test_filed_capture_best_effort_finalizer_reports_incomplete_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        observation = _prior_303_observation(pending_compensation=Decimal("1200.00")).model_copy(
            update={"extraction_coverage": {}},
        )

        finalization = finalize_filed_capture(
            (observation,),
            justificante_csvs_by_observation={},
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
        )

        stored = CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T"))

    assert finalization.calculation_observation_keys == ()
    assert len(finalization.failures) == 1
    assert finalization.failures[0].modelo == "303"
    assert finalization.failures[0].year == 2026
    assert finalization.failures[0].period == Period.from_year_and_code(2026, "1T")
    assert finalization.failures[0].expediente_id == _SYNTHETIC_EXPEDIENTE_ID
    assert finalization.failures[0].error_type == "SedeParseError"
    assert "has no extraction coverage" in finalization.failures[0].message
    assert stored is None


def test_filed_capture_fail_fast_finalizer_raises_on_incomplete_observation(tmp_path: Path) -> None:
    """Single and source capture use FAIL_FAST: a registry-enrollment failure aborts."""
    with _secure_backend(tmp_path):
        observation = _prior_303_observation(pending_compensation=Decimal("1200.00")).model_copy(
            update={"extraction_coverage": {}},
        )

        with pytest.raises(LiveApplicationError, match="could not be enrolled as registry-grounded"):
            finalize_filed_capture(
                (observation,),
                justificante_csvs_by_observation={},
                policy=FiledCaptureFailurePolicy.FAIL_FAST,
            )

        stored = CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T"))
    assert stored is None


def test_capture_finalizer_persists_in_the_shared_selection_and_ordering_authority(tmp_path: Path) -> None:
    """The finalizer persists exactly what the shared selector chooses, in its order.

    This was a two-route parity case: it asserted the finalizer and a second
    history-persistence route resolved identical ordered keys. That second
    route has been deleted — it had no production caller and its own private
    helper swallowed registry-enrollment refusals — so the parity half would
    now compare the finalizer against nothing.

    What survives is the property that was always load-bearing: the selector
    (``select_latest_filed_observations_in_history_order``) decides which
    observation wins a duplicate period (a later BAJA cannot supersede an
    earlier ALTA) and in what order the batch lands, and the finalizer
    persists that decision rather than re-deriving one. Asserting the
    selector's output and the finalizer's keys separately, then that they
    agree, keeps the finalizer from drifting into its own selection.
    """
    observations = (
        _prior_303_observation(
            year=2026,
            period="1T",
            expediente_id="200030300000030Z",
            pending_compensation=Decimal("20.00"),
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        ),
        _prior_303_observation(
            year=2026,
            period="1T",
            expediente_id="200030300000031Z",
            status="BAJA",
            pending_compensation=Decimal("99.00"),
            presented_at=datetime(2026, 4, 25, 10, 0, 0, tzinfo=UTC),
        ),
        _prior_303_observation(
            year=2025,
            period="4T",
            expediente_id="200030300000032Z",
            pending_compensation=Decimal("10.00"),
            presented_at=datetime(2026, 1, 20, 10, 0, 0, tzinfo=UTC),
        ),
    )

    # Pure selection + ordering: the later BAJA is superseded by the earlier ALTA
    # for 2026/1T, and the result is ordered by (year, history-period key).
    selected = select_latest_filed_observations_in_history_order(observations)
    assert tuple((obs.ejercicio, obs.period.registry_token, obs.expediente_id) for obs in selected) == (
        (2025, "4T", "200030300000032Z"),
        (2026, "1T", "200030300000030Z"),
    )

    # The finalizer persists those same keys in that same order via the shared authority.
    with _secure_backend(tmp_path / "finalizer"):
        finalization = finalize_filed_capture(observations, policy=FiledCaptureFailurePolicy.BEST_EFFORT)

    assert finalization.failures == ()
    assert finalization.calculation_observation_keys == ("303:2025:4T", "303:2026:1T")
    # Pinned against the selector's own output, not just a literal, so the two
    # cannot drift apart without this failing.
    assert finalization.calculation_observation_keys == tuple(
        f"{obs.modelo}:{obs.ejercicio}:{obs.period.registry_token}" for obs in selected
    )


def test_finalizer_does_not_disturb_the_separate_strict_iva_compensation_path(tmp_path: Path) -> None:
    """The strict IVA compensation persistence remains a distinct authority.

    The finalizer promotes latest filed observations into calculation history;
    the strict IVA path (``persist_iva_compensation_history_observations_strict``)
    stays a separate function with its own reload-verification contract, so the
    two are not collapsed by the finalizer consolidation.
    """
    observation = _prior_303_observation(
        pending_compensation=Decimal("5.00"),
        expediente_id="200030300000040Z",
        presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
    )
    with _secure_backend(tmp_path):
        strict_keys = persist_iva_compensation_history_observations_strict((observation,))
        strict_history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

    assert strict_keys == ("303:2026:1T",)
    assert strict_history is not None
    assert finalize_filed_capture is not persist_iva_compensation_history_observations_strict


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

        target_snapshot = _registry_snapshot("303", 2026, "1T")
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

        target_snapshot = _registry_snapshot("303", 2026, "2T")
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
        keys = persist_iva_compensation_history_observations_strict(
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
    ("wrong-taxpayer", "X1234567L", "13020260410ABCD1234EFGH5678"),
    ("mismatched-presentation-id", "00000000T", "13020260410ZZZZ1234EFGH5678"),
)


def test_filed_observation_capture_refuses_invalid_justificante_metadata(
    tmp_path: Path,
) -> None:
    with _secure_backend(tmp_path):
        for case_id, authenticated_identity, expediente_id in _REFUSED_JUSTIFICANTE_METADATA_CASES:
            store = FiledDeclaracionObservationStore(tmp_path / f"filed-declarations-{case_id}")
            observation = _stored_130_justificante_observation(
                store,
                authenticated_identity=authenticated_identity,
                expediente_id=expediente_id,
            )

            csvs = persist_filed_justificante_metadata(observation, store=store)

            assert csvs == (), case_id
            assert JustificanteRepository().load("ABCD1234EFGH5678") is None, case_id


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
    selected = latest_declarations_by_period(
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


def test_iva_history_capture_orders_annual_0a_after_periodic_declarations() -> None:
    annual = _declaration(
        period="0A",
        expediente_id="200039000000020Z",
        estado="ALTA",
        presented_at=datetime(2027, 1, 30, 10, 0, 0, tzinfo=UTC),
    ).model_copy(update={"modelo": "390"})
    selected = latest_declarations_by_period(
        (
            annual,
            _declaration(
                period="4T",
                expediente_id="200030300000019Z",
                estado="ALTA",
                presented_at=datetime(2027, 1, 20, 10, 0, 0, tzinfo=UTC),
            ),
        ),
    )

    assert tuple(row.period.registry_token for row in selected) == ("4T", "0A")


def test_filed_history_keeps_non_iva_numeric_period_order_alongside_iva_rows() -> None:
    def declaration_for(modelo: str, period: str, expediente_id: str) -> Declaracion:
        return _declaration(
            period=period,
            expediente_id=expediente_id,
            estado="ALTA",
            presented_at=datetime(2027, 1, 20, 10, 0, 0, tzinfo=UTC),
        ).model_copy(update={"modelo": modelo})

    selected = latest_declarations_by_period(
        (
            declaration_for("190", "0A", "200019000000024Z"),
            declaration_for("111", "10", "200011100000023Z"),
            declaration_for("303", "4T", "200030300000022Z"),
            declaration_for("111", "2T", "200011100000021Z"),
            declaration_for("111", "1T", "200011100000020Z"),
        ),
    )

    assert tuple(row.period.registry_token for row in selected) == ("1T", "2T", "4T", "10", "0A")
    assert tuple(row.modelo for row in selected) == ("111", "111", "303", "111", "190")


def test_duplicate_period_capture_promotes_alta_over_later_non_alta_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        keys = finalize_filed_capture(
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
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
        ).calculation_observation_keys

        stored = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))
        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert keys == ("303:2026:1T",)
        assert stored is not None
        assert stored.observation.casilla_values[_M303_DISPONIBLE_CASILLA] == Decimal("1200.00")
        assert history is not None
        assert history.expediente_id == "200030300000012Z"


def test_iva_history_strict_persist_promotes_alta_over_later_non_alta_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        keys = persist_iva_compensation_history_observations_strict(
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


def test_iva_history_strict_persist_ignores_non_alta_only_period(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        keys = persist_iva_compensation_history_observations_strict(
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


def test_iva_history_strict_persist_refuses_non_303_before_writing(tmp_path: Path) -> None:
    non_303 = _prior_303_observation(pending_compensation=Decimal("900.00")).model_copy(
        update={"modelo": "130"},
    )

    with _secure_backend(tmp_path):
        with pytest.raises(LiveApplicationInputError) as error:
            persist_iva_compensation_history_observations_strict((non_303,))

        assert error.value.translated_message == "live.errors.iva_history_modelo_303_only"
        assert error.value.context == {"modelo": "130"}
        assert IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T")) is None


def test_duplicate_period_capture_promotes_latest_filing_to_calculation_history(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        finalize_filed_capture(
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
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
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

        database_bytes = read_db_at_rest_bytes(db_path)
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

        keys = persist_iva_compensation_history_observations_strict(observations)
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


def test_history_selection_is_invariant_to_the_order_duplicated_periods_arrive_in() -> None:
    """A period with two active filings collapses to one, and input order cannot change which.

    The register can return an original and a later-presented amendment for the
    same period, both registered ALTA. Selection must keep exactly one per
    period and keep the later one -- and it must reach that answer by ranking,
    not by whichever row happened to be seen last. Feeding the identical set in
    reverse is what separates those two implementations: a last-write-wins
    reduction agrees with a max-by-rank one on a conveniently ordered input and
    disagrees the moment the order flips.

    Ordinary single-filing periods sit in the same batch so a selector that
    collapsed everything to one row per modelo-year would not pass.
    """
    original_3t = _prior_303_observation(
        year=2024,
        period="3T",
        expediente_id="202430300000303C",
        pending_compensation=Decimal("300.00"),
        presented_at=datetime(2024, 10, 18, 12, 5, 11, tzinfo=UTC),
    )
    amendment_3t = _prior_303_observation(
        year=2024,
        period="3T",
        expediente_id="202430300000505E",
        pending_compensation=Decimal("355.00"),
        presented_at=datetime(2025, 3, 14, 11, 20, 36, tzinfo=UTC),
    )
    original_4t = _prior_303_observation(
        year=2024,
        period="4T",
        expediente_id="202430300000404D",
        pending_compensation=Decimal("400.00"),
        presented_at=datetime(2025, 1, 27, 16, 42, 58, tzinfo=UTC),
    )
    amendment_4t = _prior_303_observation(
        year=2024,
        period="4T",
        expediente_id="202430300000606F",
        pending_compensation=Decimal("444.00"),
        presented_at=datetime(2025, 3, 14, 11, 58, 9, tzinfo=UTC),
    )
    single_1t = _prior_303_observation(
        year=2024,
        period="1T",
        expediente_id="202430300000101A",
        pending_compensation=Decimal("100.00"),
        presented_at=datetime(2024, 4, 22, 10, 14, 3, tzinfo=UTC),
    )
    observations = (single_1t, original_3t, original_4t, amendment_3t, amendment_4t)

    selected = select_latest_filed_observations_in_history_order(observations)
    reversed_selection = select_latest_filed_observations_in_history_order(tuple(reversed(observations)))

    periods_selected = [observation.period for observation in selected]
    assert len(periods_selected) == len(set(periods_selected)), (
        "a period survived more than once, so duplicated filings were not collapsed"
    )
    assert set(periods_selected) == {observation.period for observation in observations}, (
        "collapsing dropped a period entirely instead of choosing one filing within it"
    )
    winners = {observation.period: observation.expediente_id for observation in selected}
    assert winners[amendment_3t.period] == amendment_3t.expediente_id
    assert winners[amendment_4t.period] == amendment_4t.expediente_id
    assert winners[single_1t.period] == single_1t.expediente_id
    assert reversed_selection == selected, (
        "selection depends on the order the register rows arrived in, so it is not ranking them"
    )


_SYNTHETIC_REQUEST_TYPE = "SYNTHETIC-REQUEST-TYPE"


def _filed_130_observation_carrying_a_request_type() -> FiledDeclaracionObservation:
    """Build one active filed Modelo 130 observation whose metadata states a request type.

    The metadata mapping mirrors what the live capture path writes off the
    register row. Modelo 130 keeps this out of the IVA compensation machinery,
    so the persistence boundary is exercised on its own.
    """
    body = b"130-2026-1T-submitted-file"
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl("https://www6.agenciatributaria.gob.es/wlpl/BUCV-JDIT/AvisoLegal"),
        content_type="application/octet-stream",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=_CAPTURED_AT,
    )
    return FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="202613000000101A",
        status="ALTA",
        presented_at=_CAPTURED_AT,
        authenticated_identity=_SYNTHETIC_PROFILE_ID,
        artefacts=(artefact,),
        casillas=(
            ObservedCasillaValue(
                casilla_id=validated_casilla_id("01", surface="filed request-type observation"),
                value="1000.00",
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:01",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
        metadata={"tipo_solicitud": _SYNTHETIC_REQUEST_TYPE, "observaciones": ""},
    )


def test_persisted_source_metadata_drops_the_register_request_type_signal(tmp_path: Path) -> None:
    """AEAT's own request-type signal reaches the observation and is lost at persistence.

    The capture path reads the register row's request type into the raw
    observation's ``metadata``, and the calculation-observation source metadata
    is built from a fixed key set that does not include it. So the one signal
    that could distinguish an original filing from an amendment is discarded
    before anything downstream could elect on it, and no selection logic reads
    it today.

    This pins that loss deliberately rather than repairing it: which identifier
    an amendment-aware election should key on is an open decision, and a silent
    half-fix would be worse than a visible gap. REVERSE THIS TEST when the
    request-type signal is carried through -- assert the persisted metadata
    carries it, and the two absence assertions below become the ones to delete.
    """
    observation = _filed_130_observation_carrying_a_request_type()
    assert observation.metadata["tipo_solicitud"] == _SYNTHETIC_REQUEST_TYPE, (
        "the raw observation does not carry the signal, so this test cannot show it being dropped"
    )

    with _secure_backend(tmp_path):
        persist_filed_calculation_observation(observation, repository=CalculationObservationRepository())
        loaded = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert loaded is not None
    assert "aeat_expediente_id" in loaded.source_metadata, (
        "the metadata was not built at all, so the absences below would prove nothing"
    )
    assert "tipo_solicitud" not in loaded.source_metadata
    assert _SYNTHETIC_REQUEST_TYPE not in loaded.source_metadata.values(), (
        "the request type reached persistence under some other key; this test must name that key instead"
    )


def test_receipt_presentation_identifier_is_rejected_against_a_register_expediente_id(tmp_path: Path) -> None:
    """The match predicate refuses a receipt that belongs to the filing, so nothing is stamped.

    A justificante carries its own presentation identifier, and the register row
    carries an expediente id. Those are differently shaped identifiers for the
    same filing, and the production comparison feeds the expediente id into the
    receipt's presentation-identifier check. So a receipt agreeing on modelo,
    ejercicio, period and taxpayer identity -- every axis that establishes it IS
    this filing's receipt -- is still rejected, and no evidence is stamped onto
    the filing record.

    The first assertion is what makes this a false rejection rather than an
    ordinary one: the same predicate accepts the receipt on every other axis
    when the presentation identifier is not supplied.

    The predicate is deliberately left as it is. Which identifier the comparison
    should use is unsettled, and dropping the comparison would trade a visible
    refusal for silent mis-stamping. REVERSE THIS TEST once that is decided:
    assert the receipt stamps, and delete the rejection assertions below.
    """
    register_expediente_id = "202613000000101A"
    receipt = parse_justificante_bytes(_modelo_130_justificante_pdf_bytes())
    assert receipt.presentation_id is not None
    assert receipt.presentation_id != register_expediente_id, (
        "the receipt's presentation identifier equals the register expediente id, "
        "so this fixture pair cannot exercise the divergence"
    )
    assert receipt.matches_filing_target(
        modelo="130",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        tax_id="00000000T",
    ), "the receipt does not belong to this filing on the other axes, so its rejection is not a false one"

    assert (
        receipt.matches_filing_target(
            modelo="130",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            tax_id="00000000T",
            presentation_id=register_expediente_id,
        )
        is False
    )

    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store, expediente_id=register_expediente_id)
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

        target_snapshot = _registry_snapshot("303", 2026, "2T")

        with pytest.raises(RegistryValidationError, match=r"iva\.compensacion-disponible-fin-periodo"):
            resolve_bindings_from_local_store(target_snapshot, repository=repository, captured_at=_CAPTURED_AT)


def _filed_130_observation(
    *,
    expediente_id: str = "13020260410ABCD1234EFGH5678",
    presented_at: datetime = _CAPTURED_AT,
) -> FiledDeclaracionObservation:
    """One Modelo 130 filed observation that enrols as registry-grounded evidence.

    Deliberately NOT Modelo 303. The provenance stamp is modelo-agnostic, while a
    303 observation additionally drives the IVA compensation wallet on the way to
    persistence -- a side effect with nothing to do with provenance, whose failure
    would be indistinguishable here from a provenance divergence. Modelo 130
    exercises the same single stamping site with nothing else attached.
    """
    period = Period.from_year_and_code(2026, "1T")
    body = b"130-2026-1T-submitted-file"
    external = Settings.external_constants().aeat
    declarations_url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    artefact = FiledDeclaracionArtefact(
        kind="submitted_file",
        source_url=AnyHttpUrl(declarations_url),
        content_type="application/octet-stream",
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        captured_at=presented_at,
    )
    return FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period=period,
        expediente_id=expediente_id,
        status="ALTA",
        presented_at=presented_at,
        authenticated_identity=_SYNTHETIC_PROFILE_ID,
        artefacts=(artefact,),
        casillas=(
            ObservedCasillaValue(
                casilla_id=validated_casilla_id("03"),
                value="1500.00",
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:03",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
    )


def test_discovery_driven_capture_stamps_the_same_official_source_kind(tmp_path: Path) -> None:
    """A discovery-nominated pair is provenance-identical to a single-pair capture.

    This is the point of the Step, not a formality. The design deliberately adds
    NO sixth ``ObservationSourceKind`` for a backfilled historical filing, on the
    ground that an imported filing IS an AEAT-sourced filed declaración rather
    than a lesser-trust echo of one. That is only safe if the discovery signal
    genuinely cannot reach the stamp -- so the same synthetic declaración is
    pushed through the single-pair finalizer policy and through the bulk policy a
    discovery-driven sweep uses, into two real repositories on real encrypted
    backends, and the two persisted rows are compared whole.

    The comparison excludes nothing. ``captured_at`` is derived from the filing's
    own ``presented_at``, so it is genuinely equal on both paths and is asserted
    equal rather than waved through; the registry observation, the revision stamp,
    the source metadata and the member NIF are each asserted equal, and then the
    two rows are compared with ``==`` so a field added later is covered without
    this test being edited.
    """
    observation = _filed_130_observation()
    period = Period.from_year_and_code(2026, "1T")

    with _secure_backend(tmp_path / "single"):
        single_finalization = finalize_filed_capture(
            (observation,),
            policy=FiledCaptureFailurePolicy.FAIL_FAST,
        )
        single_row = CalculationObservationRepository().load_observation("130", period)

    # A discovery-driven sweep reaches capture through the bulk grid, whose
    # finalizer policy is BEST_EFFORT because partial success is the expected
    # outcome of a history walk. That policy is the ONLY thing the discovery route
    # changes about finalization, which is why it is the arm under test.
    with _secure_backend(tmp_path / "discovered"):
        discovered_finalization = finalize_filed_capture(
            (observation,),
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
        )
        discovered_row = CalculationObservationRepository().load_observation("130", period)

    assert single_row is not None
    assert discovered_row is not None
    assert discovered_finalization.failures == ()
    assert single_finalization.calculation_observation_keys == discovered_finalization.calculation_observation_keys

    assert single_row.source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
    assert discovered_row.source_kind is ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE
    assert discovered_row.source_kind.is_official_aeat

    assert discovered_row.observation == single_row.observation
    assert discovered_row.stamped_revision_id == single_row.stamped_revision_id
    assert discovered_row.source_metadata == single_row.source_metadata
    assert discovered_row.member_nif == single_row.member_nif
    assert discovered_row.captured_at == single_row.captured_at == observation.presented_at
    assert discovered_row == single_row


def test_no_discovery_signal_token_reaches_the_observation_provenance(tmp_path: Path) -> None:
    """The persisted provenance names no discovery signal, so it cannot depend on one.

    The parity assertion above compares two runs and would pass if both were
    wrong in the same way. This closes that side: a signal token reaching
    ``source_metadata`` would make the stored provenance vary with WHICH signal
    nominated the pair, which is exactly the distinction the domain does not have.
    """
    from ....core import FiledHistoryDiscoverySignal

    with _secure_backend(tmp_path):
        finalize_filed_capture((_filed_130_observation(),), policy=FiledCaptureFailurePolicy.BEST_EFFORT)
        row = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert row is not None
    assert row.source_metadata
    stored = " ".join((*row.source_metadata.keys(), *row.source_metadata.values())).casefold()
    for signal in FiledHistoryDiscoverySignal:
        assert signal.value not in stored


def test_the_official_source_kind_set_gains_no_discovery_specific_member() -> None:
    """No sixth kind was introduced, and the official set is still exactly three.

    Gated on membership of the official set rather than on a total count of the
    enum, so adding a genuinely unrelated NON-official kind does not force an edit
    here -- while adding a discovery-specific official kind, which is the decision
    this Step settled, fails.
    """
    official = {kind for kind in ObservationSourceKind if kind.is_official_aeat}
    assert official == {
        ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE,
        ObservationSourceKind.AEAT_CSV_REGISTER,
    }
    assert not any("discover" in kind.value or "history" in kind.value for kind in ObservationSourceKind)
