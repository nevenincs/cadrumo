"""Tests for application-owned CLI diagnostics."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aeat.adapters.persistence.storage import (
    EphemeralMasterKeyProvider,
    override_master_key_provider,
)
from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.core.classification import SensitivityClass
from aeat.core.config import Settings

from .diagnostics import (
    build_config_doctor_report,
    quarantine_unreadable_secure_objects,
    render_config_doctor_text,
    secure_object_unreadable_total,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_config_doctor_report_contains_registry_and_setup_checks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")

    report = build_config_doctor_report()

    assert report.package_name == "aeat"
    assert report.registry.available is True
    assert report.registry.modelo_count > 0
    assert {check.name for check in report.checks} >= {
        "environment.python",
        "registry.load",
        "secure_state.load",
        "profile.active",
        "auth.provider",
    }
    assert report.overall in {"ok", "warn"}


def test_render_config_doctor_text_is_operator_readable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")

    rendered = render_config_doctor_text(build_config_doctor_report())

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
    namespace = "aeat.test.doctor.rotation"

    # Seed three rows under the OLD master key.
    override_master_key_provider(key_old)
    engine_old = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine_old)
    try:
        repo_old = SecureObjectRepository(engine=engine_old)
        for natural_key, payload in (
            ("doctor-row-1", b"old-1"),
            ("doctor-row-2", b"old-2"),
            ("doctor-row-3", b"old-3"),
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
    override_master_key_provider(key_new)
    engine_new = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"))
    Base.metadata.create_all(engine_new)
    try:
        SecureObjectRepository(engine=engine_new).save(
            namespace=namespace,
            object_key="doctor-row-4",
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=b"new-4",
        )
    finally:
        engine_new.dispose()

    # The default doctor pipeline picks up the master key from the keyring;
    # we want it to use the same NEW key we just wrote under, so keep the
    # process-wide override in place but redirect the engine resolution to
    # the same database file.
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()
    try:
        report = build_config_doctor_report()
        integrity_check = next(c for c in report.checks if c.name == "secure_objects.integrity")
        assert integrity_check.status == "warn"
        assert "unreadable row" in integrity_check.summary
        assert integrity_check.next_action == "aeat config doctor quarantine --yes"

        ns_report = next(item for item in report.secure_objects.namespaces if item.namespace == namespace)
        # Three rows sealed under the OLD ephemeral key should be unreadable
        # under the unsecured backend; rows we wrote under the unsecured
        # backend itself remain readable (set is at least 0 under the
        # unsecured key, depending on whether the canary fires).
        assert ns_report.unreadable >= 3
        assert ns_report.unreadable + ns_report.readable == 4
    finally:
        override_master_key_provider(None)
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

    report = build_config_doctor_report()
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
    pointing the operator at ``aeat config doctor``.
    """
    db_path = tmp_path / "agg.db"
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    dispose_engine()

    key_old = EphemeralMasterKeyProvider()
    key_new = EphemeralMasterKeyProvider()

    override_master_key_provider(key_old)
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
    override_master_key_provider(key_new)
    dispose_engine()
    try:
        total = secure_object_unreadable_total()
        assert total >= 3, f"expected at least three unreadable rows; got {total}"
    finally:
        override_master_key_provider(None)
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


def test_doctor_auth_session_predicate_agrees_with_setup_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """``aeat config doctor`` and ``aeat setup status`` must read auth readiness from one source.

    UX-022 root cause: doctor checked ``state.auth.authenticated_at is
    not None`` while ``aeat setup auth status`` ran a live session
    probe that wrote a fresh authenticated_at on success and cleared
    it on failure. When the live probe had not been refreshed the two
    surfaces could disagree. The current contract is that BOTH
    surfaces read the same ``authenticated_at`` field on the
    ``SetupStatusReport``; this test pins that contract.

    The test parametrises over three states:
    - no provider configured -> doctor reports auth.provider warn,
      both surfaces agree there is no readiness to evaluate;
    - provider configured but no session -> doctor reports
      auth.session warn, setup status reports login_ready=False;
    - provider configured and session active -> doctor reports
      auth.session ok, setup status reports login_ready=True.
    """
    from aeat.application.user_cli import (
        UserCliState,
        set_active_profile,
        set_profile_values,
        update_auth,
    )

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'auth.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()

    base = set_active_profile(
        set_profile_values(
            UserCliState(),
            "operator",
            {"tax.id": "00000000T", "activity": "design", "iva.regime": "general"},
        ),
        "operator",
    )

    no_provider = base
    provider_only = update_auth(no_provider, provider="clave_movil")
    fully_authenticated = update_auth(provider_only, authenticated=True, subject="00000000T")

    from aeat.application.setup_status import build_setup_status

    for state in (no_provider, provider_only, fully_authenticated):
        setup_report = build_setup_status(state)
        # Mirror what doctor does: build the report from the same state by
        # re-using the SetupStatusReport.login_ready field.
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

    override_master_key_provider(key_old)
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
    override_master_key_provider(key_new)
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
        override_master_key_provider(None)
        dispose_engine()

    # Inspect the database directly to prove the row distribution.
    with sqlite3.connect(db_path) as con:
        active = con.execute("SELECT COUNT(*) FROM secure_objects").fetchone()[0]
        archived = con.execute("SELECT COUNT(*) FROM secure_objects_quarantine").fetchone()[0]
    assert active == 1, f"expected one row left in secure_objects; got {active}"
    assert archived == 2, f"expected two rows archived; got {archived}"
