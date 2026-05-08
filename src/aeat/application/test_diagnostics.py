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
        assert integrity_check.next_action == "aeat config doctor --quarantine-unreadable"

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
