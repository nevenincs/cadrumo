"""A readiness read releases the certificate file's configured path, whoever submitted it.

The real executor runs the read and the real projector releases it. The two
readiness services are the only stand-ins: they supply a result that carries a
synthetic certificate path, in the member that holds it and in the summaries
that quote it. The executor is told nothing about the submitting frontend, so
one result serves every frontend.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import PurePath
from types import SimpleNamespace
from typing import Literal, cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...state_projection_ports import StateProjectionReadPorts
from .. import read_operation
from ..auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
    AuthReadResult,
)
from ..certificate_secret_backend import CertificateSecretBackendFactory
from ..diagnostics_ports import AuthDiagnosticPersistencePort
from ..operator_probe_ports import OperatorProbePorts
from ..operator_results import AuthStatusResult, AuthTestResult
from ..operator_scope_ports import OperatorScopePorts
from ..probes import ProviderProbeResult
from ..read_operation import AuthReadExecutor, AuthReadPorts, project_auth_read_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_PATHS = ("C:\\synthetic\\certificates\\holder.p12", "/synthetic/certificates/holder.p12", "")
_SUMMARY_WORDING = "certificate file not found: {path}"
_Kind = Literal["status", "test"]


def _readiness(path: str, kind: _Kind) -> AuthStatusResult:
    summary = _SUMMARY_WORDING.format(path=path)
    if kind == "status":
        return AuthStatusResult(provider="certificate", certificate_path=path, health_summary=summary)
    return AuthTestResult(
        provider="certificate",
        certificate_path=path,
        health_summary=summary,
        probe_summary=_SUMMARY_WORDING.format(path=str(PurePath(path))),
        probe_result=ProviderProbeResult.FILE_MISSING,
    )


class _Recorder:
    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.result: BaseModel | None = None

    async def phase(self, code: str) -> None:
        assert code == "auth.local-read.execute"

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        self.result = value
        return "b" * 64


def _run(
    monkeypatch: pytest.MonkeyPatch, authority: PinnedAuthorityOperation, *, kind: _Kind, path: str
) -> AuthReadProjection:
    """Execute the read over a readiness that holds ``path``, then release it through the registered projector."""
    readiness = _readiness(path, kind)
    monkeypatch.setattr(read_operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(read_operation, "inspect_operator_auth", lambda *_args, **_kwargs: readiness)
    monkeypatch.setattr(read_operation, "test_operator_auth", lambda *_args, **_kwargs: readiness)
    ports = AuthReadPorts(
        certificate_secret_backend_factory=cast(CertificateSecretBackendFactory, object()),
        operator_probe_ports=cast(OperatorProbePorts, object()),
        operator_scope_ports=cast(OperatorScopePorts, object()),
        read_ports=cast(StateProjectionReadPorts, object()),
        diagnostics_persistence=cast(AuthDiagnosticPersistencePort, object()),
    )
    identity = OperationIdentity(
        operation_id="a" * 64,
        definition_id=AUTH_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
    )
    recorder = _Recorder()
    context = cast(
        OperationExecutorContext,
        SimpleNamespace(identity=identity, events=recorder, operands=recorder, authority_operation=authority),
    )
    request = OperationRequest[AuthReadRequest](
        definition_id=AUTH_READ_OPERATION_DEFINITION_ID,
        subject_ref=identity.subject_ref,
        payload=AuthReadRequest(profile_id=_PROFILE, kind=kind),
    )

    asyncio.run(AuthReadExecutor(lambda _profile: ports).execute(request, context))

    assert recorder.effects == [OperationEffect.NONE]
    assert isinstance(recorder.result, AuthReadResult)
    receipt = OperationTerminalReceipt(
        identity=identity,
        revision=1,
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        settled_at=datetime(2026, 10, 11, tzinfo=UTC),
        result_ref="b" * 64,
    )
    projection = project_auth_read_result(recorder.result, receipt)
    assert isinstance(projection, AuthReadProjection)
    return projection


@pytest.mark.parametrize("kind", ["status", "test"])
@pytest.mark.parametrize("path", _PATHS, ids=["windows-spelling", "posix-spelling", "unconfigured"])
def test_the_read_releases_the_configured_certificate_path_and_the_summaries_that_quote_it(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    kind: _Kind,
    path: str,
) -> None:
    released = _run(monkeypatch, authority_operation, kind=kind, path=path)

    readiness = released.status if kind == "status" else released.test
    assert readiness is not None
    assert readiness.certificate_path == path
    assert readiness.health_summary == _SUMMARY_WORDING.format(path=path)
    if released.test is not None:
        assert released.test.probe_summary == _SUMMARY_WORDING.format(path=str(PurePath(path)))
    restored = released.to_result()
    assert (restored.status or restored.test) == _readiness(path, kind)
