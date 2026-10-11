"""Installation acts are a closed table whose every message crosses the runtime's two doors whole."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from cadrumo.application.config_reset_models import ConfigResetOperation, ConfigResetPointerSnapshot
from cadrumo.application.diagnostic_models import (
    ConfigRepairReport,
    DiagnosticCheck,
    DiagnosticStatus,
    SecureObjectIntegrityReport,
    diagnostic_action_verdict,
    ensure_models_rebuilt,
)
from cadrumo.application.diagnostics_ports import DiagnosticSecureObjectNamespace
from cadrumo.application.operations.error_detail import build_operation_error_detail
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActFacts,
    RuntimeArchiveImportPrepareReply,
    RuntimeArchiveImportReply,
    RuntimeArchiveImportRequest,
    RuntimeArchiveInspectReply,
    RuntimeArchiveInspectRequest,
    RuntimeInstallationActRequest,
    RuntimeInstallationCompleted,
    RuntimeInstallationFailed,
    RuntimeInstallationPassphrase,
    RuntimeInstallationRefused,
    RuntimeInstallationReplyTransfer,
    RuntimeInstallationSecretDelivery,
    RuntimeInstallationSecretReceipt,
    RuntimeProfileHealth,
    RuntimeProfileListReply,
    RuntimeProfilePointerRepair,
    RuntimeProfileRecordStatus,
    RuntimeRecoveryEnrollReply,
    RuntimeRepairLogsReply,
    RuntimeRepairLogsRequest,
    RuntimeRepairProfileReply,
    RuntimeRepairProfileRequest,
    RuntimeRepairReportProjection,
    RuntimeRepairReportReply,
    RuntimeReportVerification,
    RuntimeReportVerificationCheck,
    RuntimeReportVerifyDocumentReply,
    RuntimeResetResumeReply,
    RuntimeResetResumeRequest,
    RuntimeResetStartReply,
    RuntimeResetStartRequest,
    RuntimeResetStatusReply,
    RuntimeReviewPackageManifest,
    RuntimeReviewPackageVerification,
    RuntimeReviewPackageVerifyReceiptReply,
    RuntimeReviewPackageVerifyReply,
    RuntimeReviewPackageVerifySignatureReply,
    RuntimeStorageCheckReply,
    RuntimeStorageInitReply,
    RuntimeStorageInventoryReply,
    RuntimeStorageInventoryRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
    installation_act_of,
    installation_request_facts,
)
from cadrumo.application.runtime.profile_access import RuntimeReply, RuntimeRequest
from cadrumo.application.storage_management.models import (
    StorageAreaDisposition,
    StorageAreaInventoryReport,
    StorageAreaInventoryRow,
    StorageInitReport,
    StorageOccupancy,
    StorageReclaimReport,
    StorageTreeCheckReport,
    StorageTreeIssue,
    StorageTreeIssueKind,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.capsule_archive import ProfileCapsuleArchiveInspection
from cadrumo.application.user_profile.capsule_restore import ProfileRestoreOutcome
from cadrumo.application.user_profile.profile_summary import ProfileSummary, ProfileSummaryInventory
from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryEnrollmentOutcome
from cadrumo.core.bucket_pointer import BucketPointer
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.period import Period
from cadrumo.core.profile_discovery import ProfileSummaryOutcome
from cadrumo.core.profile_publication import ProfilePublicationKind
from cadrumo.core.storage_taxonomy import StorageArea

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = "6f1f6a0e-6f3c-4a55-9d1e-3b0a7c1d2e4f"
_DIGEST = "ab" * 32
_INSTANT = datetime(2026, 3, 4, 5, 6, 7, tzinfo=UTC)
_HOST_FILE = str(Path(__file__).resolve())
_HOST_DIRECTORY = Path(__file__).resolve().parent
_PROOF = "synthetic-installation-passphrase"
_ACT_REQUESTS: TypeAdapter[RuntimeInstallationActRequest] = TypeAdapter(RuntimeInstallationActRequest)


def _reply[ReplyT: BaseModel](reply_type: type[ReplyT], **members: object) -> ReplyT:
    """Build one reply on fresh coordinates, as the door builds a handler's reply."""
    return reply_type.model_validate(
        {"request_id": uuid4(), "runtime_boot_id": uuid4(), "connection_id": uuid4(), **members}
    )


def _health(status: str) -> RuntimeProfileHealth:
    verdict = diagnostic_action_verdict(
        condition_id="profile.pointer.dangling",
        evidence_id="profile.pointer",
        values={"registered_bucket": False},
        action_id="operator.config.repair.profile",
    )
    return RuntimeProfileHealth(
        active_profile=_PROFILE,
        active_profile_label="Synthetic profile",
        source="pointer",
        status=status,
        repairable_by_clearing_pointer=True,
        precondition_verdict_json=verdict.model_dump_json(),
    )


def _repair_report() -> RuntimeRepairReportProjection:
    ensure_models_rebuilt()
    verdict = diagnostic_action_verdict(
        condition_id="logging.directory.missing",
        evidence_id="logging.directory",
        values={"present": False},
        action_id="operator.storage.init",
    )
    return RuntimeRepairReportProjection.from_report(
        ConfigRepairReport(
            overall=DiagnosticStatus.WARN,
            package_name="cadrumo",
            package_version="0.0.0",
            python_version="3.13.0",
            log_file="synthetic.log",
            setup=None,
            secure_objects=SecureObjectIntegrityReport(
                namespaces=(DiagnosticSecureObjectNamespace(namespace="ledger", readable=3, unreadable=1),),
                readable_total=3,
                unreadable_total=1,
            ),
            checks=(
                DiagnosticCheck(name="environment.python", status=DiagnosticStatus.OK, summary="3.13.0"),
                DiagnosticCheck(
                    name="logging.directory",
                    status=DiagnosticStatus.WARN,
                    summary="missing",
                    precondition_verdict=verdict,
                ),
            ),
        )
    )


def _completed_replies() -> dict[InstallationAct, RuntimeInstallationCompleted]:
    """One synthetic completed reply for every act, built from the services' own models."""
    reset = ConfigResetOperation(
        operation_id=_DIGEST,
        started_at=_INSTANT,
        updated_at=_INSTANT,
        pointer_snapshot=ConfigResetPointerSnapshot(
            record=BucketPointer(selection="absent", transition_revision=0, schema_version=2)
        ),
        targets=(),
    )
    manifest = RuntimeReviewPackageManifest(
        package_info_version=1,
        bucket_id=_PROFILE,
        work_unit_id=_DIGEST,
        calculation_revision_id=_DIGEST,
        registry_revision_id="2026-y-siguientes",
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_state="BORRADOR",
        has_ledger_evidence=True,
        built_at=_INSTANT,
        built_by="operator",
    )
    return {
        InstallationAct.STORAGE_INVENTORY: _reply(
            RuntimeStorageInventoryReply,
            report=StorageAreaInventoryReport(
                storage_root=_HOST_DIRECTORY,
                rows=(
                    StorageAreaInventoryRow(
                        area=StorageArea.CACHE,
                        occupancy=StorageOccupancy.POPULATED,
                        disposition=StorageAreaDisposition.RECLAIMABLE,
                        reclaimable=True,
                        resolved_paths=2,
                        entry_count=5,
                        footprint_bytes=4096,
                    ),
                ),
            ),
        ),
        InstallationAct.STORAGE_CHECK: _reply(
            RuntimeStorageCheckReply,
            report=StorageTreeCheckReport(
                storage_root=_HOST_DIRECTORY,
                healthy=False,
                root_mode_enforced=False,
                checked_locations=7,
                issues=(
                    StorageTreeIssue(
                        kind=StorageTreeIssueKind.MISSING_DIRECTORY,
                        path=_HOST_DIRECTORY / "logs",
                        area=StorageArea.LOGS,
                        detail="declared directory has not been materialised",
                    ),
                ),
            ),
        ),
        InstallationAct.STORAGE_INIT: _reply(
            RuntimeStorageInitReply,
            report=StorageInitReport(storage_root=_HOST_DIRECTORY, created=(_HOST_DIRECTORY / "cache",)),
        ),
        InstallationAct.STORAGE_RECLAIM: _reply(
            RuntimeStorageReclaimReply,
            report=StorageReclaimReport(
                area=StorageArea.CACHE,
                target_count=2,
                removed_entries=4,
                retained_entries=1,
                retained_paths=(Path(_HOST_FILE),),
            ),
        ),
        InstallationAct.PROFILE_LIST: _reply(
            RuntimeProfileListReply,
            inventory=ProfileSummaryInventory(
                outcome=ProfileSummaryOutcome.RECOGNIZED,
                summaries=(
                    ProfileSummary(
                        profile_id=_PROFILE,
                        label="Synthetic profile",
                        label_revision=1,
                        published_at=_INSTANT,
                        publication_kind=ProfilePublicationKind.RESTORE,
                    ),
                ),
            ),
            active_profile_id=_PROFILE,
        ),
        InstallationAct.RESET_START: _reply(RuntimeResetStartReply, operation=reset),
        InstallationAct.RESET_STATUS: _reply(RuntimeResetStatusReply, operation=None),
        InstallationAct.RESET_RESUME: _reply(RuntimeResetResumeReply, operation=reset),
        InstallationAct.ARCHIVE_INSPECT: _reply(
            RuntimeArchiveInspectReply,
            inspection=ProfileCapsuleArchiveInspection(
                product="cadrumo",
                bucket_id=_PROFILE,
                archive_schema_version=1,
                created_at=_INSTANT,
                manifest_digest=_DIGEST,
            ),
        ),
        InstallationAct.ARCHIVE_IMPORT_PREPARE: _reply(RuntimeArchiveImportPrepareReply, source_digest=_DIGEST),
        InstallationAct.ARCHIVE_IMPORT: _reply(
            RuntimeArchiveImportReply,
            outcome=ProfileRestoreOutcome(
                profile_id=_PROFILE, label="Synthetic profile", authority="password", recovery_enrolled=False
            ),
        ),
        InstallationAct.RECOVERY_ENROLL: _reply(
            RuntimeRecoveryEnrollReply,
            outcome=ProfileRecoveryEnrollmentOutcome(profile_id=_PROFILE, enrolled=True, changed=True),
        ),
        InstallationAct.REPAIR_REPORT: _reply(RuntimeRepairReportReply, report=_repair_report()),
        InstallationAct.REPAIR_LOGS: _reply(
            RuntimeRepairLogsReply, path=_HOST_FILE, lines=("first synthetic line", "second synthetic line")
        ),
        InstallationAct.REPAIR_PROFILE: _reply(
            RuntimeRepairProfileReply,
            pointer_repair=RuntimeProfilePointerRepair(
                dry_run=False,
                cleared_pointer=True,
                before=_health("dangling_pointer"),
                after=RuntimeProfileHealth(active_profile=None, source="none", status="none"),
            ),
        ),
        InstallationAct.REVIEW_PACKAGE_VERIFY: _reply(
            RuntimeReviewPackageVerifyReply,
            verification=RuntimeReviewPackageVerification(manifest=manifest, mismatched=("fichero.txt",)),
        ),
        InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE: _reply(
            RuntimeReviewPackageVerifySignatureReply, is_valid=True, signer_public_key_hex=_DIGEST
        ),
        InstallationAct.REVIEW_PACKAGE_VERIFY_RECEIPT: _reply(
            RuntimeReviewPackageVerifyReceiptReply,
            is_valid=False,
            operator_public_key_hex=_DIGEST,
            counter_signer_public_key_hex=_DIGEST,
        ),
        InstallationAct.REPORT_VERIFY_DOCUMENT: _reply(
            RuntimeReportVerifyDocumentReply,
            verification=RuntimeReportVerification(
                outcome="refused",
                checks=(
                    RuntimeReportVerificationCheck(
                        check="statement_signature", layer="document", reason="signature_invalid", detail="statement"
                    ),
                ),
                store_checked=False,
                calculation_revision_id=_DIGEST,
            ),
        ),
    }


def _requests() -> dict[InstallationAct, BaseModel]:
    """One request for every act, as any of the three frontends would send it."""
    members: dict[InstallationAct, dict[str, object]] = {
        InstallationAct.STORAGE_RECLAIM: {"area": StorageArea.CACHE, "confirmed": True},
        InstallationAct.RESET_START: {"confirmed": True, "retention_override_reason": "synthetic reason"},
        InstallationAct.RESET_STATUS: {"operation_id": _DIGEST},
        InstallationAct.RESET_RESUME: {"operation_id": _DIGEST, "confirmed": True},
        InstallationAct.ARCHIVE_INSPECT: {"path": _HOST_FILE},
        InstallationAct.ARCHIVE_IMPORT_PREPARE: {"label": "Synthetic profile", "path": _HOST_FILE},
        InstallationAct.ARCHIVE_IMPORT: {"label": "Synthetic profile", "path": _HOST_FILE, "source_digest": _DIGEST},
        InstallationAct.RECOVERY_ENROLL: {"profile_id": UUID(_PROFILE)},
        InstallationAct.REPAIR_LOGS: {"lines": 40},
        InstallationAct.REPAIR_PROFILE: {"profile": "Synthetic profile", "clear_active": True, "confirmed": True},
        InstallationAct.REVIEW_PACKAGE_VERIFY: {"package": _HOST_FILE},
        InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE: {
            "package": _HOST_FILE,
            "signature": _HOST_FILE,
            "public_key": _DIGEST,
        },
        InstallationAct.REVIEW_PACKAGE_VERIFY_RECEIPT: {
            "package": _HOST_FILE,
            "receipt": _HOST_FILE,
            "operator_public_key": _DIGEST,
            "counter_signer_public_key": _DIGEST,
        },
        InstallationAct.REPORT_VERIFY_DOCUMENT: {"path": _HOST_FILE, "trusted_key": _DIGEST},
    }
    return {
        act: contract.request.model_validate(
            {"request_id": uuid4(), "frontend": OperationFrontendProjection.MCP, **members.get(act, {})}
        )
        for act, contract in INSTALLATION_ACT_CONTRACTS.items()
    }


def _over_the_wire(document: BaseModel) -> bytes:
    return canonical_json_bytes(document.model_dump(mode="json"))


def test_the_table_declares_every_act_once_with_its_own_models() -> None:
    assert set(INSTALLATION_ACT_CONTRACTS) == set(InstallationAct)
    requests = [contract.request for contract in INSTALLATION_ACT_CONTRACTS.values()]
    replies = [contract.reply for contract in INSTALLATION_ACT_CONTRACTS.values()]
    assert len(set(requests)) == len(requests) == len(set(replies))
    for act, contract in INSTALLATION_ACT_CONTRACTS.items():
        assert contract.act is act
        assert contract.request.model_fields["action"].default == act.value
        assert contract.reply.model_fields["kind"].default == f"{act.value}_reply"
        assert {"request_id", "frontend"} <= set(contract.request.model_fields)
        assert {"request_id", "runtime_boot_id", "connection_id"} <= set(contract.reply.model_fields)
        assert "session_id" not in contract.request.model_fields


def test_each_act_declares_whether_it_changes_records_and_reaches_the_network() -> None:
    changes = {act for act, contract in INSTALLATION_ACT_CONTRACTS.items() if contract.facts.changes_records}
    assert changes == {
        InstallationAct.STORAGE_INIT,
        InstallationAct.STORAGE_RECLAIM,
        InstallationAct.RESET_START,
        InstallationAct.RESET_RESUME,
        InstallationAct.ARCHIVE_IMPORT,
        InstallationAct.RECOVERY_ENROLL,
        InstallationAct.REPAIR_PROFILE,
    }
    assert not any(contract.facts.reaches_network for contract in INSTALLATION_ACT_CONTRACTS.values())
    assert {act for act, contract in INSTALLATION_ACT_CONTRACTS.items() if contract.takes_secret} == {
        InstallationAct.ARCHIVE_IMPORT,
        InstallationAct.RECOVERY_ENROLL,
    }
    assert {act for act, contract in INSTALLATION_ACT_CONTRACTS.items() if contract.delivers_secret} == {
        InstallationAct.RECOVERY_ENROLL
    }


@pytest.mark.parametrize("act", list(InstallationAct))
def test_every_request_crosses_the_request_door_whole(act: InstallationAct) -> None:
    request = _requests()[act]

    received = RuntimeRequest.model_validate_json(_over_the_wire(request)).root

    assert received == request
    assert type(received) is INSTALLATION_ACT_CONTRACTS[act].request
    assert installation_act_of(_ACT_REQUESTS.validate_json(_over_the_wire(request))) is act


@pytest.mark.parametrize("act", list(InstallationAct))
def test_every_completed_reply_crosses_the_reply_door_whole(act: InstallationAct) -> None:
    reply = _completed_replies()[act]

    received = RuntimeReply.model_validate_json(_over_the_wire(reply)).root

    assert type(received) is INSTALLATION_ACT_CONTRACTS[act].reply
    assert received == reply


def test_the_shared_outcomes_cross_the_reply_door_whole() -> None:
    detail = build_operation_error_detail(RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE))
    assert detail is not None
    outcomes: tuple[BaseModel, ...] = (
        _reply(RuntimeInstallationRefused, act=InstallationAct.STORAGE_RECLAIM, detail=detail),
        _reply(RuntimeInstallationFailed, act=InstallationAct.REPAIR_REPORT),
        _reply(RuntimeInstallationSecretDelivery, act=InstallationAct.RECOVERY_ENROLL, delivery_id=uuid4()),
        _reply(RuntimeInstallationReplyTransfer, byte_count=70_000, payload_digest=_DIGEST),
    )

    for outcome in outcomes:
        assert RuntimeReply.model_validate_json(_over_the_wire(outcome)).root == outcome


def test_a_repair_check_restores_the_verdict_its_report_carried() -> None:
    report = _repair_report()

    restored = RuntimeRepairReportProjection.model_validate_json(_over_the_wire(report))

    warned = next(check for check in restored.checks if check.name == "logging.directory")
    verdict = warned.precondition_verdict()
    assert verdict is not None
    assert verdict.failed_condition_id == "logging.directory.missing"
    assert next(check for check in restored.checks if check.name == "environment.python").precondition_verdict() is None
    assert (restored.secure_objects_readable_total, restored.secure_objects_unreadable_total) == (3, 1)
    with pytest.raises(ValidationError):
        type(warned).model_validate({**warned.model_dump(), "precondition_verdict_json": "{}"})


def test_an_unconfirmed_request_reads_and_a_confirmed_one_changes_records() -> None:
    request_id, frontend = uuid4(), OperationFrontendProjection.CLI
    reads = InstallationActFacts(changes_records=False, reaches_network=False)
    changes = InstallationActFacts(changes_records=True, reaches_network=False)

    def facts(request: BaseModel) -> InstallationActFacts:
        return installation_request_facts(_ACT_REQUESTS.validate_json(_over_the_wire(request)))

    assert facts(RuntimeStorageInventoryRequest(request_id=request_id, frontend=frontend)) == reads
    assert (
        facts(RuntimeStorageReclaimRequest(request_id=request_id, frontend=frontend, area=StorageArea.CACHE)) == reads
    )
    assert (
        facts(
            RuntimeStorageReclaimRequest(
                request_id=request_id, frontend=frontend, area=StorageArea.CACHE, confirmed=True
            )
        )
        == changes
    )
    assert facts(RuntimeResetStartRequest(request_id=request_id, frontend=frontend)) == reads
    assert facts(RuntimeResetStartRequest(request_id=request_id, frontend=frontend, confirmed=True)) == changes
    assert facts(RuntimeResetResumeRequest(request_id=request_id, frontend=frontend)) == reads
    assert facts(RuntimeResetResumeRequest(request_id=request_id, frontend=frontend, confirmed=True)) == changes
    assert facts(RuntimeRepairProfileRequest(request_id=request_id, frontend=frontend, profile="Synthetic")) == reads
    assert facts(RuntimeRepairProfileRequest(request_id=request_id, frontend=frontend, clear_active=True)) == reads
    assert (
        facts(RuntimeRepairProfileRequest(request_id=request_id, frontend=frontend, clear_active=True, confirmed=True))
        == changes
    )
    assert (
        facts(
            RuntimeArchiveImportRequest(
                request_id=request_id, frontend=frontend, label="Synthetic", path=_HOST_FILE, source_digest=_DIGEST
            )
        )
        == changes
    )


@pytest.mark.parametrize("path", ["relative/archive.cadrumo", "archive.cadrumo", ""])
def test_a_request_names_a_host_file_only_by_its_absolute_path(path: str) -> None:
    with pytest.raises(ValidationError) as refused:
        RuntimeArchiveInspectRequest(request_id=uuid4(), frontend=OperationFrontendProjection.TUI, path=path)

    assert "archive.cadrumo" not in str(refused.value)


def test_a_request_refuses_a_member_its_act_does_not_declare() -> None:
    document = json.loads(_over_the_wire(_requests()[InstallationAct.STORAGE_INVENTORY]))

    with pytest.raises(ValidationError):
        RuntimeRequest.model_validate_json(canonical_json_bytes({**document, "profile_id": _PROFILE}))
    with pytest.raises(ValidationError):
        RuntimeRepairLogsRequest(request_id=uuid4(), frontend=OperationFrontendProjection.CLI, lines=-1)


def test_a_profile_repair_reply_carries_exactly_one_branch() -> None:
    record = RuntimeProfileRecordStatus(
        profile_id=_PROFILE,
        display_name="Synthetic profile",
        registered_bucket=True,
        profile_record_present=False,
        status="missing_profile_record",
    )
    repair = RuntimeProfilePointerRepair(dry_run=True, cleared_pointer=False, before=_health("dangling_pointer"))

    assert _reply(RuntimeRepairProfileReply, record_status=record).pointer_repair is None
    with pytest.raises(ValidationError):
        _reply(RuntimeRepairProfileReply)
    with pytest.raises(ValidationError):
        _reply(RuntimeRepairProfileReply, pointer_repair=repair, record_status=record)
    with pytest.raises(ValidationError):
        RuntimeProfileRecordStatus(
            profile_id=_PROFILE,
            display_name="Synthetic profile",
            registered_bucket=True,
            profile_record_present=True,
            status="missing_profile_record",
        )


def test_secret_documents_never_show_what_they_carry() -> None:
    passphrase = RuntimeInstallationPassphrase.model_validate_json(canonical_json_bytes({"passphrase": _PROOF}))

    assert _PROOF not in repr(passphrase)
    assert _PROOF not in passphrase.model_dump_json()
    with pytest.raises(ValidationError) as refused:
        RuntimeInstallationPassphrase.model_validate_json(canonical_json_bytes({"passphrase": _PROOF, "other": 1}))
    assert _PROOF not in str(refused.value)
    with pytest.raises(ValidationError):
        RuntimeInstallationSecretReceipt(delivery_id=uuid4(), outcome="held", code=AutomationCustodyCode.MISSING)
    with pytest.raises(ValidationError):
        RuntimeInstallationSecretReceipt(delivery_id=uuid4(), outcome="refused")
