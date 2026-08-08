"""The channel an operator answers the establishment question through.

The establishment ladder walks a document's printed evidence and stops at the
first decisive rung. Its last rung is not on the paper at all: it asks the store
what the operator has already confirmed about this counterparty, so the question
is asked at most once per counterparty rather than once per invoice. That rung
was wired and readable, and nothing could write to it -- the recording function
had no production caller and no operator surface, so the loop the design turns on
was open at exactly one end.

**What the open end cost.** A domestic invoice printing a bare CIF and no country
establishes neither party's territory from its face, which is the commonest
document in the corpus rather than an edge case. The ladder exhausted, the
confirmation surfaced a review item naming the counterparty, and the operator had
no verb to answer it -- so the next document from the same counterparty exhausted
identically. The review item was a question nobody could reply to, which is why
exhaustion surfaces an item today instead of refusing: refusing without this
channel would have made every such invoice permanently unconfirmable, and a
refusal nobody can answer is not a review gate. This surface is what lets that
posture tighten.

**Confirming and withdrawing are separate acts, deliberately.** A second answer
naming a DIFFERENT territory refuses rather than overwriting, because an
overwrite would silently discard the operator's earlier answer and quietly
reclassify every invoice already derived under it. Correcting therefore means
saying so: withdraw the fact, then confirm the new one. The refusal names that
route, and this module ships the verb it names -- an instruction pointing at a
command that does not exist is the shape this campaign keeps finding.

**A retry is a no-op that says it was one.** The same operator answer arriving
twice returns the stored fact with its original provenance intact, because
re-stamping the timestamp would make a repeated call look like a fresh
confirmation. The caller is told through an info notice and a ``recorded`` flag
rather than being left to infer it from an unchanged timestamp.

See Also:
    :func:`~application.ledger.record_confirmed_counterparty_facts`
        The single writer this delegates to, which owns the idempotency rules.
    :func:`~application.ledger.resolve_confirmed_counterparty_facts`
        The ladder rung that reads what this writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.time import now
from ...domain.iva import EUMemberState, IvaTerritorialScope
from ._common import _bad, _emit_envelope
from ._common import active_bucket_id_or_refuse as _counterparty_bucket_id
from ._ledger_counterparty_payloads import (
    CounterpartyConfirmResult,
    CounterpartyEstablishmentPayload,
    CounterpartyShowResult,
    CounterpartyWithdrawResult,
)

if TYPE_CHECKING:
    from ...application.ledger import ConfirmedCounterpartyFacts

counterparty_app = typer.Typer(
    name="counterparty",
    help=tr(
        "cli.app.ledger.counterparty.group_help",
        default="Confirm where a counterparty is established, once, for every later document.",
    ),
    no_args_is_help=True,
)


def register_counterparty_commands(app: typer.Typer) -> None:
    """Mount the counterparty establishment commands on the ledger app."""
    app.add_typer(counterparty_app, name="counterparty")


def _payload(fact: ConfirmedCounterpartyFacts) -> CounterpartyEstablishmentPayload:
    """Project the persisted fact onto its wire shape."""
    return CounterpartyEstablishmentPayload(
        counterparty_key=fact.counterparty_key,
        canonical_tax_identifier=fact.canonical_tax_identifier,
        territorial_scope=fact.territorial_scope,
        identification_state=fact.identification_state,
        asserted_by=fact.asserted_by,
        asserted_at=fact.asserted_at,
        note=fact.note,
    )


@counterparty_app.command(
    "confirm",
    help=tr(
        "cli.app.ledger.counterparty.confirm_help",
        default="Confirm the territory a counterparty is established in.",
    ),
)
def counterparty_confirm(
    ctx: typer.Context,
    # The subject is a POSITIONAL argument, not an option: the verb addresses one
    # counterparty and the flags configure the operation, which is the shape
    # every single-subject ledger verb takes.
    tax_identifier: str = typer.Argument(
        ...,
        help=tr(
            "cli.app.ledger.counterparty.tax_identifier_help",
            default="The counterparty's tax identifier as printed on the document.",
        ),
    ),
    # Declared as the enum so click renders the accepted set on a parse failure,
    # rather than the operator meeting a late refusal that names no alternatives.
    scope: IvaTerritorialScope = typer.Option(
        ...,
        "--scope",
        help=tr(
            "cli.app.ledger.counterparty.scope_help",
            default="The IVA territory the counterparty is established in.",
        ),
    ),
    # A SECOND axis, not a synonym for --scope. Ley 37/1992 art. 25 exempts on
    # where a counterparty is VAT-IDENTIFIED; arts. 69-70 govern where it is
    # ESTABLISHED. They diverge in real trade, so the operator answers each.
    # Declared as the enum for the same reason --scope is: a guessed Member
    # State is precisely the invented fact this axis exists to prevent.
    identification_state: EUMemberState | None = typer.Option(
        None,
        "--identification-state",
        help=tr(
            "cli.app.ledger.counterparty.identification_state_help",
            default=(
                "Member State that VAT-identifies the counterparty. A different fact from --scope: "
                "art. 25 exempts on this, not on where the party is established."
            ),
        ),
    ),
    country_code: str | None = typer.Option(
        None,
        "--country-code",
        help=tr(
            "cli.app.ledger.counterparty.country_code_help",
            default="Country the identifier is stated under, when it is not Spanish.",
        ),
    ),
    note: str = typer.Option(
        "",
        "--note",
        help=tr(
            "cli.app.ledger.counterparty.note_help",
            default="What the answer rests on, in your own words. Recorded, never consulted.",
        ),
    ),
    actor: str | None = typer.Option(
        None,
        "--actor",
        help=tr(
            "cli.app.ledger.counterparty.actor_help",
            default="Operator identifier recorded as having made the assertion.",
        ),
    ),
) -> None:
    """Persist the operator's answer, or report the stored one unchanged."""
    from ...application.ledger import (
        ConfirmedCounterpartyFactsInputError,
        CounterpartyEstablishmentConflictError,
        record_confirmed_counterparty_facts,
    )

    bucket_id = _counterparty_bucket_id()
    asserted_by = actor or bucket_id or "operator"
    # The stamp is supplied rather than left to the writer's clock so this call
    # can recognise its own write in what comes back. A pre-read of the store
    # would answer the same question through a check-then-act window that a
    # retrying caller can lose; comparing the returned stamp against the one
    # handed in has no window at all, because the writer preserves the ORIGINAL
    # stamp on a retry precisely so a repeat cannot look like a fresh answer.
    stamped_at = now()
    try:
        fact = record_confirmed_counterparty_facts(
            bucket_id=bucket_id,
            tax_identifier=tax_identifier,
            territorial_scope=scope,
            asserted_by=asserted_by,
            identification_state=identification_state,
            country_code=country_code,
            note=note,
            asserted_at=stamped_at,
        )
    except ConfirmedCounterpartyFactsInputError as exc:
        raise _bad(
            tr(
                "cli.ledger.counterparty.errors.unverifiable_identifier",
                identifier=tax_identifier,
                default=(
                    f"'{tax_identifier}' is not a verifiable tax identifier, so there is no counterparty "
                    f"to confirm an establishment for."
                ),
            ),
        ) from exc
    except CounterpartyEstablishmentConflictError as exc:
        raise _bad(
            tr(
                "cli.ledger.counterparty.errors.scope_conflict",
                identifier=tax_identifier,
                asserted=scope.value,
                detail=str(exc),
                default=(
                    f"A different territory is already confirmed for '{tax_identifier}', so confirming "
                    f"'{scope.value}' would discard the earlier answer. Withdraw it first with "
                    f"'aeat app ledger counterparty withdraw'. {exc}"
                ),
            ),
        ) from exc

    recorded = fact.asserted_at == stamped_at
    notices: list[Notice] = []
    if not recorded:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.counterparty.already_confirmed",
                message=tr(
                    "cli.ledger.counterparty.notices.already_confirmed",
                    identifier=fact.canonical_tax_identifier,
                    scope=fact.territorial_scope.value,
                    asserted_by=fact.asserted_by,
                    default=(
                        f"'{fact.canonical_tax_identifier}' was already confirmed as established in "
                        f"'{fact.territorial_scope.value}' by '{fact.asserted_by}'; this call created no new "
                        f"confirmation and the original provenance stands."
                    ),
                ),
                context={
                    "canonical_tax_identifier": fact.canonical_tax_identifier,
                    "territorial_scope": fact.territorial_scope.value,
                    "stored_asserted_by": fact.asserted_by,
                    "supplied_asserted_by": asserted_by,
                },
            ),
        )

    _emit_envelope(
        ctx,
        command="ledger.counterparty.confirm",
        result=CounterpartyConfirmResult(counterparty=_payload(fact), recorded=recorded),
        lines=[
            f"{fact.canonical_tax_identifier}: {fact.territorial_scope.value}"
            f"{'' if recorded else ' (already confirmed)'}",
        ],
        notices=notices,
    )


@counterparty_app.command(
    "withdraw",
    help=tr(
        "cli.app.ledger.counterparty.withdraw_help",
        default="Withdraw a confirmed establishment, stating the earlier answer was wrong.",
    ),
)
def counterparty_withdraw(
    ctx: typer.Context,
    tax_identifier: str = typer.Argument(
        ...,
        help=tr(
            "cli.app.ledger.counterparty.tax_identifier_help",
            default="The counterparty's tax identifier as printed on the document.",
        ),
    ),
    country_code: str | None = typer.Option(
        None,
        "--country-code",
        help=tr(
            "cli.app.ledger.counterparty.country_code_help",
            default="Country the identifier is stated under, when it is not Spanish.",
        ),
    ),
) -> None:
    """Remove a confirmed fact so a corrected one can be confirmed."""
    from ...application.ledger import confirmed_counterparty_facts_key, forget_confirmed_counterparty_facts

    bucket_id = _counterparty_bucket_id()
    if confirmed_counterparty_facts_key(tax_identifier, country_code=country_code) is None:
        raise _bad(
            tr(
                "cli.ledger.counterparty.errors.unverifiable_identifier",
                identifier=tax_identifier,
                default=(
                    f"'{tax_identifier}' is not a verifiable tax identifier, so there is no counterparty "
                    f"to confirm an establishment for."
                ),
            ),
        )
    withdrawn = forget_confirmed_counterparty_facts(
        bucket_id=bucket_id,
        tax_identifier=tax_identifier,
        country_code=country_code,
    )
    notices: list[Notice] = []
    if not withdrawn:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.counterparty.nothing_to_withdraw",
                message=tr(
                    "cli.ledger.counterparty.notices.nothing_to_withdraw",
                    identifier=tax_identifier,
                    default=(
                        f"No confirmed establishment was held for '{tax_identifier}', so nothing was "
                        f"withdrawn and the store is already in the state you asked for."
                    ),
                ),
                context={"tax_identifier": tax_identifier},
            ),
        )
    _emit_envelope(
        ctx,
        command="ledger.counterparty.withdraw",
        result=CounterpartyWithdrawResult(
            canonical_tax_identifier=tax_identifier,
            withdrawn=withdrawn,
        ),
        lines=[f"{tax_identifier}: {'withdrawn' if withdrawn else 'nothing to withdraw'}"],
        notices=notices,
    )


@counterparty_app.command(
    "show",
    help=tr(
        "cli.app.ledger.counterparty.show_help",
        default="Show the establishment confirmed for a counterparty, if any.",
    ),
)
def counterparty_show(
    ctx: typer.Context,
    tax_identifier: str = typer.Argument(
        ...,
        help=tr(
            "cli.app.ledger.counterparty.tax_identifier_help",
            default="The counterparty's tax identifier as printed on the document.",
        ),
    ),
    country_code: str | None = typer.Option(
        None,
        "--country-code",
        help=tr(
            "cli.app.ledger.counterparty.country_code_help",
            default="Country the identifier is stated under, when it is not Spanish.",
        ),
    ),
    evidenced_scope: IvaTerritorialScope | None = typer.Option(
        None,
        "--evidenced-scope",
        help=tr(
            "cli.app.ledger.counterparty.evidenced_scope_help",
            default=(
                "Territory a document in hand places this party in. Supply it to ask what the "
                "ladder will answer for that document, which is the only way to see a "
                "disagreement with what you confirmed before a confirm refuses on it."
            ),
        ),
    ),
) -> None:
    """Report what the ladder's last rung will answer for this counterparty.

    Deliberately asks the same resolver the ladder asks rather than reading the
    repository directly, so what an operator is shown and what a later document
    resolves to cannot drift apart.

    **That guarantee only holds for the question actually asked**, which is why
    the evidence option exists. The rung's answer depends on what a document
    places the party in: the resolver withholds a confirmed fact the document's
    own evidence contradicts, and that branch is reachable only when an
    evidenced territory is supplied. Asked bare, this reports what is
    confirmed -- true, and a narrower claim than the one the payload's design
    rests on. Asked with ``--evidenced-scope``, it asks the ladder's real
    question and can show the disagreement BEFORE a confirm surfaces it as a
    blocker.

    Without the option threaded, an operator who confirmed one territory and
    then held a document printing another was shown the confirmed value with
    nothing indicating that a confirm would refuse to use it -- the two surfaces
    diverging in exactly the case the verb exists for, invisibly.
    """
    from ...application.ledger import resolve_confirmed_counterparty_facts

    resolution = resolve_confirmed_counterparty_facts(
        bucket_id=_counterparty_bucket_id(),
        tax_identifier=tax_identifier,
        country_code=country_code,
        evidenced_scope=evidenced_scope,
    )
    fact = resolution.fact
    contradiction = resolution.contradiction
    notices: list[Notice] = []
    if contradiction is not None:
        # A WARNING rather than INFO: nothing here is a next-step hint. The
        # store and the document make incompatible claims about the same party,
        # and until one is withdrawn every confirm against this counterparty
        # settles no territory at all.
        notices.append(
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.counterparty.evidence_contradicts_confirmation",
                message=tr(
                    "cli.ledger.counterparty.notices.evidence_contradicts_confirmation",
                    identifier=tax_identifier,
                    confirmed=contradiction.confirmed_scope.value,
                    evidenced=contradiction.evidenced_scope.value,
                    default=(
                        f"'{tax_identifier}' was confirmed as established in "
                        f"{contradiction.confirmed_scope.value}, but the evidence you supplied places "
                        f"the same party in {contradiction.evidenced_scope.value}. The ladder will "
                        f"settle no territory for this counterparty until one of the two is withdrawn."
                    ),
                ),
                context={
                    "tax_identifier": tax_identifier,
                    "confirmed_scope": contradiction.confirmed_scope.value,
                    "evidenced_scope": contradiction.evidenced_scope.value,
                },
            ),
        )
    elif fact is None:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.counterparty.not_confirmed",
                message=tr(
                    "cli.ledger.counterparty.notices.not_confirmed",
                    identifier=tax_identifier,
                    default=(
                        f"No establishment is confirmed for '{tax_identifier}', so the ladder settles "
                        f"nothing from this rung and a document whose paper is non-decisive will raise "
                        f"the question."
                    ),
                ),
                context={"tax_identifier": tax_identifier},
            ),
        )
    _emit_envelope(
        ctx,
        command="ledger.counterparty.show",
        result=CounterpartyShowResult(
            tax_identifier=tax_identifier,
            confirmed=fact is not None,
            territorial_scope=fact.value if fact is not None else None,
            source=fact.source if fact is not None else None,
            evidenced_scope=evidenced_scope,
            contradicted=contradiction is not None,
            # Carried only here and deliberately NOT in `territorial_scope`:
            # that field is what the rung will answer, and on a contradiction it
            # answers nothing.
            confirmed_scope=contradiction.confirmed_scope if contradiction is not None else None,
            contradiction_detail=contradiction.detail if contradiction is not None else None,
        ),
        lines=[
            # Rebuilt from the same three states the payload reports, so the
            # text and the JSON cannot describe different outcomes. A
            # contradiction must not read as "not confirmed": the store holds an
            # answer, and it is the document that disagrees with it.
            f"{tax_identifier}: "
            + (
                f"contradicted (confirmed {contradiction.confirmed_scope.value}, "
                f"evidence {contradiction.evidenced_scope.value})"
                if contradiction is not None
                else fact.value.value
                if fact is not None
                else "not confirmed"
            ),
        ],
        notices=notices,
    )
