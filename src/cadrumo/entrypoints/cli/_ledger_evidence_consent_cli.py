"""Operator surface for off-host consent history.

``list`` enumerates the profile's off-host dispatches and marks the artefacts
derived from them.

**Both surfaces state that transmitted bytes cannot be recalled, every time.**
The statement is carried in the JSON payload as well as the rendered lines,
because an agent consuming the envelope never sees prose, and this is the one
caveat on this surface an operator must not act without. It is unconditional:
an empty history is still surfaced with the caveat, since an operator with no
history is precisely the one deciding whether to enable the route.

See Also:
    :func:`~application.ledger.consent_withdrawal.survey_cloud_consent`
        The enumeration behind ``consent list``.
"""

from __future__ import annotations

import typer

from ...application.ledger.consent_withdrawal import (
    ConsentedDispatch,
    survey_cloud_consent,
)
from ...core.config import load_settings
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from .common import current_workflow_state, emit_envelope, transaction_catalogue_repo
from .ledger_business_payloads import EvidenceConsentListResult

_UNRECALLABLE_LOCALE_KEY = "cli.app.ledger.evidence.consent.bytes_unrecallable"
_NO_HISTORY_LOCALE_KEY = "cli.app.ledger.evidence.consent.no_history"


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
    bucket_id = transaction_catalogue_repo(current_workflow_state()).bucket_id
    survey = survey_cloud_consent(bucket_id=bucket_id, settings=load_settings(), consent_entries=_recorded_dispatches())
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
            }
            for row in survey.cloud_derived_artefacts
        ],
    }
    lines = ["evidence_reference\ttransport\tprovenance_stamp"]
    lines.extend(
        f"{row.evidence_reference}\t{row.transport or '-'}\t{row.provenance_stamp}"
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


def _recorded_dispatches() -> tuple[ConsentedDispatch, ...]:
    """Project the adapter-side consent ledger onto the shape the survey reads.

    This composition is the CLI's job and nowhere else's. The application layer
    that owns the survey deliberately does not import the ledger -- it lives on
    the adapter side and the dependency direction forbids the reach -- so the
    entries arrive as an injected projection, and this is the one production
    site that performs it. Absent it the survey enumerates an empty history
    forever while the ledger fills up beside it, which is not a missing feature
    but an affirmative false statement: the verb tells an operator nothing left
    their machine.

    Every entry is projected, including those recorded under other profiles.
    Scoping is the survey's, because it holds the bucket being surveyed and
    already scopes its other input the same way; a filter here would have to be
    repeated by every future composition root, and forgotten once is a
    disclosure.

    Deferred import, matching the on-host reader below: this module must stay
    loadable on an install without the inference extra.
    """
    from ...adapters.outbound.llm.consent_ledger import EvidenceConsentLedger

    return tuple(
        ConsentedDispatch(
            profile_bucket_id=entry.profile_bucket_id,
            evidence_content_address=entry.evidence_content_address,
            provider=entry.provider,
            model=entry.model,
            surface=entry.surface,
            recorded_at=entry.recorded_at,
        )
        for entry in EvidenceConsentLedger().load_entries()
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
