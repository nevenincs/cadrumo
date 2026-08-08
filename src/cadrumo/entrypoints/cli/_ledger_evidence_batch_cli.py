"""Typer registration for the bounded evidence batch run.

The operator half of batch ingestion. The run itself belongs to
:func:`~cadrumo.application.ledger.run_evidence_batch`, which owns per-item
truth, deterministic ordering, idempotent re-run and the inference lane; this
module only resolves the operator's sources, projects the run's typed rows onto
the JSON envelope, and turns the run's own signals into operator-facing text.
Nothing here re-decides what a row means.

Two reporting rules carry the design, and both are about what an operator is
trained to believe:

**A refusal and a deferral are separate signals.** ``any_failed`` says a
document was rejected; ``any_deferred`` says work this run did not attempt is
still outstanding. They render as different notices with different codes, and
only the first sets a non-zero exit -- because a paused item is a machine
condition with a remediation, not a bad document, and a failing exit on it would
read as breakage.

**A held document has not failed either.** ``pending_review`` is the review gate
working: the run produced a draft a person must adjudicate. It reports as an
info notice pointing at the review queue and never touches the exit status.

See Also:
    :func:`~cadrumo.application.ledger.run_evidence_batch`
        The run under this surface.
    :class:`~cadrumo.application.ledger.BatchRunResult`
        The typed result this module projects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.output_rendering import OutputFormat
from ...domain.iva import InvoiceKind
from ._common import _bad, _emit_envelope, _format_of, _state, _tx_repo
from ._ledger_evidence_batch_payloads import EvidenceBatchResult

if TYPE_CHECKING:
    from ...application.ledger import BatchItemResult, BatchRunResult

__all__ = ["register_evidence_batch_command"]

#: The verb an operator runs next on a document the batch held for review. Named
#: once so the notice and any later surface cannot drift apart.
_REVIEW_QUEUE_COMMAND = "aeat app ledger evidence review list"


def register_evidence_batch_command(evidence_app: typer.Typer) -> None:
    """Mount ``aeat app ledger evidence batch`` on the evidence sub-app."""

    @evidence_app.command(
        "batch",
        help=tr(
            "cli.app.ledger.evidence.batch_help",
            default=(
                "Ingest every document in a directory (or each --file) into evidence and a reviewable "
                "draft, one typed result row per document."
            ),
        ),
    )
    def evidence_batch(
        ctx: typer.Context,
        directory: str | None = typer.Argument(
            None,
            help=tr(
                "cli.app.ledger.evidence.batch_directory_help",
                default="Directory whose files are ingested. Combine with or replace by repeated --file.",
            ),
        ),
        kind: InvoiceKind = typer.Option(
            ...,
            "--kind",
            help=tr(
                "cli.app.ledger.invoice.kind_help",
                default="Invoice kind: issued (a customer owes us) or received (we owe a vendor).",
            ),
        ),
        file: list[str] = typer.Option(
            [],
            "--file",
            help=tr(
                "cli.app.ledger.evidence.batch_file_help",
                default="One document to ingest. Repeat once per document; combines with a directory.",
            ),
        ),
    ) -> None:
        """Run the ingestion pipeline over every source, one typed row per document.

        One document cannot end the run: every source finishes in a row of its
        own -- ingested, an idempotent no-op, refused with its reason, held for
        review, or deferred because the machine could not admit a reading model
        -- and the run reports the list plus the tally. The exit status reads
        "any item was refused", never "the first item was refused".

        A re-run over the same sources is the resume. Each item's identity is
        its content address plus the declared kind, so an already-ingested
        document is reported as a no-op and nothing is written twice.
        """
        sources: list[str] = [*file]
        if directory is not None:
            sources.insert(0, directory)
        if not sources:
            raise _bad(
                tr(
                    "cli.app.ledger.evidence.batch_source_required",
                    default="Supply a directory argument, one or more --file options, or both.",
                ),
            )

        from ...application.ledger import run_evidence_batch

        bucket_id = _tx_repo(_state()).bucket_id
        text_mode = _format_of(ctx) is not OutputFormat.JSON
        run = run_evidence_batch(
            bucket_id=bucket_id,
            sources=sources,
            direction=kind,
            # Progress is a TEXT-mode stream. In JSON the complete row set on
            # `result` already carries every item, and echoing progress there
            # would both break the single-document contract and duplicate the
            # rows -- the second progress channel the design refuses.
            on_item=(lambda item: typer.echo(_progress_line(item))) if text_mode else None,
        )

        _emit_envelope(
            ctx,
            command="ledger.evidence.batch",
            result=_batch_payload(run, bucket_id=bucket_id, direction=kind),
            lines=_batch_text_lines(run, bucket_id=bucket_id, direction=kind),
            notices=_run_notices(run),
        )
        if run.any_failed:
            raise typer.Exit(code=1)


def _batch_payload(run: BatchRunResult, *, bucket_id: str, direction: InvoiceKind) -> EvidenceBatchResult:
    """Project the run onto its wire schema from the run's own dump.

    Built by re-validating the engine's serialisation rather than by copying
    field by field, so a row field added upstream either arrives here by name or
    reds the strict schema. A hand-written projection would silently drop it.
    """
    return EvidenceBatchResult.model_validate(
        {
            "bucket_id": bucket_id,
            "direction": direction.value,
            "items": [item.model_dump(mode="json") for item in run.items],
            "unresolved": [source.model_dump(mode="json") for source in run.unresolved],
            "inference_pause": (run.inference_pause.model_dump(mode="json") if run.inference_pause else None),
            "summary": run.summary,
            "deterministic_completed": run.deterministic_completed,
            "paced": run.paced,
            "any_failed": run.any_failed,
            "any_deferred": run.any_deferred,
        },
    )


def _progress_line(item: BatchItemResult) -> str:
    """Return the text-mode progress line for one completed item.

    Rebuilt from the same notice the item would carry, so the streamed line and
    the notice cannot say different things.
    """
    return _notice_line(_item_notice(item))


def _item_notice(item: BatchItemResult) -> Notice:
    """Return the per-item progress notice.

    Severity follows the row: only a refusal is a warning. A no-op is the
    idempotent success, and a held document is the review gate doing its job --
    marking either of them as a warning would teach an operator to read a
    correct run as a troubled one.
    """
    severity = NoticeSeverity.WARNING if item.status == "refused" else NoticeSeverity.INFO
    return Notice(
        severity=severity,
        code=f"ledger.evidence.batch.item.{item.status}",
        message=tr(
            "cli.app.ledger.evidence.batch_progress_message",
            source=item.source_name,
            status=item.status,
            default=f"{item.source_name}: {item.status}",
        ),
        context={
            "source_name": item.source_name,
            "status": item.status,
            "content_address": item.content_address,
            "refusal_code": item.refusal_code or "-",
        },
    )


def _run_notices(run: BatchRunResult) -> list[Notice]:
    """Return the run-level notices, one per distinct outcome class.

    Refusal, deferral and pending review are three different things an operator
    must act on differently, so each gets its own code rather than one
    "something happened" advisory.
    """
    notices: list[Notice] = []
    if run.any_failed:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.batch.items_refused",
                message=tr(
                    "cli.app.ledger.evidence.batch_items_refused_message",
                    default=(
                        "Some documents were refused. Every other document in the run still completed; "
                        "the refused rows name what was seen."
                    ),
                ),
                context={
                    "refused": str(run.count_of("refused")),
                    "unresolved": str(len(run.unresolved)),
                },
            ),
        )
    pause = run.inference_pause
    if run.any_deferred and pause is not None:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.batch.work_deferred",
                message=tr(
                    "cli.app.ledger.evidence.batch_work_deferred_message",
                    default=(
                        "Some documents were not read because no reading model could be run. Nothing was "
                        "guessed from them and nothing failed; re-run once the cause below is cleared."
                    ),
                ),
                # Straight from the probe that measured the condition, never a
                # fixed verb: telling an operator to download a model they may
                # already have is a wrong instruction, not merely a vague one.
                suggestion=pause.remediation,
                context={
                    "paused": str(run.count_of("paused")),
                    "reason": pause.reason,
                    "detail": pause.detail,
                    "causes": ",".join(pause.causes) or "-",
                },
            ),
        )
    held = run.count_of("pending_review")
    if held:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.evidence.batch.pending_review",
                message=tr(
                    "cli.app.ledger.evidence.batch_pending_review_message",
                    default=(
                        "Some drafts carry a finding a person must adjudicate before an invoice is minted. "
                        "They are held, not failed."
                    ),
                ),
                suggestion=_REVIEW_QUEUE_COMMAND,
                context={"pending_review": str(held)},
            ),
        )
    return notices


def _notice_line(notice: Notice) -> str:
    # MACHINE-FORMAT-RATIONALE-LEDGER-EVIDENCE-BATCH-NOTICE: tab-separated machine
    # record (severity, code, message, suggestion), matching the notice line shape
    # the modelo discovery surface already emits.
    return f"notice\t{notice.severity.value}\t{notice.code}\t{notice.message}\t{notice.suggestion or '-'}"


def _batch_text_lines(run: BatchRunResult, *, bucket_id: str, direction: InvoiceKind) -> list[str]:
    """Return the closing text block: the tally, then every row needing attention.

    The per-item progress already streamed, so this does not repeat the clean
    rows. What it does repeat is every refusal, every unreadable source and the
    pause -- the things an operator scrolled past while the run was working.
    """
    lines = [
        f"bucket_id\t{bucket_id}",
        f"kind\t{direction.value}",
        f"items\t{len(run.items)}",
    ]
    lines.extend(f"{status}\t{count}" for status, count in sorted(run.summary.items()))
    lines.append(f"unresolved\t{len(run.unresolved)}")
    for item in run.items:
        if item.status == "refused":
            # MACHINE-FORMAT-RATIONALE-LEDGER-EVIDENCE-BATCH-REFUSAL: tab-separated
            # machine record (source, code, detail).
            lines.append(f"refused\t{item.source_name}\t{item.refusal_code}\t{item.refusal_detail}")
    for source in run.unresolved:
        # MACHINE-FORMAT-RATIONALE-LEDGER-EVIDENCE-BATCH-UNRESOLVED: tab-separated
        # machine record (source, code, detail).
        lines.append(f"unreadable\t{source.source_name}\t{source.refusal_code}\t{source.refusal_detail}")
    pause = run.inference_pause
    if pause is not None:
        lines.append(f"paused_reason\t{pause.reason}")
        lines.append(f"paused_detail\t{pause.detail}")
        lines.append(f"paused_remediation\t{pause.remediation}")
        lines.append(f"paused_causes\t{','.join(pause.causes) or '-'}")
    lines.append(f"any_failed\t{run.any_failed}")
    lines.append(f"any_deferred\t{run.any_deferred}")
    lines.extend(_notice_line(notice) for notice in _run_notices(run))
    return lines
