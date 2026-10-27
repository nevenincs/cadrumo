"""An off-host request reaches the agent service through the model-run port, and only there.

Every case crosses the production :class:`LLMClient`, its consent gate, cache
and usage stores, and the real agent adapter. The agent service behind the port
is a recording stand-in, so what the service was asked is observed rather than
assumed; the service side has its own tests.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunRefusalCode

from .....core.config_support import LLMProvider
from .....core.errors.error_codes import resolve_error_message
from .....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from .....core.model_roles import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.consent_ledger import EvidenceConsentLedger
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient
from ..consent import EvidenceConsentToken
from ..errors import LLMConfigError, LLMConsentError, LLMContentionError, LLMProviderError
from ..models import LLMRequest
from ..providers.agent import JSON_REASK_INSTRUCTION
from .model_run_support import DEFAULT_LANE, ON_HOST_LANE, RecordingModelRuns, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TOKEN = EvidenceConsentToken(surface="runtime:ledger.evidence.extract", evidence_content_address="c" * 64)


def _settings(tmp_path: Path, *, cloud_upload_permitted: bool = True) -> EnvFileFreeSettings:
    return EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
        cadrumo_evidence_cloud_upload_permitted=cloud_upload_permitted,
    )


def _client(settings: EnvFileFreeSettings) -> LLMClient:
    return LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
    )


def _request(**fields: object) -> LLMRequest:
    base: dict[str, object] = {
        "prompt": "Classify these lines.",
        "provider_override": LLMProvider.AGENT,
        "model_role": ModelRole.SUPPLY_NATURE_PROPOSAL,
    }
    return LLMRequest.model_validate(base | fields)


def _consented(**fields: object) -> LLMRequest:
    """A request the service admits on the default lane, which reads off-host: it carries evidence consent."""
    return _request(evidence_derived=True, consent_token=_TOKEN, **fields)


def _refusal_code(error: LLMConfigError | LLMConsentError) -> object:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    return verdict.evidence[0].values["model_run_refusal"]


def test_an_agent_request_outside_an_operation_refuses_as_service_unavailable(tmp_path: Path) -> None:
    """No port is bound, so nothing can be asked; the refusal says why."""
    with pytest.raises(LLMConfigError) as caught:
        asyncio.run(_client(_settings(tmp_path)).complete(_request()))

    assert _refusal_code(caught.value) == "service_unavailable"


def test_an_agent_request_that_names_no_role_refuses_before_asking(tmp_path: Path) -> None:
    """The service resolves the lane by role, so a request without one cannot be routed."""
    with serving_agent() as service, pytest.raises(LLMConfigError) as caught:
        asyncio.run(_client(_settings(tmp_path)).complete(_request(model_role=None)))

    verdict = caught.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.agent.model_role_named"
    assert service.lookups == []
    assert service.runs == []


def test_a_completed_run_returns_the_reply_and_names_the_lane_that_served_it(tmp_path: Path) -> None:
    with serving_agent(replies=('{"nature": "goods"}',)) as service:
        response = asyncio.run(_client(_settings(tmp_path)).complete(_consented()))

    assert response.text == '{"nature": "goods"}'
    assert response.provider is LLMProvider.AGENT
    assert response.model == "example/api/example-model-1"
    assert response.cost_estimate_usd is None, "an agent run is unpriced, not free"
    assert service.lookups == [ModelRole.SUPPLY_NATURE_PROPOSAL]
    ((header, body),) = service.runs
    assert header.role == ModelRole.SUPPLY_NATURE_PROPOSAL.value
    assert header.consent is not None and header.consent.matches(DEFAULT_LANE)
    assert body.prompt == "Classify these lines."


def test_a_request_that_states_no_run_option_sends_none_to_the_service(tmp_path: Path) -> None:
    """Cadrumo defaults no reply bound and no sampling temperature: the lane's own behaviour applies."""
    with serving_agent(replies=("{}",)) as service:
        asyncio.run(_client(_settings(tmp_path)).complete(_consented()))

    ((_, body),) = service.runs
    assert body.max_output_tokens is None
    assert body.temperature is None
    assert body.context_tokens is None


def test_the_run_options_a_request_states_reach_the_service_unchanged(tmp_path: Path) -> None:
    with serving_agent(replies=("{}",)) as service:
        asyncio.run(_client(_settings(tmp_path)).complete(_consented(max_tokens=200, temperature=0.0)))

    ((_, body),) = service.runs
    assert body.max_output_tokens == 200
    assert body.temperature == 0.0


def test_a_lookup_refusal_reaches_the_consumer_without_a_run(tmp_path: Path) -> None:
    with (
        serving_agent(lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service,
        pytest.raises(LLMConfigError) as caught,
    ):
        asyncio.run(_client(_settings(tmp_path)).complete(_request()))

    assert _refusal_code(caught.value) == "no_selection"
    assert service.runs == []


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_a_role_with_no_picked_model_says_to_pick_one_in_the_desktop_app(tmp_path: Path, locale: str) -> None:
    with (
        serving_agent(lookup_refusal=ModelRunRefusalCode.NO_SELECTION),
        pytest.raises(LLMConfigError) as caught,
    ):
        asyncio.run(_client(_settings(tmp_path)).complete(_request()))

    sentence = resolve_error_message(caught.value, locale=locale)
    assert sentence != resolve_error_message(LLMConfigError(), locale=locale), "the generic configuration sentence"
    assert "Cadrumo" in sentence
    assert "aeat" not in sentence
    if locale == "en":
        assert sentence == (
            "No model is picked to read with. Pick one in the agent's model picker in the Cadrumo desktop app, "
            "then try again."
        )


@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        (ModelRunRefusalCode.RUN_FAILED, LLMProviderError),
        (ModelRunRefusalCode.REFUSED_BY_PROVIDER, LLMProviderError),
        (ModelRunRefusalCode.DEADLINE_EXCEEDED, LLMProviderError),
        # A caller's misspelled role is a defect, never a prompt to configure a selection.
        (ModelRunRefusalCode.UNKNOWN_ROLE, LLMProviderError),
        (ModelRunRefusalCode.LANE_UNAVAILABLE, LLMConfigError),
        (ModelRunRefusalCode.CONSENT_MISSING, LLMConsentError),
        # The agent decides fit when it loads the model; the same memory meets an immediate re-send.
        (ModelRunRefusalCode.MODEL_DOES_NOT_FIT, LLMContentionError),
    ],
)
def test_each_run_refusal_maps_to_its_typed_error_and_is_not_retried(
    tmp_path: Path, code: ModelRunRefusalCode, error_type: type[Exception]
) -> None:
    """A run whose outcome the service reported is never re-sent as if it had not run."""
    with serving_agent(run_refusal=code) as service, pytest.raises(error_type):
        asyncio.run(_client(_settings(tmp_path)).complete(_consented()))

    assert len(service.runs) == 1


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_a_model_the_agent_cannot_fit_names_the_free_memory_condition_and_how_to_free_it(
    tmp_path: Path, locale: str
) -> None:
    with (
        serving_agent(lane=ON_HOST_LANE, run_refusal=ModelRunRefusalCode.MODEL_DOES_NOT_FIT),
        pytest.raises(LLMContentionError) as caught,
    ):
        asyncio.run(_client(_settings(tmp_path)).complete(_request()))

    verdict = caught.value.terminal_precondition_verdict
    assert verdict is not None
    assert str(verdict.failed_condition_id) == "provisioning.load_capacity.available"
    assert verdict.action is None, "setup cannot free memory"
    assert verdict.evidence[0].values["model_run_refusal"] == "model_does_not_fit"
    sentence = resolve_error_message(caught.value, locale=locale)
    assert "Cadrumo" in sentence
    if locale == "en":
        assert sentence == (
            "The model Cadrumo reads with does not fit in this computer's free memory right now. "
            "Close other programs, then try again."
        )


def test_a_consented_evidence_run_binds_its_consent_to_the_resolved_lane(tmp_path: Path) -> None:
    """The ledger names the lane that will run, and the run carries the same lane.

    Both halves are asserted, because the service refuses ``consent_missing``
    when the lane it would use differs from the one the consent names.
    """
    request = _request(evidence_derived=True, consent_token=_TOKEN)
    with serving_agent() as service:
        asyncio.run(_client(_settings(tmp_path)).complete(request))

    ((header, _),) = service.runs
    assert header.consent is not None
    assert header.consent.evidence_content_address == _TOKEN.evidence_content_address
    assert header.consent.matches(DEFAULT_LANE)
    (entry,) = EvidenceConsentLedger().load_entries()
    assert entry.provider == LLMProvider.AGENT.value
    assert entry.model == "example/api/example-model-1"
    assert entry.evidence_content_address == _TOKEN.evidence_content_address


def test_an_unconsented_evidence_request_is_refused_before_any_run(tmp_path: Path) -> None:
    with serving_agent() as service, pytest.raises(LLMConsentError):
        asyncio.run(_client(_settings(tmp_path)).complete(_request(evidence_derived=True)))

    assert service.runs == []


def test_an_evidence_request_on_a_lane_declared_on_host_runs_without_consent_or_a_ledger_entry(
    tmp_path: Path,
) -> None:
    """The lane's flag alone decides: no token is demanded, none is sent and nothing is recorded."""
    with serving_agent(lane=ON_HOST_LANE) as service:
        response = asyncio.run(
            _client(_settings(tmp_path, cloud_upload_permitted=False)).complete(_request(evidence_derived=True))
        )

    assert response.model == "nearby/api/synthetic-reader-1"
    ((header, _),) = service.runs
    assert header.consent is None
    assert EvidenceConsentLedger().load_entries() == ()


def test_a_token_taken_before_the_lane_was_known_is_neither_bound_nor_recorded_on_an_on_host_lane(
    tmp_path: Path,
) -> None:
    """A consent sent with an on-host run would be refused by the service as naming another lane."""
    request = _request(evidence_derived=True, consent_token=_TOKEN)
    with serving_agent(lane=ON_HOST_LANE) as service:
        asyncio.run(_client(_settings(tmp_path)).complete(request))

    ((header, _),) = service.runs
    assert header.consent is None
    assert EvidenceConsentLedger().load_entries() == ()


def test_an_unconsented_evidence_request_on_a_lane_declared_off_host_is_refused_whatever_its_name(
    tmp_path: Path,
) -> None:
    """A lane named like a local one still needs consent when its catalogue entry says it reads off-host."""
    lane = ON_HOST_LANE.model_copy(update={"reads_off_host": True})
    with serving_agent(lane=lane) as service, pytest.raises(LLMConsentError):
        asyncio.run(_client(_settings(tmp_path)).complete(_request(evidence_derived=True)))

    assert service.runs == []
    assert EvidenceConsentLedger().load_entries() == ()


def test_a_json_reply_without_an_object_is_asked_for_once_more(tmp_path: Path) -> None:
    with serving_agent(replies=("I think it is goods.", '{"nature": "goods"}')) as service:
        response = asyncio.run(_client(_settings(tmp_path)).complete(_consented(expects_json=True)))

    assert response.text == '{"nature": "goods"}'
    first, second = (body for _, body in service.runs)
    assert JSON_REASK_INSTRUCTION not in first.prompt
    assert second.prompt.endswith(JSON_REASK_INSTRUCTION)


def test_a_second_reply_without_an_object_refuses_as_output_invalid(tmp_path: Path) -> None:
    with serving_agent(replies=("no object here",)) as service, pytest.raises(LLMProviderError) as caught:
        asyncio.run(_client(_settings(tmp_path)).complete(_consented(expects_json=True)))

    assert len(service.runs) == 2
    assert caught.value.context is not None
    assert caught.value.context["model_run_refusal"] == "output_invalid"


def test_an_injected_port_wins_over_the_bound_one(tmp_path: Path) -> None:
    injected = RecordingModelRuns(
        lane=ModelRunLane(
            provider_id="other",
            transport="cli",
            model="m",
            reads_off_host=True,
            licence=None,
            size_bytes=None,
            vision=None,
            context_length=None,
            installed=None,
        )
    )
    settings = _settings(tmp_path)
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        model_runs=injected,
    )
    with serving_agent() as bound:
        response = asyncio.run(client.complete(_consented()))

    assert response.model == "other/cli/m"
    assert bound.runs == []
    assert len(injected.runs) == 1
