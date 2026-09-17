"""Loopback local-vision classifier tests for evidence classification."""

from __future__ import annotations

import base64
import json

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test

from .....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from .....application.ledger.llm_classification import ResolvedEvidence, classify_with_evidence
from .....application.ledger.llm_classification_ports import EvidenceImage, LLMClassificationPorts
from .....application.provisioning import (
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
    probe_hardware_profile,
)
from .....application.provisioning_contracts import ProvisioningPreconditionCondition
from .....core.config import Settings, load_settings, override_settings
from .....core.hardware import AcceleratorKind
from .....core.image_media_type import ImageMediaType
from .....core.model_catalogue import model_candidate
from .....domain.categories.spending_category import SpendingCategory
from .....domain.iva.schema import IvaCategory
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.llm import LLMClassificationResponse, prompt_spec_with_saturation_fields
from .....domain.transactions.tests.vision_evidence_support import vision_transaction
from .....entrypoints.cli.ledger_llm_composition import VisionReader, compose_ledger_llm
from .....tests.llm_vision_evidence_support import (
    json_array,
    json_object,
    png_image,
    run_against_loopback_ollama,
)
from ..client import LLMClient
from ..models import MultimodalImageInput
from ..vision_classifier import LocalVisionLLMClassifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "70316d3b-62cd-4735-b831-c6712f01a418"


def _llm_ports(settings: Settings) -> LLMClassificationPorts:
    """Compose the canonical reader ports against the encrypted test bucket."""
    return compose_ledger_llm(bucket_id=_BUCKET_ID, settings=settings).ports


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


def test_image_evidence_classifies_with_no_provider() -> None:
    """Image evidence routes to the vision model even with no --llm provider."""
    classification_json = json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.88,
            "reason": "scanned office-supplies invoice read on-host",
            "category": SpendingCategory.from_registry("hardware_amortizable").value,
            "iva_category": IvaCategory("domestic_general").value,
            "business_pct": None,
        },
    )
    evidence = ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(EvidenceImage.from_base64(base64.b64encode(png_image()).decode("ascii"), ImageMediaType.PNG),),
    )

    with _indexed_authority_for_test().operation() as _authority_operation_for_test:

        def _call() -> tuple[LLMClassificationResponse, str]:
            settings = load_settings()
            return classify_with_evidence(
                vision_transaction("ev-1"),
                evidence,
                text_classifier=None,
                spec=prompt_spec_with_saturation_fields(year=2025, operation=_authority_operation_for_test),
                vision_classifier=None,
                vision_model=None,
                settings=settings,
                ports=_llm_ports(settings),
            )

        _observed, (response, provenance) = run_against_loopback_ollama(classification_json, _call)
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
    # Point the local runtime at a port nothing listens on, so the refusal does
    # not depend on whether this host happens to run a model server.
    with (
        _indexed_authority_for_test().operation() as _authority_operation_for_test,
        override_settings(cadrumo_llm_ollama_chat_url="http://127.0.0.1:9/api/chat") as settings,
    ):
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            classify_with_evidence(
                vision_transaction("ev-1"),
                None,
                text_classifier=None,
                spec=prompt_spec_with_saturation_fields(year=2025, operation=_authority_operation_for_test),
                vision_classifier=None,
                vision_model=None,
                settings=settings,
                ports=_llm_ports(settings),
            )

        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
        assert verdict.evidence[0].values["runtime_reachable"] is False


def test_vision_connection_error_carries_the_runtime_precondition_verdict() -> None:
    """An unreachable on-host reader carries the canonical provisioning verdict."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        evidence = ResolvedEvidence(
            reference="ev-1",
            text=None,
            images=(EvidenceImage.from_base64(base64.b64encode(png_image()).decode("ascii"), ImageMediaType.PNG),),
        )
        unreachable_settings = load_settings().model_copy(
            update={
                "cadrumo_llm_ollama_chat_url": "http://127.0.0.1:1/api/chat",
                "cadrumo_llm_vision_read_timeout_s": 1,
            },
        )
        spec = prompt_spec_with_saturation_fields(year=2025, operation=_authority_operation_for_test)
        ports = _llm_ports(unreachable_settings)
        classifier = ports.make_vision_classifier(spec, None)
        with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
            classify_with_evidence(
                vision_transaction("ev-1"),
                evidence,
                text_classifier=None,
                spec=spec,
                vision_classifier=classifier,
                vision_model=None,
                settings=unreachable_settings,
                ports=ports,
            )

        verdict = raised.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value
        assert verdict.evidence[0].values["runtime_reachable"] is False


def test_vision_model_override_selects_the_named_model() -> None:
    """--vision-model threads through to the request model and the provenance stamp."""
    classification_json = json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.8,
            "reason": "office invoice",
            "category": SpendingCategory.from_registry("hardware_amortizable").value,
            "iva_category": IvaCategory("domestic_general").value,
        },
    )
    evidence = ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(EvidenceImage.from_base64(base64.b64encode(png_image()).decode("ascii"), ImageMediaType.PNG),),
    )

    with _indexed_authority_for_test().operation() as _authority_operation_for_test:

        def _call() -> tuple[LLMClassificationResponse, str]:
            settings = load_settings()
            spec = prompt_spec_with_saturation_fields(year=2025, operation=_authority_operation_for_test)
            classifier = LocalVisionLLMClassifier(
                spec=spec,
                model="qwen2.5vl:7b",
                client=LLMClient(
                    settings=settings,
                    hardware_profile=_admissible_measured_hardware_profile("qwen2.5vl:7b"),
                ),
                settings=settings,
            )
            return classify_with_evidence(
                vision_transaction("ev-1"),
                evidence,
                text_classifier=None,
                spec=spec,
                vision_classifier=VisionReader(classifier),
                vision_model="qwen2.5vl:7b",
                settings=settings,
                ports=_llm_ports(settings),
            )

        observed, (_response, provenance) = run_against_loopback_ollama(classification_json, _call)
    assert provenance == "llm:local-vision:qwen2.5vl:7b"
    body = json_object(observed["body"])
    assert body["model"] == "qwen2.5vl:7b"
    assert observed["runtime_requests"] == [{"method": "GET", "path": "/api/ps"}]
