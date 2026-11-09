"""The closed next step a person is offered for each failure cause."""

from __future__ import annotations

from typing import Final

from .contracts import NextStep

CONSOLE_SIGN_IN_COMMAND: Final = "cadrumo-agent-service provider-login --provider {provider}"
"""The console command that signs a provider in, as value-free words; ``{provider}`` is for the frontend to fill."""

_STEPS: Final[dict[str, NextStep]] = {
    "cli_not_found": NextStep.INSTALL_CLI,
    "home_in_git_project": NextStep.MOVE_PROFILE_OUTSIDE_GIT,
    "login_already_running": NextStep.CLOSE_OTHER_SIGN_IN,
    "cli_protocol_mismatch": NextStep.UPDATE_APP,
    "helper_output_invalid": NextStep.UPDATE_APP,
    "probe_timed_out": NextStep.CONSOLE_SIGN_IN,
    "status_not_confirmed": NextStep.CONSOLE_SIGN_IN,
    "cli_exited_early": NextStep.CONSOLE_SIGN_IN,
    "cli_reported_error": NextStep.CONSOLE_SIGN_IN,
    "login_not_completed": NextStep.CONSOLE_SIGN_IN,
    "internal_error": NextStep.CONSOLE_SIGN_IN,
    "helper_start_failed": NextStep.CONSOLE_SIGN_IN,
    "helper_ended_without_result": NextStep.CONSOLE_SIGN_IN,
    "helper_exit_nonzero": NextStep.CONSOLE_SIGN_IN,
    "cli_start_failed": NextStep.CONSOLE_SIGN_IN,
    "probe_start_failed": NextStep.CONSOLE_SIGN_IN,
    "host_disconnected": NextStep.RETRY,
    "timed_out": NextStep.RETRY,
    "home_unavailable": NextStep.RETRY,
    "agent_stop_failed": NextStep.RETRY,
    "cleanup_unconfirmed": NextStep.RETRY,
    "probe_cleanup_unconfirmed": NextStep.RETRY,
    "status_read_failed": NextStep.RETRY,
    "status_context_unavailable": NextStep.RETRY,
    "profile_missing": NextStep.UPDATE_APP,
    "unsupported_method": NextStep.UPDATE_APP,
    "host_input_invalid": NextStep.UPDATE_APP,
    "browser_relay_unavailable": NextStep.UPDATE_APP,
    "probe_output_unreadable": NextStep.UPDATE_APP,
    "status_unreadable": NextStep.UPDATE_APP,
}


def next_step_for(cause: str | None) -> NextStep | None:
    """Return the step for ``cause``; every closed cause word declares one."""
    return None if cause is None else _STEPS.get(cause)
