"""CLI attestation refuses foreign and wrong targets before runtime submission."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError

from ....application.modelo.m303_attestation_operation import ModeloWorkM303AttestationRequest
from ....application.operations.public_period import PublicPeriod
from ..operation_modelo_attestation import run_modelo_m303_attestation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_OTHER = UUID("6bb00000-0000-4000-8000-0000000000bb")
_OBSERVED = datetime(2026, 12, 31, 10, tzinfo=UTC)


def _client() -> FrontendClient:
    return cast(FrontendClient, cast(object, SimpleNamespace(profile_id=_PROFILE)))


def test_foreign_profile_refused_before_runtime_call() -> None:
    request = ModeloWorkM303AttestationRequest(
        profile_id=_OTHER,
        period=PublicPeriod(filing_year=2026, code="4T"),
        observed_at=_OBSERVED,
        actor="operator",
    )
    with pytest.raises(FrontendRefusedError, match="profile_mismatch"):
        run_modelo_m303_attestation(_client(), request)


def test_work_unit_target_refused_before_runtime_call() -> None:
    request = ModeloWorkM303AttestationRequest(
        profile_id=_PROFILE, work_unit_id="a" * 64, observed_at=_OBSERVED, actor="operator"
    )
    with pytest.raises(RefusalError) as caught:
        run_modelo_m303_attestation(_client(), request)
    assert caught.value.reason is RefusalCode.INVALID_FRAME
