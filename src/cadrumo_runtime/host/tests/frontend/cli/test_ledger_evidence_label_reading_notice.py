"""Real-CLI regression: a label reading that stands without its model fill says why.

A text-layer invoice whose labels leave a required field unread asks the
person's text-extraction selection to fill it. That fill is optional: when it
cannot run, the label reading stands and the unread field stays empty. Two
conditions stop it, and each must reach the operator on the envelope's
``notices`` channel, because a draft with an empty field otherwise looks
exactly like a document that does not print it:

- the agent service cannot run the role's lane;
- the agent refuses to load the selected model because it does not fit this
  computer's free memory. The refusal is respected: the fill is not retried.

When the labels read nothing the model read is the whole read rather than a
fill, and its refusal stands unchanged.

A batch run keeps the same fact with the draft it stores, so the item's row,
the run's notices and a later re-run over the same documents all report it.

Drives the real Typer CLI tree, a real encrypted bucket session, a real
reportlab-generated text-bearing PDF, the real composed reader and the real
execution authority's model-run door. The agent service is the recording
stand-in the portable runtime relays each model run to; it records every run
reaching it, and only its reply or its refusal is authored here.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from cadrumo.adapters.outbound.llm.preconditions import LLMPreconditionCondition
from cadrumo.adapters.outbound.llm.tests.model_run_support import ON_HOST_LANE, RecordingModelRuns
from cadrumo.application.probe_outcomes import ProbePreconditionCondition
from cadrumo.core.config import load_settings
from cadrumo.core.model_roles import ModelRole
from cadrumo.tests.pdf_fixtures import text_pdf_bytes
from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from .ledger_ux_support import _add_evidence, _invoke, _open_bucket_session
from .portable_human_cli_runtime import serving_portable_agent

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]
__all__ = ["_open_bucket_session"]

_HEADROOM_REFUSED = "ledger.evidence.label_reading.headroom_refused"
_READER_UNAVAILABLE = "ledger.evidence.label_reading.reader_unavailable"
_LABEL_READING_CODES = {_HEADROOM_REFUSED, _READER_UNAVAILABLE}
_BATCH_LABEL_READING_DEGRADED = "ledger.evidence.batch.label_reading_degraded"

#: The precondition the agent's refusal to load a model too large for the free memory fails.
_LOAD_CAPACITY = ProbePreconditionCondition.LOAD_CAPACITY_AVAILABLE.value
_DOES_NOT_FIT = ModelRunRefusalCode.MODEL_DOES_NOT_FIT

_SUPPLIER_NAME = "Estacion de Servicio Albufera SL"
_SUPPLIER_TAX_ID = "B92000082"

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
    "Moneda: EUR",
)

# Nothing here is a label the rules read, so there is no reading to stand on.
_UNLABELLED_LINES = ("B1234567X B17283946 766,30",)

#: The service's reply to every fill: the one field the labels leave unread.
_FILL_REPLY = json.dumps({"supplier_name": _SUPPLIER_NAME, "supplier_name_anchor": _SUPPLIER_NAME})


def _fills(service: RecordingModelRuns) -> list[str]:
    """Return the role of every text-extraction run that reached the service: the fills under test.

    A read may also ask for an optional supply-nature proposal; that run is
    answered and never counted.
    """
    return [header.role for header, _body in service.runs if header.role == ModelRole.TEXT_EXTRACTION.value]


@contextmanager
def _recording_agent(
    *,
    lookup_refusal: ModelRunRefusalCode | None = None,
    run_refusal: ModelRunRefusalCode | None = None,
) -> Generator[RecordingModelRuns]:
    """Serve the profile's agent service on the on-host lane, recording every run.

    Each run is answered with the fill, or refused at its start with
    ``run_refusal`` when one is given.
    """
    service = RecordingModelRuns(
        replies=(_FILL_REPLY,), lane=ON_HOST_LANE, lookup_refusal=lookup_refusal, run_refusal=run_refusal
    )
    with serving_portable_agent(service):
        yield service


def _extract(evidence_id: str) -> tuple[int, dict[str, Any]]:
    extracted = _invoke(["--format", "json", "app", "ledger", "evidence", "extract", "--evidence-id", evidence_id])
    return extracted.exit_code, json.loads(extracted.output)


def _label_reading_notices(envelope: dict[str, Any]) -> list[dict[str, Any]]:
    return [notice for notice in envelope.get("notices", []) if notice["code"] in _LABEL_READING_CODES]


def test_a_fill_the_model_does_not_fit_leaves_the_label_reading_standing_and_is_not_retried(
    tmp_path: Path,
) -> None:

    with _recording_agent(run_refusal=_DOES_NOT_FIT) as service:
        evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    # The agent refused the one fill at its start; the refusal is final for
    # this read, so the fill is not sent again.
    assert ModelRole.TEXT_EXTRACTION in service.lookups
    assert _fills(service) == [ModelRole.TEXT_EXTRACTION.value]
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
    assert notice["context"]["failed_condition_id"] == _LOAD_CAPACITY


def _store_reading_for_review(evidence_id: str) -> None:
    """Seed review through the real reader and encrypted draft writer.

    Standalone CLI extract is read-only. Setup stores an actual reading, as
    the draft-review suites do, so the confirm case can inspect its findings.
    """
    from cadrumo.application.ledger.extraction_draft_store import write_extraction_draft
    from cadrumo.application.ledger.invoice_draft_extraction import extract_invoice_draft_from_evidence
    from cadrumo.application.ledger.invoice_extraction_authority import default_invoice_extraction_period
    from cadrumo.core.bucket_pointer import require_active_bucket_id
    from cadrumo.core.provenance_stamp import LOCAL_TRANSPORT_LABEL
    from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
    from cadrumo.domain.iva.regime_legend import resolve_regime_legends
    from cadrumo.entrypoints.adapter_composition_work_ports import build_ledger_evidence_ports
    from cadrumo.entrypoints.ledger_evidence_extraction_composition import invoice_draft_extraction_ports

    bucket_id = require_active_bucket_id()
    settings = load_settings()
    with bundled_indexed_authority().operation() as operation:
        draft = extract_invoice_draft_from_evidence(
            bucket_id=bucket_id,
            evidence_id=evidence_id,
            settings=settings,
            ports=invoice_draft_extraction_ports(
                evidence_ports=build_ledger_evidence_ports(bucket_id=bucket_id), operation=operation
            ),
            operation=operation,
            legends=resolve_regime_legends(
                operation=operation, effective_date=default_invoice_extraction_period().end_date
            ),
        )
        write_extraction_draft(
            bucket_id=bucket_id,
            evidence_reference=evidence_id,
            draft=draft,
            extractor="extract_invoice_draft_from_evidence",
            settings=settings,
            read_transports=(LOCAL_TRANSPORT_LABEL,),
        )


def _confirm_supplying_the_unassigned_identifier(evidence_id: str) -> Result:
    """Confirm, answering the one blocker a ticket with no party labels raises.

    Nothing on the ticket assigns its only identifier to a party, so confirm
    asks the operator to state the counterparty's identifier. It is supplied
    rather than widened away; the label-reading notice under test is unrelated
    to that blocker and is emitted on the confirmation that succeeds.
    """
    extracted_code, extracted = _extract(evidence_id)
    assert extracted_code == 0, extracted
    reviewed = extracted["result"]
    args = [
        "--format", "json", "app", "ledger", "evidence", "confirm",
        "--expected-source-sha256", reviewed["source_sha256"],
        "--expected-draft-review-sha256", reviewed["draft_review_sha256"],
        "--country-code", "ES",
        "--evidence-id", evidence_id,
        "--kind", "received",
        "--counterparty-name", _SUPPLIER_NAME,
    ]  # fmt: skip
    confirmed = _invoke(args)
    if confirmed.exit_code == 0:
        return confirmed
    error = json.loads(confirmed.output)["error"]
    assert error["code"] == "REFUSED_LEDGER_CONFIRMATION_BLOCKED", confirmed.output
    review = _invoke(["--format", "json", "app", "ledger", "evidence", "review", "view", evidence_id])
    assert review.exit_code == 0, review.output
    blockers = json.loads(review.output)["result"]["blockers"]
    direction = [blocker for blocker in blockers if blocker["reason"] == "unresolved_direction"]
    assert len(direction) == 1, review.output
    return _invoke([*args, "--resolve", f"{direction[0]['blocker_id']}=supply:{_SUPPLIER_TAX_ID}"])


def test_confirm_reports_the_fill_the_model_does_not_fit_on_the_draft_it_re_reads(tmp_path: Path) -> None:
    """Confirm reads the document again, so the operator minting from it is told the same thing."""

    with _recording_agent(run_refusal=_DOES_NOT_FIT) as service:
        evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")
        _store_reading_for_review(evidence_id)
        confirmed = _confirm_supplying_the_unassigned_identifier(evidence_id)

    assert confirmed.exit_code == 0, confirmed.output
    # The stored reading, the review's extract and confirm's re-read each ask
    # for the fill once; none of the three refusals is retried.
    assert _fills(service) == [ModelRole.TEXT_EXTRACTION.value] * 3
    envelope = json.loads(confirmed.output)
    (notice,) = _label_reading_notices(envelope)
    assert notice["code"] == _HEADROOM_REFUSED
    assert notice["context"]["unread_fields"] == "supplier_name"


def test_a_fill_the_service_answers_is_merged_without_a_label_reading_notice(tmp_path: Path) -> None:
    """The positive control for the detector above: the same recorder sees an admitted fill arrive."""

    with _recording_agent() as service:
        evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    assert _fills(service) == [ModelRole.TEXT_EXTRACTION.value]
    assert envelope["result"]["supplier_name"] == _SUPPLIER_NAME
    assert envelope["result"]["grand_total"] == "72.60"
    assert _label_reading_notices(envelope) == []


def test_an_unavailable_lane_leaves_the_label_reading_standing_with_a_warning(tmp_path: Path) -> None:
    """The service cannot run the role's lane: the fill is refused at its lookup and nothing is run."""

    with _recording_agent(lookup_refusal=ModelRunRefusalCode.LANE_UNAVAILABLE) as service:
        evidence_id = _add_evidence(tmp_path, _PARTIALLY_LABELLED_LINES, filename="ticket.pdf")
        exit_code, envelope = _extract(evidence_id)

    assert exit_code == 0, envelope
    assert ModelRole.TEXT_EXTRACTION in service.lookups
    assert service.runs == []
    assert envelope["result"]["supplier_name"] is None
    assert envelope["result"]["grand_total"] == "72.60"
    (notice,) = _label_reading_notices(envelope)
    assert notice["code"] == _READER_UNAVAILABLE
    assert notice["severity"] == "warning"
    assert notice["context"]["reason"] == "reader_unavailable"
    assert notice["context"]["unread_fields"] == "supplier_name"
    # The notice names the agent run that did not complete; no setup supplies an unavailable lane.
    assert notice["context"]["failed_condition_id"] == LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED.value


def test_a_does_not_fit_refusal_of_the_whole_read_is_unchanged(tmp_path: Path) -> None:
    """With no label reading to stand on, the model read is required and its refusal is the command's."""

    with _recording_agent(run_refusal=_DOES_NOT_FIT) as service:
        evidence_id = _add_evidence(tmp_path, _UNLABELLED_LINES, filename="unlabelled.pdf")
        exit_code, envelope = _extract(evidence_id)

    assert exit_code != 0, envelope
    assert len(service.runs) == 1, "the refused read is not retried"
    assert envelope["error"]["code"] == "REFUSED_LLM_CONTENTION"


_CORPUS = files("cadrumo.application.ledger.tests") / "_evidence_corpus"

#: A structured record read by a parser: a batch item that never asks for a
#: fill, so it cannot be degraded by a refused load.
_STRUCTURED = "facturae_32_series_and_parties_invoice.xml"


def _batch(folder: Path, *, kind: str = "received") -> tuple[int, dict[str, Any]]:
    ran = _invoke(["--format", "json", "app", "ledger", "evidence", "batch", str(folder), "--kind", kind])
    return ran.exit_code, json.loads(ran.output)


def _rows_by_source(envelope: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["source_name"]: row for row in envelope["result"]["items"]}


def test_a_batch_item_degraded_by_a_refused_load_is_stored_and_reported_with_its_reason(tmp_path: Path) -> None:
    """One item of the run is degraded; its row, the run's notice and a re-run over its stored draft say so.

    The re-run reads nothing -- both documents are already ingested -- so the
    reason it reports can only have come from the encrypted draft record the
    first run stored.
    """
    folder = tmp_path / "batch"
    folder.mkdir()
    (folder / "ticket.pdf").write_bytes(text_pdf_bytes(_PARTIALLY_LABELLED_LINES))
    (folder / _STRUCTURED).write_bytes((_CORPUS / _STRUCTURED).read_bytes())

    with _recording_agent(run_refusal=_DOES_NOT_FIT) as service:
        exit_code, first = _batch(folder)

    assert exit_code == 0, first
    assert _fills(service) == [ModelRole.TEXT_EXTRACTION.value], "the refused fill is not retried"
    rows = _rows_by_source(first)
    ticket = rows["ticket.pdf"]
    assert ticket["status"] in {"ingested", "pending_review"}, ticket
    assert ticket["label_reading_fallback"] == {
        "cause": "load_headroom_refused",
        "unread_fields": ["supplier_name"],
        "reader_error_type": "LLMContentionError",
        "failed_condition_id": _LOAD_CAPACITY,
        # A model that does not fit is not something setup supplies.
        "recovery_action_id": None,
    }
    assert rows[_STRUCTURED]["label_reading_fallback"] is None
    (degraded,) = [notice for notice in first["notices"] if notice["code"] == _BATCH_LABEL_READING_DEGRADED]
    assert degraded["severity"] == "warning"
    assert degraded["context"] == {"label_reading_degraded": "1", "reasons": "load_headroom_refused"}
    assert first["status"] == "warning"

    with _recording_agent() as service:
        exit_code, second = _batch(folder)

    assert exit_code == 0, second
    assert _fills(service) == [], "a re-run over ingested documents must not read them again"
    rerun = _rows_by_source(second)
    assert rerun["ticket.pdf"]["status"] == "no_op", second
    assert rerun["ticket.pdf"]["label_reading_fallback"] == ticket["label_reading_fallback"]
    assert rerun[_STRUCTURED]["status"] == "no_op", second
    assert rerun[_STRUCTURED]["label_reading_fallback"] is None
    assert _BATCH_LABEL_READING_DEGRADED in {notice["code"] for notice in second["notices"]}


def test_a_stored_received_draft_does_not_complete_an_issued_batch_without_a_reader(tmp_path: Path) -> None:
    """Same bytes in the other direction require their own reading and custody."""
    folder = tmp_path / "direction-control"
    folder.mkdir()
    (folder / "ticket.pdf").write_bytes(text_pdf_bytes(_PARTIALLY_LABELLED_LINES))
    with _recording_agent(run_refusal=_DOES_NOT_FIT) as service:
        code, received = _batch(folder)
    assert code == 0, received
    assert _fills(service) == [ModelRole.TEXT_EXTRACTION.value]
    assert received["result"]["items"][0]["label_reading_fallback"]["cause"] == "load_headroom_refused"

    # No agent service answers now. The received draft is reusable, but cannot
    # satisfy the distinct issued identity: the issued item is read again, its
    # own fill is refused for the missing service, and its labels stand.
    code, issued = _batch(folder, kind="issued")
    assert code == 0, issued
    (item,) = issued["result"]["items"]
    assert item["direction"] == "issued", issued
    assert item["status"] == "pending_review", issued
    assert item["needed_inference"] is True
    assert item["label_reading_fallback"]["cause"] == "reader_unavailable"
    assert item["label_reading_fallback"]["failed_condition_id"] == (
        LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED.value
    )
    assert issued["result"]["summary"]["no_op"] == 0
