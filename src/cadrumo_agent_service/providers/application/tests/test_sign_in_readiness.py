"""Choosing provider-owned authentication does not establish remote readiness."""

from __future__ import annotations

import json
from typing import get_args

import pytest

from ...domain.record import ProviderSettingsRecord
from ..contracts import (
    CliState,
    CliStateCause,
    HelperCause,
    NextStep,
    ProviderReadiness,
    ProviderStatusReason,
    ServiceCause,
)
from ..next_steps import CONSOLE_SIGN_IN_COMMAND, next_step_for
from ..ports import AbsentProviderRecord, StoredProviderRecord, UnreadableProviderRecord
from ..resolution import status_entry
from .synthetic_catalog import synthetic_catalog

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("state", ["absent", "selected", "unreadable"])
@pytest.mark.parametrize("cli_state", list(CliState))
def test_cli_sign_in_status_distinguishes_selection_from_missing_and_unusable(state: str, cli_state: CliState) -> None:
    lane = synthetic_catalog().entry("example_cli")
    assert lane is not None
    if state == "selected":
        record = ProviderSettingsRecord.model_validate_json(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": "example",
                    "assistant_auth": "provider_sign_in",
                    "credential_state": "unset",
                    "generation": "a" * 64,
                    "updated_at": "2026-10-18T00:00:00Z",
                }
            )
        )
        read = StoredProviderRecord(record=record, revision="b" * 64)
    elif state == "absent":
        read = AbsentProviderRecord(provider="example")
    else:
        read = UnreadableProviderRecord(provider="example", revision=None)
    status = status_entry(lane, read, cli_state=cli_state)
    if state != "unreadable" and cli_state is CliState.INSTALLED_SIGNED_IN:
        assert status.readiness is ProviderReadiness.NOT_VERIFIED
        assert status.reason is None
        assert status.available
    elif state != "unreadable":
        assert not status.available
        assert status.readiness is ProviderReadiness.SIGN_IN_REQUIRED
        assert status.reason is ProviderStatusReason.SIGN_IN_WITH_PROVIDER_TOOL
    else:
        assert status.readiness is ProviderReadiness.UNUSABLE
        assert not status.available


_NEXT_STEPS = {
    "cli_not_found": "install_cli",
    "home_in_git_project": "move_profile_outside_git",
    "login_already_running": "close_other_sign_in",
    "cli_protocol_mismatch": "update_app",
    "helper_output_invalid": "update_app",
    "probe_timed_out": "console_sign_in",
    "status_not_confirmed": "console_sign_in",
    "cli_exited_early": "console_sign_in",
    "cli_reported_error": "console_sign_in",
    "login_not_completed": "console_sign_in",
    "internal_error": "console_sign_in",
    "helper_start_failed": "console_sign_in",
    "helper_ended_without_result": "console_sign_in",
    "helper_exit_nonzero": "console_sign_in",
    "host_disconnected": "retry",
    "timed_out": "retry",
}


@pytest.mark.parametrize(("cause", "step"), sorted(_NEXT_STEPS.items()))
def test_each_failure_cause_maps_to_one_closed_next_step(cause: str, step: str) -> None:
    assert next_step_for(cause) is NextStep(step)


@pytest.mark.parametrize("cause", [None, "invented"])
def test_no_cause_or_an_unknown_word_names_no_next_step(cause: str | None) -> None:
    assert next_step_for(cause) is None


@pytest.mark.parametrize(
    "cause",
    sorted({*get_args(HelperCause), *get_args(ServiceCause), *(word.value for word in CliStateCause)}),
)
def test_every_closed_failure_cause_tells_the_person_what_to_do_next(cause: str) -> None:
    assert next_step_for(cause) is not None


def _selected() -> StoredProviderRecord:
    record = ProviderSettingsRecord.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "provider": "example",
                "assistant_auth": "provider_sign_in",
                "credential_state": "unset",
                "generation": "a" * 64,
                "updated_at": "2026-10-18T00:00:00Z",
            }
        )
    )
    return StoredProviderRecord(record=record, revision="b" * 64)


@pytest.mark.parametrize("cause", [cause for cause in CliStateCause if next_step_for(cause.value) is not None])
def test_a_row_serves_the_probe_cause_and_the_step_it_maps_to(cause: CliStateCause) -> None:
    lane = synthetic_catalog().entry("example_cli")
    assert lane is not None
    status = status_entry(lane, _selected(), cli_state=CliState.UNKNOWN, cli_state_cause=cause)
    assert status.cli_state_cause is cause
    assert status.next_step is next_step_for(cause.value)
    dumped = status.model_dump(mode="json")
    assert dumped["cli_state_cause"] == cause.value
    assert status.next_step is not None
    assert dumped["next_step"] == status.next_step.value


def test_a_row_without_a_cause_serves_neither_word() -> None:
    lane = synthetic_catalog().entry("example_cli")
    assert lane is not None
    dumped = status_entry(lane, _selected(), cli_state=CliState.INSTALLED_SIGNED_OUT).model_dump(mode="json")
    assert dumped["cli_state_cause"] is None
    assert dumped["next_step"] is None


def test_the_console_command_is_value_free_words_with_a_provider_slot() -> None:
    assert CONSOLE_SIGN_IN_COMMAND == "cadrumo-agent-service provider-login --provider {provider}"
