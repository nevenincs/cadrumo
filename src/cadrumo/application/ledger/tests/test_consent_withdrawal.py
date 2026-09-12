"""Consent withdrawal enumerates persisted off-host history honestly.

Every case crosses the real encrypted draft store because the claim under test
is which persisted artefacts a withdrawal can see.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....tests.consent_profile_fixture import consent_profile

__all__ = ["consent_profile"]

from ....core.field_origin import FieldOrigin
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL, provenance_stamp_transport
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from ..consent_withdrawal import (
    ConsentedDispatch,
    artefact_is_cloud_derived,
    survey_cloud_consent,
)
from ..document_transcription import TranscriberIdentity
from ..extraction_draft_store import write_extraction_draft
from ..invoice_draft_records import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DIGEST = "d" * 64
_CLOUD_STAMP = "llm:openai-text-extract:gpt-4.1:rates-2026A-abcdef"
_LOCAL_STAMP = "llm:local-text-extract:qwen2.5:3b:rates-2026A-abcdef"

_TEXT_LAYER = TranscriberIdentity(
    transport=LOCAL_TRANSPORT_LABEL,
    origin=FieldOrigin.TEXT_LAYER,
    name="pdfplumber-text-layer",
    revision="0.11.4",
)


def _seed_cloud_draft(
    profile: TestRuntimeProfile,
    *,
    reference: str = "ev-1",
    stamp: str = _CLOUD_STAMP,
    transports: tuple[str, ...] = ("openai",),
) -> None:
    write_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=reference,
        draft=InvoiceDraft(),
        extractor=stamp,
        read_transports=transports,
        settings=profile.settings,
    )


# ── Reading a provenance stamp ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("stamp", "expected"),
    [
        (_CLOUD_STAMP, "openai"),
        (_LOCAL_STAMP, LOCAL_TRANSPORT_LABEL),
        ("llm:local-vision:qwen2.5vl:3b:rates-x", LOCAL_TRANSPORT_LABEL),
        ("llm:gemini-vision:gemini-2.5-pro:rates-x", "gemini"),
        ("classified_by_manual", None),
        ("llm:noseparator:model", None),
        ("", None),
    ],
)
def test_the_transport_is_read_from_the_stamp_or_reported_unknown(stamp: str, expected: str | None) -> None:
    """An unreadable stamp yields ``None``, never an optimistic ``local``."""
    assert provenance_stamp_transport(stamp) == expected


def test_an_unreadable_stamp_is_surfaced_rather_than_assumed_clean() -> None:
    """The uncertain case fails toward SHOWING the operator the artefact.

    A withdrawal that silently omits an artefact tells the operator they are
    clean when they may not be, which is the one direction this surface must
    never fail in. The cost of the other direction is one extra document to
    look at.
    """
    assert artefact_is_cloud_derived(()) is True, "an unestablished transport must be surfaced"
    assert artefact_is_cloud_derived(("openai",)) is True
    assert artefact_is_cloud_derived((LOCAL_TRANSPORT_LABEL, "openai")) is True, (
        "any off-host field makes the document off-host"
    )
    assert artefact_is_cloud_derived((LOCAL_TRANSPORT_LABEL,)) is False


# ── The survey ───────────────────────────────────────────────────────────────


def test_the_survey_marks_a_cloud_derived_artefact_and_carries_its_stamp(profile: TestRuntimeProfile) -> None:
    """The cloud-read artefact is listed, with the stamp that classified it."""
    _seed_cloud_draft(profile)

    survey = survey_cloud_consent(bucket_id=profile.bucket_id, settings=profile.settings, consent_entries=())

    assert [row.evidence_reference for row in survey.cloud_derived_artefacts] == ["ev-1"]
    marked = survey.cloud_derived_artefacts[0]
    assert marked.provenance_stamp == _CLOUD_STAMP
    assert marked.transport == "openai"


def test_the_survey_leaves_an_on_host_artefact_alone(profile: TestRuntimeProfile) -> None:
    """POSITIVE CONTROL: a locally-read draft is not marked.

    Without this, the marking above is equally satisfied by a survey that lists
    every draft it finds, which would tell an operator that on-host reads need
    withdrawing too.
    """
    _seed_cloud_draft(profile, reference="ev-local", stamp=_LOCAL_STAMP, transports=(LOCAL_TRANSPORT_LABEL,))

    survey = survey_cloud_consent(bucket_id=profile.bucket_id, settings=profile.settings, consent_entries=())

    assert survey.cloud_derived_artefacts == ()


def test_the_survey_always_states_that_transmitted_bytes_cannot_be_recalled(profile: TestRuntimeProfile) -> None:
    """The one claim withdrawal must never soften, carried as data.

    Asserted on an EMPTY profile too: the statement is a property of what
    withdrawal is, not a consequence of having found something, so a surface
    rendering it conditionally would drop it exactly when an operator with no
    history concludes they are safe to enable the route.
    """
    empty = survey_cloud_consent(bucket_id=profile.bucket_id, settings=profile.settings, consent_entries=())
    assert empty.transmitted_bytes_are_unrecallable is True

    _seed_cloud_draft(profile)
    populated = survey_cloud_consent(bucket_id=profile.bucket_id, settings=profile.settings, consent_entries=())
    assert populated.transmitted_bytes_are_unrecallable is True


def test_a_draft_with_no_recorded_transport_is_surfaced_not_assumed_local(
    profile: TestRuntimeProfile,
) -> None:
    """An unestablished transport is surfaced, and the survey says it cannot name one.

    This is the case a batch-driven gate cannot reach, because the batch always
    records a transport -- so the "empty means unknown" branch would otherwise
    be asserted nowhere and a change making it read as on-host would pass every
    other test in the suite.
    """
    _seed_cloud_draft(profile, reference="ev-unknown", transports=())

    survey = survey_cloud_consent(bucket_id=profile.bucket_id, settings=profile.settings, consent_entries=())

    assert [row.evidence_reference for row in survey.cloud_derived_artefacts] == ["ev-unknown"]
    assert survey.cloud_derived_artefacts[0].transport is None


def _dispatch(*, bucket_id: str, address: str = _DIGEST) -> ConsentedDispatch:
    """Return one typed consent-ledger projection for survey scoping tests."""
    return ConsentedDispatch(
        profile_bucket_id=bucket_id,
        evidence_content_address=address,
        provider="openai",
        model="gpt-4.1",
        surface="cli",
        recorded_at=datetime(2026, 3, 10, 9, 30, tzinfo=UTC),
    )


def test_the_survey_lists_a_dispatch_recorded_under_this_profile(profile: TestRuntimeProfile) -> None:
    """The baseline the scoping case is measured against."""
    survey = survey_cloud_consent(
        bucket_id=profile.bucket_id,
        settings=profile.settings,
        consent_entries=(_dispatch(bucket_id=profile.bucket_id),),
    )

    assert [row.evidence_content_address for row in survey.consented_dispatches] == [_DIGEST]


def test_the_survey_drops_a_dispatch_recorded_under_another_profile(profile: TestRuntimeProfile) -> None:
    """One profile must never see another's off-host history.

    The survey holds the bucket being surveyed and already scopes its artefacts
    that way, so scoping the dispatches here means a composition root cannot
    disclose by forgetting to filter. Provider, model, surface and timestamp
    are all in that row; leaking it says where someone else's documents went.
    """
    survey = survey_cloud_consent(
        bucket_id=profile.bucket_id,
        settings=profile.settings,
        consent_entries=(
            _dispatch(bucket_id=profile.bucket_id),
            _dispatch(bucket_id="other-profile-bucket", address="e" * 64),
        ),
    )

    addresses = [row.evidence_content_address for row in survey.consented_dispatches]
    assert addresses == [_DIGEST], "a foreign profile's dispatch reached this profile's survey"


def test_a_survey_of_only_foreign_dispatches_reports_none(profile: TestRuntimeProfile) -> None:
    """Scoping to nothing is an empty history, not the caller's whole ledger."""
    survey = survey_cloud_consent(
        bucket_id=profile.bucket_id,
        settings=profile.settings,
        consent_entries=(_dispatch(bucket_id="other-profile-bucket"),),
    )

    assert survey.consented_dispatches == ()
