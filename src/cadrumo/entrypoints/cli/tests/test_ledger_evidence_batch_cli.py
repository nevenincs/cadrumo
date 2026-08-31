"""Real-CLI regression for the bounded evidence batch run.

Drives the real Typer tree against a real encrypted bucket over the bundled
synthetic corpus. Every property here is invisible on a happy path: a surface
that aborted on the first failure would report correctly when nothing fails, and
one that re-ingested on every pass would look right on its first pass. So the
poisoned batch is paired with an all-good POSITIVE CONTROL -- without it, an exit
status of 1 could equally have come from anything ambient in the session, and a
"the run completed" assertion could not tell a guarded run from a lucky ordering.

Deterministic throughout: the structured record is read by a parser and the
malformed PDF refuses before any reader is selected. No model is loaded, pulled
or contacted.

Every assertion is on CODES and STRUCTURE -- envelope command, statuses, notice
codes, exit codes -- never on prose, which is localised.

See Also:
    :func:`~entrypoints.cli._ledger_evidence_batch_cli.register_evidence_batch_command`
        The surface under test.
    :func:`~application.ledger.batch_ingest.run_evidence_batch`
        The run it projects.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from ....application.ledger.batch_ingest import (
    BatchItemResult,
    BatchRunResult,
    InferencePause,
    UnresolvedBatchSource,
    batch_item_identity,
)
from ....application.ledger.preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict
from ....application.operator_actions._models import ConditionEvidence, PreconditionVerdict
from ....application.provisioning import ProvisioningPreconditionCondition
from ....core.config import override_settings
from ....core.json_contract import ResolvedActionReference, ResolvedNoticeAction, ResolvedPreconditionAction
from ....core.operator_action_enums import ActionConditionality, ActionEvidenceProvenance, NoRecoveryOutcome
from ....domain.iva.classification import InvoiceKind
from .._ledger_evidence_batch_cli import _batch_payload, _batch_text_lines, _run_notices
from ._ledger_ux_support import _invoke, open_ledger_ux_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CORPUS = Path(__file__).parents[3] / "application" / "ledger" / "tests" / "_evidence_corpus"

#: A structured record: read by a parser, so this row never reaches a model.
_GOOD = "facturae_32_series_and_parties_invoice.xml"

#: The poison. Malformed bytes behind a PDF extension -- the shape that must
#: produce a refusal ROW rather than end the run.
_POISON = "adversarial_malformed.pdf"

_ADDRESS = "a" * 64
_RUNTIME_REACHABLE = ProvisioningPreconditionCondition.RUNTIME_REACHABLE.value


@pytest.fixture
def session(tmp_path: Path) -> Iterator[None]:
    """A live bucket session the batch verb writes its evidence into.

    The contention override is set, and it is load-bearing rather than
    incidental. This host reports no readable accelerator, so admission control
    fails CLOSED and correctly refuses to admit a model load; left alone, the
    poisoned PDF is therefore DEFERRED before the extractor ever sees it and
    every refusal assertion below would silently measure the pause path instead.

    The override is the documented operator setting for exactly this machine
    class -- the pause's own remediation text names it -- so it configures the
    guard rather than reaching beneath it, and the run still goes through the
    real extraction path. No model is contacted: the poison refuses on its bytes
    and the structured record is read by a parser.
    """
    with open_ledger_ux_session(tmp_path), override_settings(cadrumo_llm_contention_check_override=True):
        yield


def _folder(tmp_path: Path, *names: str) -> Path:
    folder = tmp_path / ("batch_" + "_".join(name.split(".")[0][:12] for name in names))
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes((_CORPUS / name).read_bytes())
    return folder


def _json_run(args: list[str], *, expected_exit: int) -> dict[str, object]:
    result = _invoke(["--format", "json", *args])
    assert result.exit_code == expected_exit, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, dict), result.output
    assert payload["command"] == "ledger.evidence.batch"
    body = payload["result"]
    assert isinstance(body, dict)
    typed_body: dict[str, object] = {str(key): value for key, value in body.items()}
    typed_body["__notices__"] = payload["notices"]
    return typed_body


def _rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    value = payload["items"]
    assert isinstance(value, list), f"items decoded to {type(value).__name__}, not a list"
    rows: list[dict[str, object]] = []
    for entry in value:
        assert isinstance(entry, dict), f"an item decoded to {type(entry).__name__}, not an object"
        rows.append(entry)
    return rows


def _notice_codes(payload: Mapping[str, object]) -> set[str]:
    notices = payload["__notices__"]
    assert isinstance(notices, list)
    codes: set[str] = set()
    for notice in notices:
        assert isinstance(notice, dict)
        codes.add(str(notice["code"]))
    return codes


def test_a_poisoned_item_is_reported_as_a_row_and_the_run_still_completes(
    session: None,
    tmp_path: Path,
) -> None:
    """The bad document becomes a refusal row; the good one is still ingested.

    This is the whole point of the verb. A surface that let one document end the
    run would discard the result already produced for the other, which is the
    shape the adjacent statement-folder import shipped with.
    """
    folder = _folder(tmp_path, _GOOD, _POISON)

    body = _json_run(
        ["app", "ledger", "evidence", "batch", str(folder), "--kind", "received"],
        expected_exit=1,
    )

    rows = {str(row["source_name"]): row for row in _rows(body)}
    assert set(rows) == {_GOOD, _POISON}, "the run did not produce a row for every submitted document"

    poison = rows[_POISON]
    assert poison["status"] == "refused"
    assert poison["refusal_code"], "a refused row must name the reason it was refused"
    assert poison["refusal_facts"], "a refused row must say what was seen, not only that it failed"
    assert poison["refusal_action"], "a refused row must carry its resolved action or no-recovery outcome"

    good = rows[_GOOD]
    assert good["status"] in {"ingested", "pending_review"}, good
    assert good["refusal_code"] is None

    assert body["any_failed"] is True
    assert "ledger.evidence.batch.items_refused" in _notice_codes(body)


def test_an_all_good_batch_exits_zero_with_no_refusal(session: None, tmp_path: Path) -> None:
    """The positive control for the test above.

    Without it, the exit status of 1 there is not attributable to the poison:
    any ambient failure in the session would produce the same reading. This run
    differs from that one in exactly one way -- the poisoned file is absent.
    """
    folder = _folder(tmp_path, _GOOD)

    body = _json_run(
        ["app", "ledger", "evidence", "batch", str(folder), "--kind", "received"],
        expected_exit=0,
    )

    statuses = {str(row["status"]) for row in _rows(body)}
    assert statuses <= {"ingested", "pending_review", "no_op"}, statuses
    assert body["any_failed"] is False
    assert body["unresolved"] == []
    assert "ledger.evidence.batch.items_refused" not in _notice_codes(body)


def test_repeated_file_options_are_an_equivalent_source_set(session: None, tmp_path: Path) -> None:
    """``--file`` repeated names the same batch a directory would.

    Per the CLI standard the single-local-file option is ``--file``; the verb
    accepts it repeatedly so an operator can batch a hand-picked set without
    staging a directory first.
    """
    folder = _folder(tmp_path, _GOOD, _POISON)

    body = _json_run(
        [
            "app",
            "ledger",
            "evidence",
            "batch",
            "--kind",
            "received",
            "--file",
            str(folder / _GOOD),
            "--file",
            str(folder / _POISON),
        ],
        expected_exit=1,
    )

    assert {str(row["source_name"]) for row in _rows(body)} == {_GOOD, _POISON}
    assert body["any_failed"] is True


def test_a_second_run_reports_the_completed_document_as_a_no_op(session: None, tmp_path: Path) -> None:
    """Re-run is the resume: the already-ingested document is not written twice."""
    folder = _folder(tmp_path, _GOOD)

    first = _json_run(
        ["app", "ledger", "evidence", "batch", str(folder), "--kind", "received"],
        expected_exit=0,
    )
    assert {str(row["status"]) for row in _rows(first)} <= {"ingested", "pending_review"}

    second = _json_run(
        ["app", "ledger", "evidence", "batch", str(folder), "--kind", "received"],
        expected_exit=0,
    )
    assert [str(row["status"]) for row in _rows(second)] == ["no_op"]
    assert [str(row["identity"]) for row in _rows(second)] == [str(row["identity"]) for row in _rows(first)]


def test_no_source_is_a_refusal_naming_both_ways_to_supply_one(session: None, tmp_path: Path) -> None:
    """A batch with nothing to do refuses rather than reporting an empty success."""
    result = _invoke(["app", "ledger", "evidence", "batch", "--kind", "received"])
    assert result.exit_code != 0, result.output


def test_json_carries_the_complete_row_set_and_no_per_item_progress_notice(
    session: None,
    tmp_path: Path,
) -> None:
    """JSON reports rows; per-item progress is a text-mode stream only.

    Duplicating each row as a notice would be the second progress channel the
    design refuses, and it would bloat the one document a machine consumer
    parses.
    """
    folder = _folder(tmp_path, _GOOD, _POISON)

    body = _json_run(
        ["app", "ledger", "evidence", "batch", str(folder), "--kind", "received"],
        expected_exit=1,
    )

    assert len(_rows(body)) == 2
    per_item_codes = {code for code in _notice_codes(body) if code.startswith("ledger.evidence.batch.item.")}
    assert per_item_codes == set(), f"per-item progress leaked into the JSON notices channel: {per_item_codes}"
    summary = body["summary"]
    assert isinstance(summary, dict)
    assert set(summary) == {"ingested", "no_op", "paused", "pending_review", "refused"}


def test_text_mode_streams_one_progress_line_per_item(session: None, tmp_path: Path) -> None:
    """Text mode reports progress as it happens, one line per completed document."""
    folder = _folder(tmp_path, _GOOD, _POISON)

    result = _invoke(["app", "ledger", "evidence", "batch", str(folder), "--kind", "received"])
    assert result.exit_code == 1, result.output

    progress = [line for line in result.output.splitlines() if "ledger.evidence.batch.item." in line]
    assert len(progress) == 2, f"expected one progress line per document, got: {progress}"
    assert any("ledger.evidence.batch.item.refused" in line for line in progress)
    assert any("ledger.evidence.batch.items_refused" in line for line in result.output.splitlines())


def _paused_row(name: str) -> BatchItemResult:
    return BatchItemResult(
        content_address=_ADDRESS,
        identity=batch_item_identity(content_address=_ADDRESS, direction=InvoiceKind.RECEIVED),
        direction=InvoiceKind.RECEIVED,
        source_name=name,
        status="paused",
    )


def _pending_review_row(name: str) -> BatchItemResult:
    return BatchItemResult(
        content_address=_ADDRESS,
        identity=batch_item_identity(content_address=_ADDRESS, direction=InvoiceKind.RECEIVED),
        direction=InvoiceKind.RECEIVED,
        source_name=name,
        status="pending_review",
    )


def _refused_row(name: str) -> BatchItemResult:
    address = "b" * 64
    return BatchItemResult(
        content_address=address,
        identity=batch_item_identity(content_address=address, direction=InvoiceKind.RECEIVED),
        direction=InvoiceKind.RECEIVED,
        source_name=name,
        status="refused",
        refusal_code="not_readable",
        refusal_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_TEXT_LAYER_AVAILABLE,
            facts={"layer_available": False},
        ),
    )


_PAUSE = InferencePause(
    facts={"runtime_reachable": False, "runtime_url": "http://127.0.0.1:11434"},
    precondition_verdict=PreconditionVerdict(
        failed_condition_id=_RUNTIME_REACHABLE,
        evidence=(
            ConditionEvidence(
                condition_id=_RUNTIME_REACHABLE,
                evidence_id=f"{_RUNTIME_REACHABLE}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values={"runtime_reachable": False, "runtime_url": "http://127.0.0.1:11434"},
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    ),
)


def test_a_deferred_run_reports_distinctly_from_a_failed_one() -> None:
    """Deferral and refusal are two signals, and the surface never merges them.

    One boolean cannot say both "nothing went wrong" and "half the work
    remains", and an operator acts differently on each: a deferral is a machine
    condition with a remediation, a refusal is a document to look at. The
    remediation carried is the PROBE's own, never a fixed provisioning verb --
    sending an operator to download a model they may already have is a wrong
    instruction, not merely a vague one.
    """
    deferred = BatchRunResult(items=(_paused_row("scan.pdf"),), inference_pause=_PAUSE)
    assert deferred.any_deferred is True
    assert deferred.any_failed is False

    codes = {notice.code for notice in _run_notices(deferred)}
    assert codes == {"ledger.evidence.batch.work_deferred"}
    deferred_notice = _run_notices(deferred)[0]
    assert isinstance(deferred_notice.action, ResolvedPreconditionAction)
    assert deferred_notice.action.failed_condition_id == _RUNTIME_REACHABLE
    deferred_context = deferred_notice.context
    assert deferred_context is not None, "the deferral notice carries no structured cause"
    assert deferred_context == {"paused": "1"}

    pause_payload = _batch_payload(deferred, bucket_id="bucket", direction=InvoiceKind.RECEIVED)
    assert pause_payload.inference_pause is not None
    assert pause_payload.inference_pause.facts == _PAUSE.facts
    assert pause_payload.inference_pause.precondition_action.failed_condition_id == _RUNTIME_REACHABLE

    lines = _batch_text_lines(deferred, bucket_id="bucket", direction=InvoiceKind.RECEIVED)
    assert "paused.facts.runtime_reachable\tfalse" in lines
    assert any(line.startswith("paused.precondition_action.failed_condition_id\t") for line in lines)

    failed = BatchRunResult(items=(_refused_row("broken.pdf"),))
    assert {notice.code for notice in _run_notices(failed)} == {"ledger.evidence.batch.items_refused"}

    both = BatchRunResult(
        items=(_paused_row("scan.pdf"), _refused_row("broken.pdf")),
        inference_pause=_PAUSE,
    )
    assert {notice.code for notice in _run_notices(both)} == {
        "ledger.evidence.batch.items_refused",
        "ledger.evidence.batch.work_deferred",
    }


def test_pending_review_resolves_the_review_queue_action() -> None:
    notices = _run_notices(BatchRunResult(items=(_pending_review_row("review.pdf"),)))

    (notice,) = notices
    assert notice.code == "ledger.evidence.batch.pending_review"
    notice_action = notice.action
    assert isinstance(notice_action, ResolvedNoticeAction)
    action_reference = notice_action.action
    assert isinstance(action_reference, ResolvedActionReference)
    assert action_reference.action_id == "operator.ledger.evidence.review.list"
    assert action_reference.target_command_key == "ledger.evidence.review.list"
    assert notice_action.argument_bindings == ()


def test_an_unreadable_source_counts_as_a_failure_without_becoming_an_item() -> None:
    """A file whose bytes cannot be read is reported, and it fails the run.

    It cannot be an item row -- an item's identity IS its content address and an
    unreadable file has none -- but dropping it silently would be worse than
    either.
    """
    run = BatchRunResult(
        unresolved=(
            UnresolvedBatchSource(
                source_name="gone.pdf",
                refusal_code="unreadable_source",
                refusal_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.EVIDENCE_FILE_READABLE,
                    facts={"source_name": "gone.pdf", "file_readable": False},
                ),
            ),
        ),
    )
    assert run.any_failed is True
    notices = _run_notices(run)
    assert [notice.code for notice in notices] == ["ledger.evidence.batch.items_refused"]
    refusal_context = notices[0].context
    assert refusal_context is not None, "the refusal notice carries no structured context"
    assert refusal_context["unresolved"] == "1"
