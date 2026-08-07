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
import json
import textwrap
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from typing import override

import pytest
from pydantic import SecretStr

from ...adapters.outbound.llm import LLMCache, UsageRecorder
from ...core.config import LLMProvider, override_settings
from ...tests.fixtures.settings import EnvFileFreeSettings
from .. import (
    EvidenceConsentToken,
    LLMClient,
    LLMConsentError,
    LLMRequest,
    TextInvoiceFieldExtractor,
    cloud_evidence_read_permitted,
    mint_evidence_consent_token,
)
from .._client import LLMClient as _ClientUnderInspection
from .._consent import provider_reads_off_host

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

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

    class _Endpoint(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            raw = self.rfile.read(int(self.headers.get("content-length", "0")))
            bodies.put(raw.decode("utf-8"))
            payload = {
                "id": "chatcmpl-loopback",
                "model": "gpt-4.1",
                "choices": [{"message": {"content": "off-host completion"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            }
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        @override
        def log_message(self, format: str, *args: object) -> None:
            """Silence stdlib request logging during tests."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions", bodies
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


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
            extractor.extract(evidence_text="Factura 2026-001\nBase imponible 100,00 EUR")

    assert bodies.qsize() == 0


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

    assert response.text == "off-host completion"
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

    assert response.text == "off-host completion"
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
    ("permitted", "gestor", "acknowledged"),
    [
        (False, False, False),
        (False, False, True),
        (True, False, False),
        (True, True, True),
        (False, True, True),
    ],
)
def test_a_token_cannot_be_minted_unless_every_condition_holds(
    tmp_path: Path,
    *,
    permitted: bool,
    gestor: bool,
    acknowledged: bool,
) -> None:
    """Every combination short of all-three refuses to mint.

    Enumerated rather than sampled, so a future reordering of the gate's
    conditions cannot leave one of them unexercised.
    """
    settings = _settings(tmp_path, cloud_upload_permitted=permitted, gestor_mode=gestor)
    assert cloud_evidence_read_permitted(settings, acknowledged=acknowledged) is False
    with pytest.raises(LLMConsentError):
        mint_evidence_consent_token(
            settings=settings,
            acknowledged=acknowledged,
            surface="aeat app ledger evidence extract",
            evidence_content_address="b" * 64,
        )


def test_the_only_permitting_combination_mints(tmp_path: Path) -> None:
    """POSITIVE CONTROL for the minting side: all three conditions mint a token."""
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    assert cloud_evidence_read_permitted(settings, acknowledged=True) is True
    token = mint_evidence_consent_token(
        settings=settings,
        acknowledged=True,
        surface="aeat app ledger evidence extract",
        evidence_content_address="c" * 64,
    )
    assert token.surface == "aeat app ledger evidence extract"


# ── The token is per-invocation, and cannot become durable ───────────────────


def test_the_token_refuses_every_serialization_path() -> None:
    """A stored token would be the sticky enablement the posture forbids."""
    for dump in (_CONSENTED.model_dump, _CONSENTED.model_dump_json):
        with pytest.raises(LLMConsentError):
            dump()


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
        with pytest.raises(ValueError, match="real surface"):
            EvidenceConsentToken(surface=surface, evidence_content_address=address)


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
