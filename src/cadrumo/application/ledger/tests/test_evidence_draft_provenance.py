"""The per-field provenance envelope and the widened draft, gated end to end.

Three obligations are proven here rather than asserted in prose:

**A populated draft survives a real serialization round trip unchanged.** Every
defaultable field carries a NON-default value, because a save-drops-field /
load-re-defaults-field regression is structurally invisible when the fixture
uses the defaults it is meant to detect the loss of.

**The envelope cannot make a claim it does not support.** An anchored field
without an anchor, an ambiguous field without competing candidates, candidates
recorded under a decided outcome, an envelope naming a field the draft does not
have, and two envelopes for one field are each refused.

**The anti-tautology proof.** A field is deleted from the serialized payload and
the reload is asserted to differ from the original -- so if the round trip ever
passes with the boundary broken, this test says so instead of quietly agreeing.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import DraftDiscrepancyKind, FieldGroundingOutcome, FieldOrigin
from ....domain.iva import InvoiceKind, SupplyNature
from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha3
from ..evidence_draft import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
    InvoiceDraftLine,
    InvoiceDraftRateBreakdown,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TRANSCRIPTION_SHA = "b" * 64


def _fully_populated_draft() -> InvoiceDraft:
    """Return a draft with every defaultable field set to a non-default value."""
    return InvoiceDraft(
        supplier_tax_id="B12345674",
        supplier_name="Proveedor Ejemplo SL",
        customer_tax_id="X1234567L",
        customer_name="Cliente Ejemplo SL",
        # Off-default and DIFFERENT from each other: two parties sharing one
        # code would let a projection that carried only the supplier's satisfy
        # a value comparison the customer's silently failed.
        supplier_postal_code="35001",
        customer_postal_code="28013",
        # Off-default and party-DISTINCT for the same reason the codes are, and
        # deliberately naming two different countries: a projection carrying only
        # the supplier's country would satisfy a comparison the customer's had
        # silently failed, and two parties sharing one name could not fail it at
        # all.
        supplier_country="España",
        customer_country="Alemania",
        # The structured spelling of the same rung, party-distinct for the same
        # reason. Deliberately NOT the codes the two names above resolve to: a
        # projection that dropped a code field and rebuilt it from the name
        # would satisfy a comparison against matching values, and these do not
        # match, so only a genuine carry survives.
        supplier_country_code="PT",
        customer_country_code="FR",
        # The verbatim token each record stated, in a spelling the resolved code
        # beside it could never be rebuilt from and never rebuild: an alpha-3 the
        # vocabulary places, and an alpha-3 it does not. A projection that
        # dropped either and re-derived it from its neighbour would satisfy a
        # comparison against matching values, and none of these four match.
        supplier_stated_country_code="PRT",
        customer_stated_country_code=an_uncatalogued_alpha3(),
        invoice_number="0042",
        invoice_series="FA",
        rectifies_invoice_number="0028",
        proposed_supply_nature=SupplyNature.SERVICES,
        invoice_date="2026-03-14",
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("210.00"),
        grand_total=Decimal("1262.00"),
        currency="EUR",
        regime_legend="régimen especial del criterio de caja",
        recargo_amount=Decimal("52.00"),
        retencion_rate=Decimal("15"),
        retencion_amount=Decimal("150.00"),
        suplidos_amount=Decimal("30.00"),
        lines=(
            InvoiceDraftLine(
                description="Servicio de consultoría",
                quantity=Decimal("2"),
                unit_price=Decimal("500.00"),
                taxable_base=Decimal("1000.00"),
                iva_rate=Decimal("21"),
                iva_amount=Decimal("210.00"),
                recargo_rate=Decimal("5.2"),
                recargo_amount=Decimal("52.00"),
            ),
        ),
        iva_breakdown=(
            InvoiceDraftRateBreakdown(
                iva_rate=Decimal("21"),
                taxable_base=Decimal("1000.00"),
                iva_amount=Decimal("210.00"),
                recargo_rate=Decimal("5.2"),
                recargo_amount=Decimal("52.00"),
            ),
        ),
        iva_category="standard",
        suggested_kind=InvoiceKind.RECEIVED,
        transcription_sha256=_TRANSCRIPTION_SHA,
        provenance=(
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.RECONCILED,
                anchor="1.000,00 €",
                note="closes against the printed total",
            ),
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.VISION,
                grounding=FieldGroundingOutcome.AMBIGUOUS,
                anchor="B-12345674",
                candidates=(
                    FieldAmbiguityCandidate(value="B12345674", anchor="B-12345674", note="issuer block"),
                    FieldAmbiguityCandidate(value="X1234567L", anchor="X-1234567-L", note="footer block"),
                ),
                # Populated non-default so the projection gate exercises a real
                # value rather than agreeing that two ``None``s match: a
                # save-drops-field regression is invisible over a defaulted one.
                role_evidence="Proveedor:",
                note="two identifiers, neither uniquely role-evidenced",
            ),
            FieldProvenance(
                field="currency",
                origin=FieldOrigin.OPERATOR,
                grounding=FieldGroundingOutcome.UNANCHORED,
                # Populated non-default for the same reason role_evidence above
                # is: a refusal dropped on save and re-defaulted to ``None`` on
                # load compares equal to a fixture that never carried one, and
                # the round trip would agree that two absences match.
                refused_anchor="EUROS",
                note="supplied at review; the document prints no code",
            ),
        ),
        discrepancies=(
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                field="grand_total",
                detail="base plus cuota plus recargo does not reach the printed total",
                expected=Decimal("1262.00"),
                observed=Decimal("1232.00"),
            ),
            DraftDiscrepancyFinding(
                kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                field="supplier_tax_id",
                detail="issuer and recipient are not separable from the document",
            ),
        ),
        raw_text_length=4096,
    )


def test_every_defaultable_field_is_populated_off_default() -> None:
    """The fixture itself is gated, or the round trip below proves nothing.

    A round trip over a fixture that happens to use defaults cannot detect a
    field dropped on save and re-defaulted on load: both sides read the same
    default and compare equal. This asserts the fixture actually differs from a
    bare draft on every field that has a default.
    """
    draft = _fully_populated_draft()
    bare = InvoiceDraft()

    defaulted = {name for name, info in InvoiceDraft.model_fields.items() if not info.is_required()}
    assert defaulted, "InvoiceDraft has no defaultable fields; this gate is misdirected"

    still_default = {name for name in defaulted if getattr(draft, name) == getattr(bare, name)}
    assert not still_default, f"fixture leaves these fields at their default: {sorted(still_default)}"


def test_populated_draft_survives_a_real_json_round_trip() -> None:
    """Strict equality across a genuine JSON-text cycle, not a dict comparison."""
    draft = _fully_populated_draft()

    reloaded = InvoiceDraft.model_validate_json(draft.model_dump_json())

    assert reloaded == draft


def test_a_dropped_field_is_surfaced_rather_than_re_defaulted() -> None:
    """Anti-tautology: break the payload on purpose and require the boundary to notice.

    Deleting a defaultable field from the serialized document is the exact shape
    of a save-drops-field regression. The reload must not compare equal to the
    original -- if it did, every round trip in this module would be vacuous.
    """
    draft = _fully_populated_draft()
    payload = json.loads(draft.model_dump_json())
    del payload["retencion_amount"]

    reloaded = InvoiceDraft.model_validate_json(json.dumps(payload))

    assert reloaded != draft
    assert reloaded.retencion_amount is None


def test_an_unknown_serialized_field_is_refused_not_absorbed() -> None:
    """The draft is ``extra="forbid"``; a stray key raises rather than vanishing."""
    payload = json.loads(_fully_populated_draft().model_dump_json())
    payload["model_confidence"] = 0.93

    with pytest.raises(ValidationError, match="model_confidence"):
        InvoiceDraft.model_validate_json(json.dumps(payload))


def test_the_draft_carries_no_numeric_confidence_axis() -> None:
    """No field on the draft family may hold a model's opinion of its own output.

    Gated on the property rather than on a field tally: any future field whose
    name reads as a self-reported score fails here. A model's confidence in its
    own output is never a substitute for grounded verification and must not be
    persisted as if it were one.
    """
    forbidden = ("confidence", "score", "probability", "certainty", "likelihood")
    for model in (InvoiceDraft, FieldProvenance, FieldAmbiguityCandidate, DraftDiscrepancyFinding):
        offending = [name for name in model.model_fields if any(token in name.lower() for token in forbidden)]
        assert not offending, f"{model.__name__} carries a self-reported confidence axis: {offending}"


def test_an_anchored_field_must_show_its_anchor() -> None:
    with pytest.raises(ValidationError, match="anchored"):
        FieldProvenance(
            field="taxable_base",
            origin=FieldOrigin.TEXT_LAYER,
            grounding=FieldGroundingOutcome.ANCHORED,
        )


def test_an_ambiguous_field_must_record_competing_candidates() -> None:
    with pytest.raises(ValidationError, match="two competing candidates"):
        FieldProvenance(
            field="supplier_tax_id",
            origin=FieldOrigin.VISION,
            grounding=FieldGroundingOutcome.AMBIGUOUS,
            candidates=(FieldAmbiguityCandidate(value="B12345674"),),
        )


def test_candidates_under_a_decided_outcome_are_refused() -> None:
    with pytest.raises(ValidationError, match="only meaningful for an ambiguous field"):
        FieldProvenance(
            field="supplier_tax_id",
            origin=FieldOrigin.VISION,
            grounding=FieldGroundingOutcome.RECONCILED,
            candidates=(
                FieldAmbiguityCandidate(value="B12345674"),
                FieldAmbiguityCandidate(value="X1234567L"),
            ),
        )


def test_provenance_naming_a_field_the_draft_lacks_is_refused() -> None:
    """A stale envelope points at nothing; it must not validate silently."""
    with pytest.raises(ValidationError, match="unknown draft field"):
        InvoiceDraft(
            provenance=(
                FieldProvenance(
                    field="vendor_iva_number",
                    origin=FieldOrigin.TABULAR_MAPPED,
                    grounding=FieldGroundingOutcome.UNANCHORED,
                ),
            ),
        )


def test_two_envelopes_for_one_field_are_refused() -> None:
    """Two provenance claims for one value leave no answer to which is the record's."""
    envelope = FieldProvenance(
        field="iva_amount",
        origin=FieldOrigin.TEXT_LAYER,
        grounding=FieldGroundingOutcome.UNANCHORED,
    )

    with pytest.raises(ValidationError, match="two envelopes"):
        InvoiceDraft(provenance=(envelope, envelope))


def test_a_short_transcription_address_is_refused() -> None:
    """The content address is a full SHA-256; a truncated one addresses nothing."""
    with pytest.raises(ValidationError):
        InvoiceDraft(transcription_sha256="b" * 40)


class TestADerivedValueCitesItsInputsRatherThanAnAnchor:
    """A conclusion has no printed form, so it shows its working instead.

    ``DERIVED`` is the one origin that is not a reading. Every other member
    answers how a value was copied off the document; this one answers what
    followed from what was copied. The envelope has to keep that distinguishable,
    because an auditor checking a derived value must be sent to its inputs rather
    than to a phrase on the page that was never there.
    """

    def test_a_derived_value_cannot_claim_it_was_anchored(self) -> None:
        """An ANCHORED stamp would assert a printed form that does not exist."""
        with pytest.raises(ValidationError):
            FieldProvenance(
                field="iva_category",
                origin=FieldOrigin.DERIVED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="inversión del sujeto pasivo",
                derived_from=("regime_legend",),
            )

    def test_a_derived_value_must_record_the_inputs_it_followed_from(self) -> None:
        """Without them the record claims a conclusion it cannot show working for."""
        with pytest.raises(ValidationError):
            FieldProvenance(
                field="iva_category",
                origin=FieldOrigin.DERIVED,
                grounding=FieldGroundingOutcome.UNANCHORED,
            )

    def test_inputs_recorded_under_a_reading_origin_are_refused(self) -> None:
        """They would describe a derivation that did not happen."""
        with pytest.raises(ValidationError):
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.UNANCHORED,
                derived_from=("regime_legend",),
            )

    def test_a_well_formed_derived_envelope_is_accepted(self) -> None:
        """The positive case, so the three refusals above are not vacuous."""
        envelope = FieldProvenance(
            field="iva_category",
            origin=FieldOrigin.DERIVED,
            grounding=FieldGroundingOutcome.UNANCHORED,
            derived_from=("regime_legend", "iva_rate", "iva_amount"),
        )

        assert envelope.anchor is None
        assert envelope.derived_from == ("regime_legend", "iva_rate", "iva_amount")
