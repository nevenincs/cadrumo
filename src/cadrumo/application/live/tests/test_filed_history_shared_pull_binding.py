"""The shared filed-history pull binding forwards its arguments and refuses foreign results.

An entrypoint supplies its composition-owned pull through the positional
shared-pull contract; the binding must hand that callback exactly what the
executor passed, with the submitted request itself as the payload, and must not
settle anything other than the canonical onboarding run.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import cast

import pytest

from ...auth.certificate_secret_backend import CertificateSecretBackendFactory
from ...auth.operator_scope_ports import OperatorScopePorts
from ...auth.protocols import BrowserSessionFactoryPort
from ...operations.owner import OperationEventEmitter
from ...storage.sync_runs.records import SyncRunRecordRepositoryProtocol
from ..filed_data_capture import FiledHistoryEventSink, FiledHistoryOnboardingRun
from ..filed_data_ports import FiledDataCapturePort
from ..filed_history_operation import (
    FiledHistoryOperationRequest,
    FiledHistoryPull,
    bind_shared_filed_history_pull,
)
from ..filed_observation_ports import FiledObservationPersistencePorts
from ..iva_remote_state_ports import IvaRemoteStatePort
from ..notification_ports import NotificationsPorts

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Marker:
    """Distinct identity standing in for one composed dependency."""

    def __init__(self, name: str) -> None:
        self.name = name


class _RecordingSharedPull:
    """Record every positional argument and answer with a configured result."""

    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, ...]] = []

    async def __call__(
        self,
        payload: FiledHistoryOperationRequest,
        profile: object,
        repository: SyncRunRecordRepositoryProtocol | None,
        events: FiledHistoryEventSink | None,
        ports: FiledObservationPersistencePorts,
        filed_data_port: FiledDataCapturePort,
        iva_remote_state_port: IvaRemoteStatePort,
        notifications_ports: NotificationsPorts,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        /,
    ) -> object:
        self.calls.append(
            (
                payload,
                profile,
                repository,
                events,
                ports,
                filed_data_port,
                iva_remote_state_port,
                notifications_ports,
                certificate_secret_backend_factory,
                browser_session_factory,
                operator_scope_ports,
            )
        )
        return self.result


def _request() -> FiledHistoryOperationRequest:
    return FiledHistoryOperationRequest(output_root=Path("filed-history-output"), limit=3, dry_run=True)


def _dependencies() -> tuple[object, ...]:
    return tuple(
        _Marker(name)
        for name in (
            "repository",
            "events",
            "ports",
            "filed_data_port",
            "iva_remote_state_port",
            "notifications_ports",
            "certificate_secret_backend_factory",
            "browser_session_factory",
            "operator_scope_ports",
        )
    )


async def _invoke(
    pull: FiledHistoryPull,
    request: FiledHistoryOperationRequest,
    markers: tuple[object, ...],
) -> FiledHistoryOnboardingRun:
    return await pull(
        request,
        None,
        cast(SyncRunRecordRepositoryProtocol, markers[0]),
        cast(OperationEventEmitter, markers[1]),
        cast(FiledObservationPersistencePorts, markers[2]),
        cast(FiledDataCapturePort, markers[3]),
        cast(IvaRemoteStatePort, markers[4]),
        cast(NotificationsPorts, markers[5]),
        cast(CertificateSecretBackendFactory, markers[6]),
        cast(BrowserSessionFactoryPort, markers[7]),
        cast(OperatorScopePorts, markers[8]),
    )


def test_the_binding_forwards_every_argument_with_the_request_as_payload() -> None:
    run = FiledHistoryOnboardingRun(pairs=())
    shared = _RecordingSharedPull(run)
    request = _request()
    markers = _dependencies()

    result = asyncio.run(_invoke(bind_shared_filed_history_pull(shared), request, markers))

    assert result is run
    assert len(shared.calls) == 1
    forwarded = shared.calls[0]
    # The submitted request itself is the payload -- not a projection of it.
    assert forwarded[0] is request
    assert forwarded[1] is None
    assert len(forwarded) == 2 + len(markers)
    for position, marker in enumerate(markers, start=2):
        assert forwarded[position] is marker


def test_the_binding_refuses_a_result_that_is_not_an_onboarding_run() -> None:
    shared = _RecordingSharedPull({"captured_count": 0})

    with pytest.raises(TypeError, match="invalid result"):
        asyncio.run(_invoke(bind_shared_filed_history_pull(shared), _request(), _dependencies()))

    assert len(shared.calls) == 1
