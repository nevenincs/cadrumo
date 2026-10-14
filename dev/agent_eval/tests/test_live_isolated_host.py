"""The live lane hands packaged processes only allow-listed variables, and reads a refused credential store right.

These are the pure parts of the isolated host. The environment builder must
drop every variable outside its list, however the host spells it; a sign-in
the credential store could not keep must be ``unavailable``, never a pass and
never an ordinary failure; and teardown must refuse a path that is not a run
root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from ..live.isolated_host import (
    CREDENTIAL_STORE_UNAVAILABLE,
    CliResult,
    RunDirectory,
    allowlisted_environment,
    classify_sign_in,
    host_values_outside_allowlist,
    new_run_directory,
    remove_run_directory,
)
from ..live.outcome import UnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AMBIENT = {
    "SystemRoot": "C:\\Windows",
    "USERPROFILE": "C:\\Users\\someone",
    "MODEL_PROVIDER_CREDENTIAL": "planted-model-credential-value",
    "HOST_MESSAGING_HANDLE": "planted-host-handle-value",
    "CADRUMO_LOCAL_STORAGE_ROOT": "C:\\the\\operator\\real\\storage",
    "PYTHONPATH": "C:\\elsewhere",
    "Path": "C:\\tools;C:\\Windows",
}


def test_only_allow_listed_variables_reach_a_packaged_process() -> None:
    environment = allowlisted_environment(_AMBIENT)
    assert environment["SYSTEMROOT"] == "C:\\Windows"
    assert environment["USERPROFILE"] == "C:\\Users\\someone"
    for planted in ("planted-model-credential-value", "planted-host-handle-value", "C:\\the\\operator\\real\\storage"):
        assert planted not in environment.values()
    assert "C:\\tools" not in environment["PATH"]


def test_every_value_outside_the_list_is_handed_to_the_scrubber() -> None:
    outside = dict(host_values_outside_allowlist(_AMBIENT))
    assert outside["MODEL_PROVIDER_CREDENTIAL"] == "planted-model-credential-value"
    assert outside["HOST_MESSAGING_HANDLE"] == "planted-host-handle-value"
    assert "USERPROFILE" not in outside


def _result(document: dict[str, Any], returncode: int = 0) -> CliResult:
    return CliResult(arguments=("config", "login"), returncode=returncode, document=document)


@pytest.mark.parametrize(
    "document",
    [
        {"status": "error", "error": {"code": "AUTH_STORAGE_KEYRING_UNAVAILABLE"}},
        {"status": "error", "error": {"code": "AUTHENTICATION_REQUIRED", "context": {"reason": "keyring_unavailable"}}},
        {"status": "success", "result": {"session_persisted": False}},
    ],
)
def test_a_sign_in_the_credential_store_cannot_keep_is_unavailable(document: dict[str, Any]) -> None:
    with pytest.raises(UnavailableError) as raised:
        classify_sign_in(_result(document, returncode=0 if document["status"] == "success" else 1))
    assert raised.value.reason == CREDENTIAL_STORE_UNAVAILABLE


_ABSENT_CHANNEL_ACTION = {
    "action": {"action_id": "operator.profile.login", "cli_path": ["config", "login"]},
    "failed_condition_id": "profile.human.input_channel_available",
    "evidence": [{"values": {"password_channel_available": False}}],
}


@pytest.mark.parametrize(
    "document",
    [
        {
            "status": "error",
            "error": {"code": "REFUSED_CLI_BOUNDARY", "context": None, "action": _ABSENT_CHANNEL_ACTION},
        },
        {"status": "error", "error": {"code": "REFUSED", "context": {"keychain": "logon_without_credentials"}}},
        {
            "status": "warning",
            "result": {"session_persisted": False},
            "notices": [
                {"code": "config.login.session_not_persisted", "context": {"keychain": "logon_without_credentials"}}
            ],
        },
    ],
)
def test_the_products_current_answers_for_a_logon_without_a_keychain_are_unavailable(
    document: dict[str, Any],
) -> None:
    with pytest.raises(UnavailableError) as raised:
        classify_sign_in(_result(document, returncode=0 if document["status"] != "error" else 1))
    assert raised.value.reason == CREDENTIAL_STORE_UNAVAILABLE


@pytest.mark.parametrize(
    "document",
    [
        {"status": "error", "error": {"code": "REFUSED", "context": {"reason": "runtime_deadline_exceeded"}}},
        {"status": "error", "error": {"code": "REFUSED_CLI_BOUNDARY", "context": None, "action": None}},
        {
            "status": "error",
            "error": {"code": "REFUSED_CLI_BOUNDARY", "action": {"failed_condition_id": "profile.exists"}},
        },
        {"status": "error", "error": {"code": "REFUSED", "context": {"keychain": "something_else"}}},
    ],
)
def test_other_refusals_are_failures_not_unavailable(document: dict[str, Any]) -> None:
    with pytest.raises(RuntimeError, match="sign-in refused"):
        classify_sign_in(_result(document, returncode=1))


def test_a_wrong_password_is_a_failure_not_unavailable() -> None:
    refused = {"status": "error", "error": {"code": "AUTH", "context": {"reason": "credential_rejected"}}}
    with pytest.raises(RuntimeError, match="credential_rejected"):
        classify_sign_in(_result(refused, returncode=1))


def test_a_kept_sign_in_passes_classification() -> None:
    classify_sign_in(_result({"status": "success", "result": {"session_persisted": True}}))


def test_teardown_removes_only_a_run_directory(tmp_path: Path) -> None:
    base = tmp_path / "runs"
    run = new_run_directory(base)
    (run.root / "file").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not a run directory"):
        remove_run_directory(RunDirectory(tmp_path), base)
    remove_run_directory(run, base)
    assert not run.path.exists()
