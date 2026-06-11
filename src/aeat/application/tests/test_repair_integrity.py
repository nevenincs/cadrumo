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
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ...adapters.persistence.storage import (
    WORKFLOW_STATE_NAMESPACE,
    EphemeralMasterKeyProvider,
    has_active_bucket_session,
)
from ...adapters.persistence.storage.master_key._active_session import _active_session
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...core.classification import SensitivityClass
from ...core.config import override_settings
from ...tests.secure_sql import isolated_runtime_profile
from ..repair_integrity import (
    _REPAIR_DECISION_NAMESPACE,
    RepairDecisionNotFoundError,
    RepairIntegrityError,
    RepairRemediationDecision,
    RepairRemediationDecisionRepository,
    build_repair_integrity_report,
    build_repair_list_report,
    repair_remediation_decision_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Two fixed, distinct 32-byte master keys. Rows written under one and
# probed under the other are genuinely undecryptable -- the exact
# production condition `aeat config repair` exists to surface.
_KEY_A = b"\xa1" * 32
_KEY_B = b"\xb2" * 32


@pytest.fixture(autouse=True)
def _isolated_default_secure_sql(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[None]:
    """Bind each repair integrity test to one explicit database through settings."""

    if request.node.name == "test_list_opens_active_bucket_session_for_bootstrap_exempt_repair":
        yield
        return
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
    def test_clean_install_reports_ok(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 5, tag="a")
            _save_rows("aeat.profile.bucket", 3, tag="a")
            report = build_repair_integrity_report(repository=SecureObjectRepository())
        assert report.readable_total == 8
        assert report.unreadable_total == 0
        assert report.check.status == "ok"
        assert report.check.next_action is None or report.check.next_action == ""
        assert report.check.dead_end is None or report.check.dead_end == ""

    def test_undecryptable_rows_surface_fail_with_next_action(self) -> None:
        # Two rows written under key A become undecryptable once the
        # active master key rotates to B.
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows("aeat.workflow", 5, tag="current")
            _save_rows("aeat.profile.bucket", 3, tag="current")
            report = build_repair_integrity_report(repository=SecureObjectRepository())
        workflow = next(ns for ns in report.namespaces if ns.namespace == "aeat.workflow")
        assert workflow.readable == 5
        assert workflow.unreadable == 2
        assert report.unreadable_total == 2
        assert report.check.status == "fail"
        assert report.check.next_action == "aeat config repair quarantine --yes"

    def test_namespace_filter_restricts_scope(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows("aeat.workflow", 5, tag="current")
            _save_rows("aeat.profile.bucket", 3, tag="current")
            report = build_repair_integrity_report(
                namespace="aeat.profile.bucket",
                repository=SecureObjectRepository(),
            )
        # Filtering to the clean namespace excludes the workflow
        # namespace's stale rows entirely.
        assert len(report.namespaces) == 1
        assert report.namespaces[0].namespace == "aeat.profile.bucket"
        assert report.unreadable_total == 0
        assert report.check.status == "ok"

    def test_namespace_enumeration_failure_is_not_reported_as_clean_integrity(self) -> None:
        with pytest.raises(AttributeError, match="list_namespaces"):
            build_repair_integrity_report(repository=object())  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # negative test: bare object lacks list_namespaces


class TestBuildListReport:
    def test_list_returns_all_keys_in_namespace(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 3, tag="a")
            report = build_repair_list_report(namespace="aeat.workflow", repository=SecureObjectRepository())
        assert report.namespace == "aeat.workflow"
        assert report.rows_total == 3
        digests = tuple(row.object_key_digest for row in report.rows)
        # Natural keys are HMAC-digested at the column boundary; the
        # report surfaces the opaque digests, three distinct entries.
        assert len(set(digests)) == 3
        assert all(digest for digest in digests)
        assert report.integrity.readable == 3

    def test_list_filter_mode_reflects_flag_selection(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
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

    def test_list_unreadable_filters_to_only_failed_decryption_rows(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            repo = SecureObjectRepository()
            _save_rows("aeat.workflow", 3, tag="current")
            default = build_repair_list_report(namespace="aeat.workflow", repository=repo)
            unreadable = build_repair_list_report(namespace="aeat.workflow", only_unreadable=True, repository=repo)

        assert default.rows_total == 5
        assert default.integrity.readable == 3
        assert default.integrity.unreadable == 2
        assert unreadable.filter_mode == "unreadable"
        assert unreadable.rows_total == 2
        assert {row.readable for row in unreadable.rows} == {False}
        assert all(row.reason for row in unreadable.rows)
        assert set(row.object_key_digest for row in unreadable.rows).issubset(
            {row.object_key_digest for row in default.rows},
        )

    def test_list_opens_active_bucket_session_for_bootstrap_exempt_repair(self, tmp_path: Path) -> None:
        with isolated_runtime_profile(tmp_path=tmp_path):
            secure_object_repository_for_active_bucket().save(
                namespace=WORKFLOW_STATE_NAMESPACE.namespace,
                object_key="workflow:repair-list",
                classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                written_at=datetime.now(UTC),
                payload=b"repair-list-sessionless",
            )
            token = _active_session.set(None)
            assert not has_active_bucket_session()
            try:
                report = build_repair_list_report(namespace="aeat.workflow")
            finally:
                _active_session.reset(token)

        assert report.rows_total == 1
        assert report.integrity.readable + report.integrity.unreadable == 1

    def test_list_refuses_when_both_flags_passed(self) -> None:
        with (
            EphemeralMasterKeyProvider(key=_KEY_A),
            pytest.raises(RepairIntegrityError) as exc_info,
        ):
            build_repair_list_report(
                namespace="aeat.workflow",
                include_all=True,
                only_unreadable=True,
            )
        assert exc_info.value.translated_message == "application.repair_integrity.errors.conflicting_list_filters"
        assert exc_info.value.context == {"filters": "--all,--unreadable"}

    def test_list_empty_namespace_returns_zero_rows(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            report = build_repair_list_report(namespace="empty.ns", repository=SecureObjectRepository())
        assert report.rows_total == 0
        assert report.rows == ()


class TestReportInvariants:
    def test_integrity_report_is_frozen(self) -> None:
        from pydantic import ValidationError

        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("aeat.workflow", 1, tag="a")
            report = build_repair_integrity_report(repository=SecureObjectRepository())
        with pytest.raises(ValidationError):
            report.readable_total = 99  # type: ignore[misc]


class TestRepairRemediationDecisionRepository:
    def test_load_refuses_decision_payload_when_content_hash_does_not_match(self) -> None:
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
        with EphemeralMasterKeyProvider(key=_KEY_A):
            secure_repository = SecureObjectRepository()
            secure_repository.save(
                namespace=_REPAIR_DECISION_NAMESPACE,
                object_key=original_id,
                classification=SensitivityClass.AUDIT,
                schema_version=1,
                written_at=decided_at,
                payload=tampered.model_dump_json().encode("utf-8"),
            )
            with pytest.raises(RepairIntegrityError) as exc_info:
                RepairRemediationDecisionRepository(repository=secure_repository).load_decision(original_id)
        assert exc_info.value.translated_message == "application.repair_integrity.errors.decision_id_mismatch_load"
        assert exc_info.value.context is not None
        assert exc_info.value.context["decision_id"] == original_id
        assert exc_info.value.context["payload_decision_id"] == original_id
        assert exc_info.value.context["expected_decision_id"] != original_id

    def test_load_decision_not_found_uses_localized_context(self) -> None:
        missing_id = "0" * 64
        with (
            EphemeralMasterKeyProvider(key=_KEY_A),
            pytest.raises(RepairDecisionNotFoundError) as exc_info,
        ):
            RepairRemediationDecisionRepository(repository=SecureObjectRepository()).load_decision(missing_id)
        assert exc_info.value.translated_message == "application.repair_integrity.errors.decision_not_found"
        assert exc_info.value.context == {"decision_id": missing_id}
