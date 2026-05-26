"""Backend services for ``aeat config repair integrity`` and ``... repair list``.

Implements the subverbs for configuration repair and integrity checks. Each function
returns a strict Pydantic report consumed by the CLI's ``_emit``
renderer; both functions are read-only and emit no bucket events.

  ``build_repair_integrity_report``  per-namespace decryptability
                                     summary (optionally filtered to
                                     one namespace) plus an aggregate
                                     ``DiagnosticCheck`` row carrying
                                     the required ``next_action`` or
                                     ``dead_end`` field.

  ``build_repair_list_report``       namespace inventory: every stored
                                     lookup digest under the supplied
                                     namespace, plus per-namespace
                                     decryptability counts.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import ClassVar, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy.exc import SQLAlchemyError

from ..adapters.persistence.storage.crypto._encrypted_columns import HashedLookup, decrypt_encrypted_bytes_column
from ..adapters.persistence.storage.envelope import Envelope
from ..adapters.persistence.storage.envelope._secure_repository import SecureBoundRepository
from ..adapters.persistence.storage.errors import DecryptionError, StorageError
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ..adapters.persistence.storage.sql.secure_objects import (
    SecureObjectNamespaceIntegrity,
    SecureObjectRawRow,
)
from ..core.classification import SensitivityClass
from ..domain.modelos._repository import WORK_UNIT_CATALOGUE_VERSION, WORK_UNIT_NAMESPACE
from .diagnostics import DiagnosticCheck


@runtime_checkable
class _SecureObjectRepositoryProtocol(Protocol):
    """Structural interface consumed by the repair-integrity application layer.

    ``SecureObjectRepository`` satisfies this protocol; test stubs that
    implement only these three methods are accepted without subclassing.
    """

    def list_namespaces(self) -> tuple[str, ...]: ...
    def probe_namespace_integrity(self, namespace: str) -> SecureObjectNamespaceIntegrity: ...
    def list_keys(self, namespace: str) -> tuple[str, ...]: ...
    def iter_all_records_raw(self, *, batch_size: int = 256) -> Iterator[SecureObjectRawRow]: ...


class RepairIntegrityReport(BaseModel):
    """Output of ``aeat config repair integrity [--namespace N]``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespaces: tuple[SecureObjectNamespaceIntegrity, ...]
    readable_total: int = Field(ge=0)
    unreadable_total: int = Field(ge=0)
    check: DiagnosticCheck


class RepairListRow(BaseModel):
    """One row in ``aeat config repair list <namespace>``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    object_key_digest: str = Field(min_length=1)
    row_id: int | None = Field(default=None, ge=0)
    classification: str | None = None
    schema_version: int | None = Field(default=None, ge=1)
    written_at: datetime | None = None
    readable: bool | None = None
    reason: str = ""
    context_bucket_id: str = ""
    object_key_kind: str = ""
    object_key_hint: str = ""
    context_confidence: str = ""
    context_note: str = ""


class RepairNamespaceClassification(BaseModel):
    """Conservative repair guidance for one secure-object namespace."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    role: str = Field(min_length=1)
    iva_reconciliation_relevance: str = Field(min_length=1)
    participates_in_iva_compensation_history: bool
    destructive_repair_risk: str = Field(min_length=1)
    operator_note: str = Field(min_length=1)
    replacement_evidence_requirements: tuple[str, ...] = ()
    destructive_quarantine_allowed: bool = True
    destructive_quarantine_policy: str = Field(default="verified_replacement_evidence_required", min_length=1)

    @field_validator("destructive_quarantine_policy")
    @classmethod
    def _validate_destructive_quarantine_policy(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="destructive quarantine policy")
        return value

    @field_validator("replacement_evidence_requirements")
    @classmethod
    def _validate_replacement_evidence_requirements(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for requirement in value:
            if not requirement:
                msg = "replacement evidence requirements must be non-empty strings"
                raise ValueError(msg)
            _raise_if_sensitive_context(requirement, field_name="replacement evidence requirement")
        return value


class RepairNamespacePolicy(BaseModel):
    """Executable repair/recovery policy for one governed namespace."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    namespace_classification: RepairNamespaceClassification
    owner_domain: str = Field(min_length=1)
    bucket_scope: str = Field(min_length=1)
    sensitivity_class: str = Field(min_length=1)
    repair_policy: str = Field(min_length=1)
    recovery_policy: str = Field(min_length=1)
    mutation_authority: str = Field(min_length=1)
    export_policy: str = Field(min_length=1)
    import_policy: str = Field(min_length=1)
    retention_legal_note: str = Field(min_length=1)
    calculation_confidence_impact: str = Field(min_length=1)

    @field_validator(
        "namespace",
        "owner_domain",
        "bucket_scope",
        "sensitivity_class",
        "repair_policy",
        "recovery_policy",
        "mutation_authority",
        "export_policy",
        "import_policy",
        "retention_legal_note",
        "calculation_confidence_impact",
    )
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="repair namespace policy")
        return value


RepairPolicyCommandFamily = Literal["repair", "recovery", "import", "export", "bucket"]


class RepairPolicyCommandSurface(BaseModel):
    """ADR-linked policy coverage for one repair/recovery command surface."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    command_path: str = Field(min_length=1)
    command_family: RepairPolicyCommandFamily
    owner_domains: tuple[str, ...] = Field(min_length=1)
    governed_namespaces: tuple[str, ...] = ()
    mutation_policy: str = Field(min_length=1)
    redaction_policy: str = Field(min_length=1)
    adr_links: tuple[str, ...] = Field(min_length=1)

    @field_validator("command_path", "mutation_policy", "redaction_policy")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="repair command policy")
        return value

    @field_validator("owner_domains", "governed_namespaces")
    @classmethod
    def _validate_safe_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not item:
                msg = "repair command policy tuple entries must be non-empty"
                raise ValueError(msg)
            _raise_if_sensitive_context(item, field_name="repair command policy")
        return value

    @field_validator("adr_links")
    @classmethod
    def _validate_adr_links(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not item.startswith("[[") or not item.endswith("]]"):
                msg = "repair command policy ADR links must be vault wiki-links"
                raise ValueError(msg)
            _raise_if_sensitive_context(item, field_name="repair command policy ADR link")
        return value

    @model_validator(mode="after")
    def _validate_namespace_or_domain_policy(self) -> RepairPolicyCommandSurface:
        if not self.owner_domains and not self.governed_namespaces:
            msg = "repair command policy must declare at least one owner domain or namespace"
            raise ValueError(msg)
        return self

    @property
    def namespace_policies(self) -> tuple[RepairNamespacePolicy, ...]:
        """Return executable namespace policies linked to this command surface."""

        return tuple(build_repair_namespace_policy(namespace) for namespace in self.governed_namespaces)


class RepairUnreadableRowAttribution(BaseModel):
    """Safe metadata attribution for one undecryptable secure-object row."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    object_key_digest: str = Field(min_length=1)
    row_id: int | None = Field(default=None, ge=0)
    classification: str | None = None
    schema_version: int | None = Field(default=None, ge=1)
    written_at: datetime | None = None
    reason: str = ""
    owner_semantics: str = Field(min_length=1)
    likely_origin: str = Field(min_length=1)
    origin_confidence: str = Field(min_length=1)
    context_bucket_id: str = ""
    object_key_kind: str = ""
    object_key_hint: str = ""
    context_confidence: str = ""
    context_note: str = ""

    @field_validator("context_bucket_id")
    @classmethod
    def _validate_context_bucket_id(cls, value: str) -> str:
        if value not in {"", "active_profile"}:
            msg = "context_bucket_id must be empty or the redacted active_profile label"
            raise ValueError(msg)
        return value

    @field_validator("object_key_hint")
    @classmethod
    def _validate_object_key_hint(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="object_key_hint")
        if ":" in value and "<active-profile>" not in value:
            msg = "object_key_hint must redact concrete natural-key suffixes"
            raise ValueError(msg)
        return value

    @field_validator("context_note", "reason")
    @classmethod
    def _validate_safe_context_text(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="context text")
        return value


class RepairUnreadableClassificationGroup(BaseModel):
    """Unreadable-row count for one stored secure-object classification."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    classification: str = Field(min_length=1)
    unreadable_count: int = Field(ge=1)


class RepairUnreadableNamespaceAttribution(BaseModel):
    """Safe metadata attribution summary for one impacted namespace."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    namespace_classification: RepairNamespaceClassification
    owner_semantics: str = Field(min_length=1)
    classification_groups: tuple[RepairUnreadableClassificationGroup, ...]
    unreadable_rows: tuple[RepairUnreadableRowAttribution, ...]
    unreadable_count: int = Field(ge=0)
    first_written_at: datetime | None = None
    last_written_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_namespace_summary(self) -> RepairUnreadableNamespaceAttribution:
        if self.unreadable_count != len(self.unreadable_rows):
            msg = "unreadable_count must equal the number of unreadable_rows"
            raise ValueError(msg)
        grouped_total = sum(group.unreadable_count for group in self.classification_groups)
        if grouped_total != self.unreadable_count:
            msg = "classification_groups must sum to unreadable_count"
            raise ValueError(msg)
        if any(row.namespace != self.namespace for row in self.unreadable_rows):
            msg = "all unreadable_rows must belong to the namespace attribution"
            raise ValueError(msg)
        if (
            self.first_written_at is not None
            and self.last_written_at is not None
            and self.first_written_at > self.last_written_at
        ):
            msg = "first_written_at must be earlier than or equal to last_written_at"
            raise ValueError(msg)
        row_timestamps = tuple(row.written_at for row in self.unreadable_rows if row.written_at is not None)
        if self.first_written_at is not None and any(timestamp < self.first_written_at for timestamp in row_timestamps):
            msg = "row written_at values must not precede first_written_at"
            raise ValueError(msg)
        if self.last_written_at is not None and any(timestamp > self.last_written_at for timestamp in row_timestamps):
            msg = "row written_at values must not follow last_written_at"
            raise ValueError(msg)
        return self


class RepairIntegrityAttributionReport(BaseModel):
    """Output model for read-only secure-object unreadable-row attribution."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    attribution_version: int = Field(default=1, ge=1)
    payload_disclosure: Literal["metadata_only"] = "metadata_only"
    namespaces: tuple[RepairUnreadableNamespaceAttribution, ...]
    unreadable_total: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_report_total(self) -> RepairIntegrityAttributionReport:
        if self.unreadable_total != sum(namespace.unreadable_count for namespace in self.namespaces):
            msg = "unreadable_total must equal the sum of namespace unreadable counts"
            raise ValueError(msg)
        return self


class RepairEnvelopeValidationFinding(BaseModel):
    """Metadata-only finding for one readable secure-object contract drift."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    object_key_digest: str = Field(min_length=1)
    row_id: int | None = Field(default=None, ge=0)
    finding_type: str = Field(min_length=1)
    contract_kind: str = Field(min_length=1)
    expected_classification: str = Field(min_length=1)
    actual_classification: str | None = None
    max_supported_version: int = Field(ge=1)
    actual_schema_version: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="envelope validation reason")
        return value


class RepairEnvelopeValidationReport(BaseModel):
    """Read-only validation of decryptable rows against owner contracts."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    validation_version: int = Field(default=1, ge=1)
    payload_disclosure: Literal["metadata_only"] = "metadata_only"
    rows_total: int = Field(ge=0)
    readable_rows_checked: int = Field(ge=0)
    unreadable_rows_skipped: int = Field(ge=0)
    findings: tuple[RepairEnvelopeValidationFinding, ...]
    finding_count: int = Field(ge=0)
    check: DiagnosticCheck

    @model_validator(mode="after")
    def _validate_report(self) -> RepairEnvelopeValidationReport:
        if self.finding_count != len(self.findings):
            msg = "finding_count must equal the number of findings"
            raise ValueError(msg)
        if self.rows_total != self.readable_rows_checked + self.unreadable_rows_skipped:
            msg = "rows_total must equal readable rows checked plus unreadable rows skipped"
            raise ValueError(msg)
        return self


RepairDecisionOutcome = Literal["preserve", "quarantine", "rebuild", "export_required"]


class RepairRemediationDecision(BaseModel):
    """Durable, non-destructive repair planning decision.

    The record captures operator/engineer intent and evidence prerequisites.
    It never authorizes mutation by itself; actual quarantine/rebuild execution
    requires a later command and additional gates.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decision_id: str = Field(min_length=1)
    target_namespace: str = Field(min_length=1)
    target_object_key_digest: str | None = Field(default=None, min_length=1)
    outcome: RepairDecisionOutcome
    decided_at: datetime
    decided_by: str = Field(default="operator", min_length=1)
    reason: str = Field(min_length=1)
    likely_origin: str = Field(min_length=1)
    replacement_evidence_requirements: tuple[str, ...]
    verified_replacement_evidence_refs: tuple[str, ...] = ()
    mutation_authorized: Literal[False] = False

    @field_validator("decision_id")
    @classmethod
    def _validate_decision_id(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", value):
            msg = "decision_id must be a lowercase sha256 hex digest"
            raise ValueError(msg)
        return value

    @field_validator("target_namespace", "decided_by", "reason", "likely_origin")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="repair remediation decision")
        return value

    @field_validator("target_object_key_digest")
    @classmethod
    def _validate_digest(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[0-9a-f]+", value):
            msg = "target_object_key_digest must be lowercase hex when present"
            raise ValueError(msg)
        return value

    @field_validator("replacement_evidence_requirements", "verified_replacement_evidence_refs")
    @classmethod
    def _validate_safe_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not item:
                msg = "repair decision tuple entries must be non-empty"
                raise ValueError(msg)
            _raise_if_sensitive_context(item, field_name="repair remediation decision")
        return value

    @model_validator(mode="after")
    def _validate_decision(self) -> RepairRemediationDecision:
        if self.outcome != "preserve" and not self.replacement_evidence_requirements:
            msg = "non-preserve outcomes must carry replacement evidence requirements"
            raise ValueError(msg)
        classification = classify_repair_namespace(self.target_namespace)
        if self.outcome == "quarantine" and not classification.destructive_quarantine_allowed:
            msg = "quarantine is disabled for this namespace without a separate engineer override ADR"
            raise ValueError(msg)
        if self.outcome in {"quarantine", "rebuild"} and not self.verified_replacement_evidence_refs:
            msg = "quarantine and rebuild outcomes require verified replacement evidence references"
            raise ValueError(msg)
        expected_id = repair_remediation_decision_id(
            target_namespace=self.target_namespace,
            target_object_key_digest=self.target_object_key_digest,
            outcome=self.outcome,
            decided_at=self.decided_at,
            decided_by=self.decided_by,
            reason=self.reason,
            likely_origin=self.likely_origin,
            replacement_evidence_requirements=self.replacement_evidence_requirements,
            verified_replacement_evidence_refs=self.verified_replacement_evidence_refs,
        )
        if self.decision_id != expected_id:
            msg = "decision_id must match the repair remediation decision content"
            raise ValueError(msg)
        return self


class _RepairRemediationDecisionEnvelopePayload(BaseModel):
    """Encrypted payload wrapper for a repair remediation decision."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decision: RepairRemediationDecision


def repair_remediation_decision_id(
    *,
    target_namespace: str,
    target_object_key_digest: str | None,
    outcome: RepairDecisionOutcome,
    decided_at: datetime,
    decided_by: str = "operator",
    reason: str,
    likely_origin: str,
    replacement_evidence_requirements: tuple[str, ...],
    verified_replacement_evidence_refs: tuple[str, ...] = (),
) -> str:
    """Return a stable opaque id for one repair planning decision."""

    seed = "\x1f".join(
        (
            target_namespace,
            target_object_key_digest or "",
            outcome,
            decided_at.astimezone(UTC).isoformat(),
            decided_by,
            reason,
            likely_origin,
            "\x1e".join(replacement_evidence_requirements),
            "\x1e".join(verified_replacement_evidence_refs),
        )
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def repair_remediation_decision_key(decision_id: str) -> str:
    """Natural key for encrypted repair remediation decisions."""

    if not re.fullmatch(r"[0-9a-f]{64}", decision_id):
        msg = "repair remediation decision id must be a lowercase sha256 hex digest"
        raise ValueError(msg)
    return f"repair-decision:{decision_id}"


class RepairRemediationDecisionRepository(SecureBoundRepository[_RepairRemediationDecisionEnvelopePayload]):
    """Encrypted profile-local repository for non-destructive repair decisions."""

    namespace: ClassVar[str] = "aeat.application.repair.decisions"
    sensitivity: ClassVar[SensitivityClass] = SensitivityClass.AUDIT
    schema_version: ClassVar[int] = 1
    payload_type: ClassVar[type[_RepairRemediationDecisionEnvelopePayload]] = (
        _RepairRemediationDecisionEnvelopePayload
    )

    def extract_identifier(self, payload: _RepairRemediationDecisionEnvelopePayload) -> str:
        return repair_remediation_decision_key(payload.decision.decision_id)

    def save_decision(self, decision: RepairRemediationDecision) -> None:
        """Persist a non-destructive repair planning decision."""

        self.save(_RepairRemediationDecisionEnvelopePayload(decision=decision))

    def load_decision(self, decision_id: str) -> RepairRemediationDecision | None:
        """Load one repair planning decision by opaque decision id."""

        payload = self.load(repair_remediation_decision_key(decision_id))
        return payload.decision if payload is not None else None

    def list_decisions(self) -> tuple[RepairRemediationDecision, ...]:
        """Return persisted repair decisions in decision-time order."""

        return tuple(
            sorted(
                (payload.decision for payload in self.iter_records()),
                key=lambda decision: (decision.decided_at, decision.decision_id),
            )
        )


_SENSITIVE_CONTEXT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[0-9]{8}[A-Z]\b", re.IGNORECASE),
    re.compile(r"\b[XYZ][0-9]{7}[A-Z]\b", re.IGNORECASE),
    re.compile(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b[0-9a-f]{32,}\b", re.IGNORECASE),
)


def _raise_if_sensitive_context(value: str, *, field_name: str) -> None:
    if any(pattern.search(value) for pattern in _SENSITIVE_CONTEXT_PATTERNS):
        msg = f"{field_name} must not contain raw taxpayer, profile, bucket, or digest identifiers"
        raise ValueError(msg)


class RepairListReport(BaseModel):
    """Output of ``aeat config repair list <namespace> [--all|--unreadable]``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    namespace_classification: RepairNamespaceClassification
    integrity: SecureObjectNamespaceIntegrity
    rows: tuple[RepairListRow, ...]
    rows_total: int = Field(ge=0)
    filter_mode: str = Field(min_length=1)


class RepairRemediationPlanItem(BaseModel):
    """One namespace-level dry-run repair remediation recommendation."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    namespace_role: str = Field(min_length=1)
    unreadable_count: int = Field(ge=0)
    likely_origins: tuple[str, ...]
    recommended_outcome: RepairDecisionOutcome
    mutation_allowed: Literal[False] = False
    destructive_quarantine_allowed: bool
    destructive_quarantine_policy: str = Field(min_length=1)
    replacement_evidence_requirements: tuple[str, ...]
    next_action: str = Field(min_length=1)

    @field_validator("namespace", "namespace_role", "destructive_quarantine_policy", "next_action")
    @classmethod
    def _validate_safe_text(cls, value: str) -> str:
        _raise_if_sensitive_context(value, field_name="repair remediation plan")
        return value

    @field_validator("likely_origins", "replacement_evidence_requirements")
    @classmethod
    def _validate_safe_tuple(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for item in value:
            if not item:
                msg = "repair remediation plan tuple entries must be non-empty"
                raise ValueError(msg)
            _raise_if_sensitive_context(item, field_name="repair remediation plan")
        return value


class RepairRemediationPlanReport(BaseModel):
    """Dry-run output of ``aeat config repair plan``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    dry_run: Literal[True] = True
    payload_disclosure: Literal["metadata_only"] = "metadata_only"
    planned_mutations: Literal[0] = 0
    namespaces: tuple[RepairRemediationPlanItem, ...]
    unreadable_total: int = Field(ge=0)
    check: DiagnosticCheck

    @model_validator(mode="after")
    def _validate_report(self) -> RepairRemediationPlanReport:
        if self.unreadable_total != sum(item.unreadable_count for item in self.namespaces):
            msg = "unreadable_total must equal the sum of planned namespace unreadable counts"
            raise ValueError(msg)
        return self


def _aggregate_integrity(
    integrity: tuple[SecureObjectNamespaceIntegrity, ...],
) -> DiagnosticCheck:
    """Render the cross-namespace summary as one DiagnosticCheck row.

    The check honours the 2026-05-14 exhaustiveness lock: ``fail`` /
    ``warn`` rows MUST carry exactly one of ``next_action`` /
    ``dead_end``; ``ok`` rows MUST carry neither.
    """
    readable = sum(item.readable for item in integrity)
    unreadable = sum(item.unreadable for item in integrity)
    if unreadable == 0:
        return DiagnosticCheck(
            name="secure_objects.integrity",
            status="ok",
            summary=(f"{readable} row(s) decryptable across {len(integrity)} namespace(s)"),
        )
    impacted = ", ".join(
        f"{item.namespace} ({item.unreadable}/{item.readable + item.unreadable})"
        for item in integrity
        if item.unreadable
    )
    return DiagnosticCheck(
        name="secure_objects.integrity",
        status="fail",
        summary=f"{unreadable} undecryptable row(s) in: {impacted}",
        next_action=_repair_list_next_action(integrity),
    )


def _repair_list_next_action(integrity: tuple[SecureObjectNamespaceIntegrity, ...]) -> str:
    """Route undecryptable rows to read-only inventory before quarantine."""

    for item in integrity:
        if item.unreadable > 0:
            return f"aeat config repair list {item.namespace} --unreadable"
    return "aeat config repair integrity objects"


def build_repair_integrity_report(
    *,
    namespace: str | None = None,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairIntegrityReport:
    """Probe namespace integrity. When ``namespace`` is set, restrict scope."""
    if repository is not None:
        return _build_repair_integrity_report(namespace=namespace, repository=repository)
    with _best_effort_active_bucket_session():
        return _build_repair_integrity_report(
            namespace=namespace,
            repository=secure_object_repository_for_active_bucket(),
        )


def _build_repair_integrity_report(
    *,
    namespace: str | None,
    repository: _SecureObjectRepositoryProtocol,
) -> RepairIntegrityReport:
    repo = repository
    if namespace is None:
        try:
            namespaces = repo.list_namespaces()
        except (StorageError, SQLAlchemyError):
            namespaces = ()
    else:
        namespaces = (namespace,)
    integrity = tuple(repo.probe_namespace_integrity(ns) for ns in namespaces)
    readable_total = sum(item.readable for item in integrity)
    unreadable_total = sum(item.unreadable for item in integrity)
    return RepairIntegrityReport(
        namespaces=integrity,
        readable_total=readable_total,
        unreadable_total=unreadable_total,
        check=_aggregate_integrity(integrity),
    )


def build_repair_integrity_attribution_report(
    *,
    active_bucket_id: str | None = None,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairIntegrityAttributionReport:
    """Group unreadable secure-object rows by safe metadata only."""
    if repository is not None:
        return _build_repair_integrity_attribution_report(
            active_bucket_id=active_bucket_id,
            repository=repository,
        )
    with _best_effort_active_bucket_session():
        return _build_repair_integrity_attribution_report(
            active_bucket_id=active_bucket_id,
            repository=secure_object_repository_for_active_bucket(),
        )


def _build_repair_integrity_attribution_report(
    *,
    active_bucket_id: str | None,
    repository: _SecureObjectRepositoryProtocol,
) -> RepairIntegrityAttributionReport:
    rows_by_namespace: dict[str, list[RepairUnreadableRowAttribution]] = {}
    for raw in repository.iter_all_records_raw():
        try:
            decrypt_encrypted_bytes_column(raw.payload)
        except DecryptionError as exc:
            context = _repair_row_context(
                raw.namespace,
                object_key_digest=raw.object_key,
                active_bucket_id=active_bucket_id,
            )
            origin = _repair_origin_attribution(raw, context=context)
            rows_by_namespace.setdefault(raw.namespace, []).append(
                RepairUnreadableRowAttribution(
                    namespace=raw.namespace,
                    object_key_digest=raw.object_key.hex(),
                    row_id=raw.row_id,
                    classification=raw.classification,
                    schema_version=raw.schema_version,
                    written_at=raw.written_at,
                    reason=str(exc) or type(exc).__name__,
                    owner_semantics=_owner_semantics_from_key_kind(context.object_key_kind),
                    likely_origin=origin.likely_origin,
                    origin_confidence=origin.confidence,
                    context_bucket_id=context.bucket_id,
                    object_key_kind=context.object_key_kind,
                    object_key_hint=context.object_key_hint,
                    context_confidence=context.confidence,
                    context_note=context.note,
                )
            )
    namespaces = tuple(
        _build_namespace_attribution(namespace, tuple(rows_by_namespace[namespace]))
        for namespace in sorted(rows_by_namespace)
    )
    return RepairIntegrityAttributionReport(
        namespaces=namespaces,
        unreadable_total=sum(namespace.unreadable_count for namespace in namespaces),
    )


def build_repair_remediation_plan(
    *,
    active_bucket_id: str | None = None,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairRemediationPlanReport:
    """Build a metadata-only dry-run remediation plan for degraded rows."""

    if repository is not None:
        attribution = _build_repair_integrity_attribution_report(
            active_bucket_id=active_bucket_id,
            repository=repository,
        )
    else:
        with _best_effort_active_bucket_session():
            attribution = _build_repair_integrity_attribution_report(
                active_bucket_id=active_bucket_id,
                repository=secure_object_repository_for_active_bucket(),
            )
    items = tuple(_remediation_plan_item(namespace) for namespace in attribution.namespaces)
    if attribution.unreadable_total:
        check = DiagnosticCheck(
            name="secure_objects.remediation_plan",
            status="warn",
            summary=(
                f"{attribution.unreadable_total} unreadable secure-object rows require "
                "preserve-first review before remediation"
            ),
            next_action="collect replacement evidence and record repair decisions",
        )
    else:
        check = DiagnosticCheck(
            name="secure_objects.remediation_plan",
            status="ok",
            summary="no unreadable secure-object rows require remediation planning",
        )
    return RepairRemediationPlanReport(
        namespaces=items,
        unreadable_total=attribution.unreadable_total,
        check=check,
    )


def _remediation_plan_item(
    namespace: RepairUnreadableNamespaceAttribution,
) -> RepairRemediationPlanItem:
    classification = namespace.namespace_classification
    requirements = classification.replacement_evidence_requirements
    if requirements:
        recommended_outcome: RepairDecisionOutcome = "export_required"
        next_action = "collect replacement evidence before any quarantine or rebuild decision"
    else:
        recommended_outcome = "preserve"
        next_action = "preserve row and request engineer review before remediation"
    return RepairRemediationPlanItem(
        namespace=namespace.namespace,
        namespace_role=classification.role,
        unreadable_count=namespace.unreadable_count,
        likely_origins=tuple(sorted({row.likely_origin for row in namespace.unreadable_rows})),
        recommended_outcome=recommended_outcome,
        destructive_quarantine_allowed=classification.destructive_quarantine_allowed,
        destructive_quarantine_policy=classification.destructive_quarantine_policy,
        replacement_evidence_requirements=requirements,
        next_action=next_action,
    )


class _RepairOriginAttribution(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    likely_origin: str = Field(min_length=1)
    confidence: str = Field(min_length=1)


def _repair_origin_attribution(
    row: SecureObjectRawRow,
    *,
    context: _RepairRowContext,
) -> _RepairOriginAttribution:
    """Infer a conservative unreadable-row origin from safe metadata only."""

    namespace = row.namespace.casefold()
    namespace_classification = classify_repair_namespace(row.namespace)
    if namespace.startswith(("test.", "tests.")) or ".test." in namespace:
        return _RepairOriginAttribution(
            likely_origin="test_contamination_or_test_namespace_residue",
            confidence="namespace_test_marker",
        )
    if namespace_classification.role == "unknown_secure_object_namespace":
        return _RepairOriginAttribution(
            likely_origin="storage_routing_fault_or_unregistered_repository",
            confidence="unclassified_namespace",
        )
    if context.confidence == "active_key_digest_match":
        if namespace_classification.participates_in_iva_compensation_history:
            return _RepairOriginAttribution(
                likely_origin="active_profile_tax_evidence_payload_key_mismatch",
                confidence="active_key_digest_match",
            )
        return _RepairOriginAttribution(
            likely_origin="active_profile_repository_payload_key_mismatch",
            confidence="active_key_digest_match",
        )
    if "bucket" in context.object_key_kind and not context.bucket_id:
        return _RepairOriginAttribution(
            likely_origin="missing_active_profile_context",
            confidence="bucket_key_without_active_context",
        )
    if context.object_key_kind == "unknown_hmac_digest":
        return _RepairOriginAttribution(
            likely_origin="legacy_migration_or_external_restore_residue",
            confidence="unrecoverable_hmac_digest",
        )
    if namespace_classification.participates_in_iva_compensation_history:
        return _RepairOriginAttribution(
            likely_origin="tax_evidence_keychain_or_restore_mismatch",
            confidence="classified_tax_evidence_namespace",
        )
    return _RepairOriginAttribution(
        likely_origin="repository_keychain_or_restore_mismatch",
        confidence="classified_repository_namespace",
    )


def _build_namespace_attribution(
    namespace: str,
    rows: tuple[RepairUnreadableRowAttribution, ...],
) -> RepairUnreadableNamespaceAttribution:
    classification_counts: dict[str, int] = {}
    for row in rows:
        classification = row.classification or "unknown"
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
    written_at_values = tuple(row.written_at for row in rows if row.written_at is not None)
    return RepairUnreadableNamespaceAttribution(
        namespace=namespace,
        namespace_classification=classify_repair_namespace(namespace),
        owner_semantics=_namespace_owner_semantics(rows),
        classification_groups=tuple(
            RepairUnreadableClassificationGroup(
                classification=classification,
                unreadable_count=count,
            )
            for classification, count in sorted(classification_counts.items())
        ),
        unreadable_rows=rows,
        unreadable_count=len(rows),
        first_written_at=min(written_at_values) if written_at_values else None,
        last_written_at=max(written_at_values) if written_at_values else None,
    )


def _namespace_owner_semantics(rows: tuple[RepairUnreadableRowAttribution, ...]) -> str:
    semantics = {row.owner_semantics for row in rows}
    if len(semantics) == 1:
        return next(iter(semantics))
    return "mixed"


def _owner_semantics_from_key_kind(object_key_kind: str) -> str:
    if object_key_kind.startswith("singleton_") or object_key_kind.startswith("active_"):
        return "singleton"
    if object_key_kind == "unknown_hmac_digest":
        return "unknown"
    return "multirow"


class _RepairEnvelopeContract(BaseModel):
    """Owner contract used to validate one secure-object namespace."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid", arbitrary_types_allowed=True)

    namespace: str = Field(min_length=1)
    expected_classification: SensitivityClass
    max_supported_version: int = Field(ge=1)
    contract_kind: str = Field(min_length=1)
    payload_type: type[BaseModel] | None = None


def build_repair_envelope_validation_report(
    *,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairEnvelopeValidationReport:
    """Validate readable secure-object rows against owner contracts.

    The report is metadata-only: it decrypts readable rows solely to
    validate envelope headers for namespaces with typed envelopes, then
    emits row ids, opaque key digests, contract names, and drift reasons.
    Payload bytes and natural object keys never leave this function.
    """

    if repository is not None:
        return _build_repair_envelope_validation_report(repository=repository)
    with _best_effort_active_bucket_session():
        return _build_repair_envelope_validation_report(repository=secure_object_repository_for_active_bucket())


def _build_repair_envelope_validation_report(
    *,
    repository: _SecureObjectRepositoryProtocol,
) -> RepairEnvelopeValidationReport:
    contracts = _repair_envelope_contracts()
    findings: list[RepairEnvelopeValidationFinding] = []
    rows_total = 0
    readable_rows_checked = 0
    unreadable_rows_skipped = 0
    for raw in repository.iter_all_records_raw():
        rows_total += 1
        try:
            plaintext = decrypt_encrypted_bytes_column(raw.payload)
        except DecryptionError:
            unreadable_rows_skipped += 1
            continue
        readable_rows_checked += 1
        contract = contracts.get(raw.namespace.casefold())
        findings.extend(_validate_readable_row_contract(raw, plaintext=plaintext, contract=contract))
    finding_tuple = tuple(findings)
    return RepairEnvelopeValidationReport(
        rows_total=rows_total,
        readable_rows_checked=readable_rows_checked,
        unreadable_rows_skipped=unreadable_rows_skipped,
        findings=finding_tuple,
        finding_count=len(finding_tuple),
        check=_aggregate_envelope_validation(
            findings=finding_tuple,
            readable_rows_checked=readable_rows_checked,
            unreadable_rows_skipped=unreadable_rows_skipped,
        ),
    )


def _validate_readable_row_contract(
    raw: SecureObjectRawRow,
    *,
    plaintext: bytes,
    contract: _RepairEnvelopeContract | None,
) -> tuple[RepairEnvelopeValidationFinding, ...]:
    if contract is None:
        return (
            _envelope_validation_finding(
                raw,
                finding_type="unknown_owner_contract",
                contract_kind="unknown",
                expected_classification="unknown",
                max_supported_version=1,
                reason="No owner contract is registered for this namespace.",
            ),
        )
    findings: list[RepairEnvelopeValidationFinding] = []
    expected = contract.expected_classification.value
    if raw.classification != expected:
        findings.append(
            _envelope_validation_finding(
                raw,
                finding_type="row_classification_mismatch",
                contract_kind=contract.contract_kind,
                expected_classification=expected,
                max_supported_version=contract.max_supported_version,
                actual_classification=raw.classification,
                actual_schema_version=raw.schema_version,
                reason="Stored row classification differs from the owning repository contract.",
            )
        )
    if raw.schema_version > contract.max_supported_version:
        findings.append(
            _envelope_validation_finding(
                raw,
                finding_type="row_schema_version_unsupported",
                contract_kind=contract.contract_kind,
                expected_classification=expected,
                max_supported_version=contract.max_supported_version,
                actual_classification=raw.classification,
                actual_schema_version=raw.schema_version,
                reason="Stored row schema version is newer than the owning repository supports.",
            )
        )
    if contract.payload_type is None:
        return tuple(findings)
    try:
        envelope = Envelope[contract.payload_type].model_validate_json(plaintext.decode("utf-8"))  # type: ignore[valid-type]
    except (UnicodeDecodeError, ValidationError, ValueError):
        findings.append(
            _envelope_validation_finding(
                raw,
                finding_type="payload_envelope_invalid",
                contract_kind=contract.contract_kind,
                expected_classification=expected,
                max_supported_version=contract.max_supported_version,
                actual_classification=raw.classification,
                actual_schema_version=raw.schema_version,
                reason="Decrypted payload is not a valid typed envelope for the owning repository.",
            )
        )
        return tuple(findings)
    if envelope.classification != contract.expected_classification:
        findings.append(
            _envelope_validation_finding(
                raw,
                finding_type="payload_envelope_classification_mismatch",
                contract_kind=contract.contract_kind,
                expected_classification=expected,
                max_supported_version=contract.max_supported_version,
                actual_classification=envelope.classification.value,
                actual_schema_version=envelope.schema_version,
                reason="Inner envelope classification differs from the owning repository contract.",
            )
        )
    if envelope.schema_version > contract.max_supported_version:
        findings.append(
            _envelope_validation_finding(
                raw,
                finding_type="payload_envelope_schema_version_unsupported",
                contract_kind=contract.contract_kind,
                expected_classification=expected,
                max_supported_version=contract.max_supported_version,
                actual_classification=envelope.classification.value,
                actual_schema_version=envelope.schema_version,
                reason="Inner envelope schema version is newer than the owning repository supports.",
            )
        )
    return tuple(findings)


def _envelope_validation_finding(
    raw: SecureObjectRawRow,
    *,
    finding_type: str,
    contract_kind: str,
    expected_classification: str,
    max_supported_version: int,
    reason: str,
    actual_classification: str | None = None,
    actual_schema_version: int | None = None,
) -> RepairEnvelopeValidationFinding:
    return RepairEnvelopeValidationFinding(
        namespace=raw.namespace,
        object_key_digest=raw.object_key.hex(),
        row_id=raw.row_id,
        finding_type=finding_type,
        contract_kind=contract_kind,
        expected_classification=expected_classification,
        actual_classification=actual_classification,
        max_supported_version=max_supported_version,
        actual_schema_version=actual_schema_version,
        reason=reason,
    )


def _aggregate_envelope_validation(
    *,
    findings: tuple[RepairEnvelopeValidationFinding, ...],
    readable_rows_checked: int,
    unreadable_rows_skipped: int,
) -> DiagnosticCheck:
    if findings:
        namespaces = ", ".join(sorted({finding.namespace for finding in findings}))
        return DiagnosticCheck(
            name="secure_objects.envelope_contracts",
            status="fail",
            summary=f"{len(findings)} readable secure-object contract drift finding(s) in: {namespaces}",
            next_action="aeat config repair integrity attribution",
        )
    if unreadable_rows_skipped:
        return DiagnosticCheck(
            name="secure_objects.envelope_contracts",
            status="warn",
            summary=(
                f"{readable_rows_checked} readable row(s) match owner contracts; "
                f"{unreadable_rows_skipped} unreadable row(s) require attribution first"
            ),
            next_action="aeat config repair integrity attribution",
        )
    return DiagnosticCheck(
        name="secure_objects.envelope_contracts",
        status="ok",
        summary=f"{readable_rows_checked} readable secure-object row(s) match owner contracts",
    )


def _repair_envelope_contracts() -> dict[str, _RepairEnvelopeContract]:
    """Build the active secure-object owner contract map from production owners."""

    from ..adapters.outbound.aeat.auth import CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE
    from ..adapters.outbound.aeat.auth._session_store import (
        _SESSION_NAMESPACE,
        _SESSION_VERSION,
    )
    from ..adapters.outbound.aeat.sede._observation_store import (
        _ARTEFACT_NAMESPACE,
        _IVA_WALLET_OBSERVATION_NAMESPACE,
        _OBSERVATION_ENVELOPE_VERSION,
        _OBSERVATION_NAMESPACE,
    )
    from ..adapters.outbound.aeat.sede._schema import (
        FiledDeclaracionObservation,
        IvaCompensationWalletObservation,
    )
    from ..adapters.outbound.google import _session_store as google_session_store
    from ..adapters.outbound.llm._cache import _CACHE_NAMESPACE, _CACHE_VERSION
    from ..adapters.outbound.llm._usage import _USAGE_NAMESPACE, _USAGE_VERSION
    from ..adapters.persistence.profile.assets import (
        _AMORTIZACION_NAMESPACE,
        _ASSETS_NAMESPACE,
    )
    from ..adapters.persistence.profile.assets import (
        _SECURE_OBJECT_VERSION as _ASSET_SECURE_OBJECT_VERSION,
    )
    from ..adapters.persistence.profile.inventory import (
        _INVENTORY_NAMESPACE,
    )
    from ..adapters.persistence.profile.inventory import (
        _SECURE_OBJECT_VERSION as _INVENTORY_SECURE_OBJECT_VERSION,
    )
    from ..adapters.persistence.storage.attachment import (
        _ATTACHMENT_BLOB_NAMESPACE,
        _ATTACHMENT_BLOB_VERSION,
        _ATTACHMENT_MANIFEST_NAMESPACE,
        _ATTACHMENT_MANIFEST_VERSION,
    )
    from ..domain.attachments import Attachment
    from ..domain.buckets._event import BucketEventHistoryCatalogue
    from ..domain.buckets._event_repository import (
        _CATALOGUE_VERSION as _BUCKET_EVENT_CATALOGUE_VERSION,
    )
    from ..domain.buckets._event_repository import (
        _NAMESPACE as _BUCKET_EVENT_NAMESPACE,
    )
    from ..domain.filing._complementaria_repository import (
        _AMENDMENT_ENVELOPE_VERSION,
        _AMENDMENT_NAMESPACE,
        BaseAmendment,
    )
    from ..domain.filing._repository import ModeloDraftRepository
    from ..domain.invoices._models import InvoiceCatalogue
    from ..domain.invoices._repository import _INVOICE_CATALOGUE_VERSION, _INVOICE_NAMESPACE
    from ..domain.justificante._repository import JustificanteRepository
    from ..domain.modelos._calculation_repository import (
        _CALCULATION_CATALOGUE_VERSION,
        _CALCULATION_NAMESPACE,
    )
    from ..domain.modelos._calculation_revision import CalculationRevisionCatalogue
    from ..domain.modelos._filing_record import ModeloRecordCatalogue
    from ..domain.modelos._filing_repository import _FILING_CATALOGUE_VERSION, _FILING_NAMESPACE
    from ..domain.modelos._verification_report import VerificationReportCatalogue
    from ..domain.modelos._verification_repository import _VERIFICATION_CATALOGUE_VERSION, _VERIFICATION_NAMESPACE
    from ..domain.modelos._work_unit import WorkUnitCatalogue
    from ..domain.submission._repository import SubmissionRepository
    from ..domain.transactions import TX_BUCKET_NAMESPACE
    from ..domain.transactions._models import TransactionCatalogue
    from ..domain.transactions._repository import _TX_CATALOGUE_VERSION
    from ..domain.usage_ratios._model import UsageRatioProfile
    from ..domain.usage_ratios._service import _USAGE_RATIO_NAMESPACE, _USAGE_RATIO_VERSION
    from ..domain.user_profile import UserProfileRecord, UserProfileSnapshot
    from .auth._apoderado import _ApoderadoConfigRepository
    from .calculations._iva_compensation_history import IvaCompensationHistoryRepository
    from .calculations._observations_repository import (
        CalculationObservationRepository,
        IvaWalletDecisionRepository,
    )
    from .filing._history_repository import ModeloHistoryRepository
    from .live._borrador_100 import (
        _BORRADOR_100_SNAPSHOT_VERSION,
        BORRADOR_100_SNAPSHOT_NAMESPACE,
        Borrador100Snapshot,
    )
    from .live._censo import (
        _CENSUS_SNAPSHOT_VERSION,
        CENSUS_SNAPSHOT_NAMESPACE,
        CensoSnapshot,
    )
    from .user_profile._repository import (
        _USER_PROFILE_SNAPSHOT_VERSION,
        _USER_PROFILE_VALUE_VERSION,
        USER_PROFILE_SNAPSHOT_NAMESPACE,
        USER_PROFILE_VALUE_NAMESPACE,
    )
    from .workflow._models import WorkflowResult, WorkflowState
    from .workflow._persistence import (
        _RUN_NAMESPACE,
        _RUN_VERSION,
        _STATE_NAMESPACE,
        _STATE_VERSION,
    )

    def contract(
        namespace: str,
        expected_classification: SensitivityClass,
        max_supported_version: int,
        contract_kind: str,
        payload_type: type[BaseModel] | None = None,
    ) -> _RepairEnvelopeContract:
        return _RepairEnvelopeContract(
            namespace=namespace,
            expected_classification=expected_classification,
            max_supported_version=max_supported_version,
            contract_kind=contract_kind,
            payload_type=payload_type,
        )

    contracts = (
        contract(_STATE_NAMESPACE, SensitivityClass.FINANCIAL, _STATE_VERSION, "typed_envelope", WorkflowState),
        contract(_RUN_NAMESPACE, SensitivityClass.FINANCIAL, _RUN_VERSION, "typed_envelope", WorkflowResult),
        contract(
            _BUCKET_EVENT_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _BUCKET_EVENT_CATALOGUE_VERSION,
            "typed_envelope",
            BucketEventHistoryCatalogue,
        ),
        contract(
            TX_BUCKET_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _TX_CATALOGUE_VERSION,
            "typed_envelope",
            TransactionCatalogue,
        ),
        contract(
            _INVOICE_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _INVOICE_CATALOGUE_VERSION,
            "typed_envelope",
            InvoiceCatalogue,
        ),
        contract(
            WORK_UNIT_NAMESPACE,
            SensitivityClass.FINANCIAL,
            WORK_UNIT_CATALOGUE_VERSION,
            "typed_envelope",
            WorkUnitCatalogue,
        ),
        contract(
            _CALCULATION_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _CALCULATION_CATALOGUE_VERSION,
            "typed_envelope",
            CalculationRevisionCatalogue,
        ),
        contract(
            _FILING_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _FILING_CATALOGUE_VERSION,
            "typed_envelope",
            ModeloRecordCatalogue,
        ),
        contract(
            _VERIFICATION_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _VERIFICATION_CATALOGUE_VERSION,
            "typed_envelope",
            VerificationReportCatalogue,
        ),
        contract(
            _AMENDMENT_NAMESPACE,
            SensitivityClass.AUDIT,
            _AMENDMENT_ENVELOPE_VERSION,
            "typed_envelope",
            BaseAmendment,
        ),
        contract(
            ModeloDraftRepository.namespace,
            ModeloDraftRepository.sensitivity,
            ModeloDraftRepository.schema_version,
            "typed_envelope",
            ModeloDraftRepository.payload_type,
        ),
        contract(
            SubmissionRepository.namespace,
            SubmissionRepository.sensitivity,
            SubmissionRepository.schema_version,
            "typed_envelope",
            SubmissionRepository.payload_type,
        ),
        contract(
            JustificanteRepository.namespace,
            JustificanteRepository.sensitivity,
            JustificanteRepository.schema_version,
            "typed_envelope",
            JustificanteRepository.payload_type,
        ),
        contract(
            ModeloHistoryRepository.namespace,
            ModeloHistoryRepository.sensitivity,
            ModeloHistoryRepository.schema_version,
            "typed_envelope",
            ModeloHistoryRepository.payload_type,
        ),
        contract(
            CalculationObservationRepository.namespace,
            CalculationObservationRepository.sensitivity,
            CalculationObservationRepository.schema_version,
            "typed_envelope",
            CalculationObservationRepository.payload_type,
        ),
        contract(
            IvaWalletDecisionRepository.namespace,
            IvaWalletDecisionRepository.sensitivity,
            IvaWalletDecisionRepository.schema_version,
            "typed_envelope",
            IvaWalletDecisionRepository.payload_type,
        ),
        contract(
            IvaWalletDecisionRepository.history_namespace,
            IvaWalletDecisionRepository.sensitivity,
            IvaWalletDecisionRepository.schema_version,
            "typed_envelope",
            IvaWalletDecisionRepository.payload_type,
        ),
        contract(
            IvaCompensationHistoryRepository.namespace,
            IvaCompensationHistoryRepository.sensitivity,
            IvaCompensationHistoryRepository.schema_version,
            "typed_envelope",
            IvaCompensationHistoryRepository.payload_type,
        ),
        contract(
            _ApoderadoConfigRepository.namespace,
            _ApoderadoConfigRepository.sensitivity,
            _ApoderadoConfigRepository.schema_version,
            "typed_envelope",
            _ApoderadoConfigRepository.payload_type,
        ),
        contract(
            USER_PROFILE_VALUE_NAMESPACE,
            SensitivityClass.IDENTITY,
            _USER_PROFILE_VALUE_VERSION,
            "typed_envelope",
            UserProfileRecord,
        ),
        contract(
            USER_PROFILE_SNAPSHOT_NAMESPACE,
            SensitivityClass.IDENTITY,
            _USER_PROFILE_SNAPSHOT_VERSION,
            "typed_envelope",
            UserProfileSnapshot,
        ),
        contract(
            CENSUS_SNAPSHOT_NAMESPACE,
            SensitivityClass.IDENTITY,
            _CENSUS_SNAPSHOT_VERSION,
            "typed_envelope",
            CensoSnapshot,
        ),
        contract(
            BORRADOR_100_SNAPSHOT_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _BORRADOR_100_SNAPSHOT_VERSION,
            "typed_envelope",
            Borrador100Snapshot,
        ),
        contract(
            _OBSERVATION_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _OBSERVATION_ENVELOPE_VERSION,
            "typed_envelope",
            FiledDeclaracionObservation,
        ),
        contract(
            _IVA_WALLET_OBSERVATION_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _OBSERVATION_ENVELOPE_VERSION,
            "typed_envelope",
            IvaCompensationWalletObservation,
        ),
        contract(
            _USAGE_RATIO_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _USAGE_RATIO_VERSION,
            "typed_envelope",
            UsageRatioProfile,
        ),
        contract(
            _ATTACHMENT_MANIFEST_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _ATTACHMENT_MANIFEST_VERSION,
            "typed_envelope",
            Attachment,
        ),
        contract(_ARTEFACT_NAMESPACE, SensitivityClass.FINANCIAL, 1, "direct_secure_object"),
        contract(
            _ATTACHMENT_BLOB_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _ATTACHMENT_BLOB_VERSION,
            "direct_secure_object",
        ),
        contract(
            _INVENTORY_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _INVENTORY_SECURE_OBJECT_VERSION,
            "direct_secure_object",
        ),
        contract(_ASSETS_NAMESPACE, SensitivityClass.FINANCIAL, _ASSET_SECURE_OBJECT_VERSION, "direct_secure_object"),
        contract(
            _AMORTIZACION_NAMESPACE,
            SensitivityClass.FINANCIAL,
            _ASSET_SECURE_OBJECT_VERSION,
            "direct_secure_object",
        ),
        contract(
            google_session_store._NAMESPACE_CLIENT,
            SensitivityClass.SECRET,
            google_session_store._RECORD_VERSION,
            "direct_secure_object",
        ),
        contract(
            google_session_store._NAMESPACE_TOKEN,
            SensitivityClass.SECRET,
            google_session_store._RECORD_VERSION,
            "direct_secure_object",
        ),
        contract(
            google_session_store._NAMESPACE_METADATA,
            SensitivityClass.FINANCIAL,
            google_session_store._RECORD_VERSION,
            "direct_secure_object",
        ),
        contract(
            google_session_store._NAMESPACE_DRIVE_CONFIG,
            SensitivityClass.FINANCIAL,
            google_session_store._RECORD_VERSION,
            "direct_secure_object",
        ),
        contract(_CACHE_NAMESPACE, SensitivityClass.DIAGNOSTIC, _CACHE_VERSION, "direct_secure_object"),
        contract(_USAGE_NAMESPACE, SensitivityClass.DIAGNOSTIC, _USAGE_VERSION, "direct_secure_object"),
        contract(CLAVE_MOVIL_DIAGNOSTIC_NAMESPACE, SensitivityClass.SESSION, 1, "direct_secure_object"),
        contract(_SESSION_NAMESPACE, SensitivityClass.SESSION, _SESSION_VERSION, "direct_secure_object"),
    )
    return {item.namespace.casefold(): item for item in contracts}


@contextmanager
def _best_effort_active_bucket_session() -> Iterator[None]:
    """Open the active bucket session so integrity probes test decryptability, not bootstrap state."""

    provider: object | None = None
    try:
        from ..adapters.persistence.storage import get_master_key_provider, has_active_bucket_session

        if has_active_bucket_session():
            yield
            return
        provider = get_master_key_provider()
        provider.__enter__()  # type: ignore[attr-defined]
    except StorageError:
        yield
        return
    try:
        yield
    finally:
        provider.__exit__(None, None, None)  # type: ignore[attr-defined]


def build_repair_list_report(
    *,
    namespace: str,
    include_all: bool = False,
    only_unreadable: bool = False,
    active_bucket_id: str | None = None,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairListReport:
    """List object keys stored under ``namespace``.

    ``--all`` returns every key; ``--unreadable`` filters to only the
    rows whose payload cannot be decrypted under the current master
    key. Default behaviour (both flags False) returns the full key set
    but caps the inventory at the integrity-readable count for
    bandwidth control on large namespaces — same as ``--all`` for
    namespaces with no integrity issues.
    """
    if include_all and only_unreadable:
        msg = "build_repair_list_report cannot combine --all and --unreadable; pass one or neither"
        raise ValueError(msg)
    if repository is not None:
        repo = repository
    else:
        with _best_effort_active_bucket_session():
            return build_repair_list_report(
                namespace=namespace,
                include_all=include_all,
                only_unreadable=only_unreadable,
                active_bucket_id=active_bucket_id,
                repository=secure_object_repository_for_active_bucket(),
            )
    integrity = repo.probe_namespace_integrity(namespace)
    rows = _inventory_rows(
        repo,
        namespace=namespace,
        only_unreadable=only_unreadable,
        active_bucket_id=active_bucket_id,
    )
    if only_unreadable:
        filter_mode = "unreadable"
    elif include_all:
        filter_mode = "all"
    else:
        filter_mode = "default"
    return RepairListReport(
        namespace=namespace,
        namespace_classification=classify_repair_namespace(namespace),
        integrity=integrity,
        rows=rows,
        rows_total=len(rows),
        filter_mode=filter_mode,
    )


def _inventory_rows(
    repository: _SecureObjectRepositoryProtocol,
    *,
    namespace: str,
    only_unreadable: bool,
    active_bucket_id: str | None,
) -> tuple[RepairListRow, ...]:
    raw_rows = tuple(row for row in repository.iter_all_records_raw() if row.namespace == namespace)
    if not raw_rows:
        keys = repository.list_keys(namespace)
        context = _repair_row_context(namespace, object_key_digest=None, active_bucket_id=active_bucket_id)
        return tuple(
            RepairListRow(
                namespace=namespace,
                object_key_digest=k,
                context_bucket_id=context.bucket_id,
                object_key_kind=context.object_key_kind,
                object_key_hint=context.object_key_hint,
                context_confidence=context.confidence,
                context_note=context.note,
            )
            for k in keys
        )

    rows: list[RepairListRow] = []
    for raw in raw_rows:
        try:
            decrypt_encrypted_bytes_column(raw.payload)
        except DecryptionError as exc:
            readable = False
            reason = str(exc) or type(exc).__name__
        else:
            readable = True
            reason = ""
        if only_unreadable and readable:
            continue
        context = _repair_row_context(
            raw.namespace,
            object_key_digest=raw.object_key,
            active_bucket_id=active_bucket_id,
        )
        rows.append(
            RepairListRow(
                namespace=raw.namespace,
                object_key_digest=raw.object_key.hex(),
                row_id=raw.row_id,
                classification=raw.classification,
                schema_version=raw.schema_version,
                written_at=raw.written_at,
                readable=readable,
                reason=reason,
                context_bucket_id=context.bucket_id,
                object_key_kind=context.object_key_kind,
                object_key_hint=context.object_key_hint,
                context_confidence=context.confidence,
                context_note=context.note,
            )
        )
    return tuple(rows)


class _RepairRowContext(BaseModel):
    """Non-secret row context derived without decrypting payloads."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    bucket_id: str = ""
    object_key_kind: str = ""
    object_key_hint: str = ""
    digest_key_hint: str = ""
    confidence: str = ""
    note: str = ""


def _repair_row_context(
    namespace: str,
    *,
    object_key_digest: bytes | None,
    active_bucket_id: str | None,
) -> _RepairRowContext:
    key_hint, digest_key_hint, key_kind, note = _namespace_key_context(
        namespace,
        active_bucket_id=active_bucket_id,
    )
    confidence = _context_confidence(key_hint=digest_key_hint, object_key_digest=object_key_digest)
    bucket_id = "active_profile" if active_bucket_id else ""
    return _RepairRowContext(
        bucket_id=bucket_id,
        object_key_kind=key_kind,
        object_key_hint=key_hint,
        digest_key_hint=digest_key_hint,
        confidence=confidence,
        note=note,
    )


def _namespace_key_context(namespace: str, *, active_bucket_id: str | None) -> tuple[str, str, str, str]:
    normalized = namespace.casefold()
    bucket = active_bucket_id.strip() if active_bucket_id else ""
    if normalized in _SINGLETON_CATALOGUE_NAMESPACES:
        return (
            "catalogue",
            "catalogue",
            "singleton_catalogue",
            "Repository contract stores this namespace as one catalogue object.",
        )
    if normalized == "aeat.workflow":
        return (
            "state",
            "state",
            "singleton_workflow_state",
            "Repository contract stores the workflow state singleton.",
        )
    if normalized == "aeat.application.workflow.runs":
        return (
            "",
            "",
            "workflow_run_id",
            "Run id is HMAC-protected; row-level run id is not recoverable here.",
        )
    if normalized == "aeat.domain.transactions.bucket":
        if bucket:
            return (
                "transaction-catalogue:<active-profile>",
                f"transaction-catalogue:{bucket}",
                "active_bucket_transaction_catalogue",
                "Natural key is derived from the active profile bucket; the bucket id is not printed.",
            )
        return (
            "",
            "",
            "bucket_transaction_catalogue",
            "Natural key includes a bucket id, but no active bucket context was supplied.",
        )
    if normalized == "aeat.domain.usage_ratios":
        if bucket:
            return (
                "usage-ratios:<active-profile>",
                f"usage-ratios:{bucket}",
                "active_bucket_usage_ratio_profile",
                "Natural key is derived from the active profile bucket; the bucket id is not printed.",
            )
        return ("", "", "bucket_usage_ratio_profile", "Natural key includes a bucket id.")
    if normalized == "aeat.application.user_profile.value":
        if bucket:
            return (
                "user-profile:<active-profile>",
                f"user-profile:{bucket}",
                "active_profile_value",
                "Natural key is derived from the active profile; the profile id is not printed.",
            )
        return ("", "", "profile_value", "Natural key includes a profile id.")
    if normalized == "aeat.application.user_profile.snapshot":
        return (
            "",
            "",
            "profile_snapshot",
            "Natural key includes profile id and snapshot id; snapshot id is not recoverable from the digest.",
        )
    if normalized == "aeat.auth.apoderado":
        if bucket:
            return (
                "<active-profile>",
                bucket,
                "active_bucket_authorisation_config",
                "Natural key is the active profile bucket; the bucket id is not printed.",
            )
        return ("", "", "bucket_authorisation_config", "Natural key includes a bucket id.")
    for marker, kind, note in _REDACTED_KEY_CONTEXTS:
        if marker in normalized:
            return ("", "", kind, note)
    return ("", "", "unknown_hmac_digest", "Object key is an HMAC digest; natural key is not recoverable here.")


def _context_confidence(*, key_hint: str, object_key_digest: bytes | None) -> str:
    if not key_hint:
        return "unrecoverable_hmac_digest"
    if object_key_digest is None:
        return "repository_contract"
    try:
        if HashedLookup.compute(key_hint) == object_key_digest:
            return "active_key_digest_match"
    except StorageError:
        return "repository_contract_unverified_digest"
    return "repository_contract_unverified_digest"


_SINGLETON_CATALOGUE_NAMESPACES: frozenset[str] = frozenset(
    {
        "aeat.domain.buckets.event_history",
        "aeat.domain.invoices",
        "aeat.domain.modelos.calculation_revisions",
        "aeat.domain.modelos.filing_records",
        "aeat.domain.modelos.verification_reports",
        WORK_UNIT_NAMESPACE,
    }
)


_REDACTED_KEY_CONTEXTS: tuple[tuple[str, str, str], ...] = (
    (
        "filed_declaration.artefacts",
        "filed_declaration_artefact_sha256",
        "Natural key is a source artefact digest; retain the HMAC only in repair output.",
    ),
    (
        "filed_declaration.observations",
        "filed_declaration_observation",
        "Natural key is derived from modelo/year/period/expediente; expediente context is not recoverable here.",
    ),
    (
        "iva_compensation_wallet.observations",
        "iva_wallet_observation",
        "Natural key includes taxpayer and capture context; it is intentionally not printed.",
    ),
    (
        "iva_compensation.history",
        "iva_compensation_period",
        "Natural key is filing year/period; exact period is not recoverable from the digest.",
    ),
    (
        "iva_wallet.reconciliation",
        "iva_wallet_reconciliation_decision",
        "Natural key includes taxpayer and target period; it is intentionally not printed.",
    ),
    (
        "calculations.observations",
        "calculation_observation",
        "Natural key is modelo/year/period; exact period is not recoverable from the digest.",
    ),
    (
        "domain.filing.",
        "filing_domain_record",
        "Natural key is domain-specific filing id; row-level id is not recoverable here.",
    ),
    (
        "application.filing.history",
        "filing_history_record",
        "Natural key is modelo history id; row-level id is not recoverable here.",
    ),
    (
        "domain.submission.",
        "submission_record",
        "Natural key is submission id; row-level id is not recoverable here.",
    ),
    (
        "domain.justificante.",
        "submission_receipt",
        "Natural key is receipt id; row-level id is not recoverable here.",
    ),
    (
        "domain.attachments.blobs",
        "attachment_blob_digest",
        "Natural key is the attachment SHA-256 digest; retain the HMAC only in repair output.",
    ),
    (
        "domain.attachments.manifests",
        "attachment_manifest",
        "Natural key is the attachment id digest; retain the HMAC only in repair output.",
    ),
    (
        "persistence.profile.inventory",
        "profile_inventory_ledger",
        "Natural key is the inventory ledger singleton; ledger contents remain encrypted.",
    ),
    (
        "persistence.profile.assets.amortization",
        "profile_asset_amortization_ledger",
        "Natural key is the amortization ledger singleton; ledger contents remain encrypted.",
    ),
    (
        "persistence.profile.assets",
        "profile_asset_ledger",
        "Natural key is the asset ledger singleton; ledger contents remain encrypted.",
    ),
    (
        "application.live.",
        "live_snapshot",
        "Natural key is snapshot id; row-level id is not recoverable here.",
    ),
    (
        "google.oauth",
        "google_oauth_profile_record",
        "Natural key is the AEAT profile name; profile identity is not printed.",
    ),
    (
        "google.drive.config",
        "google_drive_profile_config",
        "Natural key is the AEAT profile name; profile identity is not printed.",
    ),
    (
        "outbound.aeat.auth",
        "auth_diagnostic",
        "Natural key is diagnostic id; row-level id is not recoverable here.",
    ),
    (
        "outbound.llm.cache",
        "llm_cache_entry",
        "Natural key is cache-derived and may correlate to prompt context; retain only the HMAC.",
    ),
    (
        "outbound.llm.usage",
        "llm_usage_record",
        "Natural key is usage-bucket metadata; row-level id is not recoverable here.",
    ),
)


_IVA_EVIDENCE_NOTE = (
    "Treat unreadable rows as tax evidence until an operator has exported or otherwise "
    "verified replacement evidence; do not quarantine blindly."
)


def classify_repair_namespace(namespace: str) -> RepairNamespaceClassification:
    """Classify a secure-object namespace for read-only repair inventory output."""

    normalized = namespace.casefold()
    for marker, classification in _REPAIR_NAMESPACE_CLASSIFICATIONS:
        if marker in normalized:
            return _with_replacement_requirements(classification)
    return RepairNamespaceClassification(
        role="unknown_secure_object_namespace",
        iva_reconciliation_relevance="unknown",
        participates_in_iva_compensation_history=False,
        destructive_repair_risk="unknown_do_not_quarantine_blindly",
        operator_note=(
            "Namespace is not yet classified; inspect the owning repository before any "
            "destructive repair."
        ),
        replacement_evidence_requirements=(
            "identify_owning_repository_contract",
            "export_encrypted_profile_backup_before_any_change",
            "record_engineer_review_preserve_first_decision",
        ),
        destructive_quarantine_allowed=False,
        destructive_quarantine_policy="disabled_until_namespace_owner_contract_is_registered",
    )


def build_repair_namespace_policy(namespace: str) -> RepairNamespacePolicy:
    """Return the executable repair/recovery policy for one namespace."""

    classification = classify_repair_namespace(namespace)
    return RepairNamespacePolicy(
        namespace=namespace,
        namespace_classification=classification,
        owner_domain=_policy_owner_domain(classification),
        bucket_scope=_policy_bucket_scope(classification),
        sensitivity_class=_policy_sensitivity_class(classification),
        repair_policy=_policy_repair_policy(classification),
        recovery_policy=_policy_recovery_policy(classification),
        mutation_authority=_policy_mutation_authority(classification),
        export_policy=_policy_export_policy(classification),
        import_policy=_policy_import_policy(classification),
        retention_legal_note=_policy_retention_legal_note(classification),
        calculation_confidence_impact=_policy_calculation_confidence_impact(classification),
    )


def _policy_owner_domain(classification: RepairNamespaceClassification) -> str:
    role = classification.role.casefold()
    if "wallet" in role:
        return "iva_wallet_remote_state"
    if "filed" in role or "filing_history" in role:
        return "filing_history"
    if "submission" in role or "receipt" in role:
        return "submission_and_receipt"
    if "ledger" in role:
        return "ledger"
    if "invoice" in role:
        return "invoices"
    if "modelo" in role or "calculation" in role:
        return "modelo_calculation"
    if "profile" in role:
        return "profile"
    if "auth" in role:
        return "auth"
    if "bucket" in role:
        return "bucket"
    if "workflow" in role:
        return "workflow"
    if "unknown" in role:
        return "unknown"
    return "operational_support"


def _policy_bucket_scope(classification: RepairNamespaceClassification) -> str:
    role = classification.role.casefold()
    if "unknown" in role:
        return "unregistered_preserve_first"
    if "google" in role or "remote" in classification.iva_reconciliation_relevance.casefold():
        return "profile_bucket_with_remote_authority_context"
    if "auth" in role:
        return "profile_bucket_authorisation_context"
    return "profile_bucket"


def _policy_sensitivity_class(classification: RepairNamespaceClassification) -> str:
    role = classification.role.casefold()
    relevance = classification.iva_reconciliation_relevance.casefold()
    if any(fragment in role for fragment in ("ledger", "invoice", "wallet", "filing", "submission", "receipt")):
        return SensitivityClass.FINANCIAL.value
    if "auth" in role:
        return SensitivityClass.SESSION.value
    if "profile" in role:
        return SensitivityClass.IDENTITY.value
    if "audit" in role or "event" in role or "decision" in role:
        return SensitivityClass.AUDIT.value
    if "remote" in relevance:
        return SensitivityClass.FINANCIAL.value
    return SensitivityClass.OPERATIONAL.value


def _policy_repair_policy(classification: RepairNamespaceClassification) -> str:
    if classification.role == "unknown_secure_object_namespace":
        return "preserve_until_owner_repository_policy_registered"
    if not classification.destructive_quarantine_allowed:
        return "preserve_only_no_quarantine_without_engineer_override_adr"
    if classification.replacement_evidence_requirements:
        return "preserve_first_verified_replacement_evidence_required"
    return "preserve_first_owner_review_required"


def _policy_recovery_policy(classification: RepairNamespaceClassification) -> str:
    role = classification.role.casefold()
    relevance = classification.iva_reconciliation_relevance.casefold()
    if "wallet" in role:
        return "recover_by_read_only_wallet_capture_or_verified_export"
    if "filed" in role or "filing_history" in relevance:
        return "recover_by_read_only_filed_history_redownload_or_verified_export"
    if "submission" in role or "receipt" in role:
        return "recover_by_verified_aeat_sede_receipt_or_csv_copy"
    if "ledger" in role or "invoice" in role:
        return "recover_by_reimporting_verified_source_files_and_replaying_calculations"
    if "modelo" in role or "calculation" in role:
        return "recover_by_replaying_modelo_work_units_from_source_observations"
    if "profile" in role:
        return "recover_by_profile_manifest_pointer_and_operator_verified_profile_facts"
    if "auth" in role or "google" in role:
        return "recover_by_reauthorising_operational_session"
    if "unknown" in role:
        return "recover_only_after_owner_repository_contract_is_identified"
    return "recover_by_owner_domain_review_and_verified_rebuild"


def _policy_mutation_authority(classification: RepairNamespaceClassification) -> str:
    if not classification.destructive_quarantine_allowed:
        return classification.destructive_quarantine_policy
    return "dry_run_then_verified_evidence_then_explicit_operator_confirmation"


def _policy_export_policy(classification: RepairNamespaceClassification) -> str:
    role = classification.role.casefold()
    if "auth" in role:
        return "export_redacted_diagnostics_only"
    if "unknown" in role:
        return "export_encrypted_backup_before_owner_review"
    if any(fragment in role for fragment in ("ledger", "invoice", "wallet", "filing", "submission", "receipt")):
        return "export_encrypted_or_operator_requested_redacted_evidence_only"
    return "export_encrypted_backup_or_redacted_operational_summary"


def _policy_import_policy(classification: RepairNamespaceClassification) -> str:
    role = classification.role.casefold()
    if "unknown" in role:
        return "import_disabled_until_namespace_policy_registered"
    if "auth" in role:
        return "import_disabled_reauthorise_instead"
    if any(fragment in role for fragment in ("ledger", "invoice", "modelo", "calculation")):
        return "import_validated_source_evidence_then_replay_domain_projection"
    if any(fragment in role for fragment in ("wallet", "filed", "submission", "receipt")):
        return "import_only_verified_external_evidence_or_encrypted_restore"
    return "import_only_through_owner_repository_policy"


def _policy_retention_legal_note(classification: RepairNamespaceClassification) -> str:
    role = classification.role.casefold()
    if any(fragment in role for fragment in ("ledger", "invoice", "submission", "receipt", "filed")):
        return "tax_supporting_evidence_preserve_for_statutory_retention_window"
    if "wallet" in role or classification.participates_in_iva_compensation_history:
        return "iva_compensation_evidence_preserve_until_multiyear_reconciliation_closed"
    if "auth" in role:
        return "operational_authorisation_context_preserve_until_live_capture_reviewed"
    return "operational_context_preserve_until_owner_reviewed"


def _policy_calculation_confidence_impact(classification: RepairNamespaceClassification) -> str:
    relevance = classification.iva_reconciliation_relevance.casefold()
    role = classification.role.casefold()
    if "remote_wallet" in relevance or "wallet" in role:
        return "degrades_aeat_remote_wallet_authority"
    if "filing_history" in relevance or "filed" in role:
        return "degrades_filed_history_and_multiyear_carry_forward"
    if "ledger" in role or "invoice" in role:
        return "degrades_ledger_periodic_iva_and_yearly_summary"
    if "modelo" in role or "calculation" in role:
        return "degrades_modelo_303_390_and_export_readiness"
    if "profile" in role:
        return "degrades_profile_context_and_source_resolution"
    if classification.participates_in_iva_compensation_history:
        return "degrades_iva_compensation_reconciliation"
    return "no_direct_calculation_confidence_impact"


_ADR_SECURE_STORAGE = "[[2026-05-22-secure-storage-production-hardening-architecture-adr]]"
_ADR_CONFIG_REPAIR = "[[2026-05-13-cli-workflow-redesign-config-repair-shape-adr]]"
_ADR_BUCKET = "[[2026-05-12-cli-workflow-redesign-bucket-adr]]"
_ADR_CUSTODY = "[[2026-05-14-secure-backend-passkey-custody-adr]]"
_ADR_PROFILE_BUCKET = (
    "[[2026-05-22-live-iva-compensation-wallet-profile-bucket-repository-binding-reconciliation-adr]]"
)
_ADR_LIVE_WALLET = "[[2026-05-19-live-iva-compensation-wallet-adr]]"
_ADR_SECURE_PERSISTENCE = "[[2026-05-06-secure-persistence-enforcement-adr]]"

_NS_BUCKET_EVENTS = "aeat.domain.buckets.event_history"
_NS_CALCULATION_REVISIONS = "aeat.domain.modelos.calculation_revisions"
_NS_FILING_HISTORY = "aeat.application.filing.history"
_NS_FILING_RECORDS = "aeat.domain.modelos.filing_records"
_NS_INVOICES = "aeat.domain.invoices"
_NS_MODELO_WORK_UNITS = WORK_UNIT_NAMESPACE
_NS_SUBMISSION_RECORDS = "aeat.domain.submission.records"
_NS_TRANSACTIONS = "aeat.domain.transactions.bucket"
_NS_USER_PROFILE_SNAPSHOT = "aeat.application.user_profile.snapshot"
_NS_USER_PROFILE_VALUE = "aeat.application.user_profile.value"
_NS_WORKFLOW = "aeat.workflow"


def build_repair_policy_command_surface_catalog() -> tuple[RepairPolicyCommandSurface, ...]:
    """Return policy coverage for repair, recovery, import, export, and bucket commands."""

    surfaces = (
        _command_surface(
            "config repair logs",
            "repair",
            owner_domains=("diagnostics", "operator_support"),
            mutation_policy="read_only_log_inventory",
            redaction_policy="log_output_may_contain_prior_local_diagnostics_operator_review_required",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE),
        ),
        _command_surface(
            "config repair quarantine",
            "repair",
            owner_domains=("securestorage", "cross_domain_tax_evidence"),
            mutation_policy="non_dry_run_refused_preserve_first",
            redaction_policy="metadata_only_no_payloads_no_natural_keys",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE, _ADR_SECURE_PERSISTENCE),
        ),
        _command_surface(
            "config repair reset-state",
            "recovery",
            owner_domains=("workflow",),
            governed_namespaces=(_NS_WORKFLOW,),
            mutation_policy="requires_yes_or_dry_run_single_workflow_state_reset",
            redaction_policy="metadata_fingerprint_only",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE, _ADR_PROFILE_BUCKET),
        ),
        _command_surface(
            "config repair profile",
            "recovery",
            owner_domains=("profile", "bucket"),
            governed_namespaces=(_NS_USER_PROFILE_VALUE, _NS_USER_PROFILE_SNAPSHOT, _NS_WORKFLOW),
            mutation_policy="profile_pointer_repair_requires_explicit_operator_confirmation",
            redaction_policy="profile_uuid_and_tax_id_redacted_in_public_output",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_BUCKET, _ADR_PROFILE_BUCKET),
        ),
        _command_surface(
            "config repair integrity objects",
            "repair",
            owner_domains=("securestorage",),
            mutation_policy="read_only_decryptability_probe",
            redaction_policy="namespace_counts_only",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE, _ADR_SECURE_PERSISTENCE),
        ),
        _command_surface(
            "config repair integrity attribution",
            "repair",
            owner_domains=("securestorage", "cross_domain_tax_evidence"),
            mutation_policy="read_only_metadata_attribution",
            redaction_policy="metadata_only_no_payloads_no_taxpayer_ids_no_profile_uuids",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE, _ADR_LIVE_WALLET),
        ),
        _command_surface(
            "config repair integrity registry",
            "repair",
            owner_domains=("registry", "calculation"),
            mutation_policy="read_only_registry_validation",
            redaction_policy="registry_metadata_only",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE),
        ),
        _command_surface(
            "config repair plan",
            "repair",
            owner_domains=("securestorage", "cross_domain_tax_evidence"),
            mutation_policy="dry_run_preserve_first_planned_mutations_zero",
            redaction_policy="metadata_only_replacement_evidence_requirements",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE, _ADR_LIVE_WALLET),
        ),
        _command_surface(
            "config repair list",
            "repair",
            owner_domains=("securestorage",),
            mutation_policy="read_only_inventory",
            redaction_policy="hmac_digest_and_redacted_context_only",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE, _ADR_SECURE_PERSISTENCE),
        ),
        _command_surface(
            "config repair connectivity",
            "repair",
            owner_domains=("diagnostics", "operator_support"),
            mutation_policy="read_only_connectivity_probe",
            redaction_policy="diagnostic_summary_only",
            adr_links=(_ADR_CONFIG_REPAIR, _ADR_SECURE_STORAGE),
        ),
        _command_surface(
            "config bucket history",
            "bucket",
            owner_domains=("bucket", "audit"),
            governed_namespaces=(_NS_BUCKET_EVENTS,),
            mutation_policy="read_only_bucket_event_history",
            redaction_policy="event_metadata_only",
            adr_links=(_ADR_BUCKET, _ADR_PROFILE_BUCKET, _ADR_SECURE_STORAGE),
        ),
        _command_surface(
            "config profile export",
            "export",
            owner_domains=("profile", "bucket"),
            governed_namespaces=(_NS_USER_PROFILE_VALUE, _NS_USER_PROFILE_SNAPSHOT),
            mutation_policy="operator_requested_file_export_no_storage_mutation",
            redaction_policy="portable_profile_bundle_explicit_operator_destination",
            adr_links=(_ADR_BUCKET, _ADR_PROFILE_BUCKET, _ADR_CUSTODY),
        ),
        _command_surface(
            "config profile import",
            "import",
            owner_domains=("profile", "bucket"),
            governed_namespaces=(_NS_USER_PROFILE_VALUE, _NS_USER_PROFILE_SNAPSHOT, _NS_WORKFLOW),
            mutation_policy="atomic_new_bucket_import_with_rollback",
            redaction_policy="profile_bundle_read_from_operator_supplied_path",
            adr_links=(_ADR_BUCKET, _ADR_PROFILE_BUCKET, _ADR_CUSTODY),
        ),
        _command_surface(
            "app ledger export",
            "export",
            owner_domains=("ledger",),
            governed_namespaces=(_NS_TRANSACTIONS,),
            mutation_policy="operator_requested_ledger_file_export",
            redaction_policy="export_payload_written_only_to_operator_destination",
            adr_links=(_ADR_BUCKET, _ADR_PROFILE_BUCKET, _ADR_SECURE_PERSISTENCE),
        ),
        _command_surface(
            "app ledger import",
            "import",
            owner_domains=("ledger",),
            governed_namespaces=(_NS_TRANSACTIONS,),
            mutation_policy="dry_run_available_non_dry_run_profile_bucket_import",
            redaction_policy="source_file_path_and_import_counts_only",
            adr_links=(_ADR_BUCKET, _ADR_PROFILE_BUCKET, _ADR_SECURE_PERSISTENCE),
        ),
        _command_surface(
            "app modelo export",
            "export",
            owner_domains=("modelo_calculation", "filing"),
            governed_namespaces=(
                _NS_CALCULATION_REVISIONS,
                _NS_FILING_HISTORY,
                _NS_FILING_RECORDS,
                _NS_MODELO_WORK_UNITS,
            ),
            mutation_policy="filing_grade_export_blocked_by_degraded_evidence",
            redaction_policy="operator_requested_export_path_and_readiness_summary",
            adr_links=(_ADR_SECURE_STORAGE, _ADR_PROFILE_BUCKET, _ADR_LIVE_WALLET),
        ),
        _command_surface(
            "app modelo filing-record import",
            "import",
            owner_domains=("modelo_calculation", "filing"),
            governed_namespaces=(_NS_FILING_RECORDS, _NS_SUBMISSION_RECORDS, _NS_MODELO_WORK_UNITS),
            mutation_policy="external_filing_evidence_import_requires_work_unit_binding",
            redaction_policy="evidence_reference_metadata_only",
            adr_links=(_ADR_SECURE_STORAGE, _ADR_PROFILE_BUCKET, _ADR_LIVE_WALLET),
        ),
        _command_surface(
            "app modelo audit export",
            "export",
            owner_domains=("modelo_calculation", "filing", "audit"),
            governed_namespaces=(_NS_CALCULATION_REVISIONS, _NS_FILING_RECORDS, _NS_INVOICES, _NS_TRANSACTIONS),
            mutation_policy="operator_requested_evidence_bundle_export",
            redaction_policy="bundle_manifest_and_operator_destination",
            adr_links=(_ADR_SECURE_STORAGE, _ADR_PROFILE_BUCKET, _ADR_SECURE_PERSISTENCE),
        ),
    )
    return tuple(sorted(surfaces, key=lambda surface: surface.command_path))


def _command_surface(
    command_path: str,
    command_family: RepairPolicyCommandFamily,
    *,
    owner_domains: tuple[str, ...],
    governed_namespaces: tuple[str, ...] = (),
    mutation_policy: str,
    redaction_policy: str,
    adr_links: tuple[str, ...],
) -> RepairPolicyCommandSurface:
    return RepairPolicyCommandSurface(
        command_path=command_path,
        command_family=command_family,
        owner_domains=owner_domains,
        governed_namespaces=governed_namespaces,
        mutation_policy=mutation_policy,
        redaction_policy=redaction_policy,
        adr_links=adr_links,
    )


def _with_replacement_requirements(
    classification: RepairNamespaceClassification,
) -> RepairNamespaceClassification:
    """Attach preserve-first evidence requirements to a namespace classification."""

    quarantine_allowed = _destructive_quarantine_allowed_for_role(
        role=classification.role,
        relevance=classification.iva_reconciliation_relevance,
        risk=classification.destructive_repair_risk,
    )
    if classification.replacement_evidence_requirements:
        return classification.model_copy(
            update={
                "destructive_quarantine_allowed": quarantine_allowed,
                "destructive_quarantine_policy": (
                    "verified_replacement_evidence_required"
                    if quarantine_allowed
                    else "disabled_without_engineer_override_adr"
                ),
            }
        )
    return classification.model_copy(
        update={
            "replacement_evidence_requirements": _replacement_requirements_for_role(
                role=classification.role,
                relevance=classification.iva_reconciliation_relevance,
                risk=classification.destructive_repair_risk,
            ),
            "destructive_quarantine_allowed": quarantine_allowed,
            "destructive_quarantine_policy": (
                "verified_replacement_evidence_required"
                if quarantine_allowed
                else "disabled_without_engineer_override_adr"
            ),
        }
    )


def _destructive_quarantine_allowed_for_role(
    *,
    role: str,
    relevance: str,
    risk: str,
) -> bool:
    """Return whether a namespace may ever be proposed for quarantine."""

    normalized_role = role.casefold()
    normalized_relevance = relevance.casefold()
    normalized_risk = risk.casefold()
    protected_role_fragments = (
        "submission_record",
        "submission_receipt",
        "filed_declaration",
        "filing_history",
    )
    if any(fragment in normalized_role for fragment in protected_role_fragments):
        return False
    if "filing_history" in normalized_relevance:
        return False
    return "critical_preserve_submission" not in normalized_risk


def _replacement_requirements_for_role(
    *,
    role: str,
    relevance: str,
    risk: str,
) -> tuple[str, ...]:
    """Return metadata-only evidence prerequisites for safe remediation planning."""

    normalized_role = role.casefold()
    normalized_relevance = relevance.casefold()
    normalized_risk = risk.casefold()
    common = (
        "export_encrypted_profile_backup_before_any_change",
        "record_operator_preserve_first_decision",
    )
    if "critical" in normalized_risk or "submission" in normalized_role or "receipt" in normalized_role:
        return (
            *common,
            "verify_filed_declaration_or_receipt_copy_from_aeat_sede",
            "record_csv_or_justificante_reference_before_quarantine",
            "disable_destructive_quarantine_without_engineer_override_adr",
        )
    if "wallet" in normalized_role or "remote_wallet" in normalized_relevance:
        return (
            *common,
            "capture_fresh_read_only_aeat_wallet_observation_or_export_existing_observation",
            "replay_wallet_reconciliation_decision_from_verified_evidence",
            "record_taxpayer_override_reason_if_wallet_value_is_not_selected",
        )
    if "filed" in normalized_role or "filing_history" in normalized_relevance:
        return (
            *common,
            "capture_or_redownload_filed_history_from_aeat_sede_read_only",
            "rebuild_calculation_observations_from_verified_filed_history",
            "compare_rebuilt_history_to_multiyear_compensation_chain",
        )
    if "ledger" in normalized_role or "invoice" in normalized_role:
        return (
            *common,
            "verify_bank_import_or_invoice_source_files_are_available",
            "reconcile_rebuilt_ledger_invoice_links_against_current_profile",
            "replay_modelo_303_and_modelo_390_calculations_before_quarantine",
        )
    if "modelo" in normalized_role or "calculation" in normalized_role:
        return (
            *common,
            "replay_modelo_work_units_and_calculation_revisions_from_source_evidence",
            "verify_export_and_filing_readiness_gates_after_replay",
            "compare_replayed_outputs_to_prior_audit_events_where_available",
        )
    if "profile" in normalized_role:
        return (
            *common,
            "verify_profile_manifest_pointer_and_encrypted_record_agree",
            "recreate_profile_context_from_operator_verified_facts",
            "verify_auth_and_calculation_projection_after_rebuild",
        )
    if "auth" in normalized_role or "google" in normalized_role or "llm" in normalized_role:
        return (
            *common,
            "confirm_operational_state_can_be_reauthorized_or_rebuilt",
            "verify_no_tax_evidence_namespace_depends_on_this_row",
        )
    return (
        *common,
        "identify_owning_repository_contract",
        "verify_replacement_evidence_for_affected_domain",
    )


_REPAIR_NAMESPACE_CLASSIFICATIONS: tuple[tuple[str, RepairNamespaceClassification], ...] = (
    (
        "iva_compensation_wallet.observations",
        RepairNamespaceClassification(
            role="aeat_remote_wallet_observation",
            iva_reconciliation_relevance="remote_wallet_balance_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_wallet_reconciliation_exported",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "filed_declaration.",
        RepairNamespaceClassification(
            role="aeat_remote_filed_declaration_evidence",
            iva_reconciliation_relevance="remote_filing_history_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_filing_history_reviewed",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "iva_compensation.history",
        RepairNamespaceClassification(
            role="local_iva_compensation_history",
            iva_reconciliation_relevance="carry_forward_history_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_multiyear_history_rebuilt",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "iva_wallet.reconciliation",
        RepairNamespaceClassification(
            role="local_wallet_reconciliation_decision",
            iva_reconciliation_relevance="wallet_authority_decision_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_decision_history_reviewed",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "calculations.observations",
        RepairNamespaceClassification(
            role="local_calculation_observation",
            iva_reconciliation_relevance="calculation_source_observation",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_calculation_revision_rebuilt",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.modelos.",
        RepairNamespaceClassification(
            role="modelo_calculation_and_filing_state",
            iva_reconciliation_relevance="periodic_and_yearly_form_state",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_modelo_state_reviewed",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.filing.",
        RepairNamespaceClassification(
            role="local_filing_workflow_state",
            iva_reconciliation_relevance="filing_history_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_filing_state_reviewed",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "application.filing.history",
        RepairNamespaceClassification(
            role="local_filing_history",
            iva_reconciliation_relevance="filing_history_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_filing_history_reviewed",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.submission.",
        RepairNamespaceClassification(
            role="submission_record",
            iva_reconciliation_relevance="filing_submission_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="critical_preserve_submission_records",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.justificante.",
        RepairNamespaceClassification(
            role="submission_receipt_metadata",
            iva_reconciliation_relevance="filing_submission_receipt_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="critical_preserve_submission_receipts",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.attachments.",
        RepairNamespaceClassification(
            role="filing_attachment_store",
            iva_reconciliation_relevance="filing_attachment_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="critical_preserve_attachment_evidence",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.transactions.bucket",
        RepairNamespaceClassification(
            role="ledger_transaction_catalogue",
            iva_reconciliation_relevance="ledger_source_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_ledger_reconciled",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.usage_ratios",
        RepairNamespaceClassification(
            role="usage_ratio_profile",
            iva_reconciliation_relevance="expense_deductibility_allocation_context",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_usage_ratios_rebuilt",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.invoices",
        RepairNamespaceClassification(
            role="invoice_catalogue",
            iva_reconciliation_relevance="invoice_source_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_invoice_ledger_reconciled",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "domain.buckets.event_history",
        RepairNamespaceClassification(
            role="bucket_event_history",
            iva_reconciliation_relevance="workspace_provenance_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="medium_preserve_until_event_history_reviewed",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "persistence.profile.inventory",
        RepairNamespaceClassification(
            role="profile_inventory_ledger",
            iva_reconciliation_relevance="inventory_cost_and_stock_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_inventory_ledger_reconciled",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "persistence.profile.assets.amortization",
        RepairNamespaceClassification(
            role="profile_asset_amortization_ledger",
            iva_reconciliation_relevance="asset_amortization_and_deduction_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_asset_amortization_reconciled",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "persistence.profile.assets",
        RepairNamespaceClassification(
            role="profile_asset_ledger",
            iva_reconciliation_relevance="asset_amortization_and_deduction_evidence",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_asset_ledger_reconciled",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "application.repair.decisions",
        RepairNamespaceClassification(
            role="repair_remediation_decision",
            iva_reconciliation_relevance="repair_and_calculation_confidence_context",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="medium_preserve_until_remediation_plan_reviewed",
            operator_note=(
                "Repair decision rows record non-destructive planning intent; preserve them "
                "with the affected evidence until the remediation plan is complete."
            ),
        ),
    ),
    (
        "application.user_profile.",
        RepairNamespaceClassification(
            role="user_profile_state",
            iva_reconciliation_relevance="calculation_profile_context",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="medium_preserve_until_profile_context_rebuilt",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "application.live.",
        RepairNamespaceClassification(
            role="remote_state_snapshot",
            iva_reconciliation_relevance="remote_state_reconciliation_context",
            participates_in_iva_compensation_history=True,
            destructive_repair_risk="high_preserve_until_remote_snapshot_reviewed",
            operator_note=_IVA_EVIDENCE_NOTE,
        ),
    ),
    (
        "google.oauth",
        RepairNamespaceClassification(
            role="google_oauth_session_state",
            iva_reconciliation_relevance="remote_storage_operational_context",
            participates_in_iva_compensation_history=False,
            destructive_repair_risk="medium_preserve_until_remote_sync_state_reviewed",
            operator_note=(
                "Google OAuth rows may gate Drive sync access; do not quarantine before "
                "confirming the profile can be re-authorized."
            ),
        ),
    ),
    (
        "google.drive.config",
        RepairNamespaceClassification(
            role="google_drive_sync_configuration",
            iva_reconciliation_relevance="remote_storage_operational_context",
            participates_in_iva_compensation_history=False,
            destructive_repair_risk="medium_preserve_until_remote_sync_state_reviewed",
            operator_note=(
                "Drive configuration rows route ciphertext backups; preserve them until "
                "the operator has confirmed or rebuilt the remote storage target."
            ),
        ),
    ),
    (
        "outbound.aeat.auth",
        RepairNamespaceClassification(
            role="live_auth_diagnostic_state",
            iva_reconciliation_relevance="live_capture_operational_context",
            participates_in_iva_compensation_history=False,
            destructive_repair_risk="medium_preserve_until_auth_diagnostics_reviewed",
            operator_note=(
                "Auth diagnostic rows can contain operational context for live evidence capture; "
                "do not quarantine before reviewing diagnostic ids and timestamps."
            ),
        ),
    ),
    (
        "outbound.llm.",
        RepairNamespaceClassification(
            role="llm_operational_cache_and_usage",
            iva_reconciliation_relevance="operator_assistance_operational_context",
            participates_in_iva_compensation_history=False,
            destructive_repair_risk="low_preserve_until_operator_confirms_cache_rebuild_ok",
            operator_note=(
                "LLM cache and usage rows are operational support data; preserve until the "
                "operator has confirmed cache loss and usage-audit impact are acceptable."
            ),
        ),
    ),
    (
        "aeat.auth.",
        RepairNamespaceClassification(
            role="auth_authorisation_state",
            iva_reconciliation_relevance="live_capture_authorisation_context",
            participates_in_iva_compensation_history=False,
            destructive_repair_risk="medium_preserve_until_authorisation_state_reviewed",
            operator_note=(
                "Authorisation rows can determine who was represented during live capture; "
                "do not quarantine before reviewing authority context."
            ),
        ),
    ),
    (
        "aeat.workflow",
        RepairNamespaceClassification(
            role="workflow_runtime_state",
            iva_reconciliation_relevance="workflow_context",
            participates_in_iva_compensation_history=False,
            destructive_repair_risk="medium_preserve_until_workflow_state_reviewed",
            operator_note="Workflow rows may be reconstructable, but require owner review before quarantine.",
        ),
    ),
    (
        "application.workflow.",
        RepairNamespaceClassification(
            role="workflow_runtime_state",
            iva_reconciliation_relevance="workflow_context",
            participates_in_iva_compensation_history=False,
            destructive_repair_risk="medium_preserve_until_workflow_state_reviewed",
            operator_note="Workflow rows may be reconstructable, but require owner review before quarantine.",
        ),
    ),
)


__all__ = [
    "RepairEnvelopeValidationFinding",
    "RepairEnvelopeValidationReport",
    "RepairIntegrityAttributionReport",
    "RepairIntegrityReport",
    "RepairListReport",
    "RepairListRow",
    "RepairNamespaceClassification",
    "RepairNamespacePolicy",
    "RepairPolicyCommandSurface",
    "RepairRemediationDecision",
    "RepairRemediationDecisionRepository",
    "RepairRemediationPlanItem",
    "RepairRemediationPlanReport",
    "RepairUnreadableClassificationGroup",
    "RepairUnreadableNamespaceAttribution",
    "RepairUnreadableRowAttribution",
    "build_repair_envelope_validation_report",
    "build_repair_integrity_attribution_report",
    "build_repair_integrity_report",
    "build_repair_list_report",
    "build_repair_namespace_policy",
    "build_repair_policy_command_surface_catalog",
    "build_repair_remediation_plan",
    "classify_repair_namespace",
    "repair_remediation_decision_id",
    "repair_remediation_decision_key",
]
