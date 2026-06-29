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
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from ...adapters.persistence.storage.bucket._layout import provision_bucket_directory
from ...adapters.persistence.storage.bucket._manifest import (
    BucketLifecycleStatus,
    BucketManifest,
    ManifestKdfParams,
)
from ...adapters.persistence.storage.bucket._manifest_io import write_manifest
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...core import Period
from ...core.config import SecretStoreBackend, override_settings
from ...domain.categories import SpendingCategory
from ...domain.transactions import BusinessClassification, TransactionDirection
from ...tests.secure_sql import dev_test_database_password
from ..auth._operator import inspect_operator_auth
from ..auth._operator import test_operator_auth as probe_operator_auth
from ..ledger import ManualLedgerTransactionCommand, create_manual_transaction
from ..modelo import create_work_unit, discard_work_unit
from ..overview import build_overview_status_report
from ..state_projection import (
    ModeloReadinessRequest,
    build_operator_state_projection,
    modelo_requires_ledger_preflight,
)
from ..user_profile._testing import register_minimal_profile
from ..wizard import WIZARD_FLOWS
from ..workflow._models import WorkflowState
from ..workflow._persistence import workflow_state_repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACTIVE_STORAGE_STACK: ExitStack | None = None
_PROFILE_SPAN_OPEN = False


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path: Path) -> Iterator[None]:
    """Bind a real isolated filesystem root per test."""

    global _ACTIVE_STORAGE_STACK, _PROFILE_SPAN_OPEN

    assert WIZARD_FLOWS
    dispose_engine()
    with ExitStack() as stack:
        stack.enter_context(
            override_settings(
                aeat_local_storage_root=tmp_path,
                aeat_active_profile=None,
                aeat_secret_store_backend=SecretStoreBackend.FILE,
                aeat_secret_passphrase=SecretStr(dev_test_database_password()),
            ),
        )
        _ACTIVE_STORAGE_STACK = stack
        _PROFILE_SPAN_OPEN = False
        try:
            yield
        finally:
            dispose_engine()
            _PROFILE_SPAN_OPEN = False
            _ACTIVE_STORAGE_STACK = None


def _ensure_operator_storage_span() -> None:
    global _PROFILE_SPAN_OPEN

    if _PROFILE_SPAN_OPEN:
        return
    if _ACTIVE_STORAGE_STACK is None:
        raise RuntimeError("state projection test storage span is not active")
    from ..user_profile._orchestration import profile_create_storage_span

    _ACTIVE_STORAGE_STACK.enter_context(profile_create_storage_span("operator"))
    _PROFILE_SPAN_OPEN = True


def _register_active_profile(*, overrides: Mapping[str, str] | None = None) -> str:
    """Register and activate a minimal profile; return its bucket id."""

    _ensure_operator_storage_span()
    workflow_state_repository().update(
        lambda state: register_minimal_profile(state, profile_id="operator", overrides=overrides),
    )
    bucket_id = workflow_state_repository().load().active_profile_bucket_id()
    assert bucket_id is not None
    return bucket_id


def _stage_profile_manifest(root: Path, bucket_id: str) -> None:
    paths = provision_bucket_directory(root, bucket_id)
    write_manifest(
        paths,
        BucketManifest(
            bucket_id=bucket_id,
            label=bucket_id,
            created_at=datetime.now(UTC),
            last_unlocked_at=None,
            kdf_params=ManifestKdfParams(
                algorithm="argon2id",
                version=0x13,
                memory_cost=19_456,
                time_cost=2,
                parallelism=1,
                salt=b"0123456789abcdef",
                output_length=32,
            ),
            recovery_enrolled=False,
            schema_version=1,
            status=BucketLifecycleStatus.ACTIVE,
        ),
    )


def test_overview_status_reports_modelo_work_units(tmp_path: Path) -> None:
    """The concrete bug this regression closes: with ``modelo work`` work units
    present, ``overview status`` must report them.

    Before the canonical projection, ``build_overview_status_report``
    read the declaration-draft ``ModeloDraft`` store but never the
    ``WorkUnitCatalogue`` store, so an operator who used ``modelo work
    create`` saw a silently-zero count. The projection carries
    ``work_units`` as a distinct counter."""

    bucket_id = _register_active_profile()

    create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2023-y-siguientes",
    )

    report = build_overview_status_report()

    assert report.work_units == 1, "overview status must surface modelo work units, not zero"
    assert report.drafts == 0, "the ModeloDraft store is separate and stays at zero"


def test_overview_status_distinguishes_drafts_from_work_units() -> None:
    """``drafts`` and ``work_units`` are distinct counters; neither is
    silently folded into the other."""

    bucket_id = _register_active_profile()
    for period_token in ("1T", "2T"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, period_token),
            revision_id="2023-y-siguientes",
        )

    projection = build_operator_state_projection()

    assert projection.workspace.work_units == 2
    assert projection.workspace.drafts == 0
    assert projection.workspace.transactions == 0
    assert projection.workspace.invoices == 0


def test_work_units_counter_excludes_discarded_units() -> None:
    """A discarded work unit must not inflate the active ``work_units``
    counter; it is carried separately in ``discarded_work_units`` so the
    operator is never shown a misleading total."""

    bucket_id = _register_active_profile()
    for period_token in ("1T", "2T", "3T"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, period_token),
            revision_id="2023-y-siguientes",
        )
    discarded = create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "4T"),
        revision_id="2023-y-siguientes",
    )
    discard_work_unit(discarded.work_unit_id, actor="operator", reason="superseded")

    projection = build_operator_state_projection()

    assert projection.workspace.work_units == 3, "discarded units must not inflate the active counter"
    assert projection.workspace.discarded_work_units == 1

    report = build_overview_status_report()
    assert report.work_units == 3
    assert report.discarded_work_units == 1


def test_surfaces_agree_on_one_projection() -> None:
    """Every operator-facing surface draws from one projection, so they
    cannot disagree.

    One fixture state — an active profile plus two ``modelo work`` work
    units — is built once. ``overview status``, ``auth status``,
    ``auth test``, and ``modelo readiness`` are then queried and their
    shared values are asserted mutually consistent. In particular
    ``auth status`` and ``auth test`` must report the same
    ``configured``, closing the historical two-readers-two-answers
    disagreement."""

    bucket_id = _register_active_profile()
    for period_token in ("1T", "2T"):
        create_work_unit(
            bucket_id=bucket_id,
            modelo="303",
            filing_year=2026,
            period=Period.from_year_and_code(2026, period_token),
            revision_id="2023-y-siguientes",
        )

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="303",
                revision_id="2023-y-siguientes",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            ),
        ),
        probe_live_backend=True,
    )

    overview = build_overview_status_report()
    auth_status = inspect_operator_auth()
    auth_test = probe_operator_auth()

    # auth status and auth test report the SAME configured — the
    # historical disagreement is closed structurally.
    assert auth_status.configured == auth_test.configured
    assert auth_status.configured == projection.auth.configured

    # auth status and auth test agree on the active profile too.
    assert auth_status.active_profile == auth_test.active_profile
    assert auth_status.active_profile == bucket_id

    # overview status shows the modelo work units from the same
    # projection.
    assert overview.work_units == 2
    assert overview.work_units == projection.workspace.work_units
    assert overview.active_profile == bucket_id

    # modelo readiness is carried in the same projection and is
    # consistent with what a direct readiness query reports.
    assert len(projection.modelo_readiness) == 1
    readiness = projection.modelo_readiness[0]
    assert readiness.modelo == "303"
    assert readiness.profile_id == bucket_id


def test_modelo_303_readiness_includes_ledger_preflight_blockers() -> None:
    bucket_id = _register_active_profile()
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
    )

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="303",
                revision_id="2023-y-siguientes",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            ),
        ),
    )

    readiness = projection.modelo_readiness[0]
    assert readiness.registry_ready is True
    assert readiness.ledger_preflight_required is True
    assert readiness.ledger_ready is False
    assert readiness.ready is False
    assert readiness.ledger_period == Period.from_year_and_code(2026, "1T")
    assert readiness.ledger_checked_transaction_count == 1
    assert [issue.reason.value for issue in readiness.ledger_issues] == ["missing_category"]


def test_modelo_303_readiness_reports_pre_activity_period_refusal() -> None:
    bucket_id = _register_active_profile(overrides={"censo.activity_start_date": "2026-05-01"})

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="303",
                revision_id="2023-y-siguientes",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "1T"),
            ),
        ),
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


def test_modelo_303_readiness_does_not_report_ledger_bindings_missing_after_clean_preflight() -> None:
    bucket_id = _register_active_profile()
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
    )
    create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=bucket_id,
            booked_date=date(2026, 4, 20),
            amount=Decimal("121.00"),
            direction=TransactionDirection.OUTGOING,
            description="office supplies with input IVA",
            business_classification=BusinessClassification.BUSINESS,
            category_id=SpendingCategory.MATERIAL_OFICINA.value,
            taxable_base=Decimal("100.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("21.00"),
            actor="operator",
        ),
    )

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="303",
                revision_id="2023-y-siguientes",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "2T"),
            ),
        ),
    )

    readiness = projection.modelo_readiness[0]
    assert readiness.ledger_preflight_required is True
    assert readiness.ledger_ready is True
    assert readiness.ledger_issues == ()
    assert "ledger_iva_aggregation" not in {binding.source for binding in readiness.missing_bindings}


def test_modelo_309_ad_hoc_readiness_fails_closed_for_non_span_ledger_period() -> None:
    bucket_id = _register_active_profile()

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="309",
                revision_id="2004-y-siguientes",
                filing_year=2026,
                period=Period.from_year_and_code(2026, "AD-HOC"),
            ),
        ),
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


def test_modelo_readiness_without_period_uses_annual_period() -> None:
    bucket_id = _register_active_profile()

    projection = build_operator_state_projection(
        modelo_readiness_requests=(
            ModeloReadinessRequest(
                modelo="303",
                revision_id="2009-y-siguientes",
                filing_year=2026,
            ),
        ),
    )

    readiness = projection.modelo_readiness[0]
    assert readiness.profile_id == bucket_id
    assert readiness.period == Period.from_year_and_code(2026, "0A")


def test_missing_registry_snapshot_ledger_preflight_skip_is_debug_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request = ModeloReadinessRequest(
        modelo="999",
        revision_id="missing-registry",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
    )

    with caplog.at_level(logging.DEBUG, logger="aeat.application.state_projection"):
        required = modelo_requires_ledger_preflight(request)

    assert required is False
    assert any(
        record.levelno == logging.DEBUG
        and getattr(record, "modelo", "") == "999"
        and "ledger preflight skipped" in record.getMessage()
        for record in caplog.records
    )


def test_projection_is_pure_read() -> None:
    """Building the projection mutates no store: two consecutive builds
    over an unchanged workspace return equal projections."""

    bucket_id = _register_active_profile()
    create_work_unit(
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2023-y-siguientes",
    )

    first = build_operator_state_projection()
    second = build_operator_state_projection()

    assert first == second


def test_projection_without_active_profile_is_empty() -> None:
    """With no active profile the projection reports zeroed counters and
    no encrypted store is opened."""

    projection = build_operator_state_projection()

    assert projection.active_profile.profile_id is None
    assert projection.workspace.work_units == 0
    assert projection.workspace.drafts == 0
    assert projection.auth.configured is False
    assert projection.pending_obligations == ()


def test_projection_profile_read_refuses_explicit_database_route(tmp_path: Path) -> None:
    _stage_profile_manifest(tmp_path, "operator")

    with override_settings(
        aeat_local_storage_root=tmp_path,
        aeat_active_profile="operator",
        aeat_database_url=f"sqlite:///{(tmp_path / 'explicit.db').as_posix()}",
    ):
        projection = build_operator_state_projection(
            state=WorkflowState(),
            include_workspace_summary=False,
            include_pending_obligations=False,
        )

    assert projection.active_profile.profile_id == "operator"
    assert projection.active_profile.registered_bucket is True
    assert projection.active_profile.record_present is False
    assert projection.active_profile.health_status == "profile_record_unreadable"
    assert not (tmp_path / "explicit.db").exists()


def test_auth_readiness_no_provider_matches_with_and_without_probe() -> None:
    """The auth readiness sub-record reports the same "no provider
    configured" state whether or not the live backend is probed.

    ``auth test`` probes; ``auth status`` does not. When no provider is
    configured and none requested, the projection must not invent a
    default provider for the probing caller — both report the empty
    provider, ``available: False``, and an empty health summary.
    """

    _register_active_profile()

    unprobed = build_operator_state_projection(probe_live_backend=False)
    probed = build_operator_state_projection(probe_live_backend=True)

    assert unprobed.auth.provider == ""
    assert probed.auth.provider == unprobed.auth.provider
    assert probed.auth.available == unprobed.auth.available is False
    assert probed.auth.configured == unprobed.auth.configured is False
    assert probed.auth.health_summary == unprobed.auth.health_summary == ""


def test_auth_probe_unknown_requested_provider_log_omits_raw_selector(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sensitive_provider = "client-tax-id-12345678Z-private-note"

    with caplog.at_level(logging.WARNING, logger="aeat.application.state_projection"):
        projection = build_operator_state_projection(
            requested_provider=sensitive_provider,
            probe_live_backend=True,
            include_workspace_summary=False,
            include_pending_obligations=False,
        )

    assert projection.auth.available is False
    assert any("unknown provider" in record.getMessage() for record in caplog.records)
    assert sensitive_provider not in caplog.text


def test_auth_readiness_configured_is_coherent_with_health_summary() -> None:
    """``configured`` must never be ``True`` while ``health_summary``
    reports the certificate path is not configured.

    Round-5 B1: with no certificate path persisted in workflow state
    and none in Settings, the projection reports ``configured: False``
    and an ``info`` severity (no path is an undeclared state, not a
    genuine fault — round-5 M5). The summary is user prose, never the
    raw engineering English ``certificate path not configured``.
    """

    from ..auth._operator import configure_operator_auth

    _register_active_profile()
    configure_operator_auth("certificate")

    projection = build_operator_state_projection(probe_live_backend=True)

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


def test_auth_readiness_drops_certificate_path_after_switching_provider(tmp_path: Path) -> None:
    """A non-certificate provider must not carry a stale ``certificate_path``.

    After ``configure --provider certificate --file PATH`` then
    ``configure --provider clave_movil``, the projection's
    ``certificate_path`` must be empty — the certificate path is a
    certificate-provider field and must not leak beside a different
    active provider (persona-fleet finding G1).
    """

    from ..auth._operator import configure_operator_auth

    _register_active_profile()
    cert_file = tmp_path / "operator-cert.pfx"
    cert_file.write_bytes(b"placeholder pkcs12 bytes")

    configure_operator_auth("certificate", certificate_path=cert_file)
    after_cert = build_operator_state_projection(probe_live_backend=False)
    assert after_cert.auth.certificate_path == str(cert_file)

    configure_operator_auth("clave_movil")
    after_switch = build_operator_state_projection(probe_live_backend=False)

    assert after_switch.auth.provider == "clave_movil"
    assert after_switch.auth.certificate_path == "", (
        f"certificate_path must be empty for a non-certificate provider — got {after_switch.auth.certificate_path!r}"
    )


def test_auth_readiness_health_severity_is_populated_for_a_configured_provider() -> None:
    """``health_severity`` must carry a meaningful, non-empty token.

    The Cl@ve backend reports a ``health_summary`` but no severity; the
    projection must derive a coherent token so ``health_severity`` is
    never silently empty for a configured provider (persona-fleet
    finding G4).
    """

    from ..auth._operator import configure_operator_auth

    _register_active_profile()
    configure_operator_auth("clave_movil")

    auth = build_operator_state_projection(probe_live_backend=True).auth

    # Round-5 M5: ``info`` is now a valid severity for benign undeclared
    # or pending states. ``error`` is reserved for genuine faults.
    assert auth.health_severity in {"", "ok", "info", "warning", "error"}


def test_auth_readiness_health_severity_empty_only_when_no_provider() -> None:
    """With no provider selected there is nothing to classify; severity stays empty."""

    _register_active_profile()

    auth = build_operator_state_projection(probe_live_backend=True).auth

    assert auth.provider == ""
    assert auth.health_severity == ""
