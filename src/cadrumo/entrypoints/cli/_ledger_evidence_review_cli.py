"""Behavior handlers for the human review gate over pending extraction drafts.

The operator-facing half of document ingestion. A draft is what a reader
proposed; these verbs are where a person meets it before anything is minted.
``review list`` is the queue and ``review view`` is the one-document surface,
carrying every field with its value, origin, verbatim anchor, grounding outcome
and competing candidates, every deterministic finding, and the blocking findings
that must each be answered individually at confirm.

There is deliberately no ``review confirm --all``. The confirm boundary takes one
document per invocation and one explicit resolution per blocking finding; the
whole value of the gate is the per-document attention it forces.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import typer

from ...application.ledger.confirmation_gate import FindingResolution
from ...application.ledger.evidence_followup_operation import (
    CountryVocabularyAdvisoryProjection,
    LedgerEvidenceReviewViewProjection,
    PartyAttributionAdvisoryProjection,
)
from ...application.ledger.invoice_draft_payloads import EvidenceDraftDiscrepancyPayload
from ...application.ledger.invoice_evidence_operation_dtos import (
    ConfirmationBlockerProjectionV1,
    FieldProvenanceProjectionV1,
    InvoiceDraftProjectionV1,
)
from ...application.operations.public_scalar import PublicDecimal
from ...application.operator_actions.models import ActionReference
from ...core.confirmation_gate import ConfirmationBlockReason, FindingResolutionAction, ReviewAdvisoryKind
from ...core.draft_discrepancy import DraftDiscrepancyKind
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.iva.establishment import StatedCountryCodeStatus
from ._evidence_field_notices import label_reading_fallback_notices
from .common import bad, emit_envelope, resolve_notice_action
from .ledger_business_payloads import (
    EvidenceReviewBlockerPayload,
    EvidenceReviewFieldPayload,
    EvidenceReviewRowPayload,
    EvidenceReviewViewResult,
)
from .runtime_ledger_evidence_followup import (
    run_ledger_evidence_review_list,
    run_ledger_evidence_review_view,
)


def _printed(value: object | None) -> str | None:
    """Return a draft value as the review surface prints it, or ``None``."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, PublicDecimal):
        return format(Decimal(value.decimal), "f")
    return str(getattr(value, "value", value))


def _candidate_payloads(blocker_or_envelope: object) -> list[dict[str, object]]:
    candidates = getattr(blocker_or_envelope, "candidates", ())
    return [candidate.model_dump(mode="json") for candidate in candidates]


def _blocker_payload(blocker: ConfirmationBlockerProjectionV1) -> EvidenceReviewBlockerPayload:
    return EvidenceReviewBlockerPayload.model_validate(
        {
            "blocker_id": blocker.blocker_id,
            "reason": blocker.reason.value,
            "field": blocker.field,
            "detail": blocker.detail,
            "candidates": _candidate_payloads(blocker),
        },
    )


def _field_envelope_payload(envelope: FieldProvenanceProjectionV1 | None) -> dict[str, object]:
    """Project one field's provenance envelope onto its review-row columns.

    A field the reader recovered nothing for still emits every column, so an
    absent reading and a recovered one stay distinguishable on the surface
    rather than collapsing into a missing row.
    """
    if envelope is None:
        return {
            "origin": None,
            "grounding": None,
            "anchor": None,
            "refused_anchor": None,
            "anchor_self_reported": False,
            "candidates": [],
            "note": "",
        }
    return {
        "origin": envelope.origin.value,
        "grounding": envelope.grounding.value,
        "anchor": envelope.anchor,
        # Passed beside the anchor rather than folded into it. The grounding
        # stage clears an anchor it could not locate, so a row showing only the
        # anchor renders a refused claim and an absent one identically -- which
        # is the distinction the envelope records this form to preserve.
        "refused_anchor": envelope.refused_anchor,
        "anchor_self_reported": bool(envelope.anchor_self_reported),
        "candidates": _candidate_payloads(envelope),
        "note": envelope.note,
    }


def _field_payloads(draft: InvoiceDraftProjectionV1) -> list[EvidenceReviewFieldPayload]:
    """Return one review row per scalar draft field, envelope attached when present.

    Every scalar field is emitted, not only the ones an envelope exists for. A
    field the reader recovered nothing for is exactly the field an operator most
    needs to see, and dropping it from the surface would make an absent reading
    indistinguishable from a field the document does not have.
    """
    envelopes = {envelope.field: envelope for envelope in draft.provenance}
    rows: list[EvidenceReviewFieldPayload] = []
    for field in type(draft).model_fields:
        if field in {
            "provenance",
            "discrepancies",
            "lines",
            "iva_breakdown",
            "raw_text_length",
            "facturae_invoice_class",
        }:
            continue
        rows.append(
            EvidenceReviewFieldPayload.model_validate(
                {
                    "field": field,
                    "value": _printed(getattr(draft, field, None)),
                    **_field_envelope_payload(envelopes.get(field)),
                },
            ),
        )
    return rows


def _suggested_kind_basis(draft: InvoiceDraftProjectionV1) -> str:
    """Return what the reading path read the direction suggestion FROM.

    The suggestion is never the decision --- direction is chosen by the operator
    at confirm --- so the surface shows the basis rather than only the answer,
    letting the operator disagree with something specific.
    """
    for envelope in draft.provenance:
        if envelope.field == "suggested_kind":
            return envelope.note or (envelope.anchor or "")
    return ""


def _party_attribution_notice(advisory: PartyAttributionAdvisoryProjection) -> Notice:
    """Project the attribution advisory into the envelope's one diagnostic channel.

    A Notice rather than a field on the review payload, and the distinction is
    substantive. That payload carries each party's printed postal code and
    country verbatim and deliberately never the territory read off them, because
    the reading is the domain's and a second copy of a regulatory boundary on the
    review surface is what that exclusion exists to prevent. An advisory ABOUT a
    territory therefore has no place to attach there. It attaches here instead,
    where the territory is quoted from the domain rather than recomputed -- which
    lets the operator contest a concrete claim ("these values would place the
    customer in Canarias, and nothing checked that they are the customer's")
    without the boundary acquiring a second home.
    """
    context: dict[str, str] = {"fields": ",".join(advisory.fields)}
    for party in advisory.parties:
        context[f"{party.role}_fields"] = ",".join(party.fields)
        context[f"{party.role}_territory_if_attributed"] = (
            party.scope_if_attributed if party.scope_if_attributed is not None else "undetermined"
        )
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="ledger.evidence.review.party_attribution_unverified",
        message=tr(
            "cli.app.ledger.evidence.review.party_attribution_unverified_message",
        ),
        context=context,
    )


def _party_attribution_lines(notice: Notice) -> list[str]:
    """Rebuild the advisory's text-mode lines from the notice itself.

    Read off the notice rather than the advisory so the two renderings cannot
    drift: a JSON consumer and a terminal operator are told the same thing
    because the same object produced both.
    """
    context = notice.context or {}
    lines = [f"advisory\t{notice.code}\t{notice.message}"]
    lines.extend(
        f"attribution_unverified\t{key.removesuffix('_fields')}\t{value}\t"
        f"{context.get(key.removesuffix('_fields') + '_territory_if_attributed', '-')}"
        for key, value in context.items()
        if key.endswith("_fields") and key != "fields"
    )
    return lines


_COUNTRY_NOTICE_CODE: Final[dict[StatedCountryCodeStatus, str]] = {
    StatedCountryCodeStatus.UNASSIGNED: "ledger.evidence.review.country_code_unassigned",
    StatedCountryCodeStatus.UNCATALOGUED: "ledger.evidence.review.country_code_uncatalogued",
}
"""One notice code per kind, because the kinds have different OWNERS.

Both are non-blocking and both name the stated code, so a single notice carrying
every affected party would read identically for a typo the operator fixes off the
page and a gap only a registry commit closes. Splitting on the status keeps that
distinction machine-readable in the notice ``code``, which is what a JSON
consumer routes on, rather than only in the prose.
"""


def _country_notice_message(status: StatedCountryCodeStatus) -> str:
    """Return the operator-facing sentence for one country-vocabulary kind.

    Branching rather than a status-keyed table of keys, because the catalogue
    scaffold discovers keys by reading literal :func:`tr` arguments out of the
    source. A key reached through a table entry is invisible to it, and the key
    is then reported as an orphan and swept out from under the notice.
    """
    if status is StatedCountryCodeStatus.UNASSIGNED:
        return tr("cli.app.ledger.evidence.review.country_code_unassigned_message")
    return tr("cli.app.ledger.evidence.review.country_code_uncatalogued_message")


def _country_vocabulary_notices(advisory: CountryVocabularyAdvisoryProjection) -> list[Notice]:
    """Project the country-vocabulary advisory into one notice per kind.

    Non-blocking on purpose. The bundled vocabulary carries a bounded subset of
    the world's jurisdictions, so a code outside it is an ordinary event for a
    real foreign counterparty; refusing the confirm would make those documents
    unfileable until the registry caught up, and an operator who meets that often
    enough learns to ignore the channel it arrives on. The under-declaration this
    axis was narrowed to close is shut elsewhere and stays shut: an unresolved
    country yields no residency, so the classification criteria do not assemble
    and the zero-rated export category is unreachable whatever this notice says.
    """
    notices: list[Notice] = []
    for status, code in _COUNTRY_NOTICE_CODE.items():
        affected = advisory.by_status(status)
        if not affected:
            continue
        context: dict[str, str] = {"fields": ",".join(party.field for party in affected)}
        for party in affected:
            context[f"{party.role}_country_code"] = party.stated_code
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=code,
                message=_country_notice_message(status),
                context=context,
            ),
        )
    return notices


def _country_vocabulary_lines(notice: Notice) -> list[str]:
    """Rebuild one country notice's text-mode lines from the notice itself.

    Read off the notice rather than the advisory for the reason the sibling
    projection is: a JSON consumer and a terminal operator are told the same
    thing because the same object produced both.
    """
    context = notice.context or {}
    lines = [f"advisory\t{notice.code}\t{notice.message}"]
    lines.extend(
        f"country_code_unresolved\t{key.removesuffix('_country_code')}\t{value}"
        for key, value in context.items()
        if key.endswith("_country_code")
    )
    return lines


def _review_queue_notices(rows: list[EvidenceReviewRowPayload]) -> list[Notice]:
    """Summarise the queue's advisory and blocking population for the operator."""
    notices: list[Notice] = []
    advised = sum(1 for row in rows if row.advisory_count)
    if advised:
        # A count and a route, not a row per advisory. The per-document prose
        # already exists on `show` and repeating it here once per affected
        # draft is how a channel earns the reflex to skip it -- but a queue
        # that never mentions them at all is why these fire into nothing.
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.review.advised_pending",
                message=tr(
                    "cli.app.ledger.evidence.review.advised_pending_message",
                ),
                action=resolve_notice_action(
                    action=ActionReference(action_id="operator.ledger.evidence.review.list"),
                ),
                context={
                    "advised": str(advised),
                    "kinds": ",".join(
                        sorted({value for row in rows for value in row.advisories}),
                    ),
                },
            ),
        )
    blocked = sum(1 for row in rows if row.blocking_count)
    if blocked:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.review.blocked_pending",
                message=tr(
                    "cli.app.ledger.evidence.review.blocked_pending_message",
                ),
                action=resolve_notice_action(
                    action=ActionReference(action_id="operator.ledger.evidence.review.list"),
                ),
                context={"blocked": str(blocked)},
            ),
        )
    return notices


def review_list(
    ctx: typer.Context,
    reason: ConfirmationBlockReason | None = None,
    finding: DraftDiscrepancyKind | None = None,
    advisory: ReviewAdvisoryKind | None = None,
    blocking_only: bool = False,
) -> None:
    """List the review queue, optionally narrowed to one blocking reason, check or advisory."""
    result = run_ledger_evidence_review_list(
        ctx,
        reason=reason,
        finding=finding,
        advisory=advisory,
        blocking_only=blocking_only,
    )
    rows = result.rows
    lines = [f"bucket_id\t{result.bucket_id}", f"pending\t{len(rows)}"]
    lines.extend(
        f"{row.evidence_reference}\t{row.blocking_count}\t"
        f"{','.join(row.reasons) or '-'}\t{row.extractor}\t"
        f"{row.advisory_count}\t{','.join(row.advisories) or '-'}"
        for row in rows
    )
    notices = _review_queue_notices(rows)
    emit_envelope(
        ctx,
        command="ledger.evidence.review.list",
        result=result,
        lines=lines,
        notices=notices,
    )


def _review_view_advisories(
    party_advisory: PartyAttributionAdvisoryProjection | None,
    country_advisory: CountryVocabularyAdvisoryProjection | None,
) -> tuple[list[Notice], list[str]]:
    """Return the non-blocking advisories for one draft, as notices and their text lines.

    Both channels are built from the same notice so the JSON envelope and the
    printed dump cannot state different advisories for the same document.
    """
    notices: list[Notice] = []
    lines: list[str] = []
    if party_advisory is not None:
        attribution_notice = _party_attribution_notice(party_advisory)
        notices.append(attribution_notice)
        lines.extend(_party_attribution_lines(attribution_notice))
    if country_advisory is not None:
        for country_notice in _country_vocabulary_notices(country_advisory):
            notices.append(country_notice)
            lines.extend(_country_vocabulary_lines(country_notice))
    return notices, lines


def _review_view_payload(
    bucket_id: str,
    projection: LedgerEvidenceReviewViewProjection,
    fields: list[EvidenceReviewFieldPayload],
    blockers: tuple[ConfirmationBlockerProjectionV1, ...],
) -> dict[str, object]:
    """Project one stored draft into the review view's JSON result shape."""
    draft = projection.draft
    return {
        "bucket_id": bucket_id,
        "evidence_reference": projection.evidence_reference,
        "extractor": projection.extractor,
        "drafted_at": projection.drafted_at.isoformat(),
        "transcription_sha256": draft.transcription_sha256,
        "suggested_kind": draft.suggested_kind.value if draft.suggested_kind is not None else None,
        "suggested_kind_basis": _suggested_kind_basis(draft),
        "fields": [row.model_dump(mode="json") for row in fields],
        "discrepancies": [
            EvidenceDraftDiscrepancyPayload.model_validate(
                {
                    "kind": finding.kind.value,
                    "field": finding.field,
                    "detail": finding.detail,
                    "expected": None if finding.expected is None else finding.expected.decimal,
                    "observed": None if finding.observed is None else finding.observed.decimal,
                }
            ).model_dump(mode="json")
            for finding in draft.discrepancies
        ],
        "blockers": [_blocker_payload(blocker).model_dump(mode="json") for blocker in blockers],
    }


def _review_view_lines(
    bucket_id: str,
    projection: LedgerEvidenceReviewViewProjection,
    fields: list[EvidenceReviewFieldPayload],
    blockers: tuple[ConfirmationBlockerProjectionV1, ...],
) -> list[str]:
    """Render the review view's tab-separated text rows in contract order."""
    draft = projection.draft
    lines = [
        f"bucket_id\t{bucket_id}",
        f"evidence_reference\t{projection.evidence_reference}",
        f"extractor\t{projection.extractor}",
        f"drafted_at\t{projection.drafted_at.isoformat()}",
        f"transcription_sha256\t{draft.transcription_sha256 or '-'}",
        f"suggested_kind\t{(draft.suggested_kind.value if draft.suggested_kind is not None else '-')}",
    ]
    lines.extend(
        f"field\t{row.field}\t{row.value or '-'}\t{row.origin or '-'}\t{row.grounding or '-'}\t{row.anchor or '-'}"
        for row in fields
    )
    lines.extend(
        f"blocker\t{blocker.blocker_id}\t{blocker.reason.value}\t{blocker.field or '-'}" for blocker in blockers
    )
    return lines


def _review_view_notices(
    projection: LedgerEvidenceReviewViewProjection,
    blockers: tuple[ConfirmationBlockerProjectionV1, ...],
) -> tuple[list[Notice], list[str]]:
    """Return advisory notices/lines, the stored label-reading degradation, then the blocking notice.

    Without the degradation an empty field on this surface reads as a field the
    document does not print, when the reader never looked for it.
    """
    notices, lines = _review_view_advisories(
        projection.party_attribution_advisory,
        projection.country_vocabulary_advisory,
    )
    fallback = projection.label_reading_fallback
    notices.extend(label_reading_fallback_notices(None if fallback is None else fallback.to_fallback()))
    if blockers:
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.evidence.review.blocked",
                message=tr("cli.app.ledger.evidence.review.blocked_message"),
                context={"blocker_ids": ",".join(blocker.blocker_id for blocker in blockers)},
            )
        )
    return notices, lines


def review_view(ctx: typer.Context, reference: str) -> None:
    """Show every reviewable field of one pending draft, with its blocking findings."""
    projection = run_ledger_evidence_review_view(ctx, evidence_reference=reference)
    bucket_id = str(projection.profile_id)
    blockers = projection.blockers
    draft = projection.draft
    fields = _field_payloads(draft)
    payload = _review_view_payload(bucket_id, projection, fields, blockers)
    lines = _review_view_lines(bucket_id, projection, fields, blockers)
    notices, advisory_lines = _review_view_notices(projection, blockers)
    lines.extend(advisory_lines)
    emit_envelope(
        ctx,
        command="ledger.evidence.review.view",
        result=EvidenceReviewViewResult.model_validate(payload),
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
        raise bad(
            tr("cli.app.ledger.evidence.review.resolve_shape"),
        )
    action_token, _, payload = remainder.partition(":")
    action = _RESOLUTION_ACTION_TOKENS.get(action_token.strip().casefold())
    if action is None:
        accepted = ", ".join(sorted(_RESOLUTION_ACTION_TOKENS))
        raise bad(
            tr("cli.app.ledger.evidence.review.resolve_action") + f" ({accepted})",
        )
    if action is FindingResolutionAction.ATTEST:
        return FindingResolution(blocker_id=blocker_id.strip(), action=action, note=payload.strip())
    return FindingResolution(blocker_id=blocker_id.strip(), action=action, value=payload.strip())


__all__ = ["parse_finding_resolution", "review_list", "review_view"]
