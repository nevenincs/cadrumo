"""The window is relayed the selected local engine's lane as the runtime manager serves it."""

from __future__ import annotations

import json
from typing import Any, cast

import pytest

from ...admin import AdminRequest
from ...local_ai_relay import LocalAiFacts, LocalAiModel, LocalAiServer, ServedLocalAi, relay_local_ai
from ...providers.application.served_catalog import catalog_nonconformance
from ...providers.application.tests.served_catalog_documents import declared_catalog, served_catalog
from ...providers.domain.record import LocalEngine

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_HELD = "synthetic-held:1"
_ABSENT = "synthetic-absent:1"
_UNLISTED = "synthetic-unlisted:1"
_VERSION_UNREAD = "binary_version_unavailable"
"""The refusal the agent serves for a lane whose server it could not ask its version."""
_UNREAD_SERVER_REASONS = ("provider transport is unavailable", "the router did not answer")
"""Reasons the agent words for a server it could not reach."""


def _health(*, read: bool, refusals: tuple[str, ...] = (_VERSION_UNREAD,)) -> dict[str, Any]:
    """A lane's health as the agent serves it; a sleeping server's version is unread, so the lane is not admitted."""
    if read:
        return {
            "configured": "available",
            "transport": "available",
            "authentication": "not_applicable",
            "catalog": "available",
            "admission": "unproven",
            "selectable": True,
            "reasons": [],
            "engine": {"engine": "llamacpp", "state": "running", "reason": None, "door": None},
        }
    return {
        "configured": "available",
        "transport": "unavailable",
        "authentication": "not_applicable",
        "catalog": "available",
        "admission": "not_admitted",
        "selectable": False,
        "reasons": [*_UNREAD_SERVER_REASONS, *refusals],
        "engine": {"engine": "llamacpp", "state": "not_running", "reason": "not_reachable", "door": "local_ai_setup"},
    }


def _lane(
    provider: str,
    *,
    read: bool,
    installed: bool | None = False,
    refusals: tuple[str, ...] = (_VERSION_UNREAD,),
) -> dict[str, Any]:
    models = [
        {"model": name, **({} if installed is None else {"installed": installed})}
        for name in (_HELD, _ABSENT, _UNLISTED)
    ]
    health = _health(read=read, refusals=refusals)
    return {"provider_id": provider, "transport": "api", "health": health, "catalog": {"models": models}}


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
    assert lane["health"]["admission"] == "unproven"
    assert lane["health"]["selectable"] is True
    assert lane["health"]["engine"] is None
    assert lane["health"]["reasons"] == []
    assert _held(lane) == {_HELD: True, _ABSENT: False, _UNLISTED: "unknown"}


@pytest.mark.parametrize("server", [LocalAiServer.DORMANT, LocalAiServer.RUNNING])
@pytest.mark.parametrize(
    "refusal",
    [
        "binary_out_of_proof_range",
        "provider lane llamacpp/api has no exact completed-turn proof; evidence from another execution mode is not inherited",
    ],
    ids=["refused-version", "refused-proof"],
)
def test_a_refusal_beside_the_unread_version_keeps_the_lane_not_admitted_with_its_reasons(
    server: LocalAiServer, refusal: str
) -> None:
    lane = _relayed(_lane("llamacpp", read=False, refusals=(_VERSION_UNREAD, refusal)), _facts(server))

    assert lane["health"]["admission"] == "not_admitted"
    assert lane["health"]["selectable"] is False
    assert lane["health"]["reasons"] == [_VERSION_UNREAD, refusal]
    assert lane["health"]["transport"] == "available"


def test_a_server_the_agent_read_whose_version_it_could_not_is_lifted_too() -> None:
    read = _lane("llamacpp", read=True, installed=True)
    read["health"] |= {"admission": "not_admitted", "selectable": False, "reasons": [_VERSION_UNREAD]}

    lane = _relayed(read, _facts(LocalAiServer.RUNNING))

    assert (lane["health"]["admission"], lane["health"]["selectable"], lane["health"]["reasons"]) == (
        "unproven",
        True,
        [],
    )


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
    assert lane["health"]["admission"] == "not_admitted"
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


def _declared_with_local_engines() -> dict[str, Any]:
    """The catalogue the agent declares before it runs, with both local engines' lanes beside a hosted one."""
    declared = declared_catalog()
    catalog = cast(dict[str, Any], declared["catalog"])
    hosted = catalog["providers"][0]
    local = [
        {
            **hosted,
            "id": f"{engine.value}_api",
            "provider": engine.value,
            "auth_kind": "none",
            "model_download": "required",
        }
        for engine in LocalEngine
    ]
    return {**declared, "catalog": {**catalog, "providers": [hosted, *local]}}


_EVERY_FACT: tuple[LocalAiFacts | None, ...] = (
    None,
    *(_facts(server, engine) for engine in LocalEngine for server in LocalAiServer),
)


@pytest.mark.parametrize("facts", _EVERY_FACT)
def test_a_declared_catalogue_is_relayed_as_the_agent_declared_it(facts: LocalAiFacts | None) -> None:
    declared = _declared_with_local_engines()

    assert catalog_nonconformance(declared) is None
    assert _relay(declared, facts) == declared


@pytest.mark.parametrize("facts", _EVERY_FACT)
def test_every_relayed_lane_conforms_to_the_served_catalogue(facts: LocalAiFacts | None) -> None:
    for document in (served_catalog(), _declared_with_local_engines()):
        assert catalog_nonconformance(_relay(document, facts)) is None


def test_a_refusal_is_relayed_through() -> None:
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


def test_the_kept_facts_describe_every_later_read_and_a_read_without_facts_keeps_them() -> None:
    served = ServedLocalAi()
    document = {"providers": [_lane("llamacpp", read=False), _hosted()]}
    read = served.over(lambda: document)

    unrelayed = cast(dict[str, Any], read())
    assert unrelayed["providers"][0]["health"]["transport"] == "unknown"

    served.keep(_facts(LocalAiServer.DORMANT))
    served.keep(None)

    assert served.facts() == _facts(LocalAiServer.DORMANT)
    relayed = cast(dict[str, Any], read())
    assert relayed["providers"][0]["health"]["selectable"] is True
    assert _held(relayed["providers"][0]) == {_HELD: True, _ABSENT: False, _UNLISTED: "unknown"}
    assert document["providers"][0] == _lane("llamacpp", read=False)
    assert served.over(lambda: None)() is None
