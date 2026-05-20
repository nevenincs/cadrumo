"""Tests for the repair integrity + list subverb backends.

Every test drives the *real* :class:`SecureObjectRepository` against a
real SQLite engine and a real :class:`EphemeralMasterKeyProvider`. The
"undecryptable row" path is produced the only way it occurs in
production -- rows written under one master key, probed under a
different one -- so the crypto-probe in ``probe_namespace_integrity``
is genuinely exercised. No stub repository: if that probe or the
report aggregation regressed, these tests fail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.application.repair_integrity import (
    build_repair_integrity_report,
    build_repair_list_report,
)
from aeat.core.classification import SensitivityClass
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Two fixed, distinct 32-byte master keys. Rows written under one and
# probed under the other are genuinely undecryptable -- the exact
# production condition `aeat config repair` exists to surface.
_KEY_A = b"\xa1" * 32
_KEY_B = b"\xb2" * 32


def _engine_on(tmp_path: Path):
    """Build a real SQLite engine with the secure-object schema."""
    db_path = tmp_path / "repair-integrity.db"
    engine = create_engine_from_settings(
        Settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}"),
    )
    Base.metadata.create_all(engine)
    return engine


def _save_rows(engine, namespace: str, count: int, *, tag: str) -> None:
    """Persist ``count`` real encrypted secure objects under ``namespace``.

    ``tag`` namespaces the natural object keys so rows written across
    separate master-key sessions never collide on the HMAC digest
    (which would upsert-overwrite instead of accumulating).
    """
    repo = SecureObjectRepository(engine=engine)
    for index in range(count):
        repo.save(
            namespace=namespace,
            object_key=f"{namespace}:{tag}:{index}",
            classification=SensitivityClass.OPERATIONAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=f"repair-integrity-payload:{namespace}:{tag}:{index}".encode(),
        )


class TestBuildIntegrityReport:
    def test_clean_install_reports_ok(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 5, tag="a")
            _save_rows(engine, "aeat.profile.bucket", 3, tag="a")
            report = build_repair_integrity_report(
                repository=SecureObjectRepository(engine=engine),
            )
        assert report.readable_total == 8
        assert report.unreadable_total == 0
        assert report.check.status == "ok"
        assert report.check.next_action is None or report.check.next_action == ""
        assert report.check.dead_end is None or report.check.dead_end == ""

    def test_undecryptable_rows_surface_fail_with_next_action(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        # Two rows written under key A become undecryptable once the
        # active master key rotates to B.
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows(engine, "aeat.workflow", 5, tag="current")
            _save_rows(engine, "aeat.profile.bucket", 3, tag="current")
            report = build_repair_integrity_report(
                repository=SecureObjectRepository(engine=engine),
            )
        workflow = next(ns for ns in report.namespaces if ns.namespace == "aeat.workflow")
        assert workflow.readable == 5
        assert workflow.unreadable == 2
        assert report.unreadable_total == 2
        assert report.check.status == "fail"
        assert report.check.next_action == "aeat config repair quarantine --yes"

    def test_namespace_filter_restricts_scope(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows(engine, "aeat.workflow", 5, tag="current")
            _save_rows(engine, "aeat.profile.bucket", 3, tag="current")
            report = build_repair_integrity_report(
                repository=SecureObjectRepository(engine=engine),
                namespace="aeat.profile.bucket",
            )
        # Filtering to the clean namespace excludes the workflow
        # namespace's stale rows entirely.
        assert len(report.namespaces) == 1
        assert report.namespaces[0].namespace == "aeat.profile.bucket"
        assert report.unreadable_total == 0
        assert report.check.status == "ok"


class TestBuildListReport:
    def test_list_returns_all_keys_in_namespace(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 3, tag="a")
            report = build_repair_list_report(
                namespace="aeat.workflow",
                repository=SecureObjectRepository(engine=engine),
            )
        assert report.namespace == "aeat.workflow"
        assert report.rows_total == 3
        digests = tuple(row.object_key_digest for row in report.rows)
        # Natural keys are HMAC-digested at the column boundary; the
        # report surfaces the opaque digests, three distinct entries.
        assert len(set(digests)) == 3
        assert all(digest for digest in digests)
        assert report.integrity.readable == 3

    def test_list_filter_mode_reflects_flag_selection(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            repo = SecureObjectRepository(engine=engine)
            default = build_repair_list_report(namespace="aeat.workflow", repository=repo)
            assert default.filter_mode == "default"
            all_mode = build_repair_list_report(
                namespace="aeat.workflow",
                include_all=True,
                repository=repo,
            )
            assert all_mode.filter_mode == "all"
            unreadable_mode = build_repair_list_report(
                namespace="aeat.workflow",
                only_unreadable=True,
                repository=repo,
            )
            assert unreadable_mode.filter_mode == "unreadable"

    def test_list_refuses_when_both_flags_passed(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A), pytest.raises(ValueError, match="cannot combine"):
            build_repair_list_report(
                namespace="aeat.workflow",
                include_all=True,
                only_unreadable=True,
                repository=SecureObjectRepository(engine=engine),
            )

    def test_list_empty_namespace_returns_zero_rows(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            report = build_repair_list_report(
                namespace="empty.ns",
                repository=SecureObjectRepository(engine=engine),
            )
        assert report.rows_total == 0
        assert report.rows == ()


class TestReportInvariants:
    def test_integrity_report_is_frozen(self, tmp_path: Path) -> None:
        from pydantic import ValidationError

        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 1, tag="a")
            report = build_repair_integrity_report(
                repository=SecureObjectRepository(engine=engine),
            )
        with pytest.raises(ValidationError):
            report.readable_total = 99  # type: ignore[misc]
