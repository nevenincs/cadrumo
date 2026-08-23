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

import json
from decimal import Decimal
from typing import TYPE_CHECKING

import typer

from ...application.operator_actions import ActionReference
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity, ResolvedNoticeAction
from ...core.output_rendering import OutputFormat
from ...domain.iva import InvoiceKind
from ._common import (
    _bad,
    _emit_envelope,
    _format_of,
    _state,
    _tx_repo,
    emit_progress_line,
    resolve_cli_precondition_action,
    resolve_notice_action,
)
from ._config._status_rendering import precondition_action_lines
from ._ledger_evidence_batch_payloads import EvidenceBatchResult

if TYPE_CHECKING:
    from ...application.ledger import BatchItemResult, BatchRunResult, UnresolvedBatchSource
    from ...application.operator_actions import PreconditionVerdict

__all__ = ["evidence_batch"]


def evidence_batch(
    ctx: typer.Context,
    *,
    directory: str | None = None,
    kind: InvoiceKind,
    file: tuple[str, ...] = (),
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
        raise _bad(tr("cli.app.ledger.evidence.batch_source_required"))
    from ...application.ledger import run_evidence_batch

    bucket_id = _tx_repo(_state()).bucket_id
    text_mode = _format_of(ctx) is not OutputFormat.JSON
    run = run_evidence_batch(
        bucket_id=bucket_id,
        sources=sources,
        direction=kind,
        on_item=(lambda item: emit_progress_line(_progress_line(item))) if text_mode else None,
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


def _refusal_projection(verdict: PreconditionVerdict | None) -> dict[str, object]:
    """Return the wire halves of one typed refusal: its facts and its resolved action.

    The facts are the application's own evidence values, carried verbatim. The
    action is resolved here because only the CLI knows the live action surface;
    a verdict with no bound recovery resolves to its explicit no-recovery
    outcome rather than to an invented instruction.
    """
    if verdict is None:
        return {"refusal_facts": {}, "refusal_action": None}
    facts: dict[str, str | int | bool | Decimal] = {}
    for evidence in verdict.evidence:
        facts.update(evidence.values)
    return {
        "refusal_facts": facts,
        "refusal_action": resolve_cli_precondition_action(verdict),
    }


def _item_payload(item: BatchItemResult) -> dict[str, object]:
    """Return one item row on the wire, with its verdict resolved into two fields."""
    dumped = _string_keyed_payload(item.model_dump(mode="json", exclude={"refusal_verdict"}))
    return {**dumped, **_refusal_projection(item.refusal_verdict)}


def _unresolved_payload(source: UnresolvedBatchSource) -> dict[str, object]:
    """Return one unreadable-source row on the wire, with its verdict resolved."""
    dumped = _string_keyed_payload(source.model_dump(mode="json", exclude={"refusal_verdict"}))
    return {**dumped, **_refusal_projection(source.refusal_verdict)}


def _string_keyed_payload(value: object) -> dict[str, object]:
    """Validate a JSON model dump's mapping shape at the CLI boundary."""
    if not isinstance(value, dict):
        raise TypeError("CLI payload dump must be a mapping")
    payload: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("CLI payload keys must be text")
        payload[key] = item
    return payload


def _batch_payload(run: BatchRunResult, *, bucket_id: str, direction: InvoiceKind) -> EvidenceBatchResult:
    """Project the run onto its wire schema from the run's own dump.

    Built by re-validating the engine's serialisation rather than by copying
    field by field, so a row field added upstream either arrives here by name or
    reds the strict schema. A hand-written projection would silently drop it.

    The one field that cannot arrive by name is the refusal verdict: the engine
    owns a typed ``PreconditionVerdict`` while the wire carries its facts beside
    the action this transport resolves. That resolution is the CLI's own job,
    so it is spelled out here rather than dumped.
    """
    return EvidenceBatchResult.model_validate(
        {
            "bucket_id": bucket_id,
            "direction": direction.value,
            "items": [_item_payload(item) for item in run.items],
            "unresolved": [_unresolved_payload(source) for source in run.unresolved],
            "inference_pause": (
                {
                    "facts": run.inference_pause.facts,
                    "precondition_action": resolve_cli_precondition_action(run.inference_pause.precondition_verdict),
                }
                if run.inference_pause
                else None
            ),
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
                ),
                action=resolve_cli_precondition_action(pause.precondition_verdict),
                context={
                    "paused": str(run.count_of("paused")),
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
                ),
                action=resolve_notice_action(
                    action=ActionReference(action_id="operator.ledger.evidence.review.list"),
                ),
                context={"pending_review": str(held)},
            ),
        )
    return notices


def _notice_line(notice: Notice) -> str:
    # MACHINE-FORMAT-RATIONALE-LEDGER-EVIDENCE-BATCH-NOTICE: tab-separated machine
    # record. A fully-resolved action is rendered by its typed identity, target,
    # and materialised bindings; notices without one do not gain a synthetic
    # command field.
    values = ["notice", notice.severity.value, notice.code, notice.message]
    notice_action = notice.action
    if isinstance(notice_action, ResolvedNoticeAction):
        action_reference = notice_action.action
        values.extend(
            [
                action_reference.action_id,
                action_reference.target_command_key,
                ",".join(f"{binding.argument_name}={binding.value}" for binding in notice_action.argument_bindings)
                or "-",
            ],
        )
    return "\t".join(values)


def _condition_of(verdict: PreconditionVerdict | None) -> str:
    """Return the failed-condition identity a refusal row reports."""
    return "-" if verdict is None else verdict.failed_condition_id


def _refusal_lines(verdict: PreconditionVerdict | None) -> list[str]:
    """Return the fact and resolved-action lines beneath one refusal row.

    Derived from the same verdict the JSON payload resolves, so the two
    surfaces cannot report different reasons for the same refusal.
    """
    if verdict is None:
        return []
    lines = [
        # MACHINE-FORMAT-RATIONALE-LEDGER-EVIDENCE-BATCH-REFUSAL-FACT: tab-separated
        # machine record (key, JSON value).
        f"refusal.facts.{key}\t{json.dumps(value, ensure_ascii=False, sort_keys=True)}"
        for evidence in verdict.evidence
        for key, value in sorted(evidence.values.items())
    ]
    lines.extend(precondition_action_lines(resolve_cli_precondition_action(verdict)))
    return lines


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
            # machine record (source, code, condition).
            lines.append(f"refused\t{item.source_name}\t{item.refusal_code}\t{_condition_of(item.refusal_verdict)}")
            lines.extend(_refusal_lines(item.refusal_verdict))
    for source in run.unresolved:
        # MACHINE-FORMAT-RATIONALE-LEDGER-EVIDENCE-BATCH-UNRESOLVED: tab-separated
        # machine record (source, code, condition).
        lines.append(
            f"unreadable\t{source.source_name}\t{source.refusal_code}\t{_condition_of(source.refusal_verdict)}",
        )
        lines.extend(_refusal_lines(source.refusal_verdict))
    pause = run.inference_pause
    if pause is not None:
        lines.extend(
            f"paused.facts.{key}\t{json.dumps(value, ensure_ascii=False, sort_keys=True)}"
            for key, value in sorted(pause.facts.items())
        )
        lines.extend(
            f"paused.{line}"
            for line in precondition_action_lines(resolve_cli_precondition_action(pause.precondition_verdict))
        )
    lines.append(f"any_failed\t{run.any_failed}")
    lines.append(f"any_deferred\t{run.any_deferred}")
    lines.extend(_notice_line(notice) for notice in _run_notices(run))
    return lines
