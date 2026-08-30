"""The regime legend: transcribed, never chosen, and its vocabulary never restated.

Stage 2 emits no category. An ``IvaCategory`` token is printed on no invoice, so a
model asked for one has nothing to copy and must infer -- inside the stage whose
whole guarantee is that values are copied and never computed. What the paper DOES
carry is the mention Spanish law obliges the issuer to print, and a phrase can be
copied.

Two properties are gated here, and they are different in kind.

The first is GROUNDING, proven mechanically rather than attested. The declared
phrases are compared against the guillemet-quoted mentions in the bundled
consolidated text of the regulation, as sets, in both directions. An author
saying "these are verbatim" is exactly the claim that cannot be trusted about
itself; a set equality against the shipped corpus can be re-run by anyone.

The second is NON-RESTATEMENT, on the prose axis. The numeric literal scan cannot
see a statutory phrase written into the template, because a phrase is not a
digit: the rate gate reports clean over a second, silently diverging copy of the
legal vocabulary living inside the prompt. So the scan has a counterpart, and
that counterpart is pointed at the REGISTERED template rather than at a module
constant -- the trap the numeric scan was already caught in once, where a control
proved the detector worked while never proving the gate was aimed at the artefact
that ships.

Model-free and network-free throughout: compiled text, a bundled file, and the
real parser.

See Also:
    :data:`~domain.iva.REGIME_LEGENDS`
        The single declaration both the prompt and the classifier derive from.
"""

from __future__ import annotations

import html
import json
import pathlib
import re
from typing import Final

import pytest

from ...core import FieldOrigin
from ...domain.iva.regime_legend import REGIME_LEGENDS, RegimeLegend, regime_legend_phrases
from ...domain.iva.schema import IvaCategory
from ...tests.attribute_scope import scoped_attribute
from .. import invoice_extraction_prompt as _invoice_extraction_prompt
from ..invoice_extraction_prompt import (
    INVOICE_EXTRACTION_PROMPT_ID,
    build_invoice_extraction_prompt,
    default_extraction_period,
    invoice_extraction_prompt_registry,
    template_numeric_literals,
    template_unsourced_legend_phrases,
)
from ..invoice_field_contract import INVOICE_FIELD_CONTRACTS, anchor_key_for_field
from ..invoice_field_grounding import (
    ExtractedFieldAnchors,
    ExtractedInvoiceFields,
    ground_extracted_fields,
    parse_invoice_extraction_response,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


#: The bundled consolidated text of the invoicing regulation's art. 6.
_REGULATION: Final[pathlib.Path] = (
    pathlib.Path(__file__).resolve().parents[2] / "_data" / "corpus" / "normatives" / "html" / "rd-1619-2012-art-6.html"
)

_GUILLEMET_QUOTED: Final[re.Pattern[str]] = re.compile("«([^»]+)»")


def _corpus_mandated_mentions() -> set[str]:
    """Return every phrase the bundled regulation puts in guillemets."""
    markup = _REGULATION.read_text(encoding="utf-8")
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return set(_GUILLEMET_QUOTED.findall(re.sub(r"\s+", " ", text)))


class TestTheVocabularyIsQuotedFromTheBundledRegulation:
    """Grounding proven against the shipped text, not asserted by its author."""

    def test_the_bundled_regulation_is_present_and_states_its_mentions(self) -> None:
        """Positive control: without this the set comparisons could pass on emptiness."""
        assert _REGULATION.is_file()
        assert _corpus_mandated_mentions(), "the corpus must actually carry quoted mentions"

    def test_the_declaration_equals_the_corpus_mentions_in_both_directions(self) -> None:
        """No phrase invented, and none of the regulation's dropped."""
        assert set(regime_legend_phrases()) == _corpus_mandated_mentions()

    @pytest.mark.parametrize("legend", REGIME_LEGENDS, ids=lambda legend: legend.provision)
    def test_every_declared_phrase_occurs_verbatim_in_the_bundled_text(self, legend: RegimeLegend) -> None:
        """Per row, so a failure names the provision rather than a set difference."""
        assert legend.phrase in _corpus_mandated_mentions()

    def test_the_reverse_charge_mention_is_the_one_that_declares_a_category(self) -> None:
        """Fixture anchor: pinned by member, so a rename cannot pass this vacuously.

        Also pins the deliberate sparseness. Only this mention fixes the
        operation's category on its own; the rest are obligations about the
        billing arrangement or a special regime's accounting. A future row
        claiming a category must earn it from the regulation, not from
        convenience.
        """
        declaring = {legend.phrase: legend.declares for legend in REGIME_LEGENDS if legend.declares is not None}

        assert declaring == {"inversión del sujeto pasivo": IvaCategory.DOMESTIC_REVERSE_CHARGE}

    def test_the_reverse_charge_mention_expects_no_repercutido_line(self) -> None:
        """The signal a contradiction check needs: this invoice charges no Spanish IVA."""
        reverse_charge = next(legend for legend in REGIME_LEGENDS if legend.declares is not None)

        assert reverse_charge.expects_repercutido_line is False


class TestThePromptCopiesTheLegendAndNeverChoosesOne:
    """A closed list offered as a recognition aid, not as a menu."""

    def test_every_declared_phrase_reaches_the_compiled_prompt(self) -> None:
        text = build_invoice_extraction_prompt(period=default_extraction_period()).text

        for phrase in regime_legend_phrases():
            assert phrase in text

    def test_the_instruction_is_to_copy_and_explicitly_not_to_pick(self) -> None:
        """The one sentence separating a recognition aid from a classification task."""
        text = build_invoice_extraction_prompt(period=default_extraction_period()).text

        assert "copy it into regime_legend exactly as printed" in text
        assert "Never pick the closest phrase" in text
        assert "never write one the document does not show" in text

    def test_no_iva_category_token_is_offered_for_selection(self) -> None:
        """Stage 2 emits no category, so its prompt has no business enumerating one.

        The no-printed-tax line renders category tokens as spaced words for a
        different purpose -- naming why a document may carry no tax -- so this
        asserts the machine-readable token form is absent rather than the words.
        """
        text = build_invoice_extraction_prompt(period=default_extraction_period()).text

        for category in IvaCategory:
            assert category.value not in text, f"{category.value} is a stored token, printed on no invoice"


class TestTheProseScanCatchesARestatedVocabulary:
    """The numeric scan's blind spot, closed and proven to bite.

    A statutory phrase hardcoded in the template carries no digits, so the rate
    gate passes over it while a second copy of the legal vocabulary ships inside
    the prompt and drifts the moment the regulation's list moves.
    """

    def test_the_registered_template_restates_no_declared_phrase(self) -> None:
        assert template_unsourced_legend_phrases() == ()

    def test_the_numeric_scan_is_blind_to_this_class(self) -> None:
        """Why a second scan exists at all, stated as a measurement.

        The planted phrase carries no digit, so the numeric gate reports clean on
        the very text the prose gate rejects. Without this the second scan looks
        like duplication of the first.
        """
        planted = f"- always print {regime_legend_phrases()[0]} here."

        assert template_numeric_literals(planted) == ()
        assert template_unsourced_legend_phrases(planted) == (regime_legend_phrases()[0],)

    def test_the_scan_reds_on_a_phrase_planted_in_the_registered_template(self) -> None:
        """Aimed at the artefact that ships, not at a module constant.

        This is the distinction the numeric gate's own control missed: proving a
        detector matches a string says nothing about whether the gate reads the
        template the compiler will actually use.
        """
        assert template_unsourced_legend_phrases() == (), "positive control: green before the mutation"

        registry = invoice_extraction_prompt_registry()
        definition = registry.get(INVOICE_EXTRACTION_PROMPT_ID)
        phrase = regime_legend_phrases()[0]
        poisoned = definition.model_copy(update={"template": f"{definition.template}\n- {phrase}"})
        mutated = type(registry)()
        mutated.register(poisoned)
        with scoped_attribute(_invoice_extraction_prompt, "invoice_extraction_prompt_registry", lambda: mutated):
            assert template_unsourced_legend_phrases() == (phrase,)

    def test_the_scan_is_case_folded_rather_than_variant_listed(self) -> None:
        """A document shouting the mention is the same mention.

        Folding rather than enumerating spellings keeps one declaration: a
        variants list would be a second vocabulary drifting against the first.
        """
        assert template_unsourced_legend_phrases(regime_legend_phrases()[0].upper()) == (regime_legend_phrases()[0],)


class TestTheLegendIsTranscribedLikeEveryOtherCopiedField:
    """Parity: declared once, asked for, mirrored by an anchor, carried to the draft."""

    def test_the_field_is_declared_asked_for_and_anchored(self) -> None:
        text = build_invoice_extraction_prompt(period=default_extraction_period()).text

        assert "regime_legend" in {contract.field_name for contract in INVOICE_FIELD_CONTRACTS}
        assert '"regime_legend"' in text
        assert f'"{anchor_key_for_field("regime_legend")}"' in text
        assert "regime_legend" in ExtractedInvoiceFields.model_fields
        assert "regime_legend" in ExtractedFieldAnchors.model_fields

    def test_a_printed_legend_survives_to_the_draft_with_its_anchor(self) -> None:
        """Populated non-default, through the real parser and the real grounder."""
        response = parse_invoice_extraction_response(
            json.dumps(
                {
                    "regime_legend": "inversión del sujeto pasivo",
                    "regime_legend_anchor": "Operación con inversión del sujeto pasivo (art. 84.Uno.2.º LIVA)",
                },
            ),
        )

        draft = ground_extracted_fields(response, raw_text_length=512, origin=FieldOrigin.VISION)

        assert draft.regime_legend == "inversión del sujeto pasivo"
        anchors = {envelope.field: envelope.anchor for envelope in draft.provenance}
        assert anchors["regime_legend"] == "Operación con inversión del sujeto pasivo (art. 84.Uno.2.º LIVA)"

    def test_an_unprinted_legend_yields_no_value_and_no_envelope(self) -> None:
        """Absence stays absent: nothing defaults a regime onto a plain invoice."""
        response = parse_invoice_extraction_response(json.dumps({"taxable_base": "100,00"}))

        draft = ground_extracted_fields(response, raw_text_length=512, origin=FieldOrigin.VISION)

        assert draft.regime_legend is None
        assert "regime_legend" not in {envelope.field for envelope in draft.provenance}

    def test_the_draft_carries_no_category_from_the_reading_stage(self) -> None:
        """The ruling's boundary, pinned where it would be crossed.

        The draft has a category slot for the downstream classifier to fill. What
        must never happen is the READING stage populating it, so this proves a
        response carrying a legend leaves the category untouched.
        """
        response = parse_invoice_extraction_response(
            json.dumps({"regime_legend": "inversión del sujeto pasivo", "regime_legend_anchor": "inversión..."}),
        )

        draft = ground_extracted_fields(response, raw_text_length=512, origin=FieldOrigin.VISION)

        assert draft.regime_legend is not None
        assert draft.iva_category is None
