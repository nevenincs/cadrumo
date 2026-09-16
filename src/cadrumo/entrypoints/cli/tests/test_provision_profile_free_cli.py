"""``config provision`` provisions the host without a profile session.

Each command runs in a fresh interpreter through the real entrypoint, with an
empty storage root, no active profile and a failing OS keychain, so any path
that opens a session or composes profile persistence fails the test. The
model runtime is a real loopback endpoint.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, cast, override

import pytest

from ....application.provisioning_contracts import ProvisioningPreconditionCondition
from ....core.model_catalogue import ModelRole, default_model_runtime_id
from ....tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from .subprocess_cli import run_cadrumo_subprocess

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TEXT = default_model_runtime_id(ModelRole.TEXT_EXTRACTION)
_VISION = default_model_runtime_id(ModelRole.VISION_TRANSCRIPTION)
_MAPPING = default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)
_NO_KEYCHAIN = {"PYTHON_KEYRING_BACKEND": "keyring.backends.fail.Keyring"}


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
            rows = [{"name": name, "size": 1, "digest": f"sha256:{name}"} for name in sorted(names)]
            write_json_response(self, {"models": rows}, status=HTTPStatus.OK)
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
def _runtime(*, installed: set[str]) -> Generator[str]:
    _Runtime.installed = set(installed)
    _Runtime.residents = set()
    _Runtime.paths = []
    with serving_loopback(_Runtime, path="/api/chat") as chat_url:
        yield chat_url


def _run(tmp_path: Path, chat_url: str, *args: str) -> subprocess.CompletedProcess[str]:
    storage_root = tmp_path / "storage"
    completed = run_cadrumo_subprocess(
        ["--format", "json", "config", "provision", *args],
        settings={
            "cadrumo_local_storage_root": storage_root,
            "cadrumo_output_language": "en",
            "cadrumo_llm_ollama_chat_url": chat_url,
            "cadrumo_llm_ollama_text_model": _TEXT,
            "cadrumo_llm_ollama_vision_model": _VISION,
            "cadrumo_llm_ollama_mapping_model": _MAPPING,
            "cadrumo_llm_contention_safety_margin_bytes": 0,
        },
        extra_env=_NO_KEYCHAIN,
    )
    return completed


def _result(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    envelope = cast(dict[str, object], json.loads(completed.stdout))
    assert envelope["status"] != "error", envelope
    assert envelope["active_profile"] is None, "provisioning must not select or open a profile"
    return cast(dict[str, object], envelope["result"])


@pytest.mark.timeout(180)
def test_status_and_load_run_without_a_profile(tmp_path: Path) -> None:
    with _runtime(installed={_TEXT}) as chat_url:
        status = _run(tmp_path, chat_url, "status")
        loaded = _run(tmp_path, chat_url, "load", "--role", ModelRole.TEXT_EXTRACTION.value)
        residents = set(_Runtime.residents)

    assert status.returncode == 0, status.stderr
    assert cast(dict[str, object], _result(status)["runtime"])["reachable"] is True
    assert loaded.returncode == 0, loaded.stderr
    result = _result(loaded)
    assert result["loaded"] is True
    (item,) = cast(list[dict[str, object]], result["models"])
    assert item["model"] == _TEXT
    assert item["roles"] == [ModelRole.TEXT_EXTRACTION.value]
    assert item["already_loaded"] is False
    assert item["precondition_action"] is None
    assert residents == {_TEXT}


@pytest.mark.timeout(180)
def test_load_of_an_absent_model_exits_2_with_the_resolved_refusal(tmp_path: Path) -> None:
    with _runtime(installed=set()) as chat_url:
        completed = _run(tmp_path, chat_url, "load", "--role", ModelRole.TEXT_EXTRACTION.value)
        paths = list(_Runtime.paths)

    assert completed.returncode == 2, completed.stderr
    (item,) = cast(list[dict[str, object]], _result(completed)["models"])
    assert item["loaded"] is False
    assert item["facts"] == {"model": _TEXT, "model_installed": False}
    action = cast(dict[str, object], item["precondition_action"])
    assert action["failed_condition_id"] == ProvisioningPreconditionCondition.MODEL_INSTALLED.value
    assert paths == [], "an absent model is neither pulled nor loaded"


@pytest.mark.timeout(180)
def test_setup_reports_where_it_stopped_and_exits_2(tmp_path: Path) -> None:
    with _runtime(installed=set()) as chat_url:
        completed = _run(tmp_path, chat_url, "setup")
        paths = list(_Runtime.paths)

    assert completed.returncode == 2, completed.stderr
    result = _result(completed)
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
    assert "/api/generate" not in paths


@pytest.mark.timeout(180)
def test_remove_refusals_keep_their_envelope_and_exit_code(tmp_path: Path) -> None:
    with _runtime(installed={_TEXT}) as chat_url:
        unselected = _run(tmp_path, chat_url, "remove", "--model", "someone-elses:7b")
        unnamed = _run(tmp_path, chat_url, "remove")
        installed = set(_Runtime.installed)

    assert unselected.returncode == 2, unselected.stderr
    result = _result(unselected)
    assert result["removed"] is False
    (item,) = cast(list[dict[str, object]], result["models"])
    assert item["model"] == "someone-elses:7b"
    assert item["freed_bytes"] is None
    action = cast(dict[str, object], item["precondition_action"])
    assert action["failed_condition_id"] == ProvisioningPreconditionCondition.MODEL_SELECTED_BY_CADRUMO.value
    assert unnamed.returncode == 2
    assert "--model/--role" in unnamed.stdout + unnamed.stderr
    assert installed == {_TEXT}


@pytest.mark.timeout(180)
def test_install_without_confirm_never_runs_the_installer(tmp_path: Path) -> None:
    with _runtime(installed=set()) as chat_url:
        completed = _run(tmp_path, chat_url, "install")

    result = _result(completed)
    assert result["consented"] is False
    assert result["installer_exit_code"] is None
    if result["installed"] is True:
        # This host already has the runtime; the verb reports it and runs nothing.
        assert completed.returncode == 0
        assert result["already_installed"] is True
    else:
        assert completed.returncode == 2
        action = cast(dict[str, object], result["precondition_action"])
        assert action["failed_condition_id"] in {
            ProvisioningPreconditionCondition.RUNTIME_INSTALL_CONSENTED.value,
            ProvisioningPreconditionCondition.RUNTIME_INSTALLER_AVAILABLE.value,
        }
