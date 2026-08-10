"""A local outage must never become an off-host read.

This is a confidentiality boundary, not a reliability one. Every other
degradation in this product may be answered by trying something else; this one
may not, because the something else removes a taxpayer's document from the
machine. An automatic fallback would do it at exactly the moment nobody is
watching -- a failure -- and without anyone choosing it.

The behavioural cases run a real local outage with the cloud route fully
configured (a real API key, and the vendor endpoint pointed at a loopback
recorder) and assert on what the CLOUD received, which is zero. Asserting on
the raised exception alone would not distinguish "no fallback exists" from "a
fallback exists and happened to fail too".
"""

from __future__ import annotations

import ast
import asyncio
import json
import socket
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import override

import pytest
from pydantic import SecretStr

from ...adapters.outbound.llm import LLMCache, LLMRunTelemetryRecorder, UsageRecorder
from ...core.config import LLMProvider, override_settings
from ...core.errors import build_error_envelope
from ...tests.fixtures.settings import EnvFileFreeSettings
from .. import LLMClient, LLMConsentError, LLMError, LLMRequest, LLMRetryPolicy
from .._client import reset_on_host_inference_arena

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_NO_RETRY = LLMRetryPolicy(max_attempts=1)


@pytest.fixture(autouse=True)
def _fresh_arena() -> Iterator[None]:
    reset_on_host_inference_arena()
    yield
    reset_on_host_inference_arena()


@contextmanager
def _cloud_recorder() -> Iterator[tuple[str, list[str]]]:
    """Serve a loopback endpoint standing in for the vendor, recording arrivals.

    A real HTTP listener rather than an assertion about code paths: the question
    is whether a request reached an off-host endpoint, and only the endpoint can
    answer it. It is on loopback because a test that could genuinely reach a
    vendor would be the very thing this file exists to forbid.
    """
    arrivals: list[str] = []

    class _Endpoint(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            self.rfile.read(int(self.headers.get("content-length", "0")))
            arrivals.append(self.path)
            # A well-formed vendor answer, so a request that legitimately
            # reaches here COMPLETES. The recorder has to be able to serve a
            # real dispatch, or every case asserting it stayed empty would be
            # satisfied by a recorder nothing could ever reach.
            body = json.dumps(
                {
                    "id": "probe-response",
                    "model": "gpt-4.1",
                    "choices": [{"message": {"content": "cloud completion"}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 2},
                }
            ).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: object) -> None:
            """Silence stdlib request logging during tests."""

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Endpoint)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1/chat/completions", arrivals
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def _dead_local_endpoint() -> str:
    """Return a loopback URL with nothing listening -- a genuine local outage.

    The port is bound and released so it is known to be free, which makes the
    connection refusal deterministic rather than a hope that a random port is
    unused.
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    return f"http://127.0.0.1:{port}/api/chat"


def _client(tmp_path: Path) -> LLMClient:
    settings = EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model="gpt-oss",
        # The cloud route is fully usable: a key is present and the endpoint
        # answers. If a fallback existed, nothing here would stop it.
        cadrumo_llm_openai_api_key=SecretStr("sk-test-key-present"),
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
    )
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_telemetry_recorder=LLMRunTelemetryRecorder(root_dir=settings.cadrumo_llm_run_telemetry_dir),
        retry_policy=_NO_RETRY,
    )


def test_a_local_outage_does_not_reach_the_cloud(tmp_path: Path) -> None:
    """The front door: the configured local provider is down and the cloud is ready."""
    with _cloud_recorder() as (cloud_url, arrivals):
        with (
            override_settings(
                cadrumo_llm_ollama_chat_url=_dead_local_endpoint(),
                cadrumo_llm_openai_chat_completions_url=cloud_url,
            ),
            pytest.raises(LLMError),
        ):
            asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="read this")))

        assert arrivals == []


def test_an_unmarked_request_does_not_reach_the_cloud_either(tmp_path: Path) -> None:
    """The reach-around that matters most: a request the consent gate never sees.

    The consent gate only inspects a request MARKED as evidence-derived, so an
    unmarked request is the path where a fallback would run with no gate in
    front of it at all. Proving the absence of a fallback on the marked path
    only would leave the unwatched half untested -- and the unwatched half is
    where a silent fallback would actually live.
    """
    with _cloud_recorder() as (cloud_url, arrivals):
        request = LLMRequest(prompt="a routine unmarked prompt", evidence_derived=False)
        with (
            override_settings(
                cadrumo_llm_ollama_chat_url=_dead_local_endpoint(),
                cadrumo_llm_openai_chat_completions_url=cloud_url,
            ),
            pytest.raises(LLMError),
        ):
            asyncio.run(_client(tmp_path).complete(request))

        assert arrivals == []


def test_a_permitted_request_pinned_at_the_cloud_does_reach_the_recorder(tmp_path: Path) -> None:
    """The recorder's own control: it CAN record, so an empty one is a fact about the client.

    Every other case here asserts the recorder stayed empty, and an empty
    recorder is exactly what a recorder nothing could reach also produces -- a
    drifted settings key, a changed endpoint path, a client that never wired the
    URL. Each of those would satisfy all three refusal cases identically while
    proving nothing about fallback.

    This is the same argument the file already makes one level up: asserting on
    the exception alone cannot distinguish "no fallback exists" from "a fallback
    exists and also failed". Asserting zero arrivals cannot distinguish "nothing
    was sent" from "nothing could have been recorded".

    Unmarked and deliberately pinned, so no gate stands between the request and
    the transport. Nothing about this makes a fallback reachable: the request
    NAMES its provider, which is the operator choosing, not a degradation
    choosing for them.
    """
    with _cloud_recorder() as (cloud_url, arrivals):
        request = LLMRequest(
            prompt="a routine unmarked prompt",
            evidence_derived=False,
            provider_override=LLMProvider.OPENAI,
        )
        with override_settings(
            cadrumo_llm_ollama_chat_url=_dead_local_endpoint(),
            cadrumo_llm_openai_chat_completions_url=cloud_url,
        ):
            response = asyncio.run(_client(tmp_path).complete(request))

        assert arrivals == ["/v1/chat/completions"]

    assert response.text == "cloud completion"


def test_an_evidence_request_pinned_at_the_cloud_is_refused_before_dispatch(tmp_path: Path) -> None:
    """The consent gate refuses an evidence read off-host, and refuses it EARLY.

    Asserted at the recorder rather than only on the exception type, because
    "refused before dispatch" and "dispatched, then refused" are different
    facts and only one of them keeps the document on this host. The case above
    is what makes this empty recorder meaningful: the same endpoint, reached by
    a permitted request, does record.
    """
    with _cloud_recorder() as (cloud_url, arrivals):
        request = LLMRequest(
            prompt="read this invoice",
            evidence_derived=True,
            provider_override=LLMProvider.OPENAI,
        )
        with (
            override_settings(
                cadrumo_llm_ollama_chat_url=_dead_local_endpoint(),
                cadrumo_llm_openai_chat_completions_url=cloud_url,
            ),
            pytest.raises(LLMConsentError),
        ):
            asyncio.run(_client(tmp_path).complete(request))

        assert arrivals == []


def test_a_local_degradation_names_the_provision_verb(tmp_path: Path) -> None:
    """The refusal carries the remediation that resolves it, and never the cloud."""
    with (
        override_settings(cadrumo_llm_ollama_chat_url=_dead_local_endpoint()),
        pytest.raises(LLMError) as raised,
    ):
        asyncio.run(_client(tmp_path).complete(LLMRequest(prompt="read this")))

    # The remediation TEXT is still produced at the raise site; what the retirement of
    # default suggestions changed is that it no longer reaches the operator. So the
    # safety property is asserted against the live text rather than deferred: this is
    # the exact string the registry conversion will carry into a catalogue action, and a
    # cloud provider name allowed to settle here now would migrate into the delivered
    # action later, when it is far harder to notice.
    remediation = raised.value.suggestion
    assert remediation is not None, "the local-degradation refusal produces no remediation text at all"
    assert "aeat config provision verify --model gpt-oss" in remediation
    lowered = remediation.lower()
    for forbidden in ("openai", "anthropic", "gemini", "cloud", "off-host"):
        assert forbidden not in lowered, (
            f"the local-degradation remediation names {forbidden!r}; an agent-operator follows "
            "the next step it is given, and this one must never be an off-host read"
        )

    # Delivery ground truth, stated so this test cannot be read as proving the operator
    # is told any of the above. Default suggestions were retired as the authority and
    # ``ERROR_LLM`` has not yet been converted to a catalogue action identity, so the
    # envelope carries no next step today. Its conversion is the adapters part-two step,
    # behind the registry migration contract.
    assert build_error_envelope(raised.value).action is None


def _llm_package_modules() -> list[Path]:
    """Return every production module in the LLM package."""
    root = Path(__file__).resolve().parent.parent
    return sorted(path for path in root.rglob("*.py") if "tests" not in path.parts)


_ADAPTER_CONSTRUCTORS = frozenset(
    {"_build_adapter", "AnthropicAdapter", "OpenAIAdapter", "GeminiAdapter", "LocalAdapter"}
)


def _called_names(node: ast.AST) -> set[str]:
    """Return every simple callee name reachable inside ``node``."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _handlers_building_adapters(modules: list[Path]) -> list[str]:
    """Return every failure handler in ``modules`` that constructs a provider adapter."""
    offenders: list[str] = []
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            built = _called_names(node) & _ADAPTER_CONSTRUCTORS
            if built:
                offenders.append(f"{module.name}:{node.lineno} constructs {sorted(built)} while handling a failure")
    return offenders


def _handlers_re_resolving_provider(modules: list[Path]) -> list[str]:
    """Return every failure handler in ``modules`` that re-routes a request at another provider."""
    offenders: list[str] = []
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            for child in ast.walk(node):
                if isinstance(child, ast.keyword) and child.arg == "provider_override":
                    offenders.append(f"{module.name}:{node.lineno} passes provider_override while handling a failure")
                elif (
                    isinstance(child, ast.Attribute)
                    and child.attr == "provider_override"
                    and isinstance(child.ctx, ast.Store)
                ):
                    offenders.append(f"{module.name}:{child.lineno} assigns provider_override while handling a failure")
    return offenders


_FALLBACK_SPECIMEN = '''
"""A synthetic module carrying exactly the defect the detectors look for."""


def read(request):
    try:
        return local_adapter.complete(request)
    except LLMProviderError:
        adapter = OpenAIAdapter(api_key="k", timeout_s=30)
        return adapter.complete(request.model_copy(update={"provider_override": "openai"}))


def reroute(client, request):
    try:
        return client.complete(request)
    except LLMProviderError:
        return client.complete(LLMRequest(prompt=request.prompt, provider_override="openai"))
'''


def test_the_fallback_detectors_find_a_fallback_when_one_exists(tmp_path: Path) -> None:
    """The control the two structural cases below need to mean anything.

    A detector that returns an empty list over a clean tree returns an empty
    list over a broken one too if it is looking in the wrong place, and both
    readings are green. Running the same two detectors over a module written to
    carry the defect is what separates "there is no fallback" from "this
    measures nothing".
    """
    specimen = tmp_path / "specimen.py"
    specimen.write_text(_FALLBACK_SPECIMEN, encoding="utf-8")

    assert _handlers_building_adapters([specimen]), "the adapter-construction detector missed a planted fallback"
    assert _handlers_re_resolving_provider([specimen]), "the provider-reroute detector missed a planted reroute"


def test_no_failure_handler_in_the_package_builds_another_provider() -> None:
    """Structural: a fallback would live in an exception handler, so no handler may build one.

    Stated as a property over EVERY handler in the package rather than as a
    count of dispatch sites: a count encodes today's shape and trains the next
    author to update the constant, while this reds the moment a recovery path
    reaches for a second provider anywhere -- including in a module that does
    not exist yet.
    """
    offenders = _handlers_building_adapters(_llm_package_modules())

    assert not offenders, (
        "a failure handler builds a provider adapter, which is how a local outage becomes a "
        "cloud dispatch nobody chose:\n" + "\n".join(offenders)
    )


def test_no_failure_handler_in_the_package_re_resolves_the_provider() -> None:
    """Structural: nor may a handler re-decide WHICH provider the request runs at.

    The subtler half of the same defect. A handler need not construct an adapter
    to reroute a request -- rewriting the request's provider and re-entering the
    dispatch achieves it, and reads as a retry.
    """
    offenders = _handlers_re_resolving_provider(_llm_package_modules())

    assert not offenders, (
        "a failure handler sets a provider override, re-routing a failed request at another "
        "provider:\n" + "\n".join(offenders)
    )
