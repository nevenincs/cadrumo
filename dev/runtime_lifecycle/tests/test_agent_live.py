"""The person side of the live agent proof answers only relay tools and believes only what it can check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from ..agent_live import (
    Exchange,
    answer_for,
    is_announced_relay,
    read_document,
    stored_answers_disagree,
    write_whole,
)
from ..caller_owned_root import AcceptanceError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _request(tool: str | None, *kinds: str) -> dict[str, object]:
    return {
        "run_id": "run-1",
        "request_id": "req-1",
        "description": "Run a Cadrumo tool",
        "tool_call": tool,
        "tool_kind": "other",
        "options": [{"option_id": kind, "kind": kind} for kind in kinds],
    }


def test_a_relay_tool_is_allowed_once_with_the_option_the_request_offered() -> None:
    answer = answer_for(_request("execute", "allow_once", "reject_once"))

    assert answer == {"option_id": "allow_once"}


@pytest.mark.parametrize(
    "request_",
    [
        pytest.param(_request("mcp__cadrumo__execute", "allow_once"), id="a-qualified-name-the-lane-never-stores"),
        pytest.param(_request("delete_everything", "allow_once"), id="an-undeclared-relay-tool"),
        pytest.param(_request("run_program", "allow_once"), id="the-agents-own-program-tool"),
        pytest.param(_request("write_file", "allow_once"), id="the-agents-own-file-tool"),
        pytest.param(_request(None, "allow_once"), id="no-tool-named"),
        pytest.param(_request("execute", "reject_once"), id="no-allow-once-offered"),
        pytest.param(_request("execute", "allow_once", "allow_once"), id="two-allow-once-options"),
    ],
)
def test_anything_but_one_relay_tool_offered_once_is_rejected(request_: dict[str, object]) -> None:
    assert answer_for(request_) == {"decision": "reject"}


def test_the_stored_answers_agree_only_when_every_given_answer_was_stored_and_nothing_else() -> None:
    given = {"req-1": {"option_id": "a"}, "req-2": {"decision": "reject"}}
    stored = [
        {"request": {"request_id": "req-1"}, "answer": {"option_id": "a"}},
        {"request": {"request_id": "req-2"}, "answer": {"decision": "reject"}},
    ]

    assert stored_answers_disagree(given, stored) == []
    assert stored_answers_disagree(given, stored[:1]) == ["req-2: given {'decision': 'reject'}, stored None"]
    changed = [stored[0], {"request": {"request_id": "req-2"}, "answer": {"option_id": "b"}}]
    assert stored_answers_disagree(given, changed) == ["req-2: given {'decision': 'reject'}, stored {'option_id': 'b'}"]
    extra = [*stored, {"request": {"request_id": "req-3"}, "answer": {"option_id": "c"}}]
    assert stored_answers_disagree(given, extra) == ["req-3: stored but never given here"]
    assert stored_answers_disagree(given, [{"answer": {"option_id": "a"}}])[0].startswith("a stored permission")


def test_a_document_is_read_whole_absent_or_refused(tmp_path: Path) -> None:
    path = tmp_path / "gateway.json"

    assert read_document(path) is None
    write_whole(path, {"version": 1, "pid": 7})
    assert read_document(path) == {"version": 1, "pid": 7}
    assert not any(member.name.endswith(".partial") for member in tmp_path.iterdir())
    write_whole(path, {"version": 2})
    with pytest.raises(AcceptanceError, match="protocol 2"):
        read_document(path)


def test_each_filed_request_is_answered_once_in_its_own_answer_file(tmp_path: Path) -> None:
    exchange = Exchange(tmp_path)
    write_whole(tmp_path / "requests" / "0001.json", _request("status", "allow_once", "reject_once"))
    write_whole(tmp_path / "requests" / "0002.json", {**_request("run_program", "allow_once"), "request_id": "req-2"})

    rejected = exchange.answer_pending()

    assert read_document(tmp_path / "answers" / "0001.json") == {"option_id": "allow_once"}
    assert read_document(tmp_path / "answers" / "0002.json") == {"decision": "reject"}
    assert rejected == ["'run_program': 'Run a Cadrumo tool'"]
    assert exchange.given == {"req-1": {"option_id": "allow_once"}, "req-2": {"decision": "reject"}}
    (tmp_path / "answers" / "0001.json").unlink()
    assert exchange.answer_pending() == []
    assert not (tmp_path / "answers" / "0001.json").exists()


def test_only_the_relay_program_under_the_announced_gateway_is_attended() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        relay = Path(sys.executable).resolve()
        here = __import__("os").getpid()

        assert is_announced_relay(child.pid, relay, here)
        assert not is_announced_relay(child.pid, relay, None)
        assert not is_announced_relay(child.pid, relay, child.pid)
        assert not is_announced_relay(child.pid, relay.with_name("cadrumo-mcp.exe"), here)
    finally:
        child.kill()
        child.wait(timeout=10)
