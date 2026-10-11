"""What an agent's execution may not do to a ledger row the person worked on.

Replacing the classification or a tax figure the person gave a row, or setting
aside a row that carries the person's work, stands for the person's own
decision and waits for their approval of that act. No approval step exists, so
an agent's execution is refused these acts and a person's frontend is not.
Every route asks the questions here, so no route decides for itself what the
person's work is. A row that is unprocessed, or whose classification a rule or
an agent decided, stays open to an agent.

The executor of an operation asks before it declares an effect, so the refusal
settles with nothing written. The ledger actions ask again of the row they are
about to replace, from the actor label they record, so a route that reaches a
writer without asking first is refused there too.
"""

from __future__ import annotations

from collections.abc import Iterable

from ...domain.transactions.classification_origin import classification_facts, classification_is_the_persons
from ...domain.transactions.models import Transaction
from ..operations.execution_actor import actor_label_is_an_agents
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError

_ATTACHMENT = "attachment"
_PURCHASE_EVIDENCE = "purchase_invoice_evidence"


def _evidence_no_agent_linked(row: Transaction) -> frozenset[tuple[str, str]]:
    """Return the evidence the row carries that it does not record an agent as having linked.

    The row keeps, for each piece of evidence, the label of whoever linked it.
    Evidence with no such record counts as the person's.
    """
    carried = {(_ATTACHMENT, attachment_id) for attachment_id in row.attachment_ids}
    if row.purchase_invoice_evidence_id is not None:
        carried.add((_PURCHASE_EVIDENCE, row.purchase_invoice_evidence_id))
    linked_by_an_agent = {
        (entry.evidence_kind, entry.evidence_id)
        for entry in row.evidence_provenance
        if actor_label_is_an_agents(entry.actor)
    }
    return frozenset(carried - linked_by_an_agent)


def carries_the_persons_work(row: Transaction) -> bool:
    """Return whether setting ``row`` aside would strand something the person gave it.

    That is a classification the person decided, an invoice link (the row does
    not record who linked it, so any link counts), or evidence that no agent is
    recorded as having linked.
    """
    return classification_is_the_persons(row) or row.invoice_id is not None or bool(_evidence_no_agent_linked(row))


def _refuse() -> ProfileAccessRefusedError:
    return ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)


def require_agent_may_reclassify(row: Transaction) -> None:
    """Refuse an agent replacing the classification, share or tax figures the person decided for ``row``."""
    if classification_is_the_persons(row):
        raise _refuse()


def require_agent_may_set_aside(row: Transaction) -> None:
    """Refuse an agent splitting or excluding a row that carries the person's work.

    A split passes the parent's classification and invoice link to no child,
    and only the merge, which waits for the person, recombines the rows. An
    exclusion replaces the classification, and the one operation that puts it
    back is closed to an agent.
    """
    if carries_the_persons_work(row):
        raise _refuse()


def require_agent_may_detach(row: Transaction, attachment_ids: Iterable[str]) -> None:
    """Refuse an agent detaching an attachment the row does not record an agent as having linked.

    Detaching is put back by attaching while the row is active. Left open for
    the person's attachments it would also take from a row the one thing that
    keeps an agent from splitting it, after which nothing but the merge puts
    the link back.
    """
    kept_for_the_person = _evidence_no_agent_linked(row)
    if any((_ATTACHMENT, attachment_id.strip()) in kept_for_the_person for attachment_id in attachment_ids):
        raise _refuse()


def require_agent_may_link_invoice(row: Transaction, invoice_id: str) -> None:
    """Refuse an agent replacing the invoice a row already links.

    Linking overwrites the row's link and leaves the earlier invoice citing a
    row that no longer cites it, and no operation open to an agent unlinks.
    """
    if row.invoice_id is not None and row.invoice_id != invoice_id:
        raise _refuse()


def require_actor_may_reclassify(*, actor: str, current: Transaction, replacement: Transaction) -> None:
    """Refuse a write recorded under an agent's label that changes what the person decided for ``current``."""
    if actor_label_is_an_agents(actor) and classification_facts(current) != classification_facts(replacement):
        require_agent_may_reclassify(current)


def require_actor_may_set_aside(*, actor: str, row: Transaction) -> None:
    """Refuse a split or exclusion recorded under an agent's label of a row that carries the person's work."""
    if actor_label_is_an_agents(actor):
        require_agent_may_set_aside(row)


def require_actor_may_detach(*, actor: str, row: Transaction, attachment_ids: Iterable[str]) -> None:
    """Refuse a detachment recorded under an agent's label of an attachment no agent is recorded as linking."""
    if actor_label_is_an_agents(actor):
        require_agent_may_detach(row, attachment_ids)


def require_actor_may_link_invoice(*, actor: str, row: Transaction, invoice_id: str) -> None:
    """Refuse a link recorded under an agent's label that replaces the invoice ``row`` already links."""
    if actor_label_is_an_agents(actor):
        require_agent_may_link_invoice(row, invoice_id)


__all__ = [
    "carries_the_persons_work",
    "require_actor_may_detach",
    "require_actor_may_link_invoice",
    "require_actor_may_reclassify",
    "require_actor_may_set_aside",
    "require_agent_may_detach",
    "require_agent_may_link_invoice",
    "require_agent_may_reclassify",
    "require_agent_may_set_aside",
]
