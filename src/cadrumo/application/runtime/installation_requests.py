"""Sessionless installation acts: runtime requests that name no profile session.

An installation act is work the runtime does with no profile open, across
every profile, or before a profile exists: reading the storage tree, listing
profiles, resetting the installation, importing a profile archive, verifying a
file the operator holds. Each act is one request and one reply on the verified
native connection. An act never carries a credential in a document: a
passphrase arrives in one secret frame after the runtime says it is ready, and
a recovery code leaves in one secret frame and is read back before the act
settles.

Every frontend sends the same request and receives the same reply. The
``frontend`` member records where a request came from and decides nothing.

Beside each act this module declares two facts, whether it changes records and
whether it reaches the network, in :data:`INSTALLATION_ACT_CONTRACTS`. A
narrowed surface refuses an act by those facts, never by its name.

Reply members whose owning model would load the tax registry or the profile
view are carried as typed projections defined here, so a process that only
connects to the runtime imports none of them. A projection holds a closed
vocabulary owned elsewhere as its stable token.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, Field, NonNegativeInt, SecretStr, StringConstraints, model_validator

from ...core.errors.hierarchy import InternalInvariantError
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import Period
from ...core.requirement import RequirementValue
from ...core.storage_taxonomy import StorageArea
from ..config_reset_models import ConfigResetOperation
from ..diagnostic_models import DiagnosticAudienceValue, DiagnosticStatusValue
from ..diagnostics_ports import DiagnosticSecureObjectNamespace
from ..operations.error_detail import OperationErrorDetailV1
from ..operations.registry import OperationFrontendProjection
from ..operator_actions.models import PreconditionVerdict
from ..storage_management.models import (
    StorageAreaInventoryReport,
    StorageInitReport,
    StorageReclaimReport,
    StorageTreeCheckReport,
)
from ..user_profile.automation_custody_port import AutomationCustodyCode
from ..user_profile.capsule_archive import ProfileCapsuleArchiveInspection
from ..user_profile.capsule_restore import ProfileRestoreOutcome
from ..user_profile.profile_summary import ProfileSummaryInventory
from ..user_profile.recovery_custody import ProfileRecoveryEnrollmentOutcome

if TYPE_CHECKING:
    from ..diagnostic_models import ConfigRepairReport, DiagnosticCheck

#: Largest reply one act may return across its bounded transfer.
INSTALLATION_REPLY_MAX_BYTES: Final[int] = 4_194_304

#: Most log lines one ``repair_logs`` act returns.
INSTALLATION_LOG_TAIL_MAX_LINES: Final[int] = 5_000

#: How long a client may take to hold a delivered secret before reading it back.
#: A person copies a recovery code down inside this bound.
INSTALLATION_SECRET_HANDOVER_SECONDS: Final[float] = 300.0


class InstallationAct(StrEnum):
    """Every sessionless act the runtime's installation door serves."""

    STORAGE_INVENTORY = "storage_inventory"
    STORAGE_CHECK = "storage_check"
    STORAGE_INIT = "storage_init"
    STORAGE_RECLAIM = "storage_reclaim"
    PROFILE_LIST = "profile_list"
    RESET_START = "reset_start"
    RESET_STATUS = "reset_status"
    RESET_RESUME = "reset_resume"
    ARCHIVE_INSPECT = "archive_inspect"
    ARCHIVE_IMPORT_PREPARE = "archive_import_prepare"
    ARCHIVE_IMPORT = "archive_import"
    RECOVERY_ENROLL = "recovery_enroll"
    REPAIR_REPORT = "repair_report"
    REPAIR_LOGS = "repair_logs"
    REPAIR_PROFILE = "repair_profile"
    REVIEW_PACKAGE_VERIFY = "review_package_verify"
    REVIEW_PACKAGE_VERIFY_SIGNATURE = "review_package_verify_signature"
    REVIEW_PACKAGE_VERIFY_RECEIPT = "review_package_verify_receipt"
    REPORT_VERIFY_DOCUMENT = "report_verify_document"


def _absolute_host_path(value: str) -> str:
    """Accept a path only in a form that names one host file from any working directory."""
    if not (PureWindowsPath(value).is_absolute() or PurePosixPath(value).is_absolute()):
        raise ValueError("an installation act names a host file by its absolute path")
    return value


type InstallationHostPath = Annotated[
    str, StringConstraints(min_length=1, max_length=4096), AfterValidator(_absolute_host_path)
]
"""An absolute path on the host. The runtime's working directory is not the caller's."""

type _OperatorText = Annotated[str, StringConstraints(min_length=1, max_length=512)]
type _KeyText = Annotated[str, StringConstraints(min_length=1, max_length=256)]
type _VocabularyToken = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")]
"""The stable token of a closed vocabulary whose owning module this contract does not import."""


class _InstallationRequest(BaseModel):
    """Coordinates every installation request carries; neither is a credential."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_id: UUID
    frontend: OperationFrontendProjection


class _InstallationReply(BaseModel):
    """Verified native reply coordinates; none is a bearer."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class RuntimeInstallationCompleted(_InstallationReply):
    """The reply of an act that ran to its end; each act adds its own members."""


# -- storage ---------------------------------------------------------------------


class RuntimeStorageInventoryRequest(_InstallationRequest):
    """Ask where the declared storage areas are and what they hold."""

    action: Literal["storage_inventory"] = "storage_inventory"


class RuntimeStorageInventoryReply(RuntimeInstallationCompleted):
    """One aggregate row for each operator-facing storage area."""

    kind: Literal["storage_inventory_reply"] = "storage_inventory_reply"
    report: StorageAreaInventoryReport


class RuntimeStorageCheckRequest(_InstallationRequest):
    """Compare the tree on disk with its declaration, repairing nothing."""

    action: Literal["storage_check"] = "storage_check"


class RuntimeStorageCheckReply(RuntimeInstallationCompleted):
    """The read-only verdict on the materialised tree."""

    kind: Literal["storage_check_reply"] = "storage_check_reply"
    report: StorageTreeCheckReport


class RuntimeStorageInitRequest(_InstallationRequest):
    """Create every declared directory, preserving whatever exists."""

    action: Literal["storage_init"] = "storage_init"


class RuntimeStorageInitReply(RuntimeInstallationCompleted):
    """The directories this act created and how many were already there."""

    kind: Literal["storage_init_reply"] = "storage_init_reply"
    report: StorageInitReport


class RuntimeStorageReclaimRequest(_InstallationRequest):
    """Delete one area's regenerable contents after its derived preflight.

    Without ``confirmed`` the act deletes nothing and is refused with the
    count of entries a confirmed act would remove.
    """

    action: Literal["storage_reclaim"] = "storage_reclaim"
    area: StorageArea
    confirmed: bool = False


class RuntimeStorageReclaimReply(RuntimeInstallationCompleted):
    """What one confirmed reclaim removed and what it had to leave."""

    kind: Literal["storage_reclaim_reply"] = "storage_reclaim_reply"
    report: StorageReclaimReport


# -- profiles --------------------------------------------------------------------


class RuntimeProfileListRequest(_InstallationRequest):
    """List committed profiles without unlocking any of them."""

    action: Literal["profile_list"] = "profile_list"


class RuntimeProfileListReply(RuntimeInstallationCompleted):
    """One listing observation joined to one read of the active-profile pointer.

    A degraded or concurrent observation carries no summaries and says so in
    its outcome: an empty listing never stands for a store with no profiles.
    """

    kind: Literal["profile_list_reply"] = "profile_list_reply"
    inventory: ProfileSummaryInventory
    active_profile_id: Annotated[str, StringConstraints(min_length=1, max_length=256)] | None = None


class RuntimeArchiveInspectRequest(_InstallationRequest):
    """Read an archive's plaintext header without decrypting anything."""

    action: Literal["archive_inspect"] = "archive_inspect"
    path: InstallationHostPath


class RuntimeArchiveInspectReply(RuntimeInstallationCompleted):
    """Exactly what the archive discloses to anyone holding the file."""

    kind: Literal["archive_inspect_reply"] = "archive_inspect_reply"
    inspection: ProfileCapsuleArchiveInspection


class RuntimeArchiveImportPrepareRequest(_InstallationRequest):
    """Read a capsule directory or sealed archive before any credential is asked for."""

    action: Literal["archive_import_prepare"] = "archive_import_prepare"
    label: _OperatorText
    path: InstallationHostPath


class RuntimeArchiveImportPrepareReply(RuntimeInstallationCompleted):
    """The digest of the source that was read; it authorizes nothing."""

    kind: Literal["archive_import_prepare_reply"] = "archive_import_prepare_reply"
    source_digest: ContentDigest


class RuntimeArchiveImportRequest(_InstallationRequest):
    """Republish the prepared source under its own passphrase.

    The passphrase follows in one secret frame. A source whose bytes no longer
    match ``source_digest`` is refused before that frame is asked for.
    """

    action: Literal["archive_import"] = "archive_import"
    label: _OperatorText
    path: InstallationHostPath
    source_digest: ContentDigest


class RuntimeArchiveImportReply(RuntimeInstallationCompleted):
    """The republished profile; a restore never carries recovery across."""

    kind: Literal["archive_import_reply"] = "archive_import_reply"
    outcome: ProfileRestoreOutcome


class RuntimeRecoveryEnrollRequest(_InstallationRequest):
    """Mint a recovery code for one committed profile.

    The current passphrase follows in one secret frame. The code is delivered
    in one secret frame and must be read back before the wrapper is installed.
    """

    action: Literal["recovery_enroll"] = "recovery_enroll"
    profile_id: UUID


class RuntimeRecoveryEnrollReply(RuntimeInstallationCompleted):
    """The non-secret result of one completed enrolment."""

    kind: Literal["recovery_enroll_reply"] = "recovery_enroll_reply"
    outcome: ProfileRecoveryEnrollmentOutcome


# -- reset -----------------------------------------------------------------------


class RuntimeResetStartRequest(_InstallationRequest):
    """Start one durable all-profile reset. Without ``confirmed`` it is refused."""

    action: Literal["reset_start"] = "reset_start"
    confirmed: bool = False
    acknowledge_retention_override: bool = False
    retention_override_reason: _OperatorText | None = None


class RuntimeResetStartReply(RuntimeInstallationCompleted):
    """The reset journal as this act left it."""

    kind: Literal["reset_start_reply"] = "reset_start_reply"
    operation: ConfigResetOperation


class RuntimeResetStatusRequest(_InstallationRequest):
    """Read one reset journal, or the latest, without resuming it."""

    action: Literal["reset_status"] = "reset_status"
    operation_id: Hex64Str | None = None


class RuntimeResetStatusReply(RuntimeInstallationCompleted):
    """The journal read, or ``None`` when no reset was ever started."""

    kind: Literal["reset_status_reply"] = "reset_status_reply"
    operation: ConfigResetOperation | None = None


class RuntimeResetResumeRequest(_InstallationRequest):
    """Roll one incomplete reset forward. Without an id it names the latest."""

    action: Literal["reset_resume"] = "reset_resume"
    operation_id: Hex64Str | None = None
    confirmed: bool = False
    acknowledge_retention_override: bool = False
    retention_override_reason: _OperatorText | None = None


class RuntimeResetResumeReply(RuntimeInstallationCompleted):
    """The reset journal as this act left it."""

    kind: Literal["reset_resume_reply"] = "reset_resume_reply"
    operation: ConfigResetOperation


# -- repair ----------------------------------------------------------------------


class RuntimeRepairSetup(BaseModel):
    """The active profile's readiness summary inside a repair report."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    active_profile: str | None
    profile_ready: bool
    identity_ready: bool
    enrolment_ready: bool
    missing_required: tuple[str, ...]
    missing_enrolment: tuple[str, ...]
    profile_present_keys: NonNegativeInt
    profile_total_keys: NonNegativeInt
    auth_provider: str
    login_ready: bool


class RuntimeRepairFinding(BaseModel):
    """One named sub-finding inside a repair check."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    summary: str
    detail: str | None = None
    requirement: RequirementValue | None = None


class RuntimeRepairCheck(BaseModel):
    """One repair check with its recovery verdict.

    The verdict travels as its canonical JSON because its evidence serializes
    differently from how it validates. The text is validated as the verdict on
    both sides.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    name: str
    status: DiagnosticStatusValue
    summary: str
    detail: str | None = None
    precondition_verdict_json: Annotated[str, StringConstraints(min_length=2)] | None = None
    audience: DiagnosticAudienceValue
    findings: tuple[RuntimeRepairFinding, ...] = ()

    @model_validator(mode="after")
    def _verdict_is_a_verdict(self) -> Self:
        self.precondition_verdict()
        return self

    def precondition_verdict(self) -> PreconditionVerdict | None:
        """Restore the typed verdict the check carried, or ``None``."""
        if self.precondition_verdict_json is None:
            return None
        return PreconditionVerdict.model_validate_json(self.precondition_verdict_json)

    @classmethod
    def from_check(cls, check: DiagnosticCheck) -> Self:
        """Project one application diagnostic check, keeping its verdict whole."""
        verdict = check.precondition_verdict
        return cls(
            name=check.name,
            status=check.status,
            summary=check.summary,
            detail=check.detail,
            precondition_verdict_json=None if verdict is None else verdict.model_dump_json(),
            audience=check.audience,
            findings=tuple(
                RuntimeRepairFinding(summary=finding.summary, detail=finding.detail, requirement=finding.requirement)
                for finding in check.findings
            ),
        )


class RuntimeRepairReportProjection(BaseModel):
    """Every member of the composite repair report, in a form that needs no profile view."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    overall: DiagnosticStatusValue
    package_name: str
    package_version: str
    python_version: str
    log_file: str
    setup: RuntimeRepairSetup | None
    secure_object_namespaces: tuple[DiagnosticSecureObjectNamespace, ...]
    secure_objects_readable_total: NonNegativeInt
    secure_objects_unreadable_total: NonNegativeInt
    checks: tuple[RuntimeRepairCheck, ...]

    @classmethod
    def from_report(cls, report: ConfigRepairReport) -> Self:
        """Project the application's repair report without dropping a check or a count."""
        setup = report.setup
        return cls(
            overall=report.overall,
            package_name=report.package_name,
            package_version=report.package_version,
            python_version=report.python_version,
            log_file=report.log_file,
            setup=(
                None
                if setup is None
                else RuntimeRepairSetup(
                    active_profile=setup.active_profile,
                    profile_ready=setup.profile_ready,
                    identity_ready=setup.identity_ready,
                    enrolment_ready=setup.enrolment_ready,
                    missing_required=setup.missing_required,
                    missing_enrolment=setup.missing_enrolment,
                    profile_present_keys=setup.profile_present_keys,
                    profile_total_keys=setup.profile_total_keys,
                    auth_provider=setup.auth_provider,
                    login_ready=setup.login_ready,
                )
            ),
            secure_object_namespaces=report.secure_objects.namespaces,
            secure_objects_readable_total=report.secure_objects.readable_total,
            secure_objects_unreadable_total=report.secure_objects.unreadable_total,
            checks=tuple(RuntimeRepairCheck.from_check(check) for check in report.checks),
        )


class RuntimeRepairReportRequest(_InstallationRequest):
    """Diagnose local configuration, profile, sign-in and log state."""

    action: Literal["repair_report"] = "repair_report"


class RuntimeRepairReportReply(RuntimeInstallationCompleted):
    """The composite repair report."""

    kind: Literal["repair_report_reply"] = "repair_report_reply"
    report: RuntimeRepairReportProjection


class RuntimeRepairLogsRequest(_InstallationRequest):
    """Read the configured log file's path and its most recent lines."""

    action: Literal["repair_logs"] = "repair_logs"
    lines: Annotated[int, Field(ge=0, le=INSTALLATION_LOG_TAIL_MAX_LINES)] = 20


class RuntimeRepairLogsReply(RuntimeInstallationCompleted):
    """A bounded tail of the log file; empty when the file does not exist."""

    kind: Literal["repair_logs_reply"] = "repair_logs_reply"
    path: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    lines: Annotated[tuple[str, ...], Field(max_length=INSTALLATION_LOG_TAIL_MAX_LINES)]


class RuntimeProfileHealth(BaseModel):
    """The redacted active-profile health verdict, with the label its assessment resolved."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    active_profile: str | None
    active_profile_label: str | None = None
    source: Literal["none", "env_override", "pointer"]
    status: _VocabularyToken
    registered_bucket: bool = False
    profile_record_present: bool = False
    profile_record_error: str = ""
    profile_present_keys: NonNegativeInt = 0
    profile_total_keys: NonNegativeInt = 0
    missing_required: tuple[str, ...] = ()
    repairable_by_clearing_pointer: bool = False
    precondition_verdict_json: Annotated[str, StringConstraints(min_length=2)] | None = None

    @model_validator(mode="after")
    def _verdict_is_a_verdict(self) -> Self:
        self.precondition_verdict()
        return self

    def precondition_verdict(self) -> PreconditionVerdict | None:
        """Restore the typed verdict the health assessment carried, or ``None``."""
        if self.precondition_verdict_json is None:
            return None
        return PreconditionVerdict.model_validate_json(self.precondition_verdict_json)


class RuntimeProfilePointerRepair(BaseModel):
    """The pointer-repair branch: health before, and after when the pointer was cleared."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    dry_run: bool
    cleared_pointer: bool
    before: RuntimeProfileHealth
    after: RuntimeProfileHealth | None = None


class RuntimeProfileRecordStatus(BaseModel):
    """The inspection branch: whether one named profile's record can be read.

    ``status`` is absent when the record was read. ``setup_state`` is the
    record's own token and is present only then.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: BucketId
    display_name: str
    registered_bucket: bool
    profile_record_present: bool
    setup_state: _VocabularyToken | None = None
    status: Literal["missing_profile_record", "profile_record_unreadable"] | None = None
    error: str | None = None
    precondition_verdict_json: Annotated[str, StringConstraints(min_length=2)] | None = None

    @model_validator(mode="after")
    def _closed_shape(self) -> Self:
        if self.profile_record_present != (self.status is None):
            raise ValueError("a profile record status names a fault exactly when the record was not read")
        if self.setup_state is not None and not self.profile_record_present:
            raise ValueError("a setup state belongs to a record that was read")
        self.precondition_verdict()
        return self

    def precondition_verdict(self) -> PreconditionVerdict | None:
        """Restore the typed verdict the inspection carried, or ``None``."""
        if self.precondition_verdict_json is None:
            return None
        return PreconditionVerdict.model_validate_json(self.precondition_verdict_json)


class RuntimeRepairProfileRequest(_InstallationRequest):
    """Inspect one profile's record, or repair a degraded active-profile pointer.

    Naming a profile without ``clear_active`` inspects that profile. Otherwise
    the act assesses the active pointer, and clears it only with both
    ``clear_active`` and ``confirmed``.
    """

    action: Literal["repair_profile"] = "repair_profile"
    profile: _OperatorText | None = None
    clear_active: bool = False
    confirmed: bool = False


class RuntimeRepairProfileReply(RuntimeInstallationCompleted):
    """Exactly one branch: the pointer repair, or the named profile's record status."""

    kind: Literal["repair_profile_reply"] = "repair_profile_reply"
    pointer_repair: RuntimeProfilePointerRepair | None = None
    record_status: RuntimeProfileRecordStatus | None = None

    @model_validator(mode="after")
    def _one_branch(self) -> Self:
        if (self.pointer_repair is None) == (self.record_status is None):
            raise ValueError("a profile repair reply carries exactly one branch")
        return self


# -- files the operator holds ----------------------------------------------------


class RuntimeReviewPackageManifest(BaseModel):
    """The review-domain identity a package's descriptor carries."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    package_info_version: Annotated[int, Field(ge=1)]
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    registry_revision_id: Annotated[str, StringConstraints(min_length=1, max_length=256)]
    modelo: Annotated[str, StringConstraints(min_length=1, max_length=8)]
    filing_year: FilingYear
    period: Period
    revision_state: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    has_ledger_evidence: bool
    built_at: datetime
    built_by: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    notes: Annotated[str, StringConstraints(max_length=2000)] = ""


class RuntimeReviewPackageVerification(BaseModel):
    """An integrity verdict on a package's members; it says nothing about who built it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    manifest: RuntimeReviewPackageManifest
    missing: tuple[str, ...] = ()
    unexpected: tuple[str, ...] = ()
    mismatched: tuple[str, ...] = ()

    @property
    def is_clean(self) -> bool:
        """Whether every archived member matches its checksum record."""
        return not (self.missing or self.unexpected or self.mismatched)


class RuntimeReviewPackageVerifyRequest(_InstallationRequest):
    """Verify a review package's checksum manifest and read its descriptor."""

    action: Literal["review_package_verify"] = "review_package_verify"
    package: InstallationHostPath


class RuntimeReviewPackageVerifyReply(RuntimeInstallationCompleted):
    """The integrity verdict and the descriptor recovered from the package."""

    kind: Literal["review_package_verify_reply"] = "review_package_verify_reply"
    verification: RuntimeReviewPackageVerification


class RuntimeReviewPackageVerifySignatureRequest(_InstallationRequest):
    """Verify a package's signature envelope against a key the caller trusts."""

    action: Literal["review_package_verify_signature"] = "review_package_verify_signature"
    package: InstallationHostPath
    signature: InstallationHostPath
    public_key: _KeyText


class RuntimeReviewPackageVerifySignatureReply(RuntimeInstallationCompleted):
    """Whether the signature holds for the package's current bytes and the named key."""

    kind: Literal["review_package_verify_signature_reply"] = "review_package_verify_signature_reply"
    is_valid: bool
    signer_public_key_hex: _KeyText


class RuntimeReviewPackageVerifyReceiptRequest(_InstallationRequest):
    """Verify both signature layers of a counter-signed receipt."""

    action: Literal["review_package_verify_receipt"] = "review_package_verify_receipt"
    package: InstallationHostPath
    receipt: InstallationHostPath
    operator_public_key: _KeyText
    counter_signer_public_key: _KeyText


class RuntimeReviewPackageVerifyReceiptReply(RuntimeInstallationCompleted):
    """Whether both layers hold for the package's current bytes and the named keys."""

    kind: Literal["review_package_verify_receipt_reply"] = "review_package_verify_receipt_reply"
    is_valid: bool
    operator_public_key_hex: _KeyText
    counter_signer_public_key_hex: _KeyText


class RuntimeReportVerificationCheck(BaseModel):
    """One check that ran on a calculation summary, and what it found."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    check: _VocabularyToken
    layer: _VocabularyToken
    reason: _VocabularyToken | None = None
    detail: str | None = None


class RuntimeReportVerification(BaseModel):
    """The verdict on one calculation summary and every check behind it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: _VocabularyToken
    checks: tuple[RuntimeReportVerificationCheck, ...]
    store_checked: bool
    signing_key_fingerprint: Hex64Str | None = None
    calculation_revision_id: Hex64Str | None = None
    report_sha256: Hex64Str | None = None
    statement_sha256: Hex64Str | None = None


class RuntimeReportVerifyDocumentRequest(_InstallationRequest):
    """Verify a calculation summary file by its own bytes, tracing it to no profile."""

    action: Literal["report_verify_document"] = "report_verify_document"
    path: InstallationHostPath
    trusted_key: _KeyText | None = None


class RuntimeReportVerifyDocumentReply(RuntimeInstallationCompleted):
    """The document-layer verdict; ``store_checked`` is always false for this act."""

    kind: Literal["report_verify_document_reply"] = "report_verify_document_reply"
    verification: RuntimeReportVerification


# -- outcomes every act shares ---------------------------------------------------


class RuntimeInstallationRefused(_InstallationReply):
    """An act its handler stopped with a registered error or a record that failed its contract.

    The detail is the one a refused operation records: the registered code,
    its catalogue key, the scrubbed context and any typed verdict, and never
    an exception's free text or a value.
    """

    kind: Literal["installation_refused"] = "installation_refused"
    act: InstallationAct
    detail: OperationErrorDetailV1


class RuntimeInstallationFailed(_InstallationReply):
    """An act that stopped on a fault with no public facts to give.

    The fault is in the runtime's diagnostic log. An act that changes records
    may have changed some before it stopped: this reply never says it did not.
    """

    kind: Literal["installation_failed"] = "installation_failed"
    act: InstallationAct


class RuntimeInstallationSecretDelivery(_InstallationReply):
    """Announce exactly one following secret frame the client must hold and read back."""

    kind: Literal["installation_secret_delivery"] = "installation_secret_delivery"
    act: InstallationAct
    delivery_id: UUID


class RuntimeInstallationReplyTransfer(_InstallationReply):
    """Announce a reply too large for one frame, correlated before its chunks are read."""

    kind: Literal["installation_reply_transfer"] = "installation_reply_transfer"
    byte_count: Annotated[int, Field(ge=2, le=INSTALLATION_REPLY_MAX_BYTES)]
    payload_digest: ContentDigest


class RuntimeInstallationPassphrase(BaseModel):
    """Secret-frame-only payload of an act that proves a profile passphrase."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    passphrase: SecretStr


class RuntimeInstallationSecretReceipt(BaseModel):
    """The client's answer to one delivery; a held secret follows in one secret frame."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    kind: Literal["installation_secret_receipt"] = "installation_secret_receipt"
    delivery_id: UUID
    outcome: Literal["held", "refused"]
    code: AutomationCustodyCode | None = None

    @model_validator(mode="after")
    def _refusal_code_only_for_refusal(self) -> Self:
        if (self.outcome == "refused") != (self.code is not None):
            raise ValueError("a delivery refusal and its code must agree")
        return self


type RuntimeInstallationActRequest = Annotated[
    RuntimeStorageInventoryRequest
    | RuntimeStorageCheckRequest
    | RuntimeStorageInitRequest
    | RuntimeStorageReclaimRequest
    | RuntimeProfileListRequest
    | RuntimeResetStartRequest
    | RuntimeResetStatusRequest
    | RuntimeResetResumeRequest
    | RuntimeArchiveInspectRequest
    | RuntimeArchiveImportPrepareRequest
    | RuntimeArchiveImportRequest
    | RuntimeRecoveryEnrollRequest
    | RuntimeRepairReportRequest
    | RuntimeRepairLogsRequest
    | RuntimeRepairProfileRequest
    | RuntimeReviewPackageVerifyRequest
    | RuntimeReviewPackageVerifySignatureRequest
    | RuntimeReviewPackageVerifyReceiptRequest
    | RuntimeReportVerifyDocumentRequest,
    Field(discriminator="action"),
]
"""Closed installation request union; no member names a session."""

type RuntimeInstallationActReply = (
    RuntimeStorageInventoryReply
    | RuntimeStorageCheckReply
    | RuntimeStorageInitReply
    | RuntimeStorageReclaimReply
    | RuntimeProfileListReply
    | RuntimeResetStartReply
    | RuntimeResetStatusReply
    | RuntimeResetResumeReply
    | RuntimeArchiveInspectReply
    | RuntimeArchiveImportPrepareReply
    | RuntimeArchiveImportReply
    | RuntimeRecoveryEnrollReply
    | RuntimeRepairReportReply
    | RuntimeRepairLogsReply
    | RuntimeRepairProfileReply
    | RuntimeReviewPackageVerifyReply
    | RuntimeReviewPackageVerifySignatureReply
    | RuntimeReviewPackageVerifyReceiptReply
    | RuntimeReportVerifyDocumentReply
)
"""The reply each act returns when it completes."""

type RuntimeInstallationReply = Annotated[
    RuntimeInstallationActReply
    | RuntimeInstallationRefused
    | RuntimeInstallationFailed
    | RuntimeInstallationSecretDelivery,
    Field(discriminator="kind"),
]
"""Closed nonsecret reply union of the installation door."""


@dataclass(frozen=True, slots=True)
class InstallationActFacts:
    """What an act does to the installation, for a surface that refuses by fact."""

    changes_records: bool
    reaches_network: bool


@dataclass(frozen=True, slots=True)
class InstallationActContract:
    """One act's request, its completed reply, its facts and the secrets it exchanges."""

    act: InstallationAct
    request: type[BaseModel]
    reply: type[RuntimeInstallationCompleted]
    facts: InstallationActFacts
    takes_secret: bool = False
    delivers_secret: bool = False


_READS = InstallationActFacts(changes_records=False, reaches_network=False)
_CHANGES_RECORDS = InstallationActFacts(changes_records=True, reaches_network=False)


def _closed_contracts(*contracts: InstallationActContract) -> Mapping[InstallationAct, InstallationActContract]:
    table = {contract.act: contract for contract in contracts}
    if len(table) != len(contracts) or set(table) != set(InstallationAct):
        raise InternalInvariantError("the installation act table must declare every act exactly once")
    for contract in contracts:
        declared = contract.request.model_fields["action"].default
        if declared != contract.act.value:
            raise InternalInvariantError("an installation act's request must carry that act's action")
    return MappingProxyType(table)


INSTALLATION_ACT_CONTRACTS: Final[Mapping[InstallationAct, InstallationActContract]] = _closed_contracts(
    InstallationActContract(
        InstallationAct.STORAGE_INVENTORY, RuntimeStorageInventoryRequest, RuntimeStorageInventoryReply, _READS
    ),
    InstallationActContract(
        InstallationAct.STORAGE_CHECK, RuntimeStorageCheckRequest, RuntimeStorageCheckReply, _READS
    ),
    InstallationActContract(
        InstallationAct.STORAGE_INIT, RuntimeStorageInitRequest, RuntimeStorageInitReply, _CHANGES_RECORDS
    ),
    InstallationActContract(
        InstallationAct.STORAGE_RECLAIM, RuntimeStorageReclaimRequest, RuntimeStorageReclaimReply, _CHANGES_RECORDS
    ),
    InstallationActContract(InstallationAct.PROFILE_LIST, RuntimeProfileListRequest, RuntimeProfileListReply, _READS),
    InstallationActContract(
        InstallationAct.RESET_START, RuntimeResetStartRequest, RuntimeResetStartReply, _CHANGES_RECORDS
    ),
    InstallationActContract(InstallationAct.RESET_STATUS, RuntimeResetStatusRequest, RuntimeResetStatusReply, _READS),
    InstallationActContract(
        InstallationAct.RESET_RESUME, RuntimeResetResumeRequest, RuntimeResetResumeReply, _CHANGES_RECORDS
    ),
    InstallationActContract(
        InstallationAct.ARCHIVE_INSPECT, RuntimeArchiveInspectRequest, RuntimeArchiveInspectReply, _READS
    ),
    InstallationActContract(
        InstallationAct.ARCHIVE_IMPORT_PREPARE,
        RuntimeArchiveImportPrepareRequest,
        RuntimeArchiveImportPrepareReply,
        _READS,
    ),
    InstallationActContract(
        InstallationAct.ARCHIVE_IMPORT,
        RuntimeArchiveImportRequest,
        RuntimeArchiveImportReply,
        _CHANGES_RECORDS,
        takes_secret=True,
    ),
    InstallationActContract(
        InstallationAct.RECOVERY_ENROLL,
        RuntimeRecoveryEnrollRequest,
        RuntimeRecoveryEnrollReply,
        _CHANGES_RECORDS,
        takes_secret=True,
        delivers_secret=True,
    ),
    InstallationActContract(
        InstallationAct.REPAIR_REPORT, RuntimeRepairReportRequest, RuntimeRepairReportReply, _READS
    ),
    InstallationActContract(InstallationAct.REPAIR_LOGS, RuntimeRepairLogsRequest, RuntimeRepairLogsReply, _READS),
    InstallationActContract(
        InstallationAct.REPAIR_PROFILE, RuntimeRepairProfileRequest, RuntimeRepairProfileReply, _CHANGES_RECORDS
    ),
    InstallationActContract(
        InstallationAct.REVIEW_PACKAGE_VERIFY,
        RuntimeReviewPackageVerifyRequest,
        RuntimeReviewPackageVerifyReply,
        _READS,
    ),
    InstallationActContract(
        InstallationAct.REVIEW_PACKAGE_VERIFY_SIGNATURE,
        RuntimeReviewPackageVerifySignatureRequest,
        RuntimeReviewPackageVerifySignatureReply,
        _READS,
    ),
    InstallationActContract(
        InstallationAct.REVIEW_PACKAGE_VERIFY_RECEIPT,
        RuntimeReviewPackageVerifyReceiptRequest,
        RuntimeReviewPackageVerifyReceiptReply,
        _READS,
    ),
    InstallationActContract(
        InstallationAct.REPORT_VERIFY_DOCUMENT,
        RuntimeReportVerifyDocumentRequest,
        RuntimeReportVerifyDocumentReply,
        _READS,
    ),
)
"""The closed table of acts: each act's models and the two facts a surface refuses by."""


def installation_act_of(request: RuntimeInstallationActRequest) -> InstallationAct:
    """Name the act one request asks for."""
    for contract in INSTALLATION_ACT_CONTRACTS.values():
        if type(request) is contract.request:
            return contract.act
    raise InternalInvariantError("a request outside the installation act table names no act")


def installation_request_facts(request: RuntimeInstallationActRequest) -> InstallationActFacts:
    """Return the facts of this exact request.

    An act that changes records is declared so in the table. A request for
    such an act that withholds the confirmation its service requires changes
    nothing: the service refuses it or reports what it would do. Those
    requests read, and are admitted as reads.
    """
    facts = INSTALLATION_ACT_CONTRACTS[installation_act_of(request)].facts
    if not facts.changes_records:
        return facts
    unconfirmed = (
        isinstance(request, RuntimeStorageReclaimRequest | RuntimeResetStartRequest | RuntimeResetResumeRequest)
        and not request.confirmed
    ) or (isinstance(request, RuntimeRepairProfileRequest) and not (request.clear_active and request.confirmed))
    if unconfirmed:
        return InstallationActFacts(changes_records=False, reaches_network=facts.reaches_network)
    return facts
