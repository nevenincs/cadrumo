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
from cadrumo.entrypoints.cli.tests.cli_runner import ClickInvokeKwargs

from .. import runner as sequence_runner

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


@pytest.mark.parametrize(
    ("args", "proof_expected"),
    [
        (("--format", "json", "app", "runtime", "status"), False),
        (("app", "runtime", "start"), False),
        (("--format=json", "config", "profile", "view"), True),
        (("--profile", "docs-sequence-sandbox", "config", "profile", "view"), True),
        (("config", "profile", "view", "--help"), False),
        (("not-a-command",), False),
        (("--profile-secrets-stdin", "config", "profile", "view"), False),
        (("--profile-auth-method", "password", "config", "profile", "view"), False),
        (("--profile-secrets-fd=9", "config", "profile", "view"), False),
        (("config", "profile", "resume", "--secrets-stdin"), False),
    ],
)
def test_frame_authentication_uses_real_command_metadata_and_preserves_authored_channels(
    monkeypatch: pytest.MonkeyPatch, args: tuple[str, ...], proof_expected: bool
) -> None:
    """Only a declared private invocation receives the fixture-owned proof."""
    calls: list[tuple[tuple[str, ...], str | bytes | None]] = []

    def invoke(arguments: Sequence[str], **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
        calls.append((tuple(arguments), kwargs.get("input")))
        return CliRunner().invoke(click.Command("invocation-port"))

    monkeypatch.setattr(sequence_runner, "invoke_cached_cli", invoke)
    with override_settings(cadrumo_dev_test_database_password=SecretStr("docs-frame-proof")):
        sequence_runner._invoke_authenticated_frame(args)
    assert len(calls) == 1
    actual_args, supplied = calls[0]
    if proof_expected:
        assert actual_args == ("--profile-secrets-stdin", *args)
        assert supplied is not None
        assert json.loads(supplied) == {"profile_passphrase": "docs-frame-proof"}
    else:
        assert actual_args == args
        assert supplied is None
