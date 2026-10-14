"""The person side of the live agent proof approves each request once and believes only what it can check."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
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
from ..proof_support import ProcessIdentity

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _request(tool: str | None, *kinds: str, server: str | None = "cadrumo") -> dict[str, object]:
    return {
        "run_id": "run-1",
        "request_id": "req-1",
        "description": "Run a Cadrumo tool",
        "tool_call": tool,
        "tool_server": server,
        "tool_kind": "other",
        "options": [{"option_id": kind, "kind": kind} for kind in kinds],
    }


def test_the_single_allow_once_option_the_request_offered_is_chosen() -> None:
    assert answer_for(_request("execute", "allow_once", "reject_once")) == {"option_id": "allow_once"}
    with_session = answer_for(_request("execute", "allow_once", "allow_session", "reject_once"))
    assert with_session == {"option_id": "allow_once"}
    assert answer_for(_request("execute", "reject_once", "allow_once", "allow_session")) == {"option_id": "allow_once"}


@pytest.mark.parametrize(
    "request_",
    [
        pytest.param(_request("execute", "allow_once", server=None), id="no-tool-server"),
        pytest.param(_request("execute", "allow_once", server="other"), id="another-tool-server"),
        pytest.param(_request("run_program", "allow_once", server=None), id="an-agents-own-tool"),
        pytest.param(_request(None, "allow_once"), id="no-tool-named"),
    ],
)
def test_any_request_is_approved_once_when_an_allow_once_option_is_offered(request_: dict[str, object]) -> None:
    assert answer_for(request_) == {"option_id": "allow_once"}


@pytest.mark.parametrize(
    "request_",
    [
        pytest.param(_request("execute"), id="no-options"),
        pytest.param(_request("execute", "reject_once"), id="no-allow-once-offered"),
        pytest.param(_request("execute", "allow_session", "reject_once"), id="only-a-session-allow-offered"),
        pytest.param(_request("execute", "allow_once", "allow_once"), id="two-allow-once-options"),
    ],
)
def test_a_request_without_a_single_allow_once_option_is_rejected(request_: dict[str, object]) -> None:
    assert answer_for(request_) == {"decision": "reject"}


def _entry(request_id: str, answer: dict[str, str], action: str, option_id: str | None) -> dict[str, object]:
    return {
        "number": 1,
        "request": {"request_id": request_id, "tool_call": "execute"},
        "stored": {"tool_name": "execute", "action": action, "option_id": option_id},
        "answer": answer,
    }


def test_the_stored_answers_agree_only_when_every_given_answer_was_relayed_and_stored_and_nothing_else() -> None:
    given = {"req-1": {"option_id": "allow_once"}, "req-2": {"decision": "reject"}}
    stored = [
        _entry("req-1", {"option_id": "allow_once"}, "approved", "allow_once"),
        _entry("req-2", {"decision": "reject"}, "rejected", "reject_once"),
    ]

    assert stored_answers_disagree(given, stored) == []
    assert stored_answers_disagree(given, stored[:1]) == [
        "req-2: given {'decision': 'reject'}, relayed None, stored None"
    ]
    relayed_otherwise = [stored[0], _entry("req-2", {"option_id": "allow_once"}, "rejected", "reject_once")]
    assert stored_answers_disagree(given, relayed_otherwise) == [
        "req-2: given {'decision': 'reject'}, relayed {'option_id': 'allow_once'}, stored {'decision': 'reject'}"
    ]
    stored_otherwise = [_entry("req-1", {"option_id": "allow_once"}, "rejected", "reject_once"), stored[1]]
    assert stored_answers_disagree(given, stored_otherwise) == [
        "req-1: given {'option_id': 'allow_once'}, relayed {'option_id': 'allow_once'}, stored {'decision': 'reject'}"
    ]
    extra = [*stored, _entry("req-3", {"option_id": "allow_once"}, "approved", "allow_once")]
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
    own_tool = {**_request("run_program", "allow_once", server=None), "request_id": "req-2"}
    write_whole(tmp_path / "requests" / "0002.json", own_tool)
    unanswerable = {**_request("write_file", "reject_once"), "request_id": "req-3"}
    write_whole(tmp_path / "requests" / "0003.json", unanswerable)

    rejected = exchange.answer_pending()

    assert read_document(tmp_path / "answers" / "0001.json") == {"option_id": "allow_once"}
    assert read_document(tmp_path / "answers" / "0002.json") == {"option_id": "allow_once"}
    assert read_document(tmp_path / "answers" / "0003.json") == {"decision": "reject"}
    assert rejected == ["'write_file': 'Run a Cadrumo tool'"]
    assert exchange.given == {
        "req-1": {"option_id": "allow_once"},
        "req-2": {"option_id": "allow_once"},
        "req-3": {"decision": "reject"},
    }
    (tmp_path / "answers" / "0001.json").unlink()
    assert exchange.answer_pending() == []
    assert not (tmp_path / "answers" / "0001.json").exists()


def test_only_the_relay_program_under_the_announced_gateway_is_attended() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        relay = Path(sys.executable).resolve()
        here = ProcessIdentity.capture(os.getpid())
        stale_child = replace(ProcessIdentity.capture(child.pid), birth=0.0)

        assert is_announced_relay(child.pid, relay, here)
        assert not is_announced_relay(child.pid, relay, None)
        assert not is_announced_relay(child.pid, relay, stale_child)
        assert not is_announced_relay(child.pid, relay.with_name("cadrumo-mcp.exe"), here)
    finally:
        child.kill()
        child.wait(timeout=10)
