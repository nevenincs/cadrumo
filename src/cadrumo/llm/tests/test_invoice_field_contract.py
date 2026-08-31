"""Real-behaviour gates for the single field-form declaration and the compiled prompt.

Every test here is MODEL-FREE and NETWORK-FREE by construction: each asserts on
compiled prompt text, or feeds a canned response string through the real parser
and the real grounder. Nothing constructs a transport, so these hold on a host
that can run no model at all.

The defect under gate: the expected FORM of each extracted field was stated twice
-- once in the prompt's prose, once in the grounding validators -- and the two
disagreed. On an invoice printing ``IVA (21%)`` a model returning ``"21%"`` lost
the field entirely while one returning ``"21"`` was accepted, so the model that
obeyed "copy exactly as printed" more literally was the one punished.

See Also:
    :data:`~llm.invoice_field_contract.INVOICE_FIELD_CONTRACTS`
        The one declaration both derivations bind to.
    :func:`~llm.invoice_extraction_prompt.build_invoice_extraction_prompt`
        The compiled artefact whose numbers come from the registry.
    :func:`~llm.invoice_field_grounding.ground_extracted_fields`
        The grounding derivation.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest

from ...core.field_origin import FieldOrigin
from ...core.period import Period
from ...domain import iva as _iva_module
from ...domain.iva.rates import load_iva_rate_table
from ...domain.iva.schema import EUMemberState, IvaCategory, NO_PRINTED_TAX_IVA_CATEGORIES
from ...domain.transactions.retencion_parameters import statutory_activity_retencion_rates
from ...tests.attribute_scope import scoped_attribute
from .. import invoice_extraction_prompt as _invoice_extraction_prompt
from ..invoice_extraction_prompt import (
    INVOICE_EXTRACTION_PROMPT_ID,
    PROMPT_TEMPLATE,
    build_invoice_extraction_prompt,
    default_extraction_period,
    invoice_extraction_prompt_registry,
    template_numeric_literals,
)
from ..invoice_field_contract import (
    INVOICE_FIELD_CONTRACTS,
    InvoiceFieldForm,
    anchor_key_for_field,
    role_evidence_key_for_field,
)
from ..invoice_field_grounding import (
    _NUMERIC_GROUNDING_BY_FORM,
    _TEXT_GROUNDING_BY_FORM,
    ExtractedFieldAnchors,
    ExtractedInvoiceFields,
    ExtractedInvoiceResponse,
    ground_extracted_fields,
    parse_invoice_extraction_response,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_ANNUAL_2026 = Period.from_year_and_code(2026, "0A")
_Q4_2024 = Period.from_year_and_code(2024, "4T")


def _compiled(period: Period = _ANNUAL_2026) -> str:
    return build_invoice_extraction_prompt(period=period).text


class TestTheTemplateCarriesNoRegulatoryLiteral:
    """A rate baked into a prompt is the least-audited literal in the codebase.

    ``aeat-registry-authority-flow`` forbids inlining an AEAT rate as a Python
    literal because it is versioned by filing year plus revision. A prompt is
    where such a literal hides best: nothing type-checks it and no gate reads
    it, so a stale figure keeps steering a reading model indefinitely.
    """

    def test_the_template_contains_no_numeric_literal_at_all(self) -> None:
        """Only the ISO-4217 standards token is allowed to carry digits."""
        assert template_numeric_literals() == ()

    def test_the_scan_finds_a_rate_planted_in_a_template(self) -> None:
        """The gate discriminates: it reports a literal that IS there.

        Without this the passing assertion above proves only that the scanner
        found nothing, which an always-empty scanner also achieves.
        """
        assert template_numeric_literals(PROMPT_TEMPLATE + "\n- the rate is 21%.") == ("21",)
        assert template_numeric_literals("charge 7,5 percent") == ("7,5",)

    def test_the_iso_allowance_is_narrow(self) -> None:
        """The allowlisted token is exempt; a bare number resembling it is not."""
        assert template_numeric_literals("use the ISO-4217 code") == ()
        assert template_numeric_literals("use code 4217") == ("4217",)


class TestCompiledEnumerationsComeFromTheRegistry:
    """The compiled numbers equal what the owning authority resolves for the period."""

    @pytest.mark.parametrize("period", [_ANNUAL_2026, _Q4_2024], ids=["annual-2026", "q4-2024"])
    def test_iva_rates_equal_every_registered_spanish_rate_overlapping_the_period(self, period: Period) -> None:
        """Asserted on two periods whose law differs, so one hardcoded tuple cannot satisfy both."""
        compiled = build_invoice_extraction_prompt(period=period)

        expected = sorted(
            {
                record.pct
                for record in load_iva_rate_table()[EUMemberState.ES]
                if record.effective_from <= period.end_date
                and (record.effective_until is None or record.effective_until >= period.start_date)
            },
        )

        assert list(compiled.iva_rate_pcts) == expected
        for pct in expected:
            assert format(pct.normalize(), "f") in compiled.text

    def test_retencion_rates_equal_the_rirpf_art_95_parameters_as_percentages(self) -> None:
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2026)

        expected = sorted(rate * Decimal("100") for rate in statutory_activity_retencion_rates())

        assert list(compiled.retencion_rate_pcts) == expected

    def test_a_period_whose_law_differs_compiles_a_different_enumeration(self) -> None:
        """RD-ley 4/2024 stepped part of two tiers in Q4 2024; the prompt follows.

        This is the property a literal cannot have, and it is why the values are
        resolved rather than written down: the same code compiles ``2, 7.5`` into
        the 2024 Q4 prompt and not into the 2026 one, with nothing in this
        package changed between the two calls.
        """
        annual_2026 = build_invoice_extraction_prompt(period=_ANNUAL_2026)
        q4_2024 = build_invoice_extraction_prompt(period=_Q4_2024)

        assert Decimal("7.5") in q4_2024.iva_rate_pcts
        assert Decimal("7.5") not in annual_2026.iva_rate_pcts
        assert q4_2024.text != annual_2026.text
        assert q4_2024.fingerprint != annual_2026.fingerprint

    def test_the_enumeration_is_a_hint_and_never_a_constraint(self) -> None:
        """Documents in scope are international; a foreign rate must not be coerced.

        A model told "the rate is one of these" would move a German 19 % onto
        21 %, fabricating exactly the class of figure the null-over-guess rule
        exists to prevent.
        """
        text = _compiled()

        assert "may print a rate on neither list" in text
        assert "never move it onto a listed one" in text


class TestTheAntiDriftGateBitesInBothDirections:
    """The gate is unproven until each half is shown to red on its own mutation.

    A one-directional proof is the failure mode this class exists to close. A
    gate that only proves "no literal is present" passes a template that ignores
    the registry entirely and enumerates nothing; a gate that only proves "the
    values came from the registry" passes a template that also carries a stale
    literal beside them. Both mutations are applied at RUNTIME from outside the
    production modules, so no tracked file changes and a concurrent sweep cannot
    commit the mutation.
    """

    def test_moving_a_registry_rate_moves_the_compiled_prompt(self) -> None:
        """Direction one: the compiled text FOLLOWS the rate authority.

        The mutation adds one record to the table the compiler reads and asserts
        the new percentage reaches the text. This is the assertion a template
        holding a hardcoded rate list cannot satisfy: it would keep emitting the
        original enumeration under the mutated authority.
        """
        baseline = build_invoice_extraction_prompt(period=_ANNUAL_2026)
        planted = Decimal("13.5")
        assert planted not in baseline.iva_rate_pcts, "pick a percentage the registry does not already carry"

        real_table = load_iva_rate_table()
        spain = real_table[EUMemberState.ES]
        extra = spain[0].model_copy(
            update={
                "pct": planted,
                "effective_from": _ANNUAL_2026.start_date,
                "effective_until": None,
            },
        )
        mutated = dict(real_table) | {EUMemberState.ES: (*spain, extra)}
        with scoped_attribute(_iva_module, "load_iva_rate_table", lambda: mutated):
            after = build_invoice_extraction_prompt(period=_ANNUAL_2026)

            assert planted in after.iva_rate_pcts
            assert "13.5" in after.text
            assert after.fingerprint != baseline.fingerprint

    def test_the_literal_gate_reds_on_a_template_carrying_a_rate(self) -> None:
        """Direction two: planting a literal in the REGISTERED template reds the gate.

        The distinction from the scanner's positive control is the whole point.
        That control passes a string to the scanner and proves the regex works;
        this replaces the template the shipped gate actually reads, so it proves
        the gate is pointed at the artefact that ships. A gate reading a stale
        snapshot passes this file and misses a literal added to the real
        template -- which is exactly the defect the compiler's own docstring
        records a probe having caught.
        """
        assert template_numeric_literals() == (), "positive control: the gate is green before the mutation"

        registry = invoice_extraction_prompt_registry()
        definition = registry.get(INVOICE_EXTRACTION_PROMPT_ID)
        poisoned = definition.model_copy(update={"template": definition.template + "\n- the IVA rate is 21."})
        mutated_registry = type(registry)()
        mutated_registry.register(poisoned)
        with scoped_attribute(
            _invoice_extraction_prompt, "invoice_extraction_prompt_registry", lambda: mutated_registry
        ):
            assert template_numeric_literals() == ("21",)

    def test_neither_mutation_is_visible_to_the_other_direction(self) -> None:
        """Both mutations are undone by their own context managers, so the gate is green again here.

        Ordering-independent: each mutation above is scoped to its own ``with``
        block and restored on exit, so a green here proves neither mutation
        leaked into module state (the compiler caches its registry with
        ``lru_cache``, which is exactly the kind of state a patch can strand).
        """
        assert template_numeric_literals() == ()
        assert Decimal("13.5") not in build_invoice_extraction_prompt(period=_ANNUAL_2026).iva_rate_pcts


class TestTheNoPrintedTaxLineAsksThePaperQuestion:
    """The list of tax-free reasons must describe INVOICES, not 303 cuota outcomes.

    The two authorities differ exactly on the reverse-charge family, and in the
    direction that matters: under inversion del sujeto pasivo the recipient
    self-assesses a real 303 cuota, so those members are deliberately excluded
    from the cuota-less set -- while the supplier's invoice repercutes nothing
    and is required to say so. Compiling the prompt off the cuota-less set
    therefore told a reading model that the commonest no-IVA invoice a Spanish
    autonomo receives cannot exist.
    """

    @pytest.mark.parametrize(
        "category",
        [
            IvaCategory.DOMESTIC_REVERSE_CHARGE,
            IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
        ],
    )
    def test_the_reverse_charge_family_is_named_as_a_tax_free_invoice(self, category: IvaCategory) -> None:
        """Fixture anchor: pinned by member, so a rename cannot pass this vacuously."""
        assert category in NO_PRINTED_TAX_IVA_CATEGORIES
        assert category.value.replace("_", " ") in _compiled()

    def test_the_line_enumerates_the_derived_set_exactly(self) -> None:
        """No member is dropped and none is invented, in both directions."""
        text = _compiled()
        opening = "carry no tax at all ("
        rendered = text[text.index(opening) + len(opening) : text.index(").")]

        assert set(rendered.split(", ")) == {c.value.replace("_", " ") for c in NO_PRINTED_TAX_IVA_CATEGORIES}


class TestRetencionIsAskedForAndNotMerelyEnumerated:
    """Enumerating a rate the response has no slot for is dead context, and worse.

    The prompt listed the RIRPF art. 95 rates while asking for no withholding
    field, so every reading of an invoice carrying IRPF retencion dropped it --
    on a prompt whose binding constraint is the context budget of a 2B-class
    model. The loss runs in the over-payment direction: a retencion already
    withheld and never recovered is tax paid twice, and nothing downstream
    watches that direction.
    """

    @pytest.mark.parametrize("field_name", ["retencion_rate", "retencion_amount"])
    def test_the_withholding_fields_are_declared_asked_for_and_grounded(self, field_name: str) -> None:
        text = _compiled()

        assert field_name in {contract.field_name for contract in INVOICE_FIELD_CONTRACTS}
        assert f'"{field_name}"' in text
        assert f'"{anchor_key_for_field(field_name)}"' in text
        assert field_name in ExtractedInvoiceFields.model_fields
        assert field_name in ExtractedFieldAnchors.model_fields

    def test_a_withheld_invoice_survives_grounding_with_its_anchor(self) -> None:
        """End to end through the real parser and grounder: no model, no transport."""
        response = parse_invoice_extraction_response(
            json.dumps(
                {
                    "retencion_rate": "15",
                    "retencion_rate_anchor": "-15%",
                    "retencion_amount": "150,00",
                    "retencion_amount_anchor": "-150,00 EUR",
                },
            ),
        )

        draft = ground_extracted_fields(response, raw_text_length=400, origin=FieldOrigin.VISION)

        assert draft.retencion_rate == Decimal("15")
        assert draft.retencion_amount == Decimal("150.00")
        anchors = {envelope.field: envelope.anchor for envelope in draft.provenance}
        assert anchors["retencion_rate"] == "-15%"
        assert anchors["retencion_amount"] == "-150,00 EUR"


class TestContractParityAcrossBothDerivations:
    """Prompt fields and grounder fields derive from ONE declaration.

    Two hand-maintained lists that happen to agree today is the defect, not the
    fix, so the gate is bidirectional: neither side may carry a field the other
    lacks.
    """

    def test_the_declaration_covers_the_response_schema_exactly(self) -> None:
        declared = {contract.field_name for contract in INVOICE_FIELD_CONTRACTS}

        assert declared == set(ExtractedInvoiceFields.model_fields)

    def test_every_declared_field_appears_in_the_compiled_prompt(self) -> None:
        text = _compiled()

        for contract in INVOICE_FIELD_CONTRACTS:
            assert f'"{contract.field_name}"' in text
            assert contract.form_instruction in text

    def test_the_prompt_asks_for_exactly_the_declared_keys_and_no_others(self) -> None:
        """The JSON skeleton the prompt shows is the schema, parsed as JSON."""
        text = _compiled()
        skeleton = text[text.index("{") : text.rindex("}") + 1]

        as_json = re.sub(r"<[^>]*>", "null", skeleton, flags=re.DOTALL)

        assert json.loads(as_json) == dict.fromkeys(
            key
            for contract in INVOICE_FIELD_CONTRACTS
            for key in (
                contract.field_name,
                anchor_key_for_field(contract.field_name),
                # Present on exactly the identity fields, derived from the same
                # declaration the prompt renders from. A key asked for but not
                # declared, or declared but not asked for, fails here rather
                # than arriving as an unrecognised key the parser rejects at
                # read time -- when a real document is in the operator's hands.
                *((role_evidence_key_for_field(contract.field_name),) if contract.carries_role_evidence else ()),
            )
        )

    def test_every_declared_form_has_exactly_one_grounding_validator(self) -> None:
        """The two typed tables cover the form enum exactly and without overlap."""
        text_forms = set(_TEXT_GROUNDING_BY_FORM)
        numeric_forms = set(_NUMERIC_GROUNDING_BY_FORM)
        declared_forms = {contract.form for contract in INVOICE_FIELD_CONTRACTS}

        assert not text_forms & numeric_forms
        assert text_forms | numeric_forms == set(InvoiceFieldForm)
        assert declared_forms <= set(InvoiceFieldForm)

    def test_the_grounder_grounds_exactly_the_declared_fields(self) -> None:
        """Every declared field reaches the draft; a field it cannot is caught here."""
        populated = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields(
                supplier_tax_id="B44531218",
                supplier_name="Ferretería Insular S.L.",
                supplier_postal_code="35001",
                supplier_country="España",
                customer_tax_id="12345678Z",
                customer_name="Talleres Mayor S.A.",
                customer_postal_code="28013",
                customer_country="Alemania",
                invoice_number="2026-0142",
                invoice_date="10/03/2026",
                taxable_base="100,00",
                iva_rate="21",
                iva_amount="21,00",
                retencion_rate="15",
                retencion_amount="15,00",
                grand_total="106,00",
                regime_legend="inversión del sujeto pasivo",
                currency="EUR",
            ),
            anchors=ExtractedFieldAnchors(),
        )

        draft = ground_extracted_fields(populated, raw_text_length=10, origin=FieldOrigin.TEXT_LAYER)

        for contract in INVOICE_FIELD_CONTRACTS:
            assert getattr(draft, contract.field_name) is not None, contract.field_name


class TestThePrintedPercentSignNoLongerLosesTheRate:
    """The measured defect: ``IVA (21%)`` read as ``"21%"`` dropped the field.

    The resolution is unit normalisation, not looser grounding. A percent sign is
    a unit marker, not a digit, so the number that remains is still the printed
    one -- copied, never computed -- and the ANCHOR stays the untouched printed
    text, distinct from the normalised numeric value.
    """

    @pytest.mark.parametrize("printed", ["21%", "21 %", "21percent", "21 pct", " 21% "])
    def test_a_rate_carrying_its_printed_unit_still_grounds(self, printed: str) -> None:
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields(iva_rate=printed), anchors=ExtractedFieldAnchors()
        )

        assert ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.TEXT_LAYER).iva_rate == Decimal(
            "21"
        )

    def test_the_anchor_keeps_the_printed_form_while_the_value_is_bare(self) -> None:
        """Anchor and value become explicitly distinct: the anchor keeps the printed text."""
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields(iva_rate="21%"), anchors=ExtractedFieldAnchors()
        )

        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.TEXT_LAYER)

        assert fields.fields.iva_rate == "21%"
        assert draft.iva_rate == Decimal("21")

    def test_a_percent_sign_on_a_monetary_amount_is_still_a_misread(self) -> None:
        """The tolerance is scoped to the rate form; an amount is not a percentage."""
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields(taxable_base="100,00%", grand_total="121%"), anchors=ExtractedFieldAnchors()
        )

        draft = ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.TEXT_LAYER)

        assert draft.taxable_base is None
        assert draft.grand_total is None

    @pytest.mark.parametrize("printed", ["21%%", "%21", "21% de IVA", "twenty-one percent", "%"])
    def test_a_rate_that_is_not_merely_unit_suffixed_still_drops(self, printed: str) -> None:
        """Exactly one trailing unit is stripped; anything else fails the authority."""
        fields = ExtractedInvoiceResponse(
            fields=ExtractedInvoiceFields(iva_rate=printed), anchors=ExtractedFieldAnchors()
        )

        assert ground_extracted_fields(fields, raw_text_length=10, origin=FieldOrigin.TEXT_LAYER).iva_rate is None


class TestTheSafetyPropertiesSurviveCompilation:
    """The null-over-guess line is the single most important line in the prompt."""

    def test_the_compiled_prompt_instructs_null_rather_than_a_guess(self) -> None:
        lowered = _compiled().lower()

        assert "its value is null" in lowered
        assert "never substitute a plausible value for a missing one" in lowered

    def test_the_compiled_prompt_forbids_deriving_any_value(self) -> None:
        lowered = _compiled().lower()

        for forbidden in ("calculate", "infer", "estimate", "guess"):
            assert forbidden in lowered
        assert "exactly as printed" in lowered

    def test_the_compiled_prompt_is_language_neutral(self) -> None:
        lowered = _compiled().lower()

        assert "may be written in any language" in lowered
        assert "scanned spanish invoice" not in lowered

    def test_a_document_bearing_no_tax_is_told_to_emit_null_rather_than_a_rate(self) -> None:
        """Derived from the cuota-less category set, so the law moves it, not an author."""
        text = _compiled()

        assert "carry no tax at all" in text
        assert "intra community supply" in text
        assert "Never supply a rate the document does not print." in text

    def test_no_doubled_brace_reaches_the_model(self) -> None:
        """Nothing ``format``s the COMPILED text, so a doubled brace is not an escape."""
        text = _compiled()

        assert "{{" not in text
        assert "}}" not in text


class TestAuthoredResponsesStillDropFabricatedValues:
    """A malformed or invented value per field type reaches the draft as ``None``.

    Fed through the real parser and the real grounder -- the exact production
    path -- with an authored response string standing in for the transport.
    """

    def test_a_wholly_malformed_response_drops_every_field(self) -> None:
        response = json.dumps(
            {
                # Checksum-invalid: the control digit does not compute, and the
                # ``B`` prefix names no EU Member State either, so the EU
                # structural fallback rejects it too.
                "supplier_tax_id": "B12345678",
                "invoice_number": "   ",
                "invoice_date": "the third of never",
                "taxable_base": "one hundred euros",
                "iva_rate": "twenty-one",
                "iva_amount": "NaN",
                "grand_total": "Infinity",
                "currency": "euros",
            },
        )

        draft = ground_extracted_fields(
            parse_invoice_extraction_response(response),
            raw_text_length=10,
            origin=FieldOrigin.TEXT_LAYER,
        )

        for contract in INVOICE_FIELD_CONTRACTS:
            assert getattr(draft, contract.field_name) is None, contract.field_name

    def test_an_ambiguous_thousands_reading_is_dropped_rather_than_chosen(self) -> None:
        response = json.dumps({"taxable_base": "1.234", "grand_total": "121,00"})

        draft = ground_extracted_fields(
            parse_invoice_extraction_response(response),
            raw_text_length=10,
            origin=FieldOrigin.TEXT_LAYER,
        )

        assert draft.taxable_base is None
        assert draft.grand_total == Decimal("121")


class TestTheDefaultPeriodIsDerivedNotGuessed:
    """The fallback coordinate is the current civil year's annual period."""

    def test_the_default_is_the_current_annual_period(self) -> None:
        from ...core.time import today_madrid

        period = default_extraction_period()

        assert period.filing_year == today_madrid().year
        assert str(period.code) == "0A"

    def test_the_annual_default_unions_every_rate_in_force_that_year(self) -> None:
        """An annual span never omits a rate a mid-year statute introduced."""
        annual = build_invoice_extraction_prompt(period=Period.from_year_and_code(2024, "0A"))
        q3 = build_invoice_extraction_prompt(period=Period.from_year_and_code(2024, "3T"))

        assert set(q3.iva_rate_pcts) <= set(annual.iva_rate_pcts)
        assert Decimal("7.5") in annual.iva_rate_pcts
        assert Decimal("7.5") not in q3.iva_rate_pcts
