"""The repair work every frontend runs: integrity verdict, quarantine, progress reset and log tail.

Each function here is the whole of one repair command's work apart from
parsing its arguments and rendering its result. The command line calls them
in its own process. The registered diagnostics operations and the runtime's
repair acts call the same functions, so a frontend that reaches the work
through the runtime does exactly what the command does.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel

from ..core.logging import default_log_file_path
from ..core.models import STRICT_FROZEN_CONFIG
from .diagnostic_models import DiagnosticStatus, SecureObjectIntegrityReport
from .diagnostics import preview_quarantine_unreadable_secure_objects, quarantine_unreadable_secure_objects
from .diagnostics_ports import DiagnosticsPorts
from .diagnostics_repair_documents import RepairLogsDocument

if TYPE_CHECKING:
    from .workflow.events import WorkflowStateResetFingerprint

_TAIL_CHUNK_BYTES: Final = 8192

WORKFLOW_PROGRESS_RESET_ACTOR: Final = "cadrumo.application.workflow"
"""The actor a person's frontend records for a progress reset."""


class SecureObjectIntegrityCheck(BaseModel):
    """The decryptability counts of a sweep and the verdict on its unreadable rows."""

    model_config = STRICT_FROZEN_CONFIG

    report: SecureObjectIntegrityReport
    status: Literal[DiagnosticStatus.OK, DiagnosticStatus.FAIL]
    summary: str


def check_secure_object_integrity(
    *, ports: DiagnosticsPorts, namespace: str | None = None
) -> SecureObjectIntegrityCheck:
    """Count readable and unreadable secure-object rows and judge the unreadable ones.

    ``namespace`` narrows the report, and its totals, to that one namespace. A
    namespace that holds no row yields an empty report with zero totals.
    """
    report = preview_quarantine_unreadable_secure_objects(ports=ports)
    if namespace is not None:
        namespaces = tuple(item for item in report.namespaces if item.namespace == namespace)
        report = SecureObjectIntegrityReport(
            namespaces=namespaces,
            readable_total=sum(item.readable for item in namespaces),
            unreadable_total=sum(item.unreadable for item in namespaces),
        )
    return SecureObjectIntegrityCheck(
        report=report,
        status=DiagnosticStatus.FAIL if report.unreadable_total else DiagnosticStatus.OK,
        summary=f"{report.unreadable_total} unreadable secure-object rows",
    )


def run_secure_object_quarantine(*, ports: DiagnosticsPorts, dry_run: bool) -> SecureObjectIntegrityReport:
    """Move unreadable secure-object rows into quarantine, or count what would move.

    With ``dry_run`` nothing is written: the report's unreadable counts are
    the rows a confirmed run would move and its readable counts the rows it
    would keep.
    """
    if dry_run:
        return preview_quarantine_unreadable_secure_objects(ports=ports)
    return quarantine_unreadable_secure_objects(ports=ports)


def run_workflow_progress_reset(
    *, dry_run: bool, actor: str = WORKFLOW_PROGRESS_RESET_ACTOR
) -> WorkflowStateResetFingerprint:
    """Discard the saved interrupted-command progress, or describe what would be discarded.

    With ``dry_run`` the stored record is fingerprinted and left in place.
    Otherwise the reset is recorded against ``actor`` before the record is
    deleted.
    """
    # The workflow store pulls the registry; a process that only tails a log must not pay for it.
    from .workflow.persistence import fingerprint_workflow_state, reset_workflow_state

    if dry_run:
        return fingerprint_workflow_state()
    return reset_workflow_state(actor=actor)


def read_log_tail(lines: int) -> RepairLogsDocument:
    """Return the configured log file's path and its last ``lines`` lines.

    A missing or unreadable file, and a request for no lines, yield the path
    with no lines.
    """
    path = default_log_file_path()
    tail = _tail_lines(path, lines) if path.exists() and lines > 0 else ()
    return RepairLogsDocument(path=str(path), lines=tail)


def _tail_lines(path: Path, count: int) -> tuple[str, ...]:
    """Return the last ``count`` lines of ``path`` without their line endings."""
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            position = handle.tell()
            blocks: list[bytes] = []
            newlines_seen = 0
            while position > 0 and newlines_seen <= count:
                read_size = min(_TAIL_CHUNK_BYTES, position)
                position -= read_size
                handle.seek(position)
                block = handle.read(read_size)
                blocks.append(block)
                newlines_seen += block.count(b"\n")
    except OSError:
        return ()
    text = b"".join(reversed(blocks)).decode("utf-8", errors="replace")
    return tuple(text.splitlines()[-count:])


__all__ = [
    "WORKFLOW_PROGRESS_RESET_ACTOR",
    "SecureObjectIntegrityCheck",
    "check_secure_object_integrity",
    "read_log_tail",
    "run_secure_object_quarantine",
    "run_workflow_progress_reset",
]
