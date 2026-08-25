"""Public lifecycle and validation contracts for ``AeatAuthenticator``.

Browser ownership and certificate context construction are exercised through
real Playwright in the browser factory and certificate suites. Exact protected
resource acceptance remains the credential-gated live oracle; this module does
not manufacture browser responses or mutate authenticator lifecycle internals.
"""

from __future__ import annotations

import asyncio

import pytest

from ......application.auth_credentials import ActiveCertificateCredentials
from ......core.config import Settings
from ..authenticator import AeatAuthenticator
from . import _authenticator_support as _support

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.mark.asyncio
async def test_concurrent_close_calls_complete_through_the_public_lifecycle() -> None:
    """Concurrent public close calls serialize and remain idempotent."""
    authenticator = AeatAuthenticator(
        Settings(),
        credentials=ActiveCertificateCredentials(
            certificate_path=None,
            password=None,
            friendly_name=None,
        ),
    )

    await asyncio.wait_for(
        asyncio.gather(
            authenticator.close(),
            authenticator.close(),
            authenticator.close(),
        ),
        timeout=1.0,
    )
    await asyncio.wait_for(authenticator.close(), timeout=1.0)


# Re-export network-free public contracts from the shared support module. Tests
# that fabricated browser responses or mutated private lifecycle state were
# intentionally retired in favour of real Playwright/process coverage and the
# external live protected-resource oracle.
test_authenticator_synchronous_surface = _support.test_authenticator_synchronous_surface
test_reauthenticate_does_not_deadlock = _support.test_reauthenticate_does_not_deadlock
test_verify_raises_on_stale_session = _support.test_verify_raises_on_stale_session
test_verify_raises_without_context = _support.test_verify_raises_without_context
