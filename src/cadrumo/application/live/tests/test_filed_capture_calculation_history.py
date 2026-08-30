"""Filed AEAT observations feed the calculation history repository."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl

from ....adapters.inbound.justificante.parser import parse_justificante_bytes
from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ....adapters.outbound.aeat.sede.schema import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    ObservedCasillaValue,
)
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....core import CasillaValueKind, IvaCompensationStateProvenance, Period
from ....core.casilla_id import validated_casilla_id
from ....core.config import Settings
from ....core.json_contract import NoticeSeverity
from ....domain.buckets.event import BucketEventType
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from ....domain.modelos.filing_record import ExternalEvidence, ExternalEvidenceKind
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import read_db_at_rest_bytes
from ...calculations import (
    CalculationObservationRepository,
    IvaCompensationHistoryRepository,
    ObservationSourceKind,
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from ..errors import LiveApplicationError, LiveApplicationInputError
from ..filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from ..filed_observation_persistence import (
    FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
    FiledJustificanteUnreachedReason,
    enroll_filed_justificante_evidence,
    latest_declarations_by_period,
    persist_filed_calculation_observation,
    persist_filed_justificante_metadata,
    persist_iva_compensation_history_observations_strict,
    select_latest_filed_observations_in_history_order,
)
from ..iva_remote_state import (
    list_iva_compensation_history,
    load_iva_remote_state,
)
from ._filed_capture_history_support import (
    _CAPTURED_AT,
    _M303_DECLARATION_TYPE_C,
    _M303_DECLARATION_TYPE_I,
    _M303_DISPONIBLE_CASILLA,
    _M303_GENERADA_CASILLA,
    _M303_POSTERIOR_CASILLA,
    _MODELO_130_FIXTURE_CSV,
    _MODELO_303_FIXTURE_CSV,
    _SYNTHETIC_EXPEDIENTE_ID,
    _SYNTHETIC_PROFILE_ID,
    _declaration,
    _modelo_130_justificante_pdf_bytes,
    _modelo_303_justificante_pdf_bytes,
    _parsed_303_submitted_file_observation,
    _prior_303_observation,
    _profile_backend,
    _registry_snapshot,
    _secure_backend,
    _seed_current_130_filing,
    _seed_current_303_filing,
    _stored_130_justificante_observation,
    _stored_303_justificante_observation,
    _stored_justificante_observation,
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

        with pytest.raises(
            LiveApplicationError,
            match=r"application\.live\.filed_observations\.errors\.registry_enrollment_failed",
        ):
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
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
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
        with pytest.raises(
            LiveApplicationInputError,
            match=r"application\.live\.filed_observations\.errors\.observation_not_active",
        ):
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

        csvs = persist_filed_justificante_metadata(observation, store=store).justificante_csvs

        assert csvs == ("ABCD1234EFGH5678",)
        loaded = JustificanteRepository().load("ABCD1234EFGH5678")
        assert loaded is not None
        assert loaded.modelo == "130"
        assert loaded.period == Period.from_year_and_code(2026, "1T")
        assert loaded.tax_id == "00000000T"


#: Each case diverges on exactly one axis and holds the rest at the values the
#: enrolling case uses, so a refusal is attributable to the named axis. The
#: second case used to diverge on the register expediente id, which is not an
#: axis the predicate consults; it now diverges on the csv the artefact's bytes
#: were fetched under, which is.
def test_a_committed_modelo_303_receipt_is_enrolled_from_the_register_path(tmp_path: Path) -> None:
    """A Modelo 303 receipt fixture enrolls through the register-reconciliation path.

    Modelo 303 is the case this path used to drop silently: the receipt agreed on
    modelo, ejercicio, period and taxpayer identity, so it plainly belonged to
    the filing, and it was still refused because a register expediente id was
    being compared against the receipt's own Número de justificante. The two
    values below are asserted to diverge first, so this fixture reproduces that
    divergence rather than sidestepping it, and the enrollment that follows is
    what the divergence used to prevent.
    """
    receipt = parse_justificante_bytes(_modelo_303_justificante_pdf_bytes())
    expediente_id = "202630300000411A"
    assert receipt.presentation_id is not None
    assert receipt.presentation_id.strip().casefold() != expediente_id.strip().casefold(), (
        "the receipt identifier and the register expediente id agree, so this fixture cannot "
        "show the divergence being tolerated"
    )

    with _secure_backend(tmp_path):
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_303_justificante_observation(store, expediente_id=expediente_id)

        csvs = persist_filed_justificante_metadata(observation, store=store).justificante_csvs

        assert csvs == (_MODELO_303_FIXTURE_CSV,)
        loaded = JustificanteRepository().load(_MODELO_303_FIXTURE_CSV)
        assert loaded is not None
        assert loaded.modelo == "303"
        assert loaded.ejercicio == "2026"
        assert loaded.period == Period.from_year_and_code(2026, "1T")
        assert loaded.tax_id == "00000000T"
        # The receipt's own identifier survives onto the persisted record; it is
        # no longer a matching axis, which is not the same as being discarded.
        assert loaded.presentation_id == receipt.presentation_id


#: Each case diverges on exactly one axis and holds the rest at the values the
#: enrolling case uses, so a refusal is attributable to the named axis. The
#: second case used to diverge on the register expediente id, which is not an
#: axis the predicate consults; it now diverges on the csv the artefact's bytes
#: were fetched under, which is.
_REFUSED_JUSTIFICANTE_METADATA_CASES = (
    ("wrong-taxpayer", "X1234567L", _MODELO_130_FIXTURE_CSV),
    ("csv-is-another-filings", "00000000T", "QQQQ7777WWWW3333"),
)


def test_filed_observation_capture_refuses_invalid_justificante_metadata(
    tmp_path: Path,
) -> None:
    with _secure_backend(tmp_path):
        for case_id, authenticated_identity, captured_csv in _REFUSED_JUSTIFICANTE_METADATA_CASES:
            store = FiledDeclaracionObservationStore(tmp_path / f"filed-declarations-{case_id}")
            observation = _stored_130_justificante_observation(
                store,
                authenticated_identity=authenticated_identity,
                captured_csv=captured_csv,
            )

            csvs = persist_filed_justificante_metadata(observation, store=store).justificante_csvs

            assert csvs == (), case_id
            assert JustificanteRepository().load(_MODELO_130_FIXTURE_CSV) is None, case_id


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
                headers=(_M303_DECLARATION_TYPE_C,),
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
                headers=(_M303_DECLARATION_TYPE_C,),
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
                casilla_110=Decimal("0.00"),
                casilla_78=Decimal("0.00"),
                casilla_87=Decimal("0.00"),
                casilla_69=Decimal("-100.00"),
                casilla_71=Decimal("-100.00"),
            ),
            _parsed_303_submitted_file_observation(
                year=2026,
                period="1T",
                expediente_id="200030300000010Z",
                presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                casilla_110=Decimal("100.00"),
                casilla_78=Decimal("30.00"),
                casilla_87=Decimal("120.00"),
                casilla_69=Decimal("-50.00"),
                casilla_71=Decimal("-50.00"),
            ),
            _parsed_303_submitted_file_observation(
                year=2026,
                period="2T",
                expediente_id="200030300000011Z",
                presented_at=datetime(2026, 7, 20, 10, 0, 0, tzinfo=UTC),
                casilla_110=Decimal("170.00"),
                casilla_78=Decimal("20.00"),
                casilla_87=Decimal("100.00"),
                casilla_69=Decimal("25.00"),
                casilla_71=Decimal("25.00"),
                headers=(_M303_DECLARATION_TYPE_I,),
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


def test_persisted_source_metadata_carries_the_register_request_type_signal(tmp_path: Path) -> None:
    """AEAT's own request-type signal now survives to persisted provenance.

    This test previously pinned the OPPOSITE: the capture path read the register
    row's request type into the raw observation and the source metadata was built
    from a fixed key set that dropped it, so the one signal distinguishing an
    original filing from an amendment was gone before anything downstream could
    read it. Its docstring said to reverse it when the carry-through landed, and
    this is that reversal -- the absence assertions are gone rather than relaxed.

    Carrying the signal is NOT electing on it. No selection logic reads this key,
    and which identifier an amendment-aware election should key on stays an open
    decision; what changed is that the evidence survives so that decision can be
    made against persisted data instead of requiring a re-capture.

    Modelo 130 keeps this off the IVA compensation machinery a Modelo 303
    observation additionally drives, so the persistence boundary is exercised on
    its own. The metadata mapping mirrors what the live capture path writes off
    the register row.
    """
    observation = _filed_130_observation().model_copy(
        update={"metadata": {"tipo_solicitud": _SYNTHETIC_REQUEST_TYPE, "observaciones": ""}},
    )
    assert observation.metadata["tipo_solicitud"] == _SYNTHETIC_REQUEST_TYPE, (
        "the raw observation does not carry the signal, so this test cannot show it being carried"
    )

    with _secure_backend(tmp_path):
        persist_filed_calculation_observation(observation, repository=CalculationObservationRepository())
        loaded = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert loaded is not None
    assert loaded.source_metadata["aeat_tipo_solicitud"] == _SYNTHETIC_REQUEST_TYPE
    # The surrounding provenance is asserted too, so a change that carried the
    # request type while dropping a sibling key would not read as a pass.
    assert loaded.source_metadata["aeat_expediente_id"] == observation.expediente_id
    assert loaded.source_metadata["aeat_register_status"] == "ALTA"


def test_persisted_source_metadata_omits_an_absent_request_type_rather_than_writing_it_empty(
    tmp_path: Path,
) -> None:
    """A register row with no request type leaves the key ABSENT, never empty.

    An empty string would be indistinguishable from AEAT declaring an empty
    request type, so a later amendment-aware reader could not tell "the row did
    not say" from "the row said nothing". Absence is the honest encoding, and
    this pins it in both directions: the blank-string case and the
    key-entirely-missing case both omit it.
    """
    blank = _filed_130_observation().model_copy(update={"metadata": {"tipo_solicitud": "   "}})
    missing = _filed_130_observation().model_copy(update={"metadata": {"observaciones": ""}})

    with _secure_backend(tmp_path / "blank"):
        persist_filed_calculation_observation(blank, repository=CalculationObservationRepository())
        blank_row = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))
    with _secure_backend(tmp_path / "missing"):
        persist_filed_calculation_observation(missing, repository=CalculationObservationRepository())
        missing_row = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert blank_row is not None
    assert missing_row is not None
    assert "aeat_tipo_solicitud" not in blank_row.source_metadata
    assert "aeat_tipo_solicitud" not in missing_row.source_metadata
    # Anchor: the metadata was built at all, so the absences above mean something.
    assert "aeat_expediente_id" in blank_row.source_metadata
    assert "aeat_expediente_id" in missing_row.source_metadata


def test_the_request_type_signal_survives_a_strict_persistence_roundtrip(tmp_path: Path) -> None:
    """The carried key crosses the real encrypted boundary and reloads equal.

    Real key provider, real SQLite, real serializer: the field is written through
    the production persist path and read back through the production load path,
    then the whole reloaded provenance envelope is compared rather than just the
    one key, so a save that carried the request type while re-defaulting a
    neighbouring field fails here.
    """
    observation = _filed_130_observation().model_copy(
        update={"metadata": {"tipo_solicitud": _SYNTHETIC_REQUEST_TYPE, "observaciones": "OBS"}},
    )
    with _secure_backend(tmp_path):
        persist_filed_calculation_observation(
            observation,
            repository=CalculationObservationRepository(),
            justificante_csvs=("CSV13020261T",),
        )
        first = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))
        second = CalculationObservationRepository().load_observation("130", Period.from_year_and_code(2026, "1T"))

    assert first is not None
    assert second is not None
    assert first == second
    assert first.source_metadata == {
        "aeat_register_status": "ALTA",
        "aeat_expediente_id": observation.expediente_id,
        "authenticated_identity": _SYNTHETIC_PROFILE_ID,
        "aeat_tipo_solicitud": _SYNTHETIC_REQUEST_TYPE,
        "aeat_justificante_csv": "CSV13020261T",
    }


def test_a_receipt_stamps_its_filing_even_though_its_identifier_is_not_the_register_expediente_id(
    tmp_path: Path,
) -> None:
    """A receipt that belongs to the filing is enrolled, and its own identifier is not consulted.

    This test previously pinned the OPPOSITE. A justificante carries AEAT's
    Número de justificante and the register row carries an expediente id; those
    are different AEAT identifier namespaces for the same filing, and the
    production comparison fed the expediente id into the receipt's
    presentation-identifier check. Since no receipt body ever carries the
    register's expediente id, that comparison could never agree, so a receipt
    agreeing on modelo, ejercicio, period and taxpayer identity was still
    rejected and nothing was stamped. Its docstring said to reverse it once the
    comparison was settled, and this is that reversal -- the rejection
    assertions are gone rather than relaxed.

    What replaced the broken axis is a csv comparison the caller performs
    itself, against a csv recovered from the URL the bytes were fetched under.
    That axis is exercised in both directions by
    ``test_a_receipt_is_refused_when_its_csv_is_not_the_csv_its_bytes_were_fetched_under``
    and the two-filings discrimination test below, so this test's job is
    narrower: the divergent identifiers no longer block a legitimate stamp.
    """
    # DO NOT "tidy" these two into agreement. Their divergence is still the
    # premise: it is what makes the stamp below evidence that the identifier is
    # no longer consulted, rather than evidence that two equal values agreed.
    register_expediente_id = "202613000000101A"
    receipt = parse_justificante_bytes(_modelo_130_justificante_pdf_bytes())
    assert receipt.presentation_id is not None
    assert receipt.presentation_id.strip().casefold() != register_expediente_id.strip().casefold(), (
        "the receipt's presentation identifier and the register expediente id no longer diverge, "
        "so this fixture pair cannot exercise the divergence"
    )

    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store, expediente_id=register_expediente_id)
        filing = _seed_current_130_filing(bucket_id=bucket_id)

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

    assert result.justificante_csvs == (receipt.csv,)
    assert result.filing_record_ids == (filing.filing_record_id,)
    assert result.conflicting_filing_record_ids == ()
    assert current is not None
    assert current.aeat_accepted is True
    assert current.external_evidence is not None
    assert current.external_evidence.kind is ExternalEvidenceKind.AEAT_LIVE_CAPTURE
    assert current.external_evidence.reference_id == receipt.csv


def test_a_receipt_is_refused_when_its_csv_is_not_the_csv_its_bytes_were_fetched_under(
    tmp_path: Path,
) -> None:
    """The csv check is what refuses a mis-paired artefact, now that the identifier axis is gone.

    The stored artefact records the cotejo document URL its bytes were fetched
    under, and that csv came from AEAT's own cotejo redirect rather than from
    the PDF. Here the URL names one filing's csv while the stored bytes are the
    receipt of another, which is the shape a storage or selection defect
    re-associating an artefact after capture would produce.

    Everything else agrees, so this refusal is attributable to the csv axis
    alone: same modelo, ejercicio, period and taxpayer identity, and a filing
    record present and ready to be stamped.
    """
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store, captured_csv="QQQQ7777WWWW3333")
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


def test_a_receipt_is_refused_when_no_csv_can_be_recovered_from_the_artefact_url(
    tmp_path: Path,
) -> None:
    """A source URL carrying no csv is reported as a non-match, never an exception.

    The recovery helper raises on a URL with no usable ``CSV`` query, and this
    function runs inside an enrollment loop over every artefact. Letting that
    propagate would abort the whole enrollment over one malformed URL, so it
    joins the other swallowed outcomes instead.
    """
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)
        artefact = observation.artefacts[0]
        observation = observation.model_copy(
            update={
                "artefacts": (
                    artefact.model_copy(
                        update={"source_url": AnyHttpUrl(str(artefact.source_url).split("?", 1)[0])},
                    ),
                ),
            },
        )
        _seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

    assert result.justificante_csvs == ()
    assert result.filing_record_ids == ()


def test_the_csv_check_tells_two_same_period_filings_apart_where_the_other_axes_cannot(
    tmp_path: Path,
) -> None:
    """Two Modelo 303 filings for one period are discriminated by csv alone.

    A period can carry more than one filing -- an original and a substitutive,
    say -- and they share modelo, ejercicio, period and taxpayer identity. Those
    are every axis the match predicate consults, so the predicate cannot tell
    the two apart; the first block below asserts exactly that, which is what
    makes the csv axis load-bearing rather than redundant.

    So the same receipt bytes are enrolled twice against two register rows that
    differ only in expediente id. The row whose artefact URL names the csv
    printed on those bytes stamps its filing. The row whose URL names the other
    filing's csv is refused, and its filing is left unstamped.
    """
    receipt = parse_justificante_bytes(_modelo_303_justificante_pdf_bytes())
    other_filing_csv = "QQQQ7777WWWW3333"
    assert receipt.csv.strip().upper() != other_filing_csv, (
        "the two filings' csvs no longer diverge, so nothing here can be discriminated"
    )

    # The four surviving axes are identical for both filings, so the predicate
    # returns True for each. Only the csv separates them.
    for expediente_id in ("202630300000411A", "202630300000412B"):
        assert receipt.matches_filing_target(
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, "1T"),
            tax_id="00000000T",
        ), f"the predicate must accept the receipt for {expediente_id}, or the two are already separable"

    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        filing = _seed_current_303_filing(bucket_id=bucket_id)

        wrong_filing = _stored_303_justificante_observation(
            store,
            expediente_id="202630300000412B",
            captured_csv=other_filing_csv,
        )
        refused = enroll_filed_justificante_evidence(wrong_filing, store=store, bucket_id=bucket_id)
        after_refusal = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )

        right_filing = _stored_303_justificante_observation(store)
        accepted = enroll_filed_justificante_evidence(right_filing, store=store, bucket_id=bucket_id)
        after_acceptance = (
            ModeloRecordCatalogueRepository()
            .load()
            .current_for(
                bucket_id=bucket_id,
                modelo="303",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            )
        )

    assert refused.justificante_csvs == ()
    assert refused.filing_record_ids == ()
    assert after_refusal is not None
    assert after_refusal.external_evidence is None
    assert after_refusal.aeat_accepted is False

    assert accepted.justificante_csvs == (receipt.csv,)
    assert accepted.filing_record_ids == (filing.filing_record_id,)
    assert after_acceptance is not None
    assert after_acceptance.aeat_accepted is True
    assert after_acceptance.external_evidence is not None
    assert after_acceptance.external_evidence.reference_id == receipt.csv


def _artefact_replaced(
    observation: FiledDeclaracionObservation,
    **updates: object,
) -> FiledDeclaracionObservation:
    artefact = observation.artefacts[0]
    return observation.model_copy(update={"artefacts": (artefact.model_copy(update=updates),)})


def _manifest_mismatch_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    observation = _stored_130_justificante_observation(store)
    return _artefact_replaced(observation, byte_count=observation.artefacts[0].byte_count + 1)


def _unparsable_pdf_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    return _stored_justificante_observation(
        store,
        modelo="130",
        pdf_bytes=b"%PDF-1.4 not a receipt",
        authenticated_identity="00000000T",
        expediente_id="202613000000199Z",
        captured_csv=_MODELO_130_FIXTURE_CSV,
    )


def _csv_unresolvable_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    observation = _stored_130_justificante_observation(store)
    stripped = str(observation.artefacts[0].source_url).split("?", 1)[0]
    return _artefact_replaced(observation, source_url=AnyHttpUrl(stripped))


def _csv_mismatch_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    return _stored_130_justificante_observation(store, captured_csv="QQQQ7777WWWW3333")


def _filing_target_mismatch_observation(store: FiledDeclaracionObservationStore) -> FiledDeclaracionObservation:
    # The csv agrees, so this reaches the filing-target axis rather than stopping
    # at the csv one: a Modelo 130 receipt filed under a Modelo 303 register row.
    return _stored_justificante_observation(
        store,
        modelo="303",
        pdf_bytes=_modelo_130_justificante_pdf_bytes(),
        authenticated_identity="00000000T",
        expediente_id="202630300000199Z",
        captured_csv=_MODELO_130_FIXTURE_CSV,
    )


_UNREACHED_JUSTIFICANTE_CASES = (
    ("manifest-mismatch", _manifest_mismatch_observation),
    ("unparsable-pdf", _unparsable_pdf_observation),
    ("csv-unresolvable", _csv_unresolvable_observation),
    ("csv-mismatch", _csv_mismatch_observation),
    ("filing-target-mismatch", _filing_target_mismatch_observation),
)


def test_each_unreached_justificante_outcome_reports_its_own_reason(tmp_path: Path) -> None:
    """Five dead ends that used to share one shape now name themselves.

    A capture that extracted casillas while enrolling nothing reported an
    unexplained zero, indistinguishable from a period with no receipt. Each case
    below reaches the same "no evidence" outcome by a different route, and the
    assertion is that the reasons are DISTINCT -- a branch that collapsed any two
    of them back together would still produce five notices and still pass a
    count-only check, so the set of reasons is what is compared.
    """
    reasons: dict[str, str] = {}
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        for case_id, mutate in _UNREACHED_JUSTIFICANTE_CASES:
            store = FiledDeclaracionObservationStore(tmp_path / f"unreached-{case_id}")
            observation = mutate(store)
            _seed_current_130_filing(bucket_id=bucket_id)

            result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

            assert result.justificante_csvs == (), case_id
            assert len(result.notices) == 1, case_id
            notice = result.notices[0]
            assert notice.severity is NoticeSeverity.WARNING, case_id
            assert notice.code == FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE, case_id
            assert notice.context is not None
            assert notice.context["expediente_id"] == observation.expediente_id, case_id
            reasons[case_id] = notice.context["reason"]

    # Derived from the enum, never a hand-listed copy of it: a member added
    # without a case here fails this assertion instead of going unwatched. Only
    # UNREADABLE_ARTEFACT is excluded, because reaching it means secure storage
    # failed to return bytes it holds, which this harness cannot stage without a
    # test double standing in for the real store.
    expected = {
        reason.value
        for reason in FiledJustificanteUnreachedReason
        if reason is not FiledJustificanteUnreachedReason.UNREADABLE_ARTEFACT
    }
    assert set(reasons.values()) == expected, reasons
    assert len(set(reasons.values())) == len(reasons), (
        f"two cases reported the same reason, so the outcomes are not distinguished: {reasons}"
    )


def test_an_enrollment_that_saves_evidence_raises_no_unreached_notice(tmp_path: Path) -> None:
    """The notice channel stays empty on the success path.

    Without this, a change emitting the notice unconditionally would still pass
    every case above while telling an operator that a successful enrollment
    reached no evidence.
    """
    with _profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = _stored_130_justificante_observation(store)
        _seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(observation, store=store, bucket_id=bucket_id)

    assert result.justificante_csvs == (_MODELO_130_FIXTURE_CSV,)
    assert result.notices == ()


def test_fixture_csv_constants_still_match_the_receipts() -> None:
    """The csvs the support helpers state independently are the csvs AEAT printed.

    The helpers deliberately do not read these out of the PDFs, because a URL
    built from the receipt's own csv would make every csv comparison in this
    module compare one value against itself. That independence costs a way to
    drift, and this is the anchor that catches the drift: replace a fixture and
    the constants stop describing it.
    """
    assert parse_justificante_bytes(_modelo_130_justificante_pdf_bytes()).csv == _MODELO_130_FIXTURE_CSV
    assert parse_justificante_bytes(_modelo_303_justificante_pdf_bytes()).csv == _MODELO_303_FIXTURE_CSV


def test_binding_prefill_refuses_incomplete_prior_filing_observation(tmp_path: Path) -> None:
    with _secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        repository.save(
            repository.prepare_observation_envelope(
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

    This is the point of the test, not a formality. The design deliberately adds
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
    here -- while adding a discovery-specific official kind, which this test
    settles against, fails.
    """
    official = {kind for kind in ObservationSourceKind if kind.is_official_aeat}
    assert official == {
        ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,
        ObservationSourceKind.AEAT_SEDE_LIVE_CAPTURE,
        ObservationSourceKind.AEAT_CSV_REGISTER,
    }
    assert not any("discover" in kind.value or "history" in kind.value for kind in ObservationSourceKind)
