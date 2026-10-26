"""Encrypted confirmation-record repository integration at the profile adapter seam.

The application tests keep the assertion and record-model contracts inward. These
tests bind the concrete encrypted repository boundary directly, so a serializer
or persistence regression cannot hide behind an application fake.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.ledger.confirmation_gate import ConfirmationBlocker, FindingResolution
from cadrumo.application.ledger.confirmation_record import (
    FieldAssertion,
    InvoiceConfirmationRecord,
    ResolvedFinding,
    load_confirmation_records,
    write_confirmation_record,
)
from cadrumo.application.ledger.invoice_draft_records import FieldAmbiguityCandidate
from cadrumo.core.confirmation_gate import ConfirmationBlockReason, FindingResolutionAction
from cadrumo.core.field_grounding import FieldGroundingOutcome
from cadrumo.core.field_origin import FieldOrigin

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"
_TRANSCRIPTION_SHA = "a" * 64
_EVIDENCE_SHA = "b" * 64
_INVOICE_ID = "c" * 64


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Provide a real isolated runtime profile with its encrypted SQLite engine."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as resolved:
        yield resolved


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
