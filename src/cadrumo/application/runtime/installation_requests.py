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
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    NonNegativeInt,
    SecretStr,
    SerializerFunctionWrapHandler,
    StringConstraints,
    field_serializer,
    model_serializer,
    model_validator,
)

from ...core.errors.hierarchy import InternalInvariantError
from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId, WorkUnitId
from ...core.identity.profile import ProfileId
from ...core.identity.profile_label import ProfileLabel
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.storage_taxonomy import StorageArea
from ...core.text_bounds import NonEmptyStr
from ..config_reset_documents import ConfigResetOperationPayload
from ..diagnostics_repair_documents import RepairProfileDocument, RepairReportDocument
from ..operations.error_detail import OperationErrorDetailV1
from ..operations.public_period import PublicPeriod
from ..operations.registry import OperationFrontendProjection
from ..storage_management.documents import StorageAreaIssuePayload, StorageAreaPayload
from ..user_profile.automation_custody_port import AutomationCustodyCode

#: Largest reply one act may return across its bounded transfer.
INSTALLATION_REPLY_MAX_BYTES: Final[int] = 4_194_304

#: Most log lines one ``repair_logs`` act returns.
INSTALLATION_LOG_TAIL_MAX_LINES: Final[int] = 5_000

#: Seconds a client waits for an act that has no deadline of its own in the table.
INSTALLATION_ACT_DEFAULT_DEADLINE_SECONDS: Final[float] = 30.0

#: Seconds a reset may run: each hosted profile is drained within its own bound
#: before anything is deleted, and each profile is then erased in turn.
INSTALLATION_RESET_DEADLINE_SECONDS: Final[float] = 900.0

#: Seconds a reclaim or an archive import may run: both walk or copy a tree whose size is the operator's.
INSTALLATION_BULK_DEADLINE_SECONDS: Final[float] = 600.0

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
type _ResultText = Annotated[str, StringConstraints(max_length=1024)]
"""One text member of a result whose vocabulary is owned by a module this contract does not import."""
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
    """Ask where the declared storage areas are and what they hold.

    Without ``area`` the reply lists every area; with one it reports that area
    alone, as ``config storage view`` does.
    """

    action: Literal["storage_inventory"] = "storage_inventory"
    area: StorageArea | None = None


class RuntimeStorageInventoryReply(RuntimeInstallationCompleted):
    """What ``config storage list`` or ``config storage view`` prints.

    Exactly one of ``areas`` and ``area`` is present, and the other is absent
    from the document rather than null, as it is in the command's result.
    """

    kind: Literal["storage_inventory_reply"] = "storage_inventory_reply"
    storage_root: NonEmptyStr
    areas: list[StorageAreaPayload] | None = None
    area: StorageAreaPayload | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> Self:
        if (self.areas is None) == (self.area is None):
            raise ValueError("a storage inventory reply lists every area or reports one")
        return self

    @model_serializer(mode="wrap")
    def _omit_the_shape_not_asked_for(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        document: dict[str, object] = {str(name): value for name, value in handler(self).items()}
        for name in ("areas", "area"):
            if document.get(name) is None:
                document.pop(name, None)
        return document


class RuntimeStorageCheckRequest(_InstallationRequest):
    """Compare the tree on disk with its declaration, repairing nothing."""

    action: Literal["storage_check"] = "storage_check"


class RuntimeStorageCheckReply(RuntimeInstallationCompleted):
    """What ``config storage check`` prints: the read-only verdict on the materialised tree."""

    kind: Literal["storage_check_reply"] = "storage_check_reply"
    storage_root: NonEmptyStr
    healthy: bool
    root_mode_enforced: bool
    checked_areas: NonNegativeInt
    issues: list[StorageAreaIssuePayload] = []


class RuntimeStorageInitRequest(_InstallationRequest):
    """Create every declared directory, preserving whatever exists."""

    action: Literal["storage_init"] = "storage_init"


class RuntimeStorageInitReply(RuntimeInstallationCompleted):
    """What ``config storage init`` prints: the directories this act created and how many were already there."""

    kind: Literal["storage_init_reply"] = "storage_init_reply"
    storage_root: NonEmptyStr
    created_count: NonNegativeInt = 0
    already_present: NonNegativeInt = 0


class RuntimeStorageReclaimRequest(_InstallationRequest):
    """Delete one area's regenerable contents after its derived preflight.

    Without ``confirmed`` the act deletes nothing and is refused with the
    count of entries a confirmed act would remove.
    """

    action: Literal["storage_reclaim"] = "storage_reclaim"
    area: StorageArea
    confirmed: bool = False


class RuntimeStorageReclaimReply(RuntimeInstallationCompleted):
    """What ``config storage reclaim`` prints: what one confirmed reclaim removed and what it had to leave."""

    kind: Literal["storage_reclaim_reply"] = "storage_reclaim_reply"
    area: StorageArea
    target_count: NonNegativeInt
    removed_entries: NonNegativeInt
    retained_entries: NonNegativeInt = 0


# -- profiles --------------------------------------------------------------------


class RuntimeProfileListRequest(_InstallationRequest):
    """List committed profiles without unlocking any of them."""

    action: Literal["profile_list"] = "profile_list"


class RuntimeProfileListRow(BaseModel):
    """One listed profile: its label, its identifier, and whether it is the selected one."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    name: ProfileLabel
    bucket_id: ProfileId
    active: bool


class RuntimeProfileListReply(RuntimeInstallationCompleted):
    """The result of ``config profile list``, from one listing observation and one pointer read.

    Identifiers are the real ones. The command hides them when it prints
    unless the installation reveals them; a reply hides nothing, because a
    caller names a profile by the identifier it reads here.

    An observation that could not be trusted is refused, never answered with
    an empty listing: an empty listing stands only for a store with no profiles.
    """

    kind: Literal["profile_list_reply"] = "profile_list_reply"
    active_profile: ProfileLabel | None = None
    profiles: tuple[RuntimeProfileListRow, ...] = ()


class RuntimeArchiveInspectRequest(_InstallationRequest):
    """Read an archive's plaintext header without decrypting anything."""

    action: Literal["archive_inspect"] = "archive_inspect"
    path: InstallationHostPath


class RuntimeArchiveInspectReply(RuntimeInstallationCompleted):
    """The result of ``config profile archive inspect``: what the archive discloses to anyone holding it."""

    kind: Literal["archive_inspect_reply"] = "archive_inspect_reply"
    product: _ResultText
    bucket_id: BucketId
    archive_schema_version: int
    created_at: datetime
    manifest_digest: _ResultText

    @field_serializer("created_at", when_used="json")
    def _instant_as_the_command_writes_it(self, value: datetime) -> str:
        """Write the instant in the text form the command prints, so both show one document."""
        return value.isoformat()


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
    """The result of ``config profile archive import``; a restore never carries recovery across."""

    kind: Literal["archive_import_reply"] = "archive_import_reply"
    profile_id: ProfileId
    label: ProfileLabel
    authority: _ResultText
    recovery_enrolled: bool


class RuntimeRecoveryEnrollRequest(_InstallationRequest):
    """Mint a recovery code for one committed profile.

    The current passphrase follows in one secret frame. The code is delivered
    in one secret frame and must be read back before the wrapper is installed.
    A request that names no profile enrols the selected one, as the command does.
    """

    action: Literal["recovery_enroll"] = "recovery_enroll"
    profile_id: UUID | None = None


class RuntimeRecoveryEnrollReply(RuntimeInstallationCompleted):
    """The result of ``config profile recovery enable``; the code is never part of it."""

    kind: Literal["recovery_enroll_reply"] = "recovery_enroll_reply"
    profile_id: ProfileId
    enrolled: bool
    changed: bool


# -- reset -----------------------------------------------------------------------


class RuntimeResetStartRequest(_InstallationRequest):
    """Start one durable all-profile reset. Without ``confirmed`` it is refused."""

    action: Literal["reset_start"] = "reset_start"
    confirmed: bool = False
    acknowledge_retention_override: bool = False
    retention_override_reason: _OperatorText | None = None


class RuntimeResetStartReply(RuntimeInstallationCompleted):
    """What ``config reset start`` prints: the reset journal as this act left it."""

    kind: Literal["reset_start_reply"] = "reset_start_reply"
    operation: ConfigResetOperationPayload


class RuntimeResetStatusRequest(_InstallationRequest):
    """Read one reset journal, or the latest, without resuming it."""

    action: Literal["reset_status"] = "reset_status"
    operation_id: Hex64Str | None = None


class RuntimeResetStatusReply(RuntimeInstallationCompleted):
    """What ``config reset status`` prints: the journal read, or ``None`` when no reset was ever started."""

    kind: Literal["reset_status_reply"] = "reset_status_reply"
    operation: ConfigResetOperationPayload | None


class RuntimeResetResumeRequest(_InstallationRequest):
    """Roll one incomplete reset forward. Without an id it names the latest."""

    action: Literal["reset_resume"] = "reset_resume"
    operation_id: Hex64Str | None = None
    confirmed: bool = False
    acknowledge_retention_override: bool = False
    retention_override_reason: _OperatorText | None = None


class RuntimeResetResumeReply(RuntimeInstallationCompleted):
    """What ``config reset resume`` prints: the reset journal as this act left it."""

    kind: Literal["reset_resume_reply"] = "reset_resume_reply"
    operation: ConfigResetOperationPayload


# -- repair ----------------------------------------------------------------------


class RuntimeRepairReportRequest(_InstallationRequest):
    """Diagnose local configuration, profile, sign-in and log state."""

    action: Literal["repair_report"] = "repair_report"


class RuntimeRepairReportReply(RepairReportDocument, RuntimeInstallationCompleted):
    """What ``config repair`` prints: the composite diagnosis of the installation."""

    kind: Literal["repair_report_reply"] = "repair_report_reply"


class RuntimeRepairLogsRequest(_InstallationRequest):
    """Read the configured log file's path and its most recent lines."""

    action: Literal["repair_logs"] = "repair_logs"
    lines: Annotated[int, Field(ge=0, le=INSTALLATION_LOG_TAIL_MAX_LINES)] = 20


class RuntimeRepairLogsReply(RuntimeInstallationCompleted):
    """A bounded tail of the log file; empty when the file does not exist."""

    kind: Literal["repair_logs_reply"] = "repair_logs_reply"
    path: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    lines: Annotated[tuple[str, ...], Field(max_length=INSTALLATION_LOG_TAIL_MAX_LINES)]


class RuntimeRepairProfileRequest(_InstallationRequest):
    """Inspect one profile's record, or repair a degraded active-profile pointer.

    Naming a profile without ``clear_active`` inspects that profile. Without
    ``clear_active`` and without a profile the act assesses the active pointer
    and changes nothing. With ``clear_active`` it clears a degraded pointer,
    and without ``confirmed`` that request is refused as the command refuses
    it without ``--yes``.
    """

    action: Literal["repair_profile"] = "repair_profile"
    profile: _OperatorText | None = None
    clear_active: bool = False
    confirmed: bool = False


class RuntimeRepairProfileReply(RepairProfileDocument, RuntimeInstallationCompleted):
    """What ``config repair profile`` prints: a pointer repair, or one named profile's record status."""

    kind: Literal["repair_profile_reply"] = "repair_profile_reply"


# -- files the operator holds ----------------------------------------------------
#
# Each reply below carries, besides the transport members, the members of the
# document the matching command prints as the ``result`` of its JSON envelope,
# with the real values, as a registered operation's result carries them. The
# command line applies its output redaction when it prints.


class RuntimeReviewPackageVerifyRequest(_InstallationRequest):
    """Verify a review package's checksum manifest and read its descriptor."""

    action: Literal["review_package_verify"] = "review_package_verify"
    package: InstallationHostPath


class RuntimeReviewPackageVerifyReply(RuntimeInstallationCompleted):
    """The integrity verdict and the descriptor recovered from the package."""

    kind: Literal["review_package_verify_reply"] = "review_package_verify_reply"
    operation: Literal["modelo.review_package.verify"]
    package_path: str
    is_clean: bool
    missing: list[str]
    unexpected: list[str]
    mismatched: list[str]
    bucket_id: BucketId
    work_unit_id: WorkUnitId
    calculation_revision_id: CalculationRevisionId
    modelo: str
    filing_year: FilingYear
    period: PublicPeriod
    revision_state: str
    has_ledger_evidence: bool
    built_by: str
    built_at: datetime


class RuntimeReviewPackageVerifySignatureRequest(_InstallationRequest):
    """Verify a package's signature envelope against a key the caller trusts."""

    action: Literal["review_package_verify_signature"] = "review_package_verify_signature"
    package: InstallationHostPath
    signature: InstallationHostPath
    public_key: _KeyText


class RuntimeReviewPackageVerifySignatureReply(RuntimeInstallationCompleted):
    """Whether the signature holds for the package's current bytes and the named key."""

    kind: Literal["review_package_verify_signature_reply"] = "review_package_verify_signature_reply"
    operation: Literal["modelo.review_package.verify_signature"]
    package_path: str
    signature_path: str
    signer_public_key_hex: str
    is_valid: bool


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
    operation: Literal["modelo.review_package.verify_receipt"]
    package_path: str
    receipt_path: str
    operator_public_key_hex: str
    counter_signer_public_key_hex: str
    is_valid: bool


class RuntimeReportVerificationCheck(BaseModel):
    """One check that ran on a calculation summary, and what it found."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    check: _VocabularyToken
    layer: _VocabularyToken
    reason: _VocabularyToken | None = None
    detail: str | None = None
    refuses: bool


class RuntimeReportVerifyDocumentRequest(_InstallationRequest):
    """Verify a calculation summary file by its own bytes, tracing it to no profile."""

    action: Literal["report_verify_document"] = "report_verify_document"
    path: InstallationHostPath
    trusted_key: _KeyText | None = None


class RuntimeReportVerifyDocumentReply(RuntimeInstallationCompleted):
    """The document-layer verdict; ``store_checked`` is always false for this act."""

    kind: Literal["report_verify_document_reply"] = "report_verify_document_reply"
    operation: Literal["modelo.work.report_verify"]
    path: str
    outcome: _VocabularyToken
    store_checked: bool
    reasons: list[_VocabularyToken]
    checks: list[RuntimeReportVerificationCheck]
    calculation_revision_id: Hex64Str | None = None
    report_sha256: Hex64Str | None = None
    statement_sha256: Hex64Str | None = None
    signing_key_fingerprint: Hex64Str | None = None


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

    An access refusal raised after the act began to change records settles
    here too, because a refusal would say that nothing changed. The fault is in
    the runtime's diagnostic log. An act that changes records may have changed
    some before it stopped: this reply never says it did not, and the act's
    contract names the act that reads its outcome where there is one.
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
    deadline_seconds: float = INSTALLATION_ACT_DEFAULT_DEADLINE_SECONDS
    """How long a client waits for this act. A secret handover adds its own bound."""
    outcome_read_by: InstallationAct | None = None
    """The act that reads this act's outcome when a client stopped waiting before it settled."""


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
        InstallationAct.STORAGE_RECLAIM,
        RuntimeStorageReclaimRequest,
        RuntimeStorageReclaimReply,
        _CHANGES_RECORDS,
        deadline_seconds=INSTALLATION_BULK_DEADLINE_SECONDS,
    ),
    InstallationActContract(InstallationAct.PROFILE_LIST, RuntimeProfileListRequest, RuntimeProfileListReply, _READS),
    InstallationActContract(
        InstallationAct.RESET_START,
        RuntimeResetStartRequest,
        RuntimeResetStartReply,
        _CHANGES_RECORDS,
        deadline_seconds=INSTALLATION_RESET_DEADLINE_SECONDS,
        outcome_read_by=InstallationAct.RESET_STATUS,
    ),
    InstallationActContract(InstallationAct.RESET_STATUS, RuntimeResetStatusRequest, RuntimeResetStatusReply, _READS),
    InstallationActContract(
        InstallationAct.RESET_RESUME,
        RuntimeResetResumeRequest,
        RuntimeResetResumeReply,
        _CHANGES_RECORDS,
        deadline_seconds=INSTALLATION_RESET_DEADLINE_SECONDS,
        outcome_read_by=InstallationAct.RESET_STATUS,
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
        deadline_seconds=INSTALLATION_BULK_DEADLINE_SECONDS,
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
