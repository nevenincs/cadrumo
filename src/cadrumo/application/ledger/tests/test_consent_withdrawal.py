"""Withdrawal enumerates honestly, and re-derivation asserts without overwriting.

Every case crosses the REAL encrypted stores -- real key provider, real SQLite
engine, real serializer -- because the two claims under test are both about
persisted state: which artefacts a withdrawal can see, and what survives a
re-derivation. A stand-in store would answer both questions by construction.

The on-host reader is injected as a plain callable rather than a model client.
That is not a test double standing in for inference: the production seam is a
Protocol precisely so this layer never constructs the gated subpackage, so the
callable here exercises the same contract production does. No model is loaded
or invoked anywhere in this module.
"""

from __future__ import annotations

import pytest

from ....tests.consent_profile_fixture import consent_profile

__all__ = ["consent_profile"]

from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....core.field_origin import FieldOrigin
from ....tests.secure_sql import TestRuntimeProfile
from ..consent_withdrawal import (
    ConsentRederivationError,
    artefact_is_cloud_derived,
    provenance_stamp_transport,
    rederive_artefact_on_host,
    survey_cloud_consent,
)
from ..document_transcription import DocumentTranscription, TranscriberIdentity
from ..evidence_draft import InvoiceDraft
from ..extracted_document_cache import write_cached_transcription
from ..extraction_draft_store import read_extraction_draft, write_extraction_draft

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


def _seed_transcription(profile: TestRuntimeProfile, *, text: str = "Factura Acme SL\nBase imponible 2.420,00") -> None:
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=DocumentTranscription(
            text=text,
            page_count=1,
            source_content_sha256=_DIGEST,
            transcriber=_TEXT_LAYER,
        ),
        settings=profile.settings,
    )


def _local_reader(transcription: DocumentTranscription, /) -> tuple[InvoiceDraft, str]:
    """An on-host reader: consumes the cached transcription, stamps a local transport.

    Takes the ARTEFACT, matching the protocol. The parameter was a bare string
    until the semantic stage began consuming the transcription, and the
    truthiness assertion that guarded it then became near-vacuous: every model
    instance is truthy, so it passed for any object at all. Asserting on the
    cached TEXT restores what it was checking -- that the reader is handed the
    transcription that was stored, rather than something reconstructed.
    """
    assert transcription.text.startswith("Factura Acme SL"), (
        "the reader must receive the CACHED transcription, not a reconstructed or empty one"
    )
    return InvoiceDraft(), _LOCAL_STAMP


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


def test_re_derivability_is_unknown_rather_than_false_when_nobody_asked(profile: TestRuntimeProfile) -> None:
    """No resolver means the question was never put, and ``None`` says so.

    The draft store keys by evidence reference and the cache keys by content
    address, so without a resolver the two cannot be joined. Reporting ``False``
    would state a fact nobody established, and "cannot re-derive" and "cannot
    say whether it can be re-derived" lead an operator to different actions.
    """
    _seed_cloud_draft(profile)

    survey = survey_cloud_consent(bucket_id=profile.bucket_id, settings=profile.settings, consent_entries=())

    assert survey.cloud_derived_artefacts[0].rederivable_on_host is None


def test_re_derivability_resolves_true_and_false_once_a_resolver_is_supplied(profile: TestRuntimeProfile) -> None:
    """With the join available, the answer is established in both directions."""
    _seed_cloud_draft(profile)
    _seed_transcription(profile)

    resolved = survey_cloud_consent(
        bucket_id=profile.bucket_id,
        settings=profile.settings,
        consent_entries=(),
        resolve_content_address=lambda _reference: _DIGEST,
        transcriber_cache_key=_TEXT_LAYER.cache_key,
    )
    assert resolved.cloud_derived_artefacts[0].rederivable_on_host is True

    unresolvable = survey_cloud_consent(
        bucket_id=profile.bucket_id,
        settings=profile.settings,
        consent_entries=(),
        resolve_content_address=lambda _reference: None,
        transcriber_cache_key=_TEXT_LAYER.cache_key,
    )
    assert unresolvable.cloud_derived_artefacts[0].rederivable_on_host is False


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


# ── Re-derivation: the re-stamp gate ─────────────────────────────────────────


def test_re_derivation_re_stamps_the_artefact_without_rewriting_its_history(profile: TestRuntimeProfile) -> None:
    """The re-stamp gate: a new local derivation, with the prior stamp preserved.

    Three things are asserted together because the value of the operation is
    exactly their conjunction: the stored artefact now carries a LOCAL stamp
    (no current artefact depends on the cloud read), the outcome still names the
    stamp it superseded (the history is asserted over, not erased), and the
    cached transcription supplied the text (no document was re-read, and
    nothing left the host).
    """
    _seed_cloud_draft(profile)
    _seed_transcription(profile)

    outcome = rederive_artefact_on_host(
        bucket_id=profile.bucket_id,
        evidence_reference="ev-1",
        source_content_sha256=_DIGEST,
        transcriber_cache_key=_TEXT_LAYER.cache_key,
        settings=profile.settings,
        read_on_host=_local_reader,
    )

    assert outcome.previous_provenance_stamp == _CLOUD_STAMP
    assert outcome.provenance_stamp == _LOCAL_STAMP
    assert outcome.transcription_reused is True

    stored = read_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference="ev-1",
        settings=profile.settings,
    )
    assert stored is not None
    assert stored.extractor == _LOCAL_STAMP

    survey = survey_cloud_consent(bucket_id=profile.bucket_id, settings=profile.settings, consent_entries=())
    assert survey.cloud_derived_artefacts == (), "the re-derived artefact must no longer be marked cloud-derived"


def test_re_derivation_refuses_rather_than_re_reading_the_document(profile: TestRuntimeProfile) -> None:
    """No cached transcription means refuse, never fall back to a fresh read.

    A silent fallback would turn a withdrawal into a second document read of
    unknown cost and, on a path whose whole purpose is to stop transmitting,
    would be the wrong default to take without the operator saying so.
    """
    _seed_cloud_draft(profile)

    with pytest.raises(ConsentRederivationError) as raised:
        rederive_artefact_on_host(
            bucket_id=profile.bucket_id,
            evidence_reference="ev-1",
            source_content_sha256=_DIGEST,
            transcriber_cache_key=_TEXT_LAYER.cache_key,
            settings=profile.settings,
            read_on_host=_local_reader,
        )
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "ledger.consent_rederivation.transcription_available"
    assert verdict.evidence[0].values == {"transcription_available": False}


def test_re_derivation_refuses_a_reader_that_stamps_a_cloud_transport(profile: TestRuntimeProfile) -> None:
    """A re-derivation that transmitted again must not be recorded as local.

    This is the failure that would be invisible without the check: the operator
    asks to come back on-host, the reader routes off-host anyway, and the
    artefact is re-stamped as re-derived. The withdrawal would then report
    completion having just repeated the transmission it existed to stop.
    """
    _seed_cloud_draft(profile)
    _seed_transcription(profile)

    def _cloud_reader(transcription: DocumentTranscription, /) -> tuple[InvoiceDraft, str]:
        assert transcription.text
        return InvoiceDraft(), _CLOUD_STAMP

    with pytest.raises(ConsentRederivationError) as raised:
        rederive_artefact_on_host(
            bucket_id=profile.bucket_id,
            evidence_reference="ev-1",
            source_content_sha256=_DIGEST,
            transcriber_cache_key=_TEXT_LAYER.cache_key,
            settings=profile.settings,
            read_on_host=_cloud_reader,
        )
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "ledger.consent_rederivation.on_host"

    stored = read_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference="ev-1",
        settings=profile.settings,
    )
    assert stored is not None
    assert stored.extractor == _CLOUD_STAMP, "the refused re-derivation must not have written anything"


def test_re_derivation_refuses_an_unknown_artefact(profile: TestRuntimeProfile) -> None:
    """A reference with no pending artefact refuses rather than creating one."""
    _seed_transcription(profile)

    with pytest.raises(ConsentRederivationError) as raised:
        rederive_artefact_on_host(
            bucket_id=profile.bucket_id,
            evidence_reference="ev-absent",
            source_content_sha256=_DIGEST,
            transcriber_cache_key=_TEXT_LAYER.cache_key,
            settings=profile.settings,
            read_on_host=_local_reader,
        )
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "ledger.consent_rederivation.artefact_available"
    assert verdict.evidence[0].values == {"artefact_available": False}
