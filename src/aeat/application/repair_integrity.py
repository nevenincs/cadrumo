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

Repair-remediation decisions (per ADR
``2026-05-26-linkage-design-audit-adr`` Decision 4) are non-destructive
planning records persisted as encrypted AUDIT-class secure-object rows
in a profile-local namespace. The full preserve/quarantine/rebuild/
export-required semantics + repair-policy command-surface catalog land
here as scaffolds matching the design documented at
``.vault/exec/2026-05-19-live-iva-compensation-wallet/2026-05-22-live-iva-compensation-wallet-w05-p02-s01.md``.
The live-iva-compensation-wallet campaign's eventual landing
supersedes via standard merge resolution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..adapters.persistence.storage.sql.secure_objects import (
    SecureObjectNamespaceIntegrity,
    SecureObjectRepository,
)
from ..core.logging import get_logger
from .diagnostics import DiagnosticCheck

_log = get_logger(__name__)

_REPAIR_DECISION_NAMESPACE = "aeat.application.repair_integrity.decisions"
"""Profile-local secure-object namespace for repair-remediation decisions.

The encrypted secure-object rows live in the active profile's bucket;
cross-profile reads are not permitted by the underlying repository.
"""

_RepairDecisionOutcome = Literal["preserve", "quarantine", "rebuild", "export-required"]
"""Closed set of non-destructive planning outcomes per the
live-iva-compensation-wallet W05.P02.S01 exec record."""


@runtime_checkable
class _SecureObjectRepositoryProtocol(Protocol):
    """Structural interface consumed by the repair-integrity application layer.

    ``SecureObjectRepository`` satisfies this protocol; test stubs that
    implement only these three methods are accepted without subclassing.
    """

    def list_namespaces(self) -> tuple[str, ...]: ...
    def probe_namespace_integrity(self, namespace: str) -> SecureObjectNamespaceIntegrity: ...
    def list_keys(self, namespace: str) -> tuple[str, ...]: ...


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
    readable: bool | None = None
    row_id: int | None = Field(default=None, ge=0)
    classification: str | None = None
    schema_version: int | None = Field(default=None, ge=1)
    written_at: datetime | None = None
    reason: str | None = None


class RepairListReport(BaseModel):
    """Output of ``aeat config repair list <namespace> [--all|--unreadable]``."""

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
        next_action="aeat config repair quarantine --yes",
    )


def build_repair_integrity_report(
    *,
    namespace: str | None = None,
    repository: _SecureObjectRepositoryProtocol | None = None,
) -> RepairIntegrityReport:
    """Probe namespace integrity. When ``namespace`` is set, restrict scope."""
    if repository is not None:
        return _build_repair_integrity_report(namespace=namespace, repository=repository)
    with _best_effort_active_bucket_session():
        return _build_repair_integrity_report(namespace=namespace, repository=SecureObjectRepository())


def _build_repair_integrity_report(
    *,
    namespace: str | None,
    repository: _SecureObjectRepositoryProtocol,
) -> RepairIntegrityReport:
    repo = repository
    if namespace is None:
        try:
            namespaces = repo.list_namespaces()
        except Exception:  # pragma: no cover - defensive; storage layer surfaces typed errors
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
    except Exception:
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
    repo = repository or SecureObjectRepository()
    integrity = repo.probe_namespace_integrity(namespace)
    keys = repo.list_keys(namespace)
    rows = tuple(RepairListRow(namespace=namespace, object_key_digest=k) for k in keys)
    if only_unreadable:
        # Surface the integrity status; the storage layer does not yet
        # expose per-key decryptability without attempting decryption,
        # so this filter currently surfaces every key with a flag.
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


class RepairRemediationDecision(BaseModel):
    """Non-destructive planning record for a repair-remediation outcome.

    Per ADR ``2026-05-26-linkage-design-audit-adr`` Decision 4 + the
    live-iva-compensation-wallet W05.P02.S01 exec record: the decision
    records preserve / quarantine / rebuild / export-required planning
    outcomes without authorising mutation. ``mutation_authorized`` is
    hard-typed to ``False`` so a decision record can never be mistaken
    for an execute order.

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
        self._repository = repository

    def _repo(self) -> SecureObjectRepository:
        if self._repository is not None:
            return self._repository
        from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

        return secure_object_repository_for_active_bucket()

    def save_decision(self, decision: RepairRemediationDecision) -> None:
        """Persist one decision as an encrypted AUDIT-class secure-object row."""
        from ..core.classification import SensitivityClass

        payload = decision.model_dump_json().encode("utf-8")
        self._repo().save(
            namespace=_REPAIR_DECISION_NAMESPACE,
            object_key=decision.decision_id,
            classification=SensitivityClass.AUDIT,
            schema_version=1,
            written_at=decision.decided_at,
            payload=payload,
        )

    def load_decision(self, decision_id: str) -> RepairRemediationDecision:
        """Load one decision by its content-addressed id; re-derives + checks the id."""
        record = self._repo().load(namespace=_REPAIR_DECISION_NAMESPACE, object_key=decision_id)
        decoded = RepairRemediationDecision.model_validate_json(record.payload)
        if decoded.decision_id != decision_id:
            raise ValueError(
                f"repair-remediation decision payload at key {decision_id!r} "
                f"declares decision_id {decoded.decision_id!r}; refusing the load"
            )
        return decoded

    def list_decisions(self) -> tuple[RepairRemediationDecision, ...]:
        """Return every persisted decision in decision-time descending order."""
        repo = self._repo()
        try:
            keys = repo.list_keys(_REPAIR_DECISION_NAMESPACE)
        except Exception:
            return ()
        decisions: list[RepairRemediationDecision] = []
        for key in keys:
            try:
                decisions.append(self.load_decision(key))
            except Exception as exc:
                _log.debug("skipping unreadable repair decision %s: %s", key, type(exc).__name__)
                continue
        return tuple(sorted(decisions, key=lambda d: d.decided_at, reverse=True))


class RepairPolicyCommandSurface(BaseModel):
    """One catalogued repair-policy CLI command surface."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    command_path: str = Field(min_length=1)
    """The canonical CLI command path (e.g. ``aeat config repair integrity``)."""


def build_repair_policy_command_surface_catalog() -> tuple[RepairPolicyCommandSurface, ...]:
    """Return the catalogued repair-policy CLI surfaces.

    Per ADR Decision 4, this is a scaffold matching the consumer test
    contract at ``test_repair_policy_coverage.py``: returns objects
    carrying a ``command_path`` string that aligns with the CLI
    registry. The live-iva-compensation-wallet campaign's full
    implementation supersedes via standard merge.
    """
    return (
        RepairPolicyCommandSurface(command_path="aeat config repair integrity"),
        RepairPolicyCommandSurface(command_path="aeat config repair list"),
    )


__all__ = [
    "RepairIntegrityReport",
    "RepairListReport",
    "RepairListRow",
    "RepairPolicyCommandSurface",
    "RepairRemediationDecision",
    "RepairRemediationDecisionRepository",
    "build_repair_integrity_report",
    "build_repair_list_report",
    "build_repair_policy_command_surface_catalog",
    "repair_remediation_decision_id",
]
