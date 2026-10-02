"""The automation list leaf emits only the settled public inventory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
import typer

from cadrumo.adapters.local_runtime.automation_inventory import (
    AutomationInventoryCompletion,
    AutomationInventoryReadError,
)
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.user_profile.access_contracts import AuthorityState
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationGrantProjection,
    AutomationInventoryProjection,
    AutomationKeyProjection,
    AutomationScopeProjection,
)
from cadrumo.entrypoints.cli.config import runtime_access_management as subject
from cadrumo.entrypoints.cli.config.runtime_access_management_payloads import ConfigProfileAutomationListResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _context() -> typer.Context:
    app = typer.Typer()

    @app.command()
    def noop() -> None:
        return

    return typer.Context(typer.main.get_command(app))


def test_list_uses_bound_profile_and_emits_only_public_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id, client_id, grant_id = uuid4(), uuid4(), uuid4()
    instant = datetime.now(UTC)
    projection = AutomationInventoryProjection(
        grants=(
            AutomationGrantProjection(
                grant_id=grant_id,
                profile_id=profile_id,
                client_id=client_id,
                state=AuthorityState.ACTIVE,
                scope=AutomationScopeProjection(
                    operations=("user-profile.automation-inventory",),
                    actions=(),
                    disclosures=(),
                    periods=None,
                    allow_period_independent=False,
                    allow_delegation=False,
                ),
                valid_from=instant,
                expires_at=instant + timedelta(days=1),
                unattended=False,
                allow_os_lock=False,
            ),
        ),
        keys=(
            AutomationKeyProjection(
                key_id=uuid4(),
                grant_id=grant_id,
                profile_id=profile_id,
                state=AuthorityState.ACTIVE,
                valid_from=instant,
                expires_at=instant + timedelta(days=1),
                last_used_at=None,
            ),
        ),
        requests=(),
    )
    completion = AutomationInventoryCompletion(operation_id="a" * 64, projection=projection)
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=profile_id))
    seen: list[object] = []
    monkeypatch.setattr(subject, "_client", lambda _ctx, *, requested_language: client)

    def read(bound: RuntimeFrontendClient) -> AutomationInventoryCompletion:
        assert bound is client
        return completion

    monkeypatch.setattr(subject, "read_automation_inventory", read)
    monkeypatch.setattr(subject, "emit_envelope", lambda _ctx, **kwargs: seen.append(kwargs))

    subject.automation_list(_context())

    assert len(seen) == 1
    envelope = seen[0]
    assert isinstance(envelope, dict)
    assert envelope["command"] == "config.profile.automation.list"
    result = envelope["result"]
    assert isinstance(result, ConfigProfileAutomationListResult)
    assert result.profile_id == profile_id
    assert result.operation_id == completion.operation_id
    assert result.inventory == projection
    document = result.model_dump_json()
    assert str(grant_id) in document and str(profile_id) in document
    assert "secret" not in document and "verifier" not in document and "dek" not in document
    lines = envelope["lines"]
    assert isinstance(lines, tuple)
    assert any(line.startswith("grant\t") for line in lines)
    assert any(line.startswith("key\t") for line in lines)


def test_post_submit_uncertainty_keeps_operation_identity_without_success_envelope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id = "b" * 64
    client = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=uuid4()))
    monkeypatch.setattr(subject, "_client", lambda _ctx, *, requested_language: client)
    monkeypatch.setattr(
        subject,
        "read_automation_inventory",
        lambda _client: (_ for _ in ()).throw(
            AutomationInventoryReadError(operation_id=operation_id, code="unavailable")
        ),
    )
    emitted: list[object] = []
    monkeypatch.setattr(subject, "emit_envelope", lambda _ctx, **kwargs: emitted.append(kwargs))

    with pytest.raises(AutomationInventoryReadError) as caught:
        subject.automation_list(_context())

    assert caught.value.operation_id == operation_id
    assert emitted == []
