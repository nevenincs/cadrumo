"""Loopback local-vision classifier tests for evidence classification."""

from __future__ import annotations

import base64
import json

import pytest

from ...application.ledger._llm_classification import _classify_with_evidence, _ResolvedEvidence
from ...application.ledger.tests._llm_vision_evidence_support import (
    _json_array,
    _json_object,
    _png_image,
    _run_against_loopback_ollama,
    _transaction,
)
from ...application.ledger.tests._llm_vision_evidence_support import (
    profile as profile,
)
from ...core import ImageMediaType
from ...core.config import load_settings
from ...domain.categories import SpendingCategory
from ...domain.iva import IvaCategory
from ...domain.transactions import (
    BusinessClassification,
    LLMClassificationResponse,
    prompt_spec_with_saturation_fields,
)
from ...tests.secure_sql import TestRuntimeProfile
from .._models import MultimodalImageInput
from .._vision_classifier import LocalVisionLLMClassifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["profile"]


def test_vision_classifier_classifies_from_images(profile: TestRuntimeProfile) -> None:
    """The vision classifier sends the images to the local model and parses the result."""
    _ = profile
    classification_json = json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.9,
            "reason": "office hardware invoice read from the attached image",
            "category": SpendingCategory.HARDWARE_AMORTIZABLE.value,
            "iva_category": IvaCategory.DOMESTIC_GENERAL.value,
            "business_pct": None,
        },
    )
    images = (MultimodalImageInput.from_base64(base64.b64encode(_png_image()).decode("ascii"), ImageMediaType.PNG),)

    def _call() -> LLMClassificationResponse:
        classifier = LocalVisionLLMClassifier(spec=prompt_spec_with_saturation_fields(), model="llava-test")
        return classifier.classify(_transaction("ev-1"), evidence_images=images)

    observed, response = _run_against_loopback_ollama(classification_json, _call)
    assert response.classification is BusinessClassification.BUSINESS
    assert response.category is SpendingCategory.HARDWARE_AMORTIZABLE
    assert response.iva_category is IvaCategory.DOMESTIC_GENERAL

    body = _json_object(observed["body"])
    messages = _json_array(body["messages"])
    user_message = _json_object(messages[-1])
    assert user_message["images"] == [image.base64_data for image in images]


def test_image_evidence_classifies_with_no_provider(profile: TestRuntimeProfile) -> None:
    """Image evidence routes to the vision model even with no --llm provider."""
    _ = profile
    classification_json = json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.88,
            "reason": "scanned office-supplies invoice read on-host",
            "category": SpendingCategory.HARDWARE_AMORTIZABLE.value,
            "iva_category": IvaCategory.DOMESTIC_GENERAL.value,
            "business_pct": None,
        },
    )
    evidence = _ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(MultimodalImageInput.from_base64(base64.b64encode(_png_image()).decode("ascii"), ImageMediaType.PNG),),
    )

    def _call() -> tuple[LLMClassificationResponse, str]:
        return _classify_with_evidence(
            _transaction("ev-1"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=None,
            vision_model=None,
            settings=load_settings(),
        )

    _observed, (response, provenance) = _run_against_loopback_ollama(classification_json, _call)
    assert response.classification is BusinessClassification.BUSINESS
    assert provenance.startswith("llm:local-vision:")


def test_text_path_without_a_cloud_provider_now_routes_on_host() -> None:
    """The text path no longer demands a cloud provider; it reads on-host.

    This test previously asserted the OPPOSITE -- that the branch refused with
    "needs a cloud provider" -- and that refusal was the mechanism behind the
    inverted privacy posture: a text-layer document, the more machine-readable
    one, was the only class whose contents had to leave the host, decided by
    nothing but how the file happened to be produced.

    Inverted deliberately rather than deleted, so the change of posture is
    visible in the test history rather than silently disappearing from it. The
    refusal that survives is about the RUNTIME being unreachable, which is a
    provisioning problem with a stated fix, not a transport policy.
    """
    from ...domain.transactions import LLMClassifierError

    with pytest.raises(LLMClassifierError, match="on-host"):
        _classify_with_evidence(
            _transaction("ev-1"),
            None,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=None,
            vision_model=None,
            settings=load_settings(),
        )


def test_vision_connection_error_becomes_a_typed_refusal_with_fix(profile: TestRuntimeProfile) -> None:
    """A down/unreachable Ollama is converted to LLMClassifierError, not a raw traceback."""
    from ...domain.transactions import LLMClassifierError

    _ = profile
    evidence = _ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(MultimodalImageInput.from_base64(base64.b64encode(_png_image()).decode("ascii"), ImageMediaType.PNG),),
    )
    unreachable_settings = load_settings().model_copy(
        update={
            "cadrumo_llm_ollama_chat_url": "http://127.0.0.1:1/api/chat",
            "cadrumo_llm_vision_read_timeout_s": 1,
        },
    )
    classifier = LocalVisionLLMClassifier(
        spec=prompt_spec_with_saturation_fields(),
        settings=unreachable_settings,
    )
    with pytest.raises(LLMClassifierError, match=r"model reading failed.*Fix:"):
        _classify_with_evidence(
            _transaction("ev-1"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=classifier,
            vision_model=None,
            settings=unreachable_settings,
        )


def test_vision_model_override_selects_the_named_model(profile: TestRuntimeProfile) -> None:
    """--vision-model threads through to the request model and the provenance stamp."""
    _ = profile
    classification_json = json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.8,
            "reason": "office invoice",
            "category": SpendingCategory.HARDWARE_AMORTIZABLE.value,
            "iva_category": IvaCategory.DOMESTIC_GENERAL.value,
        },
    )
    evidence = _ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(MultimodalImageInput.from_base64(base64.b64encode(_png_image()).decode("ascii"), ImageMediaType.PNG),),
    )

    def _call() -> tuple[LLMClassificationResponse, str]:
        return _classify_with_evidence(
            _transaction("ev-1"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=None,
            vision_model="qwen2.5vl:7b",
            settings=load_settings(),
        )

    observed, (_response, provenance) = _run_against_loopback_ollama(classification_json, _call)
    assert provenance == "llm:local-vision:qwen2.5vl:7b"
    body = _json_object(observed["body"])
    assert body["model"] == "qwen2.5vl:7b"
