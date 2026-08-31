"""The off-host consent verbs, driven through the REAL command tree.

This module exists because its subject had none, and that absence hid two live
operator-facing crashes until a lane building on top of the surface happened to
probe a real instance. Both verbs read ``_state().settings``; ``WorkflowState``
has no such attribute, so ``consent list`` and ``consent rederive`` raised
``AttributeError`` for every operator who ran them. Separately, the on-host
re-derivation reader called a semantic-stage signature that had changed under
it, while being annotated loosely enough that the type checker saw nothing.

**Every case here invokes the real Click tree and reads the real envelope**, and
that is the whole design constraint rather than a stylistic preference. A test
that constructed a ``WorkflowState`` and called the handler would have passed
against both defects: the first lived precisely in the gap between constructed
state and the state the command tree actually produces, and the second behind an
``object`` annotation that a direct call would have satisfied.

The runtime profile is real -- real key provider, real SQLite engine -- because
both verbs open a bucket. No model runs: the one case that needs a reader points
the local transport at a loopback endpoint, so a real HTTP round-trip happens
with no inference.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from ....tests.consent_profile_fixture import consent_profile

__all__ = ["consent_profile"]

from ....application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ....application.ledger.extracted_document_cache import write_cached_transcription
from ....application.ledger.extraction_draft_store import write_extraction_draft
from ....application.ledger.invoice_draft_records import InvoiceDraft
from ....core.field_origin import FieldOrigin
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import TestRuntimeProfile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_DIGEST = "c" * 64
_REFERENCE = "ev-consent-cli"
_CLOUD_STAMP = "llm:openai-text-extract:gpt-4.1:rates-2026A-abcdef"

_TEXT_LAYER = TranscriberIdentity(
    transport=LOCAL_TRANSPORT_LABEL,
    origin=FieldOrigin.TEXT_LAYER,
    name="pdfplumber-text-layer",
    revision="0.11.4",
)


def _seed_cloud_artefact(profile: TestRuntimeProfile, *, reference: str = _REFERENCE) -> None:
    """Record a draft derived off-host, so the survey has something to report."""
    write_extraction_draft(
        bucket_id=profile.bucket_id,
        evidence_reference=reference,
        draft=InvoiceDraft(),
        extractor=_CLOUD_STAMP,
        read_transports=("openai",),
        settings=profile.settings,
    )


def _seed_consented_dispatch(profile: TestRuntimeProfile, *, address: str = _DIGEST) -> None:
    """Record one real off-host dispatch in the real consent ledger.

    The production append, not a constructed row: the ledger writes to the
    profile's encrypted store through the active bucket session this fixture
    opened, so what the verb reads back is what a consented dispatch actually
    leaves behind.
    """
    from ....adapters.outbound.llm._consent_ledger import EvidenceConsentLedger

    _ = profile
    EvidenceConsentLedger().append(
        evidence_content_address=address,
        provider="openai",
        model="gpt-4.1",
        surface="app.ledger.evidence.extract",
    )


def _seed_transcription(profile: TestRuntimeProfile) -> None:
    """Cache the transcription a re-derivation reads instead of the document."""
    write_cached_transcription(
        bucket_id=profile.bucket_id,
        transcription=DocumentTranscription(
            text="Factura Acme SL\nBase imponible 2.420,00",
            page_count=1,
            source_content_sha256=_DIGEST,
            transcriber=_TEXT_LAYER,
        ),
        settings=profile.settings,
    )


def _envelope(args: list[str]) -> tuple[int, dict[str, Any]]:
    """Invoke the real tree with JSON output and return the exit code and envelope.

    Typed ``Any`` at the value position rather than ``object``: the envelope is
    a decoded JSON document whose members are nested lists and mappings, and
    ``object`` made every ``envelope["result"][...]`` read a type error while
    describing the shape no more accurately.
    """
    # `--format` is a ROOT option, so it precedes the command path; the leaf
    # verbs declare no options of their own.
    result = invoke_cached_cli(["--format", "json", *args])
    if not result.stdout.strip():
        return result.exit_code, {}
    return result.exit_code, json.loads(result.stdout)


# ── The crash the missing tests hid ──────────────────────────────────────────


def test_consent_list_runs_at_all_on_a_profile_with_no_history(profile: TestRuntimeProfile) -> None:
    """The regression for the crash, and deliberately the emptiest possible case.

    ``consent list`` raised ``AttributeError`` on every invocation, empty history
    or not, because it read an attribute ``WorkflowState`` does not carry. The
    profile with NOTHING recorded is the right shape for the regression: it
    reaches the same attribute access while asserting nothing about content, so
    it cannot pass for a reason unrelated to the defect.

    Asserting the exit code AND a parsed envelope, because a crash and an empty
    result are exactly what an operator cannot tell apart here.
    """
    _ = profile
    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0, "the consent survey must run on a profile with no off-host history"
    assert envelope, "the survey must emit an envelope rather than crashing before it"
    assert envelope["result"]["consented_dispatches"] == []
    assert envelope["result"]["cloud_derived_artefacts"] == []


def test_consent_rederive_reaches_its_own_refusal_rather_than_crashing(profile: TestRuntimeProfile) -> None:
    """The same regression on the second verb, via its instructive refusal.

    ``rederive`` read the same missing attribute, so it crashed before it could
    refuse. Naming an artefact that does not exist proves the handler ran far
    enough to consult the store and answer -- an ``AttributeError`` would surface
    as an unhandled failure, not as this refusal.
    """
    _ = profile
    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "evidence",
            "consent",
            "rederive",
            "no-such-artefact",
            "--content-address",
            _DIGEST,
            "--transcriber",
            "text_layer:pdfplumber-text-layer@0.11.4",
        ],
    )

    # The REFUSAL's own words, not merely a non-zero exit. A crash also exits
    # non-zero, so an exit-code assertion cannot tell "refused instructively"
    # from "died before it could" -- which is exactly the pair this module
    # exists to separate.
    assert result.exit_code != 0, "re-deriving an unknown artefact must refuse"
    envelope = json.loads(next(line for line in result.output.splitlines() if line.startswith("{")))
    error = envelope["error"]
    assert error["code"] != "REFUSED_CLI_BOUNDARY"
    action = error["action"]
    assert action["failed_condition_id"] == "ledger.consent_rederivation.artefact_available"
    assert action["evidence"][0]["values"] == {"artefact_available": False}
    assert action["action"] is None
    assert action["no_recovery_outcome"] == "operator_decision"


# ── The survey reports what is there, not only that it is empty ──────────────


def test_the_survey_reports_a_cloud_derived_artefact_when_one_exists(profile: TestRuntimeProfile) -> None:
    """The positive control for the survey.

    An empty survey proves nothing on its own: a verb that reported zero
    artefacts unconditionally would satisfy the empty case above and every
    refusal in this module. This differs from that case in ONE variable -- a
    recorded off-host draft -- and requires the artefact to come back with the
    transport it was derived under.
    """
    _seed_cloud_artefact(profile)

    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0
    artefacts = envelope["result"]["cloud_derived_artefacts"]
    assert [row["evidence_reference"] for row in artefacts] == [_REFERENCE]
    # The transport, not merely the row: the survey exists to answer WHICH
    # artefacts left the host, and a row with the transport stripped would
    # satisfy a presence check while losing the only fact that matters.
    assert artefacts[0]["transport"] == "openai"
    assert artefacts[0]["provenance_stamp"] == _CLOUD_STAMP


def test_the_survey_reports_a_recorded_dispatch(profile: TestRuntimeProfile) -> None:
    """The ENUMERATION leg, which had no test and no production wiring.

    The survey's three-part contract is enumerate, mark, offer. Every other case
    in this module exercises the marking leg -- artefacts, transports, stamps --
    and the empty case asserts ``consented_dispatches == []`` on a profile with
    no history, which a verb that never reads the ledger satisfies identically.
    So the leg that answers "what left this machine" was covered only by an
    assertion that it was empty when it should be.

    This differs from the empty case in ONE variable: a real appended ledger
    entry. Its fields are asserted individually rather than by row count,
    because a row that lost the provider or the surface tells an operator a
    transmission happened without saying where it went.
    """
    _seed_consented_dispatch(profile)

    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0
    dispatches = envelope["result"]["consented_dispatches"]
    assert len(dispatches) == 1, "a recorded off-host dispatch must reach the operator surface"
    assert dispatches[0]["evidence_content_address"] == _DIGEST
    assert dispatches[0]["provider"] == "openai"
    assert dispatches[0]["model"] == "gpt-4.1"
    assert dispatches[0]["surface"] == "app.ledger.evidence.extract"


def test_a_recorded_dispatch_denies_the_nothing_left_this_host_notice(profile: TestRuntimeProfile) -> None:
    """The sharp case: history on record, no surviving artefact, and the verb must not say "clean".

    This is the state a profile is in AFTER a successful re-derivation. The
    artefact has been rewritten with an on-host stamp, so nothing is
    cloud-derived any more -- and the consent ledger still holds the entry,
    because re-derivation asserts a new derivation rather than claiming the
    transmission never happened.

    With the enumeration leg unwired the dispatch list is empty regardless, so
    both halves of the emptiness test hold and the surface emits the
    affirmative "nothing has been sent off-host" notice over a profile that
    demonstrably did send something. An operator reading that has been told the
    opposite of the truth by the one verb built to tell them.

    Seeded with a dispatch and deliberately NO artefact, so the notice's
    suppression can only come from the dispatch leg.
    """
    _seed_consented_dispatch(profile)

    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0
    assert envelope["result"]["cloud_derived_artefacts"] == [], "this case must carry no surviving artefact"
    codes = {notice["code"] for notice in envelope["notices"]}
    assert "evidence_consent_no_history" not in codes, (
        "a profile with a recorded off-host dispatch must never be told that nothing has left this host, "
        "even once no cloud-derived artefact survives"
    )


def test_a_dispatch_recorded_under_another_profile_is_not_listed_here(profile: TestRuntimeProfile) -> None:
    """The survey is scoped to one profile, and over-reporting is its own defect.

    One machine can serve several taxpayers. The ledger reads the active
    bucket's store, and every entry carries the bucket it ran under, so the
    projection filters on that stamp rather than trusting the store it came
    from. Without the filter, a row belonging to another profile would appear
    on this profile's confidentiality surface -- an operator told that a
    document left their machine when it was someone else's.

    Written through the REAL secure-object repository at the ledger's own
    namespace and key shape, so the row is indistinguishable from an appended
    one except in the field under test. The own-profile row is seeded alongside
    it, so this cannot pass by the verb reporting nothing at all.
    """
    from ....adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
    from ....adapters.persistence.storage.secure_object_namespaces import LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE
    from ....core.hashing import canonical_json_bytes
    from ....core.time.clock import now
    from ....domain.evidence_consent._record import EvidenceConsentLedgerEntry

    _seed_consented_dispatch(profile)
    foreign = EvidenceConsentLedgerEntry(
        entry_id="ffffffffffffffffffffffffffffffff",
        profile_bucket_id="99999999-9999-4999-8999-999999999999",
        evidence_content_address="f" * 64,
        provider="openai",
        model="gpt-4.1",
        surface="app.ledger.evidence.extract",
        recorded_at=now(),
    )
    secure_object_repository_for_active_bucket().save(
        namespace=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.namespace,
        object_key="|".join((foreign.recorded_at.isoformat(), foreign.evidence_content_address, foreign.entry_id)),
        classification=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.sensitivity,
        schema_version=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.schema_version,
        written_at=foreign.recorded_at,
        payload=canonical_json_bytes({"entry": foreign.model_dump(mode="json")}),
    )

    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0
    addresses = [row["evidence_content_address"] for row in envelope["result"]["consented_dispatches"]]
    assert addresses == [_DIGEST], (
        "the survey must list this profile's dispatches only; a row stamped with another profile's "
        f"bucket must not surface here, got {addresses}"
    )


def test_the_survey_states_the_bytes_cannot_be_recalled_even_with_no_history(profile: TestRuntimeProfile) -> None:
    """The caveat is unconditional, and the empty case is where it matters most.

    An operator with no history is precisely the one deciding whether to enable
    the route, so the warning must reach them before there is anything to warn
    about.
    """
    _ = profile
    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0
    assert envelope["result"]["transmitted_bytes_are_unrecallable"] is True
    codes = {notice["code"] for notice in envelope["notices"]}
    assert "evidence_consent_bytes_unrecallable" in codes


def test_an_empty_survey_says_so_rather_than_showing_a_bare_header(profile: TestRuntimeProfile) -> None:
    """An empty history must be stated, not implied by the absence of rows.

    This is the shape that let the crash sit unnoticed: an operator who sees no
    rows cannot tell "nothing was ever sent off-host" from "this verb did not
    work". The affirmative notice is the difference, and it is a ``Notice`` on
    the shared spine rather than a bespoke result field, per the envelope
    contract.
    """
    _ = profile
    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0
    codes = {notice["code"] for notice in envelope["notices"]}
    assert "evidence_consent_no_history" in codes, (
        "an empty survey must state that nothing has been sent off-host, so it is "
        "distinguishable from a survey that failed to report"
    )


def test_the_no_history_notice_is_absent_once_there_is_history(profile: TestRuntimeProfile) -> None:
    """The bound on the notice above, so it reports a fact rather than always firing.

    Without this, the empty-case assertion is satisfied by a notice emitted
    unconditionally -- which would say "nothing was sent off-host" over a survey
    that had just listed something that was.
    """
    _seed_cloud_artefact(profile)

    exit_code, envelope = _envelope(["app", "ledger", "evidence", "consent", "list"])

    assert exit_code == 0
    codes = {notice["code"] for notice in envelope["notices"]}
    assert "evidence_consent_no_history" not in codes


# ── Re-derivation refuses honestly ───────────────────────────────────────────


def test_re_derivation_refuses_when_no_cached_transcription_exists(profile: TestRuntimeProfile) -> None:
    """The document is never re-read; absent a cached transcription the verb refuses.

    Seeded WITH the artefact and WITHOUT the transcription, so the refusal is
    about the missing transcription rather than the missing artefact -- the
    previous case already covers the latter, and a fixture missing both would
    not distinguish them.
    """
    _seed_cloud_artefact(profile)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "evidence",
            "consent",
            "rederive",
            _REFERENCE,
            "--content-address",
            _DIGEST,
            "--transcriber",
            "text_layer:pdfplumber-text-layer@0.11.4",
        ],
    )

    assert result.exit_code != 0
    envelope = json.loads(next(line for line in result.output.splitlines() if line.startswith("{")))
    error = envelope["error"]
    assert error["code"] != "REFUSED_CLI_BOUNDARY"
    action = error["action"]
    assert action["failed_condition_id"] == "ledger.consent_rederivation.transcription_available"
    assert action["evidence"][0]["values"] == {"transcription_available": False}
    assert action["action"] is None
    assert action["no_recovery_outcome"] == "operator_decision"
