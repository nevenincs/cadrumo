"""Facturae states no element equal to this codebase's invoice total.

``InvoiceTotal`` looks like the printed total and is not one. The schema
documents it as ``TotalGrossAmountBeforeTaxes + TotalTaxOutputs -
TotalTaxesWithheld``, so it is stated NET of any IRPF retención, and
reimbursable expenses join only at ``TotalExecutableAmount``. Meanwhile this
codebase's identity (LIVA art. 78.Tres.3.º) is::

    total = taxable_base + cuota + recargo + suplido
    cash  = total - retención

So ``InvoiceTotal`` is neither: it is ``cash`` minus the suplido. Reading it as
the total understated every withheld invoice by exactly its retención, and the
arithmetic-closure check then refused documents that are perfectly correct --
the over-refusal direction, on the commonest Spanish professional invoice there
is, and invisible because both older corpus specimens carry neither optional
term.

**The mapping is grounded in the schema's own words, in Spanish.** The bundled
``facturae-3-2-2-invoice-totals`` extract carries each element's
``xs:documentation``: ``TotalTaxOutputs`` is *"Sumatorio de todas Cuotas y
Recargos de Equivalencia"* -- both tax terms of the identity in this codebase's
own vocabulary -- ``TotalTaxesWithheld`` is *"Total impuestos retenidos"*, and
``ReimbursableExpenses`` is *"Suplidos incorporados en la factura"*. The format
names the concepts; nothing here is inferred through an English gloss.

**The total is DERIVED, never read**, because no element carries it.

See Also:
    :func:`~application.ledger.closure_findings`
        The identity this mapping exists to let a correct document satisfy.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from ..parsers import parse_einvoice_document

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_CORPUS = Path(__file__).parents[4] / "application" / "ledger" / "tests" / "_evidence_corpus"
_EXTRACT = Path(__file__).parents[4] / "_data" / "corpus" / "facturae" / "facturae-3-2-2-invoice-totals.json"

#: The specimen carrying both optional terms. Every other Facturae specimen in
#: the corpus omits them, which is why nothing failed before.
_WITHHELD: Final = "facturae_32_retencion_suplidos_invoice.xml"
_PLAIN: Final = "facturae_32_series_and_parties_invoice.xml"

_BASE: Final = Decimal("1000.00")
_CUOTA: Final = Decimal("210.00")
_RETENCION: Final = Decimal("150.00")
_SUPLIDO: Final = Decimal("45.00")

#: What the document itself states, and neither is the codebase's total.
_STATED_INVOICE_TOTAL: Final = Decimal("1060.00")
_STATED_EXECUTABLE: Final = Decimal("1105.00")


def _parsed(name: str):
    return parse_einvoice_document((_CORPUS / name).read_bytes())


class TestTheTotalIsDerivedRatherThanRead:
    """No Facturae element equals the identity's total, so it is assembled."""

    def test_the_derived_total_is_gross_of_retencion(self) -> None:
        """The identity's total, which is NOT the element that looks like it.

        Asserted against the stated ``InvoiceTotal`` as well, because equality
        with the derived figure would mean the derivation had quietly become a
        read again -- the exact regression this file exists to catch.
        """
        parsed = _parsed(_WITHHELD)

        assert parsed.grand_total == _BASE + _CUOTA + _SUPLIDO
        assert parsed.grand_total != _STATED_INVOICE_TOTAL

    def test_the_two_terms_the_reader_previously_dropped_are_recovered(self) -> None:
        """Retención and suplido, each from the element the format dedicates to it."""
        parsed = _parsed(_WITHHELD)

        assert parsed.retencion_amount == _RETENCION
        assert parsed.suplidos_amount == _SUPLIDO

    def test_the_derivation_reconciles_with_an_element_it_never_reads(self) -> None:
        """The anti-tautology check: two routes, one figure.

        ``TotalExecutableAmount`` is documented as the outstanding amount plus
        reimbursable expenses, and this codebase's ``cash`` is ``total -
        retención``. The reader derives the total from the base, the output-tax
        total and the suplido, and never looks at ``TotalExecutableAmount`` --
        so the two agreeing is an independent confirmation rather than a value
        restated. A derivation that dropped or double-counted any term reds
        here even if every assertion above were rewritten to match it.
        """
        parsed = _parsed(_WITHHELD)
        assert parsed.grand_total is not None
        assert parsed.retencion_amount is not None

        assert parsed.grand_total - parsed.retencion_amount == _STATED_EXECUTABLE

    def test_a_document_stating_neither_term_is_unchanged(self) -> None:
        """The control, and it is what the older corpus specimens exercise.

        With no retención and no suplido the derived total coincides with the
        stated ``InvoiceTotal``, which is why reading that element looked
        correct for as long as the corpus carried only such documents.
        """
        parsed = _parsed(_PLAIN)

        assert parsed.grand_total == Decimal("242.00")
        assert parsed.suplidos_amount is None
        assert parsed.retencion_amount == Decimal("0.00")


class TestTheSuplidoIsReadFromEitherStatement:
    """Facturae states suplidos twice, both optional, and a document may use either."""

    @staticmethod
    def _with(totals_fragment: str) -> bytes:
        """Return the plain specimen with a suplidos statement injected."""
        xml = (_CORPUS / _PLAIN).read_text(encoding="utf-8")
        anchor = "        <InvoiceTotal>242.00</InvoiceTotal>\n"
        assert xml.count(anchor) == 1, "the specimen's totals block has drifted"
        return xml.replace(anchor, anchor + totals_fragment, 1).encode("utf-8")

    def test_the_aggregate_is_taken_where_the_document_states_it(self) -> None:
        """``Total de suplidos`` -- the format's own sum, preferred."""
        parsed = parse_einvoice_document(
            self._with("        <TotalReimbursableExpenses>30.00</TotalReimbursableExpenses>\n"),
        )

        assert parsed.suplidos_amount == Decimal("30.00")
        assert parsed.grand_total == Decimal("272.00")

    def test_the_itemised_block_is_summed_where_the_aggregate_is_absent(self) -> None:
        """Both statements are optional, so neither may be assumed present."""
        parsed = parse_einvoice_document(
            self._with(
                "        <ReimbursableExpenses>"
                "<ReimbursableExpense><ReimbursableExpenseAmount>12.00</ReimbursableExpenseAmount></ReimbursableExpense>"
                "<ReimbursableExpense><ReimbursableExpenseAmount>18.00</ReimbursableExpenseAmount></ReimbursableExpense>"
                "</ReimbursableExpenses>\n",
            ),
        )

        assert parsed.suplidos_amount == Decimal("30.00"), "both itemised expenses, summed"
        assert parsed.grand_total == Decimal("272.00")


class TestTheMappingIsGroundedInTheBundledExtract:
    """The arithmetic above is the schema's, and this states where that is checkable.

    Without this the numbers in the cases above would rest on the fixture's
    author. The extract carries the format's own computation annotations, so a
    reader can confirm the mapping against the authority rather than against
    this suite.
    """

    def test_the_extract_documents_the_elements_the_mapping_reads(self) -> None:
        """Each element the reader maps carries its own annotation in the extract."""
        extract = json.loads(_EXTRACT.read_text(encoding="utf-8"))
        documented = {entry["name"]: " ".join(entry.get("documentation", [])) for entry in extract["elements"]}

        assert "Sumatorio de todas Cuotas y Recargos de Equivalencia" in documented["TotalTaxOutputs"]
        assert "Total impuestos retenidos" in documented["TotalTaxesWithheld"]
        assert "Suplidos" in documented["ReimbursableExpenses"]

    def test_the_extract_records_why_the_total_cannot_be_read(self) -> None:
        """``InvoiceTotal``'s own annotation is what rules out reading it."""
        extract = json.loads(_EXTRACT.read_text(encoding="utf-8"))
        invoice_total = next(e for e in extract["elements"] if e["name"] == "InvoiceTotal")

        assert any(
            "TotalGrossAmountBeforeTaxes + TotalTaxOutputs - TotalTaxesWithheld" in doc
            for doc in invoice_total["documentation"]
        )

    def test_the_extract_is_stamped_against_the_official_payload(self) -> None:
        """A grounding artefact naming a mirror is the defect it exists to prevent."""
        provenance = json.loads(_EXTRACT.read_text(encoding="utf-8"))["provenance"]

        assert provenance["source_url"].startswith("https://www.facturae.gob.es/")
        assert provenance["schema_version"] == "Facturae 3.2.2"
        assert len(provenance["payload_sha256"]) == 64
