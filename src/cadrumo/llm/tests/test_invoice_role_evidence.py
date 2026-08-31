"""The anchored candidate payload's THIRD half: what assigns an identity to a party.

An invoice prints two tax identifiers of identical shape. An anchor answers
*where on the page was this printed*, which for two same-shaped numbers is no
answer at all to *whose is it* -- and whose it is decides the counterparty AEAT
reconciles a declaration against, so a wrong one is worse than an absent one.

The role-evidence key is the payload field that closes that. It carries the
printed heading or label the reader copied, and it is a printed excerpt, which
is what makes it checkable: an invented heading is dropped by the grounding
stage the same way an invented anchor is.

What it replaces was circular. The reading stage once synthesised ``the reader
assigned this identifier to supplier_tax_id``, which says the reader assigned
the field rather than that the document evidenced it -- always truthy, so it
permanently satisfied the guard that exists to refuse an unevidenced identity,
while its note read to an operator as positive evidence.

No model runs in this module. Every property here is a property of the declared
contract, the compiled prompt text, or the parser, and each is assertable
without inference.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ...core.period import Period
from ..invoice_extraction_prompt import build_invoice_extraction_prompt
from ..invoice_field_contract import (
    ANCHOR_KEY_SUFFIX,
    INVOICE_FIELD_CONTRACTS,
    ROLE_EVIDENCE_KEY_SUFFIX,
    InvoiceFieldContract,
    InvoiceFieldForm,
    identity_field_names,
    role_evidence_key_for_field,
)
from ..invoice_field_grounding import (
    ExtractedInvoiceFields,
    ExtractedRoleEvidence,
    parse_invoice_extraction_response,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_2026 = Period.from_year_and_code(2026, "0A")


class TestTheContractDeclaresRoleEvidenceExactlyWhereItIsMeaningful:
    """One declaration decides which fields evidence a role, and it is derived."""

    def test_the_identity_fields_are_exactly_the_tax_identifier_fields(self) -> None:
        """Derived from the FORM, so a fourth identity field enrols by construction.

        A hand-listed set is how a family ends up half-covered: the collection
        describes the enrolled set while enforcing nothing about it, which is
        the shape a ledger source-kind collection failed in before.
        """
        assert set(identity_field_names()) == {
            contract.field_name
            for contract in INVOICE_FIELD_CONTRACTS
            if contract.form is InvoiceFieldForm.TAX_IDENTIFIER
        }
        assert identity_field_names(), "the fixture must find identity fields, or every case below is vacuous"

    def test_the_payload_schema_carries_exactly_the_declared_identity_fields(self) -> None:
        """The schema and the declaration agree, in both directions."""
        assert set(ExtractedRoleEvidence.model_fields) == set(identity_field_names())

    def test_an_identity_field_without_a_role_evidence_instruction_is_refused(self) -> None:
        """The declaration cannot ship half-made.

        Mutation that must trip this: drop ``role_evidence_instruction`` from
        either identity row in ``INVOICE_FIELD_CONTRACTS``.
        """
        with pytest.raises(ValidationError, match="must declare how its role is evidenced"):
            InvoiceFieldContract(
                field_name="supplier_tax_id",
                form=InvoiceFieldForm.TAX_IDENTIFIER,
                concept="the issuer's identifier",
                form_instruction="copy as printed",
            )

    def test_a_non_identity_field_carrying_role_evidence_is_refused(self) -> None:
        """The other direction: a monetary value has no party role to evidence.

        Asking for one would invite a model to invent a role for a figure that
        does not have one, which is fabrication with extra structure.
        """
        with pytest.raises(ValidationError, match="only meaningful for an identity field"):
            InvoiceFieldContract(
                field_name="taxable_base",
                form=InvoiceFieldForm.MONETARY_AMOUNT,
                concept="the net amount before tax",
                form_instruction="digits only",
                role_evidence_instruction="copy the heading",
            )


class TestThePromptAsksForPrintedEvidenceRatherThanAConclusion:
    """The instruction must demand a copy, never the reader's own account."""

    def test_the_prompt_asks_for_the_role_evidence_key_of_every_identity_field(self) -> None:
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text

        for field_name in identity_field_names():
            assert f'"{role_evidence_key_for_field(field_name)}"' in text

    def test_the_prompt_never_asks_a_non_identity_field_to_evidence_a_role(self) -> None:
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text
        identity = set(identity_field_names())

        for contract in INVOICE_FIELD_CONTRACTS:
            if contract.field_name in identity:
                continue
            assert role_evidence_key_for_field(contract.field_name) not in text

    def test_the_instruction_demands_a_printed_copy_and_forbids_a_decision(self) -> None:
        """The distinction the whole mechanism turns on, stated to the model.

        A reader told to explain its choice writes an unfalsifiable sentence; a
        reader told to copy what is printed writes something the document can
        contradict. Only the second can ever be dropped.
        """
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text

        assert "Never write what you decided; write what the document shows." in text
        assert "copy the printed heading, label or line" in text

    def test_the_suffix_the_prompt_renders_is_the_one_the_parser_reads(self) -> None:
        """One declaration, two derivations: a suffix spelled twice fails silently.

        Silently is the operative word -- a key the parser does not recognise is
        indistinguishable from a model that returned nothing for it, so the
        counterparty path would simply stop working with no error anywhere.
        """
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text
        assert ROLE_EVIDENCE_KEY_SUFFIX in text

        parsed = parse_invoice_extraction_response(
            json.dumps(
                {
                    "supplier_tax_id": "B12345674",
                    f"supplier_tax_id{ROLE_EVIDENCE_KEY_SUFFIX}": "Proveedor:",
                    "customer_tax_id": "A82645177",
                    f"customer_tax_id{ROLE_EVIDENCE_KEY_SUFFIX}": "Cliente:",
                },
            ),
        )

        assert parsed.role_evidence.supplier_tax_id == "Proveedor:"
        assert parsed.role_evidence.customer_tax_id == "Cliente:"

    def test_the_two_suffixes_do_not_collide(self) -> None:
        """A role-evidence key must never be routed into the anchors half.

        The parser tests the more specific suffix first, so the two staying
        distinct is a property worth asserting rather than assuming: if one ever
        became a suffix of the other, every role-evidence value would silently
        land in an anchor slot.
        """
        assert not ROLE_EVIDENCE_KEY_SUFFIX.endswith(ANCHOR_KEY_SUFFIX)
        assert not ANCHOR_KEY_SUFFIX.endswith(ROLE_EVIDENCE_KEY_SUFFIX)


class TestTheStrictClosedPayloadRefuses:
    """The schema is closed, and an unrecognised key is a model inventing structure."""

    def test_an_out_of_schema_role_evidence_key_refuses(self) -> None:
        """A role-evidence key for a field that declares none is rejected.

        Not tolerated as a stray extra: a model that has invented a party role
        for the grand total has invented a fact about the document, and letting
        it ride along is how a fabricated field reaches an operator unnoticed.
        """
        payload = json.dumps(
            {
                "supplier_tax_id": "B12345674",
                f"grand_total{ROLE_EVIDENCE_KEY_SUFFIX}": "Total:",
            },
        )

        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            parse_invoice_extraction_response(payload)
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.response_schema_valid"

    def test_an_unrecognised_top_level_key_still_refuses(self) -> None:
        """The pre-existing bound, re-asserted beside the new half.

        Splitting the reply into three halves must not have opened a route where
        an unknown key lands in whichever bucket its name happens to suffix.
        """
        payload = json.dumps({"supplier_tax_id": "B12345674", "vendor_confidence": "high"})

        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            parse_invoice_extraction_response(payload)
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.response_schema_valid"

    def test_a_reply_carrying_no_role_evidence_parses_and_evidences_nothing(self) -> None:
        """Absence is the fail-safe direction, so it must parse rather than raise.

        An unevidenced identity refuses downstream, so tolerating the absence
        here costs no safety -- while rejecting the reply would lose every other
        field the model read correctly.
        """
        parsed = parse_invoice_extraction_response(json.dumps({"supplier_tax_id": "B12345674"}))

        assert parsed.fields.supplier_tax_id == "B12345674"
        assert parsed.role_evidence.supplier_tax_id is None
        assert parsed.role_evidence.customer_tax_id is None

    def test_the_role_evidence_half_is_disjoint_from_the_value_half(self) -> None:
        """A role-evidence key never lands in the value half, and vice versa.

        Proven by sending both for one field and asserting each arrived in its
        own half, rather than by trusting the split's implementation.
        """
        parsed = parse_invoice_extraction_response(
            json.dumps(
                {
                    "supplier_tax_id": "B12345674",
                    f"supplier_tax_id{ANCHOR_KEY_SUFFIX}": "B-12345674",
                    f"supplier_tax_id{ROLE_EVIDENCE_KEY_SUFFIX}": "Proveedor:",
                },
            ),
        )

        assert parsed.fields.supplier_tax_id == "B12345674"
        assert parsed.anchors.supplier_tax_id == "B-12345674"
        assert parsed.role_evidence.supplier_tax_id == "Proveedor:"
        assert set(ExtractedRoleEvidence.model_fields) <= set(ExtractedInvoiceFields.model_fields)
