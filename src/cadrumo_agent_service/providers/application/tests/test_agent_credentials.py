"""Catalog failures retain their cause instead of asking the person to replace credentials."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast, override
from uuid import uuid4

import pytest

from cadrumo.tests.log_records import delivered_text
from cadrumo_client.contracts import deadline_budget
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.contracts.extension_records import ExtensionRecordReply, ExtensionRecordRequest
from cadrumo_client.contracts.service_access import ServiceConnect, ServiceConnected, ServiceLease
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.service_client import InstalledServiceClient

from ....host.controller import AgentHostError, AgentHostRefusal
from ....host.launcher_protocol import AgentLauncherRefusal, launcher_refusal_for
from ...domain.catalog import ProviderCatalog
from ...persistence.store import SecureProviderSettingsStore
from ..agent_credentials import ProviderSettingsAgentCredentialSource
from ..ports import (
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    ProviderCatalogUnavailableReason,
    StoreGenerations,
)
from ..resolution import ProviderCredentialResolver
from .memory_store import MemoryProviderSettingsStore
from .synthetic_catalog import StaticCatalogSource

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _SignedInStore(MemoryProviderSettingsStore):
    @override
    def observe_generations(self, *, deadline: TimeoutDeadline | None = None) -> StoreGenerations:
        return StoreGenerations(sign_in="a" * 64, provider_settings="b" * 64)


class _UnavailableCatalog(ProviderCatalogSource):
    def __init__(self, reason: ProviderCatalogUnavailableReason) -> None:
        self.reason = reason

    @override
    def catalog(self, *, deadline: TimeoutDeadline | None = None) -> ProviderCatalog:
        raise ProviderCatalogUnavailableError(self.reason)


def _source(catalog: ProviderCatalogSource) -> ProviderSettingsAgentCredentialSource:
    store = _SignedInStore()
    return ProviderSettingsAgentCredentialSource(
        store=store,
        resolver=ProviderCredentialResolver(store=store, catalog_source=catalog),
        catalog_source=catalog,
    )


@pytest.mark.parametrize(
    ("reason", "host_refusal", "launcher_refusal"),
    [
        (
            ProviderCatalogUnavailableReason.CATALOG_MALFORMED,
            AgentHostRefusal.AGENT_INCOMPATIBLE,
            AgentLauncherRefusal.SERVICE_INCOMPATIBLE,
        ),
        (
            ProviderCatalogUnavailableReason.AGENT_NOT_FOUND,
            AgentHostRefusal.LAUNCH_FAILED,
            AgentLauncherRefusal.SERVICE_FAILED,
        ),
        (
            ProviderCatalogUnavailableReason.AGENT_FAILED,
            AgentHostRefusal.LAUNCH_FAILED,
            AgentLauncherRefusal.SERVICE_FAILED,
        ),
        (
            ProviderCatalogUnavailableReason.AGENT_TIMED_OUT,
            AgentHostRefusal.LAUNCH_FAILED,
            AgentLauncherRefusal.SERVICE_FAILED,
        ),
    ],
)
def test_catalog_failure_retains_its_category_and_safe_diagnostic(
    reason: ProviderCatalogUnavailableReason,
    host_refusal: AgentHostRefusal,
    launcher_refusal: AgentLauncherRefusal,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING), pytest.raises(AgentHostError) as refused:
        _source(_UnavailableCatalog(reason)).resolve_for_agent()

    assert refused.value.reason is host_refusal
    assert launcher_refusal_for(refused.value) is launcher_refusal
    assert isinstance(refused.value.__cause__, ProviderCatalogUnavailableError)
    assert f"agent provider catalog unavailable reason={reason.value}" in delivered_text(caplog)


def test_unset_credentials_do_not_prevent_a_valid_agent_from_starting() -> None:
    resolved = _source(StaticCatalogSource()).resolve_for_agent()

    assert resolved.credentials == {}
    assert resolved.generations.sign_in == "a" * 64


def test_signed_out_profile_is_refused_before_reading_the_catalog() -> None:
    store = MemoryProviderSettingsStore()
    catalog = _UnavailableCatalog(ProviderCatalogUnavailableReason.CATALOG_MALFORMED)
    source = ProviderSettingsAgentCredentialSource(
        store=store,
        resolver=ProviderCredentialResolver(store=store, catalog_source=catalog),
        catalog_source=catalog,
    )

    with pytest.raises(AgentHostError) as refused:
        source.resolve_for_agent()

    assert refused.value.reason is AgentHostRefusal.SIGNED_OUT


def test_credential_resolution_preserves_one_deadline_through_all_native_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1005.0]
    monkeypatch.setattr(deadline_budget, "time", SimpleNamespace(monotonic=lambda: now[0]))
    owner = deadline_budget.TimeoutDeadline(1020.0)
    lease = ServiceLease(
        lease_id=uuid4(),
        session_id=uuid4(),
        profile_id=uuid4(),
        parent_session_id=uuid4(),
        descriptor_digest="a" * 64,
        service_id="cadrumo-agent-service",
        runtime_boot_id=uuid4(),
        connection_id=uuid4(),
    )
    observed: list[tuple[float, float]] = []

    class Runtime:
        def service_access(self, request: ServiceConnect, *, deadline: float) -> ServiceConnected:
            observed.append((deadline, deadline - now[0]))
            now[0] += 1
            return ServiceConnected(
                request_id=request.request_id,
                runtime_boot_id=lease.runtime_boot_id,
                connection_id=lease.connection_id,
                profile_id=lease.profile_id,
                service_id=lease.service_id,
                lease=lease,
            )

        def extension_record(
            self, request: ExtensionRecordRequest, *, deadline: float
        ) -> tuple[ExtensionRecordReply, bytearray]:
            observed.append((deadline, deadline - now[0]))
            now[0] += 1
            return ExtensionRecordReply(
                request_id=request.request_id,
                runtime_boot_id=lease.runtime_boot_id,
                connection_id=lease.connection_id,
                state="generation" if request.action == "extension_record_generation" else "absent",
                custody_generation="b" * 64,
                records_generation="c" * 64,
            ), bytearray()

    client = InstalledServiceClient(
        cast(VerifiedConnection, Runtime()),
        profile_id=lease.profile_id,
        service_id=lease.service_id,
        startup_deadline=deadline_budget.TimeoutDeadline(1030.0),
    )
    store = SecureProviderSettingsStore(client=client)
    catalog = StaticCatalogSource()
    source = ProviderSettingsAgentCredentialSource(
        store=store,
        catalog_source=catalog,
        resolver=ProviderCredentialResolver(store=store, catalog_source=catalog),
    )
    resolved = source.resolve_for_agent(deadline=owner)
    assert resolved.generations.provider_settings == "c" * 64
    assert len(observed) >= 3, "the claim, generation and provider records must all use the owner's deadline"
    assert all(deadline == owner.instant for deadline, _remaining in observed)
    assert [remaining for _deadline, remaining in observed] == [15.0 - index for index in range(len(observed))]
