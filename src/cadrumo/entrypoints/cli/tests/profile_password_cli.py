"""Admit a test profile's CLI commands the way an operator without a saved sign-in is admitted."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Unpack, cast

from click.testing import Result

from ....application.operator_surface.command_ports import ProfileAuthenticationPosture
from ....core.config import load_settings
from .._profile_authentication_contract import profile_authentication_posture
from ..command_specs import COMMAND_GRAPH
from .cli_runner import ClickInvokeKwargs, invoke_unbound_cli

__all__ = ["invoke_with_profile_password"]


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
    if any(
        token.startswith(("--profile-secrets-", "--profile-credential-ref", "--profile-auth-method"))
        for token in arguments
    ):
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
