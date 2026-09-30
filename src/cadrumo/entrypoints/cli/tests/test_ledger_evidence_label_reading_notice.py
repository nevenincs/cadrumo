"""Real-CLI regression: a label reading that stands without its model fill says why.

A text-layer invoice whose labels leave a required field unread asks the on-host
text model to fill it. That fill is optional: when it cannot run, the label
reading stands and the unread field stays empty. Two conditions stop it, and
both must reach the operator on the envelope's ``notices`` channel, because a
draft with an empty field otherwise looks exactly like a document that does not
print it:

- the model runtime cannot be reached;
- admission control refuses to load the model because this machine shows no
  measured memory headroom for it. The refusal is respected: the model is never
  loaded, and nothing is sent to the runtime.

When the labels read nothing the model read is the whole read rather than a
fill, and admission control's refusal stands unchanged.

Drives the real Typer CLI tree, a real encrypted bucket session, a real
reportlab-generated text-bearing PDF, the real composed reader and the real
admission check. The runtime is a real HTTP endpoint on a loopback port that
records every request reaching it; only its reply is authored here.
"""

from __future__ import annotations

import json
import re
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import Any, override

import pytest
from click.testing import Result

from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.config import load_settings, override_settings
from ....core.model_catalogue import model_candidate
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from .ledger_ux_support import _add_evidence, _invoke, _open_bucket_session, admit_an_unmeasurable_host

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session", "admit_an_unmeasurable_host"]

_HEADROOM_REFUSED = "ledger.evidence.label_reading.headroom_refused"
_READER_UNAVAILABLE = "ledger.evidence.label_reading.reader_unavailable"
_LABEL_READING_CODES = {_HEADROOM_REFUSED, _READER_UNAVAILABLE}

#: The preconditions a headroom refusal can fail on this host: the free memory
#: could not be measured, or it was measured short of the requirement plus the
#: margin with the runtime's resident set readable or not.
_HEADROOM_CONDITIONS = {
    ProvisioningPreconditionCondition.LOAD_HEADROOM_MEASURABLE.value,
    ProvisioningPreconditionCondition.LOAD_CAPACITY_AVAILABLE.value,
    ProvisioningPreconditionCondition.RESIDENT_SET_READABLE.value,
}

_SUPPLIER_NAME = "Estacion de Servicio Albufera SL"
_SUPPLIER_TAX_ID = "B92000082"
_DIRECTION_BLOCKER_ID = re.compile(r"([0-9a-f]+) \(unresolved_direction\)")

# The labels read every required field here except the issuer's letterhead name,
# which no label assigns, so the text model is asked for exactly that one field.
_PARTIALLY_LABELLED_LINES = (
    _SUPPLIER_NAME,
    f"NIF: {_SUPPLIER_TAX_ID}",
    "FACTURA SIMPLIFICADA",
    "Numero: T-0042-2026",
    "Fecha: 14.02.2026",
    "Base imponible 60,00",
    "IVA 21% 12,60",
    "Total (IVA incluido) 72,60 EUR",
)

# Nothing here is a label the rules read, so there is no reading to stand on.
_UNLABELLED_LINES = ("B1234567X B17283946 766,30",)

#: A model the catalogue makes no memory claim about. Admission control does
#: not assess such a model, so the cases whose subject is NOT admission run the
#: same way on every host whatever its free memory.
_UNASSESSED_MODEL = "cadrumo-test-unassessed-reader:1b"

#: A margin no machine can satisfy, so the real admission check refuses on every
#: host: a measurable one falls short, an unmeasurable one fails closed.
_UNSATISFIABLE_MARGIN_BYTES = 1 << 60


@contextmanager
def _recording_runtime() -> Iterator[tuple[str, list[str]]]:
    """Serve a runtime that answers the fill and records every request that reaches it."""
    arrivals: list[str] = []

    class _Runtime(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            read_json_body(self)
            arrivals.append(self.path)
            reply = {"supplier_name": _SUPPLIER_NAME, "supplier_name_anchor": _SUPPLIER_NAME}
            write_json_response(
                self,
                ollama_chat_reply(json.dumps(reply), model=_UNASSESSED_MODEL, prompt_eval_count=100, eval_count=20),
                status=HTTPStatus.OK,
            )

    with serving_loopback(_Runtime, path="/api/chat") as chat_url:
        yield chat_url, arrivals


@contextmanager
def _unreachable_runtime_url() -> Iterator[str]:
    """Reserve a loopback port that nothing listens on, so a connection is refused."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reserved:
        reserved.bind(("127.0.0.1", 0))
        yield f"http://127.0.0.1:{reserved.getsockname()[1]}/api/chat"


def _extract(evidence_id: str) -> tuple[int, dict[str, Any]]:
    extracted = _invoke(["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id])
    return extracted.exit_code, json.loads(extracted.output)


def _label_reading_notices(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    return [notice for notice in envelope.get("notices", []) if notice["code"] in _LABEL_READING_CODES]


def test_the_refused_model_is_one_the_admission_check_assesses() -> None:
    """Anchor the detector: a model with no declared requirement is never refused, so the case would be vacuous."""
    candidate = model_candidate(load_settings().cadrumo_llm_ollama_text_model)

    assert candidate is not None
    assert candidate.memory_requirement_bytes is not None


def test_a_headroom_refused_fill_leaves_the_label_reading_standing_and_never_touches_the_runtime(
    tmp_path: Path,
) -> None:
    evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")

    with (
        _recording_runtime() as (chat_url, arrivals),
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_contention_check_override=False,
            cadrumo_llm_contention_safety_margin_bytes=_UNSATISFIABLE_MARGIN_BYTES,
        ),
    ):
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    # Admission control, not a failed read: no request reached the runtime, so
    # no model was loaded to be refused afterwards.
    assert arrivals == []
    result = envelope["result"]
    assert result["supplier_name"] is None
    assert result["invoice_number"] == "T-0042-2026"
    assert result["grand_total"] == "72.60"
    (notice,) = _label_reading_notices(envelope)
    assert notice["code"] == _HEADROOM_REFUSED
    assert notice["severity"] == "warning"
    assert envelope["status"] == "warning"
    assert notice["context"]["reason"] == "load_headroom_refused"
    assert notice["context"]["unread_fields"] == "supplier_name"
    assert notice["context"]["reader_error_type"] == "LLMContentionError"
    assert notice["context"]["failed_condition_id"] in _HEADROOM_CONDITIONS


def _confirm_supplying_the_unassigned_identifier(evidence_id: str) -> Result:
    """Confirm, answering the one blocker a ticket with no party labels raises.

    Nothing on the ticket assigns its only identifier to a party, so confirm
    asks the operator to state the counterparty's identifier. It is supplied
    rather than widened away; the label-reading notice under test is unrelated
    to that blocker and is emitted on the confirmation that succeeds.
    """
    args = [
        "--format", "json", "app", "ledger", "evidence", "confirm",
        "--country-code", "ES",
        "--evidence-id", evidence_id,
        "--kind", "received",
        "--counterparty-name", _SUPPLIER_NAME,
    ]  # fmt: skip
    confirmed = _invoke(args)
    if confirmed.exit_code == 0:
        return confirmed
    context = json.loads(confirmed.output)["error"].get("context") or {}
    blocker = _DIRECTION_BLOCKER_ID.search(str(context.get("unresolved_blockers", "")))
    assert blocker, confirmed.output
    return _invoke([*args, "--resolve", f"{blocker.group(1)}=supply:{_SUPPLIER_TAX_ID}"])


def test_confirm_reports_the_headroom_refused_fill_on_the_draft_it_re_reads(tmp_path: Path) -> None:
    """Confirm reads the document again, so the operator minting from it is told the same thing."""
    evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")

    with (
        _recording_runtime() as (chat_url, arrivals),
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_contention_check_override=False,
            cadrumo_llm_contention_safety_margin_bytes=_UNSATISFIABLE_MARGIN_BYTES,
        ),
    ):
        confirmed = _confirm_supplying_the_unassigned_identifier(evidence_id)

    assert confirmed.exit_code == 0, confirmed.output
    assert arrivals == []
    envelope = json.loads(confirmed.output)
    (notice,) = _label_reading_notices(envelope)
    assert notice["code"] == _HEADROOM_REFUSED
    assert notice["context"]["unread_fields"] == "supplier_name"


def test_a_fill_the_runtime_answers_is_merged_without_a_label_reading_notice(tmp_path: Path) -> None:
    """The positive control for the detector above: the same recorder sees an admitted fill arrive."""
    evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")

    with (
        _recording_runtime() as (chat_url, arrivals),
        override_settings(cadrumo_llm_ollama_chat_url=chat_url, cadrumo_llm_ollama_text_model=_UNASSESSED_MODEL),
    ):
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    assert arrivals == ["/api/chat"]
    assert envelope["result"]["supplier_name"] == _SUPPLIER_NAME
    assert envelope["result"]["grand_total"] == "72.60"
    assert _label_reading_notices(envelope) == []


def test_an_unreachable_runtime_leaves_the_label_reading_standing_with_a_warning(tmp_path: Path) -> None:
    evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")

    with (
        _unreachable_runtime_url() as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url, cadrumo_llm_ollama_text_model=_UNASSESSED_MODEL),
    ):
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    assert envelope["result"]["supplier_name"] is None
    assert envelope["result"]["grand_total"] == "72.60"
    (notice,) = _label_reading_notices(envelope)
    assert notice["code"] == _READER_UNAVAILABLE
    assert notice["severity"] == "warning"
    assert notice["context"]["reason"] == "reader_unavailable"
    assert notice["context"]["unread_fields"] == "supplier_name"
    assert "failed_condition_id" not in notice["context"]


def test_a_headroom_refusal_of_the_whole_read_is_unchanged(tmp_path: Path) -> None:
    """With no label reading to stand on, the model read is required and its refusal is the command's."""
    evidence_id = _add_evidence(tmp_path, _UNLABELLED_LINES, filename="unlabelled.pdf")

    with (
        _recording_runtime() as (chat_url, arrivals),
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_contention_check_override=False,
            cadrumo_llm_contention_safety_margin_bytes=_UNSATISFIABLE_MARGIN_BYTES,
        ),
    ):
        exit_code, envelope = _extract(evidence_id)

    assert exit_code != 0, envelope
    assert arrivals == []
    assert envelope["error"]["code"] == "REFUSED_LLM_CONTENTION"
