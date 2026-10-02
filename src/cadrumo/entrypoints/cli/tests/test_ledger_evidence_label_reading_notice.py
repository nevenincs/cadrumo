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
  loaded, and nothing is sent to the runtime;
- admission control refuses the fill because another read already holds the
  process's on-host inference slot. Nothing is sent to the runtime either.

When the labels read nothing the model read is the whole read rather than a
fill, and admission control's refusal stands unchanged.

A batch run keeps the same fact with the draft it stores, so the item's row,
the run's notices and a later re-run over the same documents all report it.

Drives the real Typer CLI tree, a real encrypted bucket session, a real
reportlab-generated text-bearing PDF, the real composed reader and the real
admission check. The runtime is a real HTTP endpoint on a loopback port that
records every request reaching it; only its reply is authored here. The
occupied slot is held by a real client dispatch that the runtime keeps open,
so the arena is full the way a concurrent read fills it.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import re
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import Any, override

import pytest
from click.testing import Result

from ....adapters.outbound.llm.client import LLMClient
from ....adapters.outbound.llm.models import LLMRequest
from ....adapters.persistence.llm.cache import LLMCache
from ....adapters.persistence.llm.run_telemetry import LLMRunTelemetryRecorder
from ....adapters.persistence.llm.usage import UsageRecorder
from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.config import load_settings, override_settings
from ....core.config_support import LLMProvider
from ....core.model_catalogue import model_candidate
from ....tests.fixtures.settings import EnvFileFreeSettings
from ....tests.loopback_llm import (
    SilentLoopbackHandler,
    ollama_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ....tests.pdf_fixtures import text_pdf_bytes
from .ledger_ux_support import _add_evidence, _invoke, _open_bucket_session, admit_an_unmeasurable_host

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session", "admit_an_unmeasurable_host"]

_HEADROOM_REFUSED = "ledger.evidence.label_reading.headroom_refused"
_READER_UNAVAILABLE = "ledger.evidence.label_reading.reader_unavailable"
_BUSY_REFUSED = "ledger.evidence.label_reading.busy_refused"
_LABEL_READING_CODES = {_HEADROOM_REFUSED, _READER_UNAVAILABLE, _BUSY_REFUSED}
_BATCH_LABEL_READING_DEGRADED = "ledger.evidence.batch.label_reading_degraded"
_SLOT_AVAILABLE = "llm.local_inference.slot_available"

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


# --- an optional fill refused because another read holds the inference slot ---

#: The prompt the holding read sends, so the runtime can tell it from the fill.
_HOLDING_PROMPT = "cadrumo-test: hold the on-host inference slot"

#: How long the runtime keeps the holding read open, and how long each side
#: waits on the other. Generous, because a miss is a hang rather than a pass.
_HOLD_WAIT_S = 60.0

_CORPUS = Path(__file__).parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"

#: A structured record read by a parser: a batch item that never asks for a
#: fill, so it cannot be degraded by the occupied slot.
_STRUCTURED = "facturae_32_series_and_parties_invoice.xml"


def _start_holding_read(tmp_path: Path) -> tuple[threading.Thread, list[object]]:
    """Dispatch one real on-host read from its own thread, and let it hold the slot.

    The thread runs in a copy of this context, because the runtime URL is bound
    through a context variable and a bare thread would resolve the host's real
    runtime instead of the loopback one. The model is uncatalogued, so the
    holding read is admitted on headroom on any host and it is occupancy alone
    that the read under test meets.
    """
    root = tmp_path / "holding-read"
    settings = EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model=_UNASSESSED_MODEL,
        cadrumo_llm_ollama_chat_url=load_settings().cadrumo_llm_ollama_chat_url,
        cadrumo_llm_cache_dir=root / "cache",
        cadrumo_llm_usage_dir=root / "usage",
        cadrumo_llm_run_telemetry_dir=root / "run-telemetry",
    )
    client = LLMClient(
        settings=settings,
        cache=LLMCache(root_dir=settings.cadrumo_llm_cache_dir),
        usage_recorder=UsageRecorder(root_dir=settings.cadrumo_llm_usage_dir),
        run_telemetry_recorder=LLMRunTelemetryRecorder(root_dir=settings.cadrumo_llm_run_telemetry_dir),
    )
    outcome: list[object] = []
    context = contextvars.copy_context()

    def _run() -> None:
        try:
            outcome.append(context.run(asyncio.run, client.complete(LLMRequest(prompt=_HOLDING_PROMPT))))
        except BaseException as exc:  # captured and re-asserted by the caller
            outcome.append(exc)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread, outcome


@contextmanager
def _runtime_with_the_slot(tmp_path: Path, *, held: bool) -> Iterator[list[str]]:
    """Serve the reading runtime, with another read holding the inference slot when ``held``.

    Yields the requests that reached the runtime OTHER than the holding read,
    so an empty list means no read under test was sent. ``held=False`` is the
    positive control: the same runtime and the same recorder, with the slot
    free, see the fill arrive.
    """
    arrivals: list[str] = []
    holding = threading.Event()
    release = threading.Event()

    class _Runtime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            # The batch lane asks the runtime which models it has before it
            # attempts a document that needs one.
            write_json_response(
                self,
                {"models": [{"name": _UNASSESSED_MODEL, "model": _UNASSESSED_MODEL, "size": 0}]},
                status=HTTPStatus.OK,
            )

        @override
        def do_POST(self) -> None:
            prompt = json.dumps(read_json_body(self)["messages"])
            if _HOLDING_PROMPT in prompt:
                holding.set()
                release.wait(_HOLD_WAIT_S)
                write_json_response(self, ollama_chat_reply("held", model=_UNASSESSED_MODEL), status=HTTPStatus.OK)
                return
            arrivals.append(self.path)
            reply = {"supplier_name": _SUPPLIER_NAME, "supplier_name_anchor": _SUPPLIER_NAME}
            write_json_response(
                self,
                ollama_chat_reply(json.dumps(reply), model=_UNASSESSED_MODEL, prompt_eval_count=100, eval_count=20),
                status=HTTPStatus.OK,
            )

    with (
        serving_loopback(_Runtime, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url, cadrumo_llm_ollama_text_model=_UNASSESSED_MODEL),
    ):
        if not held:
            yield arrivals
            return
        thread, outcome = _start_holding_read(tmp_path)
        try:
            assert holding.wait(_HOLD_WAIT_S), f"the holding read never reached the runtime: {outcome}"
            yield arrivals
        finally:
            release.set()
            thread.join(_HOLD_WAIT_S)
        # A slot still held here would refuse every later read in this process.
        assert not thread.is_alive(), "the holding read did not finish, so the slot may still be held"
        (completed,) = outcome
        assert not isinstance(completed, BaseException), completed


def test_a_busy_refused_fill_leaves_the_label_reading_standing_and_never_touches_the_runtime(
    tmp_path: Path,
) -> None:
    evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")

    with _runtime_with_the_slot(tmp_path, held=True) as arrivals:
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    # Refused at admission: the fill was never sent, so nothing was loaded for it.
    assert arrivals == []
    result = envelope["result"]
    assert result["supplier_name"] is None
    assert result["invoice_number"] == "T-0042-2026"
    assert result["grand_total"] == "72.60"
    (notice,) = _label_reading_notices(envelope)
    assert notice["code"] == _BUSY_REFUSED
    assert notice["severity"] == "warning"
    assert envelope["status"] == "warning"
    assert notice["context"]["reason"] == "inference_slot_busy"
    assert notice["context"]["unread_fields"] == "supplier_name"
    assert notice["context"]["reader_error_type"] == "LLMBusyError"
    assert notice["context"]["failed_condition_id"] == _SLOT_AVAILABLE


def test_the_same_runtime_sees_the_fill_arrive_when_the_slot_is_free(tmp_path: Path) -> None:
    """The positive control for the case above: with the slot free the recorder sees the fill."""
    evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")

    with _runtime_with_the_slot(tmp_path, held=False) as arrivals:
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    assert arrivals == ["/api/chat"]
    assert envelope["result"]["supplier_name"] == _SUPPLIER_NAME
    assert _label_reading_notices(envelope) == []


def test_a_busy_refusal_of_the_whole_read_is_unchanged(tmp_path: Path) -> None:
    """With no label reading to stand on, the occupancy refusal is the command's own refusal."""
    evidence_id = _add_evidence(tmp_path, _UNLABELLED_LINES, filename="unlabelled.pdf")

    with _runtime_with_the_slot(tmp_path, held=True) as arrivals:
        exit_code, envelope = _extract(evidence_id)

    assert exit_code != 0, envelope
    assert arrivals == []
    assert envelope["error"]["code"] == "REFUSED_LLM_BUSY"


def _batch(folder: Path) -> tuple[int, dict[str, Any]]:
    ran = _invoke(["--format", "json", "app", "ledger", "evidence", "batch", str(folder), "--kind", "received"])
    return ran.exit_code, json.loads(ran.output)


def _rows_by_source(envelope: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["source_name"]: row for row in envelope["result"]["items"]}


def test_a_batch_item_degraded_by_a_busy_fill_is_stored_and_reported_with_its_reason(tmp_path: Path) -> None:
    """One item of the run is degraded; its row, the run's notice and a re-run over its stored draft say so.

    The re-run reads nothing -- both documents are already ingested -- so the
    reason it reports can only have come from the encrypted draft record the
    first run stored.
    """
    folder = tmp_path / "batch"
    folder.mkdir()
    (folder / "ticket.pdf").write_bytes(text_pdf_bytes(_PARTIALLY_LABELLED_LINES))
    (folder / _STRUCTURED).write_bytes((_CORPUS / _STRUCTURED).read_bytes())

    with _runtime_with_the_slot(tmp_path, held=True) as arrivals:
        exit_code, first = _batch(folder)

    assert exit_code == 0, first
    assert arrivals == []
    rows = _rows_by_source(first)
    ticket = rows["ticket.pdf"]
    assert ticket["status"] in {"ingested", "pending_review"}, ticket
    assert ticket["label_reading_fallback"] == {
        "cause": "inference_slot_busy",
        "unread_fields": ["supplier_name"],
        "reader_error_type": "LLMBusyError",
        "failed_condition_id": _SLOT_AVAILABLE,
    }
    assert rows[_STRUCTURED]["label_reading_fallback"] is None
    (degraded,) = [notice for notice in first["notices"] if notice["code"] == _BATCH_LABEL_READING_DEGRADED]
    assert degraded["severity"] == "warning"
    assert degraded["context"] == {"label_reading_degraded": "1", "reasons": "inference_slot_busy"}
    assert first["status"] == "warning"

    with _runtime_with_the_slot(tmp_path, held=False) as arrivals:
        exit_code, second = _batch(folder)

    assert exit_code == 0, second
    assert arrivals == [], "a re-run over ingested documents must not read them again"
    rerun = _rows_by_source(second)
    assert rerun["ticket.pdf"]["status"] == "no_op"
    assert rerun["ticket.pdf"]["label_reading_fallback"] == ticket["label_reading_fallback"]
    assert rerun[_STRUCTURED]["status"] == "no_op"
    assert rerun[_STRUCTURED]["label_reading_fallback"] is None
    assert _BATCH_LABEL_READING_DEGRADED in {notice["code"] for notice in second["notices"]}
