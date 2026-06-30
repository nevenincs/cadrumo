"""Real-behaviour tests for the on-host vision evidence read path.

A scan-only PDF or an image is read in memory by a LOCAL vision model: the
evidence resolves to base64 images (never inlined text), routes to the
:class:`LocalVisionLLMClassifier`, and is sent to a loopback Ollama endpoint --
no cloud consent, gestor-allowed, nothing written to disk, no byte leaving the
host. The classifier is driven against a real local HTTP server (no mocks) and
its response is parsed through the same allow-list the subprocess path uses.
"""

from __future__ import annotations

import base64
import json
import threading
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from queue import Queue
from typing import ClassVar, override

import pytest
from PIL import Image

from ....core.config import Settings, load_settings, override_settings
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.categories import SpendingCategory
from ....domain.iva import IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    LLMClassificationResponse,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
    TransactionValidationError,
    prompt_spec_with_saturation_fields,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceService
from .._llm_classification import _classify_with_evidence, _resolve_evidence, _ResolvedEvidence
from .._vision_classifier import LocalVisionLLMClassifier

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


def _json_object(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    result: dict[str, object] = {}
    for key, item in value.items():
        assert isinstance(key, str)
        result[key] = item
    return result


def _json_array(value: object) -> list[object]:
    assert isinstance(value, list)
    return list(value)


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        yield runtime


def _scan_only_pdf() -> bytes:
    """A one-page raster (text-layer-free) PDF -- the scan-only case."""
    buffer = BytesIO()
    Image.new("RGB", (260, 160), "white").save(buffer, format="PDF")
    return buffer.getvalue()


def _png_image() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (120, 80), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _transaction(evidence_id: str) -> Transaction:
    raw = RawTransaction(
        transaction_id="row-vision",
        booked_date=date(2025, 5, 1),
        value_date=date(2025, 5, 1),
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Acme SL",
        description="office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": "office supplies"},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": TransactionDirection.OUTGOING, "purchase_invoice_evidence_id": evidence_id},
    )


def _add_evidence(profile: TestRuntimeProfile, tmp_path: Path, *, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    service = PurchaseInvoiceEvidenceService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    return service.add(bucket_id=_BUCKET_ID, source_path=path).record.evidence_id


def test_scan_only_pdf_resolves_to_images_gestor_allowed_no_consent(
    profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    """A scan-only PDF resolves to base64 PNG images on-host, even for a gestor."""
    evidence_id = _add_evidence(profile, tmp_path, name="scan.pdf", data=_scan_only_pdf())
    # Gestor mode ON and cloud upload NOT permitted: the on-host vision path must
    # still resolve (no cloud consent needed) -- this is the gestor read path.
    gestor: Settings = profile.settings.model_copy(
        update={"aeat_evidence_gestor_mode": True, "aeat_evidence_cloud_upload_permitted": False},
    )
    resolved = _resolve_evidence(
        _transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=gestor,
        evidence_acknowledged=False,
    )
    assert resolved is not None
    assert resolved.text is None
    assert resolved.is_images
    assert base64.b64decode(resolved.images[0])[:8] == b"\x89PNG\r\n\x1a\n"
    assert resolved.reference == evidence_id


def test_image_evidence_resolves_to_images(profile: TestRuntimeProfile, tmp_path: Path) -> None:
    """An image invoice resolves to its base64 bytes for the on-host vision read."""
    evidence_id = _add_evidence(profile, tmp_path, name="receipt.png", data=_png_image())
    resolved = _resolve_evidence(
        _transaction(evidence_id),
        bucket_id=_BUCKET_ID,
        settings=profile.settings,
        evidence_acknowledged=False,
    )
    assert resolved is not None
    assert resolved.text is None
    assert resolved.images == (base64.b64encode(_png_image()).decode("ascii"),)


@pytest.mark.parametrize(
    ("name", "data_factory"),
    [("scan.pdf", _scan_only_pdf), ("receipt.png", _png_image)],
    ids=["scan-pdf", "image"],
)
def test_llm_vision_off_refuses_both_on_host_read_modes(
    profile: TestRuntimeProfile,
    tmp_path: Path,
    name: str,
    data_factory: Callable[[], bytes],
) -> None:
    """An ``llm_vision=off`` profile refuses BOTH on-host read modes (honesty review M1).

    The capability gate sits past the text-layer early return, so it must cover
    every on-host read mode: a scan-only PDF (rasterise path) and an image
    attachment (direct-bytes path). Both reach the gate and must refuse with an
    instructive, non-silent error naming the opt-in command.
    """
    from ....domain.user_profile import UserProfileFact, UserProfileRecord
    from ...user_profile import UserProfileLifecycleRepository

    clock = datetime(2026, 1, 1, tzinfo=UTC)
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(
        UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="Vision opted out",
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="capabilities.llm_vision", value=False),
            ),
            created_at=clock,
            updated_at=clock,
        ),
    )

    evidence_id = _add_evidence(profile, tmp_path, name=name, data=data_factory())
    with pytest.raises(PurchaseInvoiceEvidenceInputError) as raised:
        _resolve_evidence(
            _transaction(evidence_id),
            bucket_id=_BUCKET_ID,
            settings=profile.settings,
            evidence_acknowledged=False,
        )
    assert "vision" in str(raised.value).lower()
    assert "llm_vision on" in (raised.value.suggestion or "")


class _ObservedOllamaRequest(BaseHTTPRequestHandler):
    """Loopback Ollama endpoint that captures the chat body and returns a classification."""

    events: ClassVar[Queue[dict[str, object]]]
    content: ClassVar[str]

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.events.put({"body": json.loads(body.decode("utf-8"))})
        payload = {
            "model": "llava-test",
            "message": {"content": self.content},
            "prompt_eval_count": 9,
            "eval_count": 5,
        }
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Silence stdlib request logging during tests."""


def _run_against_loopback_ollama[T](content: str, call: Callable[[], T]) -> tuple[dict[str, object], T]:
    """Stand up a loopback Ollama returning ``content`` and run ``call()`` against it.

    Returns ``(observed_request_body, call_result)``.
    """
    events: Queue[dict[str, object]] = Queue()
    _ObservedOllamaRequest.events = events
    _ObservedOllamaRequest.content = content
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ObservedOllamaRequest)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/api/chat"
    try:
        with override_settings(aeat_llm_ollama_chat_url=endpoint):
            result = call()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    return events.get_nowait(), result


def test_vision_classifier_classifies_from_images(profile: TestRuntimeProfile) -> None:
    """The vision classifier sends the images to the local model and parses the result."""
    _ = profile  # active bucket session backs the LLM cache
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
    """The UX fix: image evidence routes to the vision model even with no --llm provider."""
    _ = profile  # active bucket session backs the LLM cache
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
            text_classifier=None,  # no --llm provider resolved
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
            None,  # no linked evidence -> text path -> needs a provider
            text_classifier=None,
            spec=prompt_spec_with_saturation_fields(),
            vision_classifier=None,
            vision_model=None,
            settings=load_settings(),
        )


def test_vision_connection_error_becomes_a_typed_refusal_with_fix(profile: TestRuntimeProfile) -> None:
    """A down/unreachable Ollama is converted to LLMClassifierError, not a raw traceback."""
    from ....domain.transactions import LLMClassifierError

    _ = profile  # active bucket session backs the LLM cache before the connection attempt
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
    _ = profile  # active bucket session backs the LLM cache
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
