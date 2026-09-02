"""The extract verb can mint a consent token, and refuses every incomplete way of asking.

The consent gate, its ledger, the per-profile eligibility bar and the withdrawal
verb all shipped before any surface could mint a token. That left the lifecycle
correct and incomplete in one specific way: in production the gate refused
*every* off-host evidence read, because nothing could produce the token it
demands. This module covers the surface that closes it.

**The positive control is the load-bearing case here.** Every "refuses without
consent" assertion below passes equally against a path that refuses always --
including one that can no longer dispatch at all -- so a refusal-only suite
would be satisfied by a broken feature. The control therefore mints a REAL token
through the real minting path and drives a real HTTP request into a real
loopback endpoint, asserting the body arrived. It could genuinely have failed:
if a minted token did not satisfy the dispatch-point gate, the queue would be
empty.

The refusals are asserted on their CONSEQUENCE rather than on the call raising.
Where a value was chosen by the code -- which surface a token names, whether a
provider reached the request -- the assertion names that value, because "it
raised" is equally true of a surface that refuses for an unrelated reason.

No model runs. The endpoint is loopback and nothing leaves the machine.
"""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from queue import Queue
from typing import override

import pytest
from pydantic import SecretStr

from ....adapters.outbound.llm.cache import LLMCache
from ....adapters.outbound.llm.usage import UsageRecorder
from ....application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ....core.config import override_settings
from ....core.field_origin import FieldOrigin
from ....core.provenance_stamp import LOCAL_TRANSPORT_LABEL
from ....llm.client import LLMClient
from ....llm.consent import mint_evidence_consent_token
from ....llm.errors import LLMConsentError
from ....llm.evidence_draft_text import TextInvoiceFieldExtractor
from ....llm.models import LLMProvider
from ....tests.fixtures.settings import EnvFileFreeSettings
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    openai_chat_reply,
    read_text_body,
    serving_loopback,
    write_json_response,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile

# INTEGRATION, not unit, and the reason is a production guard rather than a
# preference: a consented off-host dispatch writes a consent-ledger entry, and
# the ledger refuses outright when no profile bucket session is open, because a
# transmission that leaves no audit trail must not happen. Proving the consented
# path therefore requires a real bucket runtime -- real KEK/DEK, real SQLite --
# and a lane that mocked it would be asserting the audit trail exists by
# assuming it.
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    """Provision a real active-profile bucket runtime for the transport cases."""
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_BUCKET_ID,
        label="Test evidence consent profile",
    ) as profile:
        yield profile


_CONTENT_ADDRESS = "a" * 64
_SURFACE = "cli:ledger.evidence.extract"


def _settings(tmp_path: Path, *, cloud_upload_permitted: bool, gestor_mode: bool = False) -> EnvFileFreeSettings:
    """Build settings with the LLM stores inside ``tmp_path``.

    The OpenAI key is populated in EVERY case, refusals included. An absent
    credential is an accident that looks like a control: with the key unset the
    provider refuses first, and the suite would go green on a consent boundary
    that had stopped working.
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


@contextmanager
def _serve_openai() -> Generator[tuple[str, Queue[str]]]:
    """Serve an OpenAI-shaped endpoint on loopback, recording every body that arrives.

    The queue is what makes "the document was transmitted" an observation rather
    than an inference from the absence of an exception.
    """
    bodies: Queue[str] = Queue()

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            bodies.put(read_text_body(self))
            write_json_response(
                self,
                openai_chat_reply(
                    '{"taxable_base": "100,00"}',
                    prompt_tokens=1,
                    completion_tokens=1,
                ),
                status=HTTPStatus.OK,
            )

    with serving_loopback(_Endpoint, path="/v1/chat/completions") as endpoint:
        yield endpoint, bodies


def _transcription() -> DocumentTranscription:
    return DocumentTranscription(
        text="FACTURA Base imponible 100,00 EUR",
        page_count=1,
        source_content_sha256=_CONTENT_ADDRESS,
        transcriber=TranscriberIdentity(
            origin=FieldOrigin.TEXT_LAYER,
            name="pdfplumber",
            transport=LOCAL_TRANSPORT_LABEL,
            revision="gate",
        ),
    )


def _client(settings: EnvFileFreeSettings) -> LLMClient:
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
    )


# ── The positive control: a consented read genuinely transmits ───────────────


def test_a_minted_token_carries_an_evidence_read_all_the_way_to_the_endpoint(
    tmp_path: Path,
    runtime_profile: TestRuntimeProfile,
) -> None:
    """THE control. A real token, a real request, a real body at a real endpoint.

    Without this, every refusal in this module is satisfied by a path that
    refuses unconditionally, and the feature could ship unable to transmit at
    all while the suite stayed green. That trap has caught two lanes on this
    campaign.

    The token is minted through the SOLE constructor rather than built directly,
    so what is proven is that the production minting path yields something the
    dispatch-point gate accepts -- not merely that a hand-built token would.
    """
    _ = runtime_profile
    settings = _settings(tmp_path, cloud_upload_permitted=True)
    token = mint_evidence_consent_token(
        settings=settings,
        profile_eligible=True,
        acknowledged=True,
        surface=_SURFACE,
        evidence_content_address=_CONTENT_ADDRESS,
    )

    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        extractor = TextInvoiceFieldExtractor(
            provider=LLMProvider.OPENAI,
            model="gpt-4.1",
            settings=settings,
            client=_client(settings),
            consent_token=token,
        )
        draft = extractor.extract(transcription=_transcription())

    assert bodies.qsize() == 1, "a consented off-host read must actually reach the provider"
    # The consequence, not merely that the call returned: the endpoint's reply
    # has to have been read back into the draft, or the transport is only
    # half-proven.
    assert draft.taxable_base == 100


def test_the_same_read_without_the_token_reaches_nothing(
    tmp_path: Path,
    runtime_profile: TestRuntimeProfile,
) -> None:
    """The discriminating negative, differing from the control in ONE variable.

    Same settings, same provider, same model, same endpoint, same reader -- only
    the token is withheld. That single-variable difference is what makes the
    empty queue evidence about consent rather than about configuration.
    """
    _ = runtime_profile
    settings = _settings(tmp_path, cloud_upload_permitted=True)

    with _serve_openai() as (endpoint, bodies), override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
        extractor = TextInvoiceFieldExtractor(
            provider=LLMProvider.OPENAI,
            model="gpt-4.1",
            settings=settings,
            client=_client(settings),
        )
        with pytest.raises(LLMConsentError):
            extractor.extract(transcription=_transcription())

    assert bodies.qsize() == 0, "an unconsented read must not reach the provider"


# ── The minting path's own refusals ──────────────────────────────────────────


def test_minting_refuses_while_the_deployment_has_not_opted_in(tmp_path: Path) -> None:
    """An untouched deployment cannot mint, so no surface can offer a working gate."""
    with pytest.raises(LLMConsentError):
        mint_evidence_consent_token(
            settings=_settings(tmp_path, cloud_upload_permitted=False),
            profile_eligible=True,
            acknowledged=True,
            surface=_SURFACE,
            evidence_content_address=_CONTENT_ADDRESS,
        )


def test_minting_refuses_a_gestor_deployment_outright(tmp_path: Path) -> None:
    """The categorical bar: a gestor never transmits a client's document.

    Asserted with every other condition satisfied, so the refusal can only be
    the gestor bar. A case that also left the opt-in off would pass whether or
    not the gestor condition existed.
    """
    with pytest.raises(LLMConsentError):
        mint_evidence_consent_token(
            settings=_settings(tmp_path, cloud_upload_permitted=True, gestor_mode=True),
            profile_eligible=True,
            acknowledged=True,
            surface=_SURFACE,
            evidence_content_address=_CONTENT_ADDRESS,
        )


def test_minting_refuses_when_the_profile_bar_is_off(tmp_path: Path) -> None:
    """Deployment opt-in does not decide it for every taxpayer on the machine."""
    with pytest.raises(LLMConsentError):
        mint_evidence_consent_token(
            settings=_settings(tmp_path, cloud_upload_permitted=True),
            profile_eligible=False,
            acknowledged=True,
            surface=_SURFACE,
            evidence_content_address=_CONTENT_ADDRESS,
        )


def test_minting_refuses_without_the_per_invocation_acknowledgement(tmp_path: Path) -> None:
    """Standing eligibility is not consent; the acknowledgement is never sticky."""
    with pytest.raises(LLMConsentError):
        mint_evidence_consent_token(
            settings=_settings(tmp_path, cloud_upload_permitted=True),
            profile_eligible=True,
            acknowledged=False,
            surface=_SURFACE,
            evidence_content_address=_CONTENT_ADDRESS,
        )


def test_the_token_names_the_verb_that_took_the_acknowledgement(tmp_path: Path) -> None:
    """The recorded surface must identify the VERB, not the entrypoint.

    A withdrawal survey answers "where was this acknowledged", and a whole-CLI
    label cannot. Asserting the value rather than that minting succeeded is the
    point: the surface is a value this code chose.
    """
    token = mint_evidence_consent_token(
        settings=_settings(tmp_path, cloud_upload_permitted=True),
        profile_eligible=True,
        acknowledged=True,
        surface=_SURFACE,
        evidence_content_address=_CONTENT_ADDRESS,
    )

    assert token.surface == "cli:ledger.evidence.extract"
    assert token.evidence_content_address == _CONTENT_ADDRESS
