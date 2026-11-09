"""``aeat config provider-login`` - sign in to an AI provider by hand from a console.

The desktop application signs in to a provider inside its own isolated provider
home. When that fails, this verb runs the bundled agent's own login against the
same home with the operator's terminal, and the application finds the sign-in
on its next status read. The agent's exit status ends the command: it is zero
only when the provider reports signed in.

The agent root and launch live in the agent service's own module, which this
package never imports; the verb starts it as a child process and passes the
terminal through unchanged. Nothing the provider prints is captured or logged.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Final

import typer

from cadrumo_client.commands import profile_selection
from cadrumo_client.commands.errors import CliRefusedBoundaryError
from cadrumo_client.commands.output import activate_subcommand_output_language

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....core.output_rendering import OutputFormat
from ..common import emit_envelope, format_of

_HELPER_MODULE: Final = "cadrumo_agent_service.adapters.provider_login"
_PROVIDERS: Final = ("claude", "codex", "antigravity")
_DEVICE_PROVIDERS: Final = ("codex",)


def helper_command(profile_id: str, provider: str, *, device: bool) -> list[str]:
    """Return the child command that runs the service's sign-in door for one profile and provider."""
    return [
        sys.executable,
        "-m",
        _HELPER_MODULE,
        "--profile-id",
        profile_id,
        "--provider",
        provider,
        *(("--device",) if device else ()),
    ]


def run_helper(command: list[str]) -> int:
    """Run the command on the caller's terminal, capturing nothing, and return its exit status."""
    return subprocess.run(command, check=False).returncode


def _profile_id(profile: str | None) -> str:
    if profile is not None and profile.strip():
        return profile_selection.require_runtime_login_target(profile).bucket_id
    selected = profile_selection.command_profile_id()
    if selected is None:
        raise CliRefusedBoundaryError(translated_message="cli.config.provider_login.no_profile")
    return selected


def config_provider_login(
    ctx: typer.Context,
    provider: str,
    device: bool = False,
    profile: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Hand the terminal to the bundled agent's own sign-in for one provider."""
    activate_subcommand_output_language(ctx, output_language)
    if format_of(ctx) is OutputFormat.JSON:
        raise CliRefusedBoundaryError(translated_message="cli.config.provider_login.json_unsupported")
    if provider not in _PROVIDERS:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.provider_login.unsupported_provider",
            context={"provider": provider, "supported": ", ".join(_PROVIDERS)},
        )
    if device and provider not in _DEVICE_PROVIDERS:
        raise CliRefusedBoundaryError(
            translated_message="cli.config.provider_login.device_unsupported",
            context={"supported": ", ".join(_DEVICE_PROVIDERS)},
        )
    status = run_helper(helper_command(_profile_id(profile), provider, device=device))
    if status != 0:
        raise typer.Exit(status)
    from cadrumo_client.commands.payloads import ConfigProviderLoginResult

    emit_envelope(
        ctx,
        command="config.provider_login",
        result=ConfigProviderLoginResult(provider=provider, device=device, signed_in=True),
        lines=(tr("cli.config.provider_login.signed_in", provider=provider),),
    )


__all__ = ["config_provider_login", "helper_command", "run_helper"]
