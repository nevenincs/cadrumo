"""Vision classifier tests: evidence images reach the agent service for the vision role.

Every case crosses the production :class:`~llm.LLMClient`, its consent gate and
the real agent adapter; the agent service behind the model-run port is a
recording stand-in, so what the service was asked is observed.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunMediaKind, ModelRunRefusalCode

from .....core.image_media_type import ImageMediaType
from .....core.model_roles import ModelRole
from .....domain.categories.spending_category import SpendingCategory
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.llm import PromptSpec, prompt_spec_with_saturation_fields
from .....domain.transactions.tests.vision_evidence_support import vision_transaction
from .....tests.fixtures.settings import EnvFileFreeSettings
from .....tests.llm_vision_evidence_support import png_image
from ....persistence.llm.cache import LLMCache
from ....persistence.llm.usage import UsageRecorder
from ..client import LLMClient
from ..consent import EvidenceConsentToken
from ..errors import LLMConfigError, LLMConsentError
from ..models import MultimodalImageInput
from ..vision_classifier import VisionLLMClassifier
from .model_run_support import serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ON_HOST_VISION_LANE = ModelRunLane(
    provider_id="nearby",
    transport="api",
    model="synthetic-vision:1",
    reads_off_host=False,
    accepted_media=(ModelRunMediaKind.IMAGE,),
    licence=None,
    size_bytes=None,
    vision=True,
    context_length=None,
    installed=None,
)
_OFF_HOST_VISION_LANE = _ON_HOST_VISION_LANE.model_copy(update={"provider_id": "faraway", "reads_off_host": True})


def _classification_json() -> str:
    return json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.9,
            "reason": "office hardware invoice read from the attached image",
            "category": SpendingCategory.from_registry("hardware_amortizable").value,
            "iva_category": IvaCategory("domestic_general").value,
            "business_pct": None,
        },
    )


def _images() -> tuple[MultimodalImageInput, ...]:
    return (MultimodalImageInput.from_base64(base64.b64encode(png_image()).decode("ascii"), ImageMediaType.PNG),)


def _spec(operation: PinnedAuthorityOperation) -> PromptSpec:
    return prompt_spec_with_saturation_fields(year=2025, operation=operation)


def _classifier(
    tmp_path: Path, spec: PromptSpec, *, consent_token: EvidenceConsentToken | None = None
) -> VisionLLMClassifier:
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
    return VisionLLMClassifier(spec=spec, client=client, settings=settings, consent_token=consent_token)


def test_the_classifier_sends_the_images_for_the_vision_role_and_parses_the_reply(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    images = _images()
    classifier = _classifier(tmp_path, _spec(operation))
    with serving_agent(replies=(_classification_json(),), lane=_ON_HOST_VISION_LANE) as service:
        response = classifier.classify(vision_transaction("ev-1"), evidence_images=images)

    assert response.classification is BusinessClassification.BUSINESS
    assert response.category == SpendingCategory.from_registry("hardware_amortizable")
    assert response.iva_category == IvaCategory("domestic_general")
    assert service.lookups == [ModelRole.VISION_TRANSCRIPTION]
    ((header, body),) = service.runs
    assert header.role == ModelRole.VISION_TRANSCRIPTION.value
    assert header.consent is None
    assert [(item.media_type, item.base64_data) for item in body.attachments] == [
        (image.media_type.value, image.base64_data) for image in images
    ]
    # The stamp names the lane and model the agent reported, never a Cadrumo default.
    assert classifier.decided_by == "llm:agent-vision:nearby/api/synthetic-vision:1"


def test_an_off_host_lane_without_consent_refuses_before_any_run(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    classifier = _classifier(tmp_path, _spec(operation))
    with (
        serving_agent(replies=(_classification_json(),), lane=_OFF_HOST_VISION_LANE) as service,
        pytest.raises(LLMConsentError),
    ):
        classifier.classify(vision_transaction("ev-1"), evidence_images=_images())

    assert service.runs == []


def test_an_off_host_lane_with_consent_carries_it_bound_to_the_lane(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    token = EvidenceConsentToken(surface="runtime:ledger.classify", evidence_content_address="d" * 64)
    classifier = _classifier(tmp_path, _spec(operation), consent_token=token)
    with serving_agent(replies=(_classification_json(),), lane=_OFF_HOST_VISION_LANE) as service:
        classifier.classify(vision_transaction("ev-1"), evidence_images=_images())

    ((header, _body),) = service.runs
    assert header.consent is not None
    assert header.consent.evidence_content_address == "d" * 64
    assert header.consent.matches(_OFF_HOST_VISION_LANE)


def test_no_selection_for_the_vision_role_refuses_typed_without_a_run(
    tmp_path: Path, *, operation: PinnedAuthorityOperation
) -> None:
    classifier = _classifier(tmp_path, _spec(operation))
    with (
        serving_agent(lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service,
        pytest.raises(LLMConfigError) as caught,
    ):
        classifier.propose_split(vision_transaction("ev-1"), evidence_images=_images())

    verdict = caught.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.evidence[0].values["model_run_refusal"] == "no_selection"
    assert verdict.evidence[0].values["model_role"] == ModelRole.VISION_TRANSCRIPTION.value
    assert service.runs == []
