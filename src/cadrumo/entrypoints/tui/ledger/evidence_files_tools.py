"""The evidence and attachment tools the Records workspace lists, bound to their doors."""

from __future__ import annotations

from ....application.ledger.workspace import LedgerWorkspaceArea
from .controller import LedgerWorkspaceController, LedgerWorkspaceScreen
from .evidence_files_attachments import LedgerEvidenceFilesAttachmentsScreen
from .evidence_files_batch import LedgerEvidenceFilesBatchScreen
from .evidence_files_consent import LedgerEvidenceFilesConsentScreen
from .evidence_files_doors import LedgerEvidenceFilesDoorsV1
from .evidence_files_queue import LedgerEvidenceFilesQueueScreen
from .evidence_files_records import LedgerEvidenceFilesRecordsScreen
from .evidence_files_review import LedgerEvidenceFilesReviewScreen
from .tools import LedgerToolV1


def evidence_files_tools(doors: LedgerEvidenceFilesDoorsV1) -> tuple[LedgerToolV1, ...]:
    """Name the six evidence and attachment tools, each building its screen over ``doors``."""

    def records(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerEvidenceFilesRecordsScreen(controller, doors)

    def batch(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerEvidenceFilesBatchScreen(controller, doors)

    def queue(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerEvidenceFilesQueueScreen(controller, doors)

    def review(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerEvidenceFilesReviewScreen(controller, doors)

    def consent(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerEvidenceFilesConsentScreen(controller, doors)

    def attachments(controller: LedgerWorkspaceController) -> LedgerWorkspaceScreen:
        return LedgerEvidenceFilesAttachmentsScreen(controller, doors)

    evidence = LedgerWorkspaceArea.EVIDENCE
    return (
        LedgerToolV1(
            key="ledger.tool.evidence_files.records",
            label_key="tui.ledger.evidence_files.tool.records",
            area=evidence,
            build=records,
        ),
        LedgerToolV1(
            key="ledger.tool.evidence_files.batch",
            label_key="tui.ledger.evidence_files.tool.batch",
            area=evidence,
            build=batch,
        ),
        LedgerToolV1(
            key="ledger.tool.evidence_files.queue",
            label_key="tui.ledger.evidence_files.tool.queue",
            area=evidence,
            build=queue,
        ),
        LedgerToolV1(
            key="ledger.tool.evidence_files.review",
            label_key="tui.ledger.evidence_files.tool.review",
            area=evidence,
            build=review,
        ),
        LedgerToolV1(
            key="ledger.tool.evidence_files.consent",
            label_key="tui.ledger.evidence_files.tool.consent",
            area=evidence,
            build=consent,
        ),
        LedgerToolV1(
            key="ledger.tool.evidence_files.attachments",
            label_key="tui.ledger.evidence_files.tool.attachments",
            area=LedgerWorkspaceArea.ENTRIES,
            build=attachments,
        ),
    )


__all__ = ["evidence_files_tools"]
