"""The lanes read answers what ``status`` says of the lanes without running a supplier check.

The provider store, the catalogue parser, the lane projection and the service's
administration all run for real. Only the provider command-line probe is
supplied, through the seam the settings service takes, so each call can be counted.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import SecretStr

from cadrumo.core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from cadrumo_client.transport.service_client import InstalledServiceClient

from ...adapters.agent_programs import PACKAGE_AGENT_VARIABLE
from ...providers.application.contracts import CliObservation, CliState, ProviderSettingsActionAccepted
from ...providers.application.ports import StoreRefusal, StoreRefusalCode
from ...providers.application.service import ProviderSettingsService
from ...providers.application.tests.memory_store import MemoryProviderSettingsStore
from ...providers.application.tests.synthetic_catalog import (
    KEY_LANE,
    SIGN_IN_ONLY_LANE,
    StaticCatalogSource,
    synthetic_catalog,
)
from ...providers.domain.catalog import ProviderCatalogEntry
from ...providers.domain.record import LocalEngine
from ...service import AgentService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUSY = {"kind": "refused", "code": "busy"}


class _CountingProbe:
    """The provider command-line probe, counting the lanes it was asked about."""

    def __init__(self) -> None:
        self.lanes: list[str] = []

    def __call__(self, entry: ProviderCatalogEntry) -> CliObservation:
        self.lanes.append(entry.id)
        return CliObservation(CliState.INSTALLED_SIGNED_IN)


def _service(
    tmp_path: Path, store: MemoryProviderSettingsStore, probe: _CountingProbe, *, lease: object | None = None
) -> AgentService:
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(
            InstalledServiceClient,
            SimpleNamespace(lease=object() if lease is None else lease, connection=SimpleNamespace(close=lambda: None)),
        ),
        storage_root=tmp_path,
        gateway_bearer=bytearray(b"synthetic-gateway-bearer"),
        emit=lambda _event: None,
    )
    service._providers = ProviderSettingsService(
        selected_engine=lambda: LocalEngine.LLAMACPP,
        store=store,
        catalog_source=StaticCatalogSource(),
        cli_state_probe=probe,
    )
    return service


def _status(service: AgentService) -> dict[str, Any]:
    """The kept status read, observed again until it answers."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        answer = service.admin("status")
        if answer != _BUSY:
            return answer
        time.sleep(0.01)
    raise AssertionError("the status read never settled")


@pytest.fixture(autouse=True)
def _no_agent_image(monkeypatch: pytest.MonkeyPatch) -> None:
    # With no packaged agent image the sign-in capability read is unavailable, as it is outside a package.
    monkeypatch.delenv(PACKAGE_AGENT_VARIABLE, raising=False)


def test_the_lanes_read_runs_no_probe_while_status_probes_every_cli_lane(tmp_path: Path) -> None:
    probe = _CountingProbe()
    service = _service(tmp_path, MemoryProviderSettingsStore(), probe)
    cli_lanes = sorted(entry.id for entry in synthetic_catalog().providers if entry.cli_programs)
    assert len(cli_lanes) > 1

    lanes = service.admin("provider_lanes")
    again = service.admin("provider_lanes")

    assert probe.lanes == []
    assert lanes == again

    _status(service)

    assert sorted(probe.lanes) == cli_lanes

    probed = len(probe.lanes)
    service.admin("provider_lanes")

    assert len(probe.lanes) == probed


def test_the_lanes_read_is_the_providers_part_of_status_for_the_same_state(tmp_path: Path) -> None:
    store = MemoryProviderSettingsStore()
    service = _service(tmp_path, store, _CountingProbe())
    stored = service._providers.set_credential(
        KEY_LANE, secret=SecretStr("synthetic-profile-key"), expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID
    )
    assert isinstance(stored, ProviderSettingsActionAccepted)
    off = service._providers.turn_off(KEY_LANE, expected_revision=stored.entry.revision)
    assert isinstance(off, ProviderSettingsActionAccepted)

    status = _status(service)
    lanes = service.admin("provider_lanes")

    assert set(lanes) == {"providers"}
    assert [lane["id"] for lane in lanes["providers"]] == [lane["id"] for lane in status["providers"]]
    unlike = []
    for from_lanes, from_status in zip(lanes["providers"], status["providers"], strict=True):
        assert set(from_lanes) == set(from_status)
        differing = {key for key in from_lanes if from_lanes[key] != from_status[key]}
        if from_lanes["transport"] == "api":
            assert differing == set()
            continue
        # A cli lane's own app state is the one fact only the probe reads.
        assert from_status["cli_state"] == "installed_signed_in"
        assert from_lanes["cli_state"] == "unknown"
        assert differing <= {"cli_state", "available", "readiness", "reason"}
        if differing != {"cli_state"}:
            unlike.append(from_lanes["id"])
    assert unlike == [SIGN_IN_ONLY_LANE]
    assert any(lane["id"] == KEY_LANE and lane["mode"] == "disabled" for lane in lanes["providers"])
    assert "synthetic-profile-key" not in repr(lanes)


def test_the_lanes_read_refuses_as_status_does_and_probes_nothing(tmp_path: Path) -> None:
    store = MemoryProviderSettingsStore()
    probe = _CountingProbe()
    service = _service(tmp_path, store, probe)
    store.refusal = StoreRefusal(code=StoreRefusalCode.PROFILE_LOCKED)

    assert service.admin("provider_lanes") == {"code": "profile_locked"}
    assert _status(service) == {"code": "profile_locked"}
    assert probe.lanes == []


def test_the_lanes_read_is_refused_while_signed_out_or_stopping(tmp_path: Path) -> None:
    probe = _CountingProbe()
    signed_out = _service(tmp_path, MemoryProviderSettingsStore(), probe)
    cast(Any, signed_out.client).lease = None

    assert signed_out.admin("provider_lanes") == {"kind": "refused", "code": "signed_out"}

    stopping = _service(tmp_path, MemoryProviderSettingsStore(), probe)
    stopping._closing.set()

    assert stopping.admin("provider_lanes") == {"kind": "refused", "code": "service_stopping"}
    assert probe.lanes == []
