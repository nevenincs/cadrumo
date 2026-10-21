"""Owning contract probes extracted from native integration scenarios."""

from __future__ import annotations

import pytest
import typer
from typer.core import TyperCommand

from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.entrypoints.cli._profile_session_gate import _interactive_authentication
from cadrumo_client.commands.secure_input import terminal_can_prompt_for_secrets

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    "refusal",
    [reason for reason in ProfileSessionRefusalReason if reason is not ProfileSessionRefusalReason.KEYRING_UNAVAILABLE],
)
def test_a_resumable_host_never_prompts_a_parsed_invocation(refusal: ProfileSessionRefusalReason) -> None:
    context = typer.Context(TyperCommand("probe"))
    assert _interactive_authentication(context, bucket_id="unused", refusal=refusal) is False


def test_a_keychainless_refusal_without_a_console_does_not_prompt() -> None:
    assert terminal_can_prompt_for_secrets() is False, "the test process must not own a console"
    context = typer.Context(TyperCommand("probe"))
    refusal = ProfileSessionRefusalReason.KEYRING_UNAVAILABLE
    assert _interactive_authentication(context, bucket_id="unused", refusal=refusal) is False
