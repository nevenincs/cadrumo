"""Loopback local-vision classifier tests for evidence classification."""

from __future__ import annotations

import base64
import json

import pytest

from ...application.ledger import PurchaseInvoiceEvidenceInputError
from ...application.ledger._llm_classification import _classify_with_evidence, _ResolvedEvidence
from ...application.provisioning import (
    AcceleratorReading,
    HardwareProfile,
    ProvisioningPreconditionCondition,
    SystemMemoryReading,
    probe_hardware_profile,
)
from ...core import AcceleratorKind, ImageMediaType, model_candidate
from ...core.config import load_settings
from ...domain.categories import SpendingCategory
from ...domain.iva import IvaCategory
from ...domain.transactions import (
    BusinessClassification,
    LLMClassificationResponse,
    prompt_spec_with_saturation_fields,
)
from ...tests.llm_vision_evidence_support import (
    _json_array,
    _json_object,
    _png_image,
    _run_against_loopback_ollama,
    _transaction,
)
from ...tests.llm_vision_evidence_support import (
    profile as profile,
)
from ...tests.secure_sql import TestRuntimeProfile
from .. import LLMClient
from .._models import MultimodalImageInput
from .._vision_classifier import LocalVisionLLMClassifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

__all__ = ["profile"]


def _admissible_measured_hardware_profile(model: str) -> HardwareProfile:
    """Build an injected measurement that admits this catalogued model.

    The production contention authority still reads the runtime's resident set
    and makes the admission decision.  This only keeps the test independent of
    the host GPU's transient state, as the hardware-contract suite does.
    """
    candidate = model_candidate(model)
    assert candidate is not None
    assert candidate.memory_requirement_bytes is not None
    required = candidate.memory_requirement_bytes + load_settings().cadrumo_llm_contention_safety_margin_bytes
    return probe_hardware_profile(
        memory=SystemMemoryReading(total_bytes=required, free_bytes=required),
        accelerator=AcceleratorReading(kind=AcceleratorKind.NONE),
    )


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
    refusal that survives is about the runtime being unreachable, represented
    by the canonical provisioning verdict rather than transport-specific prose.
    """
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _classify_with_evidence(
            _transaction("ev-1"),
            None,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=None,
            vision_model=None,
            settings=load_settings(),
        )

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
    assert verdict.evidence[0].values["runtime_reachable"] is False


def test_vision_connection_error_carries_the_runtime_precondition_verdict(profile: TestRuntimeProfile) -> None:
    """An unreachable on-host reader carries the canonical provisioning verdict."""
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
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _classify_with_evidence(
            _transaction("ev-1"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=classifier,
            vision_model=None,
            settings=unreachable_settings,
        )

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
    assert verdict.evidence[0].values["runtime_reachable"] is False


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
        settings = load_settings()
        classifier = LocalVisionLLMClassifier(
            spec=prompt_spec_with_saturation_fields(),
            model="qwen2.5vl:7b",
            client=LLMClient(
                settings=settings,
                hardware_profile=_admissible_measured_hardware_profile("qwen2.5vl:7b"),
            ),
            settings=settings,
        )
        return _classify_with_evidence(
            _transaction("ev-1"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=classifier,
            vision_model="qwen2.5vl:7b",
            settings=settings,
        )

    observed, (_response, provenance) = _run_against_loopback_ollama(classification_json, _call)
    assert provenance == "llm:local-vision:qwen2.5vl:7b"
    body = _json_object(observed["body"])
    assert body["model"] == "qwen2.5vl:7b"
    assert observed["runtime_requests"] == [{"method": "GET", "path": "/api/ps"}]
