"""The persona-derived seed frames render from the catalogue and refuse what a persona cannot state."""

from __future__ import annotations

import pytest

from ..persona_profile import SANDBOX_PERSONA_ID, pinned_persona
from ..seed_generator import check_seeds, parse_seed_header, render_seed, render_statement_fixture

pytestmark = [pytest.mark.integration, pytest.mark.hex_core, pytest.mark.docs]

_REGION = ":generated: begin\n:generated: end\n"


def test_the_committed_recipes_and_statement_match_their_personas() -> None:
    assert check_seeds() == ()


def test_a_ledger_region_records_every_row_invoice_and_document_of_the_persona() -> None:
    text = f":persona: {SANDBOX_PERSONA_ID}\n:profile: activity-start-date\n:ledger: all\n{_REGION}"
    rendered = render_seed(text, name="probe")
    with pinned_persona(SANDBOX_PERSONA_ID) as (persona, envelope):
        rows = persona.ledger
        documents = persona.documents
        in_date_order = [row.ref for row in sorted(rows, key=lambda row: (row.operation_date(envelope), row.ref))]

    added = [line for line in rendered.splitlines() if " app ledger add " in line]
    linked = [line for line in rendered.splitlines() if " app ledger link " in line]
    attached = [line for line in rendered.splitlines() if " app ledger attach " in line]
    assert [line.rsplit("--idempotency-key ", 1)[1] for line in added] == in_date_order
    assert len(linked) == sum(1 for row in rows if row.invoice_kind is not None)
    assert len(attached) == sum(len(document.attach_to) for document in documents)


def test_the_statement_fixture_carries_each_row_ref_as_its_bank_reference() -> None:
    name, text = render_statement_fixture()
    with pinned_persona(SANDBOX_PERSONA_ID) as (persona, envelope):
        year = persona.fiscal_year.resolve(envelope)
        refs = sorted(row.ref for row in persona.ledger)

    assert name == f"movimientos-{year}-1t.csv"
    assert sorted(line.rsplit(";", 1)[1] for line in text.splitlines()[1:]) == refs


@pytest.mark.parametrize(
    ("directive", "refusal"),
    [
        (":ledger: some", "':ledger:' takes only 'all'"),
        (":carry: 130", "':carry:' records only the Modelo 303"),
    ],
)
def test_an_unsupported_directive_value_is_refused(directive: str, refusal: str) -> None:
    text = f":persona: {SANDBOX_PERSONA_ID}\n:profile: activity-start-date\n{directive}\n{_REGION}"
    with pytest.raises(ValueError, match=refusal):
        parse_seed_header(text, name="probe")


def test_filing_a_modelo_the_persona_never_owes_is_refused() -> None:
    text = f":persona: {SANDBOX_PERSONA_ID}\n:profile: activity-start-date\n:file: 349\n{_REGION}"
    with pytest.raises(ValueError, match="files Modelo 303 only"):
        render_seed(text, name="probe")


def test_a_generated_document_is_registered_from_its_fixture_and_attached_to_its_row() -> None:
    text = ":persona: autonomo-fontanero\n:profile: tax-id\n:ledger: all\n" + _REGION
    lines = render_seed(text, name="probe").splitlines()

    added = next(
        index
        for index, line in enumerate(lines)
        if "--idempotency-key persona-autonomo-fontanero-factura-fon-alq-01" in line
    )
    assert " evidence add fixtures/personas/autonomo-fontanero/factura-fon-alq-01.xml " in lines[added]
    assert lines[added + 1] == "@capture factura_fon_alq_01_evidence result.evidence_id"
    assert lines[added + 2] == (
        "@setup aeat app ledger attach {fon_alq_01} --purchase-invoice-evidence-id {factura_fon_alq_01_evidence}"
    )


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        (f":persona: {SANDBOX_PERSONA_ID}\n{_REGION}", "also declares :profile:"),
        (f":persona: {SANDBOX_PERSONA_ID}\n:profile: a\n:profile: b\n{_REGION}", "declared twice"),
        (f":persona: {SANDBOX_PERSONA_ID}\n:profile: a\n:generated: begin\n", "exactly one"),
        (f":persona: \n:profile: a\n{_REGION}", "must each carry a value"),
    ],
)
def test_an_incomplete_header_is_refused(text: str, refusal: str) -> None:
    with pytest.raises(ValueError, match=refusal):
        parse_seed_header(text, name="probe")
