"""Typer registration for the human review gate over pending extraction drafts.

The operator-facing half of document ingestion. A draft is what a reader
proposed; these verbs are where a person meets it before anything is minted.
``review list`` is the queue and ``review show`` is the one-document surface,
carrying every field with its value, origin, verbatim anchor, grounding outcome
and competing candidates, every deterministic finding, and the blocking findings
that must each be answered individually at confirm.

There is deliberately no ``review confirm --all``. The confirm boundary takes one
document per invocation and one explicit resolution per blocking finding; the
whole value of the gate is the per-document attention it forces.
"""

from __future__ import annotations

import typer

from ...application.ledger import (
    ConfirmationBlocker,
    FindingResolution,
    InvoiceDraft,
    StoredExtractionDraft,
    confirmation_blockers,
    load_extraction_drafts,
)
from ...core import ConfirmationBlockReason, DraftDiscrepancyKind, FindingResolutionAction
from ...core.config import load_settings
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._common import _bad, _emit_envelope, _state, _tx_repo
from ._ledger_business_payloads import (
    EvidenceReviewBlockerPayload,
    EvidenceReviewFieldPayload,
    EvidenceReviewListResult,
    EvidenceReviewRowPayload,
    EvidenceReviewShowResult,
)

review_app = typer.Typer(
    name="review",
    help=tr(
        "cli.app.ledger.evidence.review.group_help",
        default="Review pending extraction drafts before confirming them into invoices.",
    ),
    no_args_is_help=True,
)


def register_evidence_review_commands(evidence_app: typer.Typer) -> None:
    """Mount and register the review verbs under ``evidence``."""
    evidence_app.add_typer(review_app, name="review")
    _register_review_list_command()
    _register_review_show_command()


def _printed(value: object | None) -> str | None:
    """Return a draft value as the review surface prints it, or ``None``."""
    if value is None:
        return None
    if hasattr(value, "as_tuple"):
        return format(value, "f")
    return str(getattr(value, "value", value))


def _candidate_payloads(blocker_or_envelope: object) -> list[dict[str, object]]:
    candidates = getattr(blocker_or_envelope, "candidates", ())
    return [candidate.model_dump(mode="json") for candidate in candidates]


def _blocker_payload(blocker: ConfirmationBlocker) -> EvidenceReviewBlockerPayload:
    return EvidenceReviewBlockerPayload.model_validate(
        {
            "blocker_id": blocker.blocker_id,
            "reason": blocker.reason.value,
            "field": blocker.field,
            "detail": blocker.detail,
            "candidates": _candidate_payloads(blocker),
        },
    )


def _field_payloads(draft: InvoiceDraft) -> list[EvidenceReviewFieldPayload]:
    """Return one review row per scalar draft field, envelope attached when present.

    Every scalar field is emitted, not only the ones an envelope exists for. A
    field the reader recovered nothing for is exactly the field an operator most
    needs to see, and dropping it from the surface would make an absent reading
    indistinguishable from a field the document does not have.
    """
    envelopes = {envelope.field: envelope for envelope in draft.provenance}
    rows: list[EvidenceReviewFieldPayload] = []
    for field in type(draft).model_fields:
        if field in {"provenance", "discrepancies", "lines", "iva_breakdown", "raw_text_length"}:
            continue
        envelope = envelopes.get(field)
        rows.append(
            EvidenceReviewFieldPayload.model_validate(
                {
                    "field": field,
                    "value": _printed(getattr(draft, field, None)),
                    "origin": envelope.origin.value if envelope is not None else None,
                    "grounding": envelope.grounding.value if envelope is not None else None,
                    "anchor": envelope.anchor if envelope is not None else None,
                    "anchor_self_reported": bool(envelope is not None and envelope.anchor_self_reported),
                    "candidates": _candidate_payloads(envelope) if envelope is not None else [],
                    "note": envelope.note if envelope is not None else "",
                },
            ),
        )
    return rows


def _suggested_kind_basis(draft: InvoiceDraft) -> str:
    """Return what the reading path read the direction suggestion FROM.

    The suggestion is never the decision --- direction is chosen by the operator
    at confirm --- so the surface shows the basis rather than only the answer,
    letting the operator disagree with something specific.
    """
    for envelope in draft.provenance:
        if envelope.field == "suggested_kind":
            return envelope.note or (envelope.anchor or "")
    return ""


def _register_review_list_command() -> None:
    @review_app.command(
        "list",
        help=tr(
            "cli.app.ledger.evidence.review.list_help",
            default="List pending extraction drafts awaiting human review.",
        ),
    )
    def review_list(
        ctx: typer.Context,
        reason: ConfirmationBlockReason | None = typer.Option(
            None,
            "--reason",
            help=tr(
                "cli.app.ledger.evidence.review.reason_help",
                default="Show only drafts blocked for this reason.",
            ),
        ),
        finding: DraftDiscrepancyKind | None = typer.Option(
            None,
            "--finding",
            help=tr(
                "cli.app.ledger.evidence.review.finding_help",
                default="Show only drafts whose document failed this deterministic check.",
            ),
        ),
        blocking_only: bool = typer.Option(
            False,
            "--blocking",
            help=tr(
                "cli.app.ledger.evidence.review.blocking_help",
                default="Show only drafts that cannot be confirmed until a finding is answered.",
            ),
        ),
    ) -> None:
        """List the review queue, optionally narrowed to one blocking reason or check."""
        bucket_id = _tx_repo(_state()).bucket_id
        document = load_extraction_drafts(bucket_id, load_settings())

        filters: list[str] = []
        if reason is not None:
            filters.append(f"reason={reason.value}")
        if finding is not None:
            filters.append(f"finding={finding.value}")
        if blocking_only:
            filters.append("blocking=true")

        rows: list[EvidenceReviewRowPayload] = []
        for stored in sorted(document.drafts, key=lambda row: row.evidence_reference):
            blockers = confirmation_blockers(stored.draft)
            reasons = sorted({blocker.reason.value for blocker in blockers})
            if reason is not None and reason.value not in reasons:
                continue
            if finding is not None and all(item.kind is not finding for item in stored.draft.discrepancies):
                continue
            if blocking_only and not blockers:
                continue
            rows.append(
                EvidenceReviewRowPayload.model_validate(
                    {
                        "evidence_reference": stored.evidence_reference,
                        "extractor": stored.extractor,
                        "drafted_at": stored.drafted_at.isoformat(),
                        "blocking_count": len(blockers),
                        "reasons": reasons,
                    },
                ),
            )

        lines = [f"bucket_id\t{bucket_id}", f"pending\t{len(rows)}"]
        lines.extend(
            f"{row.evidence_reference}\t{row.blocking_count}\t{','.join(row.reasons) or '-'}\t{row.extractor}"
            for row in rows
        )
        notices: list[Notice] = []
        blocked = sum(1 for row in rows if row.blocking_count)
        if blocked:
            notices.append(
                Notice(
                    severity=NoticeSeverity.WARNING,
                    code="ledger.evidence.review.blocked_pending",
                    message=tr(
                        "cli.app.ledger.evidence.review.blocked_pending_message",
                        default=(
                            "Some pending documents carry findings that must each be answered before "
                            "they can be confirmed. Inspect one with `review show`."
                        ),
                    ),
                    context={"blocked": str(blocked)},
                ),
            )
        _emit_envelope(
            ctx,
            command="ledger.evidence.review.list",
            result=EvidenceReviewListResult.model_validate(
                {"bucket_id": bucket_id, "filters": filters, "rows": [row.model_dump(mode="json") for row in rows]},
            ),
            lines=lines,
            notices=notices,
        )


def _register_review_show_command() -> None:
    @review_app.command(
        "show",
        help=tr(
            "cli.app.ledger.evidence.review.show_help",
            default="Show one pending draft field by field, with its findings and blockers.",
        ),
    )
    def review_show(
        ctx: typer.Context,
        reference: str = typer.Argument(
            ...,
            help=tr(
                "cli.app.ledger.evidence.review.reference_help",
                default="Evidence or attachment reference the pending draft was read from.",
            ),
        ),
    ) -> None:
        """Show every reviewable field of one pending draft, with its blocking findings."""
        bucket_id = _tx_repo(_state()).bucket_id
        document = load_extraction_drafts(bucket_id, load_settings())
        stored: StoredExtractionDraft | None = next(
            (row for row in document.drafts if row.evidence_reference == reference),
            None,
        )
        if stored is None:
            known = ", ".join(sorted(row.evidence_reference for row in document.drafts)) or "none"
            raise _bad(
                tr(
                    "cli.app.ledger.evidence.review.unknown_reference",
                    default="No pending draft for that reference.",
                )
                + f" ({known})",
            )

        draft = stored.draft
        blockers = confirmation_blockers(draft)
        fields = _field_payloads(draft)
        payload = {
            "bucket_id": bucket_id,
            "evidence_reference": stored.evidence_reference,
            "extractor": stored.extractor,
            "drafted_at": stored.drafted_at.isoformat(),
            "transcription_sha256": draft.transcription_sha256,
            "suggested_kind": draft.suggested_kind.value if draft.suggested_kind is not None else None,
            "suggested_kind_basis": _suggested_kind_basis(draft),
            "fields": [row.model_dump(mode="json") for row in fields],
            "discrepancies": [finding.model_dump(mode="json") for finding in draft.discrepancies],
            "blockers": [_blocker_payload(blocker).model_dump(mode="json") for blocker in blockers],
        }
        lines = [
            f"bucket_id\t{bucket_id}",
            f"evidence_reference\t{stored.evidence_reference}",
            f"extractor\t{stored.extractor}",
            f"drafted_at\t{stored.drafted_at.isoformat()}",
            f"transcription_sha256\t{draft.transcription_sha256 or '-'}",
            f"suggested_kind\t{draft.suggested_kind.value if draft.suggested_kind is not None else '-'}",
        ]
        lines.extend(
            f"field\t{row.field}\t{row.value or '-'}\t{row.origin or '-'}\t{row.grounding or '-'}\t{row.anchor or '-'}"
            for row in fields
        )
        lines.extend(
            f"blocker\t{blocker.blocker_id}\t{blocker.reason.value}\t{blocker.field or '-'}" for blocker in blockers
        )
        notices: list[Notice] = []
        if blockers:
            notices.append(
                Notice(
                    severity=NoticeSeverity.WARNING,
                    code="ledger.evidence.review.blocked",
                    message=tr(
                        "cli.app.ledger.evidence.review.blocked_message",
                        default=(
                            "This document cannot be confirmed until every finding below is answered "
                            "individually. Each answer names one finding by its id."
                        ),
                    ),
                    suggestion=(
                        f"aeat app ledger evidence confirm --evidence-id {stored.evidence_reference} "
                        f"--resolve {blockers[0].blocker_id}=attest:<why>"
                    ),
                    context={"blocker_ids": ",".join(blocker.blocker_id for blocker in blockers)},
                ),
            )
        _emit_envelope(
            ctx,
            command="ledger.evidence.review.show",
            result=EvidenceReviewShowResult.model_validate(payload),
            lines=lines,
            notices=notices,
        )


_RESOLUTION_ACTION_TOKENS: dict[str, FindingResolutionAction] = {
    "choose": FindingResolutionAction.CHOOSE_CANDIDATE,
    "supply": FindingResolutionAction.SUPPLY_VALUE,
    "attest": FindingResolutionAction.ATTEST,
}
"""Operator-typed token for each resolution action.

Short tokens rather than the enum's own snake_case values: the operator types
these once per blocking finding, and ``choose_candidate`` typed by hand is a
transcription error waiting to happen. The mapping is the single place the two
vocabularies meet.
"""


def parse_finding_resolution(raw: str) -> FindingResolution:
    """Parse one ``--resolve <blocker-id>=<action>:<payload>`` option.

    Args:
        raw: The option value exactly as the operator typed it.

    Returns:
        The typed resolution, whose own validator then enforces that the payload
        matches the action.

    Raises:
        click.UsageError: When the option is not in the documented shape, or
            names an action outside the closed set. Refused here rather than
            coerced: a resolution the operator mistyped must not silently become
            a different answer to a blocking finding.
    """
    blocker_id, separator, remainder = raw.partition("=")
    if not separator:
        raise _bad(
            tr(
                "cli.app.ledger.evidence.review.resolve_shape",
                default="Each --resolve is <finding-id>=<choose|supply|attest>:<value-or-reason>.",
            ),
        )
    action_token, _, payload = remainder.partition(":")
    action = _RESOLUTION_ACTION_TOKENS.get(action_token.strip().casefold())
    if action is None:
        accepted = ", ".join(sorted(_RESOLUTION_ACTION_TOKENS))
        raise _bad(
            tr(
                "cli.app.ledger.evidence.review.resolve_action",
                default="Unknown resolution action.",
            )
            + f" ({accepted})",
        )
    if action is FindingResolutionAction.ATTEST:
        return FindingResolution(blocker_id=blocker_id.strip(), action=action, note=payload.strip())
    return FindingResolution(blocker_id=blocker_id.strip(), action=action, value=payload.strip())


__all__ = ["parse_finding_resolution", "register_evidence_review_commands", "review_app"]
