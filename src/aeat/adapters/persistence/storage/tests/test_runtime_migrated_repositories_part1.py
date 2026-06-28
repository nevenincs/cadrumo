"""Focused adapter contract tests split from the original monolith."""

from __future__ import annotations

from typing import cast

import pytest

from .....core import Period
from ._runtime_migrated_repositories_support import (
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
    ConfigResetScope,
    ExpedienteNotFoundError,
    FiledDeclaracionObservationStore,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    IvaCompensationHistoryRepository,
    IvaWalletDecisionRepository,
    JustificanteRepository,
    LLMCache,
    LLMProvider,
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
    reset_config,
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
    ("config_reset_auth", lambda: reset_config(ConfigResetScope.AUTH, confirmed=True)),
    ("config_reset_profile", lambda: reset_config(ConfigResetScope.PROFILE, confirmed=True)),
    ("config_reset_data", lambda: reset_config(ConfigResetScope.DATA, confirmed=True)),
    ("config_reset_all", lambda: reset_config(ConfigResetScope.ALL, confirmed=True)),
    ("bucket_events", lambda: BucketEventHistoryRepository().load()),
    ("auth_diagnostics", list_auth_diagnostics),
    ("auth_apoderado", lambda: ApoderadoService().status(bucket_id="bucket-a")),
    ("auth_session", lambda: _session_store.load(Path("/profile/active/aeat-session"))),
    ("google_oauth_client", lambda: google_session_store.load_client("operator-google")),
    ("google_oauth_token", lambda: google_session_store.load_token("operator-google")),
    ("google_oauth_metadata", lambda: google_session_store.load_metadata("operator-google")),
    ("google_drive_config", lambda: google_session_store.load_drive_config("operator-google")),
    ("llm_cache_stats", lambda: LLMCache(root_dir=Path("runtime-cache")).stats()),
    ("llm_usage_load", lambda: UsageRecorder(root_dir=Path("runtime-usage")).load_records()),
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
    ("transactions", lambda: TransactionCatalogueRepository(bucket_id="bucket-a").load()),
    ("invoices", lambda: InvoiceCatalogueRepository().load()),
    ("filing_drafts", lambda: ModeloDraftRepository(bucket_id="bucket-a").load("d" * 64)),
    ("filing_amendments", lambda: ModeloAmendmentRepository(bucket_id="bucket-a").load("amendment-a")),
    ("submission", lambda: SubmissionRepository().list_submission_ids()),
    ("justificante", lambda: JustificanteRepository().list_csvs()),
    ("filing_history", lambda: ModeloHistoryRepository(bucket_id="bucket-a").list_modelos()),
    ("modelo_work_units", lambda: WorkUnitCatalogueRepository(bucket_id="bucket-a").load()),
    ("modelo_calculation_revisions", lambda: CalculationRevisionCatalogueRepository(bucket_id="bucket-a").load()),
    ("modelo_filing_records", lambda: ModeloRecordCatalogueRepository(bucket_id="bucket-a").load()),
    ("modelo_verification_reports", lambda: VerificationReportCatalogueRepository(bucket_id="bucket-a").load()),
    (
        "calculation_observations",
        lambda: CalculationObservationRepository(bucket_id="bucket-a").load_observation(
            "303",
            Period.from_year_and_code(2026, "1T"),
        ),
    ),
    ("iva_wallet_decisions", lambda: IvaWalletDecisionRepository().list_decisions()),
    (
        "iva_wallet_decision_history",
        lambda: IvaWalletDecisionRepository().load_decision_history(
            "ESBUCKET-A",
            Period.from_year_and_code(2026, "2T"),
        ),
    ),
    ("iva_compensation_history", lambda: IvaCompensationHistoryRepository(bucket_id="bucket-a").list_periods()),
    ("usage_ratios", lambda: load_usage_ratios(bucket_id="bucket-a")),
    ("borrador_100_snapshot", lambda: Borrador100SnapshotRepository(bucket_id="bucket-a").list_snapshots()),
    ("repair_decisions", lambda: RepairRemediationDecisionRepository().list_decisions()),
    ("profile_assets", load_assets),
    ("profile_inventory", load_inventory),
    ("profile_amortizacion", load_amortizacion_ledger),
)


@pytest.mark.parametrize(
    ("case_name", "operation"),
    _RUNTIME_DEFAULT_REFUSAL_CASES,
)
def test_migrated_runtime_defaults_refuse_missing_session(
    tmp_path: Path,
    case_name: str,
    operation: Callable[[], object],
) -> None:
    del case_name
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"),
        pytest.raises(StorageValidationError, match="no active bucket session"),
    ):
        operation()


@pytest.mark.parametrize(
    ("case_name", "operation"),
    _RUNTIME_DEFAULT_REFUSAL_CASES,
)
def test_migrated_runtime_defaults_refuse_route_session_mismatch(
    tmp_path: Path,
    case_name: str,
    operation: Callable[[], object],
) -> None:
    del case_name
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"),
        activate_session(_session("bucket-b")),
        pytest.raises(StorageValidationError, match=r"route does not match|storage runtime is not ready"),
    ):
        operation()


def test_diagnostics_secure_object_total_degrades_on_missing_session(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="aeat.application.diagnostics")

    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"):
        assert secure_object_unreadable_total() == 0

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "no active bucket session" in caplog.text


def test_diagnostics_secure_object_total_degrades_on_route_session_mismatch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("DEBUG", logger="aeat.application.diagnostics")

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a"),
        activate_session(_session("bucket-b")),
    ):
        assert secure_object_unreadable_total() == 0

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "route does not match the active bucket session" in caplog.text


def test_workflow_state_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        WorkflowStateRepository().save(_workflow_state("bucket-a"))

    with _active_runtime(tmp_path, "bucket-b"):
        assert WorkflowStateRepository().load().declarations == {}
        WorkflowStateRepository().save(_workflow_state("bucket-b"))
        assert "303:2026:1T" in WorkflowStateRepository().load().declarations

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = WorkflowStateRepository().load()

    assert "303:2026:1T" in loaded.declarations
    assert loaded.declarations["303:2026:1T"].draft_id == "a" * 64


def test_auth_session_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    logical_path = Path("/profile/active/aeat-session")

    with _active_runtime(tmp_path, "bucket-a"):
        _session_store.save(
            logical_path,
            storage_state=_storage_state("bucket-a"),
            metadata={"profile": "bucket-a"},
        )

    with _active_runtime(tmp_path, "bucket-b"):
        assert _session_store.load(logical_path) is None
        _session_store.save(
            logical_path,
            storage_state=_storage_state("bucket-b"),
            metadata={"profile": "bucket-b"},
        )

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = _session_store.load(logical_path)

    assert loaded is not None
    assert loaded.metadata == {"profile": "bucket-a"}
    cookies = loaded.storage_state["cookies"]
    assert isinstance(cookies, list)
    first_cookie = cookies[0]
    assert isinstance(first_cookie, dict)
    # storage_state is the untyped Playwright Mapping[str, object]; the cookie
    # entries are str-keyed dicts at runtime. The cast restores the str key type
    # the isinstance-narrowed dict[Unknown, Unknown] erases (key type Never).
    cookie_fields = cast("dict[str, object]", first_cookie)
    assert cookie_fields["value"] == "bucket-a"


def test_transaction_repository_default_isolates_bucket_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        repo = TransactionCatalogueRepository(bucket_id="bucket-a")
        repo.save(TransactionCatalogue.from_transactions((_transaction("bucket-a"),)))

    with _active_runtime(tmp_path, "bucket-b"):
        repo = TransactionCatalogueRepository(bucket_id="bucket-b")
        assert len(repo.load().transactions) == 0
        repo.save(TransactionCatalogue.from_transactions((_transaction("bucket-b"),)))

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = TransactionCatalogueRepository(bucket_id="bucket-a").load()

    assert len(loaded.transactions) == 1
    transaction = next(iter(loaded.transactions.values()))
    assert transaction.raw.description == "runtime migrated repository bucket-a"


def test_attachment_store_default_isolates_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        digest_a = AttachmentStore().put_bytes(b"bucket-a attachment payload")

    with _active_runtime(tmp_path, "bucket-b"):
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_a)
        digest_b = AttachmentStore().put_bytes(b"bucket-b attachment payload")
        assert AttachmentStore().read_bytes(digest_b) == b"bucket-b attachment payload"

    with _active_runtime(tmp_path, "bucket-a"):
        assert AttachmentStore().read_bytes(digest_a) == b"bucket-a attachment payload"
        with pytest.raises(AttachmentNotFoundError):
            AttachmentStore().read_bytes(digest_b)


def test_profile_asset_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        save_assets((_asset("asset-a"),))

    with _active_runtime(tmp_path, "bucket-b"):
        assert load_assets() == ()
        save_assets((_asset("asset-b"),))

    with _active_runtime(tmp_path, "bucket-a"):
        loaded = load_assets()

    assert tuple(asset.identifier for asset in loaded) == ("asset-a",)


def test_event_and_workflow_run_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    event_a = _bucket_event("bucket-a")
    event_b = _bucket_event("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_a.event_id: event_a}))
        WorkflowRunRepository().save(_workflow_run("bucket-a"), runs_dir=tmp_path / "runs-a")

    with _active_runtime(tmp_path, "bucket-b"):
        assert BucketEventHistoryRepository().load().events == {}
        assert WorkflowRunRepository().list() == ()
        BucketEventHistoryRepository().save(BucketEventHistoryCatalogue(events={event_b.event_id: event_b}))
        WorkflowRunRepository().save(_workflow_run("bucket-b"), runs_dir=tmp_path / "runs-b")

    with _active_runtime(tmp_path, "bucket-a"):
        events = BucketEventHistoryRepository().load().events
        runs = WorkflowRunRepository().list()

    assert tuple(events) == (event_a.event_id,)
    assert [run.summary for run in runs] == ["runtime migrated workflow run bucket-a"]


def test_domain_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    draft_a = _modelo_draft("bucket-a")
    draft_b = _modelo_draft("bucket-b")
    amendment_a = _modelo_amendment("bucket-a")
    amendment_b = _modelo_amendment("bucket-b")
    submission_a = _submission("bucket-a")
    submission_b = _submission("bucket-b")
    justificante_a = _justificante(tmp_path, "bucket-a")
    justificante_b = _justificante(tmp_path, "bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((_invoice("bucket-a"),)))
        ModeloDraftRepository(bucket_id="bucket-a").save(draft_a)
        ModeloAmendmentRepository(bucket_id="bucket-a").save(amendment_a)
        SubmissionRepository().save(submission_a)
        JustificanteRepository().save(justificante_a)

    with _active_runtime(tmp_path, "bucket-b"):
        assert InvoiceCatalogueRepository().load().invoices == {}
        assert ModeloDraftRepository(bucket_id="bucket-b").load(draft_a.draft_id) is None
        assert ModeloAmendmentRepository(bucket_id="bucket-b").load(amendment_a.amendment_id) is None
        assert SubmissionRepository().list_submission_ids() == ()
        assert JustificanteRepository().list_csvs() == ()
        InvoiceCatalogueRepository().save(InvoiceCatalogue.from_invoices((_invoice("bucket-b"),)))
        ModeloDraftRepository(bucket_id="bucket-b").save(draft_b)
        ModeloAmendmentRepository(bucket_id="bucket-b").save(amendment_b)
        SubmissionRepository().save(submission_b)
        JustificanteRepository().save(justificante_b)

    with _active_runtime(tmp_path, "bucket-a"):
        invoices = InvoiceCatalogueRepository().load().invoices
        loaded_draft_a = ModeloDraftRepository(bucket_id="bucket-a").load(draft_a.draft_id)
        loaded_draft_b = ModeloDraftRepository(bucket_id="bucket-a").load(draft_b.draft_id)
        loaded_amendment_a = ModeloAmendmentRepository(bucket_id="bucket-a").load(amendment_a.amendment_id)
        loaded_amendment_b = ModeloAmendmentRepository(bucket_id="bucket-a").load(amendment_b.amendment_id)
        submissions = SubmissionRepository().list_submission_ids()
        csvs = JustificanteRepository().list_csvs()

    assert tuple(invoice.invoice_number for invoice in invoices.values()) == ("INV-BUCKET-A",)
    assert loaded_draft_a == draft_a
    assert loaded_draft_b is None
    assert loaded_amendment_a == amendment_a
    assert loaded_amendment_b is None
    assert submissions == (submission_a.submission_id,)
    assert csvs == (justificante_a.csv,)


def test_modelo_catalogue_defaults_isolate_bucket_writes(tmp_path: Path) -> None:
    work_a = _work_unit("bucket-a", "bucket-a")
    work_b = _work_unit("bucket-b", "bucket-b")
    calc_a = _calculation_catalogue("bucket-a")
    calc_b = _calculation_catalogue("bucket-b")
    filing_a = _filing_record_catalogue("bucket-a", "bucket-a")
    filing_b = _filing_record_catalogue("bucket-b", "bucket-b")
    verification_a = _verification_catalogue("bucket-a")
    verification_b = _verification_catalogue("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        WorkUnitCatalogueRepository(bucket_id="bucket-a").save(
            WorkUnitCatalogue(work_units={work_a.work_unit_id: work_a}),
        )
        CalculationRevisionCatalogueRepository(bucket_id="bucket-a").save(calc_a)
        ModeloRecordCatalogueRepository(bucket_id="bucket-a").save(filing_a)
        VerificationReportCatalogueRepository(bucket_id="bucket-a").save(verification_a)

    with _active_runtime(tmp_path, "bucket-b"):
        assert WorkUnitCatalogueRepository(bucket_id="bucket-b").load().work_units == {}
        assert CalculationRevisionCatalogueRepository(bucket_id="bucket-b").load().revisions == {}
        assert ModeloRecordCatalogueRepository(bucket_id="bucket-b").load().records == {}
        assert VerificationReportCatalogueRepository(bucket_id="bucket-b").load().reports == {}
        WorkUnitCatalogueRepository(bucket_id="bucket-b").save(
            WorkUnitCatalogue(work_units={work_b.work_unit_id: work_b}),
        )
        CalculationRevisionCatalogueRepository(bucket_id="bucket-b").save(calc_b)
        ModeloRecordCatalogueRepository(bucket_id="bucket-b").save(filing_b)
        VerificationReportCatalogueRepository(bucket_id="bucket-b").save(verification_b)

    with _active_runtime(tmp_path, "bucket-a"):
        work_loaded = WorkUnitCatalogueRepository(bucket_id="bucket-a").load().work_units
        calc_loaded = CalculationRevisionCatalogueRepository(bucket_id="bucket-a").load().revisions
        filing_loaded = ModeloRecordCatalogueRepository(bucket_id="bucket-a").load().records
        verification_loaded = VerificationReportCatalogueRepository(bucket_id="bucket-a").load().reports

    assert tuple(work_loaded) == (work_a.work_unit_id,)
    assert tuple(calc_loaded) == tuple(calc_a.revisions)
    assert tuple(filing_loaded) == tuple(filing_a.records)
    assert tuple(verification_loaded) == tuple(verification_a.reports)


def test_application_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    observation_a = RegistryModeloObservation(modelo="303", filing_year=2026, period="1T")
    observation_b = RegistryModeloObservation(modelo="303", filing_year=2026, period="2T")
    history_a = _history("bucket-a")
    history_b = _history("bucket-b")
    decision_a = _iva_wallet_decision("bucket-a", target_period="2T")
    decision_b = _iva_wallet_decision("bucket-b", target_period="3T")
    usage_a = _usage_profile(SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ, "0.21")
    usage_b = _usage_profile(SpendingCategory.TELEFONIA_MOVIL, "0.60")

    with _active_runtime(tmp_path, "bucket-a"):
        ModeloHistoryRepository(bucket_id="bucket-a").save(history_a)
        CalculationObservationRepository(bucket_id="bucket-a").save_observation(
            observation_a,
            source_kind="operator_manual",
        )
        IvaWalletDecisionRepository().save_decision(decision_a)
        IvaCompensationHistoryRepository(bucket_id="bucket-a").save_period(_iva_state("bucket-a"))
        save_usage_ratios(usage_a, bucket_id="bucket-a")

    with _active_runtime(tmp_path, "bucket-b"):
        assert ModeloHistoryRepository(bucket_id="bucket-b").list_modelos() == ()
        assert (
            CalculationObservationRepository(bucket_id="bucket-b").load_observation(
                "303",
                Period.from_year_and_code(2026, "1T"),
            )
            is None
        )
        assert IvaWalletDecisionRepository().list_decisions() == ()
        assert (
            IvaWalletDecisionRepository().load_decision_history(
                "ESBUCKET-A",
                Period.from_year_and_code(2026, "2T"),
            )
            == ()
        )
        assert IvaCompensationHistoryRepository(bucket_id="bucket-b").list_periods() == ()
        assert load_usage_ratios(bucket_id="bucket-b") == UsageRatioProfile()
        ModeloHistoryRepository(bucket_id="bucket-b").save(history_b)
        CalculationObservationRepository(bucket_id="bucket-b").save_observation(
            observation_b,
            source_kind="operator_manual",
        )
        IvaWalletDecisionRepository().save_decision(decision_b)
        IvaCompensationHistoryRepository(bucket_id="bucket-b").save_period(_iva_state("bucket-b"))
        save_usage_ratios(usage_b, bucket_id="bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        modelo_ids = ModeloHistoryRepository(bucket_id="bucket-a").list_modelos()
        observed = CalculationObservationRepository(bucket_id="bucket-a").load_observation(
            "303",
            Period.from_year_and_code(2026, "1T"),
        )
        wallet_repo = IvaWalletDecisionRepository()
        decisions = wallet_repo.list_decisions()
        decision_history = wallet_repo.load_decision_history("ESBUCKET-A", Period.from_year_and_code(2026, "2T"))
        iva_periods = IvaCompensationHistoryRepository(bucket_id="bucket-a").list_periods()
        usage = load_usage_ratios(bucket_id="bucket-a")

    assert modelo_ids == ("303",)
    assert observed is not None
    assert observed.observation == observation_a
    assert decisions == (decision_a,)
    assert decision_history == (decision_a,)
    assert tuple(state.period for state in iva_periods) == (Period.from_year_and_code(2026, "1T"),)
    assert usage == usage_a


def test_runtime_default_surfaces_isolate_active_profile_writes(tmp_path: Path) -> None:
    with _active_runtime(tmp_path, "bucket-a"):
        Borrador100SnapshotRepository(bucket_id="bucket-a").save(_borrador_snapshot("bucket-a", "bucket-a"))
        RepairRemediationDecisionRepository().save_decision(_repair_decision("bucket-a"))
        _save_auth_diagnostic("bucket-a")
        _save_diagnostic_probe_row("bucket-a")

    with _active_runtime(tmp_path, "bucket-b"):
        assert Borrador100SnapshotRepository(bucket_id="bucket-b").list_snapshots() == ()
        assert RepairRemediationDecisionRepository().list_decisions() == ()
        assert list_auth_diagnostics().row_count == 0
        assert preview_quarantine_unreadable_secure_objects().namespaces == ()
        Borrador100SnapshotRepository(bucket_id="bucket-b").save(_borrador_snapshot("bucket-b", "bucket-b"))
        RepairRemediationDecisionRepository().save_decision(_repair_decision("bucket-b"))
        _save_auth_diagnostic("bucket-b")
        _save_diagnostic_probe_row("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        snapshots = Borrador100SnapshotRepository(bucket_id="bucket-a").list_snapshots()
        decisions = RepairRemediationDecisionRepository().list_decisions()
        auth_report = list_auth_diagnostics()
        diagnostic_report = preview_quarantine_unreadable_secure_objects()

    assert tuple(snapshot.snapshot_id for snapshot in snapshots) == ("snapshot-bucket-a",)
    assert tuple(decision.reason for decision in decisions) == ("runtime migrated repair decision bucket-a",)
    assert auth_report.row_count == 1
    assert tuple(row.diagnostic_id for row in auth_report.rows) == ("diagnostic-bucket-a",)
    assert LLM_USAGE_NAMESPACE.namespace in tuple(item.namespace for item in diagnostic_report.namespaces)


def test_adapter_repository_defaults_isolate_active_profile_writes(tmp_path: Path) -> None:
    profile = "operator-google"
    google_a = _google_records("bucket-a")
    google_b = _google_records("bucket-b")
    cache = LLMCache(root_dir=tmp_path / "llm-cache")
    usage = UsageRecorder(root_dir=tmp_path / "llm-usage")
    request = _llm_request()
    artefact_a, body_a = _sede_artefact("bucket-a")
    artefact_b, body_b = _sede_artefact("bucket-b")

    with _active_runtime(tmp_path, "bucket-a"):
        google_session_store.save_client(profile, google_a[0])
        google_session_store.save_token(profile, google_a[1])
        google_session_store.save_metadata(profile, google_a[2])
        google_session_store.save_drive_config(profile, google_a[3])
        cache.write(request, _llm_response("bucket-a"))
        usage.record(_usage_record("bucket-a"))
        save_inventory((_inventory_ledger("bucket-a"),))
        save_amortizacion_ledger(_amortizacion_ledger("bucket-a"))
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        stored_a = store.persist_artefact(
            ("303", 2026, Period.from_year_and_code(2026, "1T"), "202610013522456T"), artefact_a, body_a
        )

    with _active_runtime(tmp_path, "bucket-b"):
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
        cache.write(request, _llm_response("bucket-b"))
        usage.record(_usage_record("bucket-b"))
        save_inventory((_inventory_ledger("bucket-b"),))
        save_amortizacion_ledger(_amortizacion_ledger("bucket-b"))
        store = FiledDeclaracionObservationStore(tmp_path / "sede-cache")
        store.persist_artefact(
            ("303", 2026, Period.from_year_and_code(2026, "2T"), "202610013522457T"), artefact_b, body_b
        )

    with _active_runtime(tmp_path, "bucket-a"):
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
    assert cached.text == "runtime migrated response bucket-a"
    assert tuple(record.request_id for record in usage_records) == ("request-bucket-a",)
    assert tuple(ledger.actividad_id for ledger in inventory) == ("retail-bucket-a",)
    assert amortizacion == _amortizacion_ledger("bucket-a")
    assert loaded_body == body_a
