"""Real-behaviour tests for the text-to-fields semantic invoice extractor.

Every test here is offline by construction. The prompt is asserted on the string
the extractor actually builds, and the extraction behaviour is asserted by
feeding canned model-response text through the real parser and the real grounded
re-validator. No transport is dispatched, so nothing in this module can reach a
provider.

See Also:
    :class:`~llm._evidence_draft_text.TextInvoiceFieldExtractor`
        Reader under test.
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        Grounded re-validation shared with the vision reader.
    :func:`~core.identity.nif_iva_format_for_country`
        EU NIF-IVA structural authority the tax-id grounding now consults.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...application.ledger.evidence import PurchaseInvoiceEvidenceInputError
from ...core import FieldOrigin, NoRecoveryOutcome
from ...core.config import load_settings
from .._evidence_draft_text import (
    TextInvoiceFieldExtractor,
    build_text_field_extraction_prompt,
)
from .._invoice_field_grounding import (
    ExtractedFieldAnchors,
    ExtractedInvoiceFields,
    ExtractedInvoiceResponse,
    ground_extracted_fields,
    parse_invoice_extraction_response,
)
from .._models import LLMProvider, LLMRequest
from ..errors import LLMConfigError, LLMValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# AEAT-checksum-valid Spanish identifiers: a CIF and a NIF.
_SPANISH_CIF = "B12345674"
_SPANISH_NIF = "45678912S"


def _fields(**overrides: str | None) -> ExtractedInvoiceResponse:
    payload: dict[str, str | None] = {
        "supplier_tax_id": _SPANISH_CIF,
        "invoice_number": "2026-0142",
        "invoice_date": "10/03/2026",
        "taxable_base": "100,00",
        "iva_rate": "21",
        "iva_amount": "21,00",
        "grand_total": "121,00",
        "currency": "EUR",
    }
    payload.update(overrides)
    return ExtractedInvoiceResponse(
        fields=ExtractedInvoiceFields.model_validate_json(json.dumps(payload)),
        anchors=ExtractedFieldAnchors(),
    )


def _grounded_tax_id(raw: str) -> str | None:
    """Return what the grounding layer makes of ``raw``, through the real draft path."""
    return ground_extracted_fields(
        _fields(supplier_tax_id=raw),
        raw_text_length=10,
        origin=FieldOrigin.TEXT_LAYER,
    ).supplier_tax_id


class TestForeignCounterpartyTaxIdsSurviveGrounding:
    """A correct read of a valid EU IVA number must reach the operator.

    Routing every transcribed identifier through the Spanish checksum authority
    alone silently dropped every non-Spanish supplier to ``None`` -- the whole
    Modelo 349 / intra-EU reverse-charge population. Grounding now falls through
    to the EU VIES structural authority.
    """

    @pytest.mark.parametrize(
        "iva_number",
        [
            pytest.param("IE9825613K", id="ireland"),
            pytest.param("DE811569869", id="germany"),
            pytest.param("FR40303265045", id="france"),
            pytest.param("NL123456789B01", id="netherlands"),
            pytest.param("XI123456789", id="northern-ireland"),
        ],
    )
    def test_a_structurally_valid_eu_iva_number_is_kept(self, iva_number: str) -> None:
        assert _grounded_tax_id(iva_number) == iva_number

    def test_separators_an_operator_or_document_prints_are_normalised_away(self) -> None:
        """an IVA number printed with spaces or dots still grounds, in canonical form."""
        assert _grounded_tax_id("DE 811.569.869") == "DE811569869"

    @pytest.mark.parametrize(
        "tax_id",
        [
            pytest.param(_SPANISH_CIF, id="spanish-cif"),
            pytest.param(_SPANISH_NIF, id="spanish-nif"),
        ],
    )
    def test_spanish_identifiers_still_ground(self, tax_id: str) -> None:
        assert _grounded_tax_id(tax_id) == tax_id


class TestGroundingStillRefusesWhatItCannotVerify:
    """The fall-through is closed, not permissive: it did not become "accept anything"."""

    def test_an_invalid_spanish_cif_control_character_is_still_rejected(self) -> None:
        """``B1234567X`` is the deliberate control: right shape, wrong check character."""
        assert _grounded_tax_id("B1234567X") is None

    @pytest.mark.parametrize(
        "candidate",
        [
            pytest.param("ZZ123456789", id="prefix-names-no-member-state"),
            pytest.param("QQ99", id="prefix-and-body-both-unknown"),
            pytest.param("DE81156986", id="germany-one-digit-short"),
            pytest.param("DE8115698690", id="germany-one-digit-long"),
            pytest.param("IE9825613", id="ireland-missing-check-letter"),
            pytest.param("FR4030326504", id="france-one-digit-short"),
            pytest.param("NOT A TAX ID AT ALL", id="prose"),
            pytest.param("123456789", id="bare-digits"),
            pytest.param("D", id="too-short-to-carry-a-prefix"),
        ],
    )
    def test_a_number_matching_no_published_pattern_is_dropped(self, candidate: str) -> None:
        assert _grounded_tax_id(candidate) is None

    def test_a_greek_number_under_its_iso_code_rather_than_its_iva_prefix_is_dropped(self) -> None:
        """Greece's IVA prefix is ``EL``; a ``GR``-prefixed number is not an IVA number."""
        assert _grounded_tax_id("GR123456789") is None
        assert _grounded_tax_id("EL123456789") == "EL123456789"


class TestTextExtractionPrompt:
    """The prompt is the first line of defence, and it must not be Spain-shaped."""

    def test_it_instructs_null_rather_than_a_guess(self) -> None:
        prompt = build_text_field_extraction_prompt("ACME Ltd\nTotal 121,00")
        lowered = prompt.lower()

        assert "its value is null" in lowered
        assert "never substitute a plausible value for a missing one" in lowered

    def test_it_forbids_deriving_any_value(self) -> None:
        lowered = build_text_field_extraction_prompt("ACME Ltd").lower()

        for forbidden in ("calculate", "infer", "estimate", "guess"):
            assert forbidden in lowered
        assert "exactly as printed" in lowered

    def test_it_is_not_specific_to_spanish_invoices(self) -> None:
        """The prompt must not assume the document is Spanish.

        The assertion is on that PROPERTY, not on the absence of the word. The
        prompt now enumerates the rates Spain registers, so it names Spain --
        and it must, because the enumeration would otherwise be an unattributed
        list of numbers a model would read as universal. What it must never do
        is tell the model the DOCUMENT is Spanish, or present the Spanish list
        as the only admissible one, and both of those are asserted directly.
        """
        lowered = build_text_field_extraction_prompt("Rechnung Nr. 42").lower()

        assert "spanish invoice" not in lowered
        assert "may be written in any language" in lowered
        assert "may print a rate on neither list" in lowered
        assert "never move it onto a listed one" in lowered

    def test_it_carries_the_document_text_it_was_given(self) -> None:
        prompt = build_text_field_extraction_prompt("Facture 42\nTVA 20%")

        assert "Facture 42\nTVA 20%" in prompt

    def test_blank_text_refuses_rather_than_asking_a_model_to_read_nothing(self) -> None:
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            build_text_field_extraction_prompt("   \n\t ")
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.text_present"
        assert verdict.evidence[0].values == {"evidence_content_available": False}

        assert verdict.action is None
        assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION

    def test_pydantic_preserves_the_nested_typed_llm_validation_verdict(self) -> None:
        """The public request contract retains the producer error and verdict."""
        with pytest.raises(ValidationError) as raised:
            LLMRequest(prompt=" \t")

        errors = raised.value.errors(include_url=False)
        assert len(errors) == 1
        nested = errors[0]["ctx"]["error"]
        assert isinstance(nested, LLMValidationError)
        verdict = nested.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.request.prompt_nonempty"
        assert verdict.action is None
        assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
        assert verdict.evidence[0].values == {"request_prompt_nonempty": False}


class TestAuthoredResponseParsesAndGrounds:
    """A real model response string, through the real parser and grounder."""

    def test_a_full_response_grounds_into_the_expected_draft(self) -> None:
        response = json.dumps(
            {
                "supplier_tax_id": "IE9825613K",
                "invoice_number": "INV-2026-0142",
                "invoice_date": "10/03/2026",
                "taxable_base": "1.234,56",
                "iva_rate": "23",
                "iva_amount": "283,95",
                "grand_total": "1.518,51",
                "currency": "eur",
            },
        )

        draft = ground_extracted_fields(
            parse_invoice_extraction_response(response),
            raw_text_length=512,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert draft.supplier_tax_id == "IE9825613K"
        assert draft.invoice_number == "INV-2026-0142"
        assert draft.invoice_date == "2026-03-10"
        assert draft.taxable_base == Decimal("1234.56")
        assert draft.iva_rate == Decimal("23")
        assert draft.iva_amount == Decimal("283.95")
        assert draft.grand_total == Decimal("1518.51")
        assert draft.currency == "EUR"
        assert draft.raw_text_length == 512

    def test_a_null_field_the_document_never_printed_stays_none(self) -> None:
        response = json.dumps(
            {
                "supplier_tax_id": "DE811569869",
                "invoice_number": "R-9",
                "invoice_date": None,
                "taxable_base": "100.00",
                "iva_rate": None,
                "iva_amount": None,
                "grand_total": "100.00",
                "currency": None,
            },
        )

        draft = ground_extracted_fields(
            parse_invoice_extraction_response(response),
            raw_text_length=64,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert draft.supplier_tax_id == "DE811569869"
        assert draft.invoice_date is None
        assert draft.iva_rate is None
        assert draft.iva_amount is None
        assert draft.currency is None
        assert draft.taxable_base == Decimal("100.00")

    def test_a_chatty_model_wrapping_its_json_in_prose_still_parses(self) -> None:
        wrapped = f"Sure! Here you go:\n```json\n{json.dumps({'invoice_number': 'A-1'})}\n```"

        assert parse_invoice_extraction_response(wrapped).fields.invoice_number == "A-1"


class TestFabricatedValuesAreDroppedRatherThanTrusted:
    """One hallucinated value per field type, each dropped by its own authority."""

    @pytest.mark.parametrize(
        ("field", "fabricated"),
        [
            pytest.param("supplier_tax_id", "B1234567X", id="tax-id-invalid-check-character"),
            pytest.param("supplier_tax_id", "DE000", id="tax-id-wrong-shape-for-its-prefix"),
            pytest.param("invoice_date", "31/02/2026", id="date-that-does-not-exist"),
            pytest.param("invoice_date", "sometime in March", id="date-as-prose"),
            pytest.param("taxable_base", "about a thousand euros", id="amount-as-prose"),
            pytest.param("iva_amount", "NaN", id="amount-non-finite"),
            pytest.param("grand_total", "Infinity", id="amount-infinite"),
            pytest.param("iva_rate", "twenty-one percent", id="rate-as-words"),
            pytest.param("currency", "$", id="currency-as-a-symbol"),
            pytest.param("currency", "euros", id="currency-as-a-word"),
        ],
    )
    def test_a_hallucinated_value_grounds_to_none(self, field: str, fabricated: str) -> None:
        draft = ground_extracted_fields(
            _fields(**{field: fabricated}), raw_text_length=10, origin=FieldOrigin.TEXT_LAYER
        )

        assert getattr(draft, field) is None

    def test_an_ambiguous_amount_is_dropped_rather_than_read_a_hundredfold_light(self) -> None:
        """``1.234`` could be one thousand two hundred or one point two three."""
        draft = ground_extracted_fields(
            _fields(taxable_base="1.234"), raw_text_length=10, origin=FieldOrigin.TEXT_LAYER
        )

        assert draft.taxable_base is None

    def test_dropping_one_fabricated_field_does_not_discard_the_grounded_ones(self) -> None:
        draft = ground_extracted_fields(
            _fields(currency="US Dollars"), raw_text_length=10, origin=FieldOrigin.TEXT_LAYER
        )

        assert draft.currency is None
        assert draft.supplier_tax_id == _SPANISH_CIF
        assert draft.grand_total == Decimal("121.00")


class TestExtractorRequestShape:
    """The built request, asserted without dispatching it."""

    def test_an_explicit_model_rides_the_request_and_the_provenance_stamp(self) -> None:
        extractor = TextInvoiceFieldExtractor(model="some-text-model", settings=load_settings())

        assert extractor._build_request("Invoice 42").model_override == "some-text-model"
        assert extractor.decided_by.startswith("llm:local-text-extract:some-text-model:")


class TestExtractorPinsTheHostByDefault:
    """The reader pins LOCAL rather than inheriting whatever is configured.

    This class replaces two assertions that stated the OPPOSITE, and the
    inversion is the point rather than a tidy-up. They were
    ``test_the_request_pins_no_provider`` -- asserting
    ``request.provider_override is None`` -- and
    ``test_an_unpinned_model_says_so_rather_than_naming_one``, which asserted the
    provenance stamp read ``configured`` because no model was pinned.

    Both were written when carrying no override looked like neutrality. It is
    not neutral: ``cadrumo_llm_provider`` defaults to a cloud vendor, so pinning
    NOTHING meant a taxpayer's invoice text left the host by default, with no
    consent gate, no default-off posture, and nothing at the call site saying
    so. The tests asserted exactly the property that produced that exposure, and
    would have gone green again the moment anyone reverted the fix.

    They are inverted rather than deleted for that reason: a test that once
    forbade the right behaviour is worth keeping as a guard against its return.

    Split into its own class rather than renamed in place so the sibling
    heading stays honest -- the remaining case in
    :class:`TestExtractorRequestShape` really is about request shape, while
    these are about the host boundary.
    """

    def test_the_request_pins_the_local_provider(self) -> None:
        """Was: "pins no provider". Now: pins LOCAL, explicitly."""
        extractor = TextInvoiceFieldExtractor(settings=load_settings())

        request = extractor._build_request("Invoice 42\nTotal 121,00")

        assert request.provider_override is LLMProvider.LOCAL
        assert request.images == ()
        assert "Invoice 42" in request.prompt

    def test_the_default_read_names_its_local_model_rather_than_deferring(self) -> None:
        """Was: the stamp read ``configured`` because nothing was pinned.

        A stamp saying ``configured`` recorded that the reader did not know
        which model had read the document -- which is precisely the state that
        made the off-host default invisible in provenance.
        """
        extractor = TextInvoiceFieldExtractor(settings=load_settings())

        assert extractor._build_request("Invoice 42").model_override is not None
        assert not extractor.decided_by.startswith("llm:local-text-extract:configured:")

    def test_a_cloud_provider_naming_no_model_is_refused(self) -> None:
        """A refusal, not merely a default, so configuration cannot silently bypass it.

        Mirrors the vision reader's guard. A pin can be overridden; a refusal
        cannot be reached around by setting an environment variable, which is
        what makes this the stronger half of the fix.
        """
        with pytest.raises(LLMConfigError) as raised:
            TextInvoiceFieldExtractor(provider=LLMProvider.ANTHROPIC, settings=load_settings())
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.off_host_model.named"
        assert verdict.evidence[0].values == {
            "off_host_model_named": False,
            "provider": LLMProvider.ANTHROPIC.value,
        }

    def test_an_explicitly_named_cloud_provider_and_model_is_still_honoured(self) -> None:
        """Positive control, and it protects a sanctioned route.

        The measurement corpus is public, synthetic and explicitly cleared for a
        cloud engine. A fix that made every off-host read impossible would break
        that, and a refusal-only suite would not notice -- a reader that refused
        everything satisfies the case above.
        """
        extractor = TextInvoiceFieldExtractor(
            provider=LLMProvider.ANTHROPIC,
            model="claude-test-model",
            settings=load_settings(),
        )

        request = extractor._build_request("Invoice 42")

        assert request.provider_override is LLMProvider.ANTHROPIC
        assert request.model_override == "claude-test-model"
