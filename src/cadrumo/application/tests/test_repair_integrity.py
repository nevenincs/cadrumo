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
from typing import cast

import pytest

from ...adapters.persistence.storage import (
    REPAIR_INTEGRITY_DECISION_NAMESPACE,
    WORKFLOW_STATE_NAMESPACE,
    StorageValidationError,
    has_active_bucket_session,
    suspend_active_session,
)
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ...adapters.persistence.storage.sql.engine import dispose_engine
from ...adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ...core.operator_action_enums import ActionArgumentSource, ActionArgumentStatus, ActionConditionality
from ...core.classification import SensitivityClass
from ...core.config import override_settings
from ...tests.master_key import EphemeralMasterKeyProvider
from ...tests.secure_sql import isolated_runtime_profile
from ..repair_integrity import (
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
_ROW_WRITTEN_AT = datetime(2026, 5, 28, 13, 5, 0, tzinfo=UTC)
_BOOTSTRAP_WRITTEN_AT = datetime(2026, 5, 28, 13, 10, 0, tzinfo=UTC)


@pytest.fixture
def own_bucket_runtime() -> None:
    """Opt out of this module's explicit-database binding.

    Requested by a test that drives a real bucket runtime and therefore routes
    its own database.  Requesting the fixture IS the opt-out signal that
    :func:`isolated_default_secure_sql` reads.
    """
    return None


@pytest.fixture(autouse=True)
def isolated_default_secure_sql(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[None]:
    """Bind each repair integrity test to one explicit database through settings.

    The opt-out is a requested fixture rather than a test name.  This fixture
    once matched one hardcoded node name, so renaming that test silently
    re-armed the override -- and the damage landed inside the bucket runtime's
    own setup, nowhere near the rename that caused it.  A fixture name is
    checked by pytest and survives a rename.
    """

    if "own_bucket_runtime" in request.fixturenames:
        yield
        return
    db_path = tmp_path / "repair-integrity.db"
    with override_settings(cadrumo_database_url=f"sqlite:///{db_path.as_posix()}") as settings:
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
            written_at=_ROW_WRITTEN_AT,
            payload=f"repair-integrity-payload:{namespace}:{tag}:{index}".encode(),
        )


class TestBuildIntegrityReport:
    def test_clean_install_reports_ok(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("cadrumo.workflow", 5, tag="a")
            _save_rows("cadrumo.profile.bucket", 3, tag="a")
            report = build_repair_integrity_report(repository=SecureObjectRepository())
        assert report.readable_total == 8
        assert report.unreadable_total == 0
        assert report.check.status == "ok"
        assert report.check.precondition_verdict is None

    def test_undecryptable_rows_surface_fail_with_typed_quarantine_verdict(self) -> None:
        # Two rows written under key A become undecryptable once the
        # active master key rotates to B.
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("cadrumo.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows("cadrumo.workflow", 5, tag="current")
            _save_rows("cadrumo.profile.bucket", 3, tag="current")
            report = build_repair_integrity_report(repository=SecureObjectRepository())
        workflow = next(ns for ns in report.namespaces if ns.namespace == "cadrumo.workflow")
        assert workflow.readable == 5
        assert workflow.unreadable == 2
        assert report.unreadable_total == 2
        assert report.check.status == "fail"
        verdict = report.check.precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "diagnostics.secure_objects.integrity.readable"
        assert verdict.evidence[0].evidence_id == "diagnostics.secure_objects.integrity.observation"
        assert verdict.evidence[0].values == {"readable_total": 8, "unreadable_total": 2}
        assert verdict.action is not None
        assert verdict.action.action_id == "operator.diagnostics.secure_objects.quarantine"
        assert verdict.conditionality is ActionConditionality.IMMEDIATE
        assert len(verdict.argument_bindings) == 1
        binding = verdict.argument_bindings[0]
        assert binding.argument_name == "yes"
        assert binding.status is ActionArgumentStatus.RESOLVED
        assert binding.value is True
        assert binding.source is ActionArgumentSource.VERDICT_CONTEXT
        assert binding.source_key == "yes"

    def test_namespace_filter_restricts_scope(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("cadrumo.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows("cadrumo.workflow", 5, tag="current")
            _save_rows("cadrumo.profile.bucket", 3, tag="current")
            report = build_repair_integrity_report(
                namespace="cadrumo.profile.bucket",
                repository=SecureObjectRepository(),
            )
        # Filtering to the clean namespace excludes the workflow
        # namespace's stale rows entirely.
        assert len(report.namespaces) == 1
        assert report.namespaces[0].namespace == "cadrumo.profile.bucket"
        assert report.unreadable_total == 0
        assert report.check.status == "ok"

    def test_namespace_enumeration_failure_is_not_reported_as_clean_integrity(self) -> None:
        with pytest.raises(AttributeError, match="list_namespaces"):
            build_repair_integrity_report(repository=cast(SecureObjectRepository, object()))


class TestBuildListReport:
    def test_list_returns_all_keys_in_namespace(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("cadrumo.workflow", 3, tag="a")
            report = build_repair_list_report(namespace="cadrumo.workflow", repository=SecureObjectRepository())
        assert report.namespace == "cadrumo.workflow"
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
            default = build_repair_list_report(namespace="cadrumo.workflow", repository=repo)
            assert default.filter_mode == "default"
            all_mode = build_repair_list_report(
                namespace="cadrumo.workflow",
                include_all=True,
                repository=repo,
            )
            assert all_mode.filter_mode == "all"
            unreadable_mode = build_repair_list_report(
                namespace="cadrumo.workflow",
                only_unreadable=True,
                repository=repo,
            )
            assert unreadable_mode.filter_mode == "unreadable"

    def test_list_unreadable_filters_to_only_failed_decryption_rows(self) -> None:
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows("cadrumo.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            repo = SecureObjectRepository()
            _save_rows("cadrumo.workflow", 3, tag="current")
            default = build_repair_list_report(namespace="cadrumo.workflow", repository=repo)
            unreadable = build_repair_list_report(namespace="cadrumo.workflow", only_unreadable=True, repository=repo)

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

    def test_list_refuses_without_a_session_instead_of_listing_a_sound_row_as_unreadable(
        self,
        tmp_path: Path,
        own_bucket_runtime: None,
    ) -> None:
        """The list surface opens no session of its own, so it refuses without one.

        It used to enter the shared-master provider when no per-profile session
        served the bucket, which unlocked a taxpayer's records with no password
        to satisfy a diagnostic.  Without that branch the substrate answers, and
        its readiness refusal is the right answer: every row is undecryptable
        without the bucket key, so a report produced keyless would call a sound
        bucket corrupt -- and the quarantine verb moves exactly the rows a probe
        calls unreadable.

        The served read above the suspension is the anti-tautology half: it
        proves the row is present and decrypts, so the refusal below is the
        missing key and not a missing row.
        """
        with isolated_runtime_profile(tmp_path=tmp_path):
            assert WORKFLOW_STATE_NAMESPACE.default_object_key is not None
            secure_object_repository_for_active_bucket().save(
                namespace=WORKFLOW_STATE_NAMESPACE.namespace,
                object_key=WORKFLOW_STATE_NAMESPACE.default_object_key,
                classification=WORKFLOW_STATE_NAMESPACE.sensitivity,
                schema_version=WORKFLOW_STATE_NAMESPACE.schema_version,
                written_at=_BOOTSTRAP_WRITTEN_AT,
                payload=b"repair-list-sessionless",
            )
            served = build_repair_list_report(namespace="cadrumo.workflow")
            with suspend_active_session():
                assert not has_active_bucket_session()
                with pytest.raises(StorageValidationError) as refusal:
                    build_repair_list_report(namespace="cadrumo.workflow")

        assert served.rows_total == 1
        assert served.integrity.readable == 1
        assert served.integrity.unreadable == 0
        assert refusal.value.translated_message == "errors.storage.runtime.not_ready"

    def test_list_refuses_when_both_flags_passed(self) -> None:
        with (
            EphemeralMasterKeyProvider(key=_KEY_A),
            pytest.raises(RepairIntegrityError) as exc_info,
        ):
            build_repair_list_report(
                namespace="cadrumo.workflow",
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
            _save_rows("cadrumo.workflow", 1, tag="a")
            report = build_repair_integrity_report(repository=SecureObjectRepository())
        with pytest.raises(ValidationError):
            report.__setattr__("readable_total", 99)


class TestRepairRemediationDecisionRepository:
    def test_load_refuses_decision_payload_when_content_hash_does_not_match(self) -> None:
        decided_at = datetime(2026, 5, 27, 12, 0, tzinfo=UTC)
        original_id = repair_remediation_decision_id(
            target_namespace="cadrumo.workflow",
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
            target_namespace="cadrumo.workflow",
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
                namespace=REPAIR_INTEGRITY_DECISION_NAMESPACE.namespace,
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
