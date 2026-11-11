"""The window is relayed the selected local engine's lane as the runtime manager serves it."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from ...admin import AdminRequest
from ...local_ai_relay import LocalAiFacts, LocalAiModel, LocalAiServer, relay_local_ai
from ...providers.domain.record import LocalEngine

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HELD = "synthetic-held:1"
_ABSENT = "synthetic-absent:1"
_UNLISTED = "synthetic-unlisted:1"


def _health(*, read: bool) -> dict[str, Any]:
    engine = (
        {"engine": "llamacpp", "state": "running", "reason": None, "door": None}
        if read
        else {"engine": "llamacpp", "state": "not_running", "reason": "not_reachable", "door": "local_ai_setup"}
    )
    return {
        "configured": "available",
        "transport": "available" if read else "unavailable",
        "authentication": "not_applicable",
        "catalog": "available",
        "admission": "unproven",
        "selectable": read,
        "reasons": [] if read else ["the router did not answer"],
        "engine": engine,
    }


def _lane(provider: str, *, read: bool, installed: bool | None = False) -> dict[str, Any]:
    models = [
        {"model": name, **({} if installed is None else {"installed": installed})}
        for name in (_HELD, _ABSENT, _UNLISTED)
    ]
    return {"provider_id": provider, "transport": "api", "health": _health(read=read), "catalog": {"models": models}}


def _hosted() -> dict[str, Any]:
    return {"provider_id": "example", "transport": "api", "health": {"selectable": True}, "catalog": {"models": []}}


def _facts(server: LocalAiServer, engine: LocalEngine = LocalEngine.LLAMACPP) -> LocalAiFacts:
    return LocalAiFacts(
        engine=engine,
        server=server,
        models=(LocalAiModel(name=_HELD, stored=True), LocalAiModel(name=_ABSENT, stored=False)),
    )


def _held(lane: dict[str, Any]) -> dict[str, object]:
    return {model["model"]: model.get("installed", "unknown") for model in lane["catalog"]["models"]}


def _relay(document: dict[str, Any], facts: LocalAiFacts | None) -> dict[str, Any]:
    return cast(dict[str, Any], relay_local_ai(document, facts))


def _relayed(lane: dict[str, Any], facts: LocalAiFacts | None) -> dict[str, Any]:
    document = _relay({"providers": [lane, _hosted()]}, facts)
    assert document["providers"][1] == _hosted()
    return document["providers"][0]


def test_a_sleeping_server_is_a_ready_lane_holding_what_its_files_hold() -> None:
    lane = _relayed(_lane("llamacpp", read=False), _facts(LocalAiServer.DORMANT))

    assert lane["health"]["transport"] == "available"
    assert lane["health"]["selectable"] is True
    assert lane["health"]["engine"] is None
    assert lane["health"]["reasons"] == []
    assert _held(lane) == {_HELD: True, _ABSENT: False, _UNLISTED: "unknown"}


def test_a_running_server_the_agent_read_keeps_its_answer_where_no_file_says_otherwise() -> None:
    read = _lane("llamacpp", read=True, installed=True)

    lane = _relayed(read, _facts(LocalAiServer.RUNNING))

    assert lane["health"] == read["health"]
    assert _held(lane) == {_HELD: True, _ABSENT: False, _UNLISTED: True}


def test_a_running_server_the_agent_did_not_reach_is_still_a_ready_lane() -> None:
    lane = _relayed(_lane("llamacpp", read=False), _facts(LocalAiServer.RUNNING))

    assert lane["health"]["selectable"] is True
    assert lane["health"]["engine"] is None


def test_a_failed_demand_leaves_the_lane_not_running_with_its_door() -> None:
    unread = _lane("llamacpp", read=False)

    lane = _relayed(unread, _facts(LocalAiServer.START_FAILED))

    assert lane["health"] == unread["health"]
    assert lane["health"]["engine"]["state"] == "not_running"
    assert _held(lane) == {_HELD: True, _ABSENT: False, _UNLISTED: "unknown"}


def test_without_the_managers_row_an_unread_server_is_unknown_not_down() -> None:
    lane = _relayed(_lane("llamacpp", read=False), None)

    assert lane["health"]["transport"] == "unknown"
    assert lane["health"]["selectable"] is False
    assert lane["health"]["engine"] is None
    assert lane["health"]["reasons"] == []
    assert _held(lane) == {_HELD: "unknown", _ABSENT: "unknown", _UNLISTED: "unknown"}


def test_without_the_managers_row_a_server_the_agent_read_is_relayed_as_read() -> None:
    read = _lane("llamacpp", read=True, installed=True)

    assert _relayed(read, None) == read


def test_facts_of_the_other_engine_leave_a_lane_as_the_agent_served_it() -> None:
    unread = _lane("ollama", read=False)

    assert _relayed(unread, _facts(LocalAiServer.DORMANT)) == unread


def test_a_declared_catalogue_and_a_refusal_are_relayed_through() -> None:
    declared = {"kind": "declared", "catalog": {"providers": [_lane("llamacpp", read=False)]}}

    relayed = _relay(declared, _facts(LocalAiServer.DORMANT))

    assert relayed["kind"] == "declared"
    assert relayed["catalog"]["providers"][0]["health"]["selectable"] is True
    refusal = {"kind": "refused", "code": "service_stopping"}
    assert _relay(refusal, None) == refusal


def test_the_facts_are_closed_and_bounded() -> None:
    document = {"engine": "llamacpp", "server": "dormant", "models": [{"name": _HELD, "stored": True}]}

    assert LocalAiFacts.model_validate_json(_json(document)).models == (LocalAiModel(name=_HELD, stored=True),)
    for refused in (
        document | {"server": "starting"},
        document | {"extra": 1},
        document | {"models": [{"name": _HELD, "stored": True}] * 33},
        document | {"models": [{"name": "", "stored": True}]},
    ):
        with pytest.raises(ValueError, match="validation error"):
            LocalAiFacts.model_validate_json(_json(refused))


def _json(value: object) -> str:
    return json.dumps(value)


def test_a_catalogue_request_carries_the_facts_and_nothing_else() -> None:
    request = {"version": 1, "request_id": "00000000-0000-4000-8000-000000000001", "action": "catalog"}
    facts = {"engine": "ollama", "server": "start_failed", "models": []}

    carried = AdminRequest.model_validate_json(_json(request | {"local_ai": facts}))

    assert carried.local_ai == LocalAiFacts(engine=LocalEngine.OLLAMA, server=LocalAiServer.START_FAILED)
    assert AdminRequest.model_validate_json(_json(request)).local_ai is None
    with pytest.raises(ValueError, match="validation error"):
        AdminRequest.model_validate_json(_json(request | {"local_ai": facts | {"door": "local_ai_setup"}}))
