"""Operator surface for off-host consent: what was sent, and the way back on-host.

Two verbs under ``aeat app ledger evidence consent``. ``list`` enumerates the
profile's off-host dispatches and marks the artefacts derived from them;
``rederive`` re-reads one of those artefacts on this host from its cached
transcription.

**Both surfaces state that transmitted bytes cannot be recalled, every time.**
The statement is carried in the JSON payload as well as the rendered lines,
because an agent consuming the envelope never sees prose, and this is the one
caveat on this surface an operator must not act without. It is unconditional:
an empty history is still surfaced with the caveat, since an operator with no
history is precisely the one deciding whether to enable the route.

See Also:
    :func:`~application.ledger.consent_withdrawal.survey_cloud_consent`
        The enumeration behind ``consent list``.
    :func:`~application.ledger.consent_withdrawal.rederive_artefact_on_host`
        The on-host re-derivation behind ``consent rederive``.
"""

from __future__ import annotations

import typer

from ...application.ledger.consent_withdrawal import (
    ConsentedDispatch,
    OnHostReader,
    rederive_artefact_on_host,
    survey_cloud_consent,
)
from ...application.ledger.document_transcription import DocumentTranscription
from ...application.ledger.invoice_draft_records import InvoiceDraft
from ...core.config import load_settings
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._common import _state, _tx_repo, emit_envelope
from .ledger_business_payloads import EvidenceConsentListResult, EvidenceConsentRederiveResult

_UNRECALLABLE_LOCALE_KEY = "cli.app.ledger.evidence.consent.bytes_unrecallable"
_NO_HISTORY_LOCALE_KEY = "cli.app.ledger.evidence.consent.no_history"
_LIST_HELP_LOCALE_KEY = "cli.app.ledger.evidence.consent.list_help"
_REDERIVE_HELP_LOCALE_KEY = "cli.app.ledger.evidence.consent.rederive_help"
_REDERIVED_LOCALE_KEY = "cli.app.ledger.evidence.consent.rederived"
_REDERIVE_REFUSED_LOCALE_KEY = "cli.app.ledger.evidence.consent.rederive_refused"
_GROUP_HELP_LOCALE_KEY = "cli.app.ledger.evidence.consent.group_help"


def _unrecallable_notice() -> Notice:
    """Build the standing "this cannot be undone" notice.

    A :class:`Notice` rather than a bespoke ``result`` field, per the envelope
    contract, and WARNING rather than INFO because an operator who reads it as
    routine has misunderstood what withdrawal does.
    """
    return Notice(
        code="evidence_consent_bytes_unrecallable",
        severity=NoticeSeverity.WARNING,
        message=tr(_UNRECALLABLE_LOCALE_KEY),
    )


def _no_history_notice() -> Notice:
    """Build the affirmative "nothing has left this host" notice.

    An empty survey has to SAY it is empty. Rows absent from a listing is not a
    statement -- an operator who sees none cannot tell "nothing was ever sent
    off-host" from "this verb did not report", and that indistinguishability is
    how a crash on this exact surface went unnoticed until a lane probing a real
    instance found it.

    INFO rather than WARNING: an empty history is the desired posture, not a
    problem. It rides the shared notice channel rather than a bespoke result
    field, per the envelope contract, so the text and JSON surfaces cannot drift.
    """
    return Notice(
        code="evidence_consent_no_history",
        severity=NoticeSeverity.INFO,
        message=tr(_NO_HISTORY_LOCALE_KEY),
    )


def consent_list(ctx: typer.Context) -> None:
    """List off-host dispatches and the artefacts derived from them."""
    bucket_id = _tx_repo(_state()).bucket_id
    survey = survey_cloud_consent(
        bucket_id=bucket_id, settings=load_settings(), consent_entries=_recorded_dispatches(bucket_id)
    )
    payload = {
        "bucket_id": bucket_id,
        "transmitted_bytes_are_unrecallable": survey.transmitted_bytes_are_unrecallable,
        "consented_dispatches": [_dispatch_payload(row) for row in survey.consented_dispatches],
        "cloud_derived_artefacts": [
            {
                "evidence_reference": row.evidence_reference,
                "provenance_stamp": row.provenance_stamp,
                "transport": row.transport,
                "drafted_at": row.drafted_at.isoformat(),
                "rederivable_on_host": row.rederivable_on_host,
            }
            for row in survey.cloud_derived_artefacts
        ],
    }
    lines = ["evidence_reference\ttransport\trederivable_on_host\tprovenance_stamp"]
    lines.extend(
        f"{row.evidence_reference}\t{row.transport or '-'}\t"
        f"{'-' if row.rederivable_on_host is None else row.rederivable_on_host}\t"
        f"{row.provenance_stamp}"
        for row in survey.cloud_derived_artefacts
    )
    notices = [_unrecallable_notice()]
    if not survey.consented_dispatches and (not survey.cloud_derived_artefacts):
        notices.append(_no_history_notice())
    emit_envelope(
        ctx,
        command="ledger.evidence.consent.list",
        result=EvidenceConsentListResult.model_validate(payload),
        lines=lines,
        notices=notices,
    )


def _recorded_dispatches(bucket_id: str) -> tuple[ConsentedDispatch, ...]:
    """Project the profile's consent ledger onto the shape the survey enumerates.

    This composition is the CLI's job and nowhere else's. The application layer
    that owns the survey deliberately does not import the ledger -- it lives on
    the adapter side and the dependency direction forbids the reach -- so the
    entries arrive as an injected projection, and this is the one production
    site that performs it. Absent it the survey enumerates an empty history
    forever while the ledger fills up beside it, which is not a missing feature
    but an affirmative false statement: the verb tells an operator nothing left
    their machine.

    Filtered on the entry's own recorded bucket rather than trusted from the
    ambient session, because the survey is scoped to ``bucket_id`` and a row
    belonging to another profile must never appear under this one. The ledger
    stamps every entry with the bucket it ran under precisely so this
    comparison is possible.

    Deferred import, matching the on-host reader below: this module must stay
    loadable on an install without the inference extra.
    """
    from ...adapters.outbound.llm.consent_ledger import EvidenceConsentLedger

    return tuple(
        ConsentedDispatch(
            evidence_content_address=entry.evidence_content_address,
            provider=entry.provider,
            model=entry.model,
            surface=entry.surface,
            recorded_at=entry.recorded_at,
        )
        for entry in EvidenceConsentLedger().load_entries()
        if entry.profile_bucket_id == bucket_id
    )


def _dispatch_payload(dispatch: ConsentedDispatch) -> dict[str, str]:
    """Project one recorded dispatch onto its JSON shape."""
    return {
        "evidence_content_address": dispatch.evidence_content_address,
        "provider": dispatch.provider,
        "model": dispatch.model,
        "surface": dispatch.surface,
        "recorded_at": dispatch.recorded_at.isoformat(),
    }


def consent_rederive(ctx: typer.Context, evidence_reference: str, content_address: str, transcriber: str) -> None:
    """Re-derive one artefact on this host from its cached transcription."""
    bucket_id = _tx_repo(_state()).bucket_id
    outcome = rederive_artefact_on_host(
        bucket_id=bucket_id,
        evidence_reference=evidence_reference,
        source_content_sha256=content_address,
        transcriber_cache_key=transcriber,
        settings=load_settings(),
        read_on_host=_on_host_reader(),
    )
    emit_envelope(
        ctx,
        command="ledger.evidence.consent.rederive",
        result=EvidenceConsentRederiveResult.model_validate(
            {
                "bucket_id": bucket_id,
                "evidence_reference": outcome.evidence_reference,
                "previous_provenance_stamp": outcome.previous_provenance_stamp,
                "provenance_stamp": outcome.provenance_stamp,
                "transcription_reused": outcome.transcription_reused,
                "transmitted_bytes_are_unrecallable": True,
            }
        ),
        lines=[
            tr(
                _REDERIVED_LOCALE_KEY,
                reference=outcome.evidence_reference,
                previous=outcome.previous_provenance_stamp,
                current=outcome.provenance_stamp,
            )
        ],
        notices=[_unrecallable_notice()],
    )


def _on_host_reader() -> OnHostReader:
    """Resolve the on-host reader, deferred to keep the gated extra optional.

    Imported at call time rather than at module load so this CLI module stays
    importable on an install without the inference extra: the verb refuses with
    the extra's own instructive message, which is better than the whole ledger
    CLI failing to load.

    Returns the PROTOCOL rather than ``object``. The weaker annotation is what
    let this closure keep calling a signature that no longer existed: with the
    return typed as ``object`` the checker could not see through to the call,
    and this module carries no tests, so a re-derivation would have raised
    ``TypeError`` in an operator's hands.
    """
    from ...llm.evidence_draft_text import TextInvoiceFieldExtractor

    def _read(transcription: DocumentTranscription, /) -> tuple[InvoiceDraft, str]:
        extractor = TextInvoiceFieldExtractor()
        return extractor.extract(transcription=transcription), extractor.decided_by

    return _read
