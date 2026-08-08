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
    :func:`~application.ledger.record_counterparty_establishment`
        The single writer this delegates to, which owns the idempotency rules.
    :func:`~application.ledger.resolve_counterparty_establishment`
        The ladder rung that reads what this writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.time import now
from ...domain.iva import IvaTerritorialScope
from ._common import _bad, _emit_envelope
from ._common import active_bucket_id_or_refuse as _counterparty_bucket_id
from ._ledger_counterparty_payloads import (
    CounterpartyConfirmResult,
    CounterpartyEstablishmentPayload,
    CounterpartyWithdrawResult,
)

if TYPE_CHECKING:
    from ...application.ledger import CounterpartyEstablishmentFact

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


def _payload(fact: CounterpartyEstablishmentFact) -> CounterpartyEstablishmentPayload:
    """Project the persisted fact onto its wire shape."""
    return CounterpartyEstablishmentPayload(
        counterparty_key=fact.counterparty_key,
        canonical_tax_identifier=fact.canonical_tax_identifier,
        territorial_scope=fact.territorial_scope,
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
        CounterpartyEstablishmentConflictError,
        CounterpartyEstablishmentInputError,
        record_counterparty_establishment,
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
        fact = record_counterparty_establishment(
            bucket_id=bucket_id,
            tax_identifier=tax_identifier,
            territorial_scope=scope,
            asserted_by=asserted_by,
            country_code=country_code,
            note=note,
            asserted_at=stamped_at,
        )
    except CounterpartyEstablishmentInputError as exc:
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
    from ...application.ledger import counterparty_establishment_key, forget_counterparty_establishment

    bucket_id = _counterparty_bucket_id()
    if counterparty_establishment_key(tax_identifier, country_code=country_code) is None:
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
    withdrawn = forget_counterparty_establishment(
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
