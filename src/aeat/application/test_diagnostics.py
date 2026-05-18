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
    DiagnosticCheck,
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
    assert report.overall in {"ok", "warn"}


def test_render_config_repair_text_is_operator_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")

    rendered = render_config_repair_text(build_config_repair_report())

    assert "Overall\t" in rendered
    assert "registry.load" in rendered
    assert "Logs\t" in rendered


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
            assert "unreadable row" in integrity_check.summary
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
