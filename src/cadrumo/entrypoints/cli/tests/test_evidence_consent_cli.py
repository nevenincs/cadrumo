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
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....application.ledger import DocumentTranscription, InvoiceDraft, TranscriberIdentity
from ....application.ledger._extracted_document_cache import write_cached_transcription
from ....application.ledger._extraction_draft_store import write_extraction_draft
from ....core import LOCAL_TRANSPORT_LABEL, FieldOrigin
from ....tests.cli_runner import invoke_cached_cli, semantic_cli_output
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_DIGEST = "c" * 64
_REFERENCE = "ev-consent-cli"
_CLOUD_STAMP = "llm:openai-text-extract:gpt-4.1:rates-2026A-abcdef"

_TEXT_LAYER = TranscriberIdentity(
    transport=LOCAL_TRANSPORT_LABEL,
    origin=FieldOrigin.TEXT_LAYER,
    name="pdfplumber-text-layer",
    revision="0.11.4",
)


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """A real isolated runtime profile; both verbs open a bucket."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as resolved:
        yield resolved


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


def _envelope(args: list[str]) -> tuple[int, dict[str, object]]:
    """Invoke the real tree with JSON output and return the exit code and envelope."""
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
    assert "nothing to re-derive" in semantic_cli_output(result), (
        "the verb must reach its own instructive refusal rather than crashing on the way to it"
    )


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
    # Names the transcription, so the refusal is about the missing cached text
    # rather than any earlier failure that also exits non-zero.
    assert "transcription" in semantic_cli_output(result).lower(), (
        "the refusal must say the cached transcription is missing, not fail opaquely"
    )
