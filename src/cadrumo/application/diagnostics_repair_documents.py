"""The documents the repair commands print, shared by every frontend.

Each model here is the JSON data of one ``config repair`` command, member for
member. The command line prints it inside its envelope. The runtime's repair
acts reply with it and the registered diagnostics operations return it, so
the terminal interface and MCP show the document the command prints and
render nothing of their own.

A builder projects the application's own result onto its document, with the
real identifier of every profile it names. :func:`printed` then withholds
what the command line withholds from every document it writes, whoever reads
it: tax identities, tokens, addresses and storage keys inside free text. An
act or an operation returns that document.

Hiding a profile or bucket identifier is not done here. It is the command
line's own choice where it writes a document out, and an operator turns it
off there. A frontend that reaches the work through the runtime therefore
receives the identifiers the command line shows when they are revealed.

Apart from identifiers the members are plain JSON scalars on purpose, so a
process that only connects to the runtime reads these models without loading
the registry or a profile view.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel, JsonValue, NonNegativeInt, TypeAdapter

from ..core.identity.bucket import BucketId
from ..core.identity.profile import ProfileId
from ..core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..core.output_rendering import jsonable_output_payload
from ..core.redaction.rules import redact_structured_for_cli_output

if TYPE_CHECKING:
    from ..core.json_contract import ResolvedPreconditionAction
    from .connectivity_probe import ConnectivityReport
    from .diagnostic_models import ConfigRepairReport, SecureObjectIntegrityReport
    from .diagnostics_ports import DiagnosticSecureObjectNamespace
    from .diagnostics_repair import SecureObjectIntegrityCheck
    from .operator_actions.models import PreconditionVerdict
    from .workflow.events import WorkflowStateResetFingerprint
    from .workflow.profile_health import ActiveProfileHealth, ActiveProfileRepairResult
    from .workflow.profile_repair import ProfileRecordInspection

type RepairActionDocument = dict[str, JsonValue]
"""One resolved recovery action, exactly as the command line prints it."""

_ACTION_DOCUMENT = TypeAdapter[RepairActionDocument](dict[str, JsonValue])


class PreconditionActionResolver(Protocol):
    """Resolve an application verdict into the action the command line prints.

    The resolution reads the live command surface, which the application does
    not own, so the process that composes a frontend binds it.
    """

    def __call__(self, verdict: PreconditionVerdict, /) -> ResolvedPreconditionAction:
        """Return the verdict with its action resolved against the live command surface."""
        ...


class _RepairDocument(BaseModel):
    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG


class RepairNamespaceDocument(_RepairDocument):
    """Readable and unreadable row counts of one secure-object namespace."""

    namespace: str
    readable: NonNegativeInt
    unreadable: NonNegativeInt


class RepairSetupDocument(_RepairDocument):
    """The active profile's readiness summary inside a repair report."""

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


class RepairSecureObjectsDocument(_RepairDocument):
    """Secure-object integrity totals inside a repair report."""

    namespaces: tuple[RepairNamespaceDocument, ...]
    readable_total: NonNegativeInt
    unreadable_total: NonNegativeInt


class RepairFindingDocument(_RepairDocument):
    """One named sub-finding inside a repair check."""

    summary: str
    detail: str | None = None
    requirement: str | None = None


class RepairCheckDocument(_RepairDocument):
    """One repair check with the recovery action its verdict resolves to."""

    name: str
    status: str
    summary: str
    detail: str | None = None
    precondition_action: RepairActionDocument | None = None
    audience: str
    findings: tuple[RepairFindingDocument, ...]


class RepairReportDocument(_RepairDocument):
    """What ``config repair`` prints: the composite diagnosis of the installation."""

    overall: str
    package_name: str
    package_version: str
    python_version: str
    log_file: str
    setup: RepairSetupDocument | None
    secure_objects: RepairSecureObjectsDocument
    checks: tuple[RepairCheckDocument, ...]


class RepairLogsDocument(_RepairDocument):
    """What ``config repair logs`` prints: the log file's path and its most recent lines."""

    path: str
    lines: tuple[str, ...]


class RepairProfileHealthDocument(_RepairDocument):
    """One active-profile health verdict with the recovery action it resolves to.

    ``active_profile`` names the profile by its label, or by its identifier
    when the selection resolves to no labelled profile.
    """

    active_profile: str | None
    source: str
    status: str
    registered_bucket: bool = False
    profile_record_present: bool = False
    profile_record_error: str = ""
    profile_present_keys: NonNegativeInt = 0
    profile_total_keys: NonNegativeInt = 0
    missing_required: tuple[str, ...] = ()
    repairable_by_clearing_pointer: bool = False
    precondition_action: RepairActionDocument | None = None


class RepairProfileDocument(_RepairDocument):
    """What ``config repair profile`` prints.

    A pointer repair fills ``dry_run``, ``cleared_pointer``, ``before`` and
    ``after``. The inspection of one named profile fills the remaining
    members. The members of the other branch are null.
    """

    dry_run: bool | None = None
    cleared_pointer: bool | None = None
    before: RepairProfileHealthDocument | None = None
    after: RepairProfileHealthDocument | None = None
    profile_id: ProfileId | None = None
    bucket_id: BucketId | None = None
    display_name: str | None = None
    registered_bucket: bool | None = None
    profile_record_present: bool | None = None
    setup_state: str | None = None
    status: str | None = None
    error: str | None = None
    precondition_action: RepairActionDocument | None = None


class RepairIntegrityVerdictDocument(_RepairDocument):
    """The verdict of one integrity sweep on its unreadable rows."""

    status: str
    summary: str


class RepairIntegrityObjectsDocument(_RepairDocument):
    """What ``config repair integrity objects`` prints."""

    namespaces: tuple[RepairNamespaceDocument, ...]
    readable_total: NonNegativeInt
    unreadable_total: NonNegativeInt
    check: RepairIntegrityVerdictDocument


class RepairQuarantineDocument(_RepairDocument):
    """What ``config repair quarantine`` prints.

    A run over a profile fills the totals and the namespace rows. The members
    ``quarantined``, ``retained`` and ``reason`` belong to the command's answer
    when no profile is selected, and are null otherwise.
    """

    dry_run: bool
    quarantined: int | None = None
    retained: int | None = None
    reason: str | None = None
    unreadable_total: int | None = None
    readable_total: int | None = None
    namespaces: tuple[RepairNamespaceDocument, ...] | None = None


class RepairFingerprintDocument(_RepairDocument):
    """Row metadata of the saved progress record; never its contents."""

    schema_version: int | None = None
    written_at: str | None = None
    byte_length: int | None = None
    reason_class: str
    recovered_bucket_id: BucketId | None = None


class RepairResetProgressDocument(_RepairDocument):
    """What ``config repair reset-progress`` prints.

    A run over a profile fills ``dry_run`` and ``fingerprint``. The members
    ``reset`` and ``reason`` belong to the command's answer when no profile is
    selected, and are null otherwise.
    """

    reset: bool | None = None
    reason: str | None = None
    dry_run: bool | None = None
    fingerprint: RepairFingerprintDocument | None = None


class RepairConnectivityEvidenceDocument(_RepairDocument):
    """What one connectivity classification was read from."""

    url: str
    http_status: int
    html_fragment: str
    detected_markers: tuple[str, ...]


class RepairConnectivityStatusDocument(_RepairDocument):
    """The classified answer of the probed site."""

    state: str
    evidence: RepairConnectivityEvidenceDocument
    observed_at: str
    retry_after_seconds: int | None = None


class RepairConnectivityDocument(_RepairDocument):
    """What ``config repair connectivity`` prints."""

    target: str
    status: RepairConnectivityStatusDocument


def printed[DocumentT: BaseModel](document: DocumentT) -> DocumentT:
    """Return ``document`` as the command line writes it out with identifiers revealed.

    The command line passes every document through one redaction funnel
    before it is written. The same funnel is applied here for what it
    withholds from every reader, so no tax identity, token or address inside a
    log line or a fault text leaves the process. Profile and bucket
    identifiers stay as they are: only the command line hides those, at its
    own output boundary.
    """
    written = redact_structured_for_cli_output(jsonable_output_payload(document), reveal_identifiers=True)
    document_type: type[DocumentT] = type(document)
    return document_type.model_validate_json(json.dumps(written))


def _action(
    verdict: PreconditionVerdict | None, resolve_action: PreconditionActionResolver
) -> RepairActionDocument | None:
    if verdict is None:
        return None
    return _ACTION_DOCUMENT.validate_python(jsonable_output_payload(resolve_action(verdict)))


def _namespaces(rows: tuple[DiagnosticSecureObjectNamespace, ...]) -> tuple[RepairNamespaceDocument, ...]:
    return tuple(
        RepairNamespaceDocument(namespace=row.namespace, readable=row.readable, unreadable=row.unreadable)
        for row in rows
    )


def repair_report_document(
    report: ConfigRepairReport, *, resolve_action: PreconditionActionResolver
) -> RepairReportDocument:
    """Project the composite repair report onto the document ``config repair`` prints."""
    setup = report.setup
    return RepairReportDocument(
        overall=str(report.overall),
        package_name=report.package_name,
        package_version=report.package_version,
        python_version=report.python_version,
        log_file=report.log_file,
        setup=(
            None
            if setup is None
            else RepairSetupDocument(
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
        secure_objects=RepairSecureObjectsDocument(
            namespaces=_namespaces(report.secure_objects.namespaces),
            readable_total=report.secure_objects.readable_total,
            unreadable_total=report.secure_objects.unreadable_total,
        ),
        checks=tuple(
            RepairCheckDocument(
                name=check.name,
                status=str(check.status),
                summary=check.summary,
                detail=check.detail,
                precondition_action=_action(check.precondition_verdict, resolve_action),
                audience=str(check.audience),
                findings=tuple(
                    RepairFindingDocument(
                        summary=finding.summary,
                        detail=finding.detail,
                        requirement=None if finding.requirement is None else str(finding.requirement),
                    )
                    for finding in check.findings
                ),
            )
            for check in report.checks
        ),
    )


def profile_health_reference(health: ActiveProfileHealth) -> str | None:
    """Name the health verdict's profile by its label, or by its identifier when it has none."""
    return health.active_profile_label or health.active_profile


def _health_document(
    health: ActiveProfileHealth, resolve_action: PreconditionActionResolver
) -> RepairProfileHealthDocument:
    members = {
        **health.model_dump(mode="json", exclude={"precondition_verdict"}),
        "active_profile": profile_health_reference(health),
        "precondition_action": _action(health.precondition_verdict, resolve_action),
    }
    return RepairProfileHealthDocument.model_validate_json(json.dumps(members))


def profile_pointer_repair_document(
    result: ActiveProfileRepairResult, *, resolve_action: PreconditionActionResolver
) -> RepairProfileDocument:
    """Project one pointer repair onto the document ``config repair profile`` prints."""
    return RepairProfileDocument(
        dry_run=result.dry_run,
        cleared_pointer=result.cleared_pointer,
        before=_health_document(result.before, resolve_action),
        after=None if result.after is None else _health_document(result.after, resolve_action),
    )


def profile_record_document(
    inspection: ProfileRecordInspection, *, resolve_action: PreconditionActionResolver
) -> RepairProfileDocument:
    """Project one record inspection onto the document ``config repair profile`` prints."""
    return RepairProfileDocument(
        profile_id=inspection.profile_id,
        bucket_id=inspection.profile_id,
        display_name=inspection.display_name,
        registered_bucket=inspection.registered_bucket,
        profile_record_present=inspection.profile_record_present,
        setup_state=None if inspection.setup_state is None else inspection.setup_state.value,
        status=None if inspection.status is None else inspection.status.value,
        error=inspection.error,
        precondition_action=_action(inspection.precondition_verdict, resolve_action),
    )


def integrity_objects_document(check: SecureObjectIntegrityCheck) -> RepairIntegrityObjectsDocument:
    """Project one integrity sweep and its verdict onto the document the command prints."""
    return RepairIntegrityObjectsDocument(
        namespaces=_namespaces(check.report.namespaces),
        readable_total=check.report.readable_total,
        unreadable_total=check.report.unreadable_total,
        check=RepairIntegrityVerdictDocument(status=check.status.value, summary=check.summary),
    )


def quarantine_document(report: SecureObjectIntegrityReport, *, dry_run: bool) -> RepairQuarantineDocument:
    """Project one quarantine run, or its preview, onto the document the command prints."""
    return RepairQuarantineDocument(
        dry_run=dry_run,
        unreadable_total=report.unreadable_total,
        readable_total=report.readable_total,
        namespaces=_namespaces(report.namespaces),
    )


def reset_progress_document(
    fingerprint: WorkflowStateResetFingerprint, *, dry_run: bool
) -> RepairResetProgressDocument:
    """Project one progress reset, or its preview, onto the document the command prints."""
    return RepairResetProgressDocument(
        dry_run=dry_run,
        fingerprint=RepairFingerprintDocument(
            schema_version=fingerprint.schema_version,
            written_at=None if fingerprint.written_at is None else fingerprint.written_at.isoformat(),
            byte_length=fingerprint.byte_length,
            reason_class=fingerprint.reason_class,
            recovered_bucket_id=fingerprint.recovered_bucket_id or None,
        ),
    )


def connectivity_document(report: ConnectivityReport) -> RepairConnectivityDocument:
    """Project one connectivity probe onto the document the command prints."""
    return RepairConnectivityDocument.model_validate_json(
        json.dumps({"target": report.target, "status": report.status.model_dump(mode="json")})
    )


__all__ = [
    "PreconditionActionResolver",
    "RepairActionDocument",
    "RepairCheckDocument",
    "RepairConnectivityDocument",
    "RepairConnectivityEvidenceDocument",
    "RepairConnectivityStatusDocument",
    "RepairFindingDocument",
    "RepairFingerprintDocument",
    "RepairIntegrityObjectsDocument",
    "RepairIntegrityVerdictDocument",
    "RepairLogsDocument",
    "RepairNamespaceDocument",
    "RepairProfileDocument",
    "RepairProfileHealthDocument",
    "RepairQuarantineDocument",
    "RepairReportDocument",
    "RepairResetProgressDocument",
    "RepairSecureObjectsDocument",
    "RepairSetupDocument",
    "connectivity_document",
    "integrity_objects_document",
    "printed",
    "profile_health_reference",
    "profile_pointer_repair_document",
    "profile_record_document",
    "quarantine_document",
    "repair_report_document",
    "reset_progress_document",
]
