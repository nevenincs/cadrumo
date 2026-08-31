"""The off-host evidence consent gate, at the dispatch choke point.

Every case here crosses the production :class:`LLMClient` and a real HTTP
transport against a loopback server, so "refuses" and "proceeds" are observed
at the wire rather than asserted about a helper in isolation. The server also
supplies this suite's positive control: a refusal test with no counterpart is
satisfied by a gate that refuses everything, and the thing that distinguishes
the two is whether the consented route actually reaches a provider.

No case asserts refusal PROSE. The messages are localized and a test that
pinned English would fail the moment a catalogue changed while proving nothing
about the boundary; the exception TYPE and the observed transport are the
contract.
"""

from __future__ import annotations

import ast
import asyncio
import inspect
import textwrap
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import override

import pytest
from pydantic import BaseModel, SecretStr, ValidationError
from pydantic_core import PydanticSerializationError

from ...adapters.outbound.llm import LLMCache, UsageRecorder
from ...application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ...core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ...core.field_origin import FieldOrigin
from ...core.config import LLMProvider, override_settings
from ...tests.fixtures.settings import EnvFileFreeSettings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    openai_chat_reply,
    read_text_body,
    serving_loopback,
    write_json_response,
)
from ..client import LLMClient
from ..client import LLMClient as _ClientUnderInspection
from ..consent import (
    EvidenceConsentToken,
    cloud_evidence_read_permitted,
    mint_evidence_consent_token,
    provider_reads_off_host,
)
from ..errors import LLMConsentError
from ..evidence_draft_text import TextInvoiceFieldExtractor, extract_invoice_fields_from_text
from ..models import LLMRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _transcription() -> DocumentTranscription:
    """Return a minimal stage-one transcription for the reader to consume.

    The gate under test is about TRANSPORT, so the content only has to be a
    valid transcription; what matters is that the request built from it is
    marked evidence-derived unless the caller names the public corpus.
    """
    return DocumentTranscription(
        text="Factura 2026-001 Base imponible 100,00 EUR",
        page_count=1,
        source_content_sha256="d" * 64,
        transcriber=TranscriberIdentity(
            transport=LOCAL_TRANSPORT_LABEL, origin=FieldOrigin.TEXT_LAYER, name="pdfplumber", revision="gate"
        ),
    )


_CONSENTED = EvidenceConsentToken(
    surface="aeat app ledger evidence extract",
    evidence_content_address="a" * 64,
)


def _settings(
    tmp_path: Path, *, cloud_upload_permitted: bool = False, gestor_mode: bool = False
) -> EnvFileFreeSettings:
    """Build settings with the LLM stores pointed inside ``tmp_path``.

    Every consent-relevant field is left at its shipped default unless a case
    names it, so a case that passes no override is testing the posture a
    deployment gets with no configuration at all.

    The OpenAI key is populated in EVERY case, refusals included, and that is
    the point. An absent credential is an accident that looks like a control:
    with the key unset the provider refuses first, and a suite would go green
    on a boundary that had stopped working. Supplying a usable credential
    against a loopback endpoint removes the accident, so a refusal below can
    only be the consent gate.
    """
    return EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model="gpt-oss",
        cadrumo_llm_openai_api_key=SecretStr("loopback-key"),
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
        cadrumo_evidence_cloud_upload_permitted=cloud_upload_permitted,
        cadrumo_evidence_gestor_mode=gestor_mode,
    )


def _client(settings: EnvFileFreeSettings) -> LLMClient:
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
    )


@contextmanager
def _serve_openai() -> Iterator[tuple[str, Queue[str]]]:
    """Serve an OpenAI-shaped chat-completions endpoint on loopback.

    Real HTTP, real adapter, real transport, and nothing leaves the machine.
    The queue records every request body that reached the endpoint, which is
    what makes "the document was transmitted" an observation rather than an
    inference from the absence of an exception.
    """
    bodies: Queue[str] = Queue()

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            bodies.put(read_text_body(self))
            write_json_response(
                self,
                # A parsable empty extraction object, so a case that runs the full
                # reader does not fail on the stub's reply shape instead of on the
                # boundary it is testing.
                openai_chat_reply("{}", prompt_tokens=11),
                status=HTTPStatus.OK,
            )

    with serving_loopback(_Endpoint, path="/v1/chat/completions") as endpoint:
        yield endpoint, bodies


def _evidence_request(*, token: EvidenceConsentToken | None = None) -> LLMRequest:
    return LLMRequest(
        prompt="Read this invoice.",
        provider_override=LLMProvider.OPENAI,
        model_override="gpt-4.1",
        evidence_derived=True,
        consent_token=token,
    )


# ── The refusal, and the shape of the default ────────────────────────────────


def test_an_unconsented_evidence_read_never_reaches_the_provider(tmp_path: Path) -> None:
    """With no configuration at all, an off-host evidence read refuses.

    The load-bearing assertion is the empty queue, not the exception: an
    exception proves the call ended, and only the endpoint's silence proves the
    document did not leave the host on the way there.
    """
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        client = _client(_settings(tmp_path))
        with pytest.raises(LLMConsentError):
            asyncio.run(client.complete(_evidence_request()))

    assert bodies.qsize() == 0


def test_the_deployment_opt_in_alone_does_not_permit_the_read(tmp_path: Path) -> None:
    """Enabling the deployment flag is not consent; the invocation still refuses.

    Separates the two halves of the posture. A gate satisfied by configuration
    alone would be exactly the "default a caller could flip once" this decision
    exists to prevent.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    with (
        _serve_openai() as (endpoint, bodies),
        override_settings(cadrumo_llm_openai_chat_completions_url=endpoint),
        pytest.raises(LLMConsentError),
    ):
        asyncio.run(_client(settings).complete(_evidence_request()))

    assert bodies.qsize() == 0


def test_gestor_mode_refuses_even_a_minted_token(tmp_path: Path) -> None:
    """The gestor bar is absolute and is re-applied at the dispatch point.

    The token here is a real, correctly minted one -- so this case cannot pass
    by the token being malformed. It proves the bar does not depend on the
    minting site having refused.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=True, gestor_mode=True)
    with (
        _serve_openai() as (endpoint, bodies),
        override_settings(cadrumo_llm_openai_chat_completions_url=endpoint),
        pytest.raises(LLMConsentError),
    ):
        asyncio.run(_client(settings).complete(_evidence_request(token=_CONSENTED)))

    assert bodies.qsize() == 0


def test_the_unpinned_text_reader_cannot_reach_around_the_gate(tmp_path: Path) -> None:
    """A reader constructed at a cloud provider refuses, pin or no pin.

    ``extract_invoice_fields_from_text`` is exported with no provider pin, and
    its extractor's LOCAL default is a floor rather than the boundary. This
    walks the documented way past that floor -- name the provider and the model
    -- and lands on the gate.
    """
    settings = _settings(tmp_path)
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        extractor = TextInvoiceFieldExtractor(
            provider=LLMProvider.OPENAI,
            model="gpt-4.1",
            settings=settings,
            client=_client(settings),
        )
        with pytest.raises(LLMConsentError):
            extractor.extract(transcription=_transcription())

    assert bodies.qsize() == 0


def test_the_router_wrapper_pins_local_by_expression_not_by_omission() -> None:
    """The wrapper the evidence router calls STATES its pin.

    ``extract_invoice_fields_from_text`` takes no provider argument, so today it
    is pinned on-host by construction -- which is the right answer reached the
    weakest possible way. Widening this signature with a pass-through
    ``provider`` would open the off-host route for every router call with no
    diff line that looks like a confidentiality change.

    Asserted over the AST rather than by calling it: the property is that the
    pin is WRITTEN, and a behavioural test passes identically whether the value
    was stated or inherited from a default, which is precisely the distinction
    this case exists to make.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(extract_invoice_fields_from_text)))
    pinned = [
        keyword
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "provider"
    ]
    assert pinned, (
        "the router wrapper no longer states its provider pin. Restore it, or -- if the pin was "
        "deliberately widened -- confirm the dispatch-point consent gate still refuses the off-host "
        "route, because that refusal and not this pin is what keeps the document on the host."
    )


# ── The positive controls ────────────────────────────────────────────────────


def test_the_consented_route_reaches_the_provider(tmp_path: Path) -> None:
    """POSITIVE CONTROL: a fully consented off-host read transmits.

    Without this, every refusal above is satisfied by a gate that refuses
    unconditionally -- including one that has stopped distinguishing consented
    from unconsented, which is the failure mode a confidentiality boundary can
    least afford to hide behind a green suite.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        response = asyncio.run(_client(settings).complete(_evidence_request(token=_CONSENTED)))

    assert response.text == "{}"
    assert bodies.qsize() == 1


def test_an_unmarked_request_is_not_gated(tmp_path: Path) -> None:
    """POSITIVE CONTROL: the gate is scoped to evidence, not to cloud providers.

    A column-role mapping or a public-corpus measurement carries no taxpayer
    content, and gating it would make the boundary a blanket cloud ban wearing
    a consent gate's name.
    """
    settings = _settings(tmp_path)
    request = LLMRequest(prompt="Map these headers.", provider_override=LLMProvider.OPENAI, model_override="gpt-4.1")
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        response = asyncio.run(_client(settings).complete(request))

    assert response.text == "{}"
    assert bodies.qsize() == 1


def test_the_public_corpus_escape_reaches_the_provider_through_the_reader(tmp_path: Path) -> None:
    """POSITIVE CONTROL for the reach-around case, through the same class.

    Its sibling refusal builds a ``TextInvoiceFieldExtractor`` at a cloud
    provider -- which is exactly what widening the router wrapper with a
    pass-through ``provider`` would produce -- and asserts nothing reaches the
    endpoint. This case differs from it in ONE variable, the evidence marker,
    and reaches the endpoint. Without it, that refusal is equally satisfied by a
    reader that can no longer dispatch at all.
    """
    settings = _settings(tmp_path)
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        extractor = TextInvoiceFieldExtractor(
            provider=LLMProvider.OPENAI,
            model="gpt-4.1",
            settings=settings,
            client=_client(settings),
            public_corpus=True,
        )
        extractor.extract(transcription=_transcription())

    assert bodies.qsize() == 1


def test_a_local_evidence_read_needs_no_consent() -> None:
    """POSITIVE CONTROL: on-host reading is unchanged and unceremonious.

    The whole justification for a narrow gate is that the on-host route stays
    free; a gate that also taxed local reads would push operators toward
    disabling it.
    """
    assert provider_reads_off_host(LLMProvider.LOCAL) is False
    assert all(provider_reads_off_host(member) for member in LLMProvider if member is not LLMProvider.LOCAL)


# ── The minting side ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("permitted", "gestor", "profile_eligible", "acknowledged"),
    [
        (permitted, gestor, eligible, acknowledged)
        for permitted in (False, True)
        for gestor in (False, True)
        for eligible in (False, True)
        for acknowledged in (False, True)
        if not (permitted and not gestor and eligible and acknowledged)
    ],
)
def test_a_token_cannot_be_minted_unless_every_condition_holds(
    tmp_path: Path,
    *,
    permitted: bool,
    gestor: bool,
    profile_eligible: bool,
    acknowledged: bool,
) -> None:
    """Every combination short of all-four refuses to mint.

    Enumerated exhaustively rather than sampled, so a future reordering of the
    gate's conditions cannot leave one of them unexercised. The one permitting
    combination is excluded by the comprehension's filter and asserted
    positively in the next test, so the two together partition all sixteen
    states -- no state is untested and none is tested for both outcomes.

    The standing PER-PROFILE eligibility bar is the fourth condition: deployment
    opt-in and profile eligibility are separate questions, because one machine
    can serve several taxpayers and one of them permitting an off-host read must
    not decide it for the others.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=permitted, gestor_mode=gestor)
    assert (
        cloud_evidence_read_permitted(settings, profile_eligible=profile_eligible, acknowledged=acknowledged) is False
    )
    with pytest.raises(LLMConsentError) as raised:
        mint_evidence_consent_token(
            settings=settings,
            profile_eligible=profile_eligible,
            acknowledged=acknowledged,
            surface="aeat app ledger evidence extract",
            evidence_content_address="b" * 64,
        )
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.evidence.off_host_dispatch_permitted"
    assert verdict.action is None
    assert verdict.evidence[0].values == {
        "acknowledged": acknowledged,
        "deployment_permitted": permitted,
        "gestor_mode": gestor,
        "profile_eligible": profile_eligible,
    }


def test_the_only_permitting_combination_mints(tmp_path: Path) -> None:
    """POSITIVE CONTROL for the minting side: all four conditions mint a token."""
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    assert cloud_evidence_read_permitted(settings, profile_eligible=True, acknowledged=True) is True
    token = mint_evidence_consent_token(
        settings=settings,
        profile_eligible=True,
        acknowledged=True,
        surface="aeat app ledger evidence extract",
        evidence_content_address="c" * 64,
    )
    assert token.surface == "aeat app ledger evidence extract"


# ── The token is per-invocation, and cannot become durable ───────────────────


def test_the_token_refuses_every_serialization_path() -> None:
    """A stored token would be the sticky enablement the posture forbids."""
    for dump in (_CONSENTED.model_dump, _CONSENTED.model_dump_json):
        with pytest.raises(LLMConsentError) as raised:
            dump()
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.token_ephemeral"
        assert verdict.action is None
        assert verdict.evidence[0].values == {"consent_token_serializable": False}


def test_a_container_that_forgets_to_exclude_the_token_still_cannot_dump_it() -> None:
    """The REGISTERED serializer, exercised where it is the only thing refusing.

    :class:`LLMRequest` marks ``consent_token`` ``exclude=True``, so a request
    dump omits the token without the serializer being consulted at all -- which
    means the request path proves nothing about the serializer, and a proof
    built there would pass for the wrong reason. Defence-in-depth reads exactly
    like vacuity from the outside.

    The container below is the case the exclude does NOT cover: a future model
    that holds a token and forgets the exclude. That is where the registered
    serializer is the only refusal left, so that is where it is worth asserting.
    """

    class _ForgetfulContainer(BaseModel):
        token: EvidenceConsentToken

    holder = _ForgetfulContainer(token=_CONSENTED)
    with pytest.raises((LLMConsentError, PydanticSerializationError)):
        holder.model_dump()
    with pytest.raises((LLMConsentError, PydanticSerializationError)):
        holder.model_dump_json()


def test_a_request_dump_carries_no_token() -> None:
    """The request's own dump -- the request-id input -- omits the token.

    Both halves matter: the token must not reach any dump, and the dump must
    still work, because the client hashes it to build the request id.
    """
    payload = _evidence_request(token=_CONSENTED).model_dump(mode="json")
    assert "consent_token" not in payload
    assert payload["evidence_derived"] is True


def test_a_token_bound_to_nothing_is_refused() -> None:
    """A whitespace surface or address binds the acknowledgement to everything."""
    for surface, address in ((" ", "d" * 64), ("aeat app ledger evidence extract", "  ")):
        with pytest.raises(LLMConsentError) as raised:
            EvidenceConsentToken(surface=surface, evidence_content_address=address)
        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.evidence.token_bound"
        assert verdict.action is None
        assert verdict.evidence[0].values == {"consent_token_binding_valid": False}


# ── The gate's position in the dispatch, asserted structurally ───────────────


def test_the_gate_runs_before_the_cache_read_and_before_adapter_construction() -> None:
    """The consent check precedes both reach-arounds, proven over the AST.

    Ordering is the half a behavioural test cannot see. Two orderings would
    pass every case above while being wrong: gating AFTER the cache read lets a
    once-consented entry serve a later unconsented invocation, and gating AFTER
    adapter construction makes a missing API key raise first -- so the refusal
    an operator sees is a misconfiguration, and the gate's own firing becomes
    unobservable.

    Walked as an AST over ``complete``'s statements rather than matched against
    source text: a substring search cannot tell a call from a mention of the
    same name in the docstring or a comment, and this module's own prose names
    all three.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(_ClientUnderInspection.complete)))
    function = tree.body[0]
    assert isinstance(function, ast.AsyncFunctionDef)

    positions: dict[str, int] = {}
    for index, node in enumerate(function.body):
        for descendant in ast.walk(node):
            if not isinstance(descendant, ast.Call) or not isinstance(descendant.func, ast.Attribute):
                continue
            name = descendant.func.attr
            if name in {"_require_evidence_consent", "read", "_build_adapter"} and name not in positions:
                positions[name] = index

    assert positions.keys() == {"_require_evidence_consent", "read", "_build_adapter"}, (
        f"complete() no longer calls all three; found {sorted(positions)}. The ordering this test "
        "guards cannot be checked over a dispatch that lost one of them."
    )
    assert positions["_require_evidence_consent"] < positions["read"]
    assert positions["_require_evidence_consent"] < positions["_build_adapter"]


# ── The audit trail the gate writes, and whether it can be read as complete ──
#
# Every case above watches ONE direction: transmission without consent. The
# ledger the gate writes is consulted in the other direction -- an operator
# asking what left their machine -- and an omission there produces no visible
# symptom at all, which is why the survey commits to failing open toward
# surfacing. These cases constrain that direction.
#
# "Complete over a period" is currently satisfiable as "complete over all
# time": the ledger read applies no period filter and returns every entry for
# the profile. So completeness here is the conjunction of four properties --
# every crossing dispatch appends before it transmits, a cache hit appends too,
# a failed append refuses rather than transmitting unrecorded, and nothing
# prunes or silently drops an entry afterwards. Should a period filter ever be
# added to the read, this set needs a boundary case; today there is no boundary
# to test.


def _consent_entries() -> tuple[str, ...]:
    """Return the recorded content addresses for the active profile, oldest first."""
    from ...adapters.outbound.llm import EvidenceConsentLedger

    return tuple(entry.evidence_content_address for entry in EvidenceConsentLedger().load_entries())


def test_every_consented_dispatch_is_recorded_exactly_once(tmp_path: Path) -> None:
    """Set equality between what was transmitted and what was recorded, not merely non-empty.

    Three distinct consented reads, three distinct documents. A ledger that
    recorded the first and dropped the rest satisfies every "an entry exists"
    assertion, and that is precisely the shape an operator cannot detect: the
    survey shows rows, so it looks like it worked.

    Both sides are counted. The endpoint's queue is what transmitted; the
    ledger is what was recorded. Asserting their equality is the completeness
    statement -- either alone is satisfied by a boundary that stopped
    dispatching or by one that logs unconditionally.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    addresses = tuple(char * 64 for char in ("1", "2", "3"))
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        client = _client(settings)
        for index, address in enumerate(addresses):
            token = EvidenceConsentToken(surface="aeat app ledger evidence extract", evidence_content_address=address)
            request = _evidence_request(token=token).model_copy(update={"prompt": f"Read invoice {index}."})
            asyncio.run(client.complete(request))

    assert bodies.qsize() == len(addresses), "every consented read must reach the provider"
    assert _consent_entries() == addresses, (
        "the consent ledger must hold exactly one entry per transmitted document, in order; a survey "
        "built on a ledger that drops rows tells an operator they are clean when they are not"
    )


def test_a_dispatch_served_from_the_cache_is_recorded_too(tmp_path: Path) -> None:
    """A cache hit is still a cloud-derived answer, so it still owes an entry.

    The case most likely to be "optimised" later by someone reading a cache hit
    as not a transmission. It is not a transmission -- and that is exactly why
    the entry matters: the response still derives from the earlier off-host
    read, so a withdrawal must list it as a re-derivation candidate.

    The single body at the endpoint is what proves the second call really was
    served from the cache; without it, two entries would only show that two
    dispatches happened.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        client = _client(settings)
        first = asyncio.run(client.complete(_evidence_request(token=_CONSENTED)))
        second = asyncio.run(client.complete(_evidence_request(token=_CONSENTED)))

    assert first.cache_hit is False
    assert second.cache_hit is True, "the second identical request must be served from the cache"
    assert bodies.qsize() == 1, "a cache hit must not re-transmit"
    assert _consent_entries() == (_CONSENTED.evidence_content_address,) * 2, (
        "a consented dispatch served from the cache must still be recorded; the answer is cloud-derived "
        "either way and a withdrawal has to be able to find it"
    )


def test_a_dispatch_whose_record_cannot_be_written_is_refused_not_degraded(tmp_path: Path) -> None:
    """The load-bearing precondition for every completeness claim above.

    If a dispatch could succeed while its record quietly failed, no property of
    the ledger would constrain what actually left the host. So the append is
    allowed to raise, and the refusal is the only outcome.

    Reached through the production primitive for an unbound session rather than
    by breaking the store: a CLI invocation with no bucket open is a real
    condition, and suspending is reversible where closing would strand the
    fixture's own session.

    The queue is the load-bearing assertion. An exception alone proves the call
    ended; only the endpoint's silence proves the document did not leave the
    host before the record failed.
    """
    from ...adapters.persistence.storage import suspend_active_session

    settings = _settings(tmp_path, cloud_upload_permitted=True)
    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        client = _client(settings)
        with suspend_active_session(), pytest.raises(LLMConsentError):
            asyncio.run(client.complete(_evidence_request(token=_CONSENTED)))
        transmitted_while_unrecordable = bodies.qsize()

        # Positive control: the SAME client and the SAME request transmit once
        # the session is back, so the refusal above is the unwritable record and
        # not a client that had stopped dispatching.
        asyncio.run(client.complete(_evidence_request(token=_CONSENTED)))

    assert transmitted_while_unrecordable == 0, "the unrecordable dispatch must not have transmitted"
    assert bodies.qsize() == 1
    assert _consent_entries() == (_CONSENTED.evidence_content_address,)


def test_the_consent_ledger_survives_the_retention_sweep(tmp_path: Path) -> None:
    """Nothing ages an entry out, which is what makes the history readable over a period.

    The three sibling LLM stores are pruned on every client construction
    because they are diagnostic and regenerable. This one is neither: an entry
    aged out would make a withdrawal silently incomplete, and silently is the
    whole problem.

    Constructing further clients is what runs the sweep, so this exercises the
    real lifecycle rather than asserting that no prune method is called.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    with _serve_openai() as (endpoint, _), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        asyncio.run(_client(settings).complete(_evidence_request(token=_CONSENTED)))
        recorded = _consent_entries()
        _client(settings)
        _client(settings)

    assert recorded == (_CONSENTED.evidence_content_address,)
    assert _consent_entries() == recorded, "the retention sweep must not touch the consent audit trail"


def test_the_ledger_read_refuses_an_unreadable_row_rather_than_skipping_it(tmp_path: Path) -> None:
    """Completeness on the READ side: a row that cannot be parsed must not vanish.

    The anti-tautology proof for every count asserted above. A read that
    silently skipped an unparsable record would return a SHORTER history that
    still looks like a complete one, and no assertion on the returned rows
    could tell the difference -- the missing row is missing from the evidence
    too.

    The corrupt record is written through the real repository at the ledger's
    own namespace, so it is reached by exactly the read path production uses.
    """
    from ...adapters.outbound.llm import EvidenceConsentLedger
    from ...adapters.persistence.storage import (
        LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE,
        secure_object_repository_for_active_bucket,
    )
    from ...core.hashing import canonical_json_bytes
    from ...core.time import now

    settings = _settings(tmp_path, cloud_upload_permitted=True)
    with _serve_openai() as (endpoint, _), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        asyncio.run(_client(settings).complete(_evidence_request(token=_CONSENTED)))

    assert len(EvidenceConsentLedger().load_entries()) == 1, "the readable row must be there to be lost"

    written_at = now()
    secure_object_repository_for_active_bucket().save(
        namespace=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.namespace,
        object_key=f"{written_at.isoformat()}|corrupt|corrupt",
        classification=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.sensitivity,
        schema_version=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.schema_version,
        written_at=written_at,
        payload=canonical_json_bytes({"entry": {"entry_id": "only-this-field"}}),
    )

    with pytest.raises(ValidationError):
        EvidenceConsentLedger().load_entries()
