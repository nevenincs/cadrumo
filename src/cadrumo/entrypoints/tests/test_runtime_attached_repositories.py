"""Runtime-attached repository defaults refuse missing sessions and isolate profile writes."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest

from cadrumo.adapters.persistence.profile.auth_diagnostics import build_auth_diagnostic_persistence
from cadrumo.adapters.persistence.profile.calculation_observations import (
    CalculationObservationRepository,
    IvaWalletDecisionRepository,
)
from cadrumo.adapters.persistence.profile.iva_compensation_history import IvaCompensationHistoryRepository
from cadrumo.adapters.persistence.profile.review_package_recipient_registry import RecipientFingerprintRegistryAdapter
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ...adapters.outbound.aeat.auth import session_store
from ...adapters.outbound.aeat.sede.errors import ExpedienteNotFoundError
from ...adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
from ...adapters.outbound.google import session_store as google_session_store
from ...adapters.outbound.google.tests import session_records as google_session_records
from ...adapters.persistence.llm.cache import LLMCache
from ...adapters.persistence.llm.consent_ledger import EvidenceConsentLedger
from ...adapters.persistence.llm.run_records import LLMRunRecorder
from ...adapters.persistence.llm.usage import UsageRecorder
from ...adapters.persistence.profile.apoderado import build_apoderado_config_repository
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ...adapters.persistence.profile.filing_history import FilingHistoryRepositoryAdapter
from ...adapters.persistence.profile.inventory import InventoryLedgerRepository
from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...adapters.persistence.profile.justificante import JustificanteRepository
from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ...adapters.persistence.profile.recipient_replay_guard import RecipientReplayGuardRepository
from ...adapters.persistence.profile.submission import SubmissionRepository
from ...adapters.persistence.profile.tests.wallet_history import load_decision_history
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.profile.usage_ratios import load_usage_ratios, save_usage_ratios_with_secure_object_writes
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.errors import StorageValidationError
from ...adapters.persistence.storage.master_key.active_session import activate_session
from ...adapters.persistence.storage.runtime_readiness import StorageRuntimeReadinessCode
from ...adapters.persistence.storage.runtime_repository import (
    secure_object_repository_for_active_bucket_or_default_route,
    secure_object_repository_for_bucket,
)
from ...adapters.persistence.storage.secure_object_namespaces import LLM_USAGE_NAMESPACE
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...application.auth.diagnostics import list_auth_diagnostics
from ...application.auth.diagnostics_ports import AuthDiagnosticPersistenceError
from ...application.calculations.observations_repository import ResultDispositionProjection
from ...application.diagnostics import (
    preview_quarantine_unreadable_secure_objects,
    secure_object_unreadable_total,
)
from ...application.diagnostics_ports import (
    DiagnosticSecureObjectNamespace,
    DiagnosticSessionFailureClassifier,
    DiagnosticsPorts,
)
from ...application.filing.history_ports import FilingHistoryPorts
from ...application.filing.history_repository import ModeloHistoryRepository
from ...application.workflow.persistence import WorkflowRunRepository, WorkflowStateRepository
from ...core.config import load_settings, override_settings
from ...core.config_support import LLMProvider
from ...core.period import Period
from ...core.result_disposition import ResultDisposition
from ...domain.attachments.errors import AttachmentNotFoundError
from ...domain.buckets.event import BucketEventHistoryCatalogue
from ...domain.calculations.registry.bindings import CasillaObservation, RegistryModeloObservation
from ...domain.calculations.registry.casilla_membership import casillas_by_id
from ...domain.calculations.registry.iva_compensation_annual_partition_bindings import (
    M303_COMPENSATION_RESULTADO_CASILLA,
)
from ...domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...domain.calculations.registry.tests.published_authority import published_snapshot
from ...domain.contribuyente.inventory.records import InventoryLedgerDocument
from ...domain.modelos.work_unit import WorkUnitCatalogue
from ...domain.transactions.models import TransactionCatalogue
from ...domain.usage_ratios.model import UsageRatioProfile
from ...tests.log_records import delivered_text
from ..adapter_composition_ports import build_borrador_100_snapshot_repository
from .runtime_attached_repositories_support import (
    BUCKET_A_ATTACHMENT_PAYLOAD,
    BUCKET_A_ID,
    BUCKET_B_ATTACHMENT_PAYLOAD,
    BUCKET_B_ID,
    WALLET_SUBJECT_ID,
    active_runtime,
    borrador_snapshot,
    bucket_event,
    calculation_catalogue,
    filing_record_catalogue,
    google_records,
    history,
    inventory_ledger,
    invoice,
    iva_state,
    iva_wallet_decision,
    justificante,
    llm_request,
    llm_response,
    modelo_draft,
    runtime_attached_repositories_hex,
    runtime_attached_repositories_transaction,
    save_auth_diagnostic,
    save_diagnostic_probe_row,
    sede_artefact,
    session,
    storage_state,
    submission,
    usage_profile,
    usage_record,
    verification_catalogue,
    work_unit,
    workflow_run,
    workflow_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_YEAR = filing_year_envelope().horizon


class _StorageDiagnosticsPort:
    """Translate the real storage repository for this outward adapter test."""

    @staticmethod
    def _repository() -> SecureObjectRepository:
        return secure_object_repository_for_active_bucket_or_default_route()

    @staticmethod
    def _translate(row) -> DiagnosticSecureObjectNamespace:
        return DiagnosticSecureObjectNamespace(
            namespace=row.namespace,
            readable=row.readable,
            unreadable=row.unreadable,
        )

    def list_namespaces(self) -> tuple[str, ...]:
        return self._repository().list_namespaces()

    def probe_namespace_integrity(self, namespace: str) -> DiagnosticSecureObjectNamespace:
        return self._translate(self._repository().probe_namespace_integrity(namespace))

    def quarantine_unreadable_rows(self) -> tuple[DiagnosticSecureObjectNamespace, ...]:
        return tuple(self._translate(row) for row in self._repository().quarantine_unreadable_rows())


class _EmptySessionFailureClassifier(DiagnosticSessionFailureClassifier):
    """Classify the empty test repository without widening the diagnostics port."""

    @override
    def __call__(self, error: BaseException) -> bool:
        del error
        return False


def _diagnostics_ports() -> DiagnosticsPorts:
    """Provide the required application diagnostic capability bundle."""
    return DiagnosticsPorts(
        secure_object_repository=_StorageDiagnosticsPort(),
        session_failure_classifier=_EmptySessionFailureClassifier(),
    )


def _load_usage_ratios_for_test(*, bucket_id: str) -> UsageRatioProfile:
    with bundled_indexed_authority().operation() as operation:
        return load_usage_ratios(bucket_id=bucket_id, operation=operation)


_RUNTIME_DEFAULT_REFUSAL_CASES: tuple[tuple[str, Callable[[], object]], ...] = (
    ("workflow_state", lambda: WorkflowStateRepository().load()),
    ("workflow_runs", lambda: WorkflowRunRepository().list()),
    ("bucket_events", lambda: BucketEventHistoryRepository().load()),
    (
        "auth_diagnostics",
        lambda: list_auth_diagnostics(persistence=build_auth_diagnostic_persistence()),
    ),
    (
        "auth_apoderado",
        lambda: build_apoderado_config_repository(bucket_id=BUCKET_A_ID, settings=load_settings()),
    ),
    ("auth_session", lambda: session_store.load(Path("/profile/active/aeat-session"))),
    ("google_oauth_token", lambda: google_session_store.load_token("operator-google")),
    ("google_oauth_metadata", lambda: google_session_store.load_metadata("operator-google")),
    ("google_drive_config", lambda: google_session_store.load_drive_config("operator-google")),
    ("llm_cache_stats", lambda: LLMCache(root_dir=Path("runtime-cache")).stats()),
    ("llm_usage_load", lambda: UsageRecorder(root_dir=Path("runtime-usage")).load_records()),
    ("llm_run_telemetry", lambda: LLMRunRecorder(root_dir=Path("runtime-run-record")).load_records()),
    ("llm_consent_ledger", lambda: EvidenceConsentLedger().load_entries()),
    (
        "review_recipient_registry",
        lambda: RecipientFingerprintRegistryAdapter(
            repository=secure_object_repository_for_active_bucket_or_default_route(),
        ).load(),
    ),
    ("review_recipient_replay_guard", lambda: RecipientReplayGuardRepository().load()),
    (
        "sede_artefact",
        lambda: FiledDeclaracionObservationStore(Path("sede-cache")).load_artefact(
            "secure-object:financial:" + "a" * 64,
        ),
    ),
    (
        "sede_observation",
        lambda: FiledDeclaracionObservationStore(Path("sede-cache")).load_observation(Path("observation")),
    ),
    ("attachment", lambda: AttachmentStore().read_bytes("a" * 64)),
    ("transactions", lambda: TransactionCatalogueRepository(bucket_id=BUCKET_A_ID).load()),
    ("invoices", lambda: InvoiceCatalogueRepository().load()),
    ("filing_drafts", lambda: ModeloDraftRepository(bucket_id=BUCKET_A_ID).load("d" * 64)),
    ("submission", lambda: SubmissionRepository().list_submission_ids()),
    ("justificante", lambda: tuple(sorted(JustificanteRepository().iter_ids()))),
    (
        "filing_history",
        lambda: ModeloHistoryRepository(
            ports=FilingHistoryPorts(
                repository=FilingHistoryRepositoryAdapter(objects=secure_object_repository_for_bucket(BUCKET_A_ID)),
                bucket_id=BUCKET_A_ID,
            ),
        ).list_modelos(),
    ),
    ("modelo_work_units", lambda: WorkUnitCatalogueRepository(bucket_id=BUCKET_A_ID).load()),
    ("modelo_calculation_revisions", lambda: CalculationRevisionCatalogueRepository(bucket_id=BUCKET_A_ID).load()),
    ("modelo_filing_records", lambda: ModeloRecordCatalogueRepository(bucket_id=BUCKET_A_ID).load()),
    ("modelo_verification_reports", lambda: VerificationReportCatalogueRepository(bucket_id=BUCKET_A_ID).load()),
    (
        "calculation_observations",
        lambda: CalculationObservationRepository(bucket_id=BUCKET_A_ID).load_observation(
            "303",
            Period.from_year_and_code(_YEAR, "1T"),
        ),
    ),
    ("iva_wallet_decisions", lambda: IvaWalletDecisionRepository().list_decisions()),
    (
        "iva_wallet_decision_history",
        lambda: load_decision_history(
            IvaWalletDecisionRepository(), WALLET_SUBJECT_ID, Period.from_year_and_code(_YEAR, "2T")
        ),
    ),
    ("iva_compensation_history", lambda: IvaCompensationHistoryRepository(bucket_id=BUCKET_A_ID).list_periods()),
    ("usage_ratios", lambda: _load_usage_ratios_for_test(bucket_id=BUCKET_A_ID)),
    (
        "borrador_100_snapshot",
        lambda: build_borrador_100_snapshot_repository(bucket_id=BUCKET_A_ID).list_snapshots(),
    ),
    ("profile_inventory", lambda: InventoryLedgerRepository().load()),
)


def test_current_runtime_defaults_refuse_missing_session(tmp_path: Path) -> None:
    """Every runtime default refuses, and names the readiness code that stopped it.

    The refusal is localised, so its rendered prose belongs to the locale
    catalogues rather than to this assertion. The typed readiness code in the
    error context is the contract, and pinning it discriminates *which* refusal
    fired -- a prose match would pass equally on a route mismatch.
    """
    for case_name, operation in _RUNTIME_DEFAULT_REFUSAL_CASES:
        with (
            override_settings(cadrumo_storage_root=tmp_path / case_name, cadrumo_active_profile=BUCKET_A_ID),
            pytest.raises((StorageValidationError, AuthDiagnosticPersistenceError)) as raised,
        ):
            operation()
        refusal = _storage_readiness_refusal(raised.value, case_name)
        assert refusal.translated_message == "errors.storage.runtime.not_ready", case_name
        assert refusal.context is not None, case_name
        assert refusal.context["readiness_code"] == StorageRuntimeReadinessCode.NO_ACTIVE_SESSION.value, case_name


def test_current_runtime_defaults_refuse_route_session_mismatch(tmp_path: Path) -> None:
    """A session serving another bucket refuses with the mismatch code, not the absence one."""
    for case_name, operation in _RUNTIME_DEFAULT_REFUSAL_CASES:
        with (
            override_settings(cadrumo_storage_root=tmp_path / case_name, cadrumo_active_profile=BUCKET_A_ID),
            activate_session(session(BUCKET_B_ID)),
            pytest.raises((StorageValidationError, AuthDiagnosticPersistenceError)) as raised,
        ):
            operation()
        refusal = _storage_readiness_refusal(raised.value, case_name)
        assert refusal.translated_message == "errors.storage.runtime.not_ready", case_name
        assert refusal.context is not None, case_name
        expected = StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH.value
        assert refusal.context["readiness_code"] == expected, case_name


def _storage_readiness_refusal(error: BaseException, case_name: str) -> StorageValidationError:
    """Return the storage readiness refusal, beneath a port that translates storage errors."""
    refusal = error.__cause__ if isinstance(error, AuthDiagnosticPersistenceError) else error
    assert isinstance(refusal, StorageValidationError), case_name
    return refusal


def test_diagnostics_secure_object_total_degrades_on_missing_session(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="cadrumo.application.diagnostics")

    with override_settings(cadrumo_storage_root=tmp_path, cadrumo_active_profile=BUCKET_A_ID):
        # Pin the precondition through the typed refusal the probe swallows.
        # The degrade log renders the error's translation key, which is shared
        # by every unready state, so asserting on the log alone would not
        # distinguish this test from its route-mismatch sibling below.
        with pytest.raises(StorageValidationError) as raised:
            secure_object_repository_for_active_bucket_or_default_route()
        assert raised.value.context is not None
        assert raised.value.context["readiness_code"] == StorageRuntimeReadinessCode.NO_ACTIVE_SESSION.value

        assert secure_object_unreadable_total(ports=_diagnostics_ports()) == 0

    logged = delivered_text(caplog)
    assert "secure objects engine unreachable for repair probe" in logged
    assert "errors.storage.runtime.not_ready" in logged


def test_diagnostics_secure_object_total_degrades_on_route_session_mismatch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="cadrumo.application.diagnostics")

    with (
        override_settings(cadrumo_storage_root=tmp_path, cadrumo_active_profile=BUCKET_A_ID),
        activate_session(session(BUCKET_B_ID)),
    ):
        # See the sibling above: the route mismatch is what must be shown to
        # have caused the degrade, and only the typed code discriminates it.
        with pytest.raises(StorageValidationError) as raised:
            secure_object_repository_for_active_bucket_or_default_route()
        assert raised.value.context is not None
        assert raised.value.context["readiness_code"] == StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH.value

        assert secure_object_unreadable_total(ports=_diagnostics_ports()) == 0

    logged = delivered_text(caplog)
    assert "secure objects engine unreachable for repair probe" in logged
    assert "errors.storage.runtime.not_ready" in logged


def test_workflow_state_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with active_runtime(tmp_path, BUCKET_A_ID):
        WorkflowStateRepository().save(workflow_state(BUCKET_A_ID))

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert WorkflowStateRepository().load().invoice_reviews == {}
        WorkflowStateRepository().save(workflow_state(BUCKET_B_ID))
        assert WorkflowStateRepository().load().ledger_reviews == {}

    with active_runtime(tmp_path, BUCKET_A_ID):
        loaded = WorkflowStateRepository().load()

    assert loaded.invoice_reviews == {}
    assert loaded.ledger_reviews == {}


def test_auth_session_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    logical_path = Path("/profile/active/aeat-session")

    with active_runtime(tmp_path, BUCKET_A_ID):
        session_store.save(
            logical_path,
            storage_state=storage_state(BUCKET_A_ID),
            metadata={"profile": BUCKET_A_ID},
        )

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert session_store.load(logical_path) is None
        session_store.save(
            logical_path,
            storage_state=storage_state(BUCKET_B_ID),
            metadata={"profile": BUCKET_B_ID},
        )

    with active_runtime(tmp_path, BUCKET_A_ID):
        loaded = session_store.load(logical_path)

    assert loaded is not None
    assert loaded.metadata == {"profile": BUCKET_A_ID}
    cookies = loaded.storage_state["cookies"]
    assert isinstance(cookies, list)
    first_cookie = cookies[0]
    assert isinstance(first_cookie, dict)
    assert first_cookie["value"] == BUCKET_A_ID


def test_transaction_repository_default_isolates_bucket_writes(tmp_path: Path) -> None:
    with active_runtime(tmp_path, BUCKET_A_ID):
        repo = TransactionCatalogueRepository(bucket_id=BUCKET_A_ID)
        repo.save(TransactionCatalogue.from_transactions((runtime_attached_repositories_transaction(BUCKET_A_ID),)))

    with active_runtime(tmp_path, BUCKET_B_ID):
        repo = TransactionCatalogueRepository(bucket_id=BUCKET_B_ID)
        assert len(repo.load().transactions) == 0
        repo.save(TransactionCatalogue.from_transactions((runtime_attached_repositories_transaction(BUCKET_B_ID),)))

    with active_runtime(tmp_path, BUCKET_A_ID):
        loaded = TransactionCatalogueRepository(bucket_id=BUCKET_A_ID).load()

    assert len(loaded.transactions) == 1
    transaction = next(iter(loaded.transactions.values()))
    assert transaction.raw.description == f"runtime attached repository {BUCKET_A_ID}"


def test_attachment_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with active_runtime(tmp_path, BUCKET_A_ID):
        digest_a = AttachmentStore().put_bytes(BUCKET_A_ATTACHMENT_PAYLOAD)

    with active_runtime(tmp_path, BUCKET_B_ID):
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_a)
        digest_b = AttachmentStore().put_bytes(BUCKET_B_ATTACHMENT_PAYLOAD)
        assert AttachmentStore().read_bytes(digest_b) == BUCKET_B_ATTACHMENT_PAYLOAD

    with active_runtime(tmp_path, BUCKET_A_ID):
        assert AttachmentStore().read_bytes(digest_a) == BUCKET_A_ATTACHMENT_PAYLOAD
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_b)


def test_event_and_workflow_run_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    event_a = bucket_event(BUCKET_A_ID)
    event_b = bucket_event(BUCKET_B_ID)

    with active_runtime(tmp_path, BUCKET_A_ID):
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_a.event_id: event_a}))
        WorkflowRunRepository().save(workflow_run(BUCKET_A_ID), runs_dir=tmp_path / "runs-a")

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert BucketEventHistoryRepository().load().events == {}
        assert WorkflowRunRepository().list() == ()
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_b.event_id: event_b}))
        WorkflowRunRepository().save(workflow_run(BUCKET_B_ID), runs_dir=tmp_path / "runs-b")

    with active_runtime(tmp_path, BUCKET_A_ID):
        events = BucketEventHistoryRepository().load().events
        runs = WorkflowRunRepository().list()

    assert tuple(events) == (event_a.event_id,)
    assert [(run.run_id, run.summary_locale_key) for run in runs] == [
        (
            runtime_attached_repositories_hex(f"workflow-run-{BUCKET_A_ID}")[:16],
            "application.workflow.results.completed",
        )
    ]


def test_domain_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    draft_a = modelo_draft(BUCKET_A_ID)
    draft_b = modelo_draft(BUCKET_B_ID)
    submission_a = submission(BUCKET_A_ID)
    submission_b = submission(BUCKET_B_ID)
    justificante_a = justificante(tmp_path, BUCKET_A_ID)
    justificante_b = justificante(tmp_path, BUCKET_B_ID)

    with active_runtime(tmp_path, BUCKET_A_ID):
        InvoiceCatalogueRepository().save(build_invoice_catalogue((invoice(BUCKET_A_ID),)))
        ModeloDraftRepository(bucket_id=BUCKET_A_ID).save(draft_a)
        SubmissionRepository().save(submission_a)
        JustificanteRepository().save(justificante_a)

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert InvoiceCatalogueRepository().load().invoices == {}
        assert ModeloDraftRepository(bucket_id=BUCKET_B_ID).load(draft_a.draft_id) is None
        assert SubmissionRepository().list_submission_ids() == ()
        assert tuple(sorted(JustificanteRepository().iter_ids())) == ()
        InvoiceCatalogueRepository().save(build_invoice_catalogue((invoice(BUCKET_B_ID),)))
        ModeloDraftRepository(bucket_id=BUCKET_B_ID).save(draft_b)
        SubmissionRepository().save(submission_b)
        JustificanteRepository().save(justificante_b)

    with active_runtime(tmp_path, BUCKET_A_ID):
        invoices = InvoiceCatalogueRepository().load().invoices
        loaded_draft_a = ModeloDraftRepository(bucket_id=BUCKET_A_ID).load(draft_a.draft_id)
        loaded_draft_b = ModeloDraftRepository(bucket_id=BUCKET_A_ID).load(draft_b.draft_id)
        submissions = SubmissionRepository().list_submission_ids()
        csvs = tuple(sorted(JustificanteRepository().iter_ids()))

    assert tuple(invoice.invoice_number for invoice in invoices.values()) == (f"INV-{BUCKET_A_ID.upper()}",)
    assert loaded_draft_a == draft_a
    assert loaded_draft_b is None
    assert submissions == (submission_a.submission_id,)
    assert csvs == (justificante_a.csv,)


def test_modelo_catalogue_defaults_isolate_bucket_writes(tmp_path: Path) -> None:
    work_a = work_unit(BUCKET_A_ID, BUCKET_A_ID)
    work_b = work_unit(BUCKET_B_ID, BUCKET_B_ID)
    calc_a = calculation_catalogue(BUCKET_A_ID)
    calc_b = calculation_catalogue(BUCKET_B_ID)
    filing_a = filing_record_catalogue(BUCKET_A_ID, BUCKET_A_ID)
    filing_b = filing_record_catalogue(BUCKET_B_ID, BUCKET_B_ID)
    verification_a = verification_catalogue(BUCKET_A_ID)
    verification_b = verification_catalogue(BUCKET_B_ID)

    with active_runtime(tmp_path, BUCKET_A_ID):
        WorkUnitCatalogueRepository(bucket_id=BUCKET_A_ID).save(
            WorkUnitCatalogue(work_units={work_a.work_unit_id: work_a}),
        )
        CalculationRevisionCatalogueRepository(bucket_id=BUCKET_A_ID).save(calc_a)
        ModeloRecordCatalogueRepository(bucket_id=BUCKET_A_ID).save(filing_a)
        VerificationReportCatalogueRepository(bucket_id=BUCKET_A_ID).save(verification_a)

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert WorkUnitCatalogueRepository(bucket_id=BUCKET_B_ID).load().work_units == {}
        assert CalculationRevisionCatalogueRepository(bucket_id=BUCKET_B_ID).load().revisions == {}
        assert ModeloRecordCatalogueRepository(bucket_id=BUCKET_B_ID).load().records == {}
        assert VerificationReportCatalogueRepository(bucket_id=BUCKET_B_ID).load().reports == {}
        WorkUnitCatalogueRepository(bucket_id=BUCKET_B_ID).save(
            WorkUnitCatalogue(work_units={work_b.work_unit_id: work_b}),
        )
        CalculationRevisionCatalogueRepository(bucket_id=BUCKET_B_ID).save(calc_b)
        ModeloRecordCatalogueRepository(bucket_id=BUCKET_B_ID).save(filing_b)
        VerificationReportCatalogueRepository(bucket_id=BUCKET_B_ID).save(verification_b)

    with active_runtime(tmp_path, BUCKET_A_ID):
        work_loaded = WorkUnitCatalogueRepository(bucket_id=BUCKET_A_ID).load().work_units
        calc_loaded = CalculationRevisionCatalogueRepository(bucket_id=BUCKET_A_ID).load().revisions
        filing_loaded = ModeloRecordCatalogueRepository(bucket_id=BUCKET_A_ID).load().records
        verification_loaded = VerificationReportCatalogueRepository(bucket_id=BUCKET_A_ID).load().reports

    assert tuple(work_loaded) == (work_a.work_unit_id,)
    assert tuple(calc_loaded) == tuple(calc_a.revisions)
    assert tuple(filing_loaded) == tuple(filing_a.records)
    assert tuple(verification_loaded) == tuple(verification_a.reports)


def _payable_m303_observation(period: str) -> RegistryModeloObservation:
    """Return a locally filed Modelo 303 whose positive result supports an ingreso."""
    definition = casillas_by_id(published_snapshot("303", filing_year=_YEAR, period=period).revision)[
        M303_COMPENSATION_RESULTADO_CASILLA
    ]
    return RegistryModeloObservation(
        modelo="303",
        filing_year=_YEAR,
        period=period,
        observations=(
            CasillaObservation(
                casilla_id=M303_COMPENSATION_RESULTADO_CASILLA,
                value=Decimal("20.00"),
                legal_refs=tuple(definition.legal_refs),
                source_refs=tuple(definition.source_refs),
            ),
        ),
    )


def test_application_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    observation_a = _payable_m303_observation("1T")
    observation_b = _payable_m303_observation("2T")
    history_a = history(BUCKET_A_ID)
    history_b = history(BUCKET_B_ID)
    decision_a = iva_wallet_decision(BUCKET_A_ID, target_period="2T")
    decision_b = iva_wallet_decision(BUCKET_B_ID, target_period="3T")
    usage_a = usage_profile(SpendingCategory.from_registry("suministros_home_office_luz"), "0.21")
    usage_b = usage_profile(SpendingCategory.from_registry("arrendamiento_vivienda_afecto"), "0.60")

    with active_runtime(tmp_path, BUCKET_A_ID):
        ModeloHistoryRepository(
            ports=FilingHistoryPorts(
                repository=FilingHistoryRepositoryAdapter(objects=secure_object_repository_for_bucket(BUCKET_A_ID)),
                bucket_id=BUCKET_A_ID,
            ),
        ).save(history_a)
        # Ingress normalizes the observation (derived carry casillas), so the
        # prepared envelope, not the raw input, is what a reload must return.
        envelope_a = CalculationObservationRepository(bucket_id=BUCKET_A_ID).prepare_observation_envelope(
            observation_a,
            source_kind="app_filing",
            stamped_revision_id=str(published_snapshot("303", filing_year=_YEAR, period="1T").revision.id),
            result_disposition=ResultDispositionProjection(
                disposition=ResultDisposition.INGRESO,
                provenance_kind="app_filing",
                provenance_locator=f"runtime-attached-local-filing:{_YEAR}:1T",
            ),
        )
        CalculationObservationRepository(bucket_id=BUCKET_A_ID).save(envelope_a)
        IvaWalletDecisionRepository().save_decision(decision_a)
        IvaCompensationHistoryRepository(bucket_id=BUCKET_A_ID).save_period(iva_state(BUCKET_A_ID))
        save_usage_ratios_with_secure_object_writes(usage_a, (), bucket_id=BUCKET_A_ID)

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert (
            ModeloHistoryRepository(
                ports=FilingHistoryPorts(
                    repository=FilingHistoryRepositoryAdapter(objects=secure_object_repository_for_bucket(BUCKET_B_ID)),
                    bucket_id=BUCKET_B_ID,
                ),
            ).list_modelos()
            == ()
        )
        assert (
            CalculationObservationRepository(bucket_id=BUCKET_B_ID).load_observation(
                "303",
                Period.from_year_and_code(_YEAR, "1T"),
            )
            is None
        )
        assert IvaWalletDecisionRepository().list_decisions() == ()
        assert (
            load_decision_history(
                IvaWalletDecisionRepository(), WALLET_SUBJECT_ID, Period.from_year_and_code(_YEAR, "2T")
            )
            == ()
        )
        assert IvaCompensationHistoryRepository(bucket_id=BUCKET_B_ID).list_periods() == ()
        assert _load_usage_ratios_for_test(bucket_id=BUCKET_B_ID) == UsageRatioProfile()
        ModeloHistoryRepository(
            ports=FilingHistoryPorts(
                repository=FilingHistoryRepositoryAdapter(objects=secure_object_repository_for_bucket(BUCKET_B_ID)),
                bucket_id=BUCKET_B_ID,
            ),
        ).save(history_b)
        CalculationObservationRepository(bucket_id=BUCKET_B_ID).save(
            CalculationObservationRepository(bucket_id=BUCKET_B_ID).prepare_observation_envelope(
                observation_b,
                source_kind="app_filing",
                stamped_revision_id=str(published_snapshot("303", filing_year=_YEAR, period="2T").revision.id),
                result_disposition=ResultDispositionProjection(
                    disposition=ResultDisposition.INGRESO,
                    provenance_kind="app_filing",
                    provenance_locator=f"runtime-attached-local-filing:{_YEAR}:2T",
                ),
            )
        )
        IvaWalletDecisionRepository().save_decision(decision_b)
        IvaCompensationHistoryRepository(bucket_id=BUCKET_B_ID).save_period(iva_state(BUCKET_B_ID))
        save_usage_ratios_with_secure_object_writes(usage_b, (), bucket_id=BUCKET_B_ID)

    with active_runtime(tmp_path, BUCKET_A_ID):
        modelo_ids = ModeloHistoryRepository(
            ports=FilingHistoryPorts(
                repository=FilingHistoryRepositoryAdapter(objects=secure_object_repository_for_bucket(BUCKET_A_ID)),
                bucket_id=BUCKET_A_ID,
            ),
        ).list_modelos()
        observed = CalculationObservationRepository(bucket_id=BUCKET_A_ID).load_observation(
            "303",
            Period.from_year_and_code(_YEAR, "1T"),
        )
        wallet_repo = IvaWalletDecisionRepository()
        decisions = wallet_repo.list_decisions()
        decision_history = load_decision_history(wallet_repo, WALLET_SUBJECT_ID, Period.from_year_and_code(_YEAR, "2T"))
        iva_periods = IvaCompensationHistoryRepository(bucket_id=BUCKET_A_ID).list_periods()
        usage = _load_usage_ratios_for_test(bucket_id=BUCKET_A_ID)

    assert modelo_ids == ("303",)
    assert observed is not None
    assert observed.observation == envelope_a.observation
    assert decisions == (decision_a,)
    assert decision_history == (decision_a,)
    assert tuple(state.period for state in iva_periods) == (Period.from_year_and_code(_YEAR, "1T"),)
    assert usage == usage_a


def test_runtime_default_surfaces_isolate_active_profile_writes(tmp_path: Path) -> None:
    with active_runtime(tmp_path, BUCKET_A_ID):
        build_borrador_100_snapshot_repository(bucket_id=BUCKET_A_ID).save(borrador_snapshot(BUCKET_A_ID))
        save_auth_diagnostic(BUCKET_A_ID)
        save_diagnostic_probe_row(BUCKET_A_ID)

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert build_borrador_100_snapshot_repository(bucket_id=BUCKET_B_ID).list_snapshots() == ()
        assert list_auth_diagnostics(persistence=build_auth_diagnostic_persistence()).row_count == 0
        assert preview_quarantine_unreadable_secure_objects(ports=_diagnostics_ports()).namespaces == ()
        build_borrador_100_snapshot_repository(bucket_id=BUCKET_B_ID).save(borrador_snapshot(BUCKET_B_ID))
        save_auth_diagnostic(BUCKET_B_ID)
        save_diagnostic_probe_row(BUCKET_B_ID)

    with active_runtime(tmp_path, BUCKET_A_ID):
        snapshots = build_borrador_100_snapshot_repository(bucket_id=BUCKET_A_ID).list_snapshots()
        auth_report = list_auth_diagnostics(persistence=build_auth_diagnostic_persistence())
        diagnostic_report = preview_quarantine_unreadable_secure_objects(ports=_diagnostics_ports())

    assert tuple(snapshot.snapshot_id for snapshot in snapshots) == (borrador_snapshot(BUCKET_A_ID).snapshot_id,)
    assert auth_report.row_count == 1
    assert tuple(row.diagnostic_id for row in auth_report.rows) == (f"diagnostic-{BUCKET_A_ID}",)
    assert LLM_USAGE_NAMESPACE.namespace in tuple(item.namespace for item in diagnostic_report.namespaces)


def test_adapter_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    google_a = google_records(BUCKET_A_ID)
    google_b = google_records(BUCKET_B_ID)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    usage = UsageRecorder(root_dir=tmp_path / "llm-usage")
    request = llm_request()
    artefact_a, body_a = sede_artefact(BUCKET_A_ID)
    artefact_b, body_b = sede_artefact(BUCKET_B_ID)

    with active_runtime(tmp_path, BUCKET_A_ID):
        google_session_records.save_token(BUCKET_A_ID, google_a[0])
        google_session_records.save_metadata(BUCKET_A_ID, google_a[1])
        google_session_records.save_drive_config(BUCKET_A_ID, google_a[2])
        cache.write(request, llm_response(BUCKET_A_ID))
        usage.record(usage_record(BUCKET_A_ID))
        InventoryLedgerRepository().save(
            InventoryLedgerDocument(ledgers=(inventory_ledger(BUCKET_A_ID),)),
        )
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        stored_a = store.persist_artefact(
            ("303", _YEAR, Period.from_year_and_code(_YEAR, "1T"), "202610013522456T"), artefact_a, body_a
        )

    with active_runtime(tmp_path, BUCKET_B_ID):
        assert google_session_store.load_token(BUCKET_B_ID) is None
        assert cache.read(request, LLMProvider.AGENT, "gpt-test") is None
        assert usage.load_records() == ()
        assert InventoryLedgerRepository().load().ledgers == ()
        with pytest.raises(ExpedienteNotFoundError):
            FiledDeclaracionObservationStore(tmp_path / "sede-cache").load_artefact(stored_a.storage_ref or "")
        google_session_records.save_token(BUCKET_B_ID, google_b[0])
        google_session_records.save_metadata(BUCKET_B_ID, google_b[1])
        google_session_records.save_drive_config(BUCKET_B_ID, google_b[2])
        cache.write(request, llm_response(BUCKET_B_ID))
        usage.record(usage_record(BUCKET_B_ID))
        InventoryLedgerRepository().save(
            InventoryLedgerDocument(ledgers=(inventory_ledger(BUCKET_B_ID),)),
        )
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        store.persist_artefact(
            ("303", _YEAR, Period.from_year_and_code(_YEAR, "2T"), "202610013522457T"), artefact_b, body_b
        )

    with active_runtime(tmp_path, BUCKET_A_ID):
        cached = cache.read(request, LLMProvider.AGENT, "gpt-test")
        usage_records = usage.load_records()
        inventory = InventoryLedgerRepository().load().ledgers
        loaded_body = FiledDeclaracionObservationStore(tmp_path / "sede-cache").load_artefact(
            stored_a.storage_ref or "",
        )
        assert google_session_store.load_token(BUCKET_A_ID) == google_a[0]
        assert google_session_store.load_metadata(BUCKET_A_ID) == google_a[1]
        assert google_session_store.load_drive_config(BUCKET_A_ID) == google_a[2]

    assert cached is not None
    assert cached.text == f"runtime attached response {BUCKET_A_ID}"
    assert tuple(record.request_id for record in usage_records) == (f"request-{BUCKET_A_ID}",)
    assert tuple(ledger.actividad_id for ledger in inventory) == (f"retail-{BUCKET_A_ID}",)
    assert loaded_body == body_a
