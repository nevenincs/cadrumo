"""Gates for the per-field anchor: what the model points at, and what nobody checked.

Every test here is MODEL-FREE and NETWORK-FREE by construction. Each asserts on
compiled prompt text, on registry values, or on a canned response string put
through the real parser and the real grounder. Nothing builds a transport, so
none of this can reach a provider even if one were configured.

Three properties are under gate, and they are separable:

**A value travels with the printed form it came from.** Anti-fabrication is
structural rather than instructional: a later stage can only check a value
against the document if the reader said which substring it read. The prompt asks
for both, the parser keeps both, and every populated field reaches the draft with
an envelope carrying its anchor.

**Anchor and value stay distinct.** ``IVA (21%)`` yields the value ``21`` and the
anchor ``21%``. Where the two collapse to one string a downstream parse check
compares a value against itself and establishes nothing, so keeping them apart is
what gives the check something to do.

**The Spanish rate enumeration is a hint, not a menu.** The prompt lists the
registered Spanish rates so a small model SELECTS instead of inferring, which
creates its own hazard: a model shown the Spanish list and handed a German
invoice may snap a printed ``19`` onto ``21``. A prompt sentence forbidding that
is prose; the gate here drives real product code and proves the figure survives.

See Also:
    :class:`~application.ledger.evidence_draft.FieldProvenance`
        The envelope every populated field now carries.
    :class:`~core.FieldGroundingOutcome`
        The outcome axis this stage deliberately under-claims on.
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        The grounding derivation under test.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest

from ...application.ledger.evidence_draft import FieldProvenance, InvoiceDraft
from ...application.ledger.evidence import PurchaseInvoiceEvidenceInputError
from ...core import FieldGroundingOutcome, FieldOrigin, Period
from cadrumo.domain.calculations.registry.authority import bundled_authority
from ...domain.iva import EUMemberState, load_iva_rate_table
from .._invoice_extraction_prompt import (
    INVOICE_EXTRACTION_PROMPT_ID,
    INVOICE_EXTRACTION_PROMPT_VERSION,
    PROMPT_TEMPLATE,
    build_invoice_extraction_prompt,
    invoice_extraction_prompt_registry,
    template_numeric_literals,
)
from .._invoice_field_contract import (
    ANCHOR_KEY_SUFFIX,
    INVOICE_FIELD_CONTRACTS,
    anchor_key_for_field,
    role_evidence_key_for_field,
)
from .._invoice_field_grounding import (
    ExtractedFieldAnchors,
    ExtractedInvoiceFields,
    ExtractedInvoiceResponse,
    ground_extracted_fields,
    parse_invoice_extraction_response,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ANNUAL_2024 = Period.from_year_and_code(2024, "0A")
_ANNUAL_2026 = Period.from_year_and_code(2026, "0A")

# AEAT-checksum-valid Spanish CIF, so the identifier field survives grounding and
# its envelope is about a value rather than about a drop.
_SPANISH_CIF = "B12345674"

# The BILLED party, deliberately a different checksum-valid identifier from the
# issuer's. A fixture reusing one id for both parties cannot fail when the two
# sides are confused, which is the only failure these fields exist to catch.
_SPANISH_CUSTOMER_NIF = "12345678Z"

#: A Spanish invoice as a model would report it: values in their declared forms,
#: anchors in the forms the page prints. Deliberately NOT byte-identical pairs --
#: an anchor equal to its value makes the downstream parse check vacuous.
_SPANISH_INVOICE: dict[str, str | None] = {
    "supplier_tax_id": _SPANISH_CIF,
    # The name the identifier belongs to, printed as the document prints it --
    # accented and with its legal-form suffix, because a fixture spelled in
    # ASCII cannot fail when a reader silently folds diacritics.
    "supplier_name": "Ferretería Insular S.L.",
    # Las Palmas: a Canarian prefix, deliberately not a peninsular one. A
    # fixture whose two parties both sit on the mainland cannot fail when the
    # territorial reading is dropped, because the mainland is what a lost code
    # degrades to everywhere it is read carelessly.
    "supplier_postal_code": "35001",
    # Printed as a NAME in the document's language, never as "ES". A code here
    # would mean the reader translated, which is the one thing the country field
    # exists to avoid asking of it.
    "supplier_country": "España",
    "customer_tax_id": _SPANISH_CUSTOMER_NIF,
    "customer_name": "Talleres Mayor S.A.",
    "customer_postal_code": "28013",
    "customer_country": "España",
    "invoice_number": "2026-0142",
    "invoice_date": "10/03/2026",
    "taxable_base": "1.200,00",
    "iva_rate": "21",
    "iva_amount": "252,00",
    "retencion_rate": "15",
    "retencion_amount": "180,00",
    "grand_total": "1.452,00",
    "regime_legend": "régimen especial del criterio de caja",
    "currency": "EUR",
}
_SPANISH_ANCHORS: dict[str, str | None] = {
    "supplier_tax_id": f"CIF: {_SPANISH_CIF}",
    # The printed heading carries the role, so the anchor is not byte-identical
    # to the name and a value-versus-anchor comparison stays meaningful.
    "supplier_name": "Emisor: Ferretería Insular S.L.",
    "supplier_postal_code": "35001 Las Palmas de Gran Canaria",
    # Deliberately not byte-identical to the value, for the reason every anchor
    # here is not: an anchor equal to its value makes the downstream parse check
    # compare a value to itself.
    "supplier_country": "35001 Las Palmas de Gran Canaria, España",
    "customer_tax_id": f"NIF cliente: {_SPANISH_CUSTOMER_NIF}",
    "customer_name": "Cliente: Talleres Mayor S.A.",
    "customer_postal_code": "Calle Mayor 3, 28013 Madrid",
    "customer_country": "Calle Mayor 3, 28013 Madrid, España",
    "invoice_number": "Factura n.º 2026-0142",
    "invoice_date": "10/03/2026",
    "taxable_base": "1.200,00 €",
    "iva_rate": "21%",
    "iva_amount": "252,00 €",
    "retencion_rate": "-15%",
    "retencion_amount": "-180,00 €",
    "grand_total": "1.452,00 €",
    "regime_legend": "Factura acogida al régimen especial del criterio de caja",
    "currency": "€",
}


def _canned_response(values: dict[str, str | None], anchors: dict[str, str | None]) -> str:
    """Render one model reply exactly as the prompt asks for it: flat value+anchor keys."""
    payload: dict[str, str | None] = dict(values)
    payload.update({anchor_key_for_field(name): anchor for name, anchor in anchors.items()})
    return json.dumps(payload)


def _spanish_draft() -> InvoiceDraft:
    return ground_extracted_fields(
        parse_invoice_extraction_response(_canned_response(_SPANISH_INVOICE, _SPANISH_ANCHORS)),
        raw_text_length=256,
        origin=FieldOrigin.VISION,
    )


def _envelope(draft: InvoiceDraft, field_name: str) -> FieldProvenance:
    matching = [item for item in draft.provenance if item.field == field_name]
    assert len(matching) == 1, f"expected exactly one envelope for {field_name}, got {len(matching)}"
    return matching[0]


class TestThePromptAsksForEveryValueAndItsAnchor:
    """The contract the model is held to must actually request the anchor."""

    def test_the_skeleton_asks_for_a_value_key_and_an_anchor_key_per_field(self) -> None:
        """And a role-evidence key on exactly the fields whose contract declares one.

        Derived from the contract rows rather than listed, so a new identity
        field is covered the moment it is declared. Asserting the ORDER as well
        as the set is deliberate: the three keys for one field must stay
        adjacent, because the design target is a small model that pairs a value
        with its anchor and its role evidence most reliably when they are
        written together.
        """
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text
        skeleton = text[text.index("{") : text.rindex("}") + 1]

        as_json = re.sub(r"<[^>]*>", "null", skeleton, flags=re.DOTALL)
        expected = [
            key
            for contract in INVOICE_FIELD_CONTRACTS
            for key in (
                contract.field_name,
                anchor_key_for_field(contract.field_name),
                *((role_evidence_key_for_field(contract.field_name),) if contract.carries_role_evidence else ()),
            )
        ]

        assert list(json.loads(as_json)) == expected

    def test_the_prompt_states_the_anchor_keeps_what_the_field_drops(self) -> None:
        """The one instruction that makes anchor and value distinct rather than duplicated."""
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text

        assert "EXACTLY as printed" in text
        assert "the field's own rule told you to drop" in text
        assert "Never write an anchor that does not appear in the document." in text

    def test_the_anchor_suffix_the_prompt_renders_is_the_one_the_parser_reads(self) -> None:
        """One declaration, two derivations: a suffix spelled twice fails silently."""
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text

        for contract in INVOICE_FIELD_CONTRACTS:
            assert f'"{contract.field_name}{ANCHOR_KEY_SUFFIX}"' in text

        parsed = parse_invoice_extraction_response(
            _canned_response(_SPANISH_INVOICE, _SPANISH_ANCHORS),
        )

        for contract in INVOICE_FIELD_CONTRACTS:
            assert getattr(parsed.anchors, contract.field_name) == _SPANISH_ANCHORS[contract.field_name]


class TestEveryExtractedFieldCarriesItsAnchor:
    """Every extracted field carries its own anchor, driven end to end through the real path."""

    def test_every_populated_field_gets_exactly_one_envelope(self) -> None:
        draft = _spanish_draft()

        assert {item.field for item in draft.provenance} == {
            contract.field_name for contract in INVOICE_FIELD_CONTRACTS
        }

    def test_every_envelope_carries_a_populated_verbatim_anchor(self) -> None:
        """The anchor is the load-bearing half: an empty one leaves nothing to check."""
        draft = _spanish_draft()

        for item in draft.provenance:
            assert item.anchor, item.field
            assert item.anchor == _SPANISH_ANCHORS[item.field]

    def test_the_envelope_records_the_reader_that_produced_it(self) -> None:
        vision = _spanish_draft()
        text_layer = ground_extracted_fields(
            parse_invoice_extraction_response(_canned_response(_SPANISH_INVOICE, _SPANISH_ANCHORS)),
            raw_text_length=256,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert {item.origin for item in vision.provenance} == {FieldOrigin.VISION}
        assert {item.origin for item in text_layer.provenance} == {FieldOrigin.TEXT_LAYER}

    def test_a_field_the_grounder_dropped_gets_no_envelope(self) -> None:
        """An envelope describes a value; a dropped field has no value to describe."""
        values = dict(_SPANISH_INVOICE)
        values["taxable_base"] = "one thousand two hundred"
        anchors = dict(_SPANISH_ANCHORS)

        draft = ground_extracted_fields(
            parse_invoice_extraction_response(_canned_response(values, anchors)),
            raw_text_length=256,
            origin=FieldOrigin.VISION,
        )

        assert draft.taxable_base is None
        assert "taxable_base" not in {item.field for item in draft.provenance}
        assert "grand_total" in {item.field for item in draft.provenance}

    def test_a_value_reported_with_no_anchor_still_grounds_but_says_so(self) -> None:
        """Null-over-guess applies to the anchor too: absent is recorded, never invented."""
        anchors = dict(_SPANISH_ANCHORS)
        anchors["grand_total"] = None

        draft = ground_extracted_fields(
            parse_invoice_extraction_response(_canned_response(_SPANISH_INVOICE, anchors)),
            raw_text_length=256,
            origin=FieldOrigin.VISION,
        )

        envelope = _envelope(draft, "grand_total")

        assert draft.grand_total == Decimal("1452.00")
        assert envelope.anchor is None
        assert "no printed form" in envelope.note

    def test_a_reply_carrying_no_anchors_at_all_still_parses(self) -> None:
        """A model that ignores the anchor half is recorded honestly, not rejected."""
        draft = ground_extracted_fields(
            parse_invoice_extraction_response(json.dumps(_SPANISH_INVOICE)),
            raw_text_length=256,
            origin=FieldOrigin.VISION,
        )

        assert draft.grand_total == Decimal("1452.00")
        assert all(item.anchor is None for item in draft.provenance)

    def test_a_key_that_is_neither_a_field_nor_an_anchor_is_refused(self) -> None:
        """An invented key is a model inventing structure; tolerating it hides a fabrication."""
        payload: dict[str, str | None] = dict(_SPANISH_INVOICE)
        payload["supplier_confidence"] = "high"

        with pytest.raises(PurchaseInvoiceEvidenceInputError):
            parse_invoice_extraction_response(json.dumps(payload))


class TestTheAnchorKeepsThePrintedFormTheValueDropped:
    """The ``21%`` / ``21`` case, asserted as the distinctness it exists to create."""

    def test_the_rate_anchor_keeps_its_unit_while_the_value_is_bare(self) -> None:
        draft = _spanish_draft()

        assert draft.iva_rate == Decimal("21")
        assert _envelope(draft, "iva_rate").anchor == "21%"

    def test_a_rate_printed_with_its_unit_grounds_bare_and_anchors_printed(self) -> None:
        """The measured defect ran the other way: the literal reader lost the field."""
        values = dict(_SPANISH_INVOICE)
        values["iva_rate"] = "21%"
        anchors = dict(_SPANISH_ANCHORS)
        anchors["iva_rate"] = "IVA (21%)"

        draft = ground_extracted_fields(
            parse_invoice_extraction_response(_canned_response(values, anchors)),
            raw_text_length=256,
            origin=FieldOrigin.VISION,
        )

        assert draft.iva_rate == Decimal("21")
        assert _envelope(draft, "iva_rate").anchor == "IVA (21%)"

    def test_no_envelope_is_byte_identical_to_its_value(self) -> None:
        """A vacuous pair makes the downstream parse check compare a value to itself.

        Driven from the contract declaration rather than a hardcoded name tuple,
        like the sibling gates above it. The tuple named the four monetary
        fields, so the property held for those by gate and for every other
        declared field by author convention only -- and a convention is exactly
        what a gate is for. Collapsing a postal, country, legend or identifier
        anchor to equal its value reddened nothing, while the anchor evaluator
        downstream reports precisely that shape as a vacuous parse.

        Every declared field is in scope because the property is about the
        FIXTURE, not about the form: whatever a field's declared form, an anchor
        authored equal to its value tests nothing.
        """
        draft = _spanish_draft()

        for contract in INVOICE_FIELD_CONTRACTS:
            envelope = _envelope(draft, contract.field_name)
            assert envelope.anchor != str(getattr(draft, contract.field_name)), contract.field_name


class TestNothingHereClaimsAVerificationItDidNotRun:
    """The grounding outcome under-claims deliberately.

    A model REPORTING an anchor is a claim about the document, not a check
    against it. The check needs the document; this stage does not hold it. So the
    honest outcome is the one that says the check did not pass, and the anchor
    rides along as the claim a later stage verifies.
    """

    def test_every_envelope_is_unanchored_rather_than_anchored(self) -> None:
        draft = _spanish_draft()

        assert {item.grounding for item in draft.provenance} == {FieldGroundingOutcome.UNANCHORED}

    def test_no_envelope_claims_an_independent_corroboration(self) -> None:
        draft = _spanish_draft()
        overclaims = {FieldGroundingOutcome.RECONCILED, FieldGroundingOutcome.ANCHORED}

        assert not {item.grounding for item in draft.provenance} & overclaims

    def test_the_note_says_the_anchor_is_unchecked_rather_than_implying_otherwise(self) -> None:
        draft = _spanish_draft()

        assert "not yet checked against the document" in _envelope(draft, "iva_rate").note

    def test_no_envelope_carries_candidates_it_cannot_justify(self) -> None:
        """The envelope refuses candidates under a decided outcome; nothing here builds any."""
        draft = _spanish_draft()

        assert all(item.candidates == () for item in draft.provenance)


class TestAForeignRateSurvivesTheSpanishEnumeration:
    """The hazard the enumeration creates, gated on behaviour rather than on prose.

    The prompt lists the registered Spanish rates so a small model selects rather
    than infers. A model shown ``4, 10, 21`` and handed a German invoice printing
    ``19`` may coerce it onto the list -- fabricating exactly the class of figure
    the null-over-guess rule exists to prevent. The counter-instruction is prose;
    these drive the real parser and the real grounder.
    """

    _GERMAN_INVOICE: dict[str, str | None] = {
        "supplier_tax_id": "DE811907980",
        "invoice_number": "RE-2026-88",
        "invoice_date": "14/04/2026",
        "taxable_base": "1.000,00",
        "iva_rate": "19",
        "iva_amount": "190,00",
        "grand_total": "1.190,00",
        "currency": "EUR",
    }
    _GERMAN_ANCHORS: dict[str, str | None] = {
        "supplier_tax_id": "USt-IdNr. DE811907980",
        "invoice_number": "Rechnung RE-2026-88",
        "invoice_date": "14/04/2026",
        "taxable_base": "1.000,00 €",
        "iva_rate": "19 %",
        "iva_amount": "190,00 €",
        "grand_total": "1.190,00 €",
        "currency": "€",
    }

    def _german_draft(self, **value_overrides: str) -> InvoiceDraft:
        values = dict(self._GERMAN_INVOICE)
        values.update(value_overrides)
        return ground_extracted_fields(
            parse_invoice_extraction_response(_canned_response(values, self._GERMAN_ANCHORS)),
            raw_text_length=256,
            origin=FieldOrigin.VISION,
        )

    def test_the_rate_is_not_on_the_spanish_enumeration(self) -> None:
        """Anchors the premise: a fixture whose rate WAS Spanish would prove nothing."""
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2026)

        assert Decimal("19") not in compiled.iva_rate_pcts

    def test_a_foreign_rate_survives_parse_and_grounding_unmoved(self) -> None:
        draft = self._german_draft()

        assert draft.iva_rate == Decimal("19")

    def test_the_foreign_rate_is_never_snapped_onto_a_spanish_one(self) -> None:
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2026)
        draft = self._german_draft()

        assert draft.iva_rate not in set(compiled.iva_rate_pcts)

    @pytest.mark.parametrize("printed", ["19", "19%", "19 %", "19,00"])
    def test_the_foreign_rate_survives_whatever_unit_it_is_printed_with(self, printed: str) -> None:
        draft = self._german_draft(iva_rate=printed)

        assert draft.iva_rate == Decimal("19")

    def test_the_whole_foreign_invoice_survives_intact(self) -> None:
        """The rate is the headline risk, but a coerced rate would drag the cuota with it."""
        draft = self._german_draft()

        assert draft.taxable_base == Decimal("1000.00")
        assert draft.iva_amount == Decimal("190.00")
        assert draft.grand_total == Decimal("1190.00")
        assert draft.supplier_tax_id == "DE811907980"

    def test_the_foreign_rate_keeps_its_printed_anchor(self) -> None:
        draft = self._german_draft()

        assert _envelope(draft, "iva_rate").anchor == "19 %"


class TestTheTwoRateAuthoritiesAgreeForSpain:
    """The prompt reads rates from the EU table; the modelo registry declares its own.

    The compiler resolves Spanish IVA rates from the EU member-state table
    (:func:`~domain.iva.load_iva_rate_table` filtered to ``ES`` by effective
    window) rather than from the modelo registry, because the question it asks --
    "what rates are in force in country C on date D" -- has no modelo to resolve
    against. That is sound only while the two authorities agree, and they are
    independently authored: the Modelo 390 rate-box binding layer carries its own
    ``applied_rates`` as decimal FRACTIONS, and nothing until now compared them.

    The comparison is direction-aware, which is the honest shape rather than a
    convenience. The 390 layer belongs to one long-lived revision and therefore
    declares every rate that revision must be able to record, while the EU table
    is windowed by statute -- so the registry is a superset in a year where no
    transitional tier is live, and equality only holds where the two windows
    coincide. What must never happen in either direction is a rate in force with
    no box able to record it.
    """

    @staticmethod
    def _eu_table_rates(period: Period) -> set[Decimal]:
        start, end = period.start_date, period.end_date
        return {
            record.pct
            for record in load_iva_rate_table()[EUMemberState.ES]
            if record.effective_from <= end and (record.effective_until is None or record.effective_until >= start)
        }

    @staticmethod
    def _registry_rates(period: Period) -> set[Decimal]:
        """Return the Spanish percentages the Modelo 390 rate-box layer declares.

        Read off the compiled snapshot rather than the TOML, so the comparison is
        against what the authority actually serves. Stored as fractions because a
        ledger row carries a fraction; scaled here because a printed invoice --
        and the prompt -- states a percentage.
        """
        snapshot = bundled_authority().snapshot("390", filing_year=period.filing_year, period=str(period.code))
        rates: set[Decimal] = set()
        for binding in snapshot.revision.bindings:
            applied = getattr(getattr(binding, "selector", None), "applied_rates", None)
            if applied:
                rates.update(Decimal(str(value)) * Decimal("100") for value in applied)
        return rates

    def test_the_registry_declares_a_box_for_every_rate_in_force(self) -> None:
        """The load-bearing direction: an in-force rate with no box under-declares."""
        for period in (_ANNUAL_2024, _ANNUAL_2026):
            eu_rates = self._eu_table_rates(period)
            registry_rates = self._registry_rates(period)

            assert eu_rates, f"the EU table yielded no Spanish rate for {period.code} {period.filing_year}"
            assert eu_rates <= registry_rates, (
                f"{period.filing_year}: rates in force with no Modelo 390 box: {sorted(eu_rates - registry_rates)}"
            )

    def test_the_two_authorities_agree_exactly_where_their_windows_coincide(self) -> None:
        """2024 is the discriminating year: every transitional tier is live in it.

        A containment assertion alone would pass against a registry that declared
        every conceivable rate. In 2024 the RD-ley 4/2024 transitional tiers put
        all seven rates in force at once, so the EU table and the rate-box layer
        must match exactly -- there is no slack left for one to drift into.
        """
        assert self._eu_table_rates(_ANNUAL_2024) == self._registry_rates(_ANNUAL_2024)

    def test_the_agreement_is_asserted_over_a_non_trivial_rate_set(self) -> None:
        """Guards the two assertions above from passing vacuously on a thin table."""
        rates_2024 = self._eu_table_rates(_ANNUAL_2024)

        assert len(rates_2024) >= len(self._eu_table_rates(_ANNUAL_2026))
        assert {Decimal("4"), Decimal("10"), Decimal("21")} <= rates_2024

    def test_the_prompt_enumerates_exactly_the_eu_table_rates_it_resolved(self) -> None:
        """Closes the loop: the agreement above is about the numbers the model is shown."""
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2024)

        assert set(compiled.iva_rate_pcts) == self._eu_table_rates(_ANNUAL_2024)


class TestTheAnchorModelStaysBoundToTheOneDeclaration:
    """A third derivation of the field list is a third thing that can drift."""

    def test_the_anchor_schema_covers_the_declaration_exactly(self) -> None:
        declared = {contract.field_name for contract in INVOICE_FIELD_CONTRACTS}

        assert declared == set(ExtractedFieldAnchors.model_fields)

    def test_the_anchor_schema_mirrors_the_value_schema_exactly(self) -> None:
        assert set(ExtractedFieldAnchors.model_fields) == set(ExtractedInvoiceFields.model_fields)

    def test_every_draft_field_an_envelope_names_is_a_real_draft_field(self) -> None:
        """The draft's own validator enforces this; the gate proves the names we emit pass it."""
        draft = _spanish_draft()

        assert draft.provenance
        for item in draft.provenance:
            assert item.field in type(draft).model_fields

    def test_a_response_carries_values_and_anchors_together(self) -> None:
        """The pairing is structural: a caller cannot hold values without their anchors."""
        parsed = parse_invoice_extraction_response(
            _canned_response(_SPANISH_INVOICE, _SPANISH_ANCHORS),
        )

        assert isinstance(parsed, ExtractedInvoiceResponse)
        assert parsed.fields.iva_rate == "21"
        assert parsed.anchors.iva_rate == "21%"


class TestTheTemplateIsRegisteredRatherThanOnlyAConstant:
    """The pre-substitution template is versioned prompt metadata, so it lives in the registry.

    The compiler reads its template from
    :func:`~llm._invoice_extraction_prompt.invoice_extraction_prompt_registry`
    rather than closing over a module constant, which is what lets the template's
    id and version travel onto the compiled artefact. The compiled OUTPUT keeps
    its own type: an integer version cannot express a content fingerprint that
    moves whenever a substituted registry value moves, so the two are carried
    separately rather than one replacing the other.
    """

    def test_the_registry_carries_the_extraction_template(self) -> None:
        definition = invoice_extraction_prompt_registry().get(INVOICE_EXTRACTION_PROMPT_ID)

        assert definition.id == INVOICE_EXTRACTION_PROMPT_ID
        assert definition.version == INVOICE_EXTRACTION_PROMPT_VERSION
        assert definition.template == PROMPT_TEMPLATE

    def test_the_compiler_consumes_the_registered_template(self) -> None:
        """Asserted by substituting the registered template by hand and comparing."""
        definition = invoice_extraction_prompt_registry().get(INVOICE_EXTRACTION_PROMPT_ID)
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2026)

        assert compiled.text.startswith(definition.template[: definition.template.index("{")])
        assert compiled.template_version == definition.version

    def test_the_numeric_literal_scan_follows_the_registry(self) -> None:
        """The digit-free gate must read the text the compiler will actually use."""
        definition = invoice_extraction_prompt_registry().get(INVOICE_EXTRACTION_PROMPT_ID)

        assert template_numeric_literals() == template_numeric_literals(definition.template)

    def test_the_version_and_the_fingerprint_are_different_facts(self) -> None:
        """Two periods share one template version but must not share a fingerprint.

        This is why registering the template does not retire the fingerprint: the
        instructions were identical, the compiled text was not, and only one of
        the two axes can say so.
        """
        annual = build_invoice_extraction_prompt(period=_ANNUAL_2024)
        later = build_invoice_extraction_prompt(period=_ANNUAL_2026)

        assert annual.template_version == later.template_version
        assert annual.fingerprint != later.fingerprint
