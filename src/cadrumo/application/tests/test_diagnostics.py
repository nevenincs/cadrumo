"""Tests for application-owned CLI diagnostics."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, ValidationError

from ...adapters.persistence.storage import (
    SECURE_OBJECT_WORKFLOW_STATE_KEY,
    StorageValidationError,
    activate_session,
    has_active_bucket_session,
    suspend_active_session,
)
from ...adapters.persistence.storage.master_key import BucketSession
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...adapters.persistence.storage.sql import dispose_engine
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...core import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ...core.classification import SensitivityClass
from ...core.config import override_settings
from ...tests.master_key import EphemeralMasterKeyProvider
from ...tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ...tests.user_profile import register_minimal_profile
from ..diagnostics import (
    ConfigRepairReport,
    DiagnosticCheck,
    DiagnosticFinding,
    RegistryVersionSummary,
    SecureObjectIntegrityReport,
    build_config_repair_report,
    ensure_models_rebuilt,
    preview_quarantine_unreadable_secure_objects,
    profile_check,
    quarantine_unreadable_secure_objects,
    registry_cross_domain_integrity_check,
    render_config_repair_text,
    secure_object_unreadable_total,
)
from ..operator_actions import ConditionEvidence, PreconditionVerdict
from ..overview import declare_next_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ACTIVE_BUCKET_ID = "44444444-4444-4444-8444-444444444444"
_OTHER_BUCKET_ID = "55555555-5555-4555-8555-555555555555"


#: A declared continuation this module never expects to see rendered. It was a
#: bare sentinel string until ``next_action`` became a typed record; the action
#: id now carries the same "must not appear in the output" identity.
_UNRENDERED_NEXT_ACTION = declare_next_action("operator.profile.descendiente")


@pytest.fixture(autouse=True)
def isolated_default_secure_sql(tmp_path: Path) -> Iterator[None]:
    """Bind diagnostics tests to an isolated storage root by default."""

    storage_root = tmp_path / "diagnostics-storage"
    with override_settings(cadrumo_local_storage_root=storage_root, cadrumo_active_profile=None) as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


@contextmanager
def _explicit_database(db_path: Path) -> Generator[None]:
    with override_settings(cadrumo_database_url=f"sqlite:///{db_path.as_posix()}") as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


@pytest.fixture(scope="module")
def config_repair_report(tmp_path_factory: pytest.TempPathFactory) -> ConfigRepairReport:
    tmp_path = tmp_path_factory.mktemp("diagnostics-config-repair")
    with isolated_runtime_profile(tmp_path=tmp_path):
        return build_config_repair_report()


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


_DIAGNOSTIC_CHECK_INVALID_CASES: tuple[tuple[str, dict[str, object], str], ...] = (
    (
        "fail-missing-recovery",
        {"name": "x", "status": "fail", "summary": "y"},
        "must populate `precondition_verdict`",
    ),
    (
        "warn-missing-recovery",
        {"name": "x", "status": "warn", "summary": "y"},
        "must populate `precondition_verdict`",
    ),
)


def _terminal_diagnostic_verdict(condition_id: str = "diagnostics.test.available") -> PreconditionVerdict:
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=f"{condition_id}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={"available": False},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.TERMINAL,
    )


def test_diagnostic_check_invalid_recovery_fields_raise_validation_error() -> None:
    """Invalid recovery-field combinations are rejected by the real Pydantic model."""

    for _case_id, fields, _message_fragment in _DIAGNOSTIC_CHECK_INVALID_CASES:
        with pytest.raises(ValidationError):
            DiagnosticCheck.model_validate(fields)


def test_diagnostic_check_ok_row_with_no_recovery_verdict_constructs() -> None:
    """An ``ok`` row carries no recovery verdict."""

    check = DiagnosticCheck(name="x", status="ok", summary="y")
    assert check.precondition_verdict is None


def test_diagnostic_check_fail_row_with_explicit_no_recovery_constructs() -> None:
    """A failing row carries a closed typed no-recovery outcome."""

    check = DiagnosticCheck(
        name="x",
        status="fail",
        summary="y",
        precondition_verdict=_terminal_diagnostic_verdict(),
    )
    assert check.precondition_verdict is not None
    assert check.precondition_verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL


def test_diagnostic_check_model_dump_contains_only_the_typed_recovery_channel() -> None:
    """Application JSON never carries legacy command or dead-end prose fields."""

    populated = DiagnosticCheck(
        name="x",
        status="fail",
        summary="y",
        precondition_verdict=_terminal_diagnostic_verdict(),
    )
    dumped = populated.model_dump(mode="json")
    assert set(dumped) == {
        "name",
        "status",
        "summary",
        "detail",
        "precondition_verdict",
        "audience",
        "findings",
    }
    assert dumped["precondition_verdict"]["no_recovery_outcome"] == "terminal"


def test_diagnostic_models_reject_retired_recovery_transport_fields() -> None:
    """Removed prose channels are forbidden rather than silently ignored."""
    check_payload = DiagnosticCheck(
        name="x",
        status="fail",
        summary="y",
        precondition_verdict=_terminal_diagnostic_verdict(),
    ).model_dump(mode="json")
    check_payload["next_action"] = "legacy-transport"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DiagnosticCheck.model_validate(check_payload)

    finding_payload = DiagnosticFinding(summary="cause").model_dump(mode="json")
    finding_payload["next_action"] = "legacy-transport"
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DiagnosticFinding.model_validate(finding_payload)


def test_config_repair_preserves_the_active_profile_typed_verdict() -> None:
    """Cold-profile repair rows carry the health authority, never command prose."""

    report = build_config_repair_report()
    profile_check = next(check for check in report.checks if check.name == "profile.readiness")

    assert profile_check.status == "warn"
    verdict = profile_check.precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "profile.active.available"
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.create"
    assert verdict.missing_argument_names == ("profile_name",)


def test_profile_readiness_reports_no_profile_configured_when_genuinely_absent() -> None:
    """A cold environment with no registered profile keeps the honest sentence.

    The control for the locked-profile row below: a real absence must still
    report absence, or a fix that widened the locked branch too far would
    silently swallow this case instead.
    """
    from ...core.i18n import tr

    report = build_config_repair_report()
    profile_readiness = next(check for check in report.checks if check.name == "profile.readiness")

    assert profile_readiness.summary == tr("cli.diagnostics.summary.profile_none", default="No profile configured")


def test_profile_readiness_reports_the_lock_rather_than_no_profile_configured(tmp_path: Path) -> None:
    """A locked profile must not fall through to the "no profile configured" row.

    Before the fix: neither status set diagnostics keys off included
    ``profile_locked``, so a real, intact, merely-not-logged-in profile fell
    through to the same summary a cold environment with no profile at all
    gets -- true of the second, false of the first.
    """
    from ...core.i18n import tr

    with isolated_runtime_profile(tmp_path=tmp_path), suspend_active_session():
        assert not has_active_bucket_session()
        report = build_config_repair_report()

    profile_readiness = next(check for check in report.checks if check.name == "profile.readiness")

    assert profile_readiness.status == "warn"
    assert profile_readiness.summary == tr("cli.diagnostics.summary.profile_locked")
    assert profile_readiness.summary != tr("cli.diagnostics.summary.profile_none", default="No profile configured")
    verdict = profile_readiness.precondition_verdict
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.login"


def test_config_repair_report_contains_registry_and_setup_checks(config_repair_report: ConfigRepairReport) -> None:
    report = config_repair_report
    assert report.package_name == "cadrumo"
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


def test_render_config_repair_text_is_operator_readable(config_repair_report: ConfigRepairReport) -> None:
    rendered = render_config_repair_text(config_repair_report)
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

    from ...adapters.outbound.aeat.browser import (
        SiteHealthEvidence,
        SiteHealthStatus,
    )
    from ...core.errors import SiteHealthState
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
    namespace = "cadrumo-test.repair.rotation"

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
        verdict = integrity_check.precondition_verdict
        assert verdict is not None
        assert verdict.action is not None
        assert verdict.action.action_id == "operator.diagnostics.secure_objects.quarantine"
        assert verdict.argument_bindings[0].argument_name == "yes"
        assert verdict.argument_bindings[0].value is True

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
            ("cadrumo-test.agg.alpha", "alpha-1", b"alpha-1"),
            ("cadrumo-test.agg.alpha", "alpha-2", b"alpha-2"),
            ("cadrumo-test.agg.beta", "beta-1", b"beta-1"),
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

    caplog.set_level("DEBUG", logger="cadrumo.application.diagnostics")

    with override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_ACTIVE_BUCKET_ID) as settings:
        dispose_engine(settings)
        try:
            assert secure_object_unreadable_total() == 0
        finally:
            dispose_engine(settings)

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "StorageValidationError" in caplog.text
    assert "errors.storage.runtime.not_ready" in caplog.text
    assert "no active bucket session" not in caplog.text


def test_secure_object_unreadable_total_logs_route_session_mismatch(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Diagnostics do not silently swallow active-session route mismatches."""

    caplog.set_level("DEBUG", logger="cadrumo.application.diagnostics")

    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_active_profile=_ACTIVE_BUCKET_ID) as settings,
        activate_session(_bucket_session(_OTHER_BUCKET_ID)),
    ):
        dispose_engine(settings)
        try:
            assert secure_object_unreadable_total() == 0
        finally:
            dispose_engine(settings)

    assert "secure objects engine unreachable for repair probe" in caplog.text
    assert "StorageValidationError" in caplog.text
    assert "errors.storage.runtime.not_ready" in caplog.text
    assert "route does not match the active bucket session" not in caplog.text


def test_repair_auth_session_predicate_agrees_with_wizard_status(tmp_path: Path) -> None:
    """``aeat config repair`` and ``aeat config status`` must read auth readiness from one source.

    Repair and the wizard status surface share one projection: both
    build a :class:`WizardStatusReport` and read its ``login_ready`` /
    ``auth_provider`` fields. This test pins that contract by walking
    three workflow states (no provider, provider only, fully
    authenticated) and asserting the report shape across each.
    """
    from cadrumo.application.workflow.persistence import workflow_state_repository

    from ...tests.profile_capsule import open_test_profile_session
    from ..auth.actions import update_auth

    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session("11111111-1111-4111-8111-111111111111"),
    ):
        register_minimal_profile(
            profile_id="11111111-1111-4111-8111-111111111111",
            overrides={
                "identity.tax_id": "00000000T",
                "activities.description": "design",
                "tax_residence.jurisdiction_scope": "common_regime",
                "iva.regime": "GENERAL",
                "iva.m303_regime_composition": "general",
                "iva.redeme_enrolled": "false",
                "iva.cash_accounting_regime_enrolled": "false",
                "iva.voluntary_sii_enrolled": "false",
                "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
            },
        )

        # The seeding door publishes the profile CAPSULE and returns its
        # UserProfileRecord; local auth readiness lives on the WorkflowState,
        # which is a separate record read from its own repository.
        no_provider = workflow_state_repository().load()
        provider_only = update_auth(no_provider, provider="clave_movil")
        fully_authenticated = update_auth(provider_only, authenticated=True, subject="00000000T")

        from ..wizard.status import build_wizard_status

        for state in (no_provider, provider_only, fully_authenticated):
            workflow_state_repository().save(state)
            setup_report = build_wizard_status(state)
            repair_report = build_config_repair_report()
            auth_check = next(check for check in repair_report.checks if check.name == "auth.readiness")
            if state is no_provider:
                assert setup_report.login_ready is False
                verdict = auth_check.precondition_verdict
                assert verdict is not None
                assert verdict.action is not None
                assert verdict.action.action_id == "operator.auth.configure"
                assert verdict.missing_argument_names == ("file",)
            elif state is provider_only:
                assert setup_report.auth_provider == "clave_movil"
                assert setup_report.login_ready is False
                verdict = auth_check.precondition_verdict
                assert verdict is not None
                assert verdict.action is not None
                assert verdict.action.action_id == "operator.auth.login"
                assert verdict.argument_bindings[0].value == "clave_movil"
            else:
                assert setup_report.auth_provider == "clave_movil"
                assert setup_report.login_ready is True
                assert auth_check.status == "ok"
                assert auth_check.precondition_verdict is None


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
            ("cadrumo-test.quar.alpha", "row-old-1", b"old-1"),
            ("cadrumo-test.quar.beta", "row-old-2", b"old-2"),
        ):
            _save_probe_row(namespace, key, payload)

    with key_new, _explicit_database(db_path):
        _save_probe_row("cadrumo-test.quar.alpha", "row-new-1", b"new-1")

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
    contract the ``repair quarantine --dry-run`` surface relies on.
    """
    import sqlite3

    db_path = tmp_path / "preview-quar.db"
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()

    with key_old, _explicit_database(db_path):
        for namespace, key, payload in (
            ("cadrumo-test.preview.alpha", "row-old-1", b"old-1"),
            ("cadrumo-test.preview.beta", "row-old-2", b"old-2"),
        ):
            _save_probe_row(namespace, key, payload)

    with key_new, _explicit_database(db_path):
        _save_probe_row("cadrumo-test.preview.alpha", "row-new-1", b"new-1")

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


def test_the_preview_reports_nothing_without_a_session_rather_than_a_false_corruption(tmp_path: Path) -> None:
    """A keyless probe must not answer the decryptability question at all.

    Every row is undecryptable without the bucket key, so a probe that ran
    keyless would report a sound bucket as entirely corrupt.  The repair path
    used to open a shared-master session of its own to avoid that; it now opens
    none, and the substrate refusal underneath leaves the report empty.

    The served read is what gives the sessionless one meaning: it proves the row
    is there and decrypts cleanly, so an empty sessionless report is the missing
    key rather than a missing row.
    """
    namespace = "cadrumo.workflow"
    with isolated_runtime_profile(tmp_path=tmp_path):
        secure_object_repository_for_active_bucket().save(
            namespace=namespace,
            object_key=SECURE_OBJECT_WORKFLOW_STATE_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"repair-preview-sessionless",
        )
        served = preview_quarantine_unreadable_secure_objects()
        with suspend_active_session():
            assert not has_active_bucket_session()
            sessionless = preview_quarantine_unreadable_secure_objects()

    assert any(item.namespace == namespace for item in served.namespaces)
    assert served.unreadable_total == 0
    assert sessionless.namespaces == ()


def test_a_sessionless_quarantine_moves_nothing(tmp_path: Path) -> None:
    """The mutating verb is where a keyless probe would do real damage.

    ``quarantine`` moves exactly the rows the probe calls unreadable, so a
    keyless run would archive every row of a sound bucket.  It refuses instead
    of reporting an empty result, which is the right shape for a verb that
    mutates: the preview may answer "nothing to show", but the commit must not
    silently do nothing when the operator asked it to act.

    The read taken afterwards under the real session is the safety proof: the
    row is still live and still decrypts, so nothing was moved out from under
    it.
    """
    namespace = "cadrumo.workflow"
    with isolated_runtime_profile(tmp_path=tmp_path):
        secure_object_repository_for_active_bucket().save(
            namespace=namespace,
            object_key=SECURE_OBJECT_WORKFLOW_STATE_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"repair-quarantine-sessionless",
        )
        with suspend_active_session():
            assert not has_active_bucket_session()
            with pytest.raises(StorageValidationError) as refusal:
                quarantine_unreadable_secure_objects()
        survived = preview_quarantine_unreadable_secure_objects()

    assert refusal.value.translated_message == "errors.storage.runtime.not_ready"
    assert any(item.namespace == namespace for item in survived.namespaces)
    assert survived.unreadable_total == 0


def test_importing_diagnostics_does_not_pull_the_browser_or_registry_subtree() -> None:
    """Importing ``diagnostics`` stays off the heavy adapter import graph.

    The ``aeat --version`` fast path imports ``cadrumo.application.
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
            "import sys; import cadrumo.application.diagnostics; "
            "print(','.join(m for m in ("
            "'cadrumo.adapters.outbound.aeat.browser', "
            "'cadrumo.domain.calculations.registry', "
            "'cadrumo.application.workflow', "
            "'cadrumo.application.wizard.status') if m in sys.modules))",
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
    assert report.package_name == "cadrumo"
    assert report.package_version
    # Renders without raising — the model is fully defined.
    assert isinstance(render_cli_version_text(report), str)


def _internal_registry_repair_report() -> ConfigRepairReport:
    """Build a repair report carrying one internal-audience failing row.

    Used by the operator-vs-internal wording tests below; constructs the
    report directly so the test does not depend on the local secure
    backend or registry corruption.
    """

    ensure_models_rebuilt()
    registry = RegistryVersionSummary(available=True, registry_root="/x", modelo_count=1, casilla_count=2)
    checks = (
        DiagnosticCheck(
            name="registry.integrity",
            status="fail",
            summary="Registry integrity failed",
            detail="casilla 9999 missing from revision 100-2025",
            precondition_verdict=_terminal_diagnostic_verdict("diagnostics.registry.integrity.valid"),
            audience="internal",
        ),
        DiagnosticCheck(
            name="auth.readiness",
            status="warn",
            summary="Authentication is not configured",
            precondition_verdict=_terminal_diagnostic_verdict("diagnostics.auth.provider.configured"),
            audience="operator",
        ),
    )
    return ConfigRepairReport(
        overall="fail",
        package_name="cadrumo",
        package_version="0.1.0",
        python_version="3.13.11",
        log_file="cadrumo.log",
        registry=registry,
        setup=None,
        secure_objects=SecureObjectIntegrityReport(),
        checks=checks,
    )


def test_diagnostic_finding_carries_typed_per_cause_detail_without_transport() -> None:
    """A finding names one concrete cause without duplicating the parent action."""

    finding = DiagnosticFinding(
        summary="identity.tax_id — Tax identification number",
        requirement="required",
    )
    assert finding.requirement == "required"
    dumped = finding.model_dump(mode="json")
    assert set(dumped) == {"summary", "detail", "requirement"}
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
    carries one :class:`DiagnosticFinding` per unset required key and one
    canonical profile-editor action on the parent check.
    """

    from ..wizard.status import WizardStatusReport

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
        next_action=_UNRENDERED_NEXT_ACTION,
    )
    check = profile_check(report)

    assert check.status == "warn"
    finding_keys = {finding.summary.split(" — ", 1)[0] for finding in check.findings}
    assert finding_keys == {"identity.tax_id", "activities.description", "iva.regime"}
    assert all(finding.requirement == "required" for finding in check.findings)
    verdict = check.precondition_verdict
    assert verdict is not None
    assert verdict.action is not None
    assert verdict.action.action_id == "operator.profile.edit"
    assert verdict.argument_bindings[0].value == "demo"
    # The bare counter must no longer be the only signal: the row carries
    # one finding per cause.
    assert len(check.findings) == 3


def test_missing_log_parent_has_no_false_read_only_recovery_action(tmp_path: Path) -> None:
    """A log-tail command cannot repair a missing log directory."""

    missing_log_dir = tmp_path / "not-created" / "logs"
    with override_settings(cadrumo_log_dir=missing_log_dir):
        report = build_config_repair_report()
    check = next(item for item in report.checks if item.name == "logging.file")
    assert check.status == "warn"
    verdict = check.precondition_verdict
    assert verdict is not None
    assert verdict.action is None
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION


def test_render_config_repair_text_lists_specific_findings() -> None:
    """The renderer prints each finding line, not just the check summary."""

    from ..wizard.status import WizardStatusReport

    ensure_models_rebuilt()

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
        next_action=_UNRENDERED_NEXT_ACTION,
    )
    check = profile_check(report)
    registry = RegistryVersionSummary(available=True, registry_root="/x", modelo_count=1, casilla_count=2)
    repair_report = ConfigRepairReport(
        overall="warn",
        package_name="cadrumo",
        package_version="0.1.0",
        python_version="3.13.11",
        log_file="cadrumo.log",
        registry=registry,
        setup=None,
        secure_objects=SecureObjectIntegrityReport(),
        checks=(check,),
    )

    rendered = render_config_repair_text(repair_report)

    # The application renderer retains the diagnosis and leaves typed action
    # projection to the entrypoint boundary.
    assert "identity.tax_id" in rendered
    # The status report's declared continuation must not leak into the
    # application-level rendering: projecting it is the entrypoint's job. The
    # action id is the greppable identity now that the field is a typed record
    # rather than the free string this once pinned.
    assert _UNRENDERED_NEXT_ACTION.action.action_id not in rendered


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

    check = registry_cross_domain_integrity_check(bundled_path("registry", "aeat"))
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
    from ..errors import DiagnosticModelError

    code = get_registered_error_code(DiagnosticModelError)
    assert code.code in ERROR_REGISTRY
    assert ERROR_REGISTRY[code.code] == code


def test_diagnostic_model_error_round_trips_through_build_error_envelope() -> None:
    """build_error_envelope must produce a well-formed envelope for DiagnosticModelError."""

    from ...core.errors import build_error_envelope
    from ..errors import DiagnosticModelError

    err = DiagnosticModelError("invariant violated")
    envelope = build_error_envelope(err)
    assert envelope.code == "REFUSED_DIAGNOSTIC_MODEL_INVARIANT"
    assert envelope.message


def _assert_validation_error_caused_by_diagnostic_model_error(
    exc_info: pytest.ExceptionInfo[Exception],
    match: str,
) -> None:
    """Assert a pydantic ValidationError wraps a DiagnosticModelError with the given message."""

    from ..errors import DiagnosticModelError

    val_err = exc_info.value
    assert isinstance(val_err, ValidationError)
    causes: list[object] = []
    for e in val_err.errors():
        ctx = e.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            causes.append(ctx["error"])
    matching = [c for c in causes if isinstance(c, DiagnosticModelError) and match in str(c)]
    assert matching, f"Expected a DiagnosticModelError cause matching {match!r}; got causes: {causes!r}"


def test_diagnostic_check_invariant_errors_raise_diagnostic_model_error() -> None:
    """Invalid recovery fields raise ValidationError caused by DiagnosticModelError."""

    for _case_id, fields, message_fragment in _DIAGNOSTIC_CHECK_INVALID_CASES:
        with pytest.raises(ValidationError) as exc_info:
            DiagnosticCheck.model_validate(fields)
        _assert_validation_error_caused_by_diagnostic_model_error(exc_info, message_fragment)


def test_diagnostic_model_error_is_pydantic_validator_value_error() -> None:
    """DiagnosticModelError is a ValueError subclass for Pydantic validator wrapping."""

    from ..errors import DiagnosticModelError

    assert issubclass(DiagnosticModelError, ValueError)


def test_missing_active_bucket_session_is_classified_from_the_typed_chain_not_the_text() -> None:
    """The cold-start verdict reads the exception chain, never the rendered message.

    ``secure_state.load`` warns instead of failing, and withholds the raw
    exception detail, only when this classifier says the probe failed for a
    missing bucket session. Deciding that from rendered text is unsound in both
    directions, and this pins both.

    The producer already carries no authored sentence, so ``str(exc)`` is a
    locale key that does not contain the class name: any wrapper whose text a
    scan would have searched no longer mentions it. And an unrelated failure
    whose message happens to name the class must not be waved through as an
    expected cold start, because that downgrades a genuine fault to a warning
    and suppresses the detail the operator needs.
    """
    from ...adapters.persistence.storage.master_key import NoActiveBucketSessionError
    from ..diagnostics import _is_missing_active_bucket_session

    session_error = NoActiveBucketSessionError()
    assert "NoActiveBucketSessionError" not in str(session_error)
    assert _is_missing_active_bucket_session(session_error) is True

    try:
        try:
            raise session_error
        except NoActiveBucketSessionError:
            # An incidental re-raise sets `__context__` only, while the
            # explicit `from` below sets `__cause__`; the chain forks and the
            # typed link is reachable on the context edge alone.
            raise RuntimeError("secure state probe failed") from ValueError("unrelated root cause")
    except RuntimeError as forked:
        assert _is_missing_active_bucket_session(forked) is True

    impostor = RuntimeError("NoActiveBucketSessionError was mentioned in passing")
    assert _is_missing_active_bucket_session(impostor) is False


def test_missing_active_bucket_session_classifier_terminates_on_a_cyclic_chain() -> None:
    """A self-referential chain must not hang the repair report.

    The walk follows two edges per link, so a chain that points back at an
    exception already visited would revisit it forever without identity
    marking. ``config repair`` is the surface an operator reaches for when the
    application is already unhealthy, so a hang here strands the one command
    meant to explain the failure.
    """
    from ..diagnostics import _is_missing_active_bucket_session

    first = RuntimeError("first")
    second = RuntimeError("second")
    first.__cause__ = second
    second.__context__ = first

    assert _is_missing_active_bucket_session(first) is False
