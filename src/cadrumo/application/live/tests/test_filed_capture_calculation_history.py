"""Filed AEAT observations feed the calculation history repository."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede import (
    Declaracion,
    FiledDeclaracionObservationStore,
)
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....core import Period
from ....domain.buckets import BucketEventType
from ....domain.calculations.registry import (
    RegistryModeloObservation,
    RegistryValidationError,
)
from ....domain.iva_compensation import IvaCompensationPeriodState
from ....domain.modelos import (
    ExternalEvidence,
    ExternalEvidenceKind,
)
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
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
    persist_latest_filed_calculation_observations,
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

        keys = persist_latest_filed_calculation_observations(
            (observation,),
            justificante_csvs_by_observation={
                ("303", 2026, "1T", _SYNTHETIC_EXPEDIENTE_ID): ("CSV30320261T",),
            },
        )
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


def test_all_capture_routes_share_one_selection_and_ordering_authority(tmp_path: Path) -> None:
    """The finalizer and the calculation-history persistence produce identical ordered keys.

    Both delegate to ``select_latest_filed_observations_in_history_order``, so a
    duplicate-period batch (a later BAJA cannot supersede an earlier ALTA) and a
    cross-year set persist the SAME keys in the SAME order via either route —
    proving the capture finalizer and the history-persistence path cannot drift
    apart, which the duplicated capture-side selector previously allowed.
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
    # The calculation-history persistence route resolves identical keys/order.
    with _secure_backend(tmp_path / "history"):
        history_keys = persist_latest_filed_calculation_observations(observations)

    assert finalization.failures == ()
    assert finalization.calculation_observation_keys == history_keys == ("303:2025:4T", "303:2026:1T")


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
        keys = persist_latest_filed_calculation_observations(
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
        persist_latest_filed_calculation_observations(
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
