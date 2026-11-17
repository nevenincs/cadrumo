"""Runtime session refusals retire the TUI's private root."""

from datetime import timedelta
from typing import override
from uuid import uuid4

import pytest

from cadrumo.core.time.clock import now
from cadrumo.entrypoints.tui.account import AccountRecomposeReasonV1
from cadrumo.entrypoints.tui.app import CadrumoTuiApp
from cadrumo_client.contracts.access_refusals import AccessDenialCode, ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import AccessScope, Availability, EffectiveScopeSummary
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_runtime.host.frontend.tui.runtime_account_session import runtime_account_session_reader

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class StatusClient(FrontendClient):
    def __init__(self) -> None:
        self._profile_id = uuid4()
        self._session_id = uuid4()
        self.observed = ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=self.profile_id,
            session_id=self.session_id,
            session_expires_at=now() + timedelta(minutes=10),
            grant_state=None,
            grant_expires_at=None,
            grant_valid=False,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.NOT_REQUIRED,
            published_authority=Availability.AVAILABLE,
            provider=Availability.NOT_REQUIRED,
            effective_scope=EffectiveScopeSummary.summarize(
                AccessScope(
                    operations=frozenset(),
                    actions=frozenset(),
                    disclosures=frozenset(),
                    periods=frozenset(),
                    allow_period_independent=False,
                    allow_delegation=False,
                )
            ),
            denial=None,
        )

    @override
    def status(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> ProfileStatus:
        return ProfileStatus(request_id=uuid4(), runtime_boot_id=uuid4(), connection_id=uuid4(), status=self.observed)


@pytest.mark.asyncio
@pytest.mark.parametrize("condition", ("expired", "missing", "foreign_session", "foreign_profile", "unavailable"))
async def test_runtime_reader_refusal_clears_the_private_root(condition: str) -> None:
    client = StatusClient()
    reader = runtime_account_session_reader(client, profile_id=client.profile_id, profile_label="Current profile")
    initial = await reader()
    if condition == "expired":
        client.observed = client.observed.model_copy(update={"session_expires_at": now() - timedelta(seconds=1)})
    elif condition == "missing":
        client.observed = client.observed.model_copy(update={"session_expires_at": None})
    elif condition == "foreign_session":
        client.observed = client.observed.model_copy(update={"session_id": uuid4()})
    elif condition == "foreign_profile":
        client.observed = client.observed.model_copy(update={"profile_id": uuid4()})
    else:
        client.observed = client.observed.model_copy(update={"denial": AccessDenialCode.BACKEND_UNAVAILABLE})

    app = CadrumoTuiApp(read_account_session=reader)
    async with app.run_test():
        app._account_session = initial
        await app._poll_account_session()
        expected = (
            AccountRecomposeReasonV1.UNAVAILABLE if condition == "unavailable" else AccountRecomposeReasonV1.EXPIRED
        )
        assert app.return_value is not None and app.return_value.reason is expected
        assert app.account_session is None
        assert app._read_account_session is None
