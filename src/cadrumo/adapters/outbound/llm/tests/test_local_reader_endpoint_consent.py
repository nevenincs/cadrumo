"""A local reader configured at another machine is off-host for taxpayer evidence.

The provider enum names the transport, not where its endpoint is, so an Ollama
endpoint configured to another host would carry a taxpayer's document off this
machine while the request still says ``local``. These cases send real requests
through the production :class:`LLMClient` and adapter. The remote endpoint is
reached through a recording proxy on loopback, so a document that left for the
remote reader is an arrival at the proxy rather than an inference from an
exception, and each refusal has a positive control proving the same route
would have been observed.
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from pathlib import Path
from queue import Empty, Queue
from typing import ClassVar, override

import pytest

from .....core.config import override_settings
from .....core.config_support import LLMProvider
from .....tests.fixtures.settings import EnvFileFreeSettings
from .....tests.loopback_llm import SilentLoopbackHandler, ollama_chat_reply, serving_loopback, write_json_response
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient
from ..consent import EvidenceConsentToken
from ..errors import LLMConsentError
from ..models import LLMRequest
from ..preconditions import LLMPreconditionCondition

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_REMOTE_READER = "http://reader.example.test:11434/api/chat"
_PROXY_VARIABLES = ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy")
_BYPASS_VARIABLES = ("NO_PROXY", "no_proxy")
_CONSENTED = EvidenceConsentToken(surface="aeat app ledger evidence extract", evidence_content_address="a" * 64)


class _Arrivals(SilentLoopbackHandler):
    """Records each arrival's request target and answers like a reader."""

    arrivals: ClassVar[Queue[str]]
    reply: ClassVar[str]

    @override
    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("content-length", "0")))
        self.arrivals.put(self.path)
        write_json_response(self, ollama_chat_reply(self.reply), status=HTTPStatus.OK)


class _Proxy(_Arrivals):
    reply = "from the remote reader"


class _Reader(_Arrivals):
    reply = "from the loopback reader"


def _settings(
    tmp_path: Path, *, cloud_upload_permitted: bool = False, gestor_mode: bool = False
) -> EnvFileFreeSettings:
    # An uncatalogued model has no declared memory requirement, so the headroom
    # check stays out of the way and a refusal can only be the consent gate.
    return EnvFileFreeSettings(
        cadrumo_llm_ollama_text_model="endpoint-gate-model",
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
        cadrumo_evidence_cloud_upload_permitted=cloud_upload_permitted,
        cadrumo_evidence_gestor_mode=gestor_mode,
    )


def _client(settings: EnvFileFreeSettings) -> LLMClient:
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
    )


def _request(*, evidence_derived: bool, token: EvidenceConsentToken | None = None) -> LLMRequest:
    return LLMRequest(
        prompt="Read this invoice.",
        provider_override=LLMProvider.LOCAL,
        evidence_derived=evidence_derived,
        consent_token=token,
    )


def _route_through_proxy(monkeypatch: pytest.MonkeyPatch, proxy_url: str) -> None:
    proxy = proxy_url.removesuffix("/api/chat")
    for name in _PROXY_VARIABLES:
        monkeypatch.setenv(name, proxy)
    for name in _BYPASS_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _nothing_arrived(arrivals: Queue[str]) -> bool:
    try:
        arrivals.get_nowait()
    except Empty:
        return True
    return False


@pytest.mark.parametrize(
    ("token", "cloud_upload_permitted", "gestor_mode"),
    [
        pytest.param(None, False, False, id="no-consent-token"),
        pytest.param(_CONSENTED, True, False, id="consent-token"),
        pytest.param(_CONSENTED, True, True, id="gestor-mode"),
    ],
)
def test_an_evidence_read_at_a_remote_local_reader_never_leaves_the_host(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    token: EvidenceConsentToken | None,
    cloud_upload_permitted: bool,
    gestor_mode: bool,
) -> None:
    """Refused with or without a token, and in a gestor deployment, before anything is sent.

    A token does not open this route: the ledger entry it would write names the
    provider, not the endpoint, so it could not say where the document went.
    """
    proxy_arrivals: Queue[str] = Queue()
    _Proxy.arrivals = proxy_arrivals
    settings = _settings(tmp_path, cloud_upload_permitted=cloud_upload_permitted, gestor_mode=gestor_mode)
    with serving_loopback(_Proxy, path="/api/chat") as proxy_url:
        _route_through_proxy(monkeypatch, proxy_url)
        with override_settings(cadrumo_llm_ollama_chat_url=_REMOTE_READER), pytest.raises(LLMConsentError) as refused:
            asyncio.run(_client(settings).complete(_request(evidence_derived=True, token=token)))

    assert _nothing_arrived(proxy_arrivals)
    verdict = refused.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == LLMPreconditionCondition.EVIDENCE_LOCAL_READER_LOOPBACK.value


def test_an_unmarked_request_still_reaches_a_remote_local_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POSITIVE CONTROL: the route above would have been observed, and only evidence is gated."""
    proxy_arrivals: Queue[str] = Queue()
    _Proxy.arrivals = proxy_arrivals
    with serving_loopback(_Proxy, path="/api/chat") as proxy_url:
        _route_through_proxy(monkeypatch, proxy_url)
        with override_settings(cadrumo_llm_ollama_chat_url=_REMOTE_READER):
            response = asyncio.run(_client(_settings(tmp_path)).complete(_request(evidence_derived=False)))

    assert response.text == "from the remote reader"
    assert proxy_arrivals.get_nowait() == _REMOTE_READER


def test_an_evidence_read_at_a_loopback_reader_goes_direct_without_consent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POSITIVE CONTROL: on-host reading needs no consent and ignores a configured proxy."""
    reader_arrivals: Queue[str] = Queue()
    proxy_arrivals: Queue[str] = Queue()
    _Reader.arrivals = reader_arrivals
    _Proxy.arrivals = proxy_arrivals
    with (
        serving_loopback(_Proxy, path="/api/chat") as proxy_url,
        serving_loopback(_Reader, path="/api/chat") as reader_url,
    ):
        _route_through_proxy(monkeypatch, proxy_url)
        with override_settings(cadrumo_llm_ollama_chat_url=reader_url):
            response = asyncio.run(_client(_settings(tmp_path)).complete(_request(evidence_derived=True)))

    assert response.text == "from the loopback reader"
    assert reader_arrivals.get_nowait() == "/api/chat"
    assert _nothing_arrived(proxy_arrivals)
