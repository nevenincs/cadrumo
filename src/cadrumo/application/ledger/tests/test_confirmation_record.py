"""A correction is an assertion, and the confirmation itself is a record.

Two claims are proved here.

**The assertion claim.** An operator override re-stamps the field
:attr:`~core.FieldOrigin.OPERATOR` on the confirmed view WHILE the confirmation
record retains the prior value and the prior origin. Both halves must survive
together: a record keeping only the new value cannot answer what the document
said, and a confirmed view still showing the document's origin would present the
operator's figure as something the document stated.

**The record claim.** The confirmation record crosses the real encrypted
boundary by strict equality with every defaultable field populated NON-default,
because a save-drops-field / load-re-defaults-field regression is invisible when
the fixture uses defaults --- and an anti-tautology proof reddens the load when a
persisted field is deleted, without which every equality assertion here would
prove only that two objects are equal.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ._confirmation_profile_fixture import profile

__all__ = ["profile"]

from ....core import (
    ConfirmationBlockReason,
    FieldGroundingOutcome,
    FieldOrigin,
    FindingResolutionAction,
)
from ....tests.secure_sql import TestRuntimeProfile
from ..confirmation_gate import ConfirmationBlocker, FindingResolution
from ..confirmation_record import (
    ConfirmationRecordDocument,
    FieldAssertion,
    InvoiceConfirmationRecord,
    ResolvedFinding,
    build_confirmation_record,
    field_assertions,
    load_confirmation_records,
    re_stamped_provenance,
    write_confirmation_record,
)
from ..evidence_draft import FieldAmbiguityCandidate, FieldProvenance, InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_TRANSCRIPTION_SHA = "a" * 64
_EVIDENCE_SHA = "b" * 64
_INVOICE_ID = "c" * 64


def _read_draft() -> InvoiceDraft:
    """A draft whose overridden fields each carry a DISTINCT prior origin.

    The origins differ on purpose. "The operator corrected an exactly-read
    structured field" and "the operator corrected a vision guess" are not the
    same event, and a fixture using one origin throughout could not tell a record
    that retains the origin from one that stamps a constant.
    """
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        supplier_name="Proveedor Ejemplo SL",
        invoice_number="PROV-2024-0001",
        invoice_date="2024-11-15",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        transcription_sha256=_TRANSCRIPTION_SHA,
        provenance=(
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.RECONCILED,
                anchor="ESB12345674",
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
        overrides={"taxable_base": Decimal("150.00"), "supplier_tax_id": "ESX1234567L"},
    )

    by_field = {assertion.field: assertion for assertion in assertions}
    assert by_field["taxable_base"].prior_value == "100.00"
    assert by_field["taxable_base"].prior_origin is FieldOrigin.VISION
    assert by_field["taxable_base"].asserted_value == "150.00"
    assert by_field["supplier_tax_id"].prior_value == "ESB12345674"
    assert by_field["supplier_tax_id"].prior_origin is FieldOrigin.EXACT_STRUCTURED
    assert by_field["supplier_tax_id"].asserted_value == "ESX1234567L"

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
    assert stamped["supplier_tax_id"].anchor == "ESB12345674"


def test_silence_is_not_an_assertion() -> None:
    """An override the operator did not supply records nothing at all."""
    assert field_assertions(draft=_read_draft(), overrides={"taxable_base": None, "currency": None}) == ()


def test_a_supplied_value_where_the_document_was_silent_records_no_prior_origin() -> None:
    """Supplying and correcting are different acts and the record distinguishes them."""
    draft = _read_draft().model_copy(update={"customer_tax_id": None})

    assertions = field_assertions(draft=draft, overrides={"customer_tax_id": "ESX1234567L"})

    assert assertions[0].prior_value is None
    assert assertions[0].prior_origin is None
    assert assertions[0].asserted_value == "ESX1234567L"


def _populated_record() -> InvoiceConfirmationRecord:
    """A record with EVERY defaultable field populated off its default.

    ``evidence_sha256``, ``transcription_sha256``, ``assertions`` and
    ``resolutions`` all default; a fixture leaving any of them defaulted would
    roundtrip identically whether the store persisted it or dropped it.
    """
    blocker = ConfirmationBlocker(
        blocker_id="0123456789abcdef",
        reason=ConfirmationBlockReason.AMBIGUOUS_IDENTITY,
        field="supplier_tax_id",
        detail="two tax ids printed on the same document",
        candidates=(
            FieldAmbiguityCandidate(value="ESB12345674", anchor="NIF: ESB12345674", note="header block"),
            FieldAmbiguityCandidate(value="ESX1234567L", anchor="ESX1234567L", note="footer block"),
        ),
    )
    return InvoiceConfirmationRecord(
        confirmation_id="fedcba9876543210",
        bucket_id=_BUCKET_ID,
        invoice_id=_INVOICE_ID,
        evidence_reference="ev-structured-001",
        evidence_sha256=_EVIDENCE_SHA,
        transcription_sha256=_TRANSCRIPTION_SHA,
        extractor="exact_structured",
        confirmed_by="gestor@example.test",
        confirmed_at=datetime(2024, 11, 15, 9, 0, tzinfo=UTC),
        assertions=(
            FieldAssertion(
                field="taxable_base",
                asserted_value="150.00",
                prior_value="100.00",
                prior_origin=FieldOrigin.VISION,
                prior_grounding=FieldGroundingOutcome.ANCHORED,
            ),
        ),
        resolutions=(
            ResolvedFinding(
                blocker=blocker,
                resolution=FindingResolution(
                    blocker_id="0123456789abcdef",
                    action=FindingResolutionAction.CHOOSE_CANDIDATE,
                    value="ESX1234567L",
                    note="matched against the paper invoice header",
                ),
            ),
        ),
    )


def test_the_confirmation_record_survives_the_real_encrypted_boundary(profile: TestRuntimeProfile) -> None:
    """Strict equality across the real store, every defaultable field non-default.

    Asserted against the real encrypted namespace rather than a JSON round trip:
    the serializer is not the boundary that matters, the repository is, and a
    field the repository declines to persist would round-trip through JSON
    perfectly.
    """
    record = _populated_record().model_copy(update={"bucket_id": profile.bucket_id})

    write_confirmation_record(record=record, settings=profile.settings)
    reloaded = load_confirmation_records(profile.bucket_id, profile.settings)

    assert reloaded.records == (record,), "the boundary must return exactly what crossed it"
    stored = reloaded.records[0]
    assert stored.evidence_sha256 == _EVIDENCE_SHA
    assert stored.transcription_sha256 == _TRANSCRIPTION_SHA
    # The prior value and origin are the point of the record; they are nested two
    # levels deep, which is exactly what a flattening boundary loses.
    assert stored.assertions[0].prior_value == "100.00"
    assert stored.assertions[0].prior_origin is FieldOrigin.VISION
    assert stored.assertions[0].asserted_value == "150.00"
    assert stored.resolutions[0].resolution.action is FindingResolutionAction.CHOOSE_CANDIDATE
    assert stored.resolutions[0].blocker.candidate_values == ("ESB12345674", "ESX1234567L")


def test_a_retried_confirmation_addresses_the_stored_record_rather_than_appending(
    profile: TestRuntimeProfile,
) -> None:
    """One human decision, one record, however many times the call is retried."""
    record = _populated_record().model_copy(update={"bucket_id": profile.bucket_id})

    write_confirmation_record(record=record, settings=profile.settings)
    write_confirmation_record(record=record, settings=profile.settings)

    assert len(load_confirmation_records(profile.bucket_id, profile.settings).records) == 1


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
            bucket_id=_BUCKET_ID,
            invoice_id=_INVOICE_ID,
            evidence_reference="ev-structured-001",
            evidence_sha256=_EVIDENCE_SHA,
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
    document = ConfirmationRecordDocument(bucket_id=_BUCKET_ID, records=(_populated_record(),))

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
