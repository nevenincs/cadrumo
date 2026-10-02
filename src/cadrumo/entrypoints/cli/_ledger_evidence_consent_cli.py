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

from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from .common import emit_envelope
from .runtime_ledger_evidence_followup import run_ledger_evidence_consent_list

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
    result = run_ledger_evidence_consent_list(ctx)
    lines = ["evidence_reference\ttransport\tprovenance_stamp"]
    lines.extend(
        f"{row.evidence_reference}\t{row.transport or '-'}\t{row.provenance_stamp}"
        for row in result.cloud_derived_artefacts
    )
    notices = [_unrecallable_notice()]
    if not result.consented_dispatches and not result.cloud_derived_artefacts:
        notices.append(_no_history_notice())
    emit_envelope(
        ctx,
        command="ledger.evidence.consent.list",
        result=result,
        lines=lines,
        notices=notices,
    )
