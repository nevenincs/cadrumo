"""Every closed sign-in cause and next step the service serves has a sentence the window can show."""

from __future__ import annotations

from typing import get_args

import pytest

from cadrumo_agent_service.providers.application.contracts import CliStateCause, HelperCause, NextStep, ServiceCause
from cadrumo_agent_service.providers.application.next_steps import next_step_for

from ..desktop_interface_keys import DESKTOP_INTERFACE_KEYS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CAUSES = {*get_args(HelperCause), *get_args(ServiceCause), *(cause.value for cause in CliStateCause)}


def test_every_served_cause_and_next_step_has_a_declared_shell_key() -> None:
    declared = {key for key in DESKTOP_INTERFACE_KEYS if key.startswith("desktop.providers.sign_in_cause.")}
    assert declared == {f"desktop.providers.sign_in_cause.{cause}" for cause in _CAUSES}
    steps = {key for key in DESKTOP_INTERFACE_KEYS if key.startswith("desktop.providers.next_step.")}
    assert steps == {f"desktop.providers.next_step.{step.value}" for step in NextStep}
    assert {"desktop.providers.status_unconfirmed", "desktop.providers.console_command_label"} <= DESKTOP_INTERFACE_KEYS


def test_every_cause_declares_a_step() -> None:
    assert {cause: next_step_for(cause) is not None for cause in _CAUSES} == dict.fromkeys(_CAUSES, True)
