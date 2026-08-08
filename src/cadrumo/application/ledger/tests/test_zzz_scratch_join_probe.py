"""Probe: does the profile filer-id reach the derivation on the LIVE entry point?

Drives `extract_invoice_draft_from_evidence` -- the real public entry -- against a
real encrypted bucket carrying a real profile with a declared tax id, a real
reportlab PDF, a real text-layer transcription, and a real HTTP reader endpoint
on loopback. Nothing in cadrumo is substituted; only the model's REPLY is
authored, exactly as a runtime would return it.

Observes `suggested_kind` on the draft that comes out.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from queue import Queue
from typing import ClassVar

import pytest

from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine
from cadrumo.application.ledger import extract_invoice_draft_from_evidence
from cadrumo.application.user_profile import profile_create_storage_span, set_active_fields
from cadrumo.application.workflow import workflow_state_repository
from cadrumo.core.config import load_settings, override_settings
from cadrumo.domain.user_profile import UserProfileFact
from cadrumo.tests.cli_runner import invoke_cached_cli
from cadrumo.tests.secure_sql import isolated_profile_storage_root
from cadrumo.tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


_PROFILE_ID = "9e0f3a2b-5d1c-4a77-9b2d-27ed6d6c7f10"
_FILER_CIF = "B17283946"
_SUPPLIER_CIF = "B12345674"

_LINES = (
    "FACTURA 2026-0142",
    f"Proveedor: Acme Suministros SL  NIF: {_SUPPLIER_CIF}",
    f"Cliente: Tester SL  NIF: {_FILER_CIF}",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

_REPLY = {
    "supplier_tax_id": _SUPPLIER_CIF,
    "supplier_tax_id_anchor": _SUPPLIER_CIF,
    "supplier_tax_id_role_evidence": "Proveedor:",
    "customer_tax_id": _FILER_CIF,
    "customer_tax_id_anchor": _FILER_CIF,
    "customer_tax_id_role_evidence": "Cliente:",
    "invoice_number": "2026-0142",
    "invoice_number_anchor": "2026-0142",
    "invoice_date": "2026-03-10",
    "invoice_date_anchor": "2026-0142",
    "taxable_base": "100,00",
    "taxable_base_anchor": "100,00",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "21,00",
    "iva_amount_anchor": "21,00",
    "grand_total": "121,00",
    "grand_total_anchor": "121,00",
    "currency": "EUR",
}


class _ReaderStub(BaseHTTPRequestHandler):
    reply: ClassVar[str] = ""
    requests: ClassVar[Queue] = Queue()

    def do_POST(self) -> None:  # noqa: N802
        body = self.rfile.read(int(self.headers.get("content-length", "0")))
        self.requests.put(json.loads(body.decode("utf-8")))
        payload = json.dumps(
            {
                "model": "qwen2.5:7b",
                "message": {"role": "assistant", "content": self.reply},
                "prompt_eval_count": 100,
                "eval_count": 50,
            },
        ).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass


def _pdf(lines: tuple[str, ...]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buf = BytesIO()
    page = canvas.Canvas(buf, pagesize=A4)
    y = 760
    for line in lines:
        page.drawString(72, y, line)
        y -= 20
    page.save()
    return buf.getvalue()


@pytest.fixture
def reader() -> Iterator[str]:
    _ReaderStub.reply = json.dumps(_REPLY)
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ReaderStub)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/chat"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


_SHAPES = {
    "A_counterparty_checksum_fails": (
        ("FACTURA 2026-0142", "Proveedor: Acme SL  NIF: B1234567X", "Cliente: Tester SL  NIF: B17283946",
         "Base imponible: 100,00", "IVA 21%", "Cuota IVA: 21,00", "Total factura: 121,00"),
        {"supplier_tax_id": "B1234567X", "supplier_tax_id_anchor": "B1234567X",
         "supplier_tax_id_role_evidence": "Proveedor:",
         "customer_tax_id": "B17283946", "customer_tax_id_anchor": "B17283946",
         "customer_tax_id_role_evidence": "Cliente:"},
    ),
    "B_only_filer_id_simplificada": (
        ("TICKET 2026-0142", "Emisor: Acme SL", "Cliente: Tester SL  NIF: B17283946",
         "Base imponible: 100,00", "IVA 21%", "Cuota IVA: 21,00", "Total factura: 121,00"),
        {"customer_tax_id": "B17283946", "customer_tax_id_anchor": "B17283946",
         "customer_tax_id_role_evidence": "Cliente:"},
    ),
    "C_no_identifier_at_all": (
        ("TICKET 2026-0142", "Cafe Oscar", "Base imponible: 100,00", "IVA 21%",
         "Cuota IVA: 21,00", "Total factura: 121,00"),
        {},
    ),
    "D_only_counterparty_id": (
        ("FACTURA 2026-0142", "Proveedor: Acme SL  NIF: B12345674", "Cliente: Tester SL",
         "Base imponible: 100,00", "IVA 21%", "Cuota IVA: 21,00", "Total factura: 121,00"),
        {"supplier_tax_id": "B12345674", "supplier_tax_id_anchor": "B12345674",
         "supplier_tax_id_role_evidence": "Proveedor:"},
    ),
}

_COMMON = {
    "invoice_number": "2026-0142", "invoice_number_anchor": "2026-0142",
    "invoice_date": "2026-03-10",
    "taxable_base": "100,00", "taxable_base_anchor": "100,00",
    "iva_rate": "21", "iva_rate_anchor": "21%",
    "iva_amount": "21,00", "iva_amount_anchor": "21,00",
    "grand_total": "121,00", "grand_total_anchor": "121,00",
    "currency": "EUR",
}


@pytest.mark.parametrize("shape", sorted(_SHAPES))
def test_shape_measurement(tmp_path: Path, reader: str, shape: str) -> None:
    lines, fields = _SHAPES[shape]
    _ReaderStub.reply = json.dumps({**_COMMON, **fields})
    dispose_engine()
    with (
        override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_output_language="en",
            cadrumo_llm_ollama_chat_url=reader,
        ),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID, display_name="tester"),
        )
        workflow_state_repository().update(
            lambda state: set_active_fields(state, (UserProfileFact(path="identity.tax_id", value=_FILER_CIF),)),
        )
        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_pdf(lines))
        added = invoke_cached_cli(
            ["--format", "json", "app", "ledger", "evidence", "add", str(pdf_path), "--supplier", "Acme SL"],
        )
        assert added.exit_code == 0, added.output
        evidence_id = json.loads(added.output)["result"]["evidence_id"]
        draft = extract_invoice_draft_from_evidence(
            evidence_id=evidence_id, bucket_id=_PROFILE_ID, settings=load_settings(),
        )
    from cadrumo.application.ledger import confirmation_blockers

    print(f"
### {shape}")
    print("  suggested_kind:", draft.suggested_kind)
    print("  findings:", sorted({f.kind.value for f in draft.discrepancies}))
    print("  blockers:", [(b.reason.value, b.field) for b in confirmation_blockers(draft)])
    dispose_engine()


def test_the_join_carries_the_filer_id_to_the_derivation(tmp_path: Path, reader: str) -> None:
    dispose_engine()
    with (
        override_settings(
            cadrumo_local_storage_root=tmp_path,
            cadrumo_output_language="en",
            cadrumo_llm_ollama_chat_url=reader,
        ),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        workflow_state_repository().update(
            lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID, display_name="tester"),
        )
        workflow_state_repository().update(
            lambda state: set_active_fields(state, (UserProfileFact(path="identity.tax_id", value=_FILER_CIF),)),
        )

        from cadrumo.application.ledger import _evidence_draft as router

        print("FILER RESOLVED FROM PROFILE:", router._active_filer_tax_id())

        pdf_path = tmp_path / "factura.pdf"
        pdf_path.write_bytes(_pdf(_LINES))
        added = invoke_cached_cli(
            ["--format", "json", "app", "ledger", "evidence", "add", str(pdf_path), "--supplier", "Acme SL"],
        )
        assert added.exit_code == 0, added.output
        evidence_id = json.loads(added.output)["result"]["evidence_id"]

        draft = extract_invoice_draft_from_evidence(evidence_id=evidence_id, bucket_id=_PROFILE_ID, settings=load_settings())

    print("SUGGESTED KIND:", draft.suggested_kind)
    print("SUPPLIER:", draft.supplier_tax_id, "CUSTOMER:", draft.customer_tax_id)
    for env in draft.provenance:
        if env.field in {"suggested_kind", "supplier_tax_id", "customer_tax_id"}:
            print("  ENV", env.field, env.grounding, repr(env.note))
    for finding in draft.discrepancies:
        print("  FINDING", finding.kind, finding.field, finding.detail[:90])
    dispose_engine()
