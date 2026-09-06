"""Which failure during a bulk evidence pull refuses one file, and which ends the sweep.

A folder sweep fetches many documents, and the useful behaviour is that one
unreachable file is recorded and the sweep carries on. That is only correct for
failures that are genuinely a fact about THAT file. A transport collapse is not:
continuing past it would mark every remaining document "refused" and hand the
operator a scope-upgrade story for what is actually a broken connection — a
report that is wrong about every row it contains, and confidently so.

So exactly one failure continues the sweep: the document is not reachable under
the granted ``drive.file`` scope, which Google answers with 403/404 and the
resolver raises as
:exc:`~adapters.outbound.storage.errors.OutboundStoragePermissionError`. The app
can only read files it created or the operator picked, so the very next document
in the same folder may well be readable, and refusing the whole sweep over one
would make bulk pull useless on any realistic folder.

Everything else ends the sweep and surfaces as itself. A network failure is not
about the document, and a non-bytes payload from the media endpoint says the
transport is misbehaving rather than that this file is private; recording either
as a per-file refusal would invent a cause the evidence does not support.

The alternative to deciding this once is every surface deciding it again. The
CLI sweep documented the per-file behaviour in its own docstring and in the
payload model, and implemented neither: the loop had no handler at all, so the
first unreachable file aborted the run with a traceback, ``refused_count`` was
initialised and never incremented, and ``refusal_reason`` was rendered but never
set. A second frontend would have had the same three ways to get it wrong.
"""

from __future__ import annotations

from enum import StrEnum

from ...adapters.outbound.storage.errors import OutboundStoragePermissionError

__all__ = [
    "EvidenceSweepRefusal",
    "classify_evidence_sweep_failure",
]


class EvidenceSweepRefusal(StrEnum):
    """Why one document in a sweep produced no evidence.

    A stable transport token, not prose: it travels in the machine-readable
    result row, and a surface renders its own wording from it.
    """

    #: The document is not reachable under the granted ``drive.file`` scope.
    #: Reading it needs a scope upgrade the operator has to grant, so the
    #: refusal is durable and naming it per-file is what lets the rest run.
    FILE_NOT_REACHABLE = "file_not_reachable"


def classify_evidence_sweep_failure(error: Exception) -> EvidenceSweepRefusal | None:
    """Decide whether ``error`` refuses one document or ends the sweep.

    Args:
        error: The exception raised while fetching or storing one document.

    Returns:
        The per-file refusal to record before continuing, or ``None`` when the
        failure is not a fact about this document and the caller must let it
        propagate. ``None`` means re-raise, never "ignore".
    """
    if isinstance(error, OutboundStoragePermissionError):
        return EvidenceSweepRefusal.FILE_NOT_REACHABLE
    return None
