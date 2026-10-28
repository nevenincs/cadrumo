"""Every host refusal reaches the desktop as one code of the launcher protocol's closed set."""

from __future__ import annotations

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError

from ..controller import AgentHostError, AgentHostRefusal
from ..launcher_protocol import AgentLauncherRefusal, launcher_refusal_for, runtime_launcher_refusal_for
from ..native_refusal import NativeLaunchRefusal, NativeLaunchRefusalCode

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_EXPECTED = {
    AgentHostRefusal.SIGNED_OUT: AgentLauncherRefusal.SIGNED_OUT,
    AgentHostRefusal.STALE_GENERATION: AgentLauncherRefusal.SIGNED_OUT,
    AgentHostRefusal.CREDENTIALS_UNAVAILABLE: AgentLauncherRefusal.PROVIDER_CREDENTIAL_MISSING,
    AgentHostRefusal.CREDENTIALS_INVALID: AgentLauncherRefusal.PROVIDER_CREDENTIAL_MISSING,
    AgentHostRefusal.LAUNCH_FAILED: AgentLauncherRefusal.SERVICE_FAILED,
    AgentHostRefusal.LAUNCH_PROFILE_REFUSED: AgentLauncherRefusal.SERVICE_FAILED,
    AgentHostRefusal.CANCELLED: AgentLauncherRefusal.SERVICE_FAILED,
    AgentHostRefusal.EMERGENCY_CUTOFF: AgentLauncherRefusal.EMERGENCY_CUTOFF,
    AgentHostRefusal.NOT_READY: AgentLauncherRefusal.SERVICE_FAILED,
    AgentHostRefusal.AGENT_REFUSED: AgentLauncherRefusal.SERVICE_FAILED,
    AgentHostRefusal.ALREADY_RUNNING: AgentLauncherRefusal.SERVICE_FAILED,
    AgentHostRefusal.AGENT_INCOMPATIBLE: AgentLauncherRefusal.SERVICE_INCOMPATIBLE,
    AgentHostRefusal.STORES_NEWER: AgentLauncherRefusal.SERVICE_INCOMPATIBLE,
    AgentHostRefusal.STORES_UNPREPARED: AgentLauncherRefusal.SERVICE_FAILED,
}


def test_the_expectation_names_every_host_refusal() -> None:
    assert set(_EXPECTED) == set(AgentHostRefusal)


@pytest.mark.parametrize("reason", list(AgentHostRefusal))
def test_each_host_refusal_maps_to_its_launcher_code(reason: AgentHostRefusal) -> None:
    assert launcher_refusal_for(AgentHostError(reason)) is _EXPECTED[reason]


@pytest.mark.parametrize(
    "native",
    [
        pytest.param(
            NativeLaunchRefusal(code=NativeLaunchRefusalCode.LAUNCH_VALUE_MISSING, subject="SLOT"), id="stated"
        ),
        pytest.param(NativeLaunchRefusal(code=None, subject=None), id="unreadable"),
    ],
)
def test_a_native_launch_profile_refusal_ends_the_launch_as_a_service_failure(native: NativeLaunchRefusal) -> None:
    error = AgentHostError(AgentHostRefusal.LAUNCH_PROFILE_REFUSED, native_refusal=native)
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_FAILED
    assert error.native_refusal == native


def test_the_launcher_protocol_stays_the_desktops_closed_set() -> None:
    assert {code.value for code in AgentLauncherRefusal} == {
        "agent_signed_out",
        "agent_runtime_unavailable",
        "agent_service_absent",
        "agent_service_incompatible",
        "agent_provider_credential_missing",
        "agent_service_failed",
        "agent_emergency_cutoff",
    }


@pytest.mark.parametrize("code", ["frame_malformed", "frame_too_large", "provider_unsupported"])
def test_an_agent_that_does_not_speak_the_offered_contract_is_incompatible(code: str) -> None:
    error = AgentHostError(AgentHostRefusal.AGENT_REFUSED, agent_code=code)
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_INCOMPATIBLE


@pytest.mark.parametrize(
    "code", [RefusalCode.UNAVAILABLE, RefusalCode.ENDPOINT_NOT_READY, RefusalCode.DRAINING], ids=str
)
def test_a_runtime_that_is_not_there_to_serve_is_runtime_unavailable(code: RefusalCode) -> None:
    assert runtime_launcher_refusal_for(RefusalError(code)) is AgentLauncherRefusal.RUNTIME_UNAVAILABLE


@pytest.mark.parametrize(
    "code",
    [
        RefusalCode.ENDPOINT_UNTRUSTED,
        RefusalCode.PEER_UNTRUSTED,
        RefusalCode.VERSION_MISMATCH,
        RefusalCode.DEADLINE_EXCEEDED,
        RefusalCode.CONTAINMENT_UNAVAILABLE,
    ],
    ids=str,
)
def test_an_untrusted_or_failed_runtime_exchange_is_not_mistaken_for_absence(code: RefusalCode) -> None:
    assert runtime_launcher_refusal_for(RefusalError(code)) is None
