"""Tests for the repair integrity + list subverb backends.

Every test drives the *real* :class:`SecureObjectRepository` through
central settings and a real :class:`EphemeralMasterKeyProvider`. The
"undecryptable row" path is produced the only way it occurs in
production -- rows written under one master key, probed under a
different one -- so the crypto-probe in ``probe_namespace_integrity``
is genuinely exercised. No stub repository: if that probe or the
report aggregation regressed, these tests fail.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.application.repair_integrity import (
    _REPAIR_DECISION_NAMESPACE,
    RepairRemediationDecision,
    RepairRemediationDecisionRepository,
    build_repair_integrity_report,
    build_repair_list_report,
    repair_remediation_decision_id,
)
from aeat.core.classification import SensitivityClass
from aeat.core.config import override_settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Two fixed, distinct 32-byte master keys. Rows written under one and
# probed under the other are genuinely undecryptable -- the exact
# production condition `aeat config repair` exists to surface.
_KEY_A = b"\xa1" * 32
_KEY_B = b"\xb2" * 32


@contextmanager
def _explicit_storage(tmp_path: Path) -> Iterator[None]:
    """Bind the repair test to one explicit database through settings."""

    db_path = tmp_path / "repair-integrity.db"
    with override_settings(aeat_database_url=f"sqlite:///{db_path.as_posix()}") as settings:
        dispose_engine(settings)
        try:
            yield
        finally:
            dispose_engine(settings)


def _save_rows(namespace: str, count: int, *, tag: str) -> None:
    """Persist ``count`` real encrypted secure objects under ``namespace``.

    ``tag`` namespaces the natural object keys so rows written across
    separate master-key sessions never collide on the HMAC digest
    (which would upsert-overwrite instead of accumulating).
    """
    repo = SecureObjectRepository()
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
        with _explicit_storage(tmp_path), EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 5, tag="a")
            _save_rows("aeat.profile.bucket", 3, tag="a")
            report = build_repair_integrity_report()
        assert report.readable_total == 8
        assert report.unreadable_total == 0
        assert report.check.status == "ok"
        assert report.check.next_action is None or report.check.next_action == ""
        assert report.check.dead_end is None or report.check.dead_end == ""

    def test_undecryptable_rows_surface_fail_with_next_action(self, tmp_path: Path) -> None:
        with _explicit_storage(tmp_path):
            # Two rows written under key A become undecryptable once the
            # active master key rotates to B.
            with EphemeralMasterKeyProvider(key=_KEY_A):
                _save_rows("aeat.workflow", 2, tag="stale")
            with EphemeralMasterKeyProvider(key=_KEY_B):
                _save_rows("aeat.workflow", 5, tag="current")
                _save_rows("aeat.profile.bucket", 3, tag="current")
                report = build_repair_integrity_report()
        workflow = next(ns for ns in report.namespaces if ns.namespace == "aeat.workflow")
        assert workflow.readable == 5
        assert workflow.unreadable == 2
        assert report.unreadable_total == 2
        assert report.check.status == "fail"
        assert report.check.next_action == "aeat config repair quarantine --yes"

    def test_namespace_filter_restricts_scope(self, tmp_path: Path) -> None:
        with _explicit_storage(tmp_path):
            with EphemeralMasterKeyProvider(key=_KEY_A):
                _save_rows("aeat.workflow", 2, tag="stale")
            with EphemeralMasterKeyProvider(key=_KEY_B):
                _save_rows("aeat.workflow", 5, tag="current")
                _save_rows("aeat.profile.bucket", 3, tag="current")
                report = build_repair_integrity_report(namespace="aeat.profile.bucket")
        # Filtering to the clean namespace excludes the workflow
        # namespace's stale rows entirely.
        assert len(report.namespaces) == 1
        assert report.namespaces[0].namespace == "aeat.profile.bucket"
        assert report.unreadable_total == 0
        assert report.check.status == "ok"


class TestBuildListReport:
    def test_list_returns_all_keys_in_namespace(self, tmp_path: Path) -> None:
        with _explicit_storage(tmp_path), EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 3, tag="a")
            report = build_repair_list_report(namespace="aeat.workflow")
        assert report.namespace == "aeat.workflow"
        assert report.rows_total == 3
        digests = tuple(row.object_key_digest for row in report.rows)
        # Natural keys are HMAC-digested at the column boundary; the
        # report surfaces the opaque digests, three distinct entries.
        assert len(set(digests)) == 3
        assert all(digest for digest in digests)
        assert report.integrity.readable == 3

    def test_list_filter_mode_reflects_flag_selection(self, tmp_path: Path) -> None:
        with _explicit_storage(tmp_path), EphemeralMasterKeyProvider(key=_KEY_A):
            repo = SecureObjectRepository()
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

    def test_list_unreadable_filters_to_only_failed_decryption_rows(self, tmp_path: Path) -> None:
        with _explicit_storage(tmp_path):
            with EphemeralMasterKeyProvider(key=_KEY_A):
                _save_rows("aeat.workflow", 2, tag="stale")
            with EphemeralMasterKeyProvider(key=_KEY_B):
                _save_rows("aeat.workflow", 3, tag="current")
                default = build_repair_list_report(namespace="aeat.workflow")
                unreadable = build_repair_list_report(namespace="aeat.workflow", only_unreadable=True)

        assert default.rows_total == 5
        assert default.integrity.readable == 3
        assert default.integrity.unreadable == 2
        assert unreadable.filter_mode == "unreadable"
        assert unreadable.rows_total == 2
        assert {row.readable for row in unreadable.rows} == {False}
        assert all(row.reason for row in unreadable.rows)
        assert set(row.object_key_digest for row in unreadable.rows).issubset(
            {row.object_key_digest for row in default.rows}
        )

    def test_list_refuses_when_both_flags_passed(self, tmp_path: Path) -> None:
        with (
            _explicit_storage(tmp_path),
            EphemeralMasterKeyProvider(key=_KEY_A),
            pytest.raises(ValueError, match="cannot combine"),
        ):
            build_repair_list_report(
                namespace="aeat.workflow",
                include_all=True,
                only_unreadable=True,
            )

    def test_list_empty_namespace_returns_zero_rows(self, tmp_path: Path) -> None:
        with _explicit_storage(tmp_path), EphemeralMasterKeyProvider(key=_KEY_A):
            report = build_repair_list_report(namespace="empty.ns")
        assert report.rows_total == 0
        assert report.rows == ()


class TestReportInvariants:
    def test_integrity_report_is_frozen(self, tmp_path: Path) -> None:
        from pydantic import ValidationError

        with _explicit_storage(tmp_path), EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 1, tag="a")
            report = build_repair_integrity_report()
        with pytest.raises(ValidationError):
            report.readable_total = 99  # type: ignore[misc]


class TestRepairRemediationDecisionRepository:
    def test_load_refuses_decision_payload_when_content_hash_does_not_match(self, tmp_path: Path) -> None:
        decided_at = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
        original_id = repair_remediation_decision_id(
            target_namespace="aeat.workflow",
            target_object_key_digest="abc123",
            outcome="rebuild",
            decided_at=decided_at,
            decided_by="operator",
            reason="original evidence",
            likely_origin="rotated-key",
            replacement_evidence_requirements=("export",),
            verified_replacement_evidence_refs=(),
        )
        tampered = RepairRemediationDecision(
            decision_id=original_id,
            target_namespace="aeat.workflow",
            target_object_key_digest="abc123",
            outcome="rebuild",
            decided_at=decided_at,
            decided_by="operator",
            reason="tampered evidence",
            likely_origin="rotated-key",
            replacement_evidence_requirements=("export",),
            verified_replacement_evidence_refs=(),
        )
        with _explicit_storage(tmp_path), EphemeralMasterKeyProvider(key=_KEY_A):
            secure_repository = SecureObjectRepository()
            secure_repository.save(
                namespace=_REPAIR_DECISION_NAMESPACE,
                object_key=original_id,
                classification=SensitivityClass.AUDIT,
                schema_version=1,
                written_at=decided_at,
                payload=tampered.model_dump_json().encode("utf-8"),
            )
            with pytest.raises(ValueError, match="re-derived"):
                RepairRemediationDecisionRepository(repository=secure_repository).load_decision(original_id)
