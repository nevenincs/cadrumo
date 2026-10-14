"""Pure command-metadata selection of documentation authentication input."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Unpack

import click
import pytest
from click.testing import CliRunner, Result
from pydantic import SecretStr

from cadrumo.core.config import override_settings
from cadrumo.tests.cli_fixture_ports import ClickInvokeKwargs
from cadrumo_runtime.commands.tests.config import runtime_cli

from .. import runner as sequence_runner
from ..schema import CommandProgram

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize(
    ("program", "args", "proof_field"),
    [
        (CommandProgram.AEAT, ("--format", "json", "app", "runtime", "status"), None),
        (CommandProgram.AEAT, ("app", "runtime", "start"), None),
        (CommandProgram.AEAT, ("--format=json", "config", "profile", "view"), "profile_passphrase"),
        (
            CommandProgram.AEAT,
            ("--profile", "docs-sequence-sandbox", "config", "profile", "view"),
            "profile_passphrase",
        ),
        (CommandProgram.AEAT, ("config", "profile", "view", "--help"), None),
        (CommandProgram.AEAT, ("not-a-command",), None),
        (CommandProgram.AEAT, ("--profile-secrets-stdin", "config", "profile", "view"), None),
        (CommandProgram.AEAT, ("--profile-auth-method", "password", "config", "profile", "view"), None),
        (CommandProgram.AEAT, ("--profile-secrets-fd=9", "config", "profile", "view"), None),
        (CommandProgram.AUTHENTICATION, ("config", "profile", "resume", "--secrets-stdin"), None),
        (CommandProgram.AEAT, ("config", "login", "docs-sequence-replacement"), "passphrase"),
        (CommandProgram.AEAT, ("config", "login", "missing-profile"), "passphrase"),
        (CommandProgram.AEAT, ("config", "login", "--help"), None),
        (CommandProgram.AEAT, ("config", "login", "docs-sequence-replacement", "--secrets-stdin"), None),
        (CommandProgram.AEAT, ("config", "login", "docs-sequence-replacement", "--secrets-fd=9"), None),
    ],
)
def test_frame_authentication_uses_real_command_metadata_and_preserves_authored_channels(
    monkeypatch: pytest.MonkeyPatch, program: CommandProgram, args: tuple[str, ...], proof_field: str | None
) -> None:
    """Only a declared private invocation receives the fixture-owned proof."""
    calls: list[tuple[tuple[str, ...], str | bytes | None]] = []

    def invoke(arguments: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        calls.append((tuple(arguments), kwargs.get("input")))
        return CliRunner().invoke(click.Command("invocation-port"))

    if program is CommandProgram.AUTHENTICATION:
        monkeypatch.setattr(runtime_cli, "invoke_runtime_cli", invoke)
    else:
        monkeypatch.setattr(sequence_runner, "invoke_cached_cli", invoke)
    with override_settings(cadrumo_dev_test_database_password=SecretStr("docs-frame-proof")):
        sequence_runner._invoke_authenticated_frame(args, program=program)
    assert len(calls) == 1
    actual_args, supplied = calls[0]
    if proof_field is not None:
        expected_args = (
            (*args, "--secrets-stdin") if proof_field == "passphrase" else ("--profile-secrets-stdin", *args)
        )
        assert actual_args == expected_args
        assert supplied is not None
        assert json.loads(supplied) == {proof_field: "docs-frame-proof"}
    else:
        assert actual_args == args
        assert supplied is None
