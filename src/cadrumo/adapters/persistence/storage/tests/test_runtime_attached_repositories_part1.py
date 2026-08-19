"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

from typing import cast

import pytest

from .....core import Period
from .._runtime_readiness import StorageRuntimeReadinessCode
from ..runtime_repository import secure_object_repository_for_active_bucket_or_default_route
from ._runtime_attached_repositories_support import (
    _BUCKET_A_ATTACHMENT_PAYLOAD,
    _BUCKET_A_ID,
    _BUCKET_B_ATTACHMENT_PAYLOAD,
    _BUCKET_B_ID,
    _WALLET_SUBJECT_ID,
    LLM_USAGE_NAMESPACE,
    AmortizacionLedger,
    ApoderadoService,
    AttachmentNotFoundError,
    AttachmentStore,
    Borrador100SnapshotRepository,
    BucketEventHistoryCatalogue,
    BucketEventHistoryRepository,
    CalculationObservationRepository,
    CalculationRevisionCatalogueRepository,
    Callable,
    EvidenceConsentLedger,
    ExpedienteNotFoundError,
    FiledDeclaracionObservationStore,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    IvaCompensationHistoryRepository,
    IvaWalletDecisionRepository,
    JustificanteRepository,
    LLMCache,
    LLMProvider,
    LLMRunTelemetryRecorder,
    ModeloAmendmentRepository,
    ModeloDraftRepository,
    ModeloHistoryRepository,
    ModeloRecordCatalogueRepository,
    Path,
    RegistryModeloObservation,
    RepairRemediationDecisionRepository,
    SpendingCategory,
    StorageValidationError,
    SubmissionRepository,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    UsageRatioProfile,
    UsageRecorder,
    VerificationReportCatalogueRepository,
    WorkflowRunRepository,
    WorkflowStateRepository,
    WorkUnitCatalogue,
    WorkUnitCatalogueRepository,
    _active_runtime,
    _amortizacion_ledger,
    _asset,
    _borrador_snapshot,
    _bucket_event,
    _calculation_catalogue,
    _filing_record_catalogue,
    _google_records,
    _hex,
    _history,
    _inventory_ledger,
    _invoice,
    _iva_state,
    _iva_wallet_decision,
    _justificante,
    _llm_request,
    _llm_response,
    _modelo_amendment,
    _modelo_draft,
    _repair_decision,
    _save_auth_diagnostic,
    _save_diagnostic_probe_row,
    _sede_artefact,
    _session,
    _session_store,
    _storage_state,
    _submission,
    _transaction,
    _usage_profile,
    _usage_record,
    _verification_catalogue,
    _work_unit,
    _workflow_run,
    _workflow_state,
    activate_session,
    google_session_store,
    list_auth_diagnostics,
    load_amortizacion_ledger,
    load_assets,
    load_inventory,
    load_usage_ratios,
    override_settings,
    preview_quarantine_unreadable_secure_objects,
    save_amortizacion_ledger,
    save_assets,
    save_inventory,
    save_usage_ratios,
    secure_object_unreadable_total,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_RUNTIME_DEFAULT_REFUSAL_CASES: tuple[tuple[str, Callable[[], object]], ...] = (
    ("workflow_state", lambda: WorkflowStateRepository().load()),
    ("workflow_runs", lambda: WorkflowRunRepository().list()),
    ("bucket_events", lambda: BucketEventHistoryRepository().load()),
    ("auth_diagnostics", list_auth_diagnostics),
    ("auth_apoderado", lambda: ApoderadoService().status(bucket_id=_BUCKET_A_ID)),
    ("auth_session", lambda: _session_store.load(Path("/profile/active/aeat-session"))),
    ("google_oauth_client", lambda: google_session_store.load_client("operator-google")),
    ("google_oauth_token", lambda: google_session_store.load_token("operator-google")),
    ("google_oauth_metadata", lambda: google_session_store.load_metadata("operator-google")),
    ("google_drive_config", lambda: google_session_store.load_drive_config("operator-google")),
    ("llm_cache_stats", lambda: LLMCache(root_dir=Path("runtime-cache")).stats()),
    ("llm_usage_load", lambda: UsageRecorder(root_dir=Path("runtime-usage")).load_records()),
    ("llm_run_telemetry", lambda: LLMRunTelemetryRecorder(root_dir=Path("runtime-telemetry")).load_records()),
    ("llm_consent_ledger", lambda: EvidenceConsentLedger().load_entries()),
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
    ("transactions", lambda: TransactionCatalogueRepository(bucket_id=_BUCKET_A_ID).load()),
    ("invoices", lambda: InvoiceCatalogueRepository().load()),
    ("filing_drafts", lambda: ModeloDraftRepository(bucket_id=_BUCKET_A_ID).load("d" * 64)),
    ("filing_amendments", lambda: ModeloAmendmentRepository(bucket_id=_BUCKET_A_ID).load("amendment-a")),
    ("submission", lambda: SubmissionRepository().list_submission_ids()),
    ("justificante", lambda: JustificanteRepository().list_csvs()),
    ("filing_history", lambda: ModeloHistoryRepository(bucket_id=_BUCKET_A_ID).list_modelos()),
    ("modelo_work_units", lambda: WorkUnitCatalogueRepository(bucket_id=_BUCKET_A_ID).load()),
    ("modelo_calculation_revisions", lambda: CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_A_ID).load()),
    ("modelo_filing_records", lambda: ModeloRecordCatalogueRepository(bucket_id=_BUCKET_A_ID).load()),
    ("modelo_verification_reports", lambda: VerificationReportCatalogueRepository(bucket_id=_BUCKET_A_ID).load()),
    (
        "calculation_observations",
        lambda: CalculationObservationRepository(bucket_id=_BUCKET_A_ID).load_observation(
            "303",
            Period.from_year_and_code(2026, "1T"),
        ),
    ),
    ("iva_wallet_decisions", lambda: IvaWalletDecisionRepository().list_decisions()),
    (
        "iva_wallet_decision_history",
        lambda: IvaWalletDecisionRepository().load_decision_history(
            _WALLET_SUBJECT_ID,
            Period.from_year_and_code(2026, "2T"),
        ),
    ),
    ("iva_compensation_history", lambda: IvaCompensationHistoryRepository(bucket_id=_BUCKET_A_ID).list_periods()),
    ("usage_ratios", lambda: load_usage_ratios(bucket_id=_BUCKET_A_ID)),
    ("borrador_100_snapshot", lambda: Borrador100SnapshotRepository(bucket_id=_BUCKET_A_ID).list_snapshots()),
    ("repair_decisions", lambda: RepairRemediationDecisionRepository().list_decisions()),
    ("profile_assets", load_assets),
    ("profile_inventory", load_inventory),
    ("profile_amortizacion", load_amortizacion_ledger),
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
            override_settings(cadrumo_local_storage_root=tmp_path / case_name, cadrumo_active_profile=_BUCKET_A_ID),
            pytest.raises(StorageValidationError) as raised,
        ):
            operation()
        assert raised.value.translated_message == "errors.storage.runtime.not_ready", case_name
        assert raised.value.context is not None, case_name
        assert raised.value.context["readiness_code"] == StorageRuntimeReadinessCode.NO_ACTIVE_SESSION.value, case_name


def test_current_runtime_defaults_refuse_route_session_mismatch(tmp_path: Path) -> None:
    """A session serving another bucket refuses with the mismatch code, not the absence one."""
    for case_name, operation in _RUNTIME_DEFAULT_REFUSAL_CASES:
        with (
            override_settings(cadrumo_local_storage_root=tmp_path / case_name, cadrumo_active_profile=_BUCKET_A_ID),
            activate_session(_session(_BUCKET_B_ID)),
            pytest.raises(StorageValidationError) as raised,
        ):
            operation()
        assert raised.value.translated_message == "errors.storage.runtime.not_ready", case_name
        assert raised.value.context is not None, case_name
        expected = StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH.value
        assert raised.value.context["readiness_code"] == expected, case_name


def test_diagnostics_secure_object_total_degrades_on_missing_session(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="cadrumo.application.diagnostics")

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_A_ID):
        # Pin the precondition through the typed refusal the probe swallows.
        # The degrade log renders the error's translation key, which is shared
        # by every unready state, so asserting on the log alone would not
        # distinguish this test from its route-mismatch sibling below.
        with pytest.raises(StorageValidationError) as raised:
            secure_object_repository_for_active_bucket_or_default_route()
        assert raised.value.context is not None
        assert raised.value.context["readiness_code"] == StorageRuntimeReadinessCode.NO_ACTIVE_SESSION.value

        assert secure_object_unreadable_total() == 0

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "errors.storage.runtime.not_ready" in caplog.text


def test_diagnostics_secure_object_total_degrades_on_route_session_mismatch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="cadrumo.application.diagnostics")

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_BUCKET_A_ID),
        activate_session(_session(_BUCKET_B_ID)),
    ):
        # See the sibling above: the route mismatch is what must be shown to
        # have caused the degrade, and only the typed code discriminates it.
        with pytest.raises(StorageValidationError) as raised:
            secure_object_repository_for_active_bucket_or_default_route()
        assert raised.value.context is not None
        assert raised.value.context["readiness_code"] == StorageRuntimeReadinessCode.ROUTE_BUCKET_MISMATCH.value

        assert secure_object_unreadable_total() == 0

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "errors.storage.runtime.not_ready" in caplog.text


def test_workflow_state_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, _BUCKET_A_ID):
        WorkflowStateRepository().save(_workflow_state(_BUCKET_A_ID))

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert WorkflowStateRepository().load().declarations == {}
        WorkflowStateRepository().save(_workflow_state(_BUCKET_B_ID))
        assert "303:2026:1T" in WorkflowStateRepository().load().declarations

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        loaded = WorkflowStateRepository().load()

    assert "303:2026:1T" in loaded.declarations
    assert loaded.declarations["303:2026:1T"].draft_id == "a" * 64


def test_auth_session_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    logical_path = Path("/profile/active/aeat-session")

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        _session_store.save(
            logical_path,
            storage_state=_storage_state(_BUCKET_A_ID),
            metadata={"profile": _BUCKET_A_ID},
        )

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert _session_store.load(logical_path) is None
        _session_store.save(
            logical_path,
            storage_state=_storage_state(_BUCKET_B_ID),
            metadata={"profile": _BUCKET_B_ID},
        )

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        loaded = _session_store.load(logical_path)

    assert loaded is not None
    assert loaded.metadata == {"profile": _BUCKET_A_ID}
    cookies = loaded.storage_state["cookies"]
    assert isinstance(cookies, list)
    first_cookie = cookies[0]
    assert isinstance(first_cookie, dict)
    # storage_state is the untyped Playwright Mapping[str, object]; the cookie
    # entries are str-keyed dicts at runtime. The cast restores the str key type
    # the isinstance-narrowed dict[Unknown, Unknown] erases (key type Never).
    cookie_fields = cast("dict[str, object]", first_cookie)
    assert cookie_fields["value"] == _BUCKET_A_ID


def test_transaction_repository_default_isolates_bucket_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, _BUCKET_A_ID):
        repo = TransactionCatalogueRepository(bucket_id=_BUCKET_A_ID)
        repo.save(TransactionCatalogue.from_transactions((_transaction(_BUCKET_A_ID),)))

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        repo = TransactionCatalogueRepository(bucket_id=_BUCKET_B_ID)
        assert len(repo.load().transactions) == 0
        repo.save(TransactionCatalogue.from_transactions((_transaction(_BUCKET_B_ID),)))

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        loaded = TransactionCatalogueRepository(bucket_id=_BUCKET_A_ID).load()

    assert len(loaded.transactions) == 1
    transaction = next(iter(loaded.transactions.values()))
    assert transaction.raw.description == f"runtime attached repository {_BUCKET_A_ID}"


def test_attachment_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, _BUCKET_A_ID):
        digest_a = AttachmentStore().put_bytes(_BUCKET_A_ATTACHMENT_PAYLOAD)

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_a)
        digest_b = AttachmentStore().put_bytes(_BUCKET_B_ATTACHMENT_PAYLOAD)
        assert AttachmentStore().read_bytes(digest_b) == _BUCKET_B_ATTACHMENT_PAYLOAD

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        assert AttachmentStore().read_bytes(digest_a) == _BUCKET_A_ATTACHMENT_PAYLOAD
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_b)


def test_profile_asset_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, _BUCKET_A_ID):
        save_assets((_asset("asset-a"),))

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert load_assets() == ()
        save_assets((_asset("asset-b"),))

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        loaded = load_assets()

    assert tuple(asset.identifier for asset in loaded) == ("asset-a",)


def test_event_and_workflow_run_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    event_a = _bucket_event(_BUCKET_A_ID)
    event_b = _bucket_event(_BUCKET_B_ID)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_a.event_id: event_a}))
        WorkflowRunRepository().save(_workflow_run(_BUCKET_A_ID), runs_dir=tmp_path / "runs-a")

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert BucketEventHistoryRepository().load().events == {}
        assert WorkflowRunRepository().list() == ()
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_b.event_id: event_b}))
        WorkflowRunRepository().save(_workflow_run(_BUCKET_B_ID), runs_dir=tmp_path / "runs-b")

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        events = BucketEventHistoryRepository().load().events
        runs = WorkflowRunRepository().list()

    assert tuple(events) == (event_a.event_id,)
    assert [(run.run_id, run.summary_locale_key) for run in runs] == [
        (_hex(f"workflow-run-{_BUCKET_A_ID}")[:16], "application.workflow.results.completed")
    ]


def test_domain_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    draft_a = _modelo_draft(_BUCKET_A_ID)
    draft_b = _modelo_draft(_BUCKET_B_ID)
    amendment_a = _modelo_amendment(_BUCKET_A_ID)
    amendment_b = _modelo_amendment(_BUCKET_B_ID)
    submission_a = _submission(_BUCKET_A_ID)
    submission_b = _submission(_BUCKET_B_ID)
    justificante_a = _justificante(tmp_path, _BUCKET_A_ID)
    justificante_b = _justificante(tmp_path, _BUCKET_B_ID)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((_invoice(_BUCKET_A_ID),)))
        ModeloDraftRepository(bucket_id=_BUCKET_A_ID).save(draft_a)
        ModeloAmendmentRepository(bucket_id=_BUCKET_A_ID).save(amendment_a)
        SubmissionRepository().save(submission_a)
        JustificanteRepository().save(justificante_a)

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert InvoiceCatalogueRepository().load().invoices == {}
        assert ModeloDraftRepository(bucket_id=_BUCKET_B_ID).load(draft_a.draft_id) is None
        assert ModeloAmendmentRepository(bucket_id=_BUCKET_B_ID).load(amendment_a.amendment_id) is None
        assert SubmissionRepository().list_submission_ids() == ()
        assert JustificanteRepository().list_csvs() == ()
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((_invoice(_BUCKET_B_ID),)))
        ModeloDraftRepository(bucket_id=_BUCKET_B_ID).save(draft_b)
        ModeloAmendmentRepository(bucket_id=_BUCKET_B_ID).save(amendment_b)
        SubmissionRepository().save(submission_b)
        JustificanteRepository().save(justificante_b)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        invoices = InvoiceCatalogueRepository().load().invoices
        loaded_draft_a = ModeloDraftRepository(bucket_id=_BUCKET_A_ID).load(draft_a.draft_id)
        loaded_draft_b = ModeloDraftRepository(bucket_id=_BUCKET_A_ID).load(draft_b.draft_id)
        loaded_amendment_a = ModeloAmendmentRepository(bucket_id=_BUCKET_A_ID).load(amendment_a.amendment_id)
        loaded_amendment_b = ModeloAmendmentRepository(bucket_id=_BUCKET_A_ID).load(amendment_b.amendment_id)
        submissions = SubmissionRepository().list_submission_ids()
        csvs = JustificanteRepository().list_csvs()

    assert tuple(invoice.invoice_number for invoice in invoices.values()) == (f"INV-{_BUCKET_A_ID.upper()}",)
    assert loaded_draft_a == draft_a
    assert loaded_draft_b is None
    assert loaded_amendment_a == amendment_a
    assert loaded_amendment_b is None
    assert submissions == (submission_a.submission_id,)
    assert csvs == (justificante_a.csv,)


def test_modelo_catalogue_defaults_isolate_bucket_writes(tmp_path: Path) -> None:
    work_a = _work_unit(_BUCKET_A_ID, _BUCKET_A_ID)
    work_b = _work_unit(_BUCKET_B_ID, _BUCKET_B_ID)
    calc_a = _calculation_catalogue(_BUCKET_A_ID)
    calc_b = _calculation_catalogue(_BUCKET_B_ID)
    filing_a = _filing_record_catalogue(_BUCKET_A_ID, _BUCKET_A_ID)
    filing_b = _filing_record_catalogue(_BUCKET_B_ID, _BUCKET_B_ID)
    verification_a = _verification_catalogue(_BUCKET_A_ID)
    verification_b = _verification_catalogue(_BUCKET_B_ID)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        WorkUnitCatalogueRepository(bucket_id=_BUCKET_A_ID).save(
            WorkUnitCatalogue(work_units={work_a.work_unit_id: work_a}),
        )
        CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_A_ID).save(calc_a)
        ModeloRecordCatalogueRepository(bucket_id=_BUCKET_A_ID).save(filing_a)
        VerificationReportCatalogueRepository(bucket_id=_BUCKET_A_ID).save(verification_a)

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert WorkUnitCatalogueRepository(bucket_id=_BUCKET_B_ID).load().work_units == {}
        assert CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_B_ID).load().revisions == {}
        assert ModeloRecordCatalogueRepository(bucket_id=_BUCKET_B_ID).load().records == {}
        assert VerificationReportCatalogueRepository(bucket_id=_BUCKET_B_ID).load().reports == {}
        WorkUnitCatalogueRepository(bucket_id=_BUCKET_B_ID).save(
            WorkUnitCatalogue(work_units={work_b.work_unit_id: work_b}),
        )
        CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_B_ID).save(calc_b)
        ModeloRecordCatalogueRepository(bucket_id=_BUCKET_B_ID).save(filing_b)
        VerificationReportCatalogueRepository(bucket_id=_BUCKET_B_ID).save(verification_b)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        work_loaded = WorkUnitCatalogueRepository(bucket_id=_BUCKET_A_ID).load().work_units
        calc_loaded = CalculationRevisionCatalogueRepository(bucket_id=_BUCKET_A_ID).load().revisions
        filing_loaded = ModeloRecordCatalogueRepository(bucket_id=_BUCKET_A_ID).load().records
        verification_loaded = VerificationReportCatalogueRepository(bucket_id=_BUCKET_A_ID).load().reports

    assert tuple(work_loaded) == (work_a.work_unit_id,)
    assert tuple(calc_loaded) == tuple(calc_a.revisions)
    assert tuple(filing_loaded) == tuple(filing_a.records)
    assert tuple(verification_loaded) == tuple(verification_a.reports)


def test_application_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    observation_a = RegistryModeloObservation(modelo="303", filing_year=2026, period="1T")
    observation_b = RegistryModeloObservation(modelo="303", filing_year=2026, period="2T")
    history_a = _history(_BUCKET_A_ID)
    history_b = _history(_BUCKET_B_ID)
    decision_a = _iva_wallet_decision(_BUCKET_A_ID, target_period="2T")
    decision_b = _iva_wallet_decision(_BUCKET_B_ID, target_period="3T")
    usage_a = _usage_profile(SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ, "0.21")
    usage_b = _usage_profile(SpendingCategory.TELEFONIA_MOVIL, "0.60")

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        ModeloHistoryRepository(bucket_id=_BUCKET_A_ID).save(history_a)
        CalculationObservationRepository(bucket_id=_BUCKET_A_ID).save(
            CalculationObservationRepository(bucket_id=_BUCKET_A_ID).prepare_observation_envelope(
                observation_a,
                source_kind="operator_manual",
            )
        )
        IvaWalletDecisionRepository().save_decision(decision_a)
        IvaCompensationHistoryRepository(bucket_id=_BUCKET_A_ID).save_period(_iva_state(_BUCKET_A_ID))
        save_usage_ratios(usage_a, bucket_id=_BUCKET_A_ID)

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert ModeloHistoryRepository(bucket_id=_BUCKET_B_ID).list_modelos() == ()
        assert (
            CalculationObservationRepository(bucket_id=_BUCKET_B_ID).load_observation(
                "303",
                Period.from_year_and_code(2026, "1T"),
            )
            is None
        )
        assert IvaWalletDecisionRepository().list_decisions() == ()
        assert (
            IvaWalletDecisionRepository().load_decision_history(
                _WALLET_SUBJECT_ID,
                Period.from_year_and_code(2026, "2T"),
            )
            == ()
        )
        assert IvaCompensationHistoryRepository(bucket_id=_BUCKET_B_ID).list_periods() == ()
        assert load_usage_ratios(bucket_id=_BUCKET_B_ID) == UsageRatioProfile()
        ModeloHistoryRepository(bucket_id=_BUCKET_B_ID).save(history_b)
        CalculationObservationRepository(bucket_id=_BUCKET_B_ID).save(
            CalculationObservationRepository(bucket_id=_BUCKET_B_ID).prepare_observation_envelope(
                observation_b,
                source_kind="operator_manual",
            )
        )
        IvaWalletDecisionRepository().save_decision(decision_b)
        IvaCompensationHistoryRepository(bucket_id=_BUCKET_B_ID).save_period(_iva_state(_BUCKET_B_ID))
        save_usage_ratios(usage_b, bucket_id=_BUCKET_B_ID)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        modelo_ids = ModeloHistoryRepository(bucket_id=_BUCKET_A_ID).list_modelos()
        observed = CalculationObservationRepository(bucket_id=_BUCKET_A_ID).load_observation(
            "303",
            Period.from_year_and_code(2026, "1T"),
        )
        wallet_repo = IvaWalletDecisionRepository()
        decisions = wallet_repo.list_decisions()
        decision_history = wallet_repo.load_decision_history(_WALLET_SUBJECT_ID, Period.from_year_and_code(2026, "2T"))
        iva_periods = IvaCompensationHistoryRepository(bucket_id=_BUCKET_A_ID).list_periods()
        usage = load_usage_ratios(bucket_id=_BUCKET_A_ID)

    assert modelo_ids == ("303",)
    assert observed is not None
    assert observed.observation == observation_a
    assert decisions == (decision_a,)
    assert decision_history == (decision_a,)
    assert tuple(state.period for state in iva_periods) == (Period.from_year_and_code(2026, "1T"),)
    assert usage == usage_a


def test_runtime_default_surfaces_isolate_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, _BUCKET_A_ID):
        Borrador100SnapshotRepository(bucket_id=_BUCKET_A_ID).save(_borrador_snapshot(_BUCKET_A_ID))
        RepairRemediationDecisionRepository().save_decision(_repair_decision(_BUCKET_A_ID))
        _save_auth_diagnostic(_BUCKET_A_ID)
        _save_diagnostic_probe_row(_BUCKET_A_ID)

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert Borrador100SnapshotRepository(bucket_id=_BUCKET_B_ID).list_snapshots() == ()
        assert RepairRemediationDecisionRepository().list_decisions() == ()
        assert list_auth_diagnostics().row_count == 0
        assert preview_quarantine_unreadable_secure_objects().namespaces == ()
        Borrador100SnapshotRepository(bucket_id=_BUCKET_B_ID).save(_borrador_snapshot(_BUCKET_B_ID))
        RepairRemediationDecisionRepository().save_decision(_repair_decision(_BUCKET_B_ID))
        _save_auth_diagnostic(_BUCKET_B_ID)
        _save_diagnostic_probe_row(_BUCKET_B_ID)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        snapshots = Borrador100SnapshotRepository(bucket_id=_BUCKET_A_ID).list_snapshots()
        decisions = RepairRemediationDecisionRepository().list_decisions()
        auth_report = list_auth_diagnostics()
        diagnostic_report = preview_quarantine_unreadable_secure_objects()

    assert tuple(snapshot.snapshot_id for snapshot in snapshots) == (_borrador_snapshot(_BUCKET_A_ID).snapshot_id,)
    assert tuple(decision.reason for decision in decisions) == (f"runtime attached repair decision {_BUCKET_A_ID}",)
    assert auth_report.row_count == 1
    assert tuple(row.diagnostic_id for row in auth_report.rows) == (f"diagnostic-{_BUCKET_A_ID}",)
    assert LLM_USAGE_NAMESPACE.namespace in tuple(item.namespace for item in diagnostic_report.namespaces)


def test_adapter_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    profile = "operator-google"
    google_a = _google_records(_BUCKET_A_ID)
    google_b = _google_records(_BUCKET_B_ID)
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    usage = UsageRecorder(root_dir=tmp_path / "llm-usage")
    request = _llm_request()
    artefact_a, body_a = _sede_artefact(_BUCKET_A_ID)
    artefact_b, body_b = _sede_artefact(_BUCKET_B_ID)

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        google_session_store.save_client(profile, google_a[0])
        google_session_store.save_token(profile, google_a[1])
        google_session_store.save_metadata(profile, google_a[2])
        google_session_store.save_drive_config(profile, google_a[3])
        cache.write(request, _llm_response(_BUCKET_A_ID))
        usage.record(_usage_record(_BUCKET_A_ID))
        save_inventory((_inventory_ledger(_BUCKET_A_ID),))
        save_amortizacion_ledger(_amortizacion_ledger(_BUCKET_A_ID))
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        stored_a = store.persist_artefact(
            ("303", 2026, Period.from_year_and_code(2026, "1T"), "202610013522456T"), artefact_a, body_a
        )

    with _active_runtime(tmp_path, _BUCKET_B_ID):
        assert google_session_store.load_client(profile) is None
        assert cache.read(request, LLMProvider.OPENAI, "gpt-test") is None
        assert usage.load_records() == ()
        assert load_inventory() == ()
        assert load_amortizacion_ledger() == AmortizacionLedger()
        with pytest.raises(ExpedienteNotFoundError):
            FiledDeclaracionObservationStore(tmp_path / "sede-cache").load_artefact(stored_a.storage_ref or "")
        google_session_store.save_client(profile, google_b[0])
        google_session_store.save_token(profile, google_b[1])
        google_session_store.save_metadata(profile, google_b[2])
        google_session_store.save_drive_config(profile, google_b[3])
        cache.write(request, _llm_response(_BUCKET_B_ID))
        usage.record(_usage_record(_BUCKET_B_ID))
        save_inventory((_inventory_ledger(_BUCKET_B_ID),))
        save_amortizacion_ledger(_amortizacion_ledger(_BUCKET_B_ID))
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        store.persist_artefact(
            ("303", 2026, Period.from_year_and_code(2026, "2T"), "202610013522457T"), artefact_b, body_b
        )

    with _active_runtime(tmp_path, _BUCKET_A_ID):
        cached = cache.read(request, LLMProvider.OPENAI, "gpt-test")
        usage_records = usage.load_records()
        inventory = load_inventory()
        amortizacion = load_amortizacion_ledger()
        loaded_body = FiledDeclaracionObservationStore(tmp_path / "sede-cache").load_artefact(
            stored_a.storage_ref or "",
        )
        assert google_session_store.load_client(profile) == google_a[0]
        assert google_session_store.load_token(profile) == google_a[1]
        assert google_session_store.load_metadata(profile) == google_a[2]
        assert google_session_store.load_drive_config(profile) == google_a[3]

    assert cached is not None
    assert cached.text == f"runtime attached response {_BUCKET_A_ID}"
    assert tuple(record.request_id for record in usage_records) == (f"request-{_BUCKET_A_ID}",)
    assert tuple(ledger.actividad_id for ledger in inventory) == (f"retail-{_BUCKET_A_ID}",)
    assert amortizacion == _amortizacion_ledger(_BUCKET_A_ID)
    assert loaded_body == body_a
