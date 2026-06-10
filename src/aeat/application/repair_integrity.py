"""Backend services for secure-object integrity and inventory diagnostics.

Implements the subverbs for configuration repair and integrity checks. Each function
returns a strict Pydantic report consumed by the CLI's ``_emit``
renderer; both functions are read-only and emit no bucket events. Integrity
sweeps iterate every namespace inside a :class:`SecureObjectRepository` to
assess decryptability and produce per-namespace counts.

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

Repair-remediation decisions are non-destructive planning records
persisted as encrypted AUDIT-class secure-object rows in a
profile-local namespace. The full preserve/quarantine/rebuild/
export-required semantics and repair-policy command-surface catalog
live here; the design mandates that mutation is never authorised
from a decision record alone.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..adapters.persistence.storage import (
    REPAIR_INTEGRITY_DECISION_NAMESPACE as REPAIR_DECISION_STORAGE_NAMESPACE,
)
from ..adapters.persistence.storage import (
    STORAGE_NAMESPACE_REGISTRY,
    WORKFLOW_STATE_NAMESPACE,
    SecureObjectNamespaceDefinition,
)
from ..adapters.persistence.storage.sql.secure_objects import (
    SecureObjectDecryptabilityRow,
    SecureObjectNamespaceIntegrity,
    SecureObjectRepository,
)
from ..core.errors import CoreError
from ..core.logging import get_logger
from .diagnostics import DiagnosticCheck

_log = get_logger(__name__)


class RepairIntegrityError(CoreError):
    """Base error for secure-object integrity and repair-remediation failures.

    Raised by the repair-integrity application layer when an integrity
    invariant or remediation contract is violated. Inherits from
    :class:`aeat.core.errors.CoreError` so callers can catch either the
    specific subclass or the broad domain base without importing the full
    repair-integrity module.
    """


class RepairDecisionNotFoundError(RepairIntegrityError):
    """Raised when a repair-remediation decision lookup misses its target.

    Fired by :meth:`RepairRemediationDecisionRepository.load_decision`
    when no row exists for the requested ``decision_id``. Distinct from
    a generic not-found so the CLI can produce an actionable hint
    (e.g. list existing decisions) without catching broad exception classes.
    """


_REPAIR_DECISION_NAMESPACE = REPAIR_DECISION_STORAGE_NAMESPACE.namespace
"""Profile-local secure-object namespace for repair-remediation decisions.

The encrypted secure-object rows live in the active profile's bucket;
cross-profile reads are not permitted by the underlying repository.
"""

_RepairDecisionOutcome = Literal["preserve", "quarantine", "rebuild", "export-required"]
"""Closed set of non-destructive planning outcomes for repair-remediation."""


@runtime_checkable
class _SecureObjectRepositoryProtocol(Protocol):
    """Structural interface consumed by the repair-integrity application layer.

    ``SecureObjectRepository`` satisfies this protocol without forcing the
    application layer to depend on the concrete SQL implementation.
    """

    def list_namespaces(self) -> tuple[str, ...]: ...
    def probe_namespace_integrity(self, namespace: str) -> SecureObjectNamespaceIntegrity: ...
    def list_keys(self, namespace: str) -> tuple[str, ...]: ...
    def iter_namespace_decryptability(self, namespace: str) -> Iterator[SecureObjectDecryptabilityRow]: ...


class RepairIntegrityReport(BaseModel):
    """Output of ``aeat config repair integrity [--namespace N]``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespaces: tuple[SecureObjectNamespaceIntegrity, ...]
    readable_total: int = Field(ge=0)
    unreadable_total: int = Field(ge=0)
    check: DiagnosticCheck


class RepairListRow(BaseModel):
    """One row in the secure-object repair inventory."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    object_key_digest: str = Field(min_length=1)
    readable: bool | None = None
    row_id: int | None = Field(default=None, ge=0)
    classification: str | None = None
    schema_version: int | None = Field(default=None, ge=1)
    written_at: datetime | None = None
    reason: str | None = None


class RepairListReport(BaseModel):
    """Output of the secure-object repair inventory."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace: str = Field(min_length=1)
    integrity: SecureObjectNamespaceIntegrity
    rows: tuple[RepairListRow, ...]
    rows_total: int = Field(ge=0)
    filter_mode: str = Field(min_length=1)


def _aggregate_integrity(
    integrity: tuple[SecureObjectNamespaceIntegrity, ...],
) -> DiagnosticCheck:
    """Render the cross-namespace summary as one DiagnosticCheck row.

    The check honours the exhaustiveness lock: ``fail`` / ``warn`` rows
    MUST carry exactly one of ``next_action`` / ``dead_end``; ``ok`` rows
    MUST carry neither.
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
        next_action="aeat config repair quarantine --yes",
    )


def build_repair_integrity_report(
    *,
    namespace: str | None = None,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairIntegrityReport:
    """Probe namespace integrity. When ``namespace`` is set, restrict scope.

    Returns a :class:`RepairIntegrityReport`.
    """
    if repository is not None:
        return _build_repair_integrity_report(namespace=namespace, repository=repository)
    with active_bucket_repair_session():
        return _build_repair_integrity_report(namespace=namespace, repository=_active_bucket_repair_repository())


def _build_repair_integrity_report(
    *,
    namespace: str | None,
    repository: _SecureObjectRepositoryProtocol,
) -> RepairIntegrityReport:
    repo = repository
    namespaces = repo.list_namespaces() if namespace is None else (namespace,)
    integrity = tuple(repo.probe_namespace_integrity(ns) for ns in namespaces)
    readable_total = sum(item.readable for item in integrity)
    unreadable_total = sum(item.unreadable for item in integrity)
    return RepairIntegrityReport(
        namespaces=integrity,
        readable_total=readable_total,
        unreadable_total=unreadable_total,
        check=_aggregate_integrity(integrity),
    )


@contextmanager
def active_bucket_repair_session() -> Generator[None]:
    """Open the active bucket session so integrity probes test decryptability, not bootstrap state."""
    provider: object | None = None
    try:
        from ..adapters.persistence.storage import get_master_key_provider, has_active_bucket_session

        if has_active_bucket_session():
            yield
            return
        provider = get_master_key_provider()
        # TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL:
        # get_master_key_provider returns object; __enter__/__exit__ are correct
        # at runtime but unverifiable without a typed Protocol.
        provider.__enter__()  # type: ignore[attr-defined]
    except Exception as exc:
        _log.debug("repair integrity could not open active bucket session: %s", type(exc).__name__)
        yield
        return
    try:
        yield
    finally:
        # TYPE-IGNORE-RATIONALE-RUNTIME-CM-PROTOCOL:
        # get_master_key_provider returns object; __enter__/__exit__ are correct
        # at runtime but unverifiable without a typed Protocol.
        provider.__exit__(None, None, None)  # type: ignore[attr-defined]


def build_repair_list_report(
    *,
    namespace: str,
    include_all: bool = False,
    only_unreadable: bool = False,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairListReport:
    """List object keys stored under ``namespace``.

    ``--all`` returns every key; ``--unreadable`` filters to only the
    rows whose payload cannot be decrypted under the current master
    key. Default behaviour (both flags False) returns the full key set
    but caps the inventory at the integrity-readable count for
    bandwidth control on large namespaces — same as ``--all`` for
    namespaces with no integrity issues.

    Returns a :class:`RepairListReport` enumerating the matching object
    keys and their decryptability status.
    """
    if include_all and only_unreadable:
        raise RepairIntegrityError(
            translated_message="application.repair_integrity.errors.conflicting_list_filters",
            context={"filters": "--all,--unreadable"},
        )
    if repository is None:
        with active_bucket_repair_session():
            return _build_repair_list_report(
                namespace=namespace,
                include_all=include_all,
                only_unreadable=only_unreadable,
                repository=_active_bucket_repair_repository(),
            )
    return _build_repair_list_report(
        namespace=namespace,
        include_all=include_all,
        only_unreadable=only_unreadable,
        repository=repository,
    )


def _build_repair_list_report(
    *,
    namespace: str,
    include_all: bool,
    only_unreadable: bool,
    repository: _SecureObjectRepositoryProtocol,
) -> RepairListReport:
    repo = repository
    integrity = repo.probe_namespace_integrity(namespace)
    row_metadata = tuple(repo.iter_namespace_decryptability(namespace))
    rows = tuple(_repair_list_row(row) for row in row_metadata)
    if only_unreadable:
        rows = tuple(row for row in rows if row.readable is False)
        filter_mode = "unreadable"
    elif include_all:
        filter_mode = "all"
    else:
        filter_mode = "default"
    return RepairListReport(
        namespace=namespace,
        integrity=integrity,
        rows=rows,
        rows_total=len(rows),
        filter_mode=filter_mode,
    )


def _active_bucket_repair_repository() -> SecureObjectRepository:
    from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

    return secure_object_repository_for_active_bucket()


def _repair_list_row(row: SecureObjectDecryptabilityRow) -> RepairListRow:
    return RepairListRow(
        namespace=row.namespace,
        object_key_digest=row.object_key.hex(),
        readable=row.readable,
        row_id=row.row_id,
        classification=row.classification,
        schema_version=row.schema_version,
        written_at=row.written_at,
        reason=row.reason if row.readable is False else None,
    )


class RepairRemediationDecision(BaseModel):
    """Non-destructive planning record for a repair-remediation outcome.

    Decision records persist preserve / quarantine / rebuild /
    export-required planning outcomes without authorising mutation.
    ``mutation_authorized`` is hard-typed to ``False`` so a decision
    record can never be mistaken for an execute order.

    The ``decision_id`` is content-bound via
    :func:`repair_remediation_decision_id` to every other field, so
    persisting an arbitrary sha-shaped key for a different remediation
    target or evidence requirement set is rejected at load time by the
    re-derivation guard.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    decision_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_namespace: str = Field(min_length=1)
    target_object_key_digest: str | None = Field(default=None, min_length=1)
    outcome: _RepairDecisionOutcome
    decided_at: datetime
    decided_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    likely_origin: str = Field(min_length=1)
    replacement_evidence_requirements: tuple[str, ...] = Field(default_factory=tuple)
    verified_replacement_evidence_refs: tuple[str, ...] = Field(default_factory=tuple)
    mutation_authorized: Literal[False] = False
    schema_version: str = "1"


def repair_remediation_decision_id(
    *,
    target_namespace: str,
    target_object_key_digest: str | None,
    outcome: _RepairDecisionOutcome,
    decided_at: datetime,
    decided_by: str,
    reason: str,
    likely_origin: str,
    replacement_evidence_requirements: Sequence[str],
    verified_replacement_evidence_refs: Sequence[str],
) -> str:
    """Return the deterministic SHA-256 id for a repair-remediation decision.

    Content-bound to every payload field including ``decided_at`` so
    two structurally identical re-runs at the same instant produce the
    same id; differing payloads produce different ids. The hash domain
    matches the model's field set exactly so the load-time
    re-derivation guard catches any payload mutation that bypassed
    the constructor.
    """
    payload = {
        "target_namespace": target_namespace.strip(),
        "target_object_key_digest": target_object_key_digest.strip() if target_object_key_digest else None,
        "outcome": outcome,
        "decided_at": decided_at.isoformat(),
        "decided_by": decided_by.strip(),
        "reason": reason.strip(),
        "likely_origin": likely_origin.strip(),
        "replacement_evidence_requirements": tuple(sorted(item.strip() for item in replacement_evidence_requirements)),
        "verified_replacement_evidence_refs": tuple(
            sorted(item.strip() for item in verified_replacement_evidence_refs)
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class RepairRemediationDecisionRepository:
    """Profile-local persistence for :class:`RepairRemediationDecision` records.

    Decisions are persisted as encrypted AUDIT-class secure-object rows
    under the active profile's bucket. The object key is the decision's
    content-addressed ``decision_id``; the payload is the decision's
    JSON model_dump. Listing returns rows in decision-time descending
    order.

    The repository accepts an optional ``SecureObjectRepository``
    injection for tests; the no-arg constructor resolves the active
    bucket's secure-object repository via the standard runtime path.
    """

    def __init__(self, repository: SecureObjectRepository | None = None) -> None:
        """Initialise the decision repository with an optional secure-object store override."""
        self._repository = repository

    def _repo(self) -> SecureObjectRepository:
        if self._repository is not None:
            return self._repository
        from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

        return secure_object_repository_for_active_bucket()

    def save_decision(self, decision: RepairRemediationDecision) -> None:
        """Persist one decision as an encrypted AUDIT-class secure-object row."""
        expected_decision_id = _expected_repair_decision_id(decision)
        if decision.decision_id != expected_decision_id:
            raise RepairIntegrityError(
                translated_message="application.repair_integrity.errors.decision_id_mismatch_save",
                context={
                    "decision_id": decision.decision_id,
                    "expected_decision_id": expected_decision_id,
                },
            )
        payload = decision.model_dump_json().encode("utf-8")
        self._repo().save(
            namespace=_REPAIR_DECISION_NAMESPACE,
            object_key=decision.decision_id,
            classification=REPAIR_DECISION_STORAGE_NAMESPACE.sensitivity,
            schema_version=REPAIR_DECISION_STORAGE_NAMESPACE.schema_version,
            written_at=decision.decided_at,
            payload=payload,
        )

    def load_decision(self, decision_id: str) -> RepairRemediationDecision:
        """Load one decision by its content-addressed id; re-derives + checks the id.

        Returns the :class:`RepairRemediationDecision` matching
        ``decision_id`` after verifying its content-addressed identity.
        """
        record = self._repo().load(
            namespace=_REPAIR_DECISION_NAMESPACE,
            object_key=decision_id,
            expected_class=REPAIR_DECISION_STORAGE_NAMESPACE.sensitivity,
            max_supported_version=REPAIR_DECISION_STORAGE_NAMESPACE.schema_version,
        )
        if record is None:
            raise RepairDecisionNotFoundError(
                translated_message="application.repair_integrity.errors.decision_not_found",
                context={"decision_id": decision_id},
            )
        decoded = RepairRemediationDecision.model_validate_json(record.payload)
        expected_decision_id = _expected_repair_decision_id(decoded)
        if decoded.decision_id != decision_id or decoded.decision_id != expected_decision_id:
            raise RepairIntegrityError(
                translated_message="application.repair_integrity.errors.decision_id_mismatch_load",
                context={
                    "decision_id": decision_id,
                    "payload_decision_id": decoded.decision_id,
                    "expected_decision_id": expected_decision_id,
                },
            )
        return decoded

    def list_decisions(self) -> tuple[RepairRemediationDecision, ...]:
        """Return every persisted :class:`RepairRemediationDecision` in decision-time descending order."""
        repo = self._repo()
        records = tuple(
            repo.list_records(
                _REPAIR_DECISION_NAMESPACE,
                expected_class=REPAIR_DECISION_STORAGE_NAMESPACE.sensitivity,
                max_supported_version=REPAIR_DECISION_STORAGE_NAMESPACE.schema_version,
            )
        )
        decisions: list[RepairRemediationDecision] = []
        for record in records:
            decision = RepairRemediationDecision.model_validate_json(record.payload)
            expected_decision_id = _expected_repair_decision_id(decision)
            if decision.decision_id != expected_decision_id:
                raise RepairIntegrityError(
                    translated_message="application.repair_integrity.errors.decision_id_mismatch_list",
                    context={
                        "decision_id": decision.decision_id,
                        "expected_decision_id": expected_decision_id,
                    },
                )
            decisions.append(decision)
        return tuple(sorted(decisions, key=lambda d: d.decided_at, reverse=True))


def _expected_repair_decision_id(decision: RepairRemediationDecision) -> str:
    return repair_remediation_decision_id(
        target_namespace=decision.target_namespace,
        target_object_key_digest=decision.target_object_key_digest,
        outcome=decision.outcome,
        decided_at=decision.decided_at,
        decided_by=decision.decided_by,
        reason=decision.reason,
        likely_origin=decision.likely_origin,
        replacement_evidence_requirements=decision.replacement_evidence_requirements,
        verified_replacement_evidence_refs=decision.verified_replacement_evidence_refs,
    )


class RepairPolicyNamespaceClassification(BaseModel):
    """Minimal namespace classification attached to a repair-policy surface."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    role: str = Field(min_length=1)


class RepairPolicyNamespacePolicy(BaseModel):
    """Policy metadata for one namespace governed by a command surface."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    namespace_classification: RepairPolicyNamespaceClassification
    owner_domain: str = Field(min_length=1)
    repair_policy: str = Field(min_length=1)
    recovery_policy: str = Field(min_length=1)
    mutation_authority: str = Field(min_length=1)
    registered_namespace_key: str | None = Field(default=None, min_length=1)
    registered_namespace: str | None = Field(default=None, min_length=1)
    registered_owner: str | None = Field(default=None, min_length=1)
    registered_sensitivity: str | None = Field(default=None, min_length=1)
    registered_schema_version: int | None = Field(default=None, ge=1)
    registered_scope: str | None = Field(default=None, min_length=1)


class RepairPolicyCommandSurface(BaseModel):
    """One catalogued repair-policy CLI command surface."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    command_path: str = Field(min_length=1)
    """The canonical CLI command path (e.g. ``config repair integrity objects``)."""

    command_family: str = Field(min_length=1)
    owner_domains: tuple[str, ...]
    decision_links: tuple[str, ...]
    namespace_policies: tuple[RepairPolicyNamespacePolicy, ...] = ()


_PROFILE_BUNDLE_POLICY = RepairPolicyNamespacePolicy(
    namespace_classification=RepairPolicyNamespaceClassification(role="profile_bundle"),
    owner_domain="profile_lifecycle",
    repair_policy="preserve_manifest_and_encrypted_payload_identity",
    recovery_policy="profile_import_export_roundtrip",
    mutation_authority="explicit_operator_confirmation_required_for_profile_mutation",
)
_MODEL_FILING_POLICY = RepairPolicyNamespacePolicy(
    namespace_classification=RepairPolicyNamespaceClassification(role="modelo_filing_artifact"),
    owner_domain="modelo_filing",
    repair_policy="preserve_exported_or_imported_filing_evidence",
    recovery_policy="reimport_authoritative_filing_evidence",
    mutation_authority="operator_requested_import_or_export_only",
)
_LEDGER_POLICY = RepairPolicyNamespacePolicy(
    namespace_classification=RepairPolicyNamespaceClassification(role="ledger_artifact"),
    owner_domain="ledger",
    repair_policy="preserve_transaction_evidence_and_import_payloads",
    recovery_policy="reimport_authoritative_ledger_source",
    mutation_authority="operator_requested_import_or_export_only",
)
_REPAIR_DECISION_LINKS: tuple[str, ...] = (
    # Catalog itself (build_repair_policy_command_surface_catalog,
    # repair_remediation_decision_id, and the linkage-coordination
    # contract these surfaces serve as the executable mirror of).
    "[[2026-05-26-linkage-design-audit]]",
    # Repair CLI shape (the operator-facing verb surface every entry
    # in the catalog mirrors — adding a verb here without an entry
    # there is the drift the gate exists to catch).
    "[[2026-05-13-cli-workflow-redesign-config-repair-shape]]",
)


def _secure_object_policy(
    definition: SecureObjectNamespaceDefinition,
    *,
    repair_policy: str = "metadata_only_digest_inventory_preserve_ciphertext",
    recovery_policy: str = "restore_matching_master_key_or_rebuild_from_authoritative_source",
    mutation_authority: str = "explicit_operator_confirmation_required_for_mutation",
) -> RepairPolicyNamespacePolicy:
    return RepairPolicyNamespacePolicy(
        namespace_classification=RepairPolicyNamespaceClassification(role=definition.scope.value),
        owner_domain=definition.owner,
        repair_policy=repair_policy,
        recovery_policy=recovery_policy,
        mutation_authority=mutation_authority,
        registered_namespace_key=definition.key,
        registered_namespace=definition.namespace,
        registered_owner=definition.owner,
        registered_sensitivity=definition.sensitivity.value,
        registered_schema_version=definition.schema_version,
        registered_scope=definition.scope.value,
    )


def _all_secure_object_namespace_policies() -> tuple[RepairPolicyNamespacePolicy, ...]:
    return tuple(_secure_object_policy(definition) for definition in STORAGE_NAMESPACE_REGISTRY.namespaces)


def _surface(
    command_path: str,
    *,
    command_family: str,
    owner_domains: tuple[str, ...],
    namespace_policies: tuple[RepairPolicyNamespacePolicy, ...] = (),
) -> RepairPolicyCommandSurface:
    return RepairPolicyCommandSurface(
        command_path=command_path,
        command_family=command_family,
        owner_domains=owner_domains,
        decision_links=_REPAIR_DECISION_LINKS,
        namespace_policies=namespace_policies,
    )


def build_repair_policy_command_surface_catalog() -> tuple[RepairPolicyCommandSurface, ...]:
    """Return the :class:`RepairPolicyCommandSurface` catalog for repair-policy CLI surfaces.

    The catalog mirrors the Typer command registry for repair,
    recovery, import, export, and bucket-history surfaces. It is used
    as an executable drift gate: adding a new command in those families
    requires a policy row here.
    """
    return (
        _surface("config repair logs", command_family="repair", owner_domains=("diagnostics",)),
        _surface(
            "config repair quarantine",
            command_family="repair",
            owner_domains=("secure_storage",),
            namespace_policies=_all_secure_object_namespace_policies(),
        ),
        _surface(
            "config repair reset-progress",
            command_family="repair",
            owner_domains=("workflow_state",),
            namespace_policies=(
                _secure_object_policy(
                    WORKFLOW_STATE_NAMESPACE,
                    repair_policy="metadata_only_workflow_state_reset_plan",
                    recovery_policy="restore_matching_master_key_or_rebuild_workflow_state_projection",
                ),
            ),
        ),
        _surface(
            "config repair profile",
            command_family="repair",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_PROFILE_BUNDLE_POLICY,),
        ),
        _surface(
            "config repair integrity objects",
            command_family="repair",
            owner_domains=("secure_storage",),
            namespace_policies=_all_secure_object_namespace_policies(),
        ),
        _surface("config repair integrity registry", command_family="repair", owner_domains=("registry",)),
        _surface("config repair connectivity", command_family="repair", owner_domains=("remote_connectivity",)),
        _surface(
            "config profile import",
            command_family="recovery",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_PROFILE_BUNDLE_POLICY,),
        ),
        _surface(
            "config profile export",
            command_family="recovery",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_PROFILE_BUNDLE_POLICY,),
        ),
        _surface(
            "config recover",
            command_family="recovery",
            owner_domains=("secure_storage",),
        ),
        _surface(
            "config rekey",
            command_family="recovery",
            owner_domains=("secure_storage",),
        ),
        _surface(
            "config show-recovery",
            command_family="recovery",
            owner_domains=("secure_storage",),
        ),
        _surface(
            "config verify-recovery",
            command_family="recovery",
            owner_domains=("secure_storage",),
        ),
        _surface("config bucket history", command_family="audit", owner_domains=("bucket_lifecycle",)),
        _surface(
            "app ledger import",
            command_family="recovery",
            owner_domains=("ledger",),
            namespace_policies=(_LEDGER_POLICY,),
        ),
        _surface(
            "app ledger export",
            command_family="recovery",
            owner_domains=("ledger",),
            namespace_policies=(_LEDGER_POLICY,),
        ),
        _surface(
            "app modelo export",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app modelo filing-record import",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app modelo audit export",
            command_family="audit",
            owner_domains=("modelo_audit", "modelo_filing"),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
    )


__all__ = [
    "RepairIntegrityReport",
    "RepairListReport",
    "RepairListRow",
    "RepairPolicyCommandSurface",
    "RepairPolicyNamespaceClassification",
    "RepairPolicyNamespacePolicy",
    "RepairRemediationDecision",
    "RepairRemediationDecisionRepository",
    "build_repair_integrity_report",
    "build_repair_list_report",
    "build_repair_policy_command_surface_catalog",
    "repair_remediation_decision_id",
]
