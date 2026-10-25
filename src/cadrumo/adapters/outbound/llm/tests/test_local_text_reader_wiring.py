"""The text reader reads through the agent service, under the role's consent rule.

No model runs here. Each case drives the real classifier and the real
:class:`~llm.LLMClient` against a recording stand-in for the agent service, so
which lane a read reached, and whether it reached one at all, is observed at
the model-run port.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from .....core.config_support import LLMProvider
from .....core.model_catalogue import ModelRole
from .....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.llm import PromptSpec, prompt_spec_with_every_spending_category
from .....domain.transactions.models import Transaction
from .....domain.transactions.tests.vision_evidence_support import vision_transaction
from .....tests.fixtures.settings import EnvFileFreeSettings
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient
from ..errors import LLMConsentError
from ..text_classifier import TextLLMClassifier
from .model_run_support import DEFAULT_LANE, ON_HOST_LANE, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_REPLY = json.dumps({"classification": "BUSINESS", "confidence": "0.9", "reason": "Printed as office supplies."})


def _spec() -> PromptSpec:
    with _indexed_authority_for_test().operation() as operation:
        return prompt_spec_with_every_spending_category(year=2025, operation=operation)


def _transaction() -> Transaction:
    with _indexed_authority_for_test().operation() as operation, validating_governed_facts(operation):
        return vision_transaction("ev-1")


def _reader(tmp_path: Path, spec: PromptSpec) -> TextLLMClassifier:
    settings = EnvFileFreeSettings(
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
    )
    return TextLLMClassifier(spec=spec, settings=settings, client=client)


def test_the_text_reader_names_the_agent_and_its_role_and_carries_no_images() -> None:
    """Its request goes to the agent for the text extraction role, marked as evidence, with text only."""
    request = TextLLMClassifier(spec=_spec())._request("classify this")

    assert request.provider_override is LLMProvider.AGENT
    assert request.model_override is None, "the agent resolves the model for the role"
    assert request.model_role is ModelRole.TEXT_EXTRACTION
    assert request.evidence_derived
    assert not request.images, "a text read must carry no images"
    assert request.prompt == "classify this"


def test_an_on_host_lane_reads_the_evidence_without_consent(tmp_path: Path) -> None:
    """A lane that stays on this computer runs the read with no consent and returns its classification."""
    reader = _reader(tmp_path, _spec())
    with serving_agent(replies=(_REPLY,), lane=ON_HOST_LANE) as service:
        response = reader.classify(_transaction(), evidence_text="Office supplies 12,10 EUR")

    assert response.classification is BusinessClassification.BUSINESS
    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    ((header, body),) = service.runs
    assert header.role == ModelRole.TEXT_EXTRACTION.value
    assert header.consent is None
    assert "Office supplies 12,10 EUR" in body.prompt


def test_an_off_host_lane_without_consent_refuses_before_anything_is_sent(tmp_path: Path) -> None:
    """A lane that reads off the host refuses the unconsented evidence read with a typed consent refusal."""
    reader = _reader(tmp_path, _spec())
    with serving_agent(replies=(_REPLY,), lane=DEFAULT_LANE) as service, pytest.raises(LLMConsentError):
        reader.classify(_transaction(), evidence_text="Office supplies 12,10 EUR")

    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert service.runs == [], "the evidence reached the service without consent"


def test_the_provenance_stamp_names_the_agent_transport() -> None:
    """A persisted record says the agent read it; the model is the role's, resolved at dispatch."""
    reader = TextLLMClassifier(spec=_spec())

    assert reader.decided_by == "llm:agent-text:configured"


def test_the_text_model_default_sits_under_the_declared_hardware_floor() -> None:
    """The model is chosen under the hardware constraint, not beside it.

    The floor exists because a model that does not fit does not refuse -- it
    loads and thrashes, or is killed mid-read, and the operator sees an
    unexplained timeout. A default that exceeded its own declared floor would
    make the probe report a capable machine for a model it cannot run.

    Asserted as the PROPERTY, read from the catalogue, rather than against
    pinned model names. The pinned form reddened the moment the defaults moved
    for an unrelated reason (a licence correction), which taught nothing about
    the floor and had to be swept by hand; the property survives any default
    that still respects it.
    """
    from .....core.model_catalogue import ModelRole, model_candidate
    from .....tests.env_scope import isolated_aeat_env, settings_without_env_file

    # The defaults are the subject, so no host override may stand in for them.
    with isolated_aeat_env():
        settings = settings_without_env_file()
    floor = settings.cadrumo_llm_model_runtime_memory_floor_bytes

    for configured, role in (
        (settings.cadrumo_llm_ollama_text_model, ModelRole.TEXT_EXTRACTION),
        (settings.cadrumo_llm_ollama_vision_model, ModelRole.VISION_TRANSCRIPTION),
        (settings.cadrumo_llm_ollama_mapping_model, ModelRole.COLUMN_ROLE_MAPPING),
    ):
        candidate = model_candidate(configured)
        assert candidate is not None, f"the {role.value} default {configured!r} is not catalogued"
        assert candidate.serves(role)
        # The requirement is optional on the catalogue entry, and an undeclared
        # one has already fail-opened twice elsewhere -- read as zero, it makes
        # a contention check report admitted on evidence nobody has. A shipped
        # default must declare it, so that is asserted here rather than assumed.
        requirement = candidate.memory_requirement_bytes
        assert requirement is not None, f"the {role.value} default {configured!r} declares no memory requirement"
        assert requirement < floor, (
            f"the {role.value} default {configured!r} declares {requirement} bytes against a floor of {floor}"
        )

    # The text roles must stay hostable on a machine provisioned for the vision
    # default, so neither may be the heavier model.
    vision = model_candidate(settings.cadrumo_llm_ollama_vision_model)
    text = model_candidate(settings.cadrumo_llm_ollama_text_model)
    mapping = model_candidate(settings.cadrumo_llm_ollama_mapping_model)
    assert vision is not None and text is not None and mapping is not None
    vision_bytes, text_bytes, mapping_bytes = (
        vision.memory_requirement_bytes,
        text.memory_requirement_bytes,
        mapping.memory_requirement_bytes,
    )
    assert vision_bytes is not None and text_bytes is not None and mapping_bytes is not None
    assert text_bytes <= vision_bytes
    assert mapping_bytes <= text_bytes
