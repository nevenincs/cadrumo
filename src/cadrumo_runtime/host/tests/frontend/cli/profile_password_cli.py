"""Admit a test profile's CLI commands the way an operator without a saved sign-in is admitted."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Unpack, cast

from click.testing import Result

from cadrumo.core.config import load_settings
from cadrumo.entrypoints.cli._profile_authentication_contract import profile_authentication_posture
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.tests.cli_fixture_ports import ClickInvokeKwargs
from cadrumo_client.contracts.command_ports import ProfileAuthenticationPosture

from .cli_runner import invoke_unbound_cli

__all__ = [
    "chooses_own_credential_source",
    "invoke_with_profile_password",
    "refused_for_want_of_an_operator",
]


#: What a command prints when it was refused, with no effect, because no
#: runtime was reachable or no sign-in or password channel admitted it.
_OPERATOR_REFUSAL_MARKERS = ("runtime_unavailable", "operator.profile.login", "profile.human.input_channel_available")


def refused_for_want_of_an_operator(result: Result) -> bool:
    """Return whether a command was refused before any effect for want of a runtime or a sign-in."""
    return result.exit_code != 0 and any(marker in result.output for marker in _OPERATOR_REFUSAL_MARKERS)


def chooses_own_credential_source(args: Sequence[str]) -> bool:
    """Return whether an invocation already names how its profile is authenticated."""
    return any(
        token.startswith(("--profile-secrets-", "--profile-credential-ref", "--profile-auth-method")) for token in args
    )


def invoke_with_profile_password(args: Sequence[str], *, label: str, **kwargs: Unpack[ClickInvokeKwargs]) -> Result:
    """Send the profile password on the secret frame to each verb that would resume a sign-in.

    Commands the runtime admits with a resumed sign-in also accept the password
    on the protected stdin frame, which is what an operator on a host without a
    saved sign-in supplies. Commands that take no profile authentication, and
    invocations that already choose their own credential source, run unchanged.
    """
    arguments = list(args)
    spec = COMMAND_GRAPH.resolve_invocation(arguments)
    if (
        spec is None
        or profile_authentication_posture(COMMAND_GRAPH.node(spec.key))
        is not ProfileAuthenticationPosture.RESUME_FALLBACK
    ):
        return invoke_unbound_cli(arguments, **kwargs)
    if chooses_own_credential_source(arguments):
        return invoke_unbound_cli(arguments, **kwargs)
    if "input" in kwargs and kwargs["input"] is not None:
        raise AssertionError("the profile password will not overwrite explicit stdin; select its secret channel")
    passphrase = load_settings().cadrumo_dev_test_database_password.get_secret_value()
    if "--profile" not in arguments:
        arguments[:0] = ["--profile", label]
    arguments[:0] = ["--profile-secrets-stdin"]
    invocation = cast(ClickInvokeKwargs, dict(kwargs))
    invocation["input"] = json.dumps({"profile_passphrase": passphrase})
    result = invoke_unbound_cli(arguments, **invocation)
    assert passphrase not in result.output
    return result
