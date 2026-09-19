"""Real-CLI regression: the printed-total mismatch reaches the operator envelope.

``evidence confirm`` DERIVES the invoice total from the taxable base and the
registry-resolved rate slot; the figure printed on the document never overwrites
it. When the two disagree the operator must be told, because the difference is
an amount the record could not represent. The worked case prints a total above
its stated base and IVA, with no document component that accounts for the gap.

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
from collections.abc import Iterator, Mapping
from http import HTTPStatus
from pathlib import Path
from typing import Any, override

import pytest

from ....adapters.persistence.storage.tests.profile_capsule_runtime import set_active_test_profile_facts
from ....application.ledger.filer_establishment import FILER_TAX_ID_FACT_PATH
from ....core.config import override_settings
from ....domain.user_profile.values import UserProfileFact
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from .ledger_ux_support import _add_evidence, _invoke, _open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

_SUPPLIER_CIF = "B12345674"
_FILER_CIF = "B17283946"

_MISMATCH_NOTICE_CODE = "ledger.evidence.confirm.printed_total_mismatch"

#: The model name the reading runtime reports on this route.
_READING_MODEL = "qwen2.5:7b"

# base 100,00 + cuota 21,00 = 121,00; the printed total agrees.
_COHERENT_INVOICE_LINES = (
    f"Proveedor: Acme Suministros SL NIF: {_SUPPLIER_CIF}",
    f"Cliente: Tester SL NIF: {_FILER_CIF}",
    "Numero de factura: 2026-0142",
    "Fecha: 10/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
    "Total factura: 121,00",
)

# This invoice prints 126,20 while its stated base plus IVA is 121,00. No
# document component explains the 5,20 difference, so confirm must retain the
# derived total and report the exact shortfall to the operator.
_UNEXPLAINED_TOTAL_INVOICE_LINES = (
    f"Proveedor: Acme Suministros SL NIF: {_SUPPLIER_CIF}",
    f"Cliente: Tester SL NIF: {_FILER_CIF}",
    "Numero de factura: 2026-0199",
    "Fecha: 11/03/2026",
    "Base imponible: 100,00",
    "IVA 21%",
    "Cuota IVA: 21,00",
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
_COHERENT_FIELDS = {
    "supplier_tax_id": _SUPPLIER_CIF,
    "supplier_tax_id_anchor": _SUPPLIER_CIF,
    "supplier_tax_id_role_evidence": "Proveedor:",
    "customer_tax_id": _FILER_CIF,
    "customer_tax_id_anchor": _FILER_CIF,
    "customer_tax_id_role_evidence": "Cliente:",
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

_UNEXPLAINED_TOTAL_FIELDS = {
    **_COHERENT_FIELDS,
    "invoice_number": "2026-0199",
    "invoice_number_anchor": "2026-0199",
    "invoice_date": "2026-03-11",
    "invoice_date_anchor": "11/03/2026",
    "grand_total": "126,20",
    "grand_total_anchor": "126,20",
}


def _loopback_handler(fields: Mapping[str, str]) -> type[SilentLoopbackHandler]:
    """Build a reading endpoint that consistently returns one test's evidence fields.

    Confirmation can issue more than one reading request, and not each prompt
    repeats the invoice number. Routing a reply by searching an individual
    prompt therefore made the fixture depend on call shape and alternate
    between the coherent and unexplained-total readings. The selected response
    remains tied to the test document, while every request in that document's
    reading session receives the same response.
    """

    class _LoopbackRequestHandler(SilentLoopbackHandler):
        """A real local endpoint speaking the reading runtime's ``/api/chat`` shape."""

        @override
        def do_POST(self) -> None:
            read_json_body(self)
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

    return _LoopbackRequestHandler


_READER_FIELDS_BY_TEST = {
    "test_an_unexplained_total_warns_that_the_printed_total_disagrees": _UNEXPLAINED_TOTAL_FIELDS,
    "test_a_coherent_invoice_emits_no_mismatch_warning": _COHERENT_FIELDS,
}


@pytest.fixture(autouse=True)
def _loopback_reader(request: pytest.FixtureRequest) -> Iterator[None]:
    """Serve a real reading endpoint on a loopback port for the duration of a test."""
    fields = _READER_FIELDS_BY_TEST[request.node.originalname or request.node.name]
    with (
        serving_loopback(_loopback_handler(fields), path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield


@pytest.fixture(autouse=True)
def _declare_filer_tax_id(_open_bucket_session: None) -> Iterator[None]:
    """Give the confirm path the profile fact needed to resolve document direction."""
    set_active_test_profile_facts((UserProfileFact(path=FILER_TAX_ID_FACT_PATH, value=_FILER_CIF),))
    yield


_CLOSURE_BLOCKER_ID = re.compile(r"([0-9a-f]+) \(closure_discrepancy\)")


def _confirm(evidence_id: str) -> dict[str, Any]:
    """Confirm, attesting past the closure-discrepancy blocker the mismatch raises.

    The arithmetic-closure gate blocks the unexplained printed total as well as
    the advisory notice this module checks. The blocker is answered with an
    attestation naming the same gap the notice reports, rather than widened
    away -- the coherent case raises no such blocker and takes the same call
    unchanged.
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
        rejected = json.loads(confirmed.output)
        context = rejected["error"].get("context") or {}
        unresolved = context.get("unresolved_blockers", "")
        blocker_id = _CLOSURE_BLOCKER_ID.search(str(unresolved))
        assert blocker_id, confirmed.output
        confirmed = _invoke(
            [
                *args,
                "--resolve",
                f"{blocker_id.group(1)}=attest:unexplained document total needs review",
            ],
        )
    assert confirmed.exit_code == 0, confirmed.output
    return json.loads(confirmed.output)


def test_an_unexplained_total_warns_that_the_printed_total_disagrees(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path, _UNEXPLAINED_TOTAL_INVOICE_LINES, filename="factura_total_sin_desglose.pdf")

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
