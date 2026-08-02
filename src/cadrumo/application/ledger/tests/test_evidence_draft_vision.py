"""Real-behaviour tests for the on-host vision fallback invoice-field extractor.

Covers the parsing/grounding primitives directly (adversarial JSON, hallucinated
tax ids, unparsable dates/amounts) and the full transport against a real loopback
Ollama HTTP server (no mocks) -- exactly the harness
``_llm_vision_evidence_support._run_against_loopback_ollama`` already uses for the
classification vision path.

See Also:
    :class:`~application.ledger._evidence_draft_vision.LocalVisionInvoiceFieldExtractor`
        On-host Ollama transport exercised through the loopback server.
    :func:`~application.ledger._evidence_draft_vision.parse_vision_extraction_response`
        JSON-object recovery and strict schema boundary covered by adversarial
        response cases.
    :func:`~application.ledger._evidence_draft_vision._ground_extracted_fields`
        Grounded re-validation step that rejects hallucinated identifiers and
        unparsable values.
    :func:`~application.ledger.extract_invoice_draft_from_evidence`
        Text-layer-first orchestration path that routes scan-only evidence to
        this local vision fallback.
"""

from __future__ import annotations

import base64
import json
from decimal import Decimal

import pytest

from ....core.config import load_settings
from ....core.decimal import coerce_finite_european_decimal
from ....tests.secure_sql import TestRuntimeProfile
from .._evidence import PurchaseInvoiceEvidenceInputError
from .._evidence_draft import InvoiceDraft
from .._evidence_draft_vision import (
    LocalVisionInvoiceFieldExtractor,
    _ground_extracted_fields,
    _VisionExtractedFields,
    extract_invoice_fields_from_images,
    parse_vision_extraction_response,
)
from ._llm_vision_evidence_support import _json_array, _json_object, _png_image, _run_against_loopback_ollama
from ._llm_vision_evidence_support import profile as profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
__all__ = ["profile"]

# A real Spanish CIF (AEAT-checksum-valid: leading letter B, 7 digits, computed
# control character), mirroring the fixture used by the text-layer draft tests.
_SUPPLIER_CIF = "B12345674"


def _extraction_json(**overrides: str | None) -> str:
    payload: dict[str, str | None] = {
        "supplier_tax_id": _SUPPLIER_CIF,
        "invoice_number": "2026-0142",
        "invoice_date": "10/03/2026",
        "taxable_base": "100,00",
        "iva_rate": "21",
        "iva_amount": "21,00",
        "grand_total": "121,00",
    }
    payload.update(overrides)
    return json.dumps(payload)


class TestParseVisionExtractionResponse:
    """Unit tests for the JSON-object recovery and schema validation step."""

    def test_parses_a_clean_json_object(self) -> None:
        parsed = parse_vision_extraction_response(_extraction_json())
        assert parsed.supplier_tax_id == _SUPPLIER_CIF
        assert parsed.taxable_base == "100,00"

    def test_tolerates_surrounding_prose(self) -> None:
        """A chatty local model wrapping the JSON in prose still parses."""
        wrapped = f"Here is the extracted data:\n{_extraction_json()}\nLet me know if you need more."
        parsed = parse_vision_extraction_response(wrapped)
        assert parsed.invoice_number == "2026-0142"

    def test_no_json_object_refuses(self) -> None:
        with pytest.raises(PurchaseInvoiceEvidenceInputError, match="no parsable JSON object"):
            parse_vision_extraction_response("I could not read the image clearly.")

    def test_schema_violation_refuses(self) -> None:
        """A non-string field value (e.g. a nested object) fails strict schema validation."""
        with pytest.raises(PurchaseInvoiceEvidenceInputError, match="schema validation"):
            parse_vision_extraction_response('{"supplier_tax_id": {"nested": "object"}}')


class TestGroundExtractedFields:
    """Unit tests for the re-validation step: every field must pass its grounded validator."""

    def test_valid_fields_all_ground(self) -> None:
        fields = _VisionExtractedFields.model_validate_json(_extraction_json())
        draft = _ground_extracted_fields(fields, raw_text_length=42)
        assert draft.supplier_tax_id == _SUPPLIER_CIF
        assert draft.invoice_number == "2026-0142"
        assert draft.invoice_date == "2026-03-10"
        assert draft.taxable_base == 100
        assert draft.iva_rate == 21
        assert draft.iva_amount == 21
        assert draft.grand_total == 121
        assert draft.raw_text_length == 42

    def test_hallucinated_tax_id_is_dropped_not_trusted(self) -> None:
        """A checksum-invalid tax id the model 'read' is rejected, never passed through."""
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(supplier_tax_id="A0000000A"))
        draft = _ground_extracted_fields(fields, raw_text_length=10)
        assert draft.supplier_tax_id is None

    def test_unparsable_date_is_dropped(self) -> None:
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(invoice_date="not-a-date"))
        draft = _ground_extracted_fields(fields, raw_text_length=10)
        assert draft.invoice_date is None

    def test_iso8601_date_also_grounds(self) -> None:
        """A model that normalises the printed day-first date to ISO-8601 still grounds."""
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(invoice_date="2026-03-10"))
        draft = _ground_extracted_fields(fields, raw_text_length=10)
        assert draft.invoice_date == "2026-03-10"

    def test_unparsable_amount_is_dropped(self) -> None:
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(taxable_base="lots of money"))
        draft = _ground_extracted_fields(fields, raw_text_length=10)
        assert draft.taxable_base is None

    def test_all_null_fields_ground_to_an_empty_draft(self) -> None:
        fields = _VisionExtractedFields()
        draft = _ground_extracted_fields(fields, raw_text_length=0)
        assert draft.supplier_tax_id is None
        assert draft.invoice_number is None
        assert draft.invoice_date is None
        assert draft.taxable_base is None
        assert draft.iva_rate is None
        assert draft.iva_amount is None
        assert draft.grand_total is None
        assert draft.currency is None

    def test_printed_currency_code_grounds(self) -> None:
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(currency="usd"))
        draft = _ground_extracted_fields(fields, raw_text_length=10)
        assert draft.currency == "USD"

    def test_currency_symbol_is_dropped_not_guessed(self) -> None:
        """A bare symbol cannot ground a currency: '$' is USD, CAD, AUD and MXN."""
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(currency="$"))
        draft = _ground_extracted_fields(fields, raw_text_length=10)
        assert draft.currency is None

    def test_absent_currency_stays_none_rather_than_defaulting_to_euro(self) -> None:
        # The draft must not assert a currency the document never showed; euro
        # is applied (if at all) at confirm time, where the operator can override.
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(currency=None))
        draft = _ground_extracted_fields(fields, raw_text_length=10)
        assert draft.currency is None


class TestLocalVisionInvoiceFieldExtractor:
    """Real-behaviour tests against a loopback Ollama HTTP server. No mocks."""

    def test_extracts_grounded_fields_from_a_real_vision_response(self, profile: TestRuntimeProfile) -> None:
        _ = profile
        images = (base64.b64encode(_png_image()).decode("ascii"),)

        def _call() -> InvoiceDraft:
            extractor = LocalVisionInvoiceFieldExtractor(model="qwen-test")
            return extractor.extract(evidence_images=images)

        observed, draft = _run_against_loopback_ollama(_extraction_json(), _call)

        assert draft.supplier_tax_id == _SUPPLIER_CIF
        assert draft.invoice_number == "2026-0142"
        assert draft.invoice_date == "2026-03-10"
        assert draft.taxable_base == 100
        assert draft.iva_rate == 21
        assert draft.iva_amount == 21
        assert draft.grand_total == 121

        # The base64 image genuinely rode the Ollama request payload.
        body = _json_object(observed["body"])
        messages = _json_array(body["messages"])
        user_message = _json_object(messages[-1])
        assert user_message["images"] == list(images)

    def test_decided_by_names_the_model(self) -> None:
        extractor = LocalVisionInvoiceFieldExtractor(model="qwen2.5vl:3b", settings=load_settings())
        assert extractor.decided_by == "llm:local-vision:qwen2.5vl:3b"

    def test_partial_fields_ground_and_missing_fields_stay_none(self, profile: TestRuntimeProfile) -> None:
        """A real vision response that only reads some fields never fabricates the rest."""
        _ = profile
        images = (base64.b64encode(_png_image()).decode("ascii"),)
        partial = json.dumps(
            {
                "supplier_tax_id": None,
                "invoice_number": None,
                "invoice_date": None,
                "taxable_base": "250,00",
                "iva_rate": None,
                "iva_amount": None,
                "grand_total": "250,00",
            },
        )

        def _call() -> InvoiceDraft:
            return extract_invoice_fields_from_images(images, model="qwen-test")

        _observed, draft = _run_against_loopback_ollama(partial, _call)
        assert draft.taxable_base == 250
        assert draft.grand_total == 250
        assert draft.supplier_tax_id is None
        assert draft.invoice_number is None


class TestGroundedAmountsShareTheCanonicalDecimalAuthority:
    """Vision grounding reads amounts exactly as the canonical helper does.

    The grounding step stripped every dot as a thousands separator, so an
    already dot-decimal transcription was multiplied by a hundred, and it
    admitted ``NaN``/``Infinity`` as filing amounts. Both paths now route
    through :func:`~core.decimal.coerce_finite_european_decimal`.
    """

    @pytest.mark.parametrize(
        ("transcribed", "expected"),
        [
            ("1234.56", Decimal("1234.56")),
            ("259.26", Decimal("259.26")),
            ("1493.82", Decimal("1493.82")),
            ("1.234,56", Decimal("1234.56")),
            ("1234,56", Decimal("1234.56")),
            ("100,00", Decimal("100")),
        ],
        ids=["dot-decimal", "dot-decimal-small", "dot-decimal-total", "es-thousands", "comma", "canonical"],
    )
    def test_dot_and_comma_decimals_keep_their_scale(self, transcribed: str, expected: Decimal) -> None:
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(taxable_base=transcribed))
        draft = _ground_extracted_fields(fields, raw_text_length=42)

        assert draft.taxable_base == expected
        assert draft.taxable_base == coerce_finite_european_decimal(transcribed)

    @pytest.mark.parametrize("transcribed", ["NaN", "Infinity", "-Infinity", "nan"])
    def test_non_finite_amounts_are_dropped_not_grounded(self, transcribed: str) -> None:
        fields = _VisionExtractedFields.model_validate_json(_extraction_json(grand_total=transcribed))
        draft = _ground_extracted_fields(fields, raw_text_length=42)

        assert draft.grand_total is None

    @pytest.mark.parametrize(
        "transcribed",
        ["1234.56", "1.234,56", "1234,56", "NaN", "Infinity", "not-a-number"],
    )
    def test_every_amount_field_agrees_with_the_canonical_helper(self, transcribed: str) -> None:
        """No amount field may read a transcription differently from any other."""
        fields = _VisionExtractedFields.model_validate_json(
            _extraction_json(
                taxable_base=transcribed,
                iva_amount=transcribed,
                grand_total=transcribed,
            ),
        )
        draft = _ground_extracted_fields(fields, raw_text_length=42)

        expected = coerce_finite_european_decimal(transcribed)
        assert draft.taxable_base == expected
        assert draft.iva_amount == expected
        assert draft.grand_total == expected
