"""A correction is an assertion, and the confirmation itself is a record.

Two claims are proved here.

**The assertion claim.** An operator override re-stamps the field
:attr:`~core.FieldOrigin.OPERATOR` on the confirmed view WHILE the confirmation
record retains the prior value and the prior origin. Both halves must survive
together: a record keeping only the new value cannot answer what the document
said, and a confirmed view still showing the document's origin would present the
operator's figure as something the document stated.

**The record claim.** The confirmation record's model and serialization contract
remain application-owned; its encrypted repository boundary is exercised at the
profile persistence adapter seam with every defaultable field populated NON-default.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.confirmation_gate import ConfirmationBlockReason, FindingResolutionAction
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ..confirmation_gate import ConfirmationBlocker, FindingResolution
from ..confirmation_record import (
    ConfirmationRecordDocument,
    InvoiceConfirmationRecord,
    ResolvedFinding,
    build_confirmation_record,
    field_assertions,
    re_stamped_provenance,
)
from ..invoice_draft_records import FieldProvenance, InvoiceDraft
from .confirmation_record_support import (
    CONFIRMATION_BUCKET_ID,
    CONFIRMATION_EVIDENCE_SHA,
    CONFIRMATION_INVOICE_ID,
    CONFIRMATION_TRANSCRIPTION_SHA,
    populated_confirmation_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _read_draft() -> InvoiceDraft:
    """A draft whose overridden fields each carry a DISTINCT prior origin.

    The origins differ on purpose. "The operator corrected an exactly-read
    structured field" and "the operator corrected a vision guess" are not the
    same event, and a fixture using one origin throughout could not tell a record
    that retains the origin from one that stamps a constant.
    """
    return InvoiceDraft(
        supplier_tax_id="ESB00015016",
        supplier_name="Proveedor Ejemplo SL",
        invoice_number="PROV-2024-0001",
        invoice_date="2024-11-15",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        transcription_sha256=CONFIRMATION_TRANSCRIPTION_SHA,
        provenance=(
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.RECONCILED,
                anchor="ESB00015016",
                note="control character checks out",
            ),
            # Deliberately ANCHORED and carrying an anchor. A fixture whose
            # prior envelope was already UNANCHORED with no anchor would make
            # "an operator value is never stamped ANCHORED" pass without the
            # re-stamp running at all.
            FieldProvenance(
                field="taxable_base",
                origin=FieldOrigin.VISION,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="100,00",
                note="read off the rendered page",
            ),
        ),
    )


def test_an_override_re_stamps_operator_while_the_record_keeps_the_prior_value() -> None:
    """Both halves of "a correction is an assertion", asserted together.

    Either half alone is satisfiable by a broken implementation: re-stamping
    without retaining is an edit that erased its own history, and retaining
    without re-stamping leaves the operator's figure reading as a document
    reading.
    """
    draft = _read_draft()

    assertions = field_assertions(
        draft=draft,
        overrides={"taxable_base": Decimal("150.00"), "supplier_tax_id": "ESX0001500M"},
    )

    by_field = {assertion.field: assertion for assertion in assertions}
    assert by_field["taxable_base"].prior_value == "100.00"
    assert by_field["taxable_base"].prior_origin is FieldOrigin.VISION
    assert by_field["taxable_base"].asserted_value == "150.00"
    assert by_field["supplier_tax_id"].prior_value == "ESB00015016"
    assert by_field["supplier_tax_id"].prior_origin is FieldOrigin.EXACT_STRUCTURED
    assert by_field["supplier_tax_id"].asserted_value == "ESX0001500M"

    confirmed = re_stamped_provenance(draft=draft, assertions=assertions)
    stamped = {envelope.field: envelope for envelope in confirmed}
    assert stamped["taxable_base"].origin is FieldOrigin.OPERATOR
    assert stamped["supplier_tax_id"].origin is FieldOrigin.OPERATOR
    # The document's own account is untouched: the re-stamp produces a SECOND
    # view rather than editing the reading in place.
    assert {envelope.field: envelope.origin for envelope in draft.provenance} == {
        "supplier_tax_id": FieldOrigin.EXACT_STRUCTURED,
        "taxable_base": FieldOrigin.VISION,
    }


def test_an_operator_value_is_never_stamped_anchored() -> None:
    """An assertion is not a reading, so it has no verbatim occurrence to anchor to."""
    draft = _read_draft()
    assertions = field_assertions(draft=draft, overrides={"taxable_base": Decimal("150.00")})

    stamped = {envelope.field: envelope for envelope in re_stamped_provenance(draft=draft, assertions=assertions)}

    assert stamped["taxable_base"].grounding is FieldGroundingOutcome.UNANCHORED
    assert stamped["taxable_base"].anchor is None


def test_a_field_the_operator_left_alone_keeps_its_reading() -> None:
    """Scope control: only asserted fields are re-stamped.

    Without this, a re-stamp that overwrote every envelope with ``OPERATOR``
    would pass the assertion test above while laundering the whole draft.
    """
    draft = _read_draft()
    assertions = field_assertions(draft=draft, overrides={"taxable_base": Decimal("150.00")})

    stamped = {envelope.field: envelope for envelope in re_stamped_provenance(draft=draft, assertions=assertions)}

    assert stamped["supplier_tax_id"].origin is FieldOrigin.EXACT_STRUCTURED
    assert stamped["supplier_tax_id"].anchor == "ESB00015016"


def test_silence_is_not_an_assertion() -> None:
    """An override the operator did not supply records nothing at all."""
    assert field_assertions(draft=_read_draft(), overrides={"taxable_base": None, "currency": None}) == ()


def test_a_supplied_value_where_the_document_was_silent_records_no_prior_origin() -> None:
    """Supplying and correcting are different acts and the record distinguishes them."""
    draft = _read_draft().model_copy(update={"customer_tax_id": None})

    assertions = field_assertions(draft=draft, overrides={"customer_tax_id": "ESX0001500M"})

    assert assertions[0].prior_value is None
    assert assertions[0].prior_origin is None
    assert assertions[0].asserted_value == "ESX0001500M"


def test_the_derived_id_is_clock_free() -> None:
    """Two confirmations of the same outcome at different moments address one record.

    An id folding the timestamp would make an idempotent retry write a second
    account of one decision, which is the shape that lets it be counted twice.
    """
    draft = _read_draft()

    def _record(taxable_base: str) -> InvoiceConfirmationRecord:
        """Build the record, varying only the one override the case turns on.

        A factory rather than a shared kwargs dict splatted in: an inferred
        dict widens every value to the union of all of them, so the splat
        checked each parameter against `str | InvoiceDraft | dict[str, Decimal]`
        -- which none of them accept -- and verified nothing about the call.
        """
        return build_confirmation_record(
            bucket_id=CONFIRMATION_BUCKET_ID,
            invoice_id=CONFIRMATION_INVOICE_ID,
            evidence_reference="ev-structured-001",
            evidence_sha256=CONFIRMATION_EVIDENCE_SHA,
            draft=draft,
            extractor="exact_structured",
            confirmed_by="gestor@example.test",
            overrides={"taxable_base": Decimal(taxable_base)},
        )

    first = _record("150.00")
    second = _record("150.00")

    assert first.confirmation_id == second.confirmation_id
    differing = _record("175.00")
    assert differing.confirmation_id != first.confirmation_id


def test_deleting_a_persisted_field_makes_the_load_refuse() -> None:
    """Anti-tautology: corrupt the stored payload, prove the load notices.

    Two arms, because the two field classes fail differently. A REQUIRED field
    (``asserted_value``) must make the load raise; a DEFAULTABLE one
    (``evidence_sha256``) cannot raise by construction, so the proof there is
    strict inequality --- the reload must not come back equal to what was saved,
    which is exactly what a silent re-default would produce.
    """
    document = ConfirmationRecordDocument(bucket_id=CONFIRMATION_BUCKET_ID, records=(populated_confirmation_record(),))

    # A JSON round-trip rather than `model_validate` on a dumped dict: the models
    # are strict, so a dict round trip is refused for presenting lists where
    # tuples are declared, and the assertion below would go green with nothing
    # deleted at all.
    intact = json.loads(document.model_dump_json())
    assert ConfirmationRecordDocument.model_validate_json(json.dumps(intact)) == document, (
        "positive control: the intact payload must survive the round-trip"
    )

    corrupted = json.loads(document.model_dump_json())
    del corrupted["records"][0]["assertions"][0]["asserted_value"]

    with pytest.raises(ValidationError, match="asserted_value"):
        ConfirmationRecordDocument.model_validate_json(json.dumps(corrupted))

    dropped = json.loads(document.model_dump_json())
    del dropped["records"][0]["evidence_sha256"]
    revived = ConfirmationRecordDocument.model_validate_json(json.dumps(dropped))

    assert revived != document, "a dropped defaultable field must not reload as the saved record"
    assert revived.records[0].evidence_sha256 is None


def test_a_resolution_paired_with_a_different_blocker_is_refused() -> None:
    """The two halves of a resolved finding must be about one finding."""
    with pytest.raises(ValidationError, match="does not answer"):
        ResolvedFinding(
            blocker=ConfirmationBlocker(
                blocker_id="0123456789abcdef",
                reason=ConfirmationBlockReason.CLOSURE_DISCREPANCY,
                detail="the printed total does not close",
            ),
            resolution=FindingResolution(
                blocker_id="fedcba9876543210",
                action=FindingResolutionAction.ATTEST,
                note="answering a different finding entirely",
            ),
        )
