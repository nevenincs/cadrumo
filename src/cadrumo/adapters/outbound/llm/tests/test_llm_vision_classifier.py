"""Loopback local-vision classifier tests for evidence classification."""

from __future__ import annotations

import base64
import json

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from .....core.image_media_type import ImageMediaType
from .....domain.categories.spending_category import SpendingCategory
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.llm import LLMClassificationResponse, prompt_spec_with_saturation_fields
from .....domain.transactions.tests.vision_evidence_support import vision_transaction
from .....tests.llm_vision_evidence_support import (
    json_array,
    json_object,
    png_image,
    run_against_loopback_ollama,
)
from ..models import MultimodalImageInput
from ..vision_classifier import LocalVisionLLMClassifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_vision_classifier_classifies_from_images() -> None:
    """The vision classifier sends the images to the local model and parses the result."""
    classification_json = json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.9,
            "reason": "office hardware invoice read from the attached image",
            "category": SpendingCategory.from_registry("hardware_amortizable").value,
            "iva_category": IvaCategory("domestic_general").value,
            "business_pct": None,
        },
    )
    images = (MultimodalImageInput.from_base64(base64.b64encode(png_image()).decode("ascii"), ImageMediaType.PNG),)

    with _indexed_authority_for_test().operation() as _authority_operation_for_test:

        def _call() -> LLMClassificationResponse:
            classifier = LocalVisionLLMClassifier(
                spec=prompt_spec_with_saturation_fields(year=2025, operation=_authority_operation_for_test),
                model="llava-test",
            )
            return classifier.classify(vision_transaction("ev-1"), evidence_images=images)

        observed, response = run_against_loopback_ollama(classification_json, _call)
    assert response.classification is BusinessClassification.BUSINESS
    assert response.category == SpendingCategory.from_registry("hardware_amortizable")
    assert response.iva_category == IvaCategory("domestic_general")

    body = json_object(observed["body"])
    messages = json_array(body["messages"])
    user_message = json_object(messages[-1])
    assert user_message["images"] == [image.base64_data for image in images]
