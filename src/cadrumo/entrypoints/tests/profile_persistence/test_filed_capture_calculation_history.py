"""Filed AEAT observations feed the calculation history repository."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.inbound.justificante.parser import parse_justificante_bytes
from cadrumo.adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.justificante import JustificanteRepository
from cadrumo.adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from cadrumo.adapters.persistence.profile.tests.filed_capture_history_support import (
    CAPTURED_AT,
    M303_DECLARATION_TYPE_C,
    M303_DECLARATION_TYPE_I,
    M303_DISPONIBLE_CASILLA,
    M303_GENERADA_CASILLA,
    M303_POSTERIOR_CASILLA,
    MODELO_130_FIXTURE_CSV,
    MODELO_303_FIXTURE_CSV,
    SYNTHETIC_EXPEDIENTE_ID,
    SYNTHETIC_PROFILE_ID,
    filed_declaration,
    modelo_303_justificante_pdf_bytes,
    parsed_303_submitted_file_observation,
    prior_303_observation,
    profile_backend,
    registry_snapshot,
    secure_backend,
    seed_current_130_filing,
    stored_130_justificante_observation,
    stored_303_justificante_observation,
)
from cadrumo.adapters.persistence.storage.tests.secure_sql import read_db_at_rest_bytes
from cadrumo.application.calculations.binding_prefill import (
    extract_modelo_303_local_iva_compensation_recurrence,
    resolve_bindings_from_local_store,
)
from cadrumo.application.live.errors import LiveApplicationError, LiveApplicationInputError
from cadrumo.application.live.expedientes_ports import ExpedientesDeclaration
from cadrumo.application.live.filed_capture_finalizer import FiledCaptureFailurePolicy, finalize_filed_capture
from cadrumo.application.live.filed_observation_persistence import (
    enroll_filed_justificante_evidence,
    latest_declarations_by_period,
    persist_filed_calculation_observation,
    persistiva_compensation_history_observations_strict,
    select_latest_filed_observations_in_history_order,
)
from cadrumo.application.live.iva_remote_state import (
    list_iva_compensation_history,
)
from cadrumo.application.modelo.filing_chain_reconciliation import FilingReconciliationOutcome
from cadrumo.core.iva_compensation_provenance import IvaCompensationStateProvenance
from cadrumo.core.period import Period
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.iva_compensation.carry_forward import IvaCompensationPeriodState
from cadrumo.domain.modelos.filing_record import ExternalEvidence, ExternalEvidenceKind
from cadrumo.entrypoints.live_state_composition import compose_live_state

from .filed_capture_history_ports_support import FILED_OPERATION_STACK, SESSION_BUCKET_ID, filed_ports

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_filed_observation_capture_promotes_previous_303_into_recurrence_history(tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test, secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            prior_303_observation(pending_compensation=Decimal("1200.00")),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path, calculation_repository=repository),
        )

        target_snapshot = registry_snapshot("303", 2026, "2T")
        prefill = resolve_bindings_from_local_store(
            target_snapshot,
            repository=repository,
            captured_at=CAPTURED_AT,
            iva_history_repository=IvaCompensationHistoryRepository(),
            operation=_authority_operation_for_test,
        )
        recurrence, recurrence_prefill = extract_modelo_303_local_iva_compensation_recurrence(
            target_snapshot,
            repository=repository,
            captured_at=CAPTURED_AT,
            iva_history_repository=IvaCompensationHistoryRepository(),
            operation=_authority_operation_for_test,
        )

        assert calculation_key == "303:2026:1T"
        assert repository.load_observation("303", Period.from_year_and_code(2026, "1T")) is not None
        loaded = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))
        assert loaded is not None
        assert loaded.source_metadata == {
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": SYNTHETIC_EXPEDIENTE_ID,
            "authenticated_identity": SYNTHETIC_PROFILE_ID,
        }
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}
        assert prefill.prefilled[0].source_modelo == "303"
        assert prefill.prefilled[0].source_periods == ("1T",)
        assert recurrence is not None
        assert recurrence.amount == Decimal("1200.00")
        assert recurrence.source_periods == (Period.from_year_and_code(2026, "1T"),)
        assert recurrence_prefill.binding_values == prefill.binding_values


def test_filed_observation_capture_records_single_justificante_csv_metadata(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        observation = prior_303_observation(pending_compensation=Decimal("1200.00"))

        persist_filed_calculation_observation(
            observation,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path, calculation_repository=repository),
            justificante_csvs=("CSV30320261T",),
        )

        loaded = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))

    assert loaded is not None
    assert loaded.source_metadata == {
        "aeat_register_status": "ALTA",
        "aeat_expediente_id": SYNTHETIC_EXPEDIENTE_ID,
        "authenticated_identity": SYNTHETIC_PROFILE_ID,
        "aeat_justificante_csv": "CSV30320261T",
    }


def test_latest_filed_observation_capture_threads_justificante_csv_metadata(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        observation = prior_303_observation(pending_compensation=Decimal("1200.00"))

        keys = finalize_filed_capture(
            (observation,),
            justificante_csvs_by_observation={
                ("303", 2026, "1T", SYNTHETIC_EXPEDIENTE_ID): ("CSV30320261T",),
            },
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        ).calculation_observation_keys
        loaded = CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T"))

    assert keys == ("303:2026:1T",)
    assert loaded is not None
    assert loaded.source_metadata["aeat_justificante_csv"] == "CSV30320261T"


def test_filed_capture_best_effort_finalizer_reports_incomplete_observation(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        observation = prior_303_observation(pending_compensation=Decimal("1200.00")).model_copy(
            update={"extraction_coverage": {}},
        )

        finalization = finalize_filed_capture(
            (observation,),
            justificante_csvs_by_observation={},
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )

        stored = CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T"))

    assert finalization.calculation_observation_keys == ()
    assert len(finalization.failures) == 1
    assert finalization.failures[0].modelo == "303"
    assert finalization.failures[0].year == 2026
    assert finalization.failures[0].period == Period.from_year_and_code(2026, "1T")
    assert finalization.failures[0].expediente_id == SYNTHETIC_EXPEDIENTE_ID
    assert finalization.failures[0].error_type == "SedeParseError"
    assert "has no extraction coverage" in finalization.failures[0].message
    assert stored is None


def test_filed_capture_fail_fast_finalizer_raises_on_incomplete_observation(tmp_path: Path) -> None:
    """Single and source capture use FAIL_FAST: a registry-enrollment failure aborts."""
    with secure_backend(tmp_path):
        observation = prior_303_observation(pending_compensation=Decimal("1200.00")).model_copy(
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
                ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
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
        prior_303_observation(
            year=2026,
            period="1T",
            expediente_id="200030300000030Z",
            pending_compensation=Decimal("20.00"),
            presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
        ),
        prior_303_observation(
            year=2026,
            period="1T",
            expediente_id="200030300000031Z",
            status="BAJA",
            pending_compensation=Decimal("99.00"),
            presented_at=datetime(2026, 4, 25, 10, 0, 0, tzinfo=UTC),
        ),
        prior_303_observation(
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
    with secure_backend(tmp_path / "finalizer"):
        finalization = finalize_filed_capture(
            observations,
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path / "finalizer"),
        )

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
    the strict IVA path (``persistiva_compensation_history_observations_strict``)
    stays a separate function with its own reload-verification contract, so the
    two are not collapsed by the finalizer consolidation.
    """
    observation = prior_303_observation(
        pending_compensation=Decimal("5.00"),
        expediente_id="200030300000040Z",
        presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
    )
    with secure_backend(tmp_path):
        strict_keys = persistiva_compensation_history_observations_strict(
            (observation,),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )
        strict_history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

    assert strict_keys == ("303:2026:1T",)
    assert strict_history is not None
    assert finalize_filed_capture is not persistiva_compensation_history_observations_strict


def test_filed_observation_capture_promotes_cross_year_303_recurrence_history(tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test, secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        calculation_key = persist_filed_calculation_observation(
            prior_303_observation(
                year=2025,
                period="4T",
                pending_compensation=Decimal("450.00"),
                expediente_id="200030300000001Z",
            ),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path, calculation_repository=repository),
        )

        target_snapshot = registry_snapshot("303", 2026, "1T")
        prefill = resolve_bindings_from_local_store(
            target_snapshot,
            repository=repository,
            captured_at=CAPTURED_AT,
            iva_history_repository=IvaCompensationHistoryRepository(),
            operation=_authority_operation_for_test,
        )

        assert calculation_key == "303:2025:4T"
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}
        assert prefill.prefilled[0].source_filing_year == 2025
        assert prefill.prefilled[0].source_periods == ("4T",)


def test_binding_prefill_uses_profile_secure_iva_compensation_history(tmp_path: Path) -> None:
    with bundled_indexed_authority().operation() as _authority_operation_for_test, secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        history_repository = IvaCompensationHistoryRepository()
        history_repository.save_period(
            IvaCompensationPeriodState(
                provenance=IvaCompensationStateProvenance.AEAT_CAPTURE,
                taxpayer_nif=SYNTHETIC_PROFILE_ID,
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
                registry_snapshot_ref=registry_snapshot("303", 2026, "1T").snapshot_ref,
                expediente_id=SYNTHETIC_EXPEDIENTE_ID,
                status="ALTA",
                presented_at=CAPTURED_AT,
                prior_pending_amount=Decimal("2.34"),
                applied_amount=Decimal("1.23"),
                pending_for_later_amount=Decimal("8.90"),
                period_result_amount=Decimal("-4.32"),
                final_result_amount=Decimal("-4.32"),
                generated_amount=Decimal("4.32"),
                available_end_amount=Decimal("13.22"),
                source_observation_key=f"303:2026:1T:{SYNTHETIC_EXPEDIENTE_ID}",
                source_artefact_sha256=hashlib.sha256(b"synthetic-submitted-file").hexdigest(),
            ),
        )

        target_snapshot = registry_snapshot("303", 2026, "2T")
        prefill = resolve_bindings_from_local_store(
            target_snapshot,
            repository=repository,
            iva_history_repository=history_repository,
            captured_at=CAPTURED_AT,
            operation=_authority_operation_for_test,
        )

        assert repository.load_observation("303", Period.from_year_and_code(2026, "1T")) is None
        assert prefill.binding_values == {"modelo-303-compensacion-pendiente-anteriores": Decimal("13.22")}
        assert prefill.prefilled[0].source_modelo == "303"
        assert prefill.prefilled[0].source_filing_year == 2026
        assert prefill.prefilled[0].source_periods == ("1T",)


def test_iva_compensation_history_strict_persist_stores_latest_and_reloads(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        keys = persistiva_compensation_history_observations_strict(
            (
                prior_303_observation(
                    pending_compensation=Decimal("1.00"),
                    expediente_id="200030300000004Z",
                    presented_at=datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC),
                ),
                prior_303_observation(
                    pending_compensation=Decimal("2.00"),
                    expediente_id="200030300000005Z",
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
            ),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )

        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert keys == ("303:2026:1T",)
        assert history is not None
        assert history.expediente_id == "200030300000005Z"
        assert history.pending_for_later_amount == Decimal("2.00")


def test_direct_filed_observation_persist_refuses_non_alta_status(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        with pytest.raises(
            LiveApplicationInputError,
            match=r"application\.live\.filed_observations\.errors\.observation_not_active",
        ):
            persist_filed_calculation_observation(
                prior_303_observation(
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
                ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
            )

        assert CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T")) is None
        assert IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T")) is None


def test_filed_observation_capture_enrolls_matching_justificante_metadata(tmp_path: Path) -> None:
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)

        csvs = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        ).justificante_csvs

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
    receipt = parse_justificante_bytes(modelo_303_justificante_pdf_bytes())
    expediente_id = "202630300000411A"
    assert receipt.presentation_id is not None
    assert receipt.presentation_id.strip().casefold() != expediente_id.strip().casefold(), (
        "the receipt identifier and the register expediente id agree, so this fixture cannot "
        "show the divergence being tolerated"
    )

    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_303_justificante_observation(store, expediente_id=expediente_id)

        csvs = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        ).justificante_csvs

        assert csvs == (MODELO_303_FIXTURE_CSV,)
        loaded = JustificanteRepository().load(MODELO_303_FIXTURE_CSV)
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
    ("wrong-taxpayer", "X0001500M", MODELO_130_FIXTURE_CSV),
    ("csv-is-another-filings", "00000000T", "QQQQ7777WWWW3333"),
)


def test_filed_observation_capture_refuses_invalid_justificante_metadata(
    tmp_path: Path,
) -> None:
    for case_id, authenticated_identity, captured_csv in _REFUSED_JUSTIFICANTE_METADATA_CASES:
        case_root = tmp_path / case_id
        with profile_backend(case_root, tax_id=authenticated_identity) as bucket_id:
            store = FiledDeclaracionObservationStore(tmp_path / f"filed-declarations-{case_id}")
            observation = stored_130_justificante_observation(
                store,
                authenticated_identity=authenticated_identity,
                captured_csv=captured_csv,
            )

            csvs = enroll_filed_justificante_evidence(
                observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
            ).justificante_csvs

            assert csvs == (), case_id
            assert JustificanteRepository().load(MODELO_130_FIXTURE_CSV) is None, case_id


def test_filed_observation_capture_reconciles_a_matching_pending_filing_without_stamping_it(tmp_path: Path) -> None:
    """A receipt alone cannot show that the pending local filing is what AEAT holds.

    The matching receipt is enrolled and reconciled with the in-force pending
    filing; Modelo 130 declares no receipt-total comparison, so the filing stays
    unconfirmed and the reconciliation is recorded as unverifiable.
    """
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)
        filing = seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )

        assert result.justificante_csvs == ("ABCD1234EFGH5678",)
        assert result.filing_record_ids == ()
        assert [(item.outcome, item.filing_record_id) for item in result.reconciliation_results] == [
            (FilingReconciliationOutcome.UNVERIFIABLE, filing.filing_record_id),
        ]
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
        events = [
            event
            for event in BucketEventHistoryRepository().load().events.values()
            if event.event_type is BucketEventType.MODELO_FILING_RECONCILED
        ]
        assert len(events) == 1
        assert events[0].bucket_id == bucket_id
        assert events[0].actor == "aeat-filed-history"
        assert events[0].object_id == filing.filing_record_id
        assert events[0].payload["outcome"] == "unverifiable"
        assert events[0].payload["aeat_expediente_id"] == observation.expediente_id


def test_filed_observation_capture_keeps_existing_justificante_pdf_evidence_for_same_csv(tmp_path: Path) -> None:
    """An incomparable repeated receipt retains the whole existing filing and its audit history."""
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)
        filing = seed_current_130_filing(
            bucket_id=bucket_id,
            aeat_accepted=True,
            external_evidence=ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                reference_id="ABCD1234EFGH5678",
                imported_at=CAPTURED_AT,
            ),
        )
        events_before = BucketEventHistoryRepository().load()

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )

        assert result.justificante_csvs == (MODELO_130_FIXTURE_CSV,)
        assert result.filing_record_ids == ()
        assert result.conflicting_filing_record_ids == ()
        assert [(item.outcome, item.filing_record_id) for item in result.reconciliation_results] == [
            (FilingReconciliationOutcome.UNVERIFIABLE, filing.filing_record_id),
        ]
        assert [notice.code.value for notice in result.reconciliation_results[0].notices] == [
            "receipt_totals_not_reconciled",
        ]
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
        assert current == filing
        assert current is not None
        assert current.external_evidence is not None
        assert current.external_evidence.kind is ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF
        assert current.external_evidence.reference_id == "ABCD1234EFGH5678"
        assert BucketEventHistoryRepository().load() == events_before


def test_filed_observation_capture_keeps_existing_csv_register_evidence_for_same_csv_case_insensitive(
    tmp_path: Path,
) -> None:
    """CSV case folding identifies the recorded filing without bypassing content comparison."""
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)
        filing = seed_current_130_filing(
            bucket_id=bucket_id,
            aeat_accepted=True,
            external_evidence=ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                reference_id="abcd1234efgh5678",
                imported_at=CAPTURED_AT,
            ),
        )
        events_before = BucketEventHistoryRepository().load()

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )

        assert result.justificante_csvs == (MODELO_130_FIXTURE_CSV,)
        assert result.filing_record_ids == ()
        assert result.conflicting_filing_record_ids == ()
        assert [(item.outcome, item.filing_record_id) for item in result.reconciliation_results] == [
            (FilingReconciliationOutcome.UNVERIFIABLE, filing.filing_record_id),
        ]
        assert [notice.code.value for notice in result.reconciliation_results[0].notices] == [
            "receipt_totals_not_reconciled",
        ]
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
        assert current == filing
        assert current is not None
        assert current.external_evidence is not None
        assert current.external_evidence.kind is ExternalEvidenceKind.AEAT_CSV_REGISTER
        assert current.external_evidence.reference_id == "abcd1234efgh5678"
        assert BucketEventHistoryRepository().load() == events_before


def test_filed_observation_capture_leaves_a_different_confirmed_filing_untouched(tmp_path: Path) -> None:
    """A receipt for another presentation cannot be recorded without its content."""
    with profile_backend(tmp_path, tax_id="00000000T") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)
        filing = seed_current_130_filing(
            bucket_id=bucket_id,
            aeat_accepted=True,
            external_evidence=ExternalEvidence(
                kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                reference_id="DIFFERENTCSV12345",
                imported_at=CAPTURED_AT,
            ),
        )

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )

        assert result.filing_record_ids == ()
        assert result.conflicting_filing_record_ids == ()
        assert [(item.outcome, item.filing_record_id) for item in result.reconciliation_results] == [
            (FilingReconciliationOutcome.UNVERIFIABLE, filing.filing_record_id),
        ]
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
    with profile_backend(tmp_path, tax_id="X0001500M") as bucket_id:
        store = FiledDeclaracionObservationStore(tmp_path / "filed-declarations")
        observation = stored_130_justificante_observation(store)
        seed_current_130_filing(bucket_id=bucket_id)

        result = enroll_filed_justificante_evidence(
            observation, ports=filed_ports(bucket_id=bucket_id, root=tmp_path), bucket_id=bucket_id
        )

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
            filed_declaration(
                period="1T",
                expediente_id="200030300000006Z",
                estado="BAJA",
                presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
            ),
            filed_declaration(
                period="1T",
                expediente_id="200030300000007Z",
                estado="ALTA",
                presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
            ),
            filed_declaration(
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
    annual = filed_declaration(
        period="0A",
        expediente_id="200039000000020Z",
        estado="ALTA",
        presented_at=datetime(2027, 1, 30, 10, 0, 0, tzinfo=UTC),
    ).model_copy(update={"modelo": "390"})
    selected = latest_declarations_by_period(
        (
            annual,
            filed_declaration(
                period="4T",
                expediente_id="200030300000019Z",
                estado="ALTA",
                presented_at=datetime(2027, 1, 20, 10, 0, 0, tzinfo=UTC),
            ),
        ),
    )

    assert tuple(row.period.registry_token for row in selected) == ("4T", "0A")


def test_filed_history_keeps_non_iva_numeric_period_order_alongside_iva_rows() -> None:
    def declaration_for(modelo: str, period: str, expediente_id: str) -> ExpedientesDeclaration:
        return filed_declaration(
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
    with secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        keys = finalize_filed_capture(
            (
                prior_303_observation(
                    expediente_id="200030300000012Z",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
                prior_303_observation(
                    expediente_id="200030300000013Z",
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
            ),
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
            ports=filed_ports(
                bucket_id=SESSION_BUCKET_ID,
                root=tmp_path,
                calculation_repository=repository,
            ),
        ).calculation_observation_keys

        stored = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))
        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert keys == ("303:2026:1T",)
        assert stored is not None
        assert stored.observation.casilla_values[M303_DISPONIBLE_CASILLA] == Decimal("1200.00")
        assert history is not None
        assert history.expediente_id == "200030300000012Z"


def test_iva_history_strict_persist_promotes_alta_over_later_non_alta_observation(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        keys = persistiva_compensation_history_observations_strict(
            (
                prior_303_observation(
                    expediente_id="200030300000014Z",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
                prior_303_observation(
                    expediente_id="200030300000015Z",
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
            ),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )

        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert keys == ("303:2026:1T",)
        assert history is not None
        assert history.expediente_id == "200030300000014Z"
        assert history.pending_for_later_amount == Decimal("1200.00")


def test_iva_history_strict_persist_ignores_non_alta_only_period(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        keys = persistiva_compensation_history_observations_strict(
            (
                prior_303_observation(
                    expediente_id="200030300000016Z",
                    pending_compensation=Decimal("900.00"),
                    status="BAJA",
                    presented_at=datetime(2026, 4, 22, 10, 0, 0, tzinfo=UTC),
                ),
            ),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )

        assert keys == ()
        assert IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T")) is None
        assert CalculationObservationRepository().load_observation("303", Period.from_year_and_code(2026, "1T")) is None


def test_iva_history_strict_persist_refuses_non_303_before_writing(tmp_path: Path) -> None:
    non_303 = prior_303_observation(pending_compensation=Decimal("900.00")).model_copy(
        update={"modelo": "130"},
    )

    with secure_backend(tmp_path):
        with pytest.raises(LiveApplicationInputError) as error:
            persistiva_compensation_history_observations_strict(
                (non_303,),
                ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
            )

        assert error.value.translated_message == "live.errors.iva_history_modelo_303_only"
        assert error.value.context == {"modelo": "130"}
        assert IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T")) is None


def test_duplicate_period_capture_promotes_latest_filing_to_calculation_history(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        repository = CalculationObservationRepository()
        finalize_filed_capture(
            (
                prior_303_observation(
                    expediente_id="200030300000002Z",
                    pending_compensation=Decimal("800.00"),
                    presented_at=datetime(2026, 4, 19, 10, 0, 0, tzinfo=UTC),
                ),
                prior_303_observation(
                    expediente_id="200030300000003Z",
                    pending_compensation=Decimal("1200.00"),
                    presented_at=datetime(2026, 4, 20, 10, 0, 0, tzinfo=UTC),
                ),
            ),
            policy=FiledCaptureFailurePolicy.BEST_EFFORT,
            ports=filed_ports(
                bucket_id=SESSION_BUCKET_ID,
                root=tmp_path,
                calculation_repository=repository,
            ),
        )

        stored = repository.load_observation("303", Period.from_year_and_code(2026, "1T"))

        assert stored is not None
        assert stored.observation.casilla_values[M303_DISPONIBLE_CASILLA] == Decimal("1200.00")


def test_filed_303_capture_persists_secure_iva_compensation_history(tmp_path: Path) -> None:
    with secure_backend(tmp_path) as db_path:
        prior_pending = Decimal("19.99")
        applied = Decimal("3.21")
        pending_later = Decimal("7.89")
        period_result = Decimal("-4.56")
        final_result = Decimal("-4.56")
        key = persist_filed_calculation_observation(
            prior_303_observation(
                pending_compensation=pending_later,
                prior_pending=prior_pending,
                applied=applied,
                result=period_result,
                final_result=final_result,
                expediente_id=SYNTHETIC_EXPEDIENTE_ID,
                headers=(M303_DECLARATION_TYPE_C,),
            ),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )

        history = IvaCompensationHistoryRepository().load_period(Period.from_year_and_code(2026, "1T"))

        assert key == "303:2026:1T"
        assert history is not None
        assert history.taxpayer_nif == SYNTHETIC_PROFILE_ID
        assert history.expediente_id == SYNTHETIC_EXPEDIENTE_ID
        assert history.prior_pending_amount == prior_pending
        assert history.applied_amount == applied
        assert history.pending_for_later_amount == pending_later
        assert history.period_result_amount == period_result
        assert history.final_result_amount == final_result
        assert history.source_artefact_sha256 == hashlib.sha256(b"303-2026-1T-submitted-file").hexdigest()
        assert history.source_observation_key == f"303:2026:1T:{SYNTHETIC_EXPEDIENTE_ID}"

        listed = list_iva_compensation_history(
            ports=compose_live_state(
                output_root=tmp_path,
                bucket_id=SESSION_BUCKET_ID,
                operation=FILED_OPERATION_STACK.enter_context(bundled_indexed_authority().operation()),
            ).iva_remote_state_port,
        )
        assert listed.row_count == 1
        assert not hasattr(listed.rows[0], "taxpayer_nif")

        database_bytes = read_db_at_rest_bytes(db_path)
        assert SYNTHETIC_PROFILE_ID.encode("utf-8") not in database_bytes
        assert SYNTHETIC_EXPEDIENTE_ID.encode("utf-8") not in database_bytes


def test_filed_303_capture_accepts_canonical_compensation_casilla_ids(tmp_path: Path) -> None:
    pending_compensation = Decimal("11.00")
    prior_pending = Decimal("15.00")
    applied = Decimal("4.00")
    period_result = Decimal("-2.50")
    generated = Decimal("2.50")
    expected_available_end = pending_compensation + generated
    with secure_backend(tmp_path):
        key = persist_filed_calculation_observation(
            prior_303_observation(
                pending_compensation=pending_compensation,
                prior_pending=prior_pending,
                applied=applied,
                result=period_result,
                final_result=period_result,
                generated=generated,
                headers=(M303_DECLARATION_TYPE_C,),
            ),
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
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
        assert stored.observation.casilla_values[M303_DISPONIBLE_CASILLA] == expected_available_end
        available = next(item for item in stored.observation.observations if item.casilla_id == M303_DISPONIBLE_CASILLA)
        assert available.formula_id == "modelo-303-compensacion-disponible-fin-periodo"
        assert available.operand_casilla_refs == (M303_POSTERIOR_CASILLA, M303_GENERADA_CASILLA)
        assert available.operand_values == (pending_compensation, generated)


def test_multiyear_303_submitted_file_parser_promotes_sanitized_iva_history(tmp_path: Path) -> None:
    with secure_backend(tmp_path):
        observations = (
            parsed_303_submitted_file_observation(
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
            parsed_303_submitted_file_observation(
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
            parsed_303_submitted_file_observation(
                year=2026,
                period="2T",
                expediente_id="200030300000011Z",
                presented_at=datetime(2026, 7, 20, 10, 0, 0, tzinfo=UTC),
                casilla_110=Decimal("170.00"),
                casilla_78=Decimal("20.00"),
                casilla_87=Decimal("100.00"),
                casilla_69=Decimal("25.00"),
                casilla_71=Decimal("25.00"),
                headers=(M303_DECLARATION_TYPE_I,),
            ),
        )

        keys = persistiva_compensation_history_observations_strict(
            observations,
            ports=filed_ports(bucket_id=SESSION_BUCKET_ID, root=tmp_path),
        )
        history = list_iva_compensation_history(
            ports=compose_live_state(
                output_root=tmp_path,
                bucket_id=SESSION_BUCKET_ID,
                operation=FILED_OPERATION_STACK.enter_context(bundled_indexed_authority().operation()),
            ).iva_remote_state_port,
            as_of_year=2026,
        )

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
