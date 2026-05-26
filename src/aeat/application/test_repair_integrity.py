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
from pydantic import ValidationError

from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
from aeat.adapters.persistence.storage.envelope import Envelope
from aeat.adapters.persistence.storage.sql._orm import Base
from aeat.adapters.persistence.storage.sql.engine import create_engine_from_settings
from aeat.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from aeat.application.diagnostics import DiagnosticCheck
from aeat.application.repair_integrity import (
    RepairEnvelopeValidationFinding,
    RepairEnvelopeValidationReport,
    RepairIntegrityAttributionReport,
    RepairRemediationDecision,
    RepairRemediationDecisionRepository,
    RepairUnreadableClassificationGroup,
    RepairUnreadableNamespaceAttribution,
    RepairUnreadableRowAttribution,
    build_repair_envelope_validation_report,
    build_repair_integrity_attribution_report,
    build_repair_integrity_report,
    build_repair_list_report,
    build_repair_namespace_policy,
    classify_repair_namespace,
    repair_remediation_decision_id,
)
from aeat.core.classification import SensitivityClass
from aeat.core.config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

# Two fixed, distinct 32-byte master keys. Rows written under one and
# probed under the other are genuinely undecryptable -- the exact
# production condition `aeat config repair` exists to surface.
_KEY_A = b"\xa1" * 32
_KEY_B = b"\xb2" * 32


def _classification_group(count: int = 1) -> tuple[RepairUnreadableClassificationGroup, ...]:
    return (
        RepairUnreadableClassificationGroup(
            classification="operational",
            unreadable_count=count,
        ),
    )


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


def _active_secure_object_namespaces() -> tuple[str, ...]:
    """Return production secure-object namespaces imported from their owners."""
    from aeat.adapters.outbound.aeat.auth import CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE
    from aeat.adapters.outbound.aeat.auth._session_store import _SESSION_NAMESPACE
    from aeat.adapters.outbound.aeat.sede._observation_store import (
        _ARTEFACT_NAMESPACE,
        _IVA_WALLET_OBSERVATION_NAMESPACE,
        _OBSERVATION_NAMESPACE,
    )
    from aeat.adapters.outbound.google import _session_store as google_session_store
    from aeat.adapters.outbound.llm._cache import _CACHE_NAMESPACE
    from aeat.adapters.outbound.llm._usage import _USAGE_NAMESPACE
    from aeat.adapters.persistence.profile.assets import _AMORTIZACION_NAMESPACE, _ASSETS_NAMESPACE
    from aeat.adapters.persistence.profile.inventory import _INVENTORY_NAMESPACE
    from aeat.adapters.persistence.storage.attachment import (
        _ATTACHMENT_BLOB_NAMESPACE,
        _ATTACHMENT_MANIFEST_NAMESPACE,
    )
    from aeat.application.auth._apoderado import _ApoderadoConfigRepository
    from aeat.application.calculations._iva_compensation_history import IvaCompensationHistoryRepository
    from aeat.application.calculations._observations_repository import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from aeat.application.filing._history_repository import ModeloHistoryRepository
    from aeat.application.live import BORRADOR_100_SNAPSHOT_NAMESPACE
    from aeat.application.live._censo import CENSUS_SNAPSHOT_NAMESPACE
    from aeat.application.user_profile import USER_PROFILE_SNAPSHOT_NAMESPACE, USER_PROFILE_VALUE_NAMESPACE
    from aeat.application.workflow._persistence import _RUN_NAMESPACE, _STATE_NAMESPACE
    from aeat.domain.buckets._event_repository import _NAMESPACE as _BUCKET_EVENT_NAMESPACE
    from aeat.domain.filing._complementaria_repository import _AMENDMENT_NAMESPACE
    from aeat.domain.filing._repository import ModeloDraftRepository
    from aeat.domain.invoices._repository import _INVOICE_NAMESPACE
    from aeat.domain.justificante._repository import JustificanteRepository
    from aeat.domain.modelos._calculation_repository import _CALCULATION_NAMESPACE
    from aeat.domain.modelos._filing_repository import _FILING_NAMESPACE
    from aeat.domain.modelos._repository import _WORK_UNIT_NAMESPACE
    from aeat.domain.modelos._verification_repository import _VERIFICATION_NAMESPACE
    from aeat.domain.submission._repository import SubmissionRepository
    from aeat.domain.transactions import TX_BUCKET_NAMESPACE
    from aeat.domain.usage_ratios._service import _USAGE_RATIO_NAMESPACE

    namespaces = (
        CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE,
        _SESSION_NAMESPACE,
        _ARTEFACT_NAMESPACE,
        _OBSERVATION_NAMESPACE,
        _IVA_WALLET_OBSERVATION_NAMESPACE,
        google_session_store._NAMESPACE_CLIENT,
        google_session_store._NAMESPACE_TOKEN,
        google_session_store._NAMESPACE_METADATA,
        google_session_store._NAMESPACE_DRIVE_CONFIG,
        _CACHE_NAMESPACE,
        _USAGE_NAMESPACE,
        _ASSETS_NAMESPACE,
        _AMORTIZACION_NAMESPACE,
        _INVENTORY_NAMESPACE,
        _ATTACHMENT_BLOB_NAMESPACE,
        _ATTACHMENT_MANIFEST_NAMESPACE,
        _ApoderadoConfigRepository.namespace,
        IvaCompensationHistoryRepository.namespace,
        CalculationObservationRepository.namespace,
        IvaWalletDecisionRepository.namespace,
        IvaWalletDecisionRepository.history_namespace,
        ModeloHistoryRepository.namespace,
        BORRADOR_100_SNAPSHOT_NAMESPACE,
        CENSUS_SNAPSHOT_NAMESPACE,
        USER_PROFILE_VALUE_NAMESPACE,
        USER_PROFILE_SNAPSHOT_NAMESPACE,
        _STATE_NAMESPACE,
        _RUN_NAMESPACE,
        _BUCKET_EVENT_NAMESPACE,
        _AMENDMENT_NAMESPACE,
        ModeloDraftRepository.namespace,
        _INVOICE_NAMESPACE,
        JustificanteRepository.namespace,
        _CALCULATION_NAMESPACE,
        _FILING_NAMESPACE,
        _WORK_UNIT_NAMESPACE,
        _VERIFICATION_NAMESPACE,
        SubmissionRepository.namespace,
        TX_BUCKET_NAMESPACE,
        _USAGE_RATIO_NAMESPACE,
    )
    assert len(namespaces) == len(set(namespaces))
    return tuple(sorted(namespaces))


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
        assert report.check.next_action == "aeat config repair list aeat.workflow --unreadable"

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
                active_bucket_id="bucket-a",
                repository=SecureObjectRepository(engine=engine),
            )
        assert report.namespace == "aeat.workflow"
        assert report.namespace_classification.role == "workflow_runtime_state"
        assert report.namespace_classification.destructive_repair_risk.endswith("workflow_state_reviewed")
        assert report.rows_total == 3
        digests = tuple(row.object_key_digest for row in report.rows)
        # Natural keys are HMAC-digested at the column boundary; the
        # report surfaces the opaque digests, three distinct entries.
        assert len(set(digests)) == 3
        assert all(digest for digest in digests)
        assert report.integrity.readable == 3
        assert {row.context_bucket_id for row in report.rows} == {"active_profile"}
        assert {row.object_key_kind for row in report.rows} == {"singleton_workflow_state"}
        assert {row.object_key_hint for row in report.rows} == {"state"}
        assert {row.context_confidence for row in report.rows} == {"repository_contract_unverified_digest"}

    def test_list_context_matches_active_bucket_transaction_catalogue_key(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            SecureObjectRepository(engine=engine).save(
                namespace="aeat.domain.transactions.bucket",
                object_key="transaction-catalogue:bucket-a",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=b"transaction-catalogue-payload",
            )
            report = build_repair_list_report(
                namespace="aeat.domain.transactions.bucket",
                active_bucket_id="bucket-a",
                repository=SecureObjectRepository(engine=engine),
            )

        assert report.rows_total == 1
        row = report.rows[0]
        assert row.context_bucket_id == "active_profile"
        assert row.object_key_kind == "active_bucket_transaction_catalogue"
        assert row.object_key_hint == "transaction-catalogue:<active-profile>"
        assert row.context_confidence == "active_key_digest_match"
        assert "bucket-a" not in row.model_dump_json()

    def test_list_context_redacts_wallet_observation_key_shape(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(
                engine,
                "aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
                1,
                tag="a",
            )
            report = build_repair_list_report(
                namespace="aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
                active_bucket_id="bucket-a",
                repository=SecureObjectRepository(engine=engine),
            )

        assert report.rows_total == 1
        row = report.rows[0]
        assert row.context_bucket_id == "active_profile"
        assert row.object_key_kind == "iva_wallet_observation"
        assert row.object_key_hint == ""
        assert row.context_confidence == "unrecoverable_hmac_digest"
        assert "taxpayer" in row.context_note
        assert "NIF" not in row.context_note

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

    def test_list_unreadable_filters_to_rows_that_fail_decryption(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 2, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows(engine, "aeat.workflow", 3, tag="current")
            report = build_repair_list_report(
                namespace="aeat.workflow",
                only_unreadable=True,
                repository=SecureObjectRepository(engine=engine),
            )

        assert report.filter_mode == "unreadable"
        assert report.integrity.readable == 3
        assert report.integrity.unreadable == 2
        assert report.rows_total == 2
        assert all(row.readable is False for row in report.rows)
        assert all(row.row_id is not None for row in report.rows)
        assert all(row.written_at is not None for row in report.rows)

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
        assert report.namespace_classification.role == "unknown_secure_object_namespace"
        assert report.namespace_classification.destructive_repair_risk == "unknown_do_not_quarantine_blindly"

    def test_namespace_classifier_marks_wallet_observations_as_iva_history_evidence(self) -> None:
        classification = classify_repair_namespace(
            "aeat.outbound.aeat.sede.iva_compensation_wallet.observations"
        )

        assert classification.role == "aeat_remote_wallet_observation"
        assert classification.iva_reconciliation_relevance == "remote_wallet_balance_evidence"
        assert classification.participates_in_iva_compensation_history is True
        assert classification.destructive_repair_risk == "high_preserve_until_wallet_reconciliation_exported"
        assert classification.replacement_evidence_requirements == (
            "export_encrypted_profile_backup_before_any_change",
            "record_operator_preserve_first_decision",
            "capture_fresh_read_only_aeat_wallet_observation_or_export_existing_observation",
            "replay_wallet_reconciliation_decision_from_verified_evidence",
            "record_taxpayer_override_reason_if_wallet_value_is_not_selected",
        )

    def test_namespace_classifier_marks_filed_declarations_as_remote_filing_evidence(self) -> None:
        classification = classify_repair_namespace(
            "aeat.outbound.aeat.sede.filed_declaration.observations"
        )

        assert classification.role == "aeat_remote_filed_declaration_evidence"
        assert classification.iva_reconciliation_relevance == "remote_filing_history_evidence"
        assert classification.participates_in_iva_compensation_history is True
        assert classification.destructive_repair_risk == "high_preserve_until_filing_history_reviewed"
        assert classification.destructive_quarantine_allowed is False
        assert classification.destructive_quarantine_policy == "disabled_without_engineer_override_adr"

    def test_namespace_classifier_marks_submission_receipts_as_critical(self) -> None:
        classification = classify_repair_namespace("aeat.domain.justificante.metadata")

        assert classification.role == "submission_receipt_metadata"
        assert classification.participates_in_iva_compensation_history is True
        assert classification.destructive_repair_risk == "critical_preserve_submission_receipts"
        assert classification.destructive_quarantine_allowed is False
        assert classification.destructive_quarantine_policy == "disabled_without_engineer_override_adr"
        assert classification.replacement_evidence_requirements == (
            "export_encrypted_profile_backup_before_any_change",
            "record_operator_preserve_first_decision",
            "verify_filed_declaration_or_receipt_copy_from_aeat_sede",
            "record_csv_or_justificante_reference_before_quarantine",
            "disable_destructive_quarantine_without_engineer_override_adr",
        )

    def test_unknown_namespace_requires_owner_contract_before_remediation(self) -> None:
        classification = classify_repair_namespace("aeat.unregistered.future_feature")

        assert classification.role == "unknown_secure_object_namespace"
        assert classification.replacement_evidence_requirements == (
            "identify_owning_repository_contract",
            "export_encrypted_profile_backup_before_any_change",
            "record_engineer_review_preserve_first_decision",
        )
        assert classification.destructive_quarantine_allowed is False
        assert classification.destructive_quarantine_policy == "disabled_until_namespace_owner_contract_is_registered"

    def test_namespace_classifier_marks_repair_decisions_as_preserve_first_context(self) -> None:
        classification = classify_repair_namespace("aeat.application.repair.decisions")

        assert classification.role == "repair_remediation_decision"
        assert classification.participates_in_iva_compensation_history is True
        assert classification.replacement_evidence_requirements == (
            "export_encrypted_profile_backup_before_any_change",
            "record_operator_preserve_first_decision",
            "identify_owning_repository_contract",
            "verify_replacement_evidence_for_affected_domain",
        )

    def test_namespace_policy_maps_wallet_to_remote_state_recovery(self) -> None:
        policy = build_repair_namespace_policy(
            "aeat.outbound.aeat.sede.iva_compensation_wallet.observations"
        )

        assert policy.owner_domain == "iva_wallet_remote_state"
        assert policy.bucket_scope == "profile_bucket_with_remote_authority_context"
        assert policy.sensitivity_class == "financial"
        assert policy.repair_policy == "preserve_first_verified_replacement_evidence_required"
        assert policy.recovery_policy == "recover_by_read_only_wallet_capture_or_verified_export"
        assert policy.mutation_authority == "dry_run_then_verified_evidence_then_explicit_operator_confirmation"
        assert policy.export_policy == "export_encrypted_or_operator_requested_redacted_evidence_only"
        assert policy.import_policy == "import_only_verified_external_evidence_or_encrypted_restore"
        assert policy.calculation_confidence_impact == "degrades_aeat_remote_wallet_authority"

    def test_namespace_policy_disables_import_and_quarantine_for_unknown_namespaces(self) -> None:
        policy = build_repair_namespace_policy("aeat.unregistered.future_feature")

        assert policy.owner_domain == "unknown"
        assert policy.bucket_scope == "unregistered_preserve_first"
        assert policy.repair_policy == "preserve_until_owner_repository_policy_registered"
        assert policy.mutation_authority == "disabled_until_namespace_owner_contract_is_registered"
        assert policy.import_policy == "import_disabled_until_namespace_policy_registered"
        assert policy.calculation_confidence_impact == "no_direct_calculation_confidence_impact"

    def test_namespace_policy_preserves_receipts_for_statutory_retention(self) -> None:
        policy = build_repair_namespace_policy("aeat.domain.justificante.metadata")

        assert policy.owner_domain == "submission_and_receipt"
        assert policy.repair_policy == "preserve_only_no_quarantine_without_engineer_override_adr"
        assert policy.recovery_policy == "recover_by_verified_aeat_sede_receipt_or_csv_copy"
        assert policy.mutation_authority == "disabled_without_engineer_override_adr"
        assert policy.retention_legal_note == "tax_supporting_evidence_preserve_for_statutory_retention_window"

    def test_namespace_classifier_covers_active_repository_namespaces(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        expected_namespaces = _active_secure_object_namespaces()
        with EphemeralMasterKeyProvider(key=_KEY_A):
            repo = SecureObjectRepository(engine=engine)
            for index, namespace in enumerate(expected_namespaces):
                repo.save(
                    namespace=namespace,
                    object_key=f"repair-namespace:{index}",
                    classification=SensitivityClass.OPERATIONAL,
                    schema_version=1,
                    written_at=datetime.now(UTC),
                    payload=f"repair-namespace-payload:{index}".encode(),
                )
            discovered_namespaces = repo.list_namespaces()
            unclassified = tuple(
                namespace
                for namespace in discovered_namespaces
                if classify_repair_namespace(namespace).role == "unknown_secure_object_namespace"
            )
            unknown_key_context = tuple(
                namespace
                for namespace in discovered_namespaces
                if build_repair_list_report(
                    namespace=namespace,
                    active_bucket_id="active-bucket",
                    repository=repo,
                ).rows[0].object_key_kind
                == "unknown_hmac_digest"
            )

        assert discovered_namespaces == expected_namespaces
        assert unclassified == ()
        assert unknown_key_context == ()


class TestBuildAttributionReport:
    def test_attribution_groups_unreadable_rows_by_safe_metadata(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 2, tag="stale")
            _save_rows(
                engine,
                "aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
                1,
                tag="stale",
            )
        with EphemeralMasterKeyProvider(key=_KEY_B):
            _save_rows(engine, "aeat.workflow", 3, tag="current")
            report = build_repair_integrity_attribution_report(
                active_bucket_id="bucket-a",
                repository=SecureObjectRepository(engine=engine),
            )

        namespaces = {namespace.namespace: namespace for namespace in report.namespaces}
        workflow = namespaces["aeat.workflow"]
        wallet = namespaces["aeat.outbound.aeat.sede.iva_compensation_wallet.observations"]

        assert report.unreadable_total == 3
        assert workflow.unreadable_count == 2
        assert workflow.owner_semantics == "singleton"
        assert workflow.first_written_at is not None
        assert workflow.last_written_at is not None
        assert workflow.first_written_at <= workflow.last_written_at
        assert tuple(group.model_dump() for group in workflow.classification_groups) == (
            {"classification": "operational", "unreadable_count": 2},
        )
        assert wallet.unreadable_count == 1
        assert wallet.owner_semantics == "multirow"
        assert wallet.namespace_classification.participates_in_iva_compensation_history is True
        assert {row.context_bucket_id for row in wallet.unreadable_rows} == {"active_profile"}
        assert {row.object_key_kind for row in wallet.unreadable_rows} == {"iva_wallet_observation"}
        assert {row.likely_origin for row in workflow.unreadable_rows} == {
            "repository_keychain_or_restore_mismatch"
        }
        assert {row.origin_confidence for row in workflow.unreadable_rows} == {
            "classified_repository_namespace"
        }
        assert {row.likely_origin for row in wallet.unreadable_rows} == {
            "tax_evidence_keychain_or_restore_mismatch"
        }
        assert {row.origin_confidence for row in wallet.unreadable_rows} == {
            "classified_tax_evidence_namespace"
        }
        serialized = report.model_dump_json()
        assert "repair-integrity-payload" not in serialized
        assert "bucket-a" not in serialized

    def test_attribution_distinguishes_test_and_routing_origins(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "test.ephemeral.secure_objects", 1, tag="test")
            _save_rows(engine, "aeat.unregistered.feature", 1, tag="unknown")
            _save_rows(engine, "aeat.domain.transactions.bucket", 1, tag="missing-context")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            report = build_repair_integrity_attribution_report(
                repository=SecureObjectRepository(engine=engine),
            )

        rows = {
            namespace.namespace: namespace.unreadable_rows[0]
            for namespace in report.namespaces
        }
        assert rows["test.ephemeral.secure_objects"].likely_origin == (
            "test_contamination_or_test_namespace_residue"
        )
        assert rows["test.ephemeral.secure_objects"].origin_confidence == "namespace_test_marker"
        assert rows["aeat.unregistered.feature"].likely_origin == (
            "storage_routing_fault_or_unregistered_repository"
        )
        assert rows["aeat.unregistered.feature"].origin_confidence == "unclassified_namespace"
        assert rows["aeat.domain.transactions.bucket"].likely_origin == "missing_active_profile_context"
        assert rows["aeat.domain.transactions.bucket"].origin_confidence == "bucket_key_without_active_context"

    def test_attribution_report_is_empty_when_all_rows_are_readable(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 1, tag="readable")
            report = build_repair_integrity_attribution_report(
                repository=SecureObjectRepository(engine=engine),
            )

        assert report.unreadable_total == 0
        assert report.namespaces == ()

    def test_attribution_output_does_not_disclose_payload_or_private_natural_key(
        self, tmp_path: Path
    ) -> None:
        engine = _engine_on(tmp_path)
        sensitive_tax_id = "12345678Z"
        sensitive_period = "2026Q1"
        sensitive_expediente = "EXPEDIENTE-PRIVATE-42"
        sensitive_payload = b"wallet-balance=999999; taxpayer=12345678Z; expediente=EXPEDIENTE-PRIVATE-42"
        with EphemeralMasterKeyProvider(key=_KEY_A):
            SecureObjectRepository(engine=engine).save(
                namespace="aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
                object_key=f"wallet:{sensitive_tax_id}:{sensitive_period}:{sensitive_expediente}",
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=sensitive_payload,
            )
        with EphemeralMasterKeyProvider(key=_KEY_B):
            report = build_repair_integrity_attribution_report(
                active_bucket_id="bucket-a",
                repository=SecureObjectRepository(engine=engine),
            )

        serialized = report.model_dump_json()
        assert report.unreadable_total == 1
        assert "wallet-balance" not in serialized
        assert sensitive_tax_id not in serialized
        assert sensitive_period not in serialized
        assert sensitive_expediente not in serialized
        assert "bucket-a" not in serialized
        assert "iva_wallet_observation" in serialized
        assert "active_profile" in serialized


class TestBuildEnvelopeValidationReport:
    def test_envelope_contracts_cover_active_repository_namespaces(self) -> None:
        from aeat.application.repair_integrity import _repair_envelope_contracts

        expected_namespaces = _active_secure_object_namespaces()
        contracts = _repair_envelope_contracts()

        missing_contracts = tuple(
            namespace for namespace in expected_namespaces if namespace.casefold() not in contracts
        )

        assert len(contracts) >= len(expected_namespaces)
        assert missing_contracts == ()

    def test_envelope_validation_passes_for_readable_owner_contract(self, tmp_path: Path) -> None:
        from aeat.domain.usage_ratios._model import UsageRatioProfile
        from aeat.domain.usage_ratios._service import _USAGE_RATIO_NAMESPACE, _USAGE_RATIO_VERSION

        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            envelope = Envelope[UsageRatioProfile](
                schema_version=_USAGE_RATIO_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=UsageRatioProfile(),
            )
            SecureObjectRepository(engine=engine).save(
                namespace=_USAGE_RATIO_NAMESPACE,
                object_key="usage-ratios:bucket-a",
                classification=SensitivityClass.FINANCIAL,
                schema_version=_USAGE_RATIO_VERSION,
                written_at=envelope.written_at,
                payload=envelope.model_dump_json().encode("utf-8"),
            )
            report = build_repair_envelope_validation_report(
                repository=SecureObjectRepository(engine=engine),
            )

        assert report.payload_disclosure == "metadata_only"
        assert report.rows_total == 1
        assert report.readable_rows_checked == 1
        assert report.unreadable_rows_skipped == 0
        assert report.findings == ()
        assert report.check.status == "ok"

    def test_envelope_validation_reports_readable_contract_drift(self, tmp_path: Path) -> None:
        from aeat.domain.usage_ratios._model import UsageRatioProfile
        from aeat.domain.usage_ratios._service import _USAGE_RATIO_NAMESPACE, _USAGE_RATIO_VERSION

        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            repo = SecureObjectRepository(engine=engine)
            valid_envelope = Envelope[UsageRatioProfile](
                schema_version=_USAGE_RATIO_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=UsageRatioProfile(),
            )
            future_envelope = Envelope[UsageRatioProfile](
                schema_version=_USAGE_RATIO_VERSION + 1,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.FINANCIAL,
                payload=UsageRatioProfile(),
            )
            foreign_class_envelope = Envelope[UsageRatioProfile](
                schema_version=_USAGE_RATIO_VERSION,
                written_at=datetime.now(UTC),
                classification=SensitivityClass.AUDIT,
                payload=UsageRatioProfile(),
            )
            repo.save(
                namespace=_USAGE_RATIO_NAMESPACE,
                object_key="row-class-drift",
                classification=SensitivityClass.OPERATIONAL,
                schema_version=_USAGE_RATIO_VERSION,
                written_at=valid_envelope.written_at,
                payload=valid_envelope.model_dump_json().encode("utf-8"),
            )
            repo.save(
                namespace=_USAGE_RATIO_NAMESPACE,
                object_key="inner-schema-drift",
                classification=SensitivityClass.FINANCIAL,
                schema_version=_USAGE_RATIO_VERSION,
                written_at=future_envelope.written_at,
                payload=future_envelope.model_dump_json().encode("utf-8"),
            )
            repo.save(
                namespace=_USAGE_RATIO_NAMESPACE,
                object_key="inner-class-drift",
                classification=SensitivityClass.FINANCIAL,
                schema_version=_USAGE_RATIO_VERSION,
                written_at=foreign_class_envelope.written_at,
                payload=foreign_class_envelope.model_dump_json().encode("utf-8"),
            )
            report = build_repair_envelope_validation_report(repository=repo)

        finding_types = {finding.finding_type for finding in report.findings}
        assert report.rows_total == 3
        assert report.readable_rows_checked == 3
        assert report.finding_count == 3
        assert finding_types == {
            "payload_envelope_classification_mismatch",
            "payload_envelope_schema_version_unsupported",
            "row_classification_mismatch",
        }
        assert {finding.namespace for finding in report.findings} == {_USAGE_RATIO_NAMESPACE}
        assert all(finding.object_key_digest for finding in report.findings)
        serialized = report.model_dump_json()
        assert "row-class-drift" not in serialized
        assert "inner-schema-drift" not in serialized
        assert "inner-class-drift" not in serialized
        assert report.check.status == "fail"
        assert report.check.next_action == "aeat config repair integrity attribution"

    def test_envelope_validation_skips_unreadable_rows_for_attribution(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 1, tag="stale")
        with EphemeralMasterKeyProvider(key=_KEY_B):
            report = build_repair_envelope_validation_report(
                repository=SecureObjectRepository(engine=engine),
            )

        assert report.rows_total == 1
        assert report.readable_rows_checked == 0
        assert report.unreadable_rows_skipped == 1
        assert report.findings == ()
        assert report.check.status == "warn"
        assert report.check.next_action == "aeat config repair integrity attribution"


class TestRepairRemediationDecisionRepository:
    def test_repair_decision_roundtrips_through_encrypted_store(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        decided_at = datetime(2026, 5, 22, 12, 30, tzinfo=UTC)
        decision_id = repair_remediation_decision_id(
            target_namespace="aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
            target_object_key_digest="ab12",
            outcome="export_required",
            decided_at=decided_at,
            reason="wallet observation replacement required before remediation",
            likely_origin="tax_evidence_keychain_or_restore_mismatch",
            replacement_evidence_requirements=(
                "export_encrypted_profile_backup_before_any_change",
                "capture_fresh_read_only_aeat_wallet_observation_or_export_existing_observation",
            ),
            verified_replacement_evidence_refs=("operator-confirmed-wallet-export",),
        )
        decision = RepairRemediationDecision(
            decision_id=decision_id,
            target_namespace="aeat.outbound.aeat.sede.iva_compensation_wallet.observations",
            target_object_key_digest="ab12",
            outcome="export_required",
            decided_at=decided_at,
            reason="wallet observation replacement required before remediation",
            likely_origin="tax_evidence_keychain_or_restore_mismatch",
            replacement_evidence_requirements=(
                "export_encrypted_profile_backup_before_any_change",
                "capture_fresh_read_only_aeat_wallet_observation_or_export_existing_observation",
            ),
            verified_replacement_evidence_refs=("operator-confirmed-wallet-export",),
        )

        with EphemeralMasterKeyProvider(key=_KEY_A):
            repository = RepairRemediationDecisionRepository(
                objects=SecureObjectRepository(engine=engine),
            )
            repository.save_decision(decision)
            loaded = repository.load_decision(decision_id)
            listed = repository.list_decisions()
            raw_rows = tuple(SecureObjectRepository(engine=engine).iter_all_records_raw())

        assert loaded == decision
        assert listed == (decision,)
        assert len(raw_rows) == 1
        assert raw_rows[0].namespace == RepairRemediationDecisionRepository.namespace
        assert b"wallet observation replacement required" not in raw_rows[0].payload
        assert b"operator-confirmed-wallet-export" not in raw_rows[0].payload

    def test_repair_decision_repository_lists_by_decision_time(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        later = _repair_decision_for_test(
            namespace="aeat.domain.transactions.bucket",
            digest="ab12",
            outcome="preserve",
            decided_at=datetime(2026, 5, 22, 12, 30, tzinfo=UTC),
            reason="preserve ledger evidence while attribution is reviewed",
        )
        earlier = _repair_decision_for_test(
            namespace="aeat.domain.invoices",
            digest="cd34",
            outcome="rebuild",
            decided_at=datetime(2026, 5, 22, 12, 0, tzinfo=UTC),
            reason="invoice catalogue can be rebuilt from verified source files",
        )

        with EphemeralMasterKeyProvider(key=_KEY_A):
            repository = RepairRemediationDecisionRepository(
                objects=SecureObjectRepository(engine=engine),
            )
            repository.save_decision(later)
            repository.save_decision(earlier)

            assert repository.list_decisions() == (earlier, later)

    def test_repair_decision_records_do_not_authorize_mutation(self) -> None:
        decided_at = datetime(2026, 5, 22, 12, 30, tzinfo=UTC)
        decision_id = repair_remediation_decision_id(
            target_namespace="aeat.domain.justificante.metadata",
            target_object_key_digest="ab12",
            outcome="quarantine",
            decided_at=decided_at,
            reason="receipt has replacement evidence requirements but no mutation authority",
            likely_origin="tax_evidence_keychain_or_restore_mismatch",
            replacement_evidence_requirements=(
                "verify_filed_declaration_or_receipt_copy_from_aeat_sede",
            ),
        )

        with pytest.raises(ValidationError):
            RepairRemediationDecision(
                decision_id=decision_id,
                target_namespace="aeat.domain.justificante.metadata",
                target_object_key_digest="ab12",
                outcome="quarantine",
                decided_at=decided_at,
                reason="receipt has replacement evidence requirements but no mutation authority",
                likely_origin="tax_evidence_keychain_or_restore_mismatch",
                replacement_evidence_requirements=(
                    "verify_filed_declaration_or_receipt_copy_from_aeat_sede",
                ),
                mutation_authorized=True,
            )

    def test_non_preserve_decision_requires_replacement_evidence_requirements(self) -> None:
        decided_at = datetime(2026, 5, 22, 12, 30, tzinfo=UTC)
        decision_id = repair_remediation_decision_id(
            target_namespace="aeat.domain.invoices",
            target_object_key_digest="ab12",
            outcome="rebuild",
            decided_at=decided_at,
            reason="invoice catalogue rebuild requires evidence requirements",
            likely_origin="repository_keychain_or_restore_mismatch",
            replacement_evidence_requirements=(),
        )

        with pytest.raises(ValidationError, match="replacement evidence requirements"):
            RepairRemediationDecision(
                decision_id=decision_id,
                target_namespace="aeat.domain.invoices",
                target_object_key_digest="ab12",
                outcome="rebuild",
                decided_at=decided_at,
                reason="invoice catalogue rebuild requires evidence requirements",
                likely_origin="repository_keychain_or_restore_mismatch",
                replacement_evidence_requirements=(),
            )

    def test_repair_decision_rejects_id_that_does_not_match_content(self) -> None:
        decided_at = datetime(2026, 5, 22, 12, 30, tzinfo=UTC)
        decision_id = repair_remediation_decision_id(
            target_namespace="aeat.domain.invoices",
            target_object_key_digest="ab12",
            outcome="rebuild",
            decided_at=decided_at,
            reason="invoice catalogue can be rebuilt from verified source files",
            likely_origin="repository_keychain_or_restore_mismatch",
            replacement_evidence_requirements=(
                "export_encrypted_profile_backup_before_any_change",
                "verify_replacement_evidence_for_affected_domain",
            ),
            verified_replacement_evidence_refs=("invoice-export-2026-05-22",),
        )

        with pytest.raises(ValidationError, match="decision_id"):
            RepairRemediationDecision(
                decision_id=decision_id,
                target_namespace="aeat.domain.invoices",
                target_object_key_digest="ab12",
                outcome="rebuild",
                decided_at=decided_at,
                reason="invoice catalogue can be rebuilt from verified source files",
                likely_origin="repository_keychain_or_restore_mismatch",
                replacement_evidence_requirements=(
                    "export_encrypted_profile_backup_before_any_change",
                    "capture_fresh_read_only_aeat_invoice_evidence",
                ),
                verified_replacement_evidence_refs=("invoice-export-2026-05-22",),
            )

    def test_quarantine_and_rebuild_decisions_require_verified_replacement_evidence_refs(self) -> None:
        decided_at = datetime(2026, 5, 22, 12, 30, tzinfo=UTC)
        decision_id = repair_remediation_decision_id(
            target_namespace="aeat.domain.invoices",
            target_object_key_digest="ab12",
            outcome="rebuild",
            decided_at=decided_at,
            reason="invoice catalogue can be rebuilt from verified source files",
            likely_origin="repository_keychain_or_restore_mismatch",
            replacement_evidence_requirements=(
                "export_encrypted_profile_backup_before_any_change",
                "verify_replacement_evidence_for_affected_domain",
            ),
        )

        with pytest.raises(ValidationError, match="verified replacement evidence"):
            RepairRemediationDecision(
                decision_id=decision_id,
                target_namespace="aeat.domain.invoices",
                target_object_key_digest="ab12",
                outcome="rebuild",
                decided_at=decided_at,
                reason="invoice catalogue can be rebuilt from verified source files",
                likely_origin="repository_keychain_or_restore_mismatch",
                replacement_evidence_requirements=(
                    "export_encrypted_profile_backup_before_any_change",
                    "verify_replacement_evidence_for_affected_domain",
                ),
            )

    def test_quarantine_decision_rejects_protected_submission_receipt_namespace(self) -> None:
        decided_at = datetime(2026, 5, 22, 12, 30, tzinfo=UTC)
        evidence_requirements = (
            "export_encrypted_profile_backup_before_any_change",
            "record_operator_preserve_first_decision",
            "verify_filed_declaration_or_receipt_copy_from_aeat_sede",
            "record_csv_or_justificante_reference_before_quarantine",
            "disable_destructive_quarantine_without_engineer_override_adr",
        )
        evidence_refs = ("aeat-sede-justificante-export-2026-05-22",)
        decision_id = repair_remediation_decision_id(
            target_namespace="aeat.domain.justificante.metadata",
            target_object_key_digest="ab12",
            outcome="quarantine",
            decided_at=decided_at,
            reason="receipt has verified replacement evidence but quarantine remains disabled",
            likely_origin="tax_evidence_keychain_or_restore_mismatch",
            replacement_evidence_requirements=evidence_requirements,
            verified_replacement_evidence_refs=evidence_refs,
        )

        with pytest.raises(ValidationError, match="quarantine is disabled"):
            RepairRemediationDecision(
                decision_id=decision_id,
                target_namespace="aeat.domain.justificante.metadata",
                target_object_key_digest="ab12",
                outcome="quarantine",
                decided_at=decided_at,
                reason="receipt has verified replacement evidence but quarantine remains disabled",
                likely_origin="tax_evidence_keychain_or_restore_mismatch",
                replacement_evidence_requirements=evidence_requirements,
                verified_replacement_evidence_refs=evidence_refs,
            )


def _repair_decision_for_test(
    *,
    namespace: str,
    digest: str,
    outcome: str,
    decided_at: datetime,
    reason: str,
) -> RepairRemediationDecision:
    decision_id = repair_remediation_decision_id(
        target_namespace=namespace,
        target_object_key_digest=digest,
        outcome=outcome,  # type: ignore[arg-type]
        decided_at=decided_at,
        reason=reason,
        likely_origin="repository_keychain_or_restore_mismatch",
        replacement_evidence_requirements=(
            "export_encrypted_profile_backup_before_any_change",
            "verify_replacement_evidence_for_affected_domain",
        ),
        verified_replacement_evidence_refs=(
            ("verified-replacement-evidence-for-test",)
            if outcome in {"quarantine", "rebuild"}
            else ()
        ),
    )
    return RepairRemediationDecision(
        decision_id=decision_id,
        target_namespace=namespace,
        target_object_key_digest=digest,
        outcome=outcome,  # type: ignore[arg-type]
        decided_at=decided_at,
        reason=reason,
        likely_origin="repository_keychain_or_restore_mismatch",
        replacement_evidence_requirements=(
            "export_encrypted_profile_backup_before_any_change",
            "verify_replacement_evidence_for_affected_domain",
        ),
        verified_replacement_evidence_refs=(
            ("verified-replacement-evidence-for-test",)
            if outcome in {"quarantine", "rebuild"}
            else ()
        ),
    )


class TestReportInvariants:
    def test_integrity_report_is_frozen(self, tmp_path: Path) -> None:
        engine = _engine_on(tmp_path)
        with EphemeralMasterKeyProvider(key=_KEY_A):
            _save_rows(engine, "aeat.workflow", 1, tag="a")
            report = build_repair_integrity_report(
                repository=SecureObjectRepository(engine=engine),
            )
        with pytest.raises(ValidationError):
            report.readable_total = 99  # type: ignore[misc]

    def test_unreadable_attribution_report_is_metadata_only(self) -> None:
        row = RepairUnreadableRowAttribution(
            namespace="aeat.workflow",
            object_key_digest="abcd",
            row_id=1,
            classification="operational",
            schema_version=1,
            written_at=datetime(2026, 5, 22, tzinfo=UTC),
            reason="decryption failed",
            owner_semantics="singleton",
            likely_origin="repository_keychain_or_restore_mismatch",
            origin_confidence="classified_repository_namespace",
            context_bucket_id="active_profile",
            object_key_kind="singleton_workflow_state",
            object_key_hint="state",
            context_confidence="repository_contract_unverified_digest",
            context_note="Repository contract stores the workflow state singleton.",
        )
        namespace = RepairUnreadableNamespaceAttribution(
            namespace="aeat.workflow",
            namespace_classification=classify_repair_namespace("aeat.workflow"),
            owner_semantics="singleton",
            classification_groups=_classification_group(),
            unreadable_rows=(row,),
            unreadable_count=1,
            first_written_at=row.written_at,
            last_written_at=row.written_at,
        )
        report = RepairIntegrityAttributionReport(namespaces=(namespace,), unreadable_total=1)

        serialized = report.model_dump_json()
        row_dump = row.model_dump()
        assert report.payload_disclosure == "metadata_only"
        assert "payload" not in row_dump
        assert "repair-integrity-payload" not in serialized
        assert "transaction-catalogue-payload" not in serialized
        assert "taxpayer" not in serialized.casefold()
        assert "abcd" in serialized

    def test_unreadable_namespace_attribution_rejects_count_mismatch(self) -> None:
        row = RepairUnreadableRowAttribution(
            namespace="aeat.workflow",
            object_key_digest="abcd",
            owner_semantics="singleton",
            likely_origin="repository_keychain_or_restore_mismatch",
            origin_confidence="classified_repository_namespace",
        )

        with pytest.raises(ValidationError, match="unreadable_count"):
            RepairUnreadableNamespaceAttribution(
                namespace="aeat.workflow",
                namespace_classification=classify_repair_namespace("aeat.workflow"),
                owner_semantics="singleton",
                classification_groups=_classification_group(),
                unreadable_rows=(row,),
                unreadable_count=2,
            )

    def test_unreadable_row_attribution_rejects_raw_context_identifiers(self) -> None:
        with pytest.raises(ValidationError, match="context_bucket_id"):
            RepairUnreadableRowAttribution(
                namespace="aeat.workflow",
                object_key_digest="abcd",
                owner_semantics="singleton",
                likely_origin="repository_keychain_or_restore_mismatch",
                origin_confidence="classified_repository_namespace",
                context_bucket_id="bucket-a",
            )

        with pytest.raises(ValidationError, match="object_key_hint"):
            RepairUnreadableRowAttribution(
                namespace="aeat.domain.transactions.bucket",
                object_key_digest="abcd",
                owner_semantics="singleton",
                likely_origin="repository_keychain_or_restore_mismatch",
                origin_confidence="classified_repository_namespace",
                object_key_hint="transaction-catalogue:bucket-a",
            )

        with pytest.raises(ValidationError, match="digest identifiers"):
            RepairUnreadableRowAttribution(
                namespace="aeat.workflow",
                object_key_digest="abcd",
                owner_semantics="singleton",
                likely_origin="repository_keychain_or_restore_mismatch",
                origin_confidence="classified_repository_namespace",
                reason="decrypt failed for 4f8c2b0a9d6e4f1c8a7b5d3e2c1a0f99",
            )

    def test_unreadable_namespace_attribution_rejects_inconsistent_timestamp_range(self) -> None:
        row = RepairUnreadableRowAttribution(
            namespace="aeat.workflow",
            object_key_digest="abcd",
            owner_semantics="singleton",
            likely_origin="repository_keychain_or_restore_mismatch",
            origin_confidence="classified_repository_namespace",
            written_at=datetime(2026, 5, 22, tzinfo=UTC),
        )

        with pytest.raises(ValidationError, match="first_written_at"):
            RepairUnreadableNamespaceAttribution(
                namespace="aeat.workflow",
                namespace_classification=classify_repair_namespace("aeat.workflow"),
                owner_semantics="singleton",
                classification_groups=_classification_group(),
                unreadable_rows=(row,),
                unreadable_count=1,
                first_written_at=datetime(2026, 5, 23, tzinfo=UTC),
                last_written_at=datetime(2026, 5, 22, tzinfo=UTC),
            )

        with pytest.raises(ValidationError, match="must not follow"):
            RepairUnreadableNamespaceAttribution(
                namespace="aeat.workflow",
                namespace_classification=classify_repair_namespace("aeat.workflow"),
                owner_semantics="singleton",
                classification_groups=_classification_group(),
                unreadable_rows=(row,),
                unreadable_count=1,
                first_written_at=datetime(2026, 5, 20, tzinfo=UTC),
                last_written_at=datetime(2026, 5, 21, tzinfo=UTC),
            )

    def test_unreadable_report_rejects_total_mismatch(self) -> None:
        row = RepairUnreadableRowAttribution(
            namespace="aeat.workflow",
            object_key_digest="abcd",
            owner_semantics="singleton",
            likely_origin="repository_keychain_or_restore_mismatch",
            origin_confidence="classified_repository_namespace",
        )
        namespace = RepairUnreadableNamespaceAttribution(
            namespace="aeat.workflow",
            namespace_classification=classify_repair_namespace("aeat.workflow"),
            owner_semantics="singleton",
            classification_groups=_classification_group(),
            unreadable_rows=(row,),
            unreadable_count=1,
        )

        with pytest.raises(ValidationError, match="unreadable_total"):
            RepairIntegrityAttributionReport(namespaces=(namespace,), unreadable_total=2)

    def test_envelope_validation_report_rejects_count_mismatch(self) -> None:
        finding = RepairEnvelopeValidationFinding(
            namespace="aeat.workflow",
            object_key_digest="abcd",
            finding_type="row_classification_mismatch",
            contract_kind="typed_envelope",
            expected_classification="financial",
            actual_classification="operational",
            max_supported_version=1,
            actual_schema_version=1,
            reason="Stored row classification differs from the owning repository contract.",
        )
        check = DiagnosticCheck(
            name="secure_objects.envelope_contracts",
            status="fail",
            summary="contract drift",
            next_action="aeat config repair integrity attribution",
        )

        with pytest.raises(ValidationError, match="finding_count"):
            RepairEnvelopeValidationReport(
                rows_total=1,
                readable_rows_checked=1,
                unreadable_rows_skipped=0,
                findings=(finding,),
                finding_count=2,
                check=check,
            )
