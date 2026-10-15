"""Prove a review-gated operation's reject and apply paths through a built package's own programs.

Everything runs as real processes on a fresh storage root: the package's
``cadrumo-runtime --configured-root``, its ``aeat`` command line, its
``cadrumo-mcp`` server driven by an MCP client, and the local model server
reading an existing model store. The person's steps go through the command
line with the password on its standard input; the agent's steps go through an
attended MCP connection the person approved. The run proves, one receipt line
per step:

- a disposable profile with synthetic taxpayer facts and one ledger row;
- ``ledger.classify.review`` pauses with the local model's proposal and has
  written nothing before the decision;
- a rejected review leaves the row exactly as before, as the command line, an
  independent reader, lists it, and adds exactly one rejection to the row's
  audit history;
- an applied review classifies the row, the command line reads that one
  change and exactly one classification event, a second answer to the same
  review is refused, and neither the row nor its history changes again;
- the runtime stops, nothing survives the run, and the root is removed.

The attendance approval admits the MCP connection; it is not the review's
answer, which is given by ``respond`` on the review's own interaction. Run it
with ``just verify-reviewed-operation PACKAGE``. It needs the local
``qwen3:1.7b`` model in an Ollama store (``--ollama-models``, by default
Cadrumo's own) and reports the review unproven without it, or when the package
was built without the optional ``llm`` extra and so refuses local-model work;
nothing is downloaded.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import tempfile
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .caller_owned_root import (
    AcceptanceError,
    Programs,
    Receipt,
    caller_owned_runtime,
    consumer_environment,
    require,
    run_cli,
)
from .mcp_proof_support import (
    McpSession,
    ask_and_decide,
    execute,
    local_model,
    mcp_session,
    model_store,
    observe,
    settled,
)
from .proof_support import (
    Profile,
    acceptance_failure,
    create_profile,
    identify_profile,
    package_identity,
    started_processes,
    state_taxpayer,
)
from .session_holder import AsyncRuntimeSessionHolder

_PROFILE = "reviewed-operation-acceptance"
_REJECTED = "ledger.transaction.llm_suggestion.rejected"
_CLASSIFIED = "ledger.transaction.classified"
_EXTRA_MISSING = "ERROR_OPTIONAL_EXTRA_MISSING"

_REVIEW_SECONDS = 600
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class _ModelUnpackagedError(Exception):
    """The package refuses local-model work because it was built without the optional ``llm`` extra."""


def _ledger_rows(programs: Programs, environment: Mapping[str, str], profile: Profile) -> list[dict[str, Any]]:
    """Return every ledger row the person's command line lists, read independently of MCP."""
    code, envelope = run_cli(
        programs,
        environment,
        "--profile-secrets-stdin",
        "app",
        "ledger",
        "list",
        secret={"profile_passphrase": profile.password},
    )
    require(code == 0, f"app ledger list: {code} {envelope}")
    rows: list[dict[str, Any]] = []

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("transaction_id"), str):
                rows.append(value)
                return
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(envelope.get("result"))
    return rows


def _history(
    programs: Programs, environment: Mapping[str, str], profile: Profile, transaction_id: str
) -> dict[str, Any]:
    """Return the row's change history as the person's command line reports it."""
    code, envelope = run_cli(
        programs,
        environment,
        "--profile-secrets-stdin",
        "app",
        "ledger",
        "history",
        transaction_id,
        secret={"profile_passphrase": profile.password},
    )
    require(code == 0, f"app ledger history: {code} {envelope}")
    result = envelope.get("result")
    if not isinstance(result, dict):
        raise AcceptanceError(f"app ledger history returned no result: {envelope}")
    return result


def _events(history: Mapping[str, Any]) -> list[dict[str, Any]]:
    events = history.get("events")
    if not isinstance(events, list):
        raise AcceptanceError(f"the row's history lists no events: {history}")
    return [event for event in events if isinstance(event, dict)]


def _one_more_event(before: Mapping[str, Any], after: Mapping[str, Any], event_type: str, step: str) -> None:
    """Require ``after`` to be ``before`` plus exactly one event of ``event_type``."""
    previous, current = _events(before), _events(after)
    require(current[: len(previous)] == previous, f"{step}: earlier history changed")
    added = [event.get("event_type") for event in current[len(previous) :]]
    require(added == [event_type], f"{step}: the history gained {added}, not one {event_type}")


def _row(rows: list[dict[str, Any]], transaction_id: str) -> dict[str, Any]:
    matching = [row for row in rows if row.get("transaction_id") == transaction_id]
    require(len(matching) == 1, f"the command line lists {len(matching)} rows for {transaction_id}")
    return matching[0]


async def _pending_review(session: McpSession, profile: Profile, transaction_id: str) -> tuple[str, dict[str, Any]]:
    """Submit a classification review and return it once the local model's proposal waits for an answer."""
    review_id = await execute(
        session,
        "ledger.classify.review",
        {
            "profile_id": str(profile.profile_id),
            "transaction_id": transaction_id,
            "mode": "classification",
            "origin": "classify_llm_apply",
        },
    )
    deadline = time.monotonic() + _REVIEW_SECONDS
    while True:
        projection = await observe(session, review_id)
        pending = projection.get("pending_interaction") or {}
        if pending.get("disposition") == "review_available":
            break
        if projection.get("failure_error_code") == _EXTRA_MISSING:
            require(projection.get("effect") == "none", f"the refused review wrote: {projection}")
            raise _ModelUnpackagedError
        require(projection.get("terminal_condition") is None, f"the review ended without a decision: {projection}")
        require(time.monotonic() < deadline, "the local model proposed nothing in time")
        await asyncio.sleep(2)
    require(projection.get("effect") == "none", f"something was written before the decision: {projection}")
    is_error, proposal = await session.call("review", {"review": {"reference": pending["review_reference"]}})
    require(not is_error, f"review read refused: {proposal}")
    return review_id, {
        "operation_id": pending["operation_id"],
        "interaction_id": pending["interaction_id"],
        "revision": pending["revision"],
    }


async def _reject_then_apply(
    session: McpSession, programs: Programs, environment: Mapping[str, str], profile: Profile, receipt: Receipt
) -> None:
    added = await settled(
        session,
        await execute(
            session,
            "ledger.add",
            {
                "profile_id": str(profile.profile_id),
                "booked_date": "2026-07-15",
                "amount": "121.00",
                "direction": "OUTGOING",
                "description": "Papeleria y material de oficina",
                "counterparty": "Papeleria Central SL",
            },
        ),
    )
    created = ((added.get("document") or {}).get("projection") or {}).get("transaction") or {}
    transaction_id = created.get("transaction_id")
    if not isinstance(transaction_id, str):
        raise AcceptanceError(f"ledger.add created no row: {added}")
    rows = _ledger_rows(programs, environment, profile)
    before = _row(rows, transaction_id)
    history = _history(programs, environment, profile, transaction_id)
    receipt.record("row_added", rows=len(rows))

    review_id, answer = await _pending_review(session, profile, transaction_id)
    is_error, rejected = await session.call("respond", {"action": "reject", **answer})
    require(not is_error, f"reject refused: {rejected}")
    result = await settled(session, review_id)
    rejected_projection = await observe(session, review_id)
    after_reject = _ledger_rows(programs, environment, profile)
    require(len(after_reject) == len(rows), f"rows changed on reject: {len(rows)} -> {len(after_reject)}")
    require(_row(after_reject, transaction_id) == before, "the rejected review changed the row")
    rejected_history = _history(programs, environment, profile, transaction_id)
    _one_more_event(history, rejected_history, _REJECTED, "reject")
    receipt.record(
        "rejected",
        effect=rejected_projection.get("effect"),
        terminal_condition=rejected_projection.get("terminal_condition"),
        result_outcome=result.get("outcome"),
        row_unchanged=True,
        audit_event=_REJECTED,
    )

    review_id, answer = await _pending_review(session, profile, transaction_id)
    is_error, applied = await session.call("respond", {"action": "apply", **answer})
    require(not is_error, f"apply refused: {applied}")
    result = await settled(session, review_id)
    classified = ((result.get("document") or {}).get("projection") or {}).get("classification") or {}
    stored = classified.get("transaction") or {}
    require(classified.get("outcome") == "classified", f"not classified: {result}")
    require(classified.get("review_status") == "reviewed", f"not reviewed: {result}")
    require(str(stored.get("classified_by", "")).startswith("llm:local-text:"), f"not the local model: {stored}")
    after_apply = _ledger_rows(programs, environment, profile)
    require(len(after_apply) == len(rows), f"rows changed on apply: {len(rows)} -> {len(after_apply)}")
    applied_row = _row(after_apply, transaction_id)
    require(applied_row != before, "the applied review left the row as it was")
    classification = stored.get("business_classification")
    if not isinstance(classification, str) or not classification:
        raise AcceptanceError(f"no classification was stored: {stored}")
    require(classification in json.dumps(applied_row), f"the command line reads another classification: {applied_row}")
    applied_history = _history(programs, environment, profile, transaction_id)
    _one_more_event(rejected_history, applied_history, _CLASSIFIED, "apply")

    is_error, again = await session.call("respond", {"action": "apply", **answer})
    require(is_error, f"a second answer to the settled review was accepted: {again}")
    require(_row(_ledger_rows(programs, environment, profile), transaction_id) == applied_row, "a second apply wrote")
    require(
        _history(programs, environment, profile, transaction_id) == applied_history,
        "a second apply added to the row's history",
    )
    receipt.record(
        "applied_once",
        model=stored.get("classified_by"),
        classification=stored.get("business_classification"),
        review_status=classified.get("review_status"),
        second_answer_refused=True,
        rows=len(after_apply),
    )


async def run(programs: Programs, package: Path | None, scratch: Path, *, models: Path) -> Receipt:
    """Execute the reviewed operation on a fresh root below ``scratch``."""
    receipt = Receipt()
    receipt.record("artifact", **package_identity(package))
    root, secret_store = scratch / "storage", scratch / "secrets"
    secret_store.mkdir(parents=True)
    environment = consumer_environment(root, secret_store)
    profile = create_profile(programs, environment, _PROFILE)

    with caller_owned_runtime(programs, environment, scratch / "runtime-stderr.log") as runtime:
        ready = runtime.ready()
        receipt.record("runtime_ready", product_version=ready.get("product_version"))
        profile = identify_profile(programs, environment, profile)
        state_taxpayer(programs, environment, profile)
        receipt.record("profile_ready")
        with local_model(scratch, models) as available:
            if not available:
                receipt.unproven.append("reviewed operation: no local qwen3:1.7b model in the given store")
            else:
                if profile.profile_id is None:
                    raise AcceptanceError("created profile has no verified identity")
                holder = await AsyncRuntimeSessionHolder.start(
                    programs.runtime,
                    profile_id=profile.profile_id,
                    environment=environment,
                    password=bytearray(profile.password, "utf-8"),
                )
                try:
                    async with mcp_session(programs, environment, scratch) as agent:
                        is_error, content = await ask_and_decide(
                            holder, agent, approve=True, receipt=receipt, step="attended"
                        )
                        require(not is_error, f"the approved connection was refused: {content}")
                        try:
                            await _reject_then_apply(agent, programs, environment, profile, receipt)
                        except _ModelUnpackagedError:
                            receipt.unproven.append(
                                "reviewed operation: the package was built without the optional llm extra"
                            )
                    closed = await holder.command("close")
                    require(closed.get("kind") == "session_closed", "runtime did not acknowledge held-session closure")
                finally:
                    await holder.close()
        stopped = runtime.stop()
        require(stopped == 64, f"runtime exit: {stopped}")
        receipt.record("runtime_stopped", exit_code=stopped)
    survivors = started_processes()
    require(not survivors, f"processes this run started survive it: {survivors}")
    receipt.record("no_surviving_processes")
    return receipt


def main(arguments: list[str] | None = None) -> int:
    """Run the proof; exit 0 when every step held, 1 on a contradicted step, 3 when a step was left out."""
    parser = argparse.ArgumentParser(prog="reviewed-operation", description=__doc__.splitlines()[0])
    parser.add_argument("--package", type=Path, required=True, help="A built package directory.")
    parser.add_argument("--keep", action="store_true", help="Keep the disposable root for inspection.")
    parser.add_argument(
        "--ollama-models",
        type=Path,
        default=None,
        help="An existing Ollama model store to read (default: Cadrumo's own); nothing is pulled or pruned.",
    )
    options = parser.parse_args(arguments)
    package = Path(options.package).resolve(strict=True)
    base = _REPOSITORY_ROOT / "build" / "acceptance"
    base.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="reviewed-operation-", dir=base))
    try:
        receipt = asyncio.run(run(Programs.of(package), package, scratch, models=model_store(options.ollama_models)))
    except (AcceptanceError, BaseExceptionGroup) as failure:
        reason = acceptance_failure(failure)
        if reason is None:
            raise
        print(json.dumps({"step": "failed", "reason": reason, "kept_root": str(scratch)}), flush=True)
        return 1
    if not options.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    if receipt.unproven:
        print(json.dumps({"step": "incomplete", "unproven": receipt.unproven}), flush=True)
        return 3
    print(json.dumps({"step": "passed"}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
