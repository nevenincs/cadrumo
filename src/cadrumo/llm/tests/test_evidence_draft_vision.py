"""Real-behaviour tests for the on-host vision TRANSCRIBER and the shared grounding it feeds.

Covers the parsing/grounding primitives directly (adversarial JSON, hallucinated
tax ids, unparsable dates/amounts) and the full transport against a real loopback
Ollama HTTP server (no mocks) -- exactly the harness
``_llm_vision_evidence_support._run_against_loopback_ollama`` already uses for the
classification vision path.

The vision reader's own tests assert what it must NOT do as much as what it
does. It is stage one: pixels to text. A test proving it returns fields would be
proving the collapse this refit removed, so the assertions here are that it
emits a transcription, that its prompt names no invoice field, and that its
module reaches no field-grounding symbol at all.

See Also:
    :class:`~llm._evidence_draft_vision.LocalVisionDocumentTranscriber`
        On-host Ollama transport exercised through the loopback server.
    :func:`~llm._invoice_field_grounding.parse_invoice_extraction_response`
        JSON-object recovery and strict schema boundary covered by adversarial
        response cases.
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        Grounded re-validation step that rejects hallucinated identifiers and
        unparsable values.
    :func:`~application.ledger.evidence_draft.extract_invoice_draft_from_evidence`
        Text-layer-first orchestration path that routes scan-only evidence to
        this local vision fallback.
"""

from __future__ import annotations

import ast
import base64
import importlib
import json
import pathlib
import re
from decimal import Decimal

import pytest

from ...application.ledger.document_transcription import DocumentTranscription
from ...application.ledger.evidence import PurchaseInvoiceEvidenceInputError
from ...core import FieldOrigin, ImageMediaType
from ...core.config import load_settings
from ...core.decimal import coerce_finite_european_decimal
from ...tests.llm_vision_evidence_support import (
    _json_array,
    _json_object,
    _png_image,
    _run_against_loopback_ollama,
)
from .._evidence_draft_vision import (
    VISION_TRANSCRIPTION_PROMPT,
    LocalVisionDocumentTranscriber,
    transcribe_document_images,
)
from .._invoice_extraction_prompt import build_invoice_extraction_prompt, default_extraction_period
from .._invoice_field_contract import anchor_key_for_field, role_evidence_key_for_field
from .._invoice_field_grounding import (
    ExtractedFieldAnchors,
    ExtractedInvoiceFields,
    ExtractedInvoiceResponse,
    ExtractedRoleEvidence,
    ground_extracted_fields,
    parse_invoice_extraction_response,
)
from .._models import MultimodalImageInput

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A real Spanish CIF (AEAT-checksum-valid: leading letter B, 7 digits, computed
# control character), mirroring the fixture used by the text-layer draft tests.
_SUPPLIER_CIF = "B12345674"

#: Content address of the SOURCE bytes a transcription is keyed by.
_SOURCE_SHA = "b" * 64

#: A page as a transcription-only reader returns it: printed forms intact,
#: headings kept, no JSON and no field names.
_TRANSCRIBED_PAGE = """FACTURA 2026-0142
Proveedor: EJEMPLO SL B12345674
Fecha: 10/03/2026
Base imponible 100,00 EUR
IVA (21%) 21,00 EUR
TOTAL 121,00 EUR
"""


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
        parsed = parse_invoice_extraction_response(_extraction_json()).fields
        assert parsed.supplier_tax_id == _SUPPLIER_CIF
        assert parsed.taxable_base == "100,00"

    def test_tolerates_surrounding_prose(self) -> None:
        """A chatty local model wrapping the JSON in prose still parses."""
        wrapped = f"Here is the extracted data:\n{_extraction_json()}\nLet me know if you need more."
        parsed = parse_invoice_extraction_response(wrapped).fields
        assert parsed.invoice_number == "2026-0142"

    def test_no_json_object_refuses(self) -> None:
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            parse_invoice_extraction_response("I could not read the image clearly.")
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.response_json_object"
        assert verdict.evidence[0].values == {
            "evidence_response_json_object": False,
            "evidence_response_parseable": False,
        }

    def test_schema_violation_refuses(self) -> None:
        """A non-string field value (e.g. a nested object) fails strict schema validation."""
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            parse_invoice_extraction_response('{"supplier_tax_id": {"nested": "object"}}')
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.response_schema_valid"
        assert verdict.evidence[0].values == {
            "evidence_response_schema_valid": False,
            "evidence_response_validation_error_type": "ValidationError",
        }


class TestGroundExtractedFields:
    """Unit tests for the re-validation step: every field must pass its grounded validator."""

    def test_valid_fields_all_ground(self) -> None:
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json()), anchors=ExtractedFieldAnchors()
        )
        draft = ground_extracted_fields(fields, raw_text_length=42, origin=FieldOrigin.VISION)
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
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(supplier_tax_id="A0000000A")),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)
        assert draft.supplier_tax_id is None

    def test_unparsable_date_is_dropped(self) -> None:
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(invoice_date="not-a-date")),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)
        assert draft.invoice_date is None

    def test_iso8601_date_also_grounds(self) -> None:
        """A model that normalises the printed day-first date to ISO-8601 still grounds."""
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(invoice_date="2026-03-10")),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)
        assert draft.invoice_date == "2026-03-10"

    def test_unparsable_amount_is_dropped(self) -> None:
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(taxable_base="lots of money")),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)
        assert draft.taxable_base is None

    @pytest.mark.parametrize(
        "printed",
        (
            pytest.param("1.234", id="one-thousand-two-hundred-and-thirty-four"),
            pytest.param("12.500", id="twelve-thousand-five-hundred"),
            pytest.param("1.000", id="one-thousand"),
        ),
    )
    def test_a_two_way_readable_amount_is_dropped_not_read_as_cents(self, printed: str) -> None:
        """A supplier's ``1.234`` is dropped rather than stored as one euro twenty-three.

        The model transcribes what the invoice printed, so the convention in
        the string is the SUPPLIER'S. A Spanish supplier writes one thousand
        two hundred and thirty-four euros as ``1.234``; read as a decimal that
        is a taxable base a thousandfold light, bound for Modelo 303/390.

        Dropping is what makes it safe: the confirm path treats a missing
        taxable base as a hard refusal naming ``--taxable-base``, so the
        operator is asked. A guessed figure would be minted instead, because
        confirm re-extracts and uses the extracted value for every field the
        operator did not explicitly override.
        """
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(taxable_base=printed)),
            anchors=ExtractedFieldAnchors(),
        )

        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)

        assert draft.taxable_base is None

    @pytest.mark.parametrize(
        ("printed", "expected"),
        (
            pytest.param("1.234,56", Decimal("1234.56"), id="spanish-grouped-with-comma"),
            pytest.param("100,00", Decimal("100.00"), id="spanish-comma-decimal"),
            pytest.param("1.234.567,89", Decimal("1234567.89"), id="spanish-fully-grouped"),
            pytest.param("1234.56", Decimal("1234.56"), id="dot-decimal"),
            pytest.param("850", Decimal("850"), id="whole-euros-no-separator"),
        ),
    )
    def test_every_unambiguous_printed_amount_still_grounds(self, printed: str, expected: Decimal) -> None:
        """The drop is narrow: every spelling carrying its own evidence still reads.

        These are the forms a Spanish invoice actually prints, and all of them
        already worked -- which is exactly why they prove nothing on their own
        and are asserted alongside the dropped cases rather than instead of
        them.
        """
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(taxable_base=printed)),
            anchors=ExtractedFieldAnchors(),
        )

        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)

        assert draft.taxable_base == expected

    def test_all_null_fields_ground_to_an_empty_draft(self) -> None:
        fields = ExtractedInvoiceResponse(fields=ExtractedInvoiceFields(), anchors=ExtractedFieldAnchors())
        draft = ground_extracted_fields(fields, raw_text_length=0, origin=FieldOrigin.VISION)
        assert draft.supplier_tax_id is None
        assert draft.invoice_number is None
        assert draft.invoice_date is None
        assert draft.taxable_base is None
        assert draft.iva_rate is None
        assert draft.iva_amount is None
        assert draft.grand_total is None
        assert draft.currency is None

    def test_printed_currency_code_grounds(self) -> None:
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(currency="usd")),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)
        assert draft.currency == "USD"

    def test_currency_symbol_is_dropped_not_guessed(self) -> None:
        """A bare symbol cannot ground a currency: '$' is USD, CAD, AUD and MXN."""
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(currency="$")),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)
        assert draft.currency is None

    def test_absent_currency_stays_none_rather_than_defaulting_to_euro(self) -> None:
        # The draft must not assert a currency the document never showed; euro
        # is applied (if at all) at confirm time, where the operator can override.
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(currency=None)),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.VISION)
        assert draft.currency is None


class TestLocalVisionDocumentTranscriber:
    """Real-behaviour tests against a loopback Ollama HTTP server. No mocks."""

    def test_transcribes_a_real_vision_response_into_the_stage_one_artefact(
        self,
    ) -> None:
        """Text in, text out, stamped with the reader that produced it."""
        images = (MultimodalImageInput.from_base64(base64.b64encode(_png_image()).decode("ascii"), ImageMediaType.PNG),)

        def _call() -> DocumentTranscription:
            transcriber = LocalVisionDocumentTranscriber(model="qwen-test")
            return transcriber.transcribe(evidence_images=images, source_content_sha256=_SOURCE_SHA)

        observed, transcription = _run_against_loopback_ollama(_TRANSCRIBED_PAGE, _call)

        assert transcription.text == _TRANSCRIBED_PAGE.strip()
        assert transcription.page_count == 1
        assert transcription.source_content_sha256 == _SOURCE_SHA
        assert transcription.transcriber.origin is FieldOrigin.VISION
        assert "qwen-test" in transcription.transcriber.name

        # The base64 image genuinely rode the Ollama request payload.
        body = _json_object(observed["body"])
        messages = _json_array(body["messages"])
        user_message = _json_object(messages[-1])
        assert user_message["images"] == [image.base64_data for image in images]

    def test_the_prompt_that_rode_the_request_asks_for_no_invoice_field(
        self,
    ) -> None:
        """Stage one must not be told what to look for.

        Asserted on the payload that actually left the process rather than on
        the constant, because the constant proves what was written and this
        proves what was sent. A model handed field names finds them, and a
        transcription steered toward an expected answer is no longer an
        independent reading for the anchor check to run against.
        """
        images = (MultimodalImageInput.from_base64(base64.b64encode(_png_image()).decode("ascii"), ImageMediaType.PNG),)

        def _call() -> DocumentTranscription:
            return transcribe_document_images(images, source_content_sha256=_SOURCE_SHA, model="qwen-test")

        observed, _transcription = _run_against_loopback_ollama(_TRANSCRIBED_PAGE, _call)
        body = _json_object(observed["body"])
        messages = _json_array(body["messages"])
        user_message = _json_object(messages[-1])
        content = user_message["content"]
        assert isinstance(content, str)

        for field_name in ExtractedInvoiceFields.model_fields:
            assert field_name not in content, f"the transcription prompt names the invoice field {field_name!r}"
        assert anchor_key_for_field("taxable_base") not in content

    def test_an_empty_model_reply_refuses_rather_than_reporting_a_blank_document(
        self,
    ) -> None:
        """A reader that returned nothing is not a document that says nothing.

        Passing an empty transcription on would hand the semantic stage a
        document it would honestly report as carrying no fields, converting a
        reader failure into a confident statement about the taxpayer's paper.
        """
        images = (MultimodalImageInput.from_base64(base64.b64encode(_png_image()).decode("ascii"), ImageMediaType.PNG),)

        def _call() -> DocumentTranscription:
            return transcribe_document_images(images, source_content_sha256=_SOURCE_SHA, model="qwen-test")

        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            _run_against_loopback_ollama("   \n  ", _call)
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.transcription_nonempty"
        assert verdict.evidence[0].values == {"transcription_nonempty": False}

    def test_no_pages_refuses_without_dispatching(self) -> None:
        """Model-free: an empty page tuple is caught before any transport."""
        transcriber = LocalVisionDocumentTranscriber(model="qwen-test", settings=load_settings())

        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            transcriber.transcribe(evidence_images=(), source_content_sha256=_SOURCE_SHA)
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.images_present"
        assert verdict.evidence[0].values == {"evidence_image_count": 0, "evidence_images_present": False}

    def test_the_transcriber_identity_folds_the_prompt_version(self) -> None:
        """Two prompts are two readings of the same pixels, so the cache must tell them apart."""
        transcriber = LocalVisionDocumentTranscriber(model="qwen2.5vl:3b", settings=load_settings())
        identity = transcriber.transcriber_identity

        assert identity.origin is FieldOrigin.VISION
        assert identity.name.endswith("qwen2.5vl:3b")
        assert identity.revision.startswith("prompt-v")


class TestTheVisionStageInterpretsNothing:
    """Stage one performs NO field interpretation, asserted structurally and model-free."""

    def test_the_transcription_module_reaches_no_field_grounding_symbol(self) -> None:
        """Walk the module's AST for any name the interpretation stage owns.

        AST rather than a substring scan of the source: this module's own prose
        discusses the interpretation stage it no longer performs, so a text
        search would match its docstring and report a violation that is not
        there -- and, tuned to avoid that, would just as easily miss a real one.
        The walk sees imported and referenced NAMES, never prose.
        """
        module = importlib.import_module("cadrumo.llm._evidence_draft_vision")
        source = pathlib.Path(str(module.__file__)).read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden = {
            "ground_extracted_fields",
            "parse_invoice_extraction_response",
            "ExtractedInvoiceResponse",
            "ExtractedInvoiceFields",
            "INVOICE_FIELD_CONTRACTS",
            "build_invoice_extraction_prompt",
            "InvoiceDraft",
        }
        referenced = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        referenced |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                referenced |= {alias.name for alias in node.names}

        offending = sorted(forbidden & referenced)
        assert not offending, (
            "the vision stage must transcribe and interpret nothing; it reaches the field-"
            f"interpretation symbols {offending}"
        )

    def test_the_transcription_prompt_names_no_field_and_asks_for_no_json(self) -> None:
        """Model-free property of the prompt constant itself."""
        for field_name in ExtractedInvoiceFields.model_fields:
            assert field_name not in VISION_TRANSCRIPTION_PROMPT

        assert "JSON" not in VISION_TRANSCRIPTION_PROMPT
        assert "{" not in VISION_TRANSCRIPTION_PROMPT

    def test_the_transcription_prompt_demands_verbatim_printed_forms(self) -> None:
        """The rules the downstream anchor check depends on are actually stated.

        Each of these protects a specific downstream property: verbatim
        characters keep the anchor searchable, unmodified numbers keep the
        printed separator that decides a decimal reading, headings keep the role
        evidence an identity resolves on, and the illegible marker keeps an
        unreadable glyph from being replaced by a plausible one that would
        anchor perfectly against itself.
        """
        assert "EXACTLY as printed" in VISION_TRANSCRIPTION_PROMPT
        assert "Do not convert, round, reformat or normalise" in VISION_TRANSCRIPTION_PROMPT
        assert "Keep every heading and label" in VISION_TRANSCRIPTION_PROMPT
        assert "[?]" in VISION_TRANSCRIPTION_PROMPT


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
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(taxable_base=transcribed)),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=42, origin=FieldOrigin.VISION)

        assert draft.taxable_base == expected
        assert draft.taxable_base == coerce_finite_european_decimal(transcribed)

    @pytest.mark.parametrize("transcribed", ["NaN", "Infinity", "-Infinity", "nan"])
    def test_non_finite_amounts_are_dropped_not_grounded(self, transcribed: str) -> None:
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(_extraction_json(grand_total=transcribed)),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=42, origin=FieldOrigin.VISION)

        assert draft.grand_total is None

    @pytest.mark.parametrize(
        "transcribed",
        ["1234.56", "1.234,56", "1234,56", "NaN", "Infinity", "not-a-number"],
    )
    def test_every_amount_field_agrees_with_the_canonical_helper(self, transcribed: str) -> None:
        """No amount field may read a transcription differently from any other."""
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields.model_validate_json(
                _extraction_json(
                    taxable_base=transcribed,
                    iva_amount=transcribed,
                    grand_total=transcribed,
                ),
            ),
            anchors=ExtractedFieldAnchors(),
        )
        draft = ground_extracted_fields(fields, raw_text_length=42, origin=FieldOrigin.VISION)

        expected = coerce_finite_european_decimal(transcribed)
        assert draft.taxable_base == expected
        assert draft.iva_amount == expected
        assert draft.grand_total == expected


class TestFieldExtractionPromptShowsWellFormedJson:
    """The example object the prompt shows must be the object it asks for.

    The prompt is a plain string that is never passed through ``str.format``,
    so a doubled brace is not an escape -- it reaches the model verbatim. The
    template shipped ``{{``/``}}`` for a while, which showed the model a
    malformed skeleton immediately after instructing it to "Return ONLY one
    JSON object": the model then either echoes the doubling, in which case
    :func:`~llm._invoice_field_grounding.parse_invoice_extraction_response`
    rejects the response outright, or silently repairs it, in which case the
    read depends on that recovery rather than on the instruction.

    This gate is deliberately model-free: it asserts a property of the prompt
    text itself, so it holds on a machine that can run no vision model at all.
    """

    def test_template_parses_as_json_carrying_exactly_the_schema_keys(self) -> None:
        """The shown skeleton is valid JSON whose keys are the schema's keys."""
        compiled = build_invoice_extraction_prompt(period=default_extraction_period()).text
        template = compiled[compiled.index("{") : compiled.rindex("}") + 1]
        # The prompt documents each value as a `<string or null, ...>` annotation
        # rather than a literal; substituting null leaves the SHAPE under test.
        skeleton = re.sub(r"<[^>]*>", "null", template, flags=re.DOTALL)

        # Each field is asked for twice: the value in its declared form, and the
        # anchor holding the form the document printed. Both halves are the
        # schema, so both are asserted here.
        assert json.loads(skeleton) == dict.fromkeys(
            key
            for field_name in ExtractedInvoiceFields.model_fields
            for key in (
                field_name,
                anchor_key_for_field(field_name),
                # An identity field is asked a third question -- what assigns
                # it to a party -- because two identifiers on one invoice have
                # the same printed shape and an anchor cannot tell them apart.
                *(
                    (role_evidence_key_for_field(field_name),)
                    if field_name in ExtractedRoleEvidence.model_fields
                    else ()
                ),
            )
        )

    def test_prompt_carries_no_doubled_brace(self) -> None:
        """No ``{{``/``}}`` survives into the COMPILED text the model receives."""
        compiled = build_invoice_extraction_prompt(period=default_extraction_period()).text
        assert "{{" not in compiled
        assert "}}" not in compiled
