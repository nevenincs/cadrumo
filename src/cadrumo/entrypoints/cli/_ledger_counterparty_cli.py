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
    :func:`~application.ledger.counterparty_establishment.record_confirmed_counterparty_facts`
        The single writer this delegates to, which owns the idempotency rules.
    :func:`~application.ledger.counterparty_establishment.resolve_confirmed_counterparty_facts`
        The ladder rung that reads what this writes.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import typer

from ...application.ledger.counterparty_operation import (
    CounterpartyFactProjection,
    CounterpartyResolutionProjection,
    LedgerCounterpartyRequest,
)
from ...core.classifier_input_source import ClassifierInputSource
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.iva.classification import IvaTerritorialScope, require_iva_territorial_scope
from ...domain.iva.schema import EUMemberState, require_eu_member_state
from ._ledger_counterparty_payloads import (
    CounterpartyConfirmResult,
    CounterpartyEstablishmentPayload,
    CounterpartyViewResult,
    CounterpartyWithdrawResult,
)
from .common import active_bucket_id_or_refuse as _counterparty_bucket_id
from .common import bad, emit_envelope
from .runtime_counterparty import run_counterparty
from .state_projection_support import authority_operation


def _confirmed_answers(fact: CounterpartyFactProjection) -> str:
    """Name the answers actually stored, skipping the axis left unanswered.

    Establishment and IVA-identification are independent axes and either may
    stand alone, so every surface describing a stored fact has to read both
    optionally: a summary assuming a territory is present renders a
    identification-only confirmation as nothing, and reaching for its value
    raises instead.
    """
    return ", ".join(
        part
        for part in (
            fact.territorial_scope,
            fact.identification_state,
        )
        if part is not None
    )


def _payload(ctx: typer.Context, fact: CounterpartyFactProjection) -> CounterpartyEstablishmentPayload:
    """Project the persisted fact onto its wire shape."""
    return CounterpartyEstablishmentPayload(
        counterparty_key=fact.counterparty_key,
        canonical_tax_identifier=fact.canonical_tax_identifier,
        territorial_scope=(
            require_iva_territorial_scope(fact.territorial_scope, operation=authority_operation(ctx))
            if fact.territorial_scope is not None
            else None
        ),
        identification_state=(
            require_eu_member_state(fact.identification_state, authority=authority_operation(ctx))
            if fact.identification_state is not None
            else None
        ),
        asserted_by=fact.asserted_by,
        asserted_at=fact.asserted_at,
        note=fact.note,
    )


def counterparty_confirm(
    ctx: typer.Context,
    # The subject is a POSITIONAL argument, not an option: the verb addresses one
    # counterparty and the flags configure the operation, which is the shape
    # every single-subject ledger verb takes.
    tax_identifier: str,
    # Declared as the enum so click renders the accepted set on a parse failure,
    # rather than the operator meeting a late refusal that names no alternatives.
    scope: IvaTerritorialScope | None = None,
    # A SECOND axis, not a synonym for --scope. Ley 37/1992 art. 25 exempts on
    # where a counterparty is IVA-IDENTIFIED; arts. 69-70 govern where it is
    # ESTABLISHED. They diverge in real trade, so the operator answers each.
    # Declared as the enum for the same reason --scope is: a guessed Member
    # State is precisely the invented fact this axis exists to prevent.
    identification_state: EUMemberState | None = None,
    country_code: str | None = None,
    note: str = "",
    actor: str | None = None,
) -> None:
    """Persist the operator's answer, or report the stored one unchanged."""
    bucket_id = _counterparty_bucket_id()
    asserted_by = actor or bucket_id or "operator"
    if scope is None and identification_state is None:
        raise bad(
            tr("cli.ledger.counterparty.errors.nothing_asserted", identifier=tax_identifier),
        )
    completed = run_counterparty(
        ctx,
        request=LedgerCounterpartyRequest(
            profile_id=UUID(bucket_id),
            action="confirm",
            tax_identifier=tax_identifier,
            asserted_by=asserted_by,
            territorial_scope=scope.value if scope is not None else None,
            identification_state=identification_state.value if identification_state is not None else None,
            country_code=country_code,
            note=note,
        ),
    )
    if completed.projection.conflict_context is not None:
        from ...application.ledger.counterparty_establishment import CounterpartyEstablishmentConflictError

        raise CounterpartyEstablishmentConflictError(
            translated_message="errors.refused.refused_ledger_counterparty_establishment_conflict",
            context=dict(completed.projection.conflict_context),
        )
    fact = cast("CounterpartyFactProjection", completed.projection.facts)
    recorded = cast("bool", completed.projection.recorded)
    notices: list[Notice] = []
    if not recorded:
        _append_counterparty_already_confirmed_notice(fact, asserted_by, notices)

    emit_envelope(
        ctx,
        command="ledger.counterparty.confirm",
        result=CounterpartyConfirmResult(counterparty=_payload(ctx, fact), recorded=recorded),
        # Both facts are optional and either may stand alone, so the line names
        # what was answered rather than assuming a territory is present.
        lines=[
            f"{fact.canonical_tax_identifier}: {_confirmed_answers(fact)}{'' if recorded else ' (already confirmed)'}",
        ],
        notices=notices,
    )


def counterparty_withdraw(
    ctx: typer.Context,
    tax_identifier: str,
    country_code: str | None = None,
) -> None:
    """Remove a confirmed fact so a corrected one can be confirmed."""
    from ...application.ledger.counterparty_establishment import (
        confirmed_counterparty_facts_key,
    )

    bucket_id = _counterparty_bucket_id()
    if confirmed_counterparty_facts_key(tax_identifier, country_code=country_code) is None:
        raise bad(
            tr("cli.ledger.counterparty.errors.unverifiable_identifier", identifier=tax_identifier),
        )
    completed = run_counterparty(
        ctx,
        request=LedgerCounterpartyRequest(
            profile_id=UUID(bucket_id),
            action="withdraw",
            tax_identifier=tax_identifier,
            country_code=country_code,
        ),
    )
    withdrawn = cast("bool", completed.projection.withdrawn)
    notices: list[Notice] = []
    if not withdrawn:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.counterparty.nothing_to_withdraw",
                message=tr(
                    "cli.ledger.counterparty.notices.nothing_to_withdraw",
                    identifier=tax_identifier,
                ),
                context={"tax_identifier": tax_identifier},
            ),
        )
    emit_envelope(
        ctx,
        command="ledger.counterparty.withdraw",
        result=CounterpartyWithdrawResult(
            canonical_tax_identifier=tax_identifier,
            withdrawn=withdrawn,
        ),
        lines=[f"{tax_identifier}: {'withdrawn' if withdrawn else 'nothing to withdraw'}"],
        notices=notices,
    )


def _counterparty_view_notices(tax_identifier: str, resolution: CounterpartyResolutionProjection) -> list[Notice]:
    """Project contradiction or absence into the shared notice channel."""
    if resolution.contradiction_detail is not None:
        confirmed = cast("str", resolution.confirmed_scope)
        evidenced = cast("str", resolution.evidenced_scope)
        return [
            Notice(
                severity=NoticeSeverity.WARNING,
                code="ledger.counterparty.evidence_contradicts_confirmation",
                message=tr(
                    "cli.ledger.counterparty.notices.evidence_contradicts_confirmation",
                    identifier=tax_identifier,
                    confirmed=confirmed,
                    evidenced=evidenced,
                ),
                context={
                    "tax_identifier": tax_identifier,
                    "confirmed_scope": confirmed,
                    "evidenced_scope": evidenced,
                },
            ),
        ]
    if resolution.territorial_scope is None:
        return [
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.counterparty.not_confirmed",
                message=tr(
                    "cli.ledger.counterparty.notices.not_confirmed",
                    identifier=tax_identifier,
                ),
                context={"tax_identifier": tax_identifier},
            ),
        ]
    return []


def _counterparty_view_result(
    ctx: typer.Context,
    tax_identifier: str,
    evidenced_scope: IvaTerritorialScope | None,
    resolution: CounterpartyResolutionProjection,
) -> CounterpartyViewResult:
    """Project the resolver's three-state answer onto the backend-owned payload."""
    operation = authority_operation(ctx)
    return CounterpartyViewResult(
        tax_identifier=tax_identifier,
        confirmed=resolution.territorial_scope is not None,
        territorial_scope=(
            require_iva_territorial_scope(resolution.territorial_scope, operation=operation)
            if resolution.territorial_scope is not None
            else None
        ),
        source=(
            ClassifierInputSource(resolution.territorial_source) if resolution.territorial_source is not None else None
        ),
        # Read from the resolution rather than from the stored record, so
        # what an operator is shown and what a later document consumes
        # cannot drift: the resolver withholds a fact the evidence
        # contradicts, and a payload read straight from the repository would
        # show a value no document will actually use.
        identification_state=(
            require_eu_member_state(resolution.identification_state, authority=operation)
            if resolution.identification_state is not None
            else None
        ),
        identification_source=(
            ClassifierInputSource(resolution.identification_source)
            if resolution.identification_source is not None
            else None
        ),
        evidenced_scope=evidenced_scope,
        contradicted=resolution.contradiction_detail is not None,
        # Carried only here and deliberately NOT in `territorial_scope`:
        # that field is what the rung will answer, and on a contradiction it
        # answers nothing.
        confirmed_scope=(
            require_iva_territorial_scope(resolution.confirmed_scope, operation=operation)
            if resolution.confirmed_scope is not None
            else None
        ),
        contradiction_detail=resolution.contradiction_detail,
    )


def _counterparty_view_line(
    tax_identifier: str,
    resolution: CounterpartyResolutionProjection,
) -> str:
    """Render the text line from the same three states as the result payload."""
    contradiction = resolution.contradiction_detail is not None
    return f"{tax_identifier}: " + (
        f"contradicted (confirmed {resolution.confirmed_scope}, evidence {resolution.evidenced_scope})"
        if contradiction
        else resolution.territorial_scope
        if resolution.territorial_scope is not None
        else "not confirmed"
    )


def counterparty_view(
    ctx: typer.Context,
    tax_identifier: str,
    country_code: str | None = None,
    evidenced_scope: IvaTerritorialScope | None = None,
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
    bucket_id = _counterparty_bucket_id()
    completed = run_counterparty(
        ctx,
        request=LedgerCounterpartyRequest(
            profile_id=UUID(bucket_id),
            action="view",
            tax_identifier=tax_identifier,
            country_code=country_code,
            evidenced_scope=evidenced_scope.value if evidenced_scope is not None else None,
        ),
    )
    resolution = cast("CounterpartyResolutionProjection", completed.projection.resolution)
    notices = _counterparty_view_notices(tax_identifier, resolution)
    emit_envelope(
        ctx,
        command="ledger.counterparty.show",
        result=_counterparty_view_result(ctx, tax_identifier, evidenced_scope, resolution),
        lines=[_counterparty_view_line(tax_identifier, resolution)],
        notices=notices,
    )


def _append_counterparty_already_confirmed_notice(
    fact: CounterpartyFactProjection, asserted_by: str, notices: list[Notice]
) -> None:
    """Report only the axes already answered by the stored counterparty fact."""
    answered = _confirmed_answers(fact)
    # Each axis appears in the context only when it was actually answered:
    # the notice reports what is stored, and a key carrying an empty string
    # for an unanswered axis would read as a stored blank answer.
    context = {
        "canonical_tax_identifier": fact.canonical_tax_identifier,
        "stored_asserted_by": fact.asserted_by,
        "supplied_asserted_by": asserted_by,
    }
    if fact.territorial_scope is not None:
        context["territorial_scope"] = fact.territorial_scope
    if fact.identification_state is not None:
        context["identification_state"] = fact.identification_state
    notices.append(
        Notice(
            severity=NoticeSeverity.INFO,
            code="ledger.counterparty.already_confirmed",
            message=tr(
                "cli.ledger.counterparty.notices.already_confirmed",
                identifier=fact.canonical_tax_identifier,
                answered=answered,
                asserted_by=fact.asserted_by,
            ),
            context=context,
        ),
    )
