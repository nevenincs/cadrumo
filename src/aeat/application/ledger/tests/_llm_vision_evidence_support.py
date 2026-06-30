"""Shared support for local-vision evidence tests."""

from __future__ import annotations

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

from ....core.config import override_settings
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionDirection,
)
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence import PurchaseInvoiceEvidenceService

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
    """A one-page raster, text-layer-free PDF."""
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
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "purchase_invoice_evidence_id": evidence_id,
        },
    )


def _add_evidence(profile: TestRuntimeProfile, tmp_path: Path, *, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    service = PurchaseInvoiceEvidenceService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    return service.add(bucket_id=_BUCKET_ID, source_path=path).record.evidence_id


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
    """Stand up a loopback Ollama returning ``content`` and run ``call()`` against it."""
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
