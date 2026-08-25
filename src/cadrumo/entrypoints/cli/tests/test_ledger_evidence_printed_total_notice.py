"""Real-CLI regression: the printed-total mismatch reaches the operator envelope.

``evidence confirm`` DERIVES the invoice total from the taxable base and the
registry-resolved rate slot; the figure printed on the document never overwrites
it. When the two disagree the operator must be told, because the difference is
an amount the record could not represent -- a recargo de equivalencia (LIVA
art. 161) is the worked case, and before this notice the surcharge simply
vanished behind a valid-looking invoice.

The diagnostic travels on the typed ``notices`` channel of the shared envelope
spine (``aeat-cli-contract``), never as a bespoke
field inside ``result``.

Drives the real Typer CLI tree, a real encrypted bucket session, and a real
reportlab-generated text-bearing PDF. No mocks.

See Also:
    :class:`~application.ledger.evidence_draft.PrintedTotalDiscrepancy`
        The record the notice is projected from.
    :func:`~entrypoints.cli._ledger_evidence_cli._run_evidence_confirm`
        CLI runner that emits the notice.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Any, override

import pytest

from ....core.config import override_settings
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ._ledger_ux_support import _add_evidence, _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

_SUPPLIER_CIF = "B12345674"

_MISMATCH_NOTICE_CODE = "ledger.evidence.confirm.printed_total_mismatch"

#: The model name the reading runtime reports on this route.
_READING_MODEL = "qwen2.5:7b"

# base 100,00 + cuota 21,00 = 121,00; the printed total agrees.
_COHERENT_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

# A recargo de equivalencia invoice: the document totals 126,20 while
# base + cuota is 121,00.
_RECARGO_INVOICE_LINES = (
    "Factura de Acme Suministros SL",
    f"NIF: {_SUPPLIER_CIF}",
    "Numero de factura: 2026-0199",
    "Fecha: 11/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Recargo de equivalencia 5,2%: 5,20",
    "Total factura: 126,20",
)


# ---------------------------------------------------------------------------
# A real loopback reader, so the confirm path can run with no model present
# ---------------------------------------------------------------------------
#
# Wiring the semantic reader made every text-PDF confirm depend on a reading
# model, so these two cases stopped at `httpx.ConnectError` before any notice
# was built. The endpoint below is real HTTP on a loopback port speaking the
# runtime's own wire shape; only the REPLY is authored here, and everything
# downstream of the socket is production code. No model is loaded and no
# inference runs.
#
# The reply is keyed off the transcription the reader receives, so each document
# is answered with its OWN printed figures rather than one canned payload --
# otherwise the coherent and recargo cases would be indistinguishable to the
# stub and the mismatch assertion would be testing the fixture.


class _LoopbackRequestHandler(SilentLoopbackHandler):
    """A real local endpoint speaking the reading runtime's ``/api/chat`` shape."""

    @override
    def do_POST(self) -> None:
        prompt = json.dumps(read_json_body(self)["messages"])
        fields = _RECARGO_FIELDS if "2026-0199" in prompt else _COHERENT_FIELDS
        write_json_response(
            self,
            ollama_chat_reply(
                json.dumps(fields),
                model=_READING_MODEL,
                prompt_eval_count=100,
                eval_count=50,
            ),
            status=HTTPStatus.OK,
        )


_COHERENT_FIELDS = {
    "supplier_tax_id": _SUPPLIER_CIF,
    "supplier_tax_id_anchor": _SUPPLIER_CIF,
    "supplier_tax_id_role_evidence": "Factura de Acme Suministros SL",
    "invoice_number": "2026-0142",
    "invoice_number_anchor": "2026-0142",
    "invoice_date": "2026-03-10",
    "invoice_date_anchor": "10/03/2026",
    "taxable_base": "100,00",
    "taxable_base_anchor": "100,00",
    "iva_rate": "21",
    "iva_rate_anchor": "21%",
    "iva_amount": "21,00",
    "iva_amount_anchor": "21,00",
    "grand_total": "121,00",
    "grand_total_anchor": "121,00",
}

_RECARGO_FIELDS = {
    **_COHERENT_FIELDS,
    "invoice_number": "2026-0199",
    "invoice_number_anchor": "2026-0199",
    "invoice_date": "2026-03-11",
    "invoice_date_anchor": "11/03/2026",
    "grand_total": "126,20",
    "grand_total_anchor": "126,20",
}


@pytest.fixture(autouse=True)
def _loopback_reader() -> Iterator[None]:
    """Serve a real reading endpoint on a loopback port for the duration of a test."""
    with (
        serving_loopback(_LoopbackRequestHandler, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield


_UNRESOLVED_BLOCKER_ID = re.compile(r"Unresolved: ([0-9a-f]+) \(closure_discrepancy\)")


def _confirm(evidence_id: str) -> dict[str, Any]:
    """Confirm, attesting past the closure-discrepancy blocker the recargo case raises.

    The printed-total mismatch this module tests is exactly the amount the
    text-extraction contract cannot represent (recargo de equivalencia has no
    field there), so the arithmetic-closure gate now blocks confirm on it as
    well as the advisory notice this module was written to check. The blocker
    is answered with an attestation naming the same gap the notice reports,
    rather than widened away -- the coherent case raises no such blocker and
    takes the same call unchanged.
    """
    args = [
        "--format", "json", "app", "ledger", "evidence", "confirm",
        "--country-code", "ES",
        "--evidence-id", evidence_id,
        "--kind", "received",
        "--counterparty-name", "Acme Suministros SL",
    ]  # fmt: skip
    confirmed = _invoke(args)
    if confirmed.exit_code != 0:
        blocker_id = _UNRESOLVED_BLOCKER_ID.search(confirmed.output)
        assert blocker_id, confirmed.output
        confirmed = _invoke(
            [
                *args,
                "--resolve",
                f"{blocker_id.group(1)}=attest:recargo de equivalencia is not a text-extraction field",
            ],
        )
    assert confirmed.exit_code == 0, confirmed.output
    return json.loads(confirmed.output)


def test_a_recargo_invoice_warns_that_the_printed_total_disagrees(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path, _RECARGO_INVOICE_LINES, filename="factura_recargo.pdf")

    envelope = _confirm(evidence_id)

    # The derived total is what was recorded; the printed figure did not overwrite it.
    assert envelope["result"]["grand_total"] == "121.00"

    notices = {notice["code"]: notice for notice in envelope.get("notices", [])}
    assert _MISMATCH_NOTICE_CODE in notices, f"expected the mismatch warning, got {sorted(notices)}"
    notice = notices[_MISMATCH_NOTICE_CODE]
    assert notice["severity"] == "warning"
    # The operator is given both figures and the gap, so they can find the 5,20
    # on the document rather than being told only that something is wrong.
    assert notice["context"]["printed_total"] == "126.20"
    assert notice["context"]["recorded_total"] == "121.00"
    assert notice["context"]["difference"] == "5.20"


def test_a_coherent_invoice_emits_no_mismatch_warning(tmp_path: Path) -> None:
    """The negative control: an advisory that fires on a clean document is noise."""
    evidence_id = _add_evidence(tmp_path, _COHERENT_INVOICE_LINES, filename="factura.pdf")

    envelope = _confirm(evidence_id)

    notice_codes = {notice["code"] for notice in envelope.get("notices", [])}
    assert _MISMATCH_NOTICE_CODE not in notice_codes
