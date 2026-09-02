"""Secure-object repair diagnostics, remediation decisions, and policy coverage.

The read side of this module produces metadata-only reports over encrypted
secure-object rows. Integrity sweeps iterate namespaces in a
:class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository` and return
per-namespace
:class:`~cadrumo.adapters.persistence.storage.SecureObjectNamespaceIntegrity`
counts; inventory rows expose row metadata and HMAC digests, never natural
keys or payload bytes. These reports
back the repair integrity surface and the quarantine dry-run path without
emitting bucket events.

The write side is deliberately narrow: :class:`RepairRemediationDecision`
records persist non-destructive preserve / quarantine / rebuild /
export-required planning outcomes as encrypted AUDIT-class rows. A decision
record is evidence for a later operator workflow, not mutation authority.

The policy catalog returned by
:func:`build_repair_policy_command_surface_catalog` mirrors repair, recovery,
import, export, and bucket-history command surfaces against registered
:class:`SecureObjectNamespaceDefinition` metadata. Tests use it as a drift gate
so new maintenance surfaces cannot appear without an explicit namespace policy.

See Also:
    :mod:`cadrumo.application.diagnostics`
        Builds the user-facing repair report and delegates quarantine preview /
        commit flows through this module's active-bucket repair session.
    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
        Encrypted SQL repository whose namespace integrity probes and
        quarantine operation supply the repair data.
    :data:`~cadrumo.adapters.persistence.storage.STORAGE_NAMESPACE_REGISTRY`
        Central registry copied into repair-policy namespace rows.
    :mod:`cadrumo.entrypoints.cli.config._repair_cli`
        CLI command surface that renders these reports and policy-backed repair
        actions.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, NonNegativeInt

from ..adapters.persistence.storage.namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..adapters.persistence.storage.secure_object_namespaces import (
    REPAIR_INTEGRITY_DECISION_NAMESPACE as REPAIR_DECISION_STORAGE_NAMESPACE,
)
from ..adapters.persistence.storage.secure_object_namespaces import (
    SYNC_RUN_RECORDS_NAMESPACE,
    USER_PROFILE_VALUE_NAMESPACE,
    WORKFLOW_STATE_NAMESPACE,
    SecureObjectNamespaceDefinition,
)
from ..adapters.persistence.storage.sql.secure_objects import (
    SecureObjectDecryptabilityRow,
    SecureObjectNamespaceIntegrity,
    SecureObjectRepository,
)
from ..core.errors.hierarchy import CoreError
from ..core.hashing import content_hash_hex
from ..core.hex import Hex64Str
from ..core.logging import get_logger
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    ActionEvidenceProvenance,
)
from .diagnostic_models import DiagnosticCheck, DiagnosticStatus
from .operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict

_log = get_logger(__name__)


class RepairIntegrityError(CoreError):
    """Base error for secure-object integrity and repair-remediation failures.

    Raised by the repair-integrity application layer when an integrity
    invariant or remediation contract is violated. Inherits from
    :class:`cadrumo.core.errors.CoreError` so callers can catch either the
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

    :class:`~cadrumo.adapters.persistence.storage.SecureObjectRepository`
    satisfies this protocol. The interface is limited to namespace enumeration,
    integrity probing, key inventory, and
    :class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectDecryptabilityRow`
    iteration so read-only repair reports can be tested against the real
    repository without granting mutation APIs to the report builders.
    """

    def list_namespaces(self) -> tuple[str, ...]: ...
    def probe_namespace_integrity(self, namespace: str) -> SecureObjectNamespaceIntegrity: ...
    def list_keys(self, namespace: str) -> tuple[str, ...]: ...
    def iter_namespace_decryptability(self, namespace: str) -> Iterator[SecureObjectDecryptabilityRow]: ...


class RepairIntegrityReport(BaseModel):
    """Metadata-only secure-object integrity report.

    ``namespaces`` carries one :class:`SecureObjectNamespaceIntegrity` per
    probed namespace. ``check`` is the aggregate :class:`DiagnosticCheck` row
    used by repair renderers; failing reports carry a typed quarantine
    precondition verdict.

    See Also:
        :func:`build_repair_integrity_report`
            Producer that fills this report from real secure-object
            decryptability probes.
        :class:`~cadrumo.application.diagnostics.SecureObjectIntegrityReport`
            Config-repair rollup that uses the same namespace integrity shape.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespaces: tuple[SecureObjectNamespaceIntegrity, ...]
    readable_total: NonNegativeInt
    unreadable_total: NonNegativeInt
    check: DiagnosticCheck


class RepairListRow(BaseModel):
    """One metadata row in the secure-object repair inventory.

    Rows are projected from
    :class:`~cadrumo.adapters.persistence.storage.sql.secure_objects.SecureObjectDecryptabilityRow`
    values returned by
    :meth:`~cadrumo.adapters.persistence.storage.SecureObjectRepository.iter_namespace_decryptability`.
    ``object_key_digest`` is the stored HMAC digest, not the natural object key.
    ``reason`` is populated only for unreadable rows and must remain a diagnostic
    class of failure rather than decrypted payload context.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    object_key_digest: str = Field(min_length=1)
    readable: bool | None = None
    row_id: int | None = Field(default=None, ge=0)
    classification: str | None = None
    schema_version: int | None = Field(default=None, ge=1)
    written_at: datetime | None = None
    reason: str | None = None


class RepairListReport(BaseModel):
    """Internal secure-object inventory report for one namespace.

    The report combines the namespace's :class:`SecureObjectNamespaceIntegrity`
    counts with metadata-only :class:`RepairListRow` entries. Operator-facing
    repair commands render aggregate integrity and quarantine previews rather
    than exposing a broad raw list command.
    """

    model_config = STRICT_FROZEN_CONFIG

    namespace: str = Field(min_length=1)
    integrity: SecureObjectNamespaceIntegrity
    rows: tuple[RepairListRow, ...]
    rows_total: NonNegativeInt
    filter_mode: str = Field(min_length=1)


def _aggregate_integrity(
    integrity: tuple[SecureObjectNamespaceIntegrity, ...],
) -> DiagnosticCheck:
    """Render the cross-namespace summary as one :class:`DiagnosticCheck` row.

    The check honours the typed diagnostic contract: ``fail`` / ``warn`` rows
    MUST carry a precondition verdict; ``ok`` rows MUST carry neither.
    """
    readable = sum(item.readable for item in integrity)
    unreadable = sum(item.unreadable for item in integrity)
    if unreadable == 0:
        return DiagnosticCheck(
            name="secure_objects.integrity",
            status=DiagnosticStatus.OK,
            summary=(f"{readable} row(s) decryptable across {len(integrity)} namespace(s)"),
        )
    impacted = ", ".join(
        f"{item.namespace} ({item.unreadable}/{item.readable + item.unreadable})"
        for item in integrity
        if item.unreadable
    )
    return DiagnosticCheck(
        name="secure_objects.integrity",
        status=DiagnosticStatus.FAIL,
        summary=f"{unreadable} undecryptable row(s) in: {impacted}",
        precondition_verdict=PreconditionVerdict(
            failed_condition_id="diagnostics.secure_objects.integrity.readable",
            evidence=(
                ConditionEvidence(
                    condition_id="diagnostics.secure_objects.integrity.readable",
                    evidence_id="diagnostics.secure_objects.integrity.observation",
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                    values={
                        "readable_total": readable,
                        "unreadable_total": unreadable,
                    },
                ),
            ),
            action=ActionReference(action_id="operator.diagnostics.secure_objects.quarantine"),
            argument_bindings=(
                ActionArgumentBinding(
                    argument_name="yes",
                    status=ActionArgumentStatus.RESOLVED,
                    value=True,
                    source=ActionArgumentSource.VERDICT_CONTEXT,
                    source_key="yes",
                ),
            ),
            conditionality=ActionConditionality.IMMEDIATE,
        ),
    )


def build_repair_integrity_report(
    *,
    namespace: str | None = None,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairIntegrityReport:
    """Probe secure-object decryptability and return a :class:`RepairIntegrityReport`.

    When ``namespace`` is set, only that namespace is probed; otherwise every
    namespace currently present in the repository is scanned. Without an injected
    repository, the probe opens the active bucket repair session before resolving
    the runtime-bound :class:`SecureObjectRepository`.
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
    """Reuse the operator's own bucket session for active-bucket repair probes.

    Repair integrity and quarantine previews test decryptability under the
    active bucket key, but they are bootstrap-adjacent diagnostics rather than
    profile enrollment flows: they never open a session of their own. A session
    that already serves the target is reused; with none, the span runs without
    one and the caller observes the normal repository/runtime readiness result.

    Running on without a session is safe here only because the substrate fails
    closed underneath: resolving the bucket-attached repository raises the
    ``not_ready`` readiness refusal before any row is probed. That matters more
    than it looks. These probes classify a row as unreadable when it will not
    decrypt, and the quarantine flow MOVES every such row out of the live
    table -- so a probe that ran keyless would report a sound bucket as
    entirely corrupt and quarantine all of it. Do not add a fallback that opens
    a session here to make the probe "work": a keyless probe answers the
    question wrongly, and the refusal is the correct answer.

    See Also:
        :func:`~cadrumo.application.diagnostics.preview_quarantine_unreadable_secure_objects`
            Dry-run repair flow that uses this context before probing
            decryptability.
        :func:`~cadrumo.application.diagnostics.quarantine_unreadable_secure_objects`
            Commit flow that uses this context before calling
            :meth:`~cadrumo.adapters.persistence.storage.SecureObjectRepository.quarantine_unreadable_rows`.
    """
    from ..adapters.persistence.storage.master_key.active_session import (
        active_bucket_session_serves,
        has_active_bucket_session,
    )
    from ..core.bucket_pointer import resolve_active_bucket_id

    # Probing decryptability under the WRONG bucket's key reports readable rows
    # as unreadable, and this context feeds the quarantine flows, so a
    # mismatched reuse would quarantine sound records. Bucket-match when a
    # target resolves; with no resolvable active bucket there is nothing to
    # compare against, and reusing whatever is bound stays correct.
    target_bucket_id = resolve_active_bucket_id()
    reusable = (
        active_bucket_session_serves(target_bucket_id) if target_bucket_id is not None else has_active_bucket_session()
    )
    if not reusable:
        _log.debug("repair integrity found no bucket session to reuse; the substrate refusal answers")
    yield


def build_repair_list_report(
    *,
    namespace: str,
    include_all: bool = False,
    only_unreadable: bool = False,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairListReport:
    """List secure-object metadata stored under ``namespace``.

    ``--all`` returns every key; ``--unreadable`` filters to only the
    rows whose payload cannot be decrypted under the current master
    key. Default behaviour (both flags False) returns the full key set
    but caps the inventory at the integrity-readable count for
    bandwidth control on large namespaces — same as ``--all`` for
    namespaces with no integrity issues.

    Returns a :class:`RepairListReport` enumerating matching HMAC digests and
    their decryptability status. The report never exposes natural object keys or
    payload bytes. Without an injected repository, the list path enters
    :func:`active_bucket_repair_session` before resolving the active
    :class:`SecureObjectRepository`.
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
    record can never be mistaken for an execute order. The policy catalog keeps
    these records visible through :class:`RepairPolicyCommandSurface`
    decision-trail anchors.

    The ``decision_id`` is content-bound via
    :func:`repair_remediation_decision_id` to every other field, so
    persisting an arbitrary sha-shaped key for a different remediation
    target or evidence requirement set is rejected at load time by the
    re-derivation guard.

    See Also:
        :class:`RepairRemediationDecisionRepository`
            Profile-local encrypted persistence for these decision records.
        :data:`~cadrumo.adapters.persistence.storage.REPAIR_INTEGRITY_DECISION_NAMESPACE`
            Secure-object namespace used to store the decisions.
    """

    model_config = STRICT_FROZEN_CONFIG

    decision_id: Hex64Str
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
    matches the :class:`RepairRemediationDecision` field set exactly so the load-time
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
            sorted(item.strip() for item in verified_replacement_evidence_refs),
        ),
    }
    return content_hash_hex(payload)


class RepairRemediationDecisionRepository:
    """Profile-local persistence for :class:`RepairRemediationDecision` records.

    Decisions are persisted through :class:`SecureObjectRepository` as encrypted
    AUDIT-class secure-object rows under the active profile's bucket. The object
    key is the decision's content-addressed ``decision_id``; the payload is the
    decision's JSON model dump. Listing returns rows in decision-time descending
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
            ),
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
    """Minimal namespace classification attached to a repair-policy surface.

    Embedded in :class:`RepairPolicyNamespacePolicy` so command catalog rows can
    describe non-registered bundle / filing / ledger surfaces and registered
    secure-object namespace scopes with the same shape.
    """

    model_config = STRICT_FROZEN_CONFIG

    role: str = Field(min_length=1)


class RepairPolicyNamespacePolicy(BaseModel):
    """Policy metadata for one namespace governed by a command surface.

    Registered secure-object namespaces copy owner, sensitivity, schema version,
    and scope from :class:`SecureObjectNamespaceDefinition` so repair and
    recovery surfaces stay tied to the namespace registry instead of parallel
    role markers. :class:`RepairPolicyCommandSurface` attaches these rows to
    every CLI surface that can inspect, repair, import, export, or recover
    namespace-owned data.
    """

    model_config = STRICT_FROZEN_CONFIG

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
    """One catalogued repair-policy CLI command surface.

    Each row links a command path to its owner domains, decision-trail anchors,
    and the namespace policies that constrain any repair or recovery behavior
    reachable from that command family.

    See Also:
        :class:`RepairPolicyNamespacePolicy`
            Per-namespace policy rows attached to a command surface.
        :func:`build_repair_policy_command_surface_catalog`
            Executable catalog that mirrors the repair and recovery CLI surface.
    """

    model_config = STRICT_FROZEN_CONFIG

    command_path: str = Field(min_length=1)
    """The canonical CLI command path (e.g. ``config repair integrity objects``)."""

    command_family: str = Field(min_length=1)
    owner_domains: tuple[str, ...]
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
        namespace_policies=namespace_policies,
    )


def build_repair_policy_command_surface_catalog() -> tuple[RepairPolicyCommandSurface, ...]:
    """Return the :class:`RepairPolicyCommandSurface` catalog for repair-policy CLI surfaces.

    The catalog mirrors the Typer command registry for repair,
    recovery, import, export, and bucket-history surfaces. It is used
    as an executable drift gate in both directions: adding a new command in
    those families requires a policy row here, and every ``command_path`` must
    resolve to a command the live CLI actually registers, so a row cannot
    outlive the verb it governs. Secure-object rows must derive their metadata
    from the central namespace registry. Each row also carries decision links
    for :class:`RepairRemediationDecision` governance.

    See Also:
        :data:`~cadrumo.adapters.persistence.storage.STORAGE_NAMESPACE_REGISTRY`
            Source of secure-object namespace metadata copied into catalog
            policies.
        :class:`~cadrumo.adapters.persistence.storage.SecureObjectNamespaceDefinition`
            Registered namespace declaration projected into policy rows.
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
        _surface("config profile history", command_family="audit", owner_domains=("bucket_lifecycle",)),
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
        _surface(
            "app ledger invoice import",
            command_family="recovery",
            owner_domains=("ledger",),
            namespace_policies=(_LEDGER_POLICY,),
        ),
        _surface(
            "app ledger restore",
            command_family="recovery",
            owner_domains=("ledger",),
            namespace_policies=(_LEDGER_POLICY,),
        ),
        _surface(
            "app modelo m145 export",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        # `censo file` and `profile restore` were renamed to `censo import` and
        # `archive import`, which ends both paths in a token the coverage
        # predicate selects. They write, so they need governing rows.
        _surface(
            "config profile censo import",
            command_family="recovery",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_secure_object_policy(USER_PROFILE_VALUE_NAMESPACE),),
        ),
        _surface(
            "config profile archive import",
            command_family="recovery",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_PROFILE_BUNDLE_POLICY,),
        ),
        _surface(
            "config profile archive export",
            command_family="recovery",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_PROFILE_BUNDLE_POLICY,),
        ),
        _surface(
            "app modelo reconcile import",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        # D2 renamed remote transport to `push`/`pull`. These leaves move data
        # across a remote boundary and persist what they move, so they are
        # governed on the same reasoning as their local `import`/`export`
        # siblings. `app modelo spreadsheet push` in particular was governed
        # under its pre-D2 name and must not lose that.
        _surface(
            "app live expedientes pull",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app live filed pull",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app live filed pull-all",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app live iva-wallet pull",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app live justificante pull",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app live notifications document pull",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app live notifications pull",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app modelo reconcile pull",
            command_family="recovery",
            owner_domains=("modelo_filing",),
            namespace_policies=(_MODEL_FILING_POLICY,),
        ),
        _surface(
            "app ledger evidence pull",
            command_family="recovery",
            owner_domains=("ledger",),
            namespace_policies=(_LEDGER_POLICY,),
        ),
        _surface(
            "app ledger evidence pull-all",
            command_family="recovery",
            owner_domains=("ledger",),
            namespace_policies=(_LEDGER_POLICY,),
        ),
        _surface(
            "app modelo spreadsheet pull",
            command_family="recovery",
            owner_domains=("google_sync",),
            namespace_policies=(_secure_object_policy(SYNC_RUN_RECORDS_NAMESPACE),),
        ),
        _surface(
            "app modelo spreadsheet push",
            command_family="recovery",
            owner_domains=("google_sync",),
            namespace_policies=(_secure_object_policy(SYNC_RUN_RECORDS_NAMESPACE),),
        ),
        _surface(
            "config profile archive push",
            command_family="recovery",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_PROFILE_BUNDLE_POLICY,),
        ),
        _surface(
            "config profile censo pull",
            command_family="recovery",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_secure_object_policy(USER_PROFILE_VALUE_NAMESPACE),),
        ),
        # A model acquisition writes a local model artefact, not a registered
        # secure-object namespace, so this row declares its family and owner
        # without over-claiming a namespace policy.
        _surface(
            "config provision pull",
            command_family="recovery",
            owner_domains=("local_inference",),
        ),
        # The custody carve-out reactivated: `config passphrase` is registered
        # again, and a passphrase change re-wraps the profile's encrypted
        # payload.
        _surface(
            "config passphrase change",
            command_family="repair",
            owner_domains=("profile_lifecycle",),
            namespace_policies=(_PROFILE_BUNDLE_POLICY,),
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
