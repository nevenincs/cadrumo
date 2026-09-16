"""``config provision load|setup`` run the supervised operation and project its result unchanged.

The command handlers compose the production operation platform inside an
isolated profile; the model runtime is a real loopback endpoint.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, cast, override

import pytest
import typer
import typer.main

from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.config import override_settings
from ....core.model_catalogue import ModelRole, default_model_runtime_id
from ....tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from ..config.provision_cli import provision_load, provision_setup

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)


class _Runtime(SilentLoopbackHandler):
    installed: ClassVar[set[str]] = set()
    residents: ClassVar[set[str]] = set()
    paths: ClassVar[list[str]] = []

    @override
    def do_GET(self) -> None:
        if self.path == "/api/version":
            write_json_response(self, {"version": "0.9.0"}, status=HTTPStatus.OK)
        elif self.path in {"/api/tags", "/api/ps"}:
            names = self.installed if self.path == "/api/tags" else self.residents
            write_json_response(self, {"models": [{"name": n, "size": 1} for n in sorted(names)]}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    @override
    def do_POST(self) -> None:
        body = read_json_body(self)
        type(self).paths.append(self.path)
        if self.path == "/api/generate" and "prompt" not in body:
            self.residents.add(str(body.get("model")))
            write_json_response(self, {"done": True}, status=HTTPStatus.OK)
        elif self.path == "/api/pull":
            write_json_response(self, {"error": "registry unavailable"}, status=HTTPStatus.OK)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)


@contextmanager
def _runtime(tmp_path: Path, *, installed: set[str]) -> Generator[None]:
    _Runtime.installed = set(installed)
    _Runtime.residents = set()
    _Runtime.paths = []
    with (
        isolated_runtime_profile(tmp_path=tmp_path),
        serving_loopback(_Runtime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url,
            cadrumo_llm_ollama_text_model=_TEXT,
            cadrumo_llm_contention_safety_margin_bytes=0,
            cadrumo_output_language="en",
        ),
    ):
        yield


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None: ...

    return typer.Context(typer.main.get_command(app), obj={"format": "json"})


def _envelope(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    return cast(dict[str, object], json.loads(capsys.readouterr().out))


@pytest.mark.timeout(120)
def test_load_emits_the_loaded_model_through_the_operation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with _runtime(tmp_path, installed={_TEXT}):
        provision_load(_context(), role=ModelRole.TEXT_EXTRACTION)
        residents = set(_Runtime.residents)

    envelope = _envelope(capsys)
    result = cast(dict[str, object], envelope["result"])
    assert envelope["command"] == "config.provision.load"
    assert result["loaded"] is True
    (item,) = cast(list[dict[str, object]], result["models"])
    assert item["model"] == _TEXT
    assert item["roles"] == [ModelRole.TEXT_EXTRACTION.value]
    assert item["already_loaded"] is False
    assert item["precondition_action"] is None
    assert residents == {_TEXT}


@pytest.mark.timeout(120)
def test_load_of_an_absent_model_exits_2_with_the_resolved_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with _runtime(tmp_path, installed=set()), pytest.raises(typer.Exit) as raised:
        provision_load(_context(), role=ModelRole.TEXT_EXTRACTION)

    assert raised.value.exit_code == 2
    result = cast(dict[str, object], _envelope(capsys)["result"])
    (item,) = cast(list[dict[str, object]], result["models"])
    assert item["loaded"] is False
    assert item["facts"] == {"model": _TEXT, "model_installed": False}
    action = cast(dict[str, object], item["precondition_action"])
    assert action["failed_condition_id"] == ProvisioningPreconditionCondition.MODEL_INSTALLED.value
    assert "/api/pull" not in _Runtime.paths


@pytest.mark.timeout(180)
def test_setup_reports_where_it_stopped_and_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    with _runtime(tmp_path, installed=set()), pytest.raises(typer.Exit) as raised:
        provision_setup(_context())

    assert raised.value.exit_code == 2
    envelope = _envelope(capsys)
    result = cast(dict[str, object], envelope["result"])
    assert envelope["command"] == "config.provision.setup"
    assert result["succeeded"] is False
    assert result["stopped_step"] == "pull"
    assert result["install_consented"] is False
    steps = {step["step"]: step["state"] for step in cast(list[dict[str, object]], result["steps"])}
    assert steps == {
        "install": "unchanged",
        "start": "unchanged",
        "pull": "failed",
        "load": "not_reached",
        "verify": "not_reached",
    }
    assert "/api/generate" not in _Runtime.paths
