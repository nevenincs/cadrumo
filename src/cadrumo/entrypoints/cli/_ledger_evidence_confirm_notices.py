"""What the confirm path resolved about a document, projected to the operator.

The confirm path resolves two things nothing told anybody about. It settles which
IVA treatment the invoice gets and on what rung that treatment stands, and it
collects every question the establishment ladder, the profile authority and the
category rule table leave open. Both were computed, attached to the result, and
read by no production caller --- so a record whose category rests on the weakest
rung available looked exactly like one the rule table placed outright, and a
document whose category was withheld reached the catalogue with no treatment and
no sentence saying why.

**The notice channel, not a payload field.** These are diagnostics about a write
that already happened rather than the write's own data: the invoice is minted
either way, and what an operator does next depends on being told. The one thing
that IS result data --- which category landed and on which rung --- rides the
result payload, because a consumer enumerating the weakly-placed records should
not have to parse prose to do it.

**Severity tracks the record, not the rarity.** A resolution that produced a
category is reported at INFO however weak its rung: the treatment landed, it is
right in the ordinary case, and an ordinary Spanish invoice printing no postal
code is the commonest document there is --- warning on every one of them is how a
channel earns the reflex to skip it. A resolution that produced NO category is a
warning, because the record now carries no IVA treatment at all and the invoice
decomposition contract refuses it downstream. That is one rule, it is the
operator's actual consequence, and it does not require ranking the outcomes by
how alarming they sound.

See Also:
    :class:`~application.ledger.confirm_establishment.ConfirmedEstablishment`
        The resolution these notices read; every field of it was unread before.
    :class:`~core.IvaCategoryOutcome`
        Which rung established the treatment, or why none did.
    :class:`~core.ConfirmationBlockReason`
        The reason axis the carried review items address under.
    :class:`~core.json_contract.Notice`
        The one diagnostic channel this projects onto.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ...core import IvaCategoryOutcome
from ...core.confirmation_gate import ConfirmationBlockReason
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity

if TYPE_CHECKING:
    from ...application.ledger.confirm_establishment import ConfirmedEstablishment

__all__ = ["confirm_resolution_lines", "confirm_resolution_notices"]

_OUTCOME_NOTICE_CODE: Final[dict[IvaCategoryOutcome, str]] = {
    IvaCategoryOutcome.RATE_INFERRED: "ledger.evidence.confirm.category_rate_inferred",
    IvaCategoryOutcome.UNSUPPORTED_RELIEF: "ledger.evidence.confirm.category_unsupported_relief",
    IvaCategoryOutcome.CONTRADICTED: "ledger.evidence.confirm.category_contradicted",
    IvaCategoryOutcome.UNRESOLVED: "ledger.evidence.confirm.category_unresolved",
}
"""One notice code per outcome worth telling an operator about.

``CORROBORATED``, ``CLASSIFIED`` and ``DECLARED`` are deliberately absent: each
is a category established the way categories are meant to be established, and a
notice saying so on every ordinary invoice is noise that buries the four below
it. Their absence is still legible --- the outcome itself rides the result
payload, so a consumer can read the strong states without a notice existing.

Split per outcome rather than one "the category is weak" notice, because a JSON
consumer routes on ``code``: a withheld relief claim and a treatment the tier
settled are different work, and one code for both makes them indistinguishable
outside the prose.
"""

_REVIEW_NOTICE_CODE: Final[dict[ConfirmationBlockReason, str]] = {
    ConfirmationBlockReason.UNDETERMINED_ESTABLISHMENT: "ledger.evidence.confirm.review_undetermined_establishment",
    ConfirmationBlockReason.CONTRADICTED_REGIME: "ledger.evidence.confirm.review_contradicted_regime",
}
"""The reasons a confirm's carried review items are raised under.

Only two of the blocking axis's members can reach here, because only two are
raised by the confirm-path resolution rather than by the deterministic draft
checks the review gate already surfaces. A member gaining a route without an
entry here is a question that would go back to being carried and unread, which
is what :func:`confirm_resolution_notices` refuses below rather than skipping.
"""


def _outcome_message(outcome: IvaCategoryOutcome) -> str:
    """Return the operator-facing sentence for one reportable category outcome.

    Branched on literal keys rather than read from a table, because the locale
    scaffold discovers keys by reading literal :func:`tr` arguments out of the
    source: a key reached through a table entry is invisible to it and is then
    reported as an orphan and swept out from under the notice.
    """
    if outcome is IvaCategoryOutcome.RATE_INFERRED:
        return tr("cli.app.ledger.evidence.confirm_category_rate_inferred_message")
    if outcome is IvaCategoryOutcome.UNSUPPORTED_RELIEF:
        return tr("cli.app.ledger.evidence.confirm_category_unsupported_relief_message")
    if outcome is IvaCategoryOutcome.CONTRADICTED:
        return tr("cli.app.ledger.evidence.confirm_category_contradicted_message")
    return tr("cli.app.ledger.evidence.confirm_category_unresolved_message")


def _review_message(reason: ConfirmationBlockReason) -> str:
    """Return the operator-facing sentence for one carried review reason.

    Branched for the reason :func:`_outcome_message` is branched.
    """
    if reason is ConfirmationBlockReason.CONTRADICTED_REGIME:
        return tr("cli.app.ledger.evidence.confirm_review_contradicted_regime_message")
    return tr("cli.app.ledger.evidence.confirm_review_undetermined_establishment_message")


def confirm_resolution_notices(establishment: ConfirmedEstablishment | None) -> list[Notice]:
    """Return everything one confirm's resolution has to tell the operator.

    Args:
        establishment: What the confirm path resolved, or ``None`` where the
            resolution was not attempted. ``None`` yields no notices rather than
            an "unresolved" one: nothing was asked, so nothing is being reported.

    Returns:
        The category-outcome notice where the outcome is one worth reporting,
        followed by one notice per carried review item, in the order the
        resolution raised them.

    Raises:
        KeyError: When a review item carries a reason with no sentence here. A
            question raised on the confirm path and not projected is exactly the
            defect this module exists to close, so it fails loudly at the surface
            rather than dropping the item back into silence.
    """
    if establishment is None:
        return []
    # One rule for every notice below: a resolution that produced a category left
    # the record with a treatment, and one that did not left it with none. The
    # second is the operator's problem now; the first is provenance.
    severity = NoticeSeverity.INFO if establishment.category.category is not None else NoticeSeverity.WARNING
    notices: list[Notice] = []
    outcome = establishment.category.outcome
    code = _OUTCOME_NOTICE_CODE.get(outcome)
    if code is not None:
        context = {"outcome": outcome.value}
        if establishment.category.category is not None:
            context["iva_category"] = establishment.category.category.value
        if establishment.category.declared is not None:
            context["declared_category"] = establishment.category.declared.value.value
        if establishment.category.note:
            context["note"] = establishment.category.note
        notices.append(
            Notice(severity=severity, code=code, message=_outcome_message(outcome), context=context),
        )
    notices.extend(
        Notice(
            severity=severity,
            code=_REVIEW_NOTICE_CODE[item.reason],
            message=_review_message(item.reason),
            # The domain's own sentence rides the context rather than replacing
            # the localised message: it names the counterparty and the field,
            # which no translated sentence can, and a JSON consumer wanting the
            # specifics reads it from a stable key.
            context={
                "finding_id": item.blocker_id,
                "reason": item.reason.value,
                "field": item.field or "",
                "detail": item.detail,
            },
        )
        for item in establishment.review_items
    )
    return notices


def confirm_resolution_lines(establishment: ConfirmedEstablishment | None) -> list[str]:
    """Return the text-mode rendering of one confirm's resolution.

    Args:
        establishment: What the confirm path resolved, or ``None``.

    Returns:
        One ``iva_category`` line and one line per carried review item, empty
        when nothing was resolved. A terminal operator is told what a JSON
        consumer is told.
    """
    if establishment is None:
        return []
    resolution = establishment.category
    lines = [
        f"iva_category\t{resolution.category.value if resolution.category is not None else '-'}\t"
        f"{resolution.outcome.value}",
    ]
    lines.extend(
        f"review_item\t{item.reason.value}\t{item.field or '-'}\t{item.detail}" for item in establishment.review_items
    )
    return lines
