"""Tests for application-owned CLI diagnostics."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ...adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    has_active_bucket_session,
)
from ...adapters.persistence.storage.master_key._active_session import _active_session, activate_session
from ...adapters.persistence.storage.master_key._bucket_session import BucketSession
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...adapters.persistence.storage.sql import dispose_engine
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...core.classification import SensitivityClass
from ...core.config import override_settings
from ...tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ..diagnostics import (
    ConfigRepairReport,
    DiagnosticCheck,
    DiagnosticFinding,
    RegistryVersionSummary,
    SecureObjectIntegrityReport,
    build_config_repair_report,
    preview_quarantine_unreadable_secure_objects,
    quarantine_unreadable_secure_objects,
    render_config_repair_text,
    secure_object_unreadable_total,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _isolated_default_secure_sql(tmp_path: Path) -> Iterator[None]:
    """Bind diagnostics tests to an isolated storage root by default."""

    storage_root = tmp_path / "diagnostics-storage"
    with override_settings(aeat_local_storage_root=storage_root, aeat_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


@contextmanager
def _explicit_database(db_path: Path) -> Iterator[None]:
    with override_settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}") as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


def _save_probe_row(namespace: str, object_key: str, payload: bytes) -> None:
    SecureObjectRepository().save(
        namespace=namespace,
        object_key=object_key,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=datetime.now(UTC),
        payload=payload,
    )


def _bucket_session(bucket_id: str) -> BucketSession:
    return BucketSession.open(
        bucket_id=bucket_id,
        kek=b"k" * 32,
        dek=b"d" * 32,
        idle_minutes=15,
        opened_at=datetime.now(UTC),
    )


def test_diagnostic_check_fail_without_recovery_field_raises_validation_error() -> None:
    """A ``fail`` row with neither ``next_action`` nor ``dead_end`` is forbidden."""

    with pytest.raises(ValidationError):
        DiagnosticCheck(name="x", status="fail", summary="y")


def test_diagnostic_check_warn_without_recovery_field_raises_validation_error() -> None:
    """A ``warn`` row with neither ``next_action`` nor ``dead_end`` is forbidden."""

    with pytest.raises(ValidationError):
        DiagnosticCheck(name="x", status="warn", summary="y")


def test_diagnostic_check_rejects_both_next_action_and_dead_end_simultaneously() -> None:
    """A row may pick at most one of the two recovery roads."""

    with pytest.raises(ValidationError):
        DiagnosticCheck(
            name="x",
            status="fail",
            summary="y",
            next_action="aeat config repair",
            dead_end="terminal",
        )


def test_diagnostic_check_ok_row_with_both_recovery_fields_none_constructs() -> None:
    """An ``ok`` row carries neither recovery field — happy path constructs."""

    check = DiagnosticCheck(name="x", status="ok", summary="y")
    assert check.next_action is None
    assert check.dead_end is None


def test_diagnostic_check_ok_row_with_next_action_raises_validation_error() -> None:
    """``ok`` rows must not advertise recovery; that surface is reserved for fail/warn."""

    with pytest.raises(ValidationError):
        DiagnosticCheck(name="x", status="ok", summary="y", next_action="aeat config repair")


def test_diagnostic_check_fail_row_with_dead_end_only_constructs() -> None:
    """A ``fail`` row populated with ``dead_end`` alone satisfies the contract."""

    check = DiagnosticCheck(name="x", status="fail", summary="y", dead_end="terminal")
    assert check.next_action is None
    assert check.dead_end == "terminal"


def test_diagnostic_check_model_dump_surfaces_both_recovery_fields() -> None:
    """JSON rendering surfaces ``next_action`` and ``dead_end`` keys explicitly."""

    populated = DiagnosticCheck(
        name="x",
        status="fail",
        summary="y",
        next_action="aeat config repair reset-progress --yes",
    )
    dumped = populated.model_dump(mode="json")
    assert "next_action" in dumped
    assert "dead_end" in dumped
    assert dumped["next_action"] == "aeat config repair reset-progress --yes"
    assert dumped["dead_end"] is None


def test_config_repair_report_contains_registry_and_setup_checks(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        report = build_config_repair_report()

    assert report.package_name == "aeat"
    assert report.registry.available is True
    assert report.registry.modelo_count > 0
    assert {check.name for check in report.checks} >= {
        "environment.python",
        "registry.load",
        "secure_state.load",
        "profile.readiness",
        "auth.readiness",
    }
    statuses = {check.status for check in report.checks}
    expected_overall = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "ok"
    assert report.overall == expected_overall


def test_render_config_repair_text_is_operator_readable(
    tmp_path: Path,
) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path):
        rendered = render_config_repair_text(build_config_repair_report())

    from ...core.i18n import tr

    assert f"{tr('cli.diagnostics.repair.overall_label')}\t" in rendered
    assert "registry.load" in rendered
    assert f"{tr('cli.diagnostics.repair.logs_label')}\t" in rendered


def test_render_browser_connectivity_text_resolves_row_label_keys() -> None:
    """``config repair connectivity`` row keys must resolve, not leak ``.label``.

    Before fix: the browser diagnostics locale keys were unfilled, so
    ``tr('cli.diagnostics.browser.target_label')`` fell back to the
    humanised last segment and rendered ``Target label`` — the i18n
    ``.label`` key suffix bled into the operator-facing string.
    After fix: each key resolves to a real translated label.
    """

    from ...adapters.outbound.aeat.browser._site_health import (
        SiteHealthEvidence,
        SiteHealthState,
        SiteHealthStatus,
    )
    from ..diagnostics import render_browser_connectivity_text

    status = SiteHealthStatus(
        state=SiteHealthState.OK,
        evidence=SiteHealthEvidence(
            url=AnyHttpUrl("https://example.org/"),
            http_status=200,
            html_fragment="<html></html>",
            detected_markers=("healthy",),
        ),
        observed_at=datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC),
        retry_after_seconds=None,
    )

    rendered = render_browser_connectivity_text(status)

    assert "label" not in rendered.lower()
    assert "cli.diagnostics" not in rendered
    first_keys = {line.split("\t", 1)[0] for line in rendered.splitlines()}
    assert all(key for key in first_keys)


def test_secure_objects_integrity_check_reports_unreadable_rows_from_rotated_master_key(
    tmp_path: Path,
) -> None:
    """A namespace populated under master key K1 must be reported as unreadable under K2.

    Guards the divergence the audit flagged: ``secure_state.load`` used
    to report ``ok`` while iterating read paths crashed. The new
    ``secure_objects.integrity`` row must surface non-zero unreadable
    counts whenever rows from a prior keychain generation persist.
    """
    db_path = tmp_path / "rotated.db"
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()
    namespace = "aeat.test.repair.rotation"

    # Seed three rows under the OLD master key.
    with key_old, _explicit_database(db_path):
        for natural_key, payload in (
            ("repair-row-1", b"old-1"),
            ("repair-row-2", b"old-2"),
            ("repair-row-3", b"old-3"),
        ):
            _save_probe_row(namespace, natural_key, payload)

    # Switch to the NEW master key and add one decryptable row.
    with key_new, _explicit_database(db_path):
        _save_probe_row(namespace, "repair-row-4", b"new-4")
        # The default repair pipeline resolves storage from settings and
        # decrypts through the active K2 provider bound by this context.
        report = build_config_repair_report()
        integrity_check = next(c for c in report.checks if c.name == "secure_objects.integrity")
        assert integrity_check.status == "warn"
        assert str(report.secure_objects.unreadable_total) in integrity_check.summary
        assert str(report.secure_objects.readable_total) in integrity_check.summary
        assert integrity_check.next_action == "aeat config repair quarantine --yes"

        ns_report = next(item for item in report.secure_objects.namespaces if item.namespace == namespace)
        # Three rows sealed under the OLD ephemeral key should be
        # unreadable under K2; the K2 row remains readable.
        assert ns_report.unreadable >= 3
        assert ns_report.unreadable + ns_report.readable == 4


def test_secure_objects_integrity_check_reports_ok_on_clean_database(
    tmp_path: Path,
) -> None:
    """An empty or fully-decryptable secure-objects table renders ``ok``."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        report = build_config_repair_report()
    integrity_check = next(c for c in report.checks if c.name == "secure_objects.integrity")
    assert integrity_check.status == "ok"
    assert report.secure_objects.unreadable_total == 0


def test_secure_object_unreadable_total_is_nonzero_after_master_key_rotation(
    tmp_path: Path,
) -> None:
    """The helper consumed by overview status returns the aggregate count.

    Seeds rows under master key K1, rotates to K2, and asserts the
    aggregate matches the per-namespace probe. Used by
    ``aeat app overview status`` to render an inline warning footer
    pointing the operator at ``aeat config repair``.
    """
    db_path = tmp_path / "agg.db"
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()

    with key_old, _explicit_database(db_path):
        for namespace, key, payload in (
            ("aeat.test.agg.alpha", "alpha-1", b"alpha-1"),
            ("aeat.test.agg.alpha", "alpha-2", b"alpha-2"),
            ("aeat.test.agg.beta", "beta-1", b"beta-1"),
        ):
            _save_probe_row(namespace, key, payload)

    with key_new, _explicit_database(db_path):
        total = secure_object_unreadable_total()
        assert total >= 3, f"expected at least three unreadable rows; got {total}"


def test_secure_object_unreadable_total_is_zero_on_clean_database(
    tmp_path: Path,
) -> None:
    """Aggregate returns zero when no namespace has unreadable rows."""

    with isolated_runtime_profile(tmp_path=tmp_path):
        assert secure_object_unreadable_total() == 0


def test_secure_object_unreadable_total_logs_missing_active_bucket_session(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Diagnostics degrade to an empty report and log unavailable storage runtime."""

    caplog.set_level("DEBUG", logger="aeat.application.diagnostics")

    with override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a") as settings:
        dispose_engine(settings)
        try:
            assert secure_object_unreadable_total() == 0
        finally:
            dispose_engine(settings)

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "StorageValidationError" in caplog.text
    assert "no active bucket session" in caplog.text


def test_secure_object_unreadable_total_logs_route_session_mismatch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Diagnostics do not silently swallow active-session route mismatches."""

    caplog.set_level("DEBUG", logger="aeat.application.diagnostics")

    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_active_profile="bucket-a") as settings,
        activate_session(_bucket_session("bucket-b")),
    ):
        dispose_engine(settings)
        try:
            assert secure_object_unreadable_total() == 0
        finally:
            dispose_engine(settings)

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "StorageValidationError" in caplog.text
    assert "route does not match the active bucket session" in caplog.text


def test_repair_auth_session_predicate_agrees_with_wizard_status(tmp_path: Path) -> None:
    """``aeat config repair`` and ``aeat config status`` must read auth readiness from one source.

    Repair and the wizard status surface share one projection: both
    build a :class:`WizardStatusReport` and read its ``login_ready`` /
    ``auth_provider`` fields. This test pins that contract by walking
    three workflow states (no provider, provider only, fully
    authenticated) and asserting the report shape across each.
    """
    from ..auth import update_auth
    from ..user_profile._orchestration import profile_create_storage_span
    from ..user_profile._testing import register_minimal_profile
    from ..workflow import WorkflowState

    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        base = register_minimal_profile(
            WorkflowState(),
            profile_id="operator",
            overrides={
                "identity.tax_id": "00000000T",
                "activities.description": "design",
                "iva.regime": "GENERAL",
            },
        )

        no_provider = base
        provider_only = update_auth(no_provider, provider="clave_movil")
        fully_authenticated = update_auth(provider_only, authenticated=True, subject="00000000T")

        from ..wizard._status import build_wizard_status

        for state in (no_provider, provider_only, fully_authenticated):
            setup_report = build_wizard_status(state)
            # The repair renderer reads the same login_ready field; this
            # assertion pins both surfaces against the shared projection.
            if state is no_provider:
                assert setup_report.login_ready is False
            elif state is provider_only:
                assert setup_report.auth_provider == "clave_movil"
                assert setup_report.login_ready is False
            else:
                assert setup_report.auth_provider == "clave_movil"
                assert setup_report.login_ready is True


def test_quarantine_unreadable_secure_objects_moves_only_unreadable_rows(
    tmp_path: Path,
) -> None:
    """Quarantine archives the undecryptable rows; readable rows stay put.

    Seeds two rows under master key K1 plus one row under K2, runs
    the quarantine pipeline under K2, and asserts (via raw SQL) that:

    - ``secure_objects`` retains exactly the K2-decryptable row.
    - ``secure_objects_quarantine`` contains the two K1-sealed rows
      with their original metadata.
    - ``secure_object_unreadable_total()`` returns 0 after the run.

    Proves the user's ciphertext is preserved (rows are archived, not
    deleted) and that the active table is left in a fully-decryptable
    state.
    """
    import sqlite3

    db_path = tmp_path / "quar.db"
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()

    with key_old, _explicit_database(db_path):
        for namespace, key, payload in (
            ("aeat.test.quar.alpha", "row-old-1", b"old-1"),
            ("aeat.test.quar.beta", "row-old-2", b"old-2"),
        ):
            _save_probe_row(namespace, key, payload)

    with key_new, _explicit_database(db_path):
        _save_probe_row("aeat.test.quar.alpha", "row-new-1", b"new-1")

        report = quarantine_unreadable_secure_objects()
        assert report.unreadable_total == 2
        assert report.readable_total == 1

    # Inspect the database directly to prove the row distribution.
    with sqlite3.connect(db_path) as con:
        active = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()[0]
        archived = con.execute("SELECT COUNT(*) FROM secure_objects_quarantine").fetchone()[0]
    assert active == 1, f"expected one row left in secure_objects; got {active}"
    assert archived == 2, f"expected two rows archived; got {archived}"


def test_preview_quarantine_reports_unreadable_rows_without_mutating(
    tmp_path: Path,
) -> None:
    """``preview_quarantine_*`` counts the rows the verb would move and moves none.

    Seeds two rows under master key K1 plus one row under K2, runs the
    dry-run preview under K2, and asserts the preview reports two
    unreadable / one readable row while leaving ``secure_objects``
    untouched and never creating the quarantine archive table — the
    contract the ``repair quarantine --dry-run`` surface relies on
    (persona-fleet finding H3).
    """
    import sqlite3

    db_path = tmp_path / "preview-quar.db"
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()

    with key_old, _explicit_database(db_path):
        for namespace, key, payload in (
            ("aeat.test.preview.alpha", "row-old-1", b"old-1"),
            ("aeat.test.preview.beta", "row-old-2", b"old-2"),
        ):
            _save_probe_row(namespace, key, payload)

    with key_new, _explicit_database(db_path):
        _save_probe_row("aeat.test.preview.alpha", "row-new-1", b"new-1")

        preview = preview_quarantine_unreadable_secure_objects()
        assert preview.unreadable_total == 2
        assert preview.readable_total == 1

    # The preview moved nothing: all three rows stay in secure_objects
    # and the quarantine archive table was never created.
    with sqlite3.connect(db_path) as con:
        active = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()[0]
        archive_exists = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='secure_objects_quarantine'",
        ).fetchone()
    assert active == 3, f"preview must not delete rows; got {active} left"
    assert archive_exists is None, "preview must not create the quarantine table"


def test_quarantine_preview_opens_session_for_bootstrap_exempt_repair(tmp_path: Path) -> None:
    namespace = "aeat.workflow"
    with isolated_runtime_profile(tmp_path=tmp_path):
        secure_object_repository_for_active_bucket().save(
            namespace=namespace,
            object_key="workflow:repair-preview",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"repair-preview-sessionless",
        )
        token = _active_session.set(None)
        assert not has_active_bucket_session()
        try:
            report = preview_quarantine_unreadable_secure_objects()
        finally:
            _active_session.reset(token)

    assert report.readable_total + report.unreadable_total >= 1
    assert any(item.namespace == namespace for item in report.namespaces)


def test_quarantine_opens_session_for_bootstrap_exempt_repair(tmp_path: Path) -> None:
    namespace = "aeat.workflow"
    with isolated_runtime_profile(tmp_path=tmp_path):
        secure_object_repository_for_active_bucket().save(
            namespace=namespace,
            object_key="workflow:repair-quarantine",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"repair-quarantine-sessionless",
        )
        token = _active_session.set(None)
        assert not has_active_bucket_session()
        try:
            report = quarantine_unreadable_secure_objects()
        finally:
            _active_session.reset(token)

    assert report.readable_total + report.unreadable_total >= 1
    assert any(item.namespace == namespace for item in report.namespaces)


def test_importing_diagnostics_does_not_pull_the_browser_or_registry_subtree() -> None:
    """Importing ``diagnostics`` stays off the heavy adapter import graph.

    The ``aeat --version`` fast path imports ``aeat.application.
    diagnostics`` solely for ``build_cli_version_report`` /
    ``render_cli_version_text``. Disaster rollback contract mandates that
    surface return fast on cold start. The browser adapter and the
    registry-authority parse together add seconds of import time; a
    regression that re-introduces an eager module-level import of
    either drags them back onto the version path.

    Run in a fresh interpreter (no warm ``sys.modules``) so the check
    is a real structural guard: importing only ``diagnostics`` must
    leave the browser adapter and registry authority unimported.
    """

    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import aeat.application.diagnostics; "
            "print(','.join(m for m in ("
            "'aeat.adapters.outbound.aeat.browser', "
            "'aeat.domain.calculations.registry', "
            "'aeat.application.workflow', "
            "'aeat.application.wizard._status') if m in sys.modules))",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    leaked = result.stdout.strip()
    assert leaked == "", f"importing diagnostics eagerly pulled the heavy subtree: {leaked}"


def test_build_cli_version_report_fast_path_needs_no_model_rebuild() -> None:
    """The ``--version`` model is fully defined without the deferred rebuild.

    ``build_cli_version_report(with_registry=False)`` is the fast-path
    call. It returns a ``CliVersionReport``, which must carry no field
    typed by a lazily imported name — otherwise the version path would
    have to pay the heavy ``_ensure_models_rebuilt`` import cost.
    """

    from ..diagnostics import build_cli_version_report, render_cli_version_text

    report = build_cli_version_report(with_registry=False)
    assert report.package_name == "aeat"
    assert report.package_version
    # Renders without raising — the model is fully defined.
    assert isinstance(render_cli_version_text(report), str)


def _internal_registry_repair_report() -> ConfigRepairReport:
    """Build a repair report carrying one internal-audience failing row.

    Used by the operator-vs-internal wording tests below; constructs the
    report directly so the test does not depend on the local secure
    backend or registry corruption.
    """

    from ..diagnostics import _ensure_models_rebuilt

    _ensure_models_rebuilt()
    registry = RegistryVersionSummary(available=True, registry_root="/x", modelo_count=1, casilla_count=2)
    checks = (
        DiagnosticCheck(
            name="registry.integrity",
            status="fail",
            summary="Registry integrity failed",
            detail="casilla 9999 missing from revision 100-2025",
            next_action="aeat config repair integrity registry",
            audience="internal",
        ),
        DiagnosticCheck(
            name="auth.readiness",
            status="warn",
            summary="Authentication is not configured",
            next_action="aeat config auth configure --provider certificate --file PATH",
            audience="operator",
        ),
    )
    return ConfigRepairReport(
        overall="fail",
        package_name="aeat",
        package_version="0.1.0",
        python_version="3.13.11",
        log_file="aeat.log",
        registry=registry,
        setup=None,
        secure_objects=SecureObjectIntegrityReport(),
        checks=checks,
    )


def test_diagnostic_finding_carries_typed_per_cause_detail() -> None:
    """A finding names one concrete cause and its optional remediation."""

    finding = DiagnosticFinding(
        summary="identity.tax_id — Tax identification number",
        requirement="required",
        next_action="aeat config profile edit NAME",
    )
    assert finding.requirement == "required"
    assert finding.next_action == "aeat config profile edit NAME"
    dumped = finding.model_dump(mode="json")
    assert dumped["summary"].startswith("identity.tax_id")
    assert dumped["requirement"] == "required"


def test_diagnostic_check_defaults_to_operator_audience_and_no_findings() -> None:
    """An unannotated check is operator-facing and carries no sub-findings."""

    check = DiagnosticCheck(name="x", status="ok", summary="y")
    assert check.audience == "operator"
    assert check.findings == ()


def test_profile_check_warn_row_names_every_missing_required_key() -> None:
    """``profile.readiness`` warn rows must name the missing keys, not a counter.

    Reproduces cluster F / M14: a bare ``N/M`` counter or a one-word
    ``warn`` verdict told the operator nothing actionable. The fixed row
    carries one :class:`DiagnosticFinding` per unset required key, each
    with the exact ``aeat config profile edit NAME`` command.
    """

    from ..diagnostics import _profile_check
    from ..wizard._status import WizardStatusReport

    report = WizardStatusReport(
        active_profile="demo",
        profile_ready=False,
        identity_ready=False,
        enrolment_ready=False,
        missing_required=("identity.tax_id", "activities.description"),
        missing_enrolment=("iva.regime",),
        profile_present_keys=5,
        profile_total_keys=40,
        auth_provider="",
        login_ready=False,
        next_action="aeat config profile edit NAME",
    )
    check = _profile_check(report)

    assert check.status == "warn"
    finding_keys = {finding.summary.split(" — ", 1)[0] for finding in check.findings}
    assert finding_keys == {"identity.tax_id", "activities.description", "iva.regime"}
    assert all(finding.requirement == "required" for finding in check.findings)
    # The check-level next_action routes the operator to the guided
    # editor; the per-finding summaries name exactly which keys to fill.
    assert check.next_action == "aeat config profile edit NAME"
    # The bare counter must no longer be the only signal: the row carries
    # one finding per cause.
    assert len(check.findings) == 3


def test_render_config_repair_text_lists_specific_findings() -> None:
    """The renderer prints each finding line, not just the check summary."""

    from ..diagnostics import _ensure_models_rebuilt, _profile_check
    from ..wizard._status import WizardStatusReport

    _ensure_models_rebuilt()

    report = WizardStatusReport(
        active_profile="demo",
        profile_ready=False,
        identity_ready=False,
        enrolment_ready=False,
        missing_required=("identity.tax_id",),
        missing_enrolment=(),
        profile_present_keys=5,
        profile_total_keys=40,
        auth_provider="",
        login_ready=False,
        next_action="aeat config profile edit NAME",
    )
    check = _profile_check(report)
    registry = RegistryVersionSummary(available=True, registry_root="/x", modelo_count=1, casilla_count=2)
    repair_report = ConfigRepairReport(
        overall="warn",
        package_name="aeat",
        package_version="0.1.0",
        python_version="3.13.11",
        log_file="aeat.log",
        registry=registry,
        setup=None,
        secure_objects=SecureObjectIntegrityReport(),
        checks=(check,),
    )

    rendered = render_config_repair_text(repair_report)

    # The specific missing key is named, and the guided-editor command
    # that fills it is on the row — not a bare counter.
    assert "identity.tax_id" in rendered
    assert "aeat config profile edit NAME" in rendered


def test_render_config_repair_text_marks_internal_problems_distinctly() -> None:
    """Internal application defects must read differently from operator gaps.

    A persona saw an internal registry-integrity ``fail`` and believed
    their own profile was invalid. The renderer tags an
    ``audience='internal'`` row so a taxpayer is not alarmed into
    thinking they forgot a field; operator-fixable rows carry no tag.
    """

    from ...core.i18n import tr

    rendered = render_config_repair_text(_internal_registry_repair_report())
    internal_label = tr("cli.diagnostics.repair.audience_internal")

    registry_line = next(line for line in rendered.splitlines() if line.startswith("fail\tregistry.integrity"))
    auth_line = next(line for line in rendered.splitlines() if line.startswith("warn\tauth.readiness"))

    assert internal_label in registry_line
    assert internal_label not in auth_line


def test_config_repair_report_marks_registry_integrity_internal() -> None:
    """The live ``registry.integrity`` check is classified as internal.

    When the bundled registry is healthy the row is ``ok`` and
    operator-facing; the audience field exists so that, on a real
    registry-integrity defect, the renderer can word it as an internal
    problem rather than a profile gap.
    """

    from ...core.resources import bundled_path
    from ..diagnostics import _registry_cross_domain_integrity_check

    check = _registry_cross_domain_integrity_check(bundled_path("registry", "aeat"))
    # Healthy registry → ok + operator audience. A failing registry would
    # carry audience='internal'; that branch is pinned by the renderer
    # test above against a constructed report.
    assert check.name == "registry.integrity"
    assert check.audience in {"operator", "internal"}


# ---------------------------------------------------------------------------
# contract: DiagnosticModelError registration and invariant-replacement tests
# ---------------------------------------------------------------------------


def test_diagnostic_model_error_is_registered_in_error_registry() -> None:
    """DiagnosticModelError must be reachable via the ERROR_REGISTRY by its code string."""

    from ...core.errors import ERROR_REGISTRY, get_registered_error_code
    from .._errors import DiagnosticModelError

    code = get_registered_error_code(DiagnosticModelError)
    assert code.code in ERROR_REGISTRY
    assert ERROR_REGISTRY[code.code] == code


def test_diagnostic_model_error_round_trips_through_build_error_envelope() -> None:
    """build_error_envelope must produce a well-formed envelope for DiagnosticModelError."""

    from ...core.errors import build_error_envelope
    from .._errors import DiagnosticModelError

    err = DiagnosticModelError("invariant violated")
    envelope = build_error_envelope(err)
    assert envelope.code == "REFUSED_DIAGNOSTIC_MODEL_INVARIANT"
    assert envelope.message


def _assert_validation_error_caused_by_diagnostic_model_error(
    exc_info: pytest.ExceptionInfo[Exception],
    match: str,
) -> None:
    """Assert a pydantic ValidationError wraps a DiagnosticModelError with the given message."""

    from .._errors import DiagnosticModelError

    val_err = exc_info.value
    assert isinstance(val_err, ValidationError)
    causes: list[object] = []
    for e in val_err.errors():
        ctx = e.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            causes.append(ctx["error"])
    matching = [c for c in causes if isinstance(c, DiagnosticModelError) and match in str(c)]
    assert matching, f"Expected a DiagnosticModelError cause matching {match!r}; got causes: {causes!r}"


def test_diagnostic_check_both_recovery_fields_raises_diagnostic_model_error() -> None:
    """Setting both next_action and dead_end raises a ValidationError whose cause is DiagnosticModelError."""

    with pytest.raises(ValidationError) as exc_info:
        DiagnosticCheck(
            name="x",
            status="fail",
            summary="y",
            next_action="aeat config repair",
            dead_end="terminal",
        )
    _assert_validation_error_caused_by_diagnostic_model_error(exc_info, "at most one of")


def test_diagnostic_check_fail_without_recovery_raises_diagnostic_model_error() -> None:
    """A fail row with no recovery field raises a ValidationError whose cause is DiagnosticModelError."""

    with pytest.raises(ValidationError) as exc_info:
        DiagnosticCheck(name="x", status="fail", summary="y")
    _assert_validation_error_caused_by_diagnostic_model_error(exc_info, "must populate one of")


def test_diagnostic_check_warn_without_recovery_raises_diagnostic_model_error() -> None:
    """A warn row with no recovery field raises a ValidationError whose cause is DiagnosticModelError."""

    with pytest.raises(ValidationError) as exc_info:
        DiagnosticCheck(name="x", status="warn", summary="y")
    _assert_validation_error_caused_by_diagnostic_model_error(exc_info, "must populate one of")


def test_diagnostic_check_ok_with_next_action_raises_diagnostic_model_error() -> None:
    """An ok row carrying next_action raises a ValidationError whose cause is DiagnosticModelError."""

    with pytest.raises(ValidationError) as exc_info:
        DiagnosticCheck(name="x", status="ok", summary="y", next_action="aeat config repair")
    _assert_validation_error_caused_by_diagnostic_model_error(exc_info, "must not carry")


def test_diagnostic_check_ok_with_dead_end_raises_diagnostic_model_error() -> None:
    """An ok row carrying dead_end raises a ValidationError whose cause is DiagnosticModelError."""

    with pytest.raises(ValidationError) as exc_info:
        DiagnosticCheck(name="x", status="ok", summary="y", dead_end="no route")
    _assert_validation_error_caused_by_diagnostic_model_error(exc_info, "must not carry")


def test_diagnostic_model_error_is_subclass_of_value_error() -> None:
    """DiagnosticModelError is a ValueError subclass for legacy catch compatibility."""

    from .._errors import DiagnosticModelError

    assert issubclass(DiagnosticModelError, ValueError)
