"""Encrypted confirmation-record repository integration at the profile adapter seam.

The application tests keep the assertion and record-model contracts inward. These
tests bind the concrete encrypted repository boundary directly, so a serializer
or persistence regression cannot hide behind an application fake.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from cadrumo.application.ledger.confirmation_record import (
    load_confirmation_records,
    write_confirmation_record,
)
from cadrumo.application.ledger.tests.confirmation_record_support import (
    CONFIRMATION_BUCKET_ID,
    CONFIRMATION_EVIDENCE_SHA,
    CONFIRMATION_TRANSCRIPTION_SHA,
    populated_confirmation_record,
)
from cadrumo.core.confirmation_gate import FindingResolutionAction
from cadrumo.core.field_origin import FieldOrigin

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Provide a real isolated runtime profile with its encrypted SQLite engine."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=CONFIRMATION_BUCKET_ID) as resolved:
        yield resolved


def test_the_confirmation_record_survives_the_real_encrypted_boundary(profile: TestRuntimeProfile) -> None:
    """Strict equality across the real store, every defaultable field non-default.

    Asserted against the real encrypted namespace rather than a JSON round trip:
    the serializer is not the boundary that matters, the repository is, and a
    field the repository declines to persist would round-trip through JSON
    perfectly.
    """
    record = populated_confirmation_record().model_copy(update={"bucket_id": profile.bucket_id})

    write_confirmation_record(record=record, settings=profile.settings)
    reloaded = load_confirmation_records(profile.bucket_id, profile.settings)

    assert reloaded.records == (record,), "the boundary must return exactly what crossed it"
    stored = reloaded.records[0]
    assert stored.evidence_sha256 == CONFIRMATION_EVIDENCE_SHA
    assert stored.transcription_sha256 == CONFIRMATION_TRANSCRIPTION_SHA
    # The prior value and origin are the point of the record; they are nested two
    # levels deep, which is exactly what a flattening boundary loses.
    assert stored.assertions[0].prior_value == "100.00"
    assert stored.assertions[0].prior_origin is FieldOrigin.VISION
    assert stored.assertions[0].asserted_value == "150.00"
    assert stored.resolutions[0].resolution.action is FindingResolutionAction.CHOOSE_CANDIDATE
    assert stored.resolutions[0].blocker.candidate_values == ("ESB00015016", "ESX0001500M")


def test_a_retried_confirmation_addresses_the_stored_record_rather_than_appending(
    profile: TestRuntimeProfile,
) -> None:
    """One human decision, one record, however many times the call is retried."""
    record = populated_confirmation_record().model_copy(update={"bucket_id": profile.bucket_id})

    write_confirmation_record(record=record, settings=profile.settings)
    write_confirmation_record(record=record, settings=profile.settings)

    assert len(load_confirmation_records(profile.bucket_id, profile.settings).records) == 1
