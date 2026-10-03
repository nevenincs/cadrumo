"""Public JSON shape for the Google storage-provider probe result."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....adapters.outbound.storage.records import ProviderKind
from .._google_payloads import GoogleSyncProbeResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_google_sync_probe_payload_accepts_unknown_root_folder_presence() -> None:
    result = GoogleSyncProbeResult(
        profile="profile-id",
        provider_kind=ProviderKind.LOCAL_FILESYSTEM,
        reachable=True,
        writable=False,
        read_only=True,
        root_folder_present=None,
        root_folder_id="",
        detail="probe reached backend; root folder presence is not applicable",
    )

    assert result.root_folder_present is None
    assert result.model_dump()["root_folder_present"] is None


@pytest.mark.parametrize("provider_kind", ["", "bogus"])
def test_google_sync_probe_payload_refuses_unknown_provider_kind(provider_kind: str) -> None:
    """The CLI probe contract admits only backends the provider can report."""
    with pytest.raises(ValidationError, match="ProviderKind"):
        GoogleSyncProbeResult(
            profile="profile-id",
            provider_kind=provider_kind,
            reachable=True,
            writable=False,
            read_only=True,
            root_folder_present=None,
            root_folder_id="",
        )


__all__ = [
    "test_google_sync_probe_payload_accepts_unknown_root_folder_presence",
    "test_google_sync_probe_payload_refuses_unknown_provider_kind",
]
