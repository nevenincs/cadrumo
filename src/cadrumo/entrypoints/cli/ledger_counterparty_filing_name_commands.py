"""The channel a person states a counterparty's filing name through.

Every informative-return design that lists a third party gives its name one
fixed-width field and prescribes its content: the surnames and then the given
name for a natural person, the complete razón social for an entity. No invoice
holds that as a fact, so the person states it once per counterparty, in the
parts the designs name, and every export reads it from the counterparty's
record. A shorter rendering for a narrower field is the person's own words too,
stated with ``--rendering WIDTH=TEXT``; nothing here shortens a name.

The parts travel to the worker as stated. Whether they form a name the designs
can take is decided there, by the domain, and a refusal comes back as a
registered error naming the broken rule, never the name.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

import typer

from ...application.ledger.counterparty_establishment import confirmed_counterparty_facts_key
from ...application.ledger.counterparty_filing_name_kind_findings import CounterpartyFilingNameFinding
from ...application.ledger.counterparty_filing_name_rendering import CounterpartyFilingNameRendering
from ...application.ledger.counterparty_operation import (
    CounterpartyFactProjection,
    CounterpartyFilingNameProjection,
    LedgerCounterpartyRequest,
)
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.filing.declared_party_name import DeclaredPartyKind
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .ledger_counterparty_results import (
    CounterpartyFilingNameFindingPayload,
    CounterpartyFilingNamePayload,
    CounterpartyFilingNameRenderingPayload,
    CounterpartyFilingNameResult,
    CounterpartyWithdrawFilingNameResult,
)
from .operation_counterparty import run_counterparty


def filing_name_payload(stated: CounterpartyFilingNameProjection) -> CounterpartyFilingNamePayload:
    """Project the stated filing name onto its wire shape, parts as stated."""
    return CounterpartyFilingNamePayload(
        party_kind=DeclaredPartyKind(stated.party_kind),
        primer_apellido=stated.primer_apellido,
        segundo_apellido=stated.segundo_apellido,
        no_second_surname=stated.no_second_surname,
        nombre=stated.nombre,
        razon_social=stated.razon_social,
        renderings=tuple(
            CounterpartyFilingNameRenderingPayload(width=rendering.width, text=rendering.text)
            for rendering in stated.renderings
        ),
        asserted_by=stated.asserted_by,
        asserted_at=stated.asserted_at,
    )


def filing_name_finding_payloads(
    findings: tuple[CounterpartyFilingNameFinding, ...],
) -> tuple[CounterpartyFilingNameFindingPayload, ...]:
    """Project the operation's findings onto their wire shape."""
    return tuple(
        CounterpartyFilingNameFindingPayload(
            code=finding.code,
            declared_kind=DeclaredPartyKind(finding.declared_kind),
            observed_form=DeclaredPartyKind(finding.observed_form),
        )
        for finding in findings
    )


def _party_kind_words(kind: str) -> str:
    """Serve the words for a party kind from the catalogue."""
    if kind == DeclaredPartyKind.ENTITY.value:
        return tr("cli.ledger.counterparty.party_kinds.entity")
    return tr("cli.ledger.counterparty.party_kinds.natural_person")


def filing_name_finding_notices(findings: tuple[CounterpartyFilingNameFinding, ...]) -> list[Notice]:
    """Render each finding as a warning in served words, naming kinds and never the party."""
    return [
        Notice(
            severity=NoticeSeverity.WARNING,
            code=f"ledger.counterparty.{finding.code}",
            message=tr(
                "cli.ledger.counterparty.notices.filing_name_kind_contradicts_identifier_form",
                declared=_party_kind_words(finding.declared_kind),
                observed=_party_kind_words(finding.observed_form),
            ),
            context={"declared_kind": finding.declared_kind, "observed_form": finding.observed_form},
        )
        for finding in findings
    ]


def counterparty_filing_name(
    ctx: typer.Context,
    tax_identifier: str,
    kind: DeclaredPartyKind,
    primer_apellido: str | None = None,
    segundo_apellido: str | None = None,
    no_second_surname: bool = False,
    nombre: str | None = None,
    razon_social: str | None = None,
    rendering: tuple[CounterpartyFilingNameRendering, ...] = (),
    country_code: str | None = None,
    actor: str | None = None,
) -> None:
    """State the name a counterparty is filed under, or report the stored one unchanged."""
    bucket_id = active_bucket_id_or_refuse()
    asserted_by = actor or bucket_id or "operator"
    completed = run_counterparty(
        ctx,
        request=LedgerCounterpartyRequest(
            profile_id=UUID(bucket_id),
            action="filing_name",
            tax_identifier=tax_identifier,
            country_code=country_code,
            asserted_by=asserted_by,
            party_kind=kind.value,
            primer_apellido=primer_apellido,
            segundo_apellido=segundo_apellido,
            no_second_surname=no_second_surname,
            nombre=nombre,
            razon_social=razon_social,
            renderings=rendering,
        ),
    )
    result = completed.projection
    # The completion is correlated before it is returned: a statement's result
    # carries both the record and the stated name.
    facts = cast("CounterpartyFactProjection", result.facts)
    stated = cast("CounterpartyFilingNameProjection", result.filing_name)
    recorded = bool(result.recorded)
    notices: list[Notice] = filing_name_finding_notices(result.findings)
    if not recorded:
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="ledger.counterparty.filing_name_already_stated",
                message=tr(
                    "cli.ledger.counterparty.notices.filing_name_already_stated",
                    identifier=facts.canonical_tax_identifier,
                    asserted_by=stated.asserted_by,
                ),
                context={"canonical_tax_identifier": facts.canonical_tax_identifier},
            )
        )
    emit_envelope(
        ctx,
        command="ledger.counterparty.filing_name",
        result=CounterpartyFilingNameResult(
            counterparty_key=facts.counterparty_key,
            canonical_tax_identifier=facts.canonical_tax_identifier,
            filing_name=filing_name_payload(stated),
            recorded=recorded,
            findings=filing_name_finding_payloads(result.findings),
        ),
        lines=[
            tr(
                "cli.ledger.counterparty.lines.filing_name_stated"
                if recorded
                else "cli.ledger.counterparty.lines.filing_name_unchanged",
                identifier=facts.canonical_tax_identifier,
            )
        ],
        notices=notices,
    )


def counterparty_withdraw_filing_name(
    ctx: typer.Context,
    tax_identifier: str,
    country_code: str | None = None,
) -> None:
    """Withdraw only the stated filing name, keeping every other answer about the counterparty."""
    bucket_id = active_bucket_id_or_refuse()
    if confirmed_counterparty_facts_key(tax_identifier, country_code=country_code) is None:
        raise bad(tr("cli.ledger.counterparty.errors.unverifiable_identifier", identifier=tax_identifier))
    completed = run_counterparty(
        ctx,
        request=LedgerCounterpartyRequest(
            profile_id=UUID(bucket_id),
            action="withdraw_filing_name",
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
                code="ledger.counterparty.no_filing_name_to_withdraw",
                message=tr("cli.ledger.counterparty.notices.no_filing_name_to_withdraw", identifier=tax_identifier),
                context={"tax_identifier": tax_identifier},
            )
        )
    emit_envelope(
        ctx,
        command="ledger.counterparty.withdraw_filing_name",
        result=CounterpartyWithdrawFilingNameResult(canonical_tax_identifier=tax_identifier, withdrawn=withdrawn),
        lines=[
            tr("cli.ledger.counterparty.lines.filing_name_withdrawn", identifier=tax_identifier)
            if withdrawn
            else tr("cli.ledger.counterparty.notices.no_filing_name_to_withdraw", identifier=tax_identifier)
        ],
        notices=notices,
    )
