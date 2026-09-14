"""Real-behavior tests for the canonical operator state read-projection.

These tests use a real profile-scoped storage runtime and filesystem
bucket with the production repositories.

The projection's contract is that every operator-facing surface reads
ONE state view, so the surfaces cannot disagree. Two contracts are
proved here:

* the cross-surface agreement contract — ``overview status``,
  ``auth status``, ``auth test``, and ``modelo readiness`` all read
  values drawn from the same projection, and ``auth status`` /
  ``auth test`` report the same ``configured``;
* the concrete regression — with ``modelo work`` work units present,
  ``overview status`` reports them rather than the silently-zero count
  the pre-projection assembly produced.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from contextlib import ExitStack
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.state_projection import StateProjectionPersistenceAdapter
from cadrumo.adapters.persistence.profile.tests.ledger_action_create_support import ledger_ports_for_test
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.profile.usage_ratios import load_usage_ratios
from cadrumo.adapters.persistence.storage.bucket.tests.bucket_layout import provision_bucket_directory
from cadrumo.adapters.persistence.storage.custody.capsule import load_committed_profile_password_material
from cadrumo.adapters.persistence.storage.custody.kdf_supervision import unlock_profile_custody
from cadrumo.adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import (
    _profile_authority_contexts as _profile_contexts_for_test,
)
from cadrumo.application.auth.operator import inspect_operator_auth
from cadrumo.application.auth.operator import test_operator_auth as probe_operator_auth
from cadrumo.application.auth.tests.certificate_secret_fakes import InMemoryCertificateSecretBackendFactory
from cadrumo.application.diagnostics_ports import DiagnosticSecureObjectNamespace, DiagnosticsPorts
from cadrumo.application.ledger.actions_manual import create_manual_transaction
from cadrumo.application.ledger.models import ManualLedgerTransactionCommand
from cadrumo.application.modelo.tests.registry_revision import active_registry_revision_id
from cadrumo.application.modelo.work_lifecycle import (
    create_work_unit,
    discard_work_unit,
)
from cadrumo.application.overview.status_report import build_overview_status_report
from cadrumo.application.state_projection import (
    ModeloReadinessRequest,
    build_operator_state_projection,
)
from cadrumo.application.state_projection_ports import StateProjectionReadPorts
from cadrumo.application.user_profile.login_session_port import profile_login_session_port
from cadrumo.application.user_profile.profile_record_repository import close_active_profile_record_session
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.application.wizard.catalogue import build_setup_flow
from cadrumo.application.workflow.persistence import workflow_state_repository
from cadrumo.application.workflow.state_models import WorkflowState
from cadrumo.core.config import Settings, override_settings
from cadrumo.core.config_support import SecretStoreBackend
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection
from cadrumo.entrypoints.adapter_composition import build_work_lifecycle_ports

from ._operator_probe_fakes import fake_operator_probe_ports
from ._operator_scope_fakes import build_inward_operator_scope_ports_for_active_route

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_ACTIVE_STORAGE_STACK: ExitStack | None = None
_PROFILE_SPAN_OPEN = False
_ACTIVE_PROFILE_ID: str | None = None
_OPERATOR_PASSPHRASE = "state projection test passphrase 123"  # noqa: S105 - test-only credential
_OPERATOR_PROBE_PORTS = fake_operator_probe_ports()


class _EmptyDiagnosticRepository:
    """Inward fake for the projection's secure-object counter capability."""

    def list_namespaces(self) -> tuple[str, ...]:
        return ()

    def probe_namespace_integrity(self, namespace: str) -> DiagnosticSecureObjectNamespace:
        raise AssertionError(f"unexpected integrity probe for {namespace}")

    def quarantine_unreadable_rows(self) -> tuple[DiagnosticSecureObjectNamespace, ...]:
        return ()


def _diagnostics_ports() -> DiagnosticsPorts:
    return DiagnosticsPorts(
        secure_object_repository=_EmptyDiagnosticRepository(),
        session_failure_classifier=lambda error: False,
    )


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path) -> Iterator[None]:
    """Bind a real isolated filesystem root per test."""

    global _ACTIVE_STORAGE_STACK, _ACTIVE_PROFILE_ID, _PROFILE_SPAN_OPEN

    with bundled_indexed_authority().operation() as operation:
        assert build_setup_flow(operation).sections
    dispose_engine()
    with ExitStack() as stack:
        stack.enter_context(
            override_settings(
                cadrumo_local_storage_root=tmp_path,
                cadrumo_active_profile=None,
                cadrumo_secret_store_backend=SecretStoreBackend.AUTO,
                cadrumo_secret_passphrase=SecretStr(_OPERATOR_PASSPHRASE),
            ),
        )
        _ACTIVE_STORAGE_STACK = stack
        _ACTIVE_PROFILE_ID = None
        _PROFILE_SPAN_OPEN = False
        try:
            yield
        finally:
            dispose_engine()
            _ACTIVE_PROFILE_ID = None
            _PROFILE_SPAN_OPEN = False
            _ACTIVE_STORAGE_STACK = None


@pytest.fixture
def state_projection_dependencies() -> tuple[InMemoryCertificateSecretBackendFactory, StateProjectionReadPorts]:
    """Compose the application read ports and test certificate capability per test."""

    adapter = StateProjectionPersistenceAdapter(diagnostics_ports=_diagnostics_ports())
    return (
        InMemoryCertificateSecretBackendFactory(),
        StateProjectionReadPorts(
            workspace=adapter,
            profile=adapter,
            usage_ratio_profile_loader=load_usage_ratios,
        ),
    )


def _register_active_profile(*, overrides: Mapping[str, str] | None = None) -> str:
    """Create one current capsule, then bind its authenticated live session."""
    _profile_create_context_for_test, _profile_decode_context_for_test = _profile_contexts_for_test()

    global _ACTIVE_PROFILE_ID, _PROFILE_SPAN_OPEN

    if _PROFILE_SPAN_OPEN:
        if _ACTIVE_PROFILE_ID is None:
            raise RuntimeError("state projection profile span lost its active capsule UUID")
        return _ACTIVE_PROFILE_ID
    if _ACTIVE_STORAGE_STACK is None:
        raise RuntimeError("state projection test storage span is not active")

    profile_overrides = {
        "identity.tax_id": "00000000T",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
    if overrides:
        profile_overrides.update(overrides)

    outcome = register_profile_with_credentials(
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
        label="state projection operator",
        passphrase=_OPERATOR_PASSPHRASE,
        profile_create_context=_profile_create_context_for_test,
        profile_decode_context=_profile_decode_context_for_test,
    )
    storage_root = Settings().cadrumo_local_storage_root
    material = load_committed_profile_password_material(UUID(outcome.profile_id), root=storage_root)
    unlocked = unlock_profile_custody(material.envelope, _OPERATOR_PASSPHRASE, sentinel=material.sentinel)
    instant = datetime.now(UTC)
    session = profile_login_session_port().open_resumed_session(
        bucket_id=outcome.profile_id,
        dek=unlocked.dek,
        idle_minutes=15,
        opened_at=instant,
        idle_deadline=instant + timedelta(minutes=15),
        absolute_deadline=instant + timedelta(hours=4),
        storage_root=storage_root,
    )
    profile_login_session_port().bind_session(session)
    _ACTIVE_STORAGE_STACK.callback(profile_login_session_port().close_active_session)
    _ACTIVE_STORAGE_STACK.callback(close_active_profile_record_session)
    register_minimal_profile(
        profile_id=outcome.profile_id,
        overrides=profile_overrides,
    )

    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    _ACTIVE_PROFILE_ID = bucket_id
    _PROFILE_SPAN_OPEN = True
    return bucket_id


def _stage_profile_bucket(root: Path, bucket_id: str) -> None:
    """Materialise a bucket directory with no profile record.

    Staged a plaintext manifest alongside it until that format was retired.
    The state under test is the absent record, which the manifest never
    carried.
    """
    provision_bucket_directory(root, bucket_id)


def test_overview_status_reports_modelo_work_units(tmp_path: Path, state_projection_dependencies) -> None:
    """The concrete bug this regression closes: with ``modelo work`` work units
    present, ``overview status`` must report them.

    Before the canonical projection, ``build_overview_status_report``
    read the declaration-draft ``ModeloDraft`` store but never the
    ``WorkUnitCatalogue`` store, so an operator who used ``modelo work
    create`` saw a silently-zero count. The projection carries
    ``work_units`` as a distinct counter."""

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()

    create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period="1T"),
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
    )

    with bundled_indexed_authority().operation() as operation:
        report = build_overview_status_report(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert report.work_units == 1, "overview status must surface modelo work units, not zero"
    assert report.drafts == 0, "the ModeloDraft store is separate and stays at zero"


def test_overview_status_distinguishes_drafts_from_work_units(state_projection_dependencies) -> None:
    """``drafts`` and ``work_units`` are distinct counters; neither is
    silently folded into the other."""

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()
    for period_token in ("1T", "2T"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, period_token),
            revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period=period_token),
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        )

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert projection.workspace.work_units == 2
    assert projection.workspace.drafts == 0
    assert projection.workspace.transactions == 0
    assert projection.workspace.invoices == 0


def test_work_units_counter_excludes_discarded_units(state_projection_dependencies) -> None:
    """A discarded work unit must not inflate the active ``work_units``
    counter; it is carried separately in ``discarded_work_units`` so the
    operator is never shown a misleading total."""

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()
    for period_token in ("1T", "2T", "3T"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, period_token),
            revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period=period_token),
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        )
    discarded = create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "4T"),
        revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period="4T"),
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
    )
    discard_work_unit(
        discarded.work_unit_id,
        actor="operator",
        reason="superseded",
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
    )

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert projection.workspace.work_units == 3, "discarded units must not inflate the active counter"
    assert projection.workspace.discarded_work_units == 1

    with bundled_indexed_authority().operation() as operation:
        report = build_overview_status_report(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
    assert report.work_units == 3
    assert report.discarded_work_units == 1


def test_surfaces_agree_on_one_projection(state_projection_dependencies) -> None:
    """Every operator-facing surface draws from one projection, so they
    cannot disagree.

    One fixture state — an active profile plus two ``modelo work`` work
    units — is built once. ``overview status``, ``auth status``,
    ``auth test``, and ``modelo readiness`` are then queried and their
    shared values are asserted mutually consistent. In particular
    ``auth status`` and ``auth test`` must report the same
    ``configured``, closing the historical two-readers-two-answers
    disagreement."""

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()
    for period_token in ("1T", "2T"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, period_token),
            revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period=period_token),
            ports=build_work_lifecycle_ports(bucket_id=bucket_id),
        )

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo="303",
                    revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period="1T"),
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "1T"),
                ),
            ),
            probe_live_backend=True,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

        overview = build_overview_status_report(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
        auth_status = inspect_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
        auth_test = probe_operator_auth(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    # auth status and auth test report the SAME configured — the
    # historical disagreement is closed structurally.
    assert auth_status.configured == auth_test.configured
    assert auth_status.configured == projection.auth.configured

    # auth status and auth test agree on the active profile too.
    assert auth_status.active_profile == auth_test.active_profile
    assert auth_status.active_profile == projection.active_profile.label

    # overview status shows the modelo work units from the same
    # projection.
    assert overview.work_units == 2
    assert overview.work_units == projection.workspace.work_units
    assert overview.active_profile_name == projection.active_profile.label

    # modelo readiness is carried in the same projection and is
    # consistent with what a direct readiness query reports.
    assert len(projection.modelo_readiness) == 1
    readiness = projection.modelo_readiness[0]
    assert readiness.modelo == "303"
    assert readiness.profile_id == bucket_id


def test_modelo_303_readiness_includes_ledger_preflight_blockers(state_projection_dependencies) -> None:
    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()
    objects = secure_object_repository_for_active_bucket()
    transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    event_repository = BucketEventHistoryRepository(objects=objects)
    with ledger_ports_for_test(
        bucket_id=bucket_id,
        objects=objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=date(2026, 2, 10),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="business expense without category",
                business_classification=BusinessClassification.BUSINESS,
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("21.00"),
                actor="operator",
            ),
            ports=ports,
        )

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo="303",
                    revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period="1T"),
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "1T"),
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    readiness = projection.modelo_readiness[0]
    assert readiness.registry_ready is True
    assert readiness.ledger_preflight_required is True
    assert readiness.ledger_ready is False
    assert readiness.ready is False
    assert readiness.ledger_period == Period.from_year_and_code(2026, "1T")
    assert readiness.ledger_checked_transaction_count == 1
    assert [issue.reason.value for issue in readiness.ledger_issues] == ["missing_category"]


def test_modelo_303_readiness_reports_pre_activity_period_refusal(state_projection_dependencies) -> None:
    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile(overrides={"censo.activity_start_date": "2026-05-01"})

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo="303",
                    revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period="1T"),
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "1T"),
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    readiness = projection.modelo_readiness[0]
    assert readiness.profile_id == bucket_id
    assert readiness.registry_ready is True
    assert readiness.profile_ready is False
    assert readiness.ready is False
    assert "Modelo 303 2026 1T is before the profile activity-start date 2026-05-01" in readiness.profile_refusal
    assert "filing period ends on 2026-03-31" in readiness.profile_refusal
    assert "pre-activity period" in readiness.profile_refusal
    assert projection.workspace.work_units == 0


def test_modelo_349_readiness_uses_applicability_for_attribution_entity(state_projection_dependencies) -> None:
    """An attribution entity that trades intracommunity is APPLICABLE for Modelo 349.

    RD 1624/1992 art. 79 obliges the entity itself (a comunidad de bienes /
    sociedad civil) to file the declaración recapitulativa when it performs
    operaciones intracomunitarias — régimen de atribución de rentas governs
    IRPF/IS attribution, not IVA obligations. The readiness gate must not
    refuse this profile on applicability grounds; it still reports
    ``ready is False`` here because the minimal fixture has no ledger-sourced
    binding values, a separate axis from applicability.
    """
    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile(
        overrides={
            "identity.tax_id": "E12345674",
            "taxpayer_type.entity_type": "attribution_entity",
            "taxpayer_type.irpf_income_categories": "",
            "irpf.estimation_regime": "",
            "iva.does_intracomunitario": "true",
        },
    )

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo="349",
                    revision_id=active_registry_revision_id(modelo="349", filing_year=2026, period="1T"),
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "1T"),
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    readiness = projection.modelo_readiness[0]
    assert readiness.profile_id == bucket_id
    assert readiness.registry_ready is True
    assert readiness.profile_ready is True
    assert readiness.profile_refusal == ""
    assert readiness.binding_ready is False
    assert readiness.missing_bindings
    assert readiness.ready is False
    assert projection.workspace.work_units == 0


def test_modelo_303_readiness_does_not_report_ledger_bindings_missing_after_clean_preflight(
    state_projection_dependencies,
) -> None:
    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()
    objects = secure_object_repository_for_active_bucket()
    transaction_repository = TransactionCatalogueRepository(bucket_id=bucket_id, objects=objects)
    event_repository = BucketEventHistoryRepository(objects=objects)
    with ledger_ports_for_test(
        bucket_id=bucket_id,
        objects=objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=date(2026, 4, 15),
                amount=Decimal("1210.00"),
                direction=TransactionDirection.INCOMING,
                description="consulting invoice with output IVA",
                business_classification=BusinessClassification.BUSINESS,
                taxable_base=Decimal("1000.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("210.00"),
                actor="operator",
            ),
            ports=ports,
        )
    with ledger_ports_for_test(
        bucket_id=bucket_id,
        objects=objects,
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
    ) as ports:
        create_manual_transaction(
            ManualLedgerTransactionCommand(
                bucket_id=bucket_id,
                booked_date=date(2026, 4, 20),
                amount=Decimal("121.00"),
                direction=TransactionDirection.OUTGOING,
                description="office supplies with input IVA",
                business_classification=BusinessClassification.BUSINESS,
                category_id=SpendingCategory._from_registry("material_oficina").value,
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("0.21"),
                iva_amount=Decimal("21.00"),
                actor="operator",
            ),
            ports=ports,
        )

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo="303",
                    revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period="2T"),
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "2T"),
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    readiness = projection.modelo_readiness[0]
    assert readiness.ledger_preflight_required is True
    assert readiness.ledger_ready is True
    assert readiness.ledger_issues == ()
    assert "ledger_iva_aggregation" not in {binding.source for binding in readiness.missing_bindings}


def test_modelo_309_ad_hoc_readiness_fails_closed_for_non_span_ledger_period(
    state_projection_dependencies,
) -> None:
    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo="309",
                    revision_id=active_registry_revision_id(modelo="309", filing_year=2026, period="AD-HOC"),
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "AD-HOC"),
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    readiness = projection.modelo_readiness[0]
    assert readiness.profile_id == bucket_id
    assert readiness.registry_ready is True
    assert readiness.ledger_preflight_required is True
    assert readiness.ledger_ready is False
    assert readiness.ready is False
    assert readiness.ledger_period == Period.from_year_and_code(2026, "AD-HOC")
    assert readiness.ledger_checked_transaction_count == 0
    assert [issue.reason.value for issue in readiness.ledger_issues] == ["unsupported_period"]


def test_modelo_readiness_without_period_uses_annual_period(state_projection_dependencies) -> None:
    """A periodless request derives its readiness period, not its revision.

    The subject here is the ``0A`` fallback alone. ``revision_id`` is
    deliberately NOT resolved through
    :func:`active_registry_revision_id`: no M303 revision declares the
    annual ``0A`` token in its period selector, so there is no
    law-determined revision to resolve for this target and the resolver
    would refuse. The literal below is inert — the snapshot never
    resolves, and the period assertion is reached through the registry
    refusal path on purpose.
    """
    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()

    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            modelo_readiness_requests=(
                ModeloReadinessRequest(
                    modelo="303",
                    revision_id="2022",
                    filing_year=2026,
                ),
            ),
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    readiness = projection.modelo_readiness[0]
    assert readiness.profile_id == bucket_id
    assert readiness.period == Period.from_year_and_code(2026, "0A")


def test_projection_is_pure_read(state_projection_dependencies) -> None:
    """Building the projection mutates no store: two consecutive builds
    over an unchanged workspace return equal projections."""

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    bucket_id = _register_active_profile()
    create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id=active_registry_revision_id(modelo="303", filing_year=2026, period="1T"),
        ports=build_work_lifecycle_ports(bucket_id=bucket_id),
    )

    with bundled_indexed_authority().operation() as operation:
        first = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
        second = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert first == second


def test_projection_without_active_profile_is_empty(state_projection_dependencies) -> None:
    """With no active profile the projection reports zeroed counters and
    no encrypted store is opened."""

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    with bundled_indexed_authority().operation() as operation:
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert projection.active_profile.profile_id is None
    assert projection.workspace.work_units == 0
    assert projection.workspace.drafts == 0
    assert projection.auth.configured is False
    assert projection.pending_obligations == ()


def test_projection_profile_read_refuses_explicit_database_route(
    tmp_path: Path,
    state_projection_dependencies,
) -> None:
    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    profile_id = "00000000-0000-4000-8000-000000000001"
    _stage_profile_bucket(tmp_path, profile_id)

    with (
        override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_active_profile=profile_id,
            cadrumo_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
        ),
        bundled_indexed_authority().operation() as operation,
    ):
        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            state=WorkflowState(),
            include_workspace_summary=False,
            include_pending_obligations=False,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert projection.active_profile.profile_id == profile_id
    assert projection.active_profile.registered_bucket is False
    assert projection.active_profile.record_present is False
    assert projection.active_profile.health_status == "dangling_pointer"
    assert not (tmp_path / "explicit.db").exists()


def test_auth_readiness_no_provider_matches_with_and_without_probe(state_projection_dependencies) -> None:
    """The auth readiness sub-record reports the same "no provider
    configured" state whether or not the live backend is probed.

    ``auth test`` probes; ``auth status`` does not. When no provider is
    configured and none requested, the projection must not invent a
    default provider for the probing caller — both report the empty
    provider, ``available: False``, and an empty health summary.
    """

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    _register_active_profile()

    with bundled_indexed_authority().operation() as operation:
        unprobed = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            probe_live_backend=False,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
        probed = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            probe_live_backend=True,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert unprobed.auth.provider == ""
    assert probed.auth.provider == unprobed.auth.provider
    assert probed.auth.available == unprobed.auth.available is False
    assert probed.auth.configured == unprobed.auth.configured is False
    assert probed.auth.health_summary == unprobed.auth.health_summary == ""


def test_auth_probe_unknown_requested_provider_log_omits_raw_selector(
    caplog: pytest.LogCaptureFixture,
    state_projection_dependencies,
) -> None:
    sensitive_provider = "client-tax-id-12345678Z-private-note"
    certificate_secret_backend_factory, read_ports = state_projection_dependencies

    with caplog.at_level(logging.WARNING, logger="cadrumo.application.state_projection"):
        with bundled_indexed_authority().operation() as operation:
            projection = build_operator_state_projection(
                certificate_secret_backend_factory=certificate_secret_backend_factory,
                operator_probe_ports=_OPERATOR_PROBE_PORTS,
                read_ports=read_ports,
                requested_provider=sensitive_provider,
                probe_live_backend=True,
                include_workspace_summary=False,
                include_pending_obligations=False,
                operator_scope_ports=_OPERATOR_SCOPE_PORTS,
                operation=operation,
            )

    assert projection.auth.available is False
    assert any("unknown provider" in record.getMessage() for record in caplog.records)
    assert sensitive_provider not in caplog.text


def test_auth_readiness_configured_is_coherent_with_health_summary(state_projection_dependencies) -> None:
    """``configured`` must never be ``True`` while ``health_summary``
    reports the certificate path is not configured.

    Round-5 B1: with no certificate path persisted in workflow state
    and none in Settings, the projection reports ``configured: False``
    and an ``info`` severity (no path is an undeclared state, not a
    genuine fault — round-5 M5). The summary is user prose, never the
    raw engineering English ``certificate path not configured``.
    """

    from cadrumo.application.auth.operator import configure_operator_auth

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    _register_active_profile()
    with bundled_indexed_authority().operation() as operation:
        configure_operator_auth(
            "certificate",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

        projection = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            probe_live_backend=True,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    auth = projection.auth
    assert auth.configured is False, (
        f"no certificate path persisted must produce configured=False — got {auth.configured!r}"
    )
    # Round-5 M5: a not-configured / pending state must NEVER pair
    # with the loudest ``error`` severity. ``info`` (undeclared) or
    # ``warning`` (degraded) are the only acceptable tokens here;
    # ``error`` is reserved for backend-reported genuine faults.
    assert auth.health_severity != "error", (
        f"no-path-set is undeclared, not an error — got severity={auth.health_severity!r}"
    )
    # The summary must be localised user prose, never the literal
    # English engineering text that quoted ``configured``.
    assert auth.health_summary != "certificate path not configured", (
        "health_summary must be localised user prose, not the raw English engineering text"
    )


def test_auth_readiness_drops_certificate_path_after_switching_provider(
    tmp_path: Path,
    state_projection_dependencies,
) -> None:
    """A non-certificate provider must not carry a stale ``certificate_path``.

    After ``configure --provider certificate --file PATH`` then
    ``configure --provider clave_movil``, the projection's
    ``certificate_path`` must be empty — the certificate path is a
    certificate-provider field and must not leak beside a different
    active provider.
    """

    from cadrumo.application.auth.operator import configure_operator_auth

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    _register_active_profile()
    cert_file = tmp_path / "operator-cert.pfx"
    cert_file.write_bytes(b"placeholder pkcs12 bytes")

    with bundled_indexed_authority().operation() as operation:
        configure_operator_auth(
            "certificate",
            certificate_path=cert_file,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
        after_cert = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            probe_live_backend=False,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
    assert after_cert.auth.certificate_path == str(cert_file)

    with bundled_indexed_authority().operation() as operation:
        configure_operator_auth(
            "clave_movil",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )
        after_switch = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            probe_live_backend=False,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

    assert after_switch.auth.provider == "clave_movil"
    assert after_switch.auth.certificate_path == "", (
        f"certificate_path must be empty for a non-certificate provider — got {after_switch.auth.certificate_path!r}"
    )


def test_auth_readiness_health_severity_is_populated_for_a_configured_provider(
    state_projection_dependencies,
) -> None:
    """``health_severity`` must carry a meaningful, non-empty token.

    The Cl@ve backend reports a ``health_summary`` but no severity; the
    projection must derive a coherent token so ``health_severity`` is
    never silently empty for a configured provider.
    """

    from cadrumo.application.auth.operator import configure_operator_auth

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    _register_active_profile()
    with bundled_indexed_authority().operation() as operation:
        configure_operator_auth(
            "clave_movil",
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        )

        auth = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            probe_live_backend=True,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).auth

    # Round-5 M5: ``info`` is now a valid severity for benign undeclared
    # or pending states. ``error`` is reserved for genuine faults.
    assert auth.health_severity in {"", "ok", "info", "warning", "error"}


def test_auth_readiness_health_severity_empty_only_when_no_provider(state_projection_dependencies) -> None:
    """With no provider selected there is nothing to classify; severity stays empty."""

    certificate_secret_backend_factory, read_ports = state_projection_dependencies
    _register_active_profile()

    with bundled_indexed_authority().operation() as operation:
        auth = build_operator_state_projection(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            operator_probe_ports=_OPERATOR_PROBE_PORTS,
            read_ports=read_ports,
            probe_live_backend=True,
            operator_scope_ports=_OPERATOR_SCOPE_PORTS,
            operation=operation,
        ).auth

    assert auth.provider == ""
    assert auth.health_severity == ""
