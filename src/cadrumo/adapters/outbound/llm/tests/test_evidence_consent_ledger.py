"""The off-host consent ledger records every dispatch it permits, or refuses it.

Four properties, each proved against a real encrypted secure-object backend
(the package ``conftest`` binds a per-test bucket) and a real
:class:`~llm.EvidenceConsentToken`:

* **positive control** -- with the append working, a consented off-host
  evidence request DOES reach the provider adapter, and exactly one entry lands.
  Without this, the refusal test below is worthless: a probe whose "permitted"
  case cannot transmit either proves nothing about the "refused" case.
* **the entry carries no content** -- the persisted bytes hold the content
  ADDRESS, provider, model and surface, and neither the prompt nor the response
  text. An audit trail that copies the document is a second leak.
* **a failed append refuses the dispatch** -- the adapter is never reached. The
  failure is a real one (no bucket session is bound, the production condition
  the ledger raises on), and the refusal is pinned to the LEDGER's own message,
  because everything downstream of the append needs storage too and would
  otherwise refuse for its own reasons.
* **the append precedes the cache read** -- proved with storage healthy and a
  primed entry, so the confound above is absent: only a failing ledger
  distinguishes the refused call from the cache hit the call before it served.

The provider adapter is a recording subclass replacing exactly one thing: the
vendor call. Nothing else in the dispatch path is substituted -- the settings,
the gate, the token, the ledger and the storage are all real -- because what is
under test is the ORDER of the real steps, and a substituted step cannot be
ordered against. The one exception is the last test's deliberately-failing
ledger, which is the injected collaborator whose failure IS the property.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from typing import override

import pytest

from .....core.config import Settings
from .....core.external_constants import UTF_8_ENCODING
from .....domain.evidence_consent._record import EvidenceConsentLedgerEntry
from .....llm.client import LLMClient
from .....llm.consent import EvidenceConsentToken
from .....llm.errors import LLMConsentError
from .....llm.models import LLMProvider, LLMRequest
from .....llm.providers.base import ProviderAdapter, ProviderCompletion, ProviderRequest
from ....persistence.storage.master_key.active_session import close_active_bucket_session
from ....persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ....persistence.storage.secure_object_namespaces import LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE
from .._consent_ledger import EvidenceConsentLedger

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_ADDRESS = "a" * 64
_SURFACE = "app.ledger.invoice.read"
_PROMPT = "Read the invoice total from this document, DISTINCTIVE-PROMPT-TOKEN."
_COMPLETION_TEXT = "DISTINCTIVE-RESPONSE-TOKEN: 1.234,56 EUR"


class _CapturingAdapter(ProviderAdapter):
    """An off-host adapter that records the dispatch instead of calling a vendor."""

    provider = LLMProvider.ANTHROPIC
    supports_images = True

    def __init__(self) -> None:
        self.dispatched: list[ProviderRequest] = []

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:
        self.dispatched.append(request)
        return ProviderCompletion(text=_COMPLETION_TEXT, model=request.model, input_tokens=11, output_tokens=7)


class _CapturingClient(LLMClient):
    """``LLMClient`` with only the vendor call replaced."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        consent_ledger: EvidenceConsentLedger | None = None,
    ) -> None:
        """Forward the two dependencies the cases here vary.

        Named rather than forwarded through ``**kwargs: object``, which erased
        every argument and needed a suppression to reach the base constructor
        at all -- so nothing checked that these tests were configuring the
        client the way production does.
        """
        super().__init__(settings=settings, consent_ledger=consent_ledger)
        self.adapter = _CapturingAdapter()

    @override
    def _build_adapter(self, provider: LLMProvider) -> ProviderAdapter:
        return self.adapter


def _consented_settings() -> Settings:
    return Settings(
        cadrumo_evidence_gestor_mode=False,
        cadrumo_evidence_cloud_upload_permitted=True,
    )


def _evidence_request() -> LLMRequest:
    return LLMRequest(
        prompt=_PROMPT,
        provider_override=LLMProvider.ANTHROPIC,
        model_override="claude-sonnet-4-6",
        evidence_derived=True,
        consent_token=EvidenceConsentToken(surface=_SURFACE, evidence_content_address=_ADDRESS),
    )


@pytest.fixture
def client(secure_object_test_profile: object) -> Iterator[_CapturingClient]:
    _ = secure_object_test_profile
    yield _CapturingClient(settings=_consented_settings())


def test_a_consented_off_host_dispatch_reaches_the_adapter_and_lands_one_entry(
    client: _CapturingClient,
) -> None:
    """The positive control: consent working means the transmission DOES happen."""
    response = asyncio.run(client.complete(_evidence_request()))

    assert len(client.adapter.dispatched) == 1, "the positive control must actually transmit"
    assert response.text == _COMPLETION_TEXT

    entries = EvidenceConsentLedger().load_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.evidence_content_address == _ADDRESS
    assert entry.provider == LLMProvider.ANTHROPIC.value
    assert entry.model == "claude-sonnet-4-6"
    assert entry.surface == _SURFACE
    assert entry.profile_bucket_id


def test_an_on_host_or_unmarked_request_records_nothing(client: _CapturingClient) -> None:
    """The ledger records off-host EVIDENCE dispatches, not every completion."""
    asyncio.run(client.complete(LLMRequest(prompt=_PROMPT, provider_override=LLMProvider.ANTHROPIC)))

    assert len(client.adapter.dispatched) == 1
    assert EvidenceConsentLedger().load_entries() == ()


def test_the_persisted_entry_carries_neither_prompt_nor_response_text(client: _CapturingClient) -> None:
    """The ledger holds the address, never the bytes."""
    asyncio.run(client.complete(_evidence_request()))

    stored = list(
        secure_object_repository_for_active_bucket().list_records(
            LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.namespace,
            expected_class=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.sensitivity,
            max_supported_version=LLM_EVIDENCE_CONSENT_LEDGER_NAMESPACE.schema_version,
        ),
    )
    assert len(stored) == 1
    payload = stored[0].payload.decode(UTF_8_ENCODING)
    assert "DISTINCTIVE-PROMPT-TOKEN" not in payload
    assert "DISTINCTIVE-RESPONSE-TOKEN" not in payload
    assert json.loads(payload)["entry"]["evidence_content_address"] == _ADDRESS


def test_a_failed_append_refuses_the_dispatch_and_the_adapter_is_never_reached(
    client: _CapturingClient,
) -> None:
    """A ledger that cannot record must stop the transmission, not proceed unrecorded.

    A real append failure, not a patched one: with no bucket session bound there
    is nothing to record against, and the ledger raises on exactly that. The
    message assertion is what makes this discriminating -- everything downstream
    of the append also needs storage, so the refusal must be shown to be the
    LEDGER's and not a later guard's.
    """
    close_active_bucket_session()

    with pytest.raises(LLMConsentError) as excinfo:
        asyncio.run(client.complete(_evidence_request()))

    assert "audit trail" in str(excinfo.value), "the refusal must be the ledger's, not a downstream storage guard's"
    assert client.adapter.dispatched == [], (
        "a dispatch whose consent entry could not be appended must not reach the provider"
    )


class _FailingLedger(EvidenceConsentLedger):
    """A ledger whose append fails the way a storage fault makes it fail."""

    @override
    def append(
        self,
        *,
        evidence_content_address: str,
        provider: str,
        model: str,
        surface: str,
    ) -> EvidenceConsentLedgerEntry:
        msg = "Failed to record the off-host evidence-consent entry; the dispatch is refused."
        raise LLMConsentError(msg)


def test_a_failed_append_refuses_even_a_cache_hit(secure_object_test_profile: object) -> None:
    """The append precedes the cache read, so a primed entry cannot serve an unrecorded dispatch.

    The discriminating ordering probe. Storage stays fully healthy here and the
    first call proves the request IS cacheable and IS servable; only the ledger
    is swapped for one that fails. If the append were ordered after the cache
    read -- or were best-effort -- the second call would return the primed
    response with no entry behind it, which is precisely the silent gap the
    ledger exists to close.
    """
    _ = secure_object_test_profile
    settings = _consented_settings()

    primed = _CapturingClient(settings=settings)
    first = asyncio.run(primed.complete(_evidence_request()))
    assert first.cache_hit is False
    assert len(primed.adapter.dispatched) == 1

    served = _CapturingClient(settings=settings)
    cache_hit = asyncio.run(served.complete(_evidence_request()))
    assert cache_hit.cache_hit is True, "the positive control must show the entry really is served from cache"
    assert served.adapter.dispatched == []

    refused = _CapturingClient(settings=settings, consent_ledger=_FailingLedger())
    with pytest.raises(LLMConsentError):
        asyncio.run(refused.complete(_evidence_request()))
    assert refused.adapter.dispatched == []
