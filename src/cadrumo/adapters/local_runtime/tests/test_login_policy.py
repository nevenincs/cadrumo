"""Development admission relaxes only OS session policy, by explicit runtime opt-in."""

from __future__ import annotations

from threading import Event
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest

from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)
from cadrumo.application.runtime.login import RuntimeLoginInventory
from cadrumo.application.user_profile.access_contracts import Availability, LoginEligibility
from cadrumo.core.config import Settings, override_settings

from ..login import capture_runtime_login
from ..login_policy import compose_runtime_login_policy

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _channel(owner: str) -> RuntimeByteChannel:
    # This unit port represents an already OS-verified channel. Native transport
    # and frontend authentication are exercised by the runtime integration tests.
    return cast(RuntimeByteChannel, SimpleNamespace(peer=RuntimePeer(os_owner_id=owner, process_id=123)))


def _native_inventory() -> RuntimeLoginInventory:
    raise AssertionError("development policy must not consult the native desktop")


@pytest.mark.parametrize("value", ["", "0", "true", "yes", "on", " 1", "1 ", "2"])
def test_every_value_except_literal_one_retains_native_policy(value: str) -> None:
    with override_settings(cadrumo_dev_runtime_session_override=value):
        policy = compose_runtime_login_policy(
            os_owner_id="synthetic-owner", runtime_boot_id=uuid4(), stop=Event(), native_inventory=_native_inventory
        )
    assert policy.capture is capture_runtime_login
    assert policy.inventory is _native_inventory


def test_core_setting_is_strict_when_unset_and_environment_enables_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE", raising=False)
    assert not Settings().dev_runtime_session_override_enabled
    monkeypatch.setenv("CADRUMO_DEV_RUNTIME_SESSION_OVERRIDE", "1")
    assert Settings().dev_runtime_session_override_enabled


def test_development_policy_preserves_owner_and_credential_facility_and_retires_on_stop() -> None:
    stop = Event()
    with override_settings(cadrumo_dev_runtime_session_override="1"):
        policy = compose_runtime_login_policy(
            os_owner_id="synthetic-owner", runtime_boot_id=uuid4(), stop=stop, native_inventory=_native_inventory
        )
    first = policy.capture(_channel("synthetic-owner"))
    assert policy.capture(_channel("synthetic-owner")).login_id == first.login_id
    assert policy.inventory is not None
    assert policy.inventory().logins == (first,)
    for facilities in Availability:
        observation = first.observe(credential_facilities=facilities)
        assert observation.active and not observation.locked
        assert observation.unattended is LoginEligibility.ELIGIBLE
        assert observation.credential_facilities is facilities
    with pytest.raises(RuntimeRefusalError) as refused:
        policy.capture(_channel("another-owner"))
    assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
    stop.set()
    assert not first.observe(credential_facilities=Availability.UNAVAILABLE).active
    assert policy.inventory().logins == ()
    with pytest.raises(RuntimeRefusalError) as draining:
        policy.capture(_channel("synthetic-owner"))
    assert draining.value.reason is RuntimeRefusalCode.DRAINING


def test_restarting_runtime_changes_development_login_identity() -> None:
    with override_settings(cadrumo_dev_runtime_session_override="1"):
        policies = [
            compose_runtime_login_policy(
                os_owner_id="synthetic-owner", runtime_boot_id=uuid4(), stop=Event(), native_inventory=None
            )
            for _ in range(2)
        ]
    assert (
        policies[0].capture(_channel("synthetic-owner")).login_id
        != policies[1].capture(_channel("synthetic-owner")).login_id
    )
