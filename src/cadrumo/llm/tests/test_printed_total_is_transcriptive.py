"""The total a reader records is the one the document PRINTED, never a recomputation.

A reader that computes a total and never compares it to the printed one cannot
tell a correct read from a confident misread. The printed figure and the derived
figure are different facts: the reader's job is to record what the page states,
and deriving the arithmetically correct total belongs to
:func:`~application.invoices.build_catalogue_invoice`, whose disagreement with
the printed figure is reported by
:func:`~application.ledger.evidence_draft.printed_total_discrepancy`. Two authorities, one each.

**So the value this stage must not touch is exactly the one it would be most
tempted to fix.** A document whose printed total does not equal the sum of its
base and its tax is not a document to correct on the way past -- it is the single
most reliable signal that the read is wrong, or that the page carries an amount
the record cannot yet represent (a recargo de equivalencia, an unread rate). A
reader that silently substitutes the correct sum destroys that signal and
produces a record that is confidently, unsurfacably wrong.

**The figures here are the corpus's, not invented.** Of the twenty-nine pinned
corpus slots carrying a printed total, twenty-seven state the same value the sum
implies and two do not: they print 890,00 against a base of 766,30 and tax of
160,92, which sum to 927,22. That document's key lists the planted defect
verbatim as *"Total impreso no cuadra con la suma de bases e IVA"*. A fixture
authored to agree with itself could not fail on the defect that is actually
planted in the corpus, so the divergent pair is used as the corpus states it.

See Also:
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        The record whose total this pins as transcriptive.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ...core import FieldOrigin
from .._invoice_field_contract import INVOICE_FIELD_CONTRACTS, anchor_key_for_field
from .._invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PRINTED_TOTAL = Decimal("890.00")
"""What the divergent corpus document actually prints as its total."""

_SUM_THE_LINES_IMPLY = Decimal("927.22")
"""766.30 + 160.92 -- the figure a reader that "fixed" the page would record."""


def _reply(*, taxable_base: str | None, iva_amount: str | None, grand_total: str | None) -> str:
    """Render one model reply in the flat value+anchor shape the prompt asks for.

    Built as the JSON a reading model EMITS and parsed by the production parser,
    rather than by constructing the grounded record directly. A fixture that
    starts from the parsed object skips the stage under test and would pass
    against a parser that had stopped working at all.
    """
    values: dict[str, str | None] = {
        "supplier_tax_id": "B12345674",
        "supplier_name": "Pinturas del Norte SL",
        "invoice_number": "SIN-NUMERO",
        "invoice_date": "11/06/2026",
        "taxable_base": taxable_base,
        "iva_rate": "21",
        "iva_amount": iva_amount,
        "grand_total": grand_total,
        "currency": "EUR",
    }
    payload: dict[str, str | None] = dict(values)
    payload.update({anchor_key_for_field(name): value for name, value in values.items()})
    return json.dumps(payload)


def _draft_total(*, taxable_base: str | None, iva_amount: str | None, grand_total: str | None) -> Decimal | None:
    draft = ground_extracted_fields(
        parse_invoice_extraction_response(
            _reply(taxable_base=taxable_base, iva_amount=iva_amount, grand_total=grand_total),
        ),
        raw_text_length=512,
        origin=FieldOrigin.VISION,
    )
    return draft.grand_total


def test_a_printed_total_that_contradicts_the_lines_is_recorded_as_printed() -> None:
    """The defect case, and the only one that discriminates.

    On a document where the printed total agrees with the sum, recording the
    printed figure and recomputing it are indistinguishable -- which is why the
    twenty-seven agreeing corpus slots prove nothing here and the two divergent
    ones are the whole test.
    """
    recorded = _draft_total(taxable_base="766,30", iva_amount="160,92", grand_total="890,00")

    assert recorded == _PRINTED_TOTAL, (
        f"the document prints {_PRINTED_TOTAL} and the draft recorded {recorded}. The reader must "
        "carry the printed figure verbatim; the disagreement with the derived total is the signal a "
        "downstream check exists to raise, and a reader that resolves it here deletes the signal."
    )
    assert recorded != _SUM_THE_LINES_IMPLY, (
        f"the draft recorded {_SUM_THE_LINES_IMPLY}, which is the sum of the base and the tax rather "
        "than what the page states. The reading stage has acquired a second arithmetic authority, "
        "duplicating the identity owned by domain/invoices/_decomposition.py."
    )


def test_a_total_that_agrees_with_the_lines_is_still_recorded() -> None:
    """Positive control: without it, "not recomputed" cannot be told from "never populated".

    Every assertion above passes equally against a reader that dropped the total
    on the floor, so this pins that the agreeing case -- the ordinary one, and
    twenty-seven of the twenty-nine corpus slots -- still lands a value.
    """
    recorded = _draft_total(taxable_base="766,30", iva_amount="160,92", grand_total="927,22")

    assert recorded == _SUM_THE_LINES_IMPLY, (
        f"an ordinary invoice whose printed total agrees with its lines recorded {recorded}; the "
        "field is not being populated at all, so the divergence assertions above prove nothing"
    )


def test_an_unprinted_total_stays_absent_rather_than_becoming_the_sum() -> None:
    """``None`` means NOT PRINTED -- never zero, and never the figure the lines imply.

    A document carrying only line items is ordinary. Collapsing that absence into
    the derived sum would manufacture a printed total the page never stated, and
    the downstream cross-check would then compare a derived figure against itself
    and report agreement it never observed.
    """
    recorded = _draft_total(taxable_base="766,30", iva_amount="160,92", grand_total=None)

    assert recorded is None, (
        f"a document that printed no total recorded {recorded}. Absence must stay representable: "
        "zero is a stated amount and the derived sum is a fabrication, and either makes the "
        "printed-versus-derived cross-check compare something to itself."
    )


def test_the_contract_tells_the_model_to_copy_the_printed_total() -> None:
    """The instruction the model receives must say WHICH figure, not only what shape.

    Every monetary contract already constrains the FORM -- digits, printed
    decimal separator, no currency sign -- and form is silent on the question
    that matters here. The concept once read only "the total payable amount",
    which on a document whose printed total is wrong does not say whether to copy
    the page or to correct it, so the emitted figure was undetermined on exactly
    the two corpus documents where the answer changes the record.

    Asserted on the contract because the contract is what the compiled prompt
    renders; the behavioural tests above cannot see an instruction the model was
    never given.
    """
    contract = next(item for item in INVOICE_FIELD_CONTRACTS if item.field_name == "grand_total")
    guidance = f"{contract.concept} {contract.form_instruction}".lower()

    assert "as printed" in guidance or "as it is printed" in guidance, (
        f"the grand_total contract reads {contract.concept!r}, which does not tell the model to copy "
        "the printed figure. On a document whose total disagrees with its lines, nothing determines "
        "which of the two the model emits."
    )
    assert "sum" in guidance or "add" in guidance or "recompute" in guidance, (
        "the contract does not address the disagreeing case at all. It must say what to do when the "
        "printed total does not equal the sum, because that is the only case where the instruction "
        "changes the answer."
    )
