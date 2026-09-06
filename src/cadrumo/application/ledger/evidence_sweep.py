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

from collections.abc import Callable, Sequence
from enum import StrEnum
from typing import NamedTuple

from ...adapters.outbound.google.document_link_resolver import DriveFolderDocument
from ...adapters.outbound.storage.errors import OutboundStoragePermissionError

__all__ = [
    "EvidenceFolderSweep",
    "EvidenceSweepRefusal",
    "SweptDocument",
    "classify_evidence_sweep_failure",
    "sweep_evidence_folder",
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


class SweptDocument(NamedTuple):
    """What became of one document in a folder sweep.

    ``fetched`` and ``refusal`` are mutually exclusive by construction: a
    fetched document names its attachment, a refused one names why. Neither
    row can claim both, which is what keeps a caller from reporting a refusal
    with an attachment id or a fetch with no evidence behind it.
    """

    file_id: str
    name: str
    mime_type: str
    attachment_id: str | None
    refusal: EvidenceSweepRefusal | None

    @property
    def fetched(self) -> bool:
        """Whether this document's bytes reached the attachment store."""
        return self.attachment_id is not None


class EvidenceFolderSweep(NamedTuple):
    """One folder sweep's outcome, with its counts derived from its rows.

    The counts are properties rather than stored fields on purpose. The CLI
    sweep this replaced tracked ``refused_count`` in a separate variable that
    was initialised and never incremented, so the summary said zero refusals
    while the rows it printed alongside said otherwise. A count that cannot be
    computed from anything but the rows cannot disagree with them.
    """

    documents: tuple[SweptDocument, ...]

    @property
    def fetched_count(self) -> int:
        """How many documents reached the attachment store."""
        return sum(1 for document in self.documents if document.fetched)

    @property
    def refused_count(self) -> int:
        """How many documents were refused individually."""
        return sum(1 for document in self.documents if document.refusal is not None)


def sweep_evidence_folder(
    *,
    documents: Sequence[DriveFolderDocument],
    fetch: Callable[[DriveFolderDocument], str],
) -> EvidenceFolderSweep:
    """Fetch every document, recording the ones refused individually.

    One row per document, in the order given, so a caller can report the sweep
    against the folder it listed rather than against the subset that happened
    to succeed.

    Args:
        documents: The folder's children, as listed.
        fetch: Fetches and stores one document, returning its attachment id.
            Raising is how it reports a failure;
            :func:`classify_evidence_sweep_failure` decides whether that
            failure belongs to the document or to the sweep.

    Returns:
        The sweep, whose counts are derived from its rows.

    Raises:
        Exception: Whatever ``fetch`` raised, when the failure is not a fact
            about that one document. Propagating is deliberate: a transport
            that has stopped working will fail every remaining document, and
            reporting those as individually refused would be confidently wrong
            about every row.
    """
    swept: list[SweptDocument] = []
    for document in documents:
        try:
            attachment_id = fetch(document)
        except Exception as error:
            refusal = classify_evidence_sweep_failure(error)
            if refusal is None:
                raise
            swept.append(
                SweptDocument(
                    file_id=document.file_id,
                    name=document.name,
                    mime_type=document.mime_type,
                    attachment_id=None,
                    refusal=refusal,
                ),
            )
            continue
        swept.append(
            SweptDocument(
                file_id=document.file_id,
                name=document.name,
                mime_type=document.mime_type,
                attachment_id=attachment_id,
                refusal=None,
            ),
        )
    return EvidenceFolderSweep(documents=tuple(swept))
