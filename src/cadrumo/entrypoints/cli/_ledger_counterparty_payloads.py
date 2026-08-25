"""Typed ``--json`` payload schemas for the counterparty establishment commands.

Every declared payload is an :class:`OutputSchema` subclass referenced by
production-authored CommandSpec as deferred public schema targets and carried on
the shared :class:`SchemaEnvelope` spine
through ``emit_envelope``, so the answer an operator gives about a counterparty
reaches a caller under the same contract every other ledger command uses.

**Why the fact is emitted whole rather than as a confirmation flag.** The verb's
whole purpose is that the answer is reused: every later document resolving to the
same counterparty reads it as the establishment ladder's last rung. A payload
saying only "recorded" would leave a caller unable to tell what was recorded, and
unable to tell a fresh confirmation from a retry that found the stored one. Both
distinctions are on the envelope: the fact carries its own provenance, and the
retry is named by an info notice rather than by a field.

See Also:
    :class:`~application.ledger.counterparty_establishment.ConfirmedCounterpartyFacts`
        The persisted record these payloads project.
    :class:`~domain.iva.IvaTerritorialScope`
        The closed territory axis the answer settles.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ...core import ClassifierInputSource
from ...core.json_contract import OutputSchema
from ...domain.iva import EUMemberState, IvaTerritorialScope


class CounterpartyEstablishmentPayload(OutputSchema):
    """One confirmed statement of where a counterparty is established.

    Mirrors :class:`~application.ledger.counterparty_establishment.ConfirmedCounterpartyFacts`. The
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
    territorial_scope: IvaTerritorialScope | None = None
    # Emitted always, `None` included: a caller has to be able to tell an
    # unanswered registration from one answered as Spain, and a field that
    # vanished when absent would make those read alike.
    identification_state: EUMemberState | None = None
    asserted_by: str = Field(min_length=1)
    asserted_at: datetime
    note: str = ""


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


class CounterpartyShowResult(OutputSchema):
    """JSON envelope for ``aeat app ledger counterparty show``.

    The operator's read of their own answer, and a first-class verb rather than
    test scaffolding: an answer that cannot be inspected cannot be audited or
    corrected with confidence, and the confirm verb's conflict refusal was
    otherwise the only way to discover what is stored -- learning a fact by
    triggering an error is not a read path.

    **It reports what the LADDER will answer, not what the repository holds**,
    and the two are deliberately not the same question. The resolver declines to
    return a fact the document's own evidence contradicts, so a row can be
    stored and still settle nothing; a payload read from the repository would
    show the operator a territory that no later document will actually use.

    **Which of the two questions was asked depends on whether evidence was
    supplied**, and the payload says which. Asked bare, the verb has no document
    in hand, no evidence can contradict anything, and the answer is what the
    rung holds. Asked with an ``evidenced_scope``, it is the real ladder
    question -- what will this rung answer for a document placing the party
    HERE -- and that is the only form in which a contradiction can arise.

    The distinction is load-bearing rather than descriptive, because a
    contradiction and an empty store are indistinguishable on the other fields:
    the resolver returns no fact in both cases, so ``confirmed`` is ``False``
    and ``territorial_scope`` is ``None`` either way. :attr:`contradicted` is
    what separates "nobody has answered for this counterparty" from "somebody
    did, and this document disagrees with them" -- two situations whose operator
    remedies are opposite, one asking for a first answer and the other asking
    which of two existing claims to withdraw.

    **Both confirmed facts are reported, because both are settable.** The verb
    emitted the territorial side alone while ``--identification-state`` was
    already accepted, so an operator could write a fact and never read it back.
    A write-only value at the operator boundary is worse than an absent one: it
    cannot be reviewed, corrected with confidence, or told apart from a value
    nobody ever supplied.

    ``confirmed`` stays the TERRITORIAL answer rather than becoming a summary of
    both, because it is what the establishment rung fires on and what callers
    branch on. A record carrying only an identification therefore reports
    ``confirmed = false`` beside a populated ``identification_state``, which is
    the honest shape: the ladder settles nothing and the operator has still told
    us something.

    Attributes:
        tax_identifier: Whom the question was asked about, as supplied.
        confirmed: Whether the rung will answer. ``False`` is the ordinary state
            for a counterparty nobody has been asked about yet, not a failure,
            and is ALSO what a contradiction produces -- read it beside
            :attr:`contradicted`, never alone.
        territorial_scope: What it will answer, or ``None``.
        source: Who established it, which for this rung is always the operator.
        evidenced_scope: The territory the operator's document places the party
            in, when they supplied one. ``None`` means the bare question was
            asked and no contradiction was reachable.
        contradicted: Whether the supplied evidence disagrees with the confirmed
            fact. Never ``True`` when :attr:`evidenced_scope` is ``None``.
        confirmed_scope: What the operator had confirmed, carried ONLY on a
            contradiction. It is deliberately absent from
            :attr:`territorial_scope` there, because that field is what the rung
            will answer and on a contradiction the rung answers nothing -- a
            consumer reading the confirmed territory out of it would use a value
            no document will resolve to.
        contradiction_detail: The disagreement in words, taken from the resolver
            rather than recomposed, so the sentence an operator reads here and
            the one a confirm raises cannot drift.
    """

    tax_identifier: str = Field(min_length=1)
    confirmed: bool
    territorial_scope: IvaTerritorialScope | None = None
    source: ClassifierInputSource | None = None
    identification_state: EUMemberState | None = None
    identification_source: ClassifierInputSource | None = None
    evidenced_scope: IvaTerritorialScope | None = None
    contradicted: bool = False
    confirmed_scope: IvaTerritorialScope | None = None
    contradiction_detail: str | None = None
