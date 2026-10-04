"""The filed-data capture port keeps an authentication failure's own error code."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest

from ......application.auth.certificate_secret_backend import CertificateSecretBackendFactory
from ......application.auth.operator_scope_ports import OperatorScopePorts
from ......application.auth.protocols import BrowserSessionFactoryPort
from ......application.live.errors import LiveApplicationError
from ......domain.calculations.registry.authority import PinnedAuthorityOperation
from ...auth.clave_movil_support import ClaveMovilApprovalTimeoutError
from .. import filed_data_capture_port
from ..filed_data_capture_port import SedeFiledDataCapturePort, _call_adapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_an_unapproved_clave_login_reaches_the_operation_as_itself() -> None:
    async def login_times_out() -> None:
        raise ClaveMovilApprovalTimeoutError("approval window elapsed")

    with pytest.raises(ClaveMovilApprovalTimeoutError):
        asyncio.run(_call_adapter("open_register", login_times_out))


def test_opening_the_register_keeps_an_unapproved_clave_login_as_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    async def login_times_out(**_: object) -> None:
        raise ClaveMovilApprovalTimeoutError("approval window elapsed")

    monkeypatch.setattr(filed_data_capture_port, "active_verified_session", login_times_out)
    port = SedeFiledDataCapturePort(
        certificate_secret_backend_factory=cast(CertificateSecretBackendFactory, object()),
        browser_session_factory=cast(BrowserSessionFactoryPort, object()),
        operator_scope_ports=cast(OperatorScopePorts, object()),
    )

    async def open_it() -> None:
        async with port.open_register(
            operation="live.filed-list", authority_operation=cast(PinnedAuthorityOperation, object())
        ):
            pytest.fail("the register opened without an authenticated session")

    with pytest.raises(ClaveMovilApprovalTimeoutError):
        asyncio.run(open_it())


def test_a_sede_failure_is_still_translated_into_the_live_vocabulary() -> None:
    async def register_breaks() -> None:
        raise RuntimeError("synthetic sede failure")

    with pytest.raises(LiveApplicationError) as translated:
        asyncio.run(_call_adapter("open_register", register_breaks))

    assert isinstance(translated.value.__cause__, RuntimeError)
