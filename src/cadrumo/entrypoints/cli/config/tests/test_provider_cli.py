"""``aeat config provider``: live registration, refusals and the masked output every command prints.

The commands take a provider id as text and keep no list of providers: which
ids exist is what cadrumo-agent declares, which the worker reads from the
agent itself. The native cases run the real runtime and profile worker against
a stand-in agent image that declares invented lanes, and drive the commands
the way the person and the desktop do: status first, then each change guarded
by the revision status reported, with the key on its protected channel.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Iterator
from contextlib import suppress
from pathlib import Path
from types import SimpleNamespace
from typing import Final
from uuid import UUID

import pytest
import typer
from click.testing import Result
from typer.core import TyperCommand

from .....adapters.local_runtime.agent_programs import PACKAGE_AGENT_VARIABLE
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from .....application.operations.registry import OperationFrontendProjection
from .....application.provider_settings.contracts import ProviderSettingsRefusalCode
from .....application.provider_settings.tests.synthetic_catalog import (
    DEFAULTED_KEY_LANE,
    KEY_LANE,
    MISSING_LANE,
    SIGN_IN_ONLY_LANE,
    synthetic_catalog,
)
from .....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from .....core.config import override_settings
from .....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from .....core.i18n.render import tr
from .....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....runtime.tests.agent_host_support import stand_in_agent_image
from ...command_parameter_contracts import ArgumentSpec
from ...command_shared_contracts import TEXT_VALUE
from ...command_specs import COMMAND_GRAPH
from ...errors import CliRefusedBoundaryError
from ...tests.cli_runner import invoke_cached_cli, invoke_unbound_cli, semantic_cli_output
from ...tests.profile_password_cli import invoke_with_profile_password
from ...tests.runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from ..command_specs import CONFIG_COMMAND_SPECS

pytestmark = [pytest.mark.hex_entrypoint]

_COMMANDS: Final = ("status", "set", "remove", "reset")
_CHANGES: Final = ("set", "remove", "reset")
_SYNTHETIC_KEY: Final = "sk-synthetic-provider-key-0000000000000000"
"""An invented key in a provider key's form; no provider issued it."""


def _leaf(name: str) -> str:
    return f"config_provider_{name}"


# -- registration --------------------------------------------------------------------------------


@pytest.mark.unit
def test_every_provider_command_is_a_live_leaf_of_the_config_family() -> None:
    keys = {spec.key for spec in CONFIG_COMMAND_SPECS}
    assert {"config_provider", *(_leaf(name) for name in _COMMANDS)} <= keys
    for name in _COMMANDS:
        resolved = COMMAND_GRAPH.resolve_invocation(["config", "provider", name])
        assert resolved is not None and resolved.key == _leaf(name)
        assert COMMAND_GRAPH.node(resolved.key).path == ("aeat", "config", "provider", name)


@pytest.mark.unit
def test_a_change_names_its_provider_as_free_text_and_only_set_takes_a_secret_off_the_command_line() -> None:
    for name in _CHANGES:
        spec = COMMAND_GRAPH.spec(_leaf(name))
        arguments = [parameter for parameter in spec.parameters if isinstance(parameter, ArgumentSpec)]
        # The provider is text the agent's declaration settles, never a choice list kept here.
        assert [(argument.name, argument.value) for argument in arguments] == [("provider_id", TEXT_VALUE)]
        assert "expected_revision" in {parameter.name for parameter in spec.parameters}
        assert (spec.machine_secret is not None) is (name == "set")
    assert COMMAND_GRAPH.spec(_leaf("status")).machine_secret is None


@pytest.mark.unit
@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_help_of_every_provider_command_is_worded_in_each_language(language: str) -> None:
    with override_settings(cadrumo_output_language=language):
        for name in ("", *_COMMANDS):
            command = ["config", "provider", *([name] if name else []), "--help"]
            result = invoke_cached_cli(["--language", language, *command])
            assert result.exit_code == 0, semantic_cli_output(result)
            assert "cli.config.provider." not in result.output
            key = f"cli.config.provider.{name}_help" if name else "cli.config.provider.help"
            first_words = tr(key).split()[0]
            assert first_words in result.output, (language, name)


# -- refusals before the runtime is asked -----------------------------------------------------------


@pytest.fixture
def _no_profile(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path), override_settings(cadrumo_output_language="en"):
        yield


def _refusal(result: Result) -> tuple[str, str]:
    """Return the refusal reason a JSON-mode command printed, and its words."""
    assert result.exit_code != 0, semantic_cli_output(result)
    for line in result.stderr.splitlines():
        if line.strip().startswith("{"):
            error = json.loads(line)["error"]
            context = error["context"] or {}
            return str(context.get("reason")), str(error["message"])
    raise AssertionError(f"no JSON error document: {result.stderr[:400]!r}")


@pytest.mark.unit
@pytest.mark.usefixtures("_no_profile")
@pytest.mark.parametrize("name", _COMMANDS)
def test_with_no_profile_signed_in_every_command_refuses_and_reads_no_key(name: str) -> None:
    command = ["config", "provider", name]
    if name != "status":
        command += [KEY_LANE, "--expected-revision", ABSENT_SECURE_OBJECT_REVISION_ID]
    if name == "set":
        command.append("--secrets-stdin")
    result = invoke_cached_cli(
        ["--format", "json", *command], input=json.dumps({"secret": _SYNTHETIC_KEY}) if name == "set" else None
    )
    reason, message = _refusal(result)
    # Either the command line's own storage gate refuses a profile-bound command on a root with no
    # profile, or the provider bridge finds no profile pointer; both send the person to sign in.
    assert (reason, message) in {
        ("None", tr("cli.config.errors.no_active_profile")),
        (ProviderSettingsRefusalCode.NOT_SIGNED_IN.value, tr("cli.config.provider.refused.not_signed_in")),
    }, (reason, message)
    assert _SYNTHETIC_KEY not in result.output


@pytest.mark.unit
@pytest.mark.parametrize("name", _COMMANDS)
def test_with_no_runtime_every_command_refuses_with_the_closed_runtime_unavailable_code(
    name: str, tmp_path: Path
) -> None:
    command = ["config", "provider", name]
    if name != "status":
        command += [KEY_LANE, "--expected-revision", ABSENT_SECURE_OBJECT_REVISION_ID]
    if name == "set":
        command.append("--secrets-stdin")
    with isolated_runtime_profile(tmp_path=tmp_path), override_settings(cadrumo_output_language="en"):
        result = invoke_unbound_cli(
            ["--format", "json", *command], input=json.dumps({"secret": _SYNTHETIC_KEY}) if name == "set" else None
        )
    reason, _message = _refusal(result)
    # The desktop reads this reason from the provider-settings refusal set.
    assert reason == ProviderSettingsRefusalCode.RUNTIME_UNAVAILABLE.value, result.stderr[-400:]
    assert _SYNTHETIC_KEY not in result.output


@pytest.mark.unit
@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_refusal_code_has_its_own_words_in_each_language(language: str) -> None:
    with override_settings(cadrumo_output_language=language):
        worded = {code: tr(f"cli.config.provider.refused.{code.value}") for code in ProviderSettingsRefusalCode}
    assert all(not text.startswith("cli.config.provider.") for text in worded.values()), worded
    assert len(set(worded.values())) == len(worded)


# -- through the runtime ---------------------------------------------------------------------------


@pytest.fixture
def _provider_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[NativeCliProfileFixture]:
    """One registered profile whose runtime relays a stand-in agent image to its worker."""
    image, _record = stand_in_agent_image(tmp_path / "agent")
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(image))
    with (
        native_cli_profile_scope(tmp_path / "profile") as profile,
        override_settings(cadrumo_output_language="en"),
    ):
        profile.register(
            label="native-provider-settings",
            facts={"identity.name": "Synthetic", "identity.surnames": "Provider Settings"},
        )
        yield profile


def _run(profile: NativeCliProfileFixture, *command: str, key: str | None = None) -> Result:
    """Run one provider command as the person, the key on its own descriptor when one is given.

    The person's password goes on standard input, as an operator without a saved sign-in sends it,
    so the key travels on a separate protected channel.
    """
    assert profile.label is not None
    arguments = ["--language", "en", "--format", "json", "config", "provider", *command]
    if key is None:
        return invoke_with_profile_password(arguments, label=profile.label)
    reader, writer = os.pipe()
    os.write(writer, json.dumps({"secret": key}).encode())
    os.close(writer)
    try:
        return invoke_with_profile_password([*arguments, "--secrets-fd", str(reader)], label=profile.label)
    finally:
        # The command closes the descriptor it read; close it here only if it did not.
        with suppress(OSError):
            os.close(reader)


def _result(result: Result) -> dict[str, object]:
    assert result.exit_code == 0, semantic_cli_output(result)
    document = json.loads(result.stdout)
    payload = document["result"]
    assert isinstance(payload, dict)
    return {str(key): value for key, value in payload.items()}


def _providers(status: dict[str, object]) -> list[dict[str, object]]:
    providers = status["providers"]
    assert isinstance(providers, list)
    return [item for item in providers if isinstance(item, dict)]


def _entry(status: dict[str, object], lane: str) -> dict[str, object]:
    (entry,) = [item for item in _providers(status) if item["id"] == lane]
    return entry


@pytest.mark.integration
@pytest.mark.windows_only
@pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers")
@pytest.mark.usefixtures("authority_operation")
def test_status_and_every_change_print_the_masked_contract_through_the_runtime(
    _provider_profile: NativeCliProfileFixture,
) -> None:
    profile = _provider_profile
    first = _result(_run(profile, "status"))

    # Every lane the agent declares, in its order, and nothing Cadrumo holds a list of.
    assert [item["id"] for item in _providers(first)] == list(synthetic_catalog().provider_ids)
    assert isinstance(first["development"], bool)
    unset = _entry(first, KEY_LANE)
    assert unset["mode"] == "unset" and unset["source"] in {"none", "environment"}
    assert unset["revision"] == ABSENT_SECURE_OBJECT_REVISION_ID

    stored = _run(profile, "set", KEY_LANE, "--expected-revision", str(unset["revision"]), key=_SYNTHETIC_KEY)
    entry = _result(stored)
    assert _SYNTHETIC_KEY not in stored.output
    assert entry["id"] == KEY_LANE
    assert (entry["mode"], entry["source"], entry["readiness"]) == ("key", "profile", "not_verified")
    assert re.fullmatch(r"[0-9a-f]{64}", str(entry["revision"]))
    assert entry["revision"] != unset["revision"]
    assert entry == _entry(_result(_run(profile, "status")), KEY_LANE)

    # A base URL cannot be stored and cleared at once; the command refuses before it reads a key.
    both = _run(
        profile,
        "set",
        KEY_LANE,
        "--expected-revision",
        str(entry["revision"]),
        "--base-url",
        "https://endpoint.example.invalid",
        "--clear-base-url",
        key=_SYNTHETIC_KEY,
    )
    assert _refusal(both) == (
        ProviderSettingsRefusalCode.BASE_URL_REJECTED.value,
        tr("cli.config.provider.refused.base_url_rejected"),
    )

    # The revision a change sends must be the one the last read reported.
    stale = _run(profile, "remove", KEY_LANE, "--expected-revision", str(unset["revision"]))
    assert _refusal(stale) == (
        ProviderSettingsRefusalCode.REVISION_CONFLICT.value,
        tr("cli.config.provider.refused.revision_conflict"),
    )

    removed = _result(_run(profile, "remove", KEY_LANE, "--expected-revision", str(entry["revision"])))
    assert (removed["mode"], removed["readiness"], removed["available"]) == ("disabled", "disabled", False)
    reset = _result(_run(profile, "reset", KEY_LANE, "--expected-revision", str(removed["revision"])))
    assert reset["mode"] == "unset" and reset["revision"] == ABSENT_SECURE_OBJECT_REVISION_ID

    # An id the agent does not declare, and a lane that takes no key, are refused without a write.
    for lane in (MISSING_LANE, SIGN_IN_ONLY_LANE):
        refused = _run(
            profile, "set", lane, "--expected-revision", ABSENT_SECURE_OBJECT_REVISION_ID, key=_SYNTHETIC_KEY
        )
        assert _refusal(refused)[0] == ProviderSettingsRefusalCode.UNKNOWN.value
        assert _SYNTHETIC_KEY not in refused.output
    unchanged = _result(_run(profile, "status"))
    assert _entry(unchanged, DEFAULTED_KEY_LANE)["mode"] == "unset"
    assert _SYNTHETIC_KEY not in json.dumps(unchanged)


# -- the bridge's refusal mapping -------------------------------------------------------------------


class _RefusingClient:
    """A bound runtime client whose first exchange is refused, before any operation is taken."""

    profile_id = UUID("3a7c9e1f-5b2d-4c8e-9f60-1d2e3f4a5b6c")
    session_id = UUID("11111111-1111-4111-8111-111111111111")
    frontend = OperationFrontendProjection.CLI

    def __init__(self, error: Exception) -> None:
        self._error = error

    def contract(self, definition_id: str, *, deadline: float) -> object:
        del definition_id, deadline
        raise self._error


def _bridge_refusal(monkeypatch: pytest.MonkeyPatch, error: Exception) -> tuple[object, object]:
    from .. import runtime_provider_settings as bridge

    client = _RefusingClient(error)
    monkeypatch.setattr(bridge, "resolve_active_profile_pointer", lambda: SimpleNamespace(bucket_id=client.profile_id))
    monkeypatch.setattr(bridge, "require_profile_client", lambda _ctx, *, expected_profile_id: client)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        bridge.read_status(typer.Context(TyperCommand("status")))
    context = refused.value.context or {}
    return context.get("reason"), context.get("operation_id")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (RuntimeRefusalCode.UNAVAILABLE, ProviderSettingsRefusalCode.RUNTIME_UNAVAILABLE),
        (RuntimeRefusalCode.ENDPOINT_NOT_READY, ProviderSettingsRefusalCode.RUNTIME_UNAVAILABLE),
        (RuntimeRefusalCode.OWNER_BUSY, ProviderSettingsRefusalCode.RUNTIME_UNAVAILABLE),
        (RuntimeRefusalCode.DRAINING, ProviderSettingsRefusalCode.RUNTIME_UNAVAILABLE),
        # A closed connection or a missed deadline may follow a change the runtime already took.
        (RuntimeRefusalCode.CONNECTION_CLOSED, ProviderSettingsRefusalCode.UNKNOWN),
        (RuntimeRefusalCode.DEADLINE_EXCEEDED, ProviderSettingsRefusalCode.UNKNOWN),
    ],
)
def test_a_runtime_that_took_nothing_is_refused_as_unavailable_and_anything_else_as_unknown(
    code: RuntimeRefusalCode, expected: ProviderSettingsRefusalCode, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _bridge_refusal(monkeypatch, RuntimeRefusalError(code)) == (expected.value, None)


@pytest.mark.unit
def test_an_operation_the_runtime_took_is_never_reported_as_an_unavailable_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation = "a" * 64
    taken = CliRefusedBoundaryError(
        translated_message="cli.config.provider.refused.unknown",
        context={"reason": RuntimeRefusalCode.UNAVAILABLE.value, "operation_id": operation},
    )
    assert _bridge_refusal(monkeypatch, taken) == (ProviderSettingsRefusalCode.UNKNOWN.value, operation)
    untaken = CliRefusedBoundaryError(
        translated_message="cli.config.provider.refused.unknown",
        context={"reason": RuntimeRefusalCode.UNAVAILABLE.value},
    )
    assert _bridge_refusal(monkeypatch, untaken) == (ProviderSettingsRefusalCode.RUNTIME_UNAVAILABLE.value, None)
