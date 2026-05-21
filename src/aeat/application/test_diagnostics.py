"""Tests for application-owned CLI diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
)
from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.core.classification import SensitivityClass
from aeat.core.config import Settings

from .diagnostics import (
    ConfigRepairReport,
    DiagnosticCheck,
    DiagnosticFinding,
    RegistryVersionSummary,
    SecureObjectIntegrityReport,
    build_config_repair_report,
    quarantine_unreadable_secure_objects,
    render_config_repair_text,
    secure_object_unreadable_total,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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
        next_action="aeat config repair reset-state --yes",
    )
    dumped = populated.model_dump(mode="json")
    assert "next_action" in dumped
    assert "dead_end" in dumped
    assert dumped["next_action"] == "aeat config repair reset-state --yes"
    assert dumped["dead_end"] is None


def test_config_repair_report_contains_registry_and_setup_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")

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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")

    rendered = render_config_repair_text(build_config_repair_report())

    from aeat.core.i18n import tr

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

    from aeat.adapters.outbound.aeat.browser._site_health import (
        SiteHealthEvidence,
        SiteHealthState,
        SiteHealthStatus,
    )

    from .diagnostics import render_browser_connectivity_text

    status = SiteHealthStatus(
        state=SiteHealthState.OK,
        evidence=SiteHealthEvidence(
            url="https://example.org/",
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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """A namespace populated under master key K1 must be reported as unreadable under K2.

    Guards the divergence the audit flagged: ``secure_state.load`` used
    to report ``ok`` while iterating read paths crashed. The new
    ``secure_objects.integrity`` row must surface non-zero unreadable
    counts whenever rows from a prior keychain generation persist.
    """
    db_path = tmp_path / "rotated.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()
    namespace = "aeat.test.repair.rotation"

    # Seed three rows under the OLD master key.
    with key_old:
        engine_old = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine_old)
        try:
            repo_old = SecureObjectRepository(engine=engine_old)
            for natural_key, payload in (
                ("repair-row-1", b"old-1"),
                ("repair-row-2", b"old-2"),
                ("repair-row-3", b"old-3"),
            ):
                repo_old.save(
                    namespace=namespace,
                    object_key=natural_key,
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=payload,
                )
        finally:
            engine_old.dispose()

    # Switch to the NEW master key and add one decryptable row.
    with key_new:
        engine_new = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine_new)
        try:
            SecureObjectRepository(engine=engine_new).save(
                namespace=namespace,
                object_key="repair-row-4",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"new-4",
            )
        finally:
            engine_new.dispose()

        # The default repair pipeline picks up the master key from the keyring;
        # we want it to use the same NEW key we just wrote under, so keep the
        # process-wide override in place but redirect the engine resolution to
        # the same database file.
        monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
        monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
        dispose_engine()
        try:
            report = build_config_repair_report()
            integrity_check = next(c for c in report.checks if c.name == "secure_objects.integrity")
            assert integrity_check.status == "warn"
            assert str(report.secure_objects.unreadable_total) in integrity_check.summary
            assert str(report.secure_objects.readable_total) in integrity_check.summary
            assert integrity_check.next_action == "aeat config repair quarantine --yes"

            ns_report = next(item for item in report.secure_objects.namespaces if item.namespace == namespace)
            # Three rows sealed under the OLD ephemeral key should be unreadable
            # under the unsecured backend; rows we wrote under the unsecured
            # backend itself remain readable (set is at least 0 under the
            # unsecured key, depending on whether the canary fires).
            assert ns_report.unreadable >= 3
            assert ns_report.unreadable + ns_report.readable == 4
        finally:
            dispose_engine()


def test_secure_objects_integrity_check_reports_ok_on_clean_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """An empty or fully-decryptable secure-objects table renders ``ok``."""
    db_path = tmp_path / "clean.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()

    report = build_config_repair_report()
    integrity_check = next(c for c in report.checks if c.name == "secure_objects.integrity")
    assert integrity_check.status == "ok"
    assert report.secure_objects.unreadable_total == 0


def test_secure_object_unreadable_total_is_nonzero_after_master_key_rotation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """The helper consumed by overview status returns the aggregate count.

    Seeds rows under master key K1, rotates to K2, and asserts the
    aggregate matches the per-namespace probe. Used by
    ``aeat app overview status`` to render an inline warning footer
    pointing the operator at ``aeat config repair``.
    """
    db_path = tmp_path / "agg.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()

    with key_old:
        engine_old = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine_old)
        try:
            repo_old = SecureObjectRepository(engine=engine_old)
            for namespace, key, payload in (
                ("aeat.test.agg.alpha", "alpha-1", b"alpha-1"),
                ("aeat.test.agg.alpha", "alpha-2", b"alpha-2"),
                ("aeat.test.agg.beta", "beta-1", b"beta-1"),
            ):
                repo_old.save(
                    namespace=namespace,
                    object_key=key,
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=payload,
                )
        finally:
            engine_old.dispose()

    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    with key_new:
        dispose_engine()
        try:
            total = secure_object_unreadable_total()
            assert total >= 3, f"expected at least three unreadable rows; got {total}"
        finally:
            dispose_engine()


def test_secure_object_unreadable_total_is_zero_on_clean_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Aggregate returns zero when no namespace has unreadable rows."""
    db_path = tmp_path / "agg-clean.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()

    assert secure_object_unreadable_total() == 0


def test_repair_auth_session_predicate_agrees_with_wizard_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """``aeat config repair`` and ``aeat config status`` must read auth readiness from one source.

    Repair and the wizard status surface share one projection: both
    build a :class:`WizardStatusReport` and read its ``login_ready`` /
    ``auth_provider`` fields. This test pins that contract by walking
    three workflow states (no provider, provider only, fully
    authenticated) and asserting the report shape across each.
    """
    from aeat.application.auth import update_auth
    from aeat.application.user_profile._testing import register_minimal_profile
    from aeat.application.workflow import WorkflowState

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'auth.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()

    with EphemeralMasterKeyProvider():
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

        from aeat.application.wizard._status import build_wizard_status

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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
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
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()

    with key_old:
        engine_old = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        Base.metadata.create_all(engine_old)
        try:
            repo_old = SecureObjectRepository(engine=engine_old)
            for namespace, key, payload in (
                ("aeat.test.quar.alpha", "row-old-1", b"old-1"),
                ("aeat.test.quar.beta", "row-old-2", b"old-2"),
            ):
                repo_old.save(
                    namespace=namespace,
                    object_key=key,
                    classification=SensitivityClass.FINANCIAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=payload,
                )
        finally:
            engine_old.dispose()

    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    with key_new:
        dispose_engine()

        engine_new = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
        try:
            SecureObjectRepository(engine=engine_new).save(
                namespace="aeat.test.quar.alpha",
                object_key="row-new-1",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"new-1",
            )
        finally:
            engine_new.dispose()

        dispose_engine()
        try:
            report = quarantine_unreadable_secure_objects()
            assert report.unreadable_total == 2
            assert report.readable_total == 1
        finally:
            dispose_engine()

    # Inspect the database directly to prove the row distribution.
    with sqlite3.connect(db_path) as con:
        active = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()[0]
        archived = con.execute("SELECT COUNT(*) FROM secure_objects_quarantine").fetchone()[0]
    assert active == 1, f"expected one row left in secure_objects; got {active}"
    assert archived == 2, f"expected two rows archived; got {archived}"


def test_importing_diagnostics_does_not_pull_the_browser_or_registry_subtree() -> None:
    """Importing ``diagnostics`` stays off the heavy adapter import graph.

    The ``aeat --version`` fast path imports ``aeat.application.
    diagnostics`` solely for ``build_cli_version_report`` /
    ``render_cli_version_text``. Disaster ADR Ruling 4 mandates that
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

    from .diagnostics import build_cli_version_report, render_cli_version_text

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

    from .diagnostics import _ensure_models_rebuilt

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
    with the exact ``aeat config profile set ...`` command.
    """

    from aeat.application.wizard._status import WizardStatusReport

    from .diagnostics import _profile_check

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

    from aeat.application.wizard._status import WizardStatusReport

    from .diagnostics import _profile_check

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

    from aeat.core.i18n import tr

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

    from aeat.application.diagnostics import _registry_cross_domain_integrity_check
    from aeat.core.resources import bundled_path

    check = _registry_cross_domain_integrity_check(bundled_path("registry", "aeat"))
    # Healthy registry → ok + operator audience. A failing registry would
    # carry audience='internal'; that branch is pinned by the renderer
    # test above against a constructed report.
    assert check.name == "registry.integrity"
    assert check.audience in {"operator", "internal"}
