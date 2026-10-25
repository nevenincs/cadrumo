"""Choosing provider-owned authentication does not establish remote readiness."""

from __future__ import annotations

import json

import pytest

from ...domain.record import ProviderSettingsRecord
from ..contracts import CliState, ProviderReadiness, ProviderStatusReason
from ..ports import AbsentProviderRecord, StoredProviderRecord, UnreadableProviderRecord
from ..resolution import status_entry
from .synthetic_catalog import synthetic_catalog

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("state", ["absent", "selected", "unreadable"])
@pytest.mark.parametrize("cli_state", list(CliState))
def test_cli_sign_in_status_distinguishes_selection_from_missing_and_unusable(state: str, cli_state: CliState) -> None:
    lane = synthetic_catalog().entry("example_cli")
    assert lane is not None
    if state == "selected":
        record = ProviderSettingsRecord.model_validate_json(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": "example",
                    "assistant_auth": "provider_sign_in",
                    "credential_state": "unset",
                    "generation": "a" * 64,
                    "updated_at": "2026-10-18T00:00:00Z",
                }
            )
        )
        read = StoredProviderRecord(record=record, revision="b" * 64)
    elif state == "absent":
        read = AbsentProviderRecord(provider="example")
    else:
        read = UnreadableProviderRecord(provider="example", revision=None)
    status = status_entry(lane, read, cli_state=cli_state)
    if state != "unreadable" and cli_state is CliState.INSTALLED_SIGNED_IN:
        assert status.readiness is ProviderReadiness.NOT_VERIFIED
        assert status.reason is None
        assert status.available
    elif state != "unreadable":
        assert not status.available
        assert status.readiness is ProviderReadiness.SIGN_IN_REQUIRED
        assert status.reason is ProviderStatusReason.SIGN_IN_WITH_PROVIDER_TOOL
    else:
        assert status.readiness is ProviderReadiness.UNUSABLE
        assert not status.available
