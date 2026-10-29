"""Composed ledger LLM reader ports driving evidence classification through the agent path.

The ports are the composition root's own; the agent service behind the
model-run port is a recording stand-in, so the role each read asks for and the
refusal each read meets are observed rather than assumed.
"""

from __future__ import annotations

import base64
import json

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo_client.contracts.model_runs import ModelRunLane, ModelRunMediaKind, ModelRunRefusalCode

from ....adapters.outbound.llm.tests.model_run_support import TEXT_ONLY_LANE, serving_agent
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ....application.ledger.llm_classification_ports import EvidenceImage, LLMClassificationPorts
from ....application.ledger.llm_evidence import ResolvedEvidence, classify_with_evidence
from ....core.config import Settings, load_settings
from ....core.errors.error_codes import build_error_envelope
from ....core.image_media_type import ImageMediaType
from ....core.model_roles import ModelRole
from ....domain.categories.spending_category import SpendingCategory
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification
from ....domain.transactions.llm import prompt_spec_with_saturation_fields
from ....domain.transactions.tests.vision_evidence_support import vision_transaction
from ....tests.llm_vision_evidence_support import png_image
from ...ledger_llm_composition import compose_ledger_llm

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "70316d3b-62cd-4735-b831-c6712f01a418"

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)

_VISION_LANE = ModelRunLane(
    provider_id="nearby",
    transport="api",
    model="synthetic-vision:1",
    reads_off_host=False,
    accepted_media=(ModelRunMediaKind.IMAGE,),
)


def _llm_ports(settings: Settings) -> LLMClassificationPorts:
    return compose_ledger_llm(bucket_id=_BUCKET_ID, settings=settings).ports


def _image_evidence() -> ResolvedEvidence:
    return ResolvedEvidence(
        reference="ev-1",
        text=None,
        images=(EvidenceImage.from_base64(base64.b64encode(png_image()).decode("ascii"), ImageMediaType.PNG),),
    )


def _classification_json() -> str:
    return json.dumps(
        {
            "classification": "BUSINESS",
            "confidence": 0.88,
            "reason": "scanned office-supplies invoice",
            "category": SpendingCategory.from_registry("hardware_amortizable").value,
            "iva_category": IvaCategory("domestic_general").value,
            "business_pct": None,
        },
    )


def _classify(evidence: ResolvedEvidence):
    settings = load_settings()
    with _indexed_authority_for_test().operation() as operation:
        return classify_with_evidence(
            vision_transaction("ev-1"),
            evidence,
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(year=2025, operation=operation),
            vision_classifier=None,
            settings=settings,
            ports=_llm_ports(settings),
        )


def test_image_evidence_classifies_through_the_vision_role() -> None:
    images = _image_evidence()
    with serving_agent(replies=(_classification_json(),), lane=_VISION_LANE) as service:
        response, provenance = _classify(images)

    assert response.classification is BusinessClassification.BUSINESS
    assert provenance == "llm:agent-vision:nearby/api/synthetic-vision:1"
    assert service.lookups == [ModelRole.VISION_TRANSCRIPTION]
    ((_header, body),) = service.runs
    assert [item.base64_data for item in body.attachments] == [image.base64_data for image in images.images]


@pytest.mark.parametrize(
    "code",
    [ModelRunRefusalCode.NO_SELECTION, ModelRunRefusalCode.MODEL_NOT_INSTALLED, ModelRunRefusalCode.LANE_UNAVAILABLE],
)
def test_a_refused_vision_lookup_is_a_typed_reader_refusal_with_no_run(code: ModelRunRefusalCode) -> None:
    with serving_agent(lookup_refusal=code) as service, pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised:
        _classify(_image_evidence())

    assert build_error_envelope(raised.value).code == "REFUSED_LEDGER_EVIDENCE_READER"
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.evidence[0].values["model_run_refusal"] == code.value
    assert verdict.evidence[0].values["model_role"] == ModelRole.VISION_TRANSCRIPTION.value
    assert service.runs == []


def test_a_vision_lane_that_takes_no_images_refuses_input_not_supported() -> None:
    with (
        serving_agent(lane=TEXT_ONLY_LANE) as service,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _classify(_image_evidence())

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.evidence[0].values["model_run_refusal"] == "input_not_supported"
    assert service.runs == []


def test_a_text_read_with_no_selection_refuses_for_the_text_role_with_no_run() -> None:
    """The text reader no longer probes a local runtime first; the service's refusal is the verdict."""
    with (
        serving_agent(lookup_refusal=ModelRunRefusalCode.NO_SELECTION) as service,
        pytest.raises(PurchaseInvoiceEvidenceReaderError) as raised,
    ):
        _classify(ResolvedEvidence(reference="ev-1", text="FACTURA 7 Total 12,10", images=()))

    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.evidence[0].values["model_run_refusal"] == "no_selection"
    assert verdict.evidence[0].values["model_role"] == ModelRole.TEXT_EXTRACTION.value
    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert service.runs == []
