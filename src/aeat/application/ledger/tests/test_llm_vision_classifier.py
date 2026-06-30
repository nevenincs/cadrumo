"""Loopback local-vision classifier tests for evidence classification."""

from __future__ import annotations

import base64
import json

import pytest

from ....core.config import load_settings
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    LLMClassificationResponse,
    TransactionValidationError,
    prompt_spec_with_saturation_fields,
)
from ....tests.secure_sql import TestRuntimeProfile
from .._llm_classification import _classify_with_evidence, _ResolvedEvidence
from .._vision_classifier import LocalVisionLLMClassifier
from ._llm_vision_evidence_support import (
    _json_array,
    _json_object,
    _png_image,
    _run_against_loopback_ollama,
    _transaction,
)
from ._llm_vision_evidence_support import (
    profile as profile,
)

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
            "iva_category": IvaCategory.DOMESTIC_GENERAL_21.value,
            "business_pct": None,
        },
    )
    images = (base64.b64encode(_png_image()).decode("ascii"),)

    def _call() -> LLMClassificationResponse:
        classifier = LocalVisionLLMClassifier(spec=prompt_spec_with_saturation_fields(), model="llava-test")
        return classifier.classify(_transaction("ev-1"), evidence_images=images)

    observed, response = _run_against_loopback_ollama(classification_json, _call)
    assert response.classification is BusinessClassification.BUSINESS
    assert response.category is SpendingCategory.HARDWARE_AMORTIZABLE
    assert response.iva_category is IvaCategory.DOMESTIC_GENERAL_21

    body = _json_object(observed["body"])
    messages = _json_array(body["messages"])
    user_message = _json_object(messages[-1])
    assert user_message["images"] == list(images)


def test_image_evidence_classifies_with_no_provider(profile: TestRuntimeProfile) -> None:
    """Image evidence routes to the vision model even with no --llm provider."""
    _ = profile
    classification_json = json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.88,
            "reason": "scanned office-supplies invoice read on-host",
            "category": SpendingCategory.HARDWARE_AMORTIZABLE.value,
            "iva_category": IvaCategory.DOMESTIC_GENERAL_21.value,
            "business_pct": None,
        },
    )
    evidence = _ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(base64.b64encode(_png_image()).decode("ascii"),),
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


def test_text_or_no_evidence_without_provider_refuses_instructively() -> None:
    """Without a provider and without readable image evidence, the text path refuses."""
    with pytest.raises(TransactionValidationError, match="needs a cloud provider"):
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
    from ....domain.transactions import LLMClassifierError

    _ = profile
    evidence = _ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(base64.b64encode(_png_image()).decode("ascii"),),
    )
    unreachable_settings = load_settings().model_copy(
        update={
            "aeat_llm_ollama_chat_url": "http://127.0.0.1:1/api/chat",
            "aeat_llm_vision_read_timeout_s": 1,
        },
    )
    classifier = LocalVisionLLMClassifier(
        spec=prompt_spec_with_saturation_fields(),
        settings=unreachable_settings,
    )
    with pytest.raises(LLMClassifierError, match=r"vision reading failed.*Fix:"):
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
            "iva_category": IvaCategory.DOMESTIC_GENERAL_21.value,
        },
    )
    evidence = _ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(base64.b64encode(_png_image()).decode("ascii"),),
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
