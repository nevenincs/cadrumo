"""The filed-data capture port keeps an authentication failure's own error code."""

from __future__ import annotations

import asyncio

import pytest

from ......application.live.errors import LiveApplicationError
from ...auth.clave_movil_support import ClaveMovilApprovalTimeoutError
from ..filed_data_capture_port import _call_adapter

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_an_unapproved_clave_login_reaches_the_operation_as_itself() -> None:
    async def login_times_out() -> None:
        raise ClaveMovilApprovalTimeoutError("approval window elapsed")

    with pytest.raises(ClaveMovilApprovalTimeoutError):
        asyncio.run(_call_adapter("open_register", login_times_out))


def test_a_sede_failure_is_still_translated_into_the_live_vocabulary() -> None:
    async def register_breaks() -> None:
        raise RuntimeError("synthetic sede failure")

    with pytest.raises(LiveApplicationError) as translated:
        asyncio.run(_call_adapter("open_register", register_breaks))

    assert isinstance(translated.value.__cause__, RuntimeError)
