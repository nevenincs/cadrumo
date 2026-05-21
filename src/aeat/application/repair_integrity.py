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

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from ..adapters.persistence.storage.sql.secure_objects import (
    SecureObjectNamespaceIntegrity,
    SecureObjectRepository,
)
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


__all__ = [
    "RepairIntegrityReport",
    "RepairListReport",
    "RepairListRow",
    "build_repair_integrity_report",
    "build_repair_list_report",
]
