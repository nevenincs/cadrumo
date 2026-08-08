"""Typed ``--json`` payload schemas for the counterparty establishment commands.

Every declared payload is an :class:`OutputSchema` subclass registered with
:func:`register_schema` and carried on the shared :class:`SchemaEnvelope` spine
through ``_emit_envelope``, so the answer an operator gives about a counterparty
reaches a caller under the same contract every other ledger command uses.

**Why the fact is emitted whole rather than as a confirmation flag.** The verb's
whole purpose is that the answer is reused: every later document resolving to the
same counterparty reads it as the establishment ladder's last rung. A payload
saying only "recorded" would leave a caller unable to tell what was recorded, and
unable to tell a fresh confirmation from a retry that found the stored one. Both
distinctions are on the envelope: the fact carries its own provenance, and the
retry is named by an info notice rather than by a field.

See Also:
    :class:`~application.ledger.CounterpartyEstablishmentFact`
        The persisted record these payloads project.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed territory axis the answer settles.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ...core.json_contract import OutputSchema, register_schema
from ...domain.iva import IvaTerritorialScope


class CounterpartyEstablishmentPayload(OutputSchema):
    """One confirmed statement of where a counterparty is established.

    Mirrors :class:`~application.ledger.CounterpartyEstablishmentFact`. The
    canonical identifier travels beside the key because the key alone is a
    digest: an operator reading the payload back has to be able to see whom the
    record is about, and a caller reconciling two answers has to compare
    something a person can recognise.

    ``asserted_at`` is a last-seen body field and is deliberately NOT folded into
    ``counterparty_key`` -- the same counterparty addresses the same record on
    every retry, which is what makes the verb safe for an agent that retries.
    """

    counterparty_key: str = Field(min_length=1)
    canonical_tax_identifier: str = Field(min_length=1)
    territorial_scope: IvaTerritorialScope
    asserted_by: str = Field(min_length=1)
    asserted_at: datetime
    note: str = ""


@register_schema("ledger.counterparty.confirm")
class CounterpartyConfirmResult(OutputSchema):
    """JSON envelope for ``aeat app ledger counterparty confirm``.

    Attributes:
        counterparty: The stored fact, whether this call wrote it or found it.
        recorded: Whether this call was the one that persisted the answer.
            ``False`` on an idempotent retry, where the returned fact is the
            pre-existing one and no lifecycle event was emitted. Carried as a
            field as well as an info notice because a caller scripting the verb
            branches on it, while the notice is what an operator reads.
    """

    counterparty: CounterpartyEstablishmentPayload
    recorded: bool


@register_schema("ledger.counterparty.withdraw")
class CounterpartyWithdrawResult(OutputSchema):
    """JSON envelope for ``aeat app ledger counterparty withdraw``.

    Attributes:
        canonical_tax_identifier: Whom the withdrawal was about, canonicalised.
        withdrawn: Whether a confirmed fact was actually held and removed.
            ``False`` is a successful no-op rather than a failure: withdrawing an
            answer nobody gave leaves the store in the state the operator asked
            for, and refusing would make a retry after a partial failure worse
            than the first attempt.
    """

    canonical_tax_identifier: str = Field(min_length=1)
    withdrawn: bool
